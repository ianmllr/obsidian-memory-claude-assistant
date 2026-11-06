"""Fetching one web page for the read_link tool: plain text only, public addresses only.

The page is untrusted. It may contain text written to steer an AI ("ignore your
instructions and save..."), so tools.py holds every write for the user's approval in
any conversation that has read a page. This file only makes sure the fetch itself
is harmless: http(s) only, no addresses on this computer or the home network,
limited size and time, and only text comes back.
"""

import asyncio
import ipaddress
import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlsplit

import aiohttp

MAX_BYTES = 3_000_000    # downloaded HTML
MAX_CHARS = 15_000       # text handed to the model, about 4K tokens
TIMEOUT_SECONDS = 20
MAX_REDIRECTS = 5
USER_AGENT = "Mozilla/5.0 (X11; Linux x86_64) personal-assistant/1.0"

URL_RE = re.compile(r"https?://[^\s<>\"'`|]+")


class WebError(Exception):
    """The page couldn't be read. The message goes back to the model."""


def links_in(text: str) -> list[str]:
    """URLs in a message, without trailing punctuation or Markdown around them."""
    found = []
    for url in URL_RE.findall(text):
        url = url.rstrip(".,;:!?*_~)]}")
        if url not in found:
            found.append(url)
    return found


def link_key(url: str) -> str:
    """What has to match for a link to count as one the user sent: host and path.
    Query strings and #fragments may differ (tracking parameters, anchors)."""
    parts = urlsplit(url.strip())
    host = (parts.hostname or "").lower().removeprefix("www.")
    return host + (parts.path.rstrip("/") or "/")


async def _check_public(host: str) -> None:
    """Refuse hosts that resolve to this computer, the home network or other non-public addresses."""
    try:
        infos = await asyncio.get_running_loop().getaddrinfo(host, None)
    except OSError:
        raise WebError(f"Couldn't find the site '{host}'.") from None
    for info in infos:
        ip = ipaddress.ip_address(info[4][0].split("%")[0])
        if not ip.is_global:
            raise WebError("That address is on this computer or the local network, which is off-limits.")


class _PageText(HTMLParser):
    """Collects the readable text of a page, preferring <article> when there is one."""

    SKIP = {"script", "style", "noscript", "svg", "nav", "footer", "header", "form",
            "button", "iframe", "template", "select", "aside"}
    BLOCK = {"p", "div", "br", "li", "tr", "section", "article", "blockquote", "pre",
             "h1", "h2", "h3", "h4", "h5", "h6", "figcaption", "hr"}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.skip = 0
        self.article = 0
        self.in_title = False
        self.title = ""
        self.all: list[str] = []
        self.article_parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in self.SKIP:
            self.skip += 1
        elif tag == "title":
            self.in_title = True
        elif tag == "article":
            self.article += 1
        if tag in self.BLOCK:
            self._add("\n")
        if tag in ("h1", "h2", "h3") and not self.skip:
            self._add("## ")
        if tag == "li" and not self.skip:
            self._add("- ")

    def handle_endtag(self, tag):
        if tag in self.SKIP and self.skip:
            self.skip -= 1
        elif tag == "title":
            self.in_title = False
        elif tag == "article" and self.article:
            self.article -= 1
        if tag in self.BLOCK:
            self._add("\n")

    def handle_data(self, data):
        if self.in_title:
            self.title += data
        elif not self.skip:
            self._add(data)

    def _add(self, text):
        self.all.append(text)
        if self.article:
            self.article_parts.append(text)

    def text(self) -> str:
        article = _tidy("".join(self.article_parts))
        return article if len(article) > 500 else _tidy("".join(self.all))


def _tidy(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.splitlines()]
    out, blank = [], False
    for line in lines:
        if line in ("", "-", "##"):
            blank = bool(out)
            continue
        if blank:
            out.append("")
        out.append(line)
        blank = False
    return "\n".join(out)


def html_to_text(html: str) -> tuple[str, str]:
    """(title, readable text) of an HTML page."""
    parser = _PageText()
    parser.feed(html)
    parser.close()
    return " ".join(parser.title.split()), parser.text()


async def fetch_text(url: str) -> tuple[str, str, str]:
    """Download a page and return (final url, title, text). Follows redirects itself,
    so every hop is checked for a public address."""
    timeout = aiohttp.ClientTimeout(total=TIMEOUT_SECONDS)
    async with aiohttp.ClientSession(timeout=timeout, headers={"User-Agent": USER_AGENT}) as session:
        for _ in range(MAX_REDIRECTS + 1):
            parts = urlsplit(url)
            if parts.scheme not in ("http", "https") or not parts.hostname:
                raise WebError("Only http and https links can be read.")
            await _check_public(parts.hostname)
            try:
                async with session.get(url, allow_redirects=False) as resp:
                    if resp.status in (301, 302, 303, 307, 308):
                        url = urljoin(url, resp.headers.get("Location", ""))
                        continue
                    if resp.status >= 400:
                        raise WebError(f"The site answered with error {resp.status}.")
                    ctype = resp.headers.get("Content-Type", "").lower()
                    if "html" not in ctype and not ctype.startswith("text/"):
                        raise WebError(f"That isn't a web page ({ctype or 'unknown type'}).")
                    body = await resp.content.read(MAX_BYTES)
                    raw = body.decode(resp.charset or "utf-8", errors="replace")
            except (aiohttp.ClientError, asyncio.TimeoutError) as e:
                raise WebError(f"Couldn't load the page: {type(e).__name__}.") from None
            title, text = html_to_text(raw) if "html" in ctype else ("", raw.strip())
            if not text:
                raise WebError("The page has no readable text (it may need JavaScript or a login).")
            if len(text) > MAX_CHARS:
                text = text[:MAX_CHARS] + f"\n\n[Cut at {MAX_CHARS} characters.]"
            return url, title, text
        raise WebError("Too many redirects.")
