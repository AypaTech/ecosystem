# -*- coding: utf-8 -*-
"""Odoo HTML <-> Telegram HTML subset (SPEC §7 ``TelegramFormatter``).

Outbound: keep only ``b i u s a code pre blockquote``, escape everything else,
turn block elements into line breaks, split long texts without breaking tags.
Lengths are counted on the *visible* text, which is what Telegram limits
(4096 for messages, 1024 for captions).

Inbound: render ``text`` + ``entities`` as safe Odoo HTML (entity offsets are
UTF-16 code units).
"""
import html
import re
from collections import defaultdict
from html.parser import HTMLParser

from markupsafe import Markup, escape

TEXT_LIMIT = 4096
CAPTION_LIMIT = 1024

_TAG_MAP = {
    "b": "b", "strong": "b",
    "i": "i", "em": "i",
    "u": "u", "ins": "u",
    "s": "s", "strike": "s", "del": "s",
    "a": "a",
    "code": "code",
    "pre": "pre",
    "blockquote": "blockquote",
}
_BLOCK_TAGS = {"p", "div", "h1", "h2", "h3", "h4", "h5", "h6", "ul", "ol", "table", "tr", "section"}
_SKIP_CONTENT_TAGS = {"script", "style", "head", "title"}
_SAFE_HREF_RE = re.compile(r"^(https?://|tg://|mailto:)", re.IGNORECASE)


class _Events(HTMLParser):
    """Parse HTML into ('open', tag, attrs) / ('close', tag) / ('text', str) events."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.events = []
        self._skip = 0
        self._open = []  # telegram tags currently open (to ignore stray closes)

    def handle_starttag(self, tag, attrs):
        if tag in _SKIP_CONTENT_TAGS:
            self._skip += 1
            return
        if tag == "br":
            self.events.append(("text", "\n"))
            return
        if tag == "li":
            self._newline_single()
            self.events.append(("text", "• "))
            return
        if tag in _BLOCK_TAGS:
            self._newline_single()
            return
        mapped = _TAG_MAP.get(tag)
        if not mapped:
            return
        attr = ""
        if mapped == "a":
            href = dict(attrs).get("href") or ""
            if not _SAFE_HREF_RE.match(href):
                return  # drop the link, keep its text
            attr = href
        self._open.append(mapped)
        self.events.append(("open", mapped, attr))

    def handle_startendtag(self, tag, attrs):
        if tag == "br":
            self.events.append(("text", "\n"))

    def handle_endtag(self, tag):
        if tag in _SKIP_CONTENT_TAGS:
            self._skip = max(0, self._skip - 1)
            return
        if tag in _BLOCK_TAGS or tag == "li":
            self._newline_single()
            return
        mapped = _TAG_MAP.get(tag)
        if mapped and mapped in self._open:
            # close properly nested
            while self._open:
                top = self._open.pop()
                self.events.append(("close", top))
                if top == mapped:
                    break

    def handle_data(self, data):
        if self._skip or not data:
            return
        self.events.append(("text", data))

    def _newline_single(self):
        last = next((e for e in reversed(self.events) if e[0] == "text"), None)
        if last is None or last[1].endswith("\n"):
            return
        self.events.append(("text", "\n"))

    def close(self):
        super().close()
        while self._open:
            self.events.append(("close", self._open.pop()))


def _normalize_whitespace(events):
    """Collapse HTML whitespace (not inside pre) and trim leading/trailing blank lines."""
    out = []
    in_pre = 0
    for ev in events:
        if ev[0] == "open" and ev[1] == "pre":
            in_pre += 1
        elif ev[0] == "close" and ev[1] == "pre":
            in_pre = max(0, in_pre - 1)
        elif ev[0] == "text" and not in_pre and ev[1] not in ("\n", "• "):
            text = re.sub(r"[ \t\r\f\v]*\n[ \t\r\f\v]*", " ", ev[1])
            text = re.sub(r"[ \t\r\f\v]+", " ", text)
            ev = ("text", text)
        out.append(ev)
    # strip leading/trailing whitespace-only text events
    while out and out[0][0] == "text" and not out[0][1].strip():
        out.pop(0)
    while out and out[-1][0] == "text" and not out[-1][1].strip():
        out.pop()
    # collapse 3+ newlines
    merged = []
    for ev in out:
        if ev[0] == "text" and merged and merged[-1][0] == "text":
            merged[-1] = ("text", merged[-1][1] + ev[1])
        else:
            merged.append(ev)
    return [("text", re.sub(r"\n{3,}", "\n\n", e[1])) if e[0] == "text" else e for e in merged]


def _open_tag(tag, attr):
    if tag == "a":
        return f'<a href="{html.escape(attr, quote=True)}">'
    return f"<{tag}>"


def _find_break(text, capacity):
    """Best index <= capacity to cut ``text`` (prefer newline, then space)."""
    if len(text) <= capacity:
        return len(text)
    window = text[:capacity]
    for sep in ("\n", " "):
        idx = window.rfind(sep)
        if idx >= capacity // 2:
            return idx + 1
    return capacity


def _chunk(events, first_limit, next_limit):
    """Render events into HTML chunks whose visible length respects the limits."""
    chunks = []
    stack = []  # (tag, attr)
    buf = []
    visible = 0
    limit = first_limit

    def flush():
        nonlocal buf, visible, limit
        closing = "".join(f"</{t}>" for t, _a in reversed(stack))
        content = "".join(buf) + closing
        if visible:
            chunks.append(content.strip() if not stack else content)
        buf = ["".join(_open_tag(t, a) for t, a in stack)]
        visible = 0
        limit = next_limit

    for ev in events:
        if ev[0] == "open":
            stack.append((ev[1], ev[2]))
            buf.append(_open_tag(ev[1], ev[2]))
        elif ev[0] == "close":
            if stack and stack[-1][0] == ev[1]:
                stack.pop()
            buf.append(f"</{ev[1]}>")
        else:
            text = ev[1]
            while text:
                capacity = limit - visible
                if capacity <= 0:
                    flush()
                    continue
                if len(text) <= capacity:
                    buf.append(html.escape(text, quote=False))
                    visible += len(text)
                    break
                cut = _find_break(text, capacity)
                if cut == 0:
                    flush()
                    continue
                buf.append(html.escape(text[:cut], quote=False))
                visible += cut
                text = text[cut:]
                flush()
    if visible:
        chunks.append("".join(buf).strip())
    return [c for c in chunks if c]


def _events_from_html(body):
    parser = _Events()
    parser.feed(str(body or ""))
    parser.close()
    return _normalize_whitespace(parser.events)


def html_to_telegram(body, limit=TEXT_LIMIT):
    """Odoo HTML → list of Telegram HTML messages (each ≤ ``limit`` visible chars)."""
    return _chunk(_events_from_html(body), limit, limit)


def html_to_caption(body, caption_limit=CAPTION_LIMIT, text_limit=TEXT_LIMIT):
    """Return ``(caption, overflow_messages)``. Overflow is sent as follow-up text."""
    chunks = _chunk(_events_from_html(body), caption_limit, text_limit)
    if not chunks:
        return "", []
    caption = chunks[0]
    rest = chunks[1:]
    if rest:
        # re-chunk overflow with the (bigger) text limit
        rest = html_to_telegram("\n".join(rest).replace("\n", "<br/>"), text_limit)
    return caption, rest


def visible_length(telegram_html):
    """Visible length of a Telegram HTML string (for tests/validation)."""
    return len(html.unescape(re.sub(r"<[^>]+>", "", telegram_html or "")))


def plain_to_html(text):
    """Escape plain text and keep line breaks."""
    if not text:
        return Markup("")
    return Markup("<br/>").join(escape(line) for line in str(text).split("\n"))


# ----------------------------------------------------------------------
# Inbound
# ----------------------------------------------------------------------

_ENTITY_TAGS = {
    "bold": ("<b>", "</b>"),
    "italic": ("<i>", "</i>"),
    "underline": ("<u>", "</u>"),
    "strikethrough": ("<s>", "</s>"),
    "code": ("<code>", "</code>"),
    "pre": ("<pre>", "</pre>"),
    "blockquote": ("<blockquote>", "</blockquote>"),
    "expandable_blockquote": ("<blockquote>", "</blockquote>"),
}


def _entity_open_close(entity, segment_text):
    etype = entity.get("type")
    if etype in _ENTITY_TAGS:
        return _ENTITY_TAGS[etype]
    if etype == "text_link":
        url = entity.get("url") or ""
        if _SAFE_HREF_RE.match(url):
            return (
                Markup('<a href="%s" target="_blank" rel="noopener noreferrer">') % url,
                "</a>",
            )
    if etype == "url":
        url = segment_text if re.match(r"^https?://", segment_text, re.I) else f"https://{segment_text}"
        return Markup('<a href="%s" target="_blank" rel="noopener noreferrer">') % url, "</a>"
    return None


def telegram_to_html(text, entities=None):
    """Telegram text + entities → safe Odoo HTML (Markup)."""
    if not text:
        return Markup("")
    data = text.encode("utf-16-le")
    total = len(data) // 2

    def sub(start, end):
        return data[start * 2:end * 2].decode("utf-16-le", errors="replace")

    opens = defaultdict(list)
    closes = defaultdict(list)
    points = {0, total}
    for entity in sorted(entities or [], key=lambda e: (e.get("offset", 0), -e.get("length", 0))):
        start = int(entity.get("offset", 0))
        end = start + int(entity.get("length", 0))
        if start < 0 or end > total or end <= start:
            continue
        tags = _entity_open_close(entity, sub(start, end))
        if not tags:
            continue
        key = object()
        opens[start].append((key, tags))
        closes[end].append(key)
        points.update((start, end))

    out = []
    stack = []  # (key, tags)
    ordered = sorted(points)
    for idx, pos in enumerate(ordered):
        # close entities ending here (reopen those accidentally interleaved)
        ending = set(closes.get(pos, []))
        if ending:
            reopen = []
            while stack and ending:
                key, tags = stack.pop()
                out.append(Markup(tags[1]))
                if key in ending:
                    ending.discard(key)
                else:
                    reopen.append((key, tags))
            for key, tags in reversed(reopen):
                out.append(Markup(tags[0]))
                stack.append((key, tags))
        for key, tags in opens.get(pos, []):
            out.append(Markup(tags[0]))
            stack.append((key, tags))
        if idx + 1 < len(ordered):
            out.append(plain_to_html(sub(pos, ordered[idx + 1])))
    while stack:
        out.append(Markup(stack.pop()[1][1]))
    return Markup("").join(out)
