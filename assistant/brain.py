"""The 'brain': builds context from the vault and calls Claude via the Agent SDK."""

import base64
import os
from datetime import date
from pathlib import Path

from claude_agent_sdk import AssistantMessage, ClaudeAgentOptions, ResultMessage, ToolUseBlock, query

from tools import SKIP_DIRS, TOOL_NAMES, make_vault_server

# Short names you can use in Discord -> real model IDs
MODELS = {
    "haiku": "claude-haiku-5-5",
    "sonnet": "claude-sonnet-5-5",
    "opus": "claude-opus-5-5",
}
DEFAULT_MODEL = "haiku"

MAX_TURNS = 10  # model calls per message; each tool round trip is one

# Always loaded first, in this order. Missing files are skipped.
CONTEXT_FILES = [
    "CLAUDE.md",        # shared vault rules: Claudian / Claude Code read this too
    "Agent/SOUL.md",    # personality, only for this bot
    "Agent/MEMORY.md",  # index of durable facts
]


def read_if_exists(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return None


def frontmatter(text: str) -> dict[str, str]:
    """Tiny parser for the '---' block at the top of a note.
    Only reads simple 'key: value' lines, which is all pinning needs."""
    if not text.startswith("---"):
        return {}
    end = text.find("\n---", 3)
    if end == -1:
        return {}
    fields = {}
    for line in text[3:end].splitlines():
        key, sep, value = line.partition(":")
        if sep:
            fields[key.strip()] = value.strip().strip("\"'")
    return fields


def pinned_notes(vault: Path) -> list[str]:
    """Every note with 'agent: pin' in its frontmatter, as vault-relative paths."""
    found = []
    for root, dirs, files in os.walk(vault):
        # Editing dirs in place stops os.walk from descending into them
        dirs[:] = [d for d in dirs if d not in SKIP_DIRS and not d.startswith(".")]
        for name in files:
            if not name.endswith(".md") or ".sync-conflict-" in name:
                continue
            path = Path(root, name)
            try:
                with path.open(encoding="utf-8") as f:
                    head = f.read(2000)  # frontmatter is at the top; no need to read it all
            except (OSError, UnicodeDecodeError):
                continue
            if frontmatter(head).get("agent") == "pin":
                found.append(path.relative_to(vault).as_posix())
    return sorted(found)


def build_system_prompt(vault: Path, daily_dir: str) -> tuple[str, list[str]]:
    """Return the system prompt and the list of files that went into it."""
    parts, loaded = [], []

    pinned = [p for p in pinned_notes(vault) if p not in CONTEXT_FILES]
    for rel in CONTEXT_FILES + pinned:
        text = read_if_exists(vault / rel)
        if text:
            parts.append(f"## {rel}\n{text}")
            loaded.append(rel)

    today_rel = f"{daily_dir}/{date.today().isoformat()}.md"
    today = read_if_exists(vault / today_rel)
    if today:
        parts.append(f"## Today's note ({today_rel})\n{today}")
        loaded.append(today_rel)

    parts.append(f"Today's date is {date.today().isoformat()}.")
    return "\n\n".join(parts), loaded


def with_images(prompt: str, images: list[tuple[str, bytes]] | None):
    """Plain text stays a string. With images, build one user message whose content
    is the image blocks followed by the text (the SDK's streaming-input format)."""
    if not images:
        return prompt
    content = [
        {"type": "image", "source": {"type": "base64", "media_type": media_type,
                                     "data": base64.b64encode(data).decode("ascii")}}
        for media_type, data in images
    ]
    content.append({"type": "text", "text": prompt})

    async def stream():
        yield {"type": "user", "message": {"role": "user", "content": content},
               "parent_tool_use_id": None, "session_id": ""}

    return stream()


async def ask(
    prompt: str,
    system_prompt: str,
    model: str,
    cwd: Path,
    session_id: str | None = None,
    images: list[tuple[str, bytes]] | None = None,
    escalate_to: list[str] | None = None,
    links: list[str] | None = None,
    web_read: bool = False,
) -> tuple[str, dict, str | None, list[dict]]:
    """Send one message to Claude, continuing `session_id` if given. `cwd` is the vault.
    `images` is a list of (media type, raw bytes), sent along with the text.
    `escalate_to` lists models it may hand the message to (adds the escalate tool).
    `links` are URLs the user sent in this conversation (adds read_link; None = no web access).
    `web_read`: the conversation already read a web page, so writes need the user's approval.
    Returns (reply text, usage info for the log, session id to save, vault actions)."""
    actions: list[dict] = []  # filled by the vault tools: what was saved or proposed
    options = ClaudeAgentOptions(
        model=MODELS[model],
        # snapshot=False: use this message's system prompt. Otherwise a resumed session
        # keeps the prompt from its first message and never sees today's daily note,
        # new memories or edits to SOUL.md.
        system_prompt={"type": "custom", "prompt": system_prompt, "snapshot": False},
        tools=[],            # no built-in tools (no shell, no free file access)...
        mcp_servers={"vault": make_vault_server(cwd, actions, escalate_to, links, web_read)},
        # ...only our vault tools, which enforce the rules in code
        allowed_tools=TOOL_NAMES + (["mcp__vault__escalate"] if escalate_to else [])
        + (["mcp__vault__read_link"] if links is not None else []),
        strict_mcp_config=True,  # only our vault server: not the claude.ai account connectors
        setting_sources=[],  # we load CLAUDE.md ourselves, so skip Claude Code's own settings
        max_turns=MAX_TURNS,
        cwd=str(cwd),        # sessions are stored per working directory, so keep it fixed
        resume=session_id,   # None = new conversation
    )

    reply, meta, new_session = "", {}, session_id
    tools_used = []
    async for message in query(prompt=with_images(prompt, images), options=options):
        if isinstance(message, AssistantMessage):
            for block in message.content:
                if isinstance(block, ToolUseBlock):
                    tools_used.append(block.name.removeprefix("mcp__vault__"))
        elif isinstance(message, ResultMessage):
            reply = message.result or ""
            if not reply and message.subtype == "error_max_turns":
                reply = f"(I hit the {MAX_TURNS}-step limit before finishing. Try a narrower question.)"
            new_session = message.session_id
            usage = message.usage or {}
            meta = {
                "input_tokens": usage.get("input_tokens", 0),
                "output_tokens": usage.get("output_tokens", 0),
                "cache_read_tokens": usage.get("cache_read_input_tokens", 0),
                "cache_write_tokens": usage.get("cache_creation_input_tokens", 0),
                "cost_usd_equiv": message.total_cost_usd,
                "duration_ms": message.duration_ms,
                "is_error": message.is_error,
                "num_turns": message.num_turns,
                "result": message.subtype,
            }
    meta["tools_used"] = tools_used
    return reply, meta, new_session, actions
