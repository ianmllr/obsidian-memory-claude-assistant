"""Discord gateway: receives your messages, asks the brain, replies, logs usage.

Channels:
  #chat   conversations. A message here starts a thread; replies in the thread
          continue the same Claude session (saved to disk, survives restarts).
  #quick  quick capture. Anything posted here is filed into today's daily note
          with tags and links, confirmed in one line. No thread, no memory.
  DMs     one running conversation, like a thread. Heartbeat messages arrive here.

The bot can save facts to Agent/MEMORY.md on its own. Edits to existing notes are
shown as a diff with Approve/Reject buttons and only applied when the user approves.
Pending proposals are saved to disk, so the buttons still work after a restart.
"""

import asyncio
import json
import os
import time
import uuid
from pathlib import Path

import discord
from dotenv import load_dotenv

from brain import DEFAULT_MODEL, MODELS, ask, build_system_prompt
from heartbeat import Heartbeat
from tools import MEMORY_FILE, VaultError, apply_edit, render_diff

load_dotenv()

TOKEN = os.environ["DISCORD_TOKEN"]
OWNER_ID = int(os.environ["OWNER_ID"])
VAULT = Path(os.environ["VAULT_PATH"]).expanduser()
DAILY_DIR = os.environ.get("DAILY_DIR", "Agent/daily")
CHAT_CHANNEL = os.environ.get("CHAT_CHANNEL", "chat")
QUICK_CHANNEL = os.environ.get("QUICK_CHANNEL", "quick")

QUICK_PROMPT = """The user dropped this into #quick, their quick-capture channel:

{text}

File it with the capture tool (or remember, if it's a lasting fact about them). Decide
whether it's a task. Check list_tags and reuse existing tags where they fit. Use
search_vault to find one or two existing notes it relates to and pass them as links.
Then reply with ONE short line saying what you saved. Don't ask follow-up questions."""

HERE = Path(__file__).parent
LOG_FILE = HERE / "logs" / "usage.jsonl"
SESSIONS_FILE = HERE / "state" / "sessions.json"
PENDING_FILE = HERE / "state" / "pending_edits.json"

# Past this many context tokens, suggest a new thread. Haiku's price jumps 5x
# above 100K prompt tokens, and long threads get slower and more expensive anyway.
LONG_THREAD_TOKENS = 80_000

# Images Claude can read. The API rejects images over 5 MB.
IMAGE_TYPES = {"image/png", "image/jpeg", "image/gif", "image/webp"}
MAX_IMAGE_BYTES = 5_000_000
MAX_IMAGES = 4

# Models the default model may hand a hard message to, e.g. "sonnet" or "sonnet,opus".
# Opus uses up Pro plan limits much faster, so it's opt-in.
ESCALATE_TO = [m.strip() for m in os.environ.get("ESCALATE_TO", "sonnet").split(",") if m.strip() in MODELS]

# If an API key is in the environment, the SDK bills the API instead of your Pro plan.
if os.environ.get("ANTHROPIC_API_KEY"):
    raise SystemExit("ANTHROPIC_API_KEY is set; unset it so the bot uses your Pro plan.")

lock = asyncio.Lock()  # one request at a time; plenty for one user

intents = discord.Intents.default()
intents.message_content = True
client = discord.Client(intents=intents)


# ---------- small helpers ----------

class SessionStore:
    """A small JSON dict on disk. Used for conversation key (thread id, or 'dm')
    -> Claude session id, and for edit id -> pending edit proposal."""

    def __init__(self, path: Path):
        self.path = path
        try:
            self.data = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            self.data = {}

    def get(self, key: str):
        return self.data.get(key)

    def set(self, key: str, value) -> None:
        if value:
            self.data[key] = value
        else:
            self.data.pop(key, None)
        self._save()

    def pop(self, key: str):
        value = self.data.pop(key, None)
        self._save()
        return value

    def _save(self) -> None:
        self.path.parent.mkdir(exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(self.path)  # atomic: a crash mid-write can't corrupt the file


sessions = SessionStore(SESSIONS_FILE)
pending_edits = SessionStore(PENDING_FILE)

# Approve/Reject outcomes the bot hasn't heard about yet, per conversation.
# They're passed along with the user's next message in that conversation.
notices: dict[str, list[str]] = {}


def pick_model(text: str) -> tuple[str, str]:
    """'/sonnet explain X' -> ('sonnet', 'explain X'). No prefix -> default model."""
    first, _, rest = text.partition(" ")
    name = first.lstrip("/").lower()
    if first.startswith("/") and name in MODELS:
        return name, rest.strip()
    return DEFAULT_MODEL, text


def context_tokens_of(meta: dict) -> int:
    return (
        meta.get("input_tokens", 0)
        + meta.get("cache_read_tokens", 0)
        + meta.get("cache_write_tokens", 0)
    )


def log_usage(entry: dict) -> None:
    LOG_FILE.parent.mkdir(exist_ok=True)
    with LOG_FILE.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


async def send_long(channel, text: str) -> None:
    """Discord caps messages at 2000 characters."""
    text = text or "(empty reply)"
    for i in range(0, len(text), 1900):
        await channel.send(text[i : i + 1900])


async def collect_images(message: discord.Message) -> tuple[list[tuple[str, bytes]], list[str]]:
    """Download image attachments Claude can read. Returns (images, reasons for skipped files)."""
    images, skipped = [], []
    for att in message.attachments:
        media_type = (att.content_type or "").split(";")[0].strip().lower()
        if media_type not in IMAGE_TYPES:
            skipped.append(f"{att.filename} (only PNG, JPEG, GIF and WebP images are supported)")
        elif att.size > MAX_IMAGE_BYTES:
            skipped.append(f"{att.filename} (over {MAX_IMAGE_BYTES // 1_000_000} MB)")
        elif len(images) >= MAX_IMAGES:
            skipped.append(f"{att.filename} (max {MAX_IMAGES} images per message)")
        else:
            images.append((media_type, await att.read()))
    return images, skipped


def edit_buttons(edit_id: str) -> discord.ui.View:
    # The clicks are handled in on_interaction, by custom_id, so they work after a restart
    view = discord.ui.View(timeout=None)
    view.add_item(discord.ui.Button(
        label="Approve", style=discord.ButtonStyle.success, custom_id=f"edit:approve:{edit_id}"))
    view.add_item(discord.ui.Button(
        label="Reject", style=discord.ButtonStyle.danger, custom_id=f"edit:reject:{edit_id}"))
    return view


async def report_actions(channel, actions: list[dict], key: str) -> None:
    """Show the user what the bot saved, and post each proposed edit with buttons."""
    saved = [a["line"] for a in actions if a["type"] == "remembered"]
    if saved:
        await send_long(channel, f"📝 Saved to `{MEMORY_FILE}`:\n" + "\n".join(saved))
    captured = [a for a in actions if a["type"] == "captured"]
    if captured:
        await send_long(channel, f"📥 Saved to `{captured[0]['path']}`:\n"
                        + "\n".join(f"`{a['line']}`" for a in captured))

    for a in actions:
        if a["type"] != "proposal":
            continue
        edit_id = uuid.uuid4().hex[:12]
        pending_edits.set(edit_id, {**a, "conversation": key, "ts": time.time()})
        reason = f"\n{a['reason'][:200]}" if a.get("reason") else ""
        await channel.send(
            f"✏️ Proposed edit to `{a['path']}`{reason}\n```diff\n{render_diff(a['old'], a['new'])}\n```",
            view=edit_buttons(edit_id),
        )


def thread_title(text: str) -> str:
    title = " ".join(text.split())[:60]
    return title or "Conversation"


async def resolve_conversation(message: discord.Message):
    """Decide what kind of message this is and where to reply.
    Returns (mode, channel to reply in, conversation key), or None to ignore.
    mode 'chat' is a remembered conversation; 'quick' is a one-off capture with no session."""
    channel = message.channel

    if isinstance(channel, discord.DMChannel):
        return "chat", channel, "dm"

    if isinstance(channel, discord.Thread):
        parent = channel.parent
        if parent and parent.name == CHAT_CHANNEL:
            return "chat", channel, str(channel.id)
        return None

    name = getattr(channel, "name", "")
    if name == QUICK_CHANNEL:
        return "quick", channel, "quick"
    if name == CHAT_CHANNEL:
        thread = await message.create_thread(name=thread_title(message.content))
        return "chat", thread, str(thread.id)

    return None


# ---------- Discord events ----------

heartbeat = Heartbeat(VAULT, DAILY_DIR, HERE / "state" / "heartbeat.json", log_usage)
heartbeat_task: asyncio.Task | None = None


async def heartbeat_loop():
    owner = await client.fetch_user(OWNER_ID)

    async def send_dm(text: str) -> None:
        try:
            await send_long(owner, text)
            key = "dm"
        except discord.Forbidden:
            # DMs blocked (e.g. the server's privacy setting): post in #chat instead,
            # with a mention, in its own thread so a reply continues the conversation
            channel = next((ch for g in client.guilds for ch in g.text_channels
                            if ch.name == CHAT_CHANNEL), None)
            if channel is None:
                raise
            head = await channel.send(f"<@{OWNER_ID}> 🔔 {text[:1800]}")
            thread = await head.create_thread(name="Heartbeat: " + thread_title(text)[:40])
            if len(text) > 1800:
                await send_long(thread, text[1800:])
            key = str(thread.id)
        # so a reply knows what the Assistant said on its own
        notices.setdefault(key, []).append(f"You messaged the user on your own (heartbeat): {text[:1500]}")

    while True:
        try:
            await heartbeat.tick(send_dm)
        except Exception as e:
            print(f"Heartbeat error: {type(e).__name__}: {e}", flush=True)
        await asyncio.sleep(60)


@client.event
async def on_ready():
    global heartbeat_task
    print(f"Logged in as {client.user}. Vault: {VAULT}")
    if heartbeat_task is None:  # on_ready fires again after reconnects; start only once
        heartbeat_task = asyncio.create_task(heartbeat_loop())


@client.event
async def on_interaction(interaction: discord.Interaction):
    """Approve/Reject buttons on proposed edits."""
    custom_id = (interaction.data or {}).get("custom_id", "")
    if interaction.type != discord.InteractionType.component or not custom_id.startswith("edit:"):
        return
    _, choice, edit_id = custom_id.split(":", 2)

    if interaction.user.id != OWNER_ID:
        await interaction.response.send_message("Only the owner can approve edits.", ephemeral=True)
        return

    original = interaction.message.content if interaction.message else ""
    edit = pending_edits.pop(edit_id)
    if edit is None:
        await interaction.response.edit_message(content=f"{original}\n\n_Already handled._", view=None)
        return

    path = edit["path"]
    if choice == "approve":
        try:
            apply_edit(VAULT, path, edit["old"], edit["new"])
            status, applied = "✅ Approved and saved.", True
            notice = f"The user approved your proposed edit to {path}. It has been saved."
        except VaultError as e:
            status, applied = f"⚠️ Not applied: {e}", False
            notice = f"The user approved your edit to {path}, but it couldn't be applied: {e}"
    else:
        status, applied = "❌ Rejected. Nothing changed.", False
        notice = f"The user rejected your proposed edit to {path}. Nothing was changed."

    notices.setdefault(edit["conversation"], []).append(notice)
    await interaction.response.edit_message(content=f"{original}\n\n{status}", view=None)
    log_usage({"ts": time.time(), "event": f"edit_{choice}", "path": path,
               "applied": applied, "conversation": edit["conversation"]})


@client.event
async def on_message(message: discord.Message):
    if message.author.id != OWNER_ID:  # ignore everyone but you
        return

    model, text = pick_model(message.content)
    if not text and not message.attachments:
        return

    target = await resolve_conversation(message)
    if target is None:
        return
    mode, reply_channel, key = target

    images, skipped = await collect_images(message)
    if skipped:
        await reply_channel.send("⚠️ Skipped: " + "; ".join(skipped))
    if not text:
        if not images:
            return
        text = "(The user sent an image with no text.)"

    async with lock, reply_channel.typing():
        system_prompt, files_loaded = build_system_prompt(VAULT, DAILY_DIR)
        session_id = sessions.get(key) if mode == "chat" else None
        started = time.time()
        resumed = session_id is not None

        # Tell the bot what happened to its earlier proposals in this conversation
        pending_notes = notices.pop(key, [])
        body = QUICK_PROMPT.format(text=text) if mode == "quick" else text
        prompt = "\n".join(f"[System note: {n}]" for n in pending_notes + [""]) + body

        # Only the default (cheap) model in a chat gets to escalate; /sonnet and /opus answer directly
        escalate_to = ([m for m in ESCALATE_TO if m != model]
                       if model == DEFAULT_MODEL and mode == "chat" else [])

        def remember_session(session: str | None) -> None:
            if mode == "chat":  # quick captures are one-offs, never resumed
                sessions.set(key, session)

        try:
            reply, meta, new_session, actions = await ask(
                prompt, system_prompt, model, VAULT, session_id, images, escalate_to)
        except Exception as first_error:
            if not session_id:
                await reply_channel.send(f"⚠️ {type(first_error).__name__}: {first_error}")
                log_usage({"ts": started, "model": model, "conversation": key, "error": repr(first_error)})
                return
            # The saved session may be gone (e.g. Claude Code data cleared). Start fresh once.
            try:
                reply, meta, new_session, actions = await ask(
                    prompt, system_prompt, model, VAULT, None, images, escalate_to)
                resumed = False
                await reply_channel.send("ℹ️ Couldn't resume this conversation, so I started a fresh one.")
            except Exception as e:
                await reply_channel.send(f"⚠️ {type(e).__name__}: {e}")
                log_usage({"ts": started, "model": model, "conversation": key, "error": repr(e)})
                return

        def usage_entry(model: str, started: float, meta: dict, actions: list[dict], **extra) -> dict:
            return {
                "ts": started,
                "mode": mode,
                "model": model,
                "conversation": key,
                "session_id": new_session,
                "resumed": resumed,
                "message": text,
                "images": len(images),
                "files_loaded": files_loaded,
                "context_tokens": context_tokens_of(meta),
                "vault_actions": [
                    {"type": a["type"], "path": a.get("path", MEMORY_FILE)}
                    for a in actions if a["type"] != "escalate"
                ],
                **extra,
                **meta,
            }

        # Escalation: the cheap model handed the message to a stronger one.
        # The stronger model continues the same session, so it sees the whole thread.
        escalated_from = None
        escalation = next((a for a in actions if a["type"] == "escalate"), None)
        if escalation:
            target, reason = escalation["model"], escalation["reason"]
            log_usage(usage_entry(model, started, meta, actions, escalated=True, escalated_to=target))
            await reply_channel.send(f"↗️ Asking {target.title()}" + (f": {reason}" if reason else ""))
            handoff = (
                f"[System note: You are now {target.title()}. {model.title()} handed the user's last "
                "message to you" + (f" because: {reason}" if reason else "") + ". The user did not see "
                "its reply. Answer their last message fully now.]"
            )
            started = time.time()
            try:
                reply, meta, new_session, more = await ask(handoff, system_prompt, target, VAULT, new_session)
            except Exception as e:
                remember_session(new_session)
                await reply_channel.send(f"⚠️ {target.title()} failed: {type(e).__name__}: {e}")
                await report_actions(reply_channel, actions, key)
                log_usage({"ts": started, "model": target, "conversation": key,
                           "escalated_from": model, "error": repr(e)})
                return
            actions = [a for a in actions if a["type"] != "escalate"] + more
            escalated_from, model = model, target

        remember_session(new_session)
        await send_long(reply_channel, reply)
        await report_actions(reply_channel, actions, key)

        context_tokens = context_tokens_of(meta)
        if mode == "chat" and context_tokens > LONG_THREAD_TOKENS:
            await reply_channel.send(
                f"📏 This thread is at ~{context_tokens // 1000}K tokens of context. "
                "Starting a new message in #chat would make replies cheaper and faster."
            )

        log_usage(usage_entry(model, started, meta, actions,
                              escalated=False, escalated_from=escalated_from))


client.run(TOKEN)
