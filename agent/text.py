"""Clean the model's streamed text before it reaches the customer.

Some Bedrock models (Amazon Nova among them) may write their reasoning inside <thinking>...</thinking> before a
tool call. That is not meant for the customer, so it is removed - also when a tag is split across chunks.
"""

import re

OPEN, CLOSE = "<thinking>", "</thinking>"

# The site shows Western digits everywhere; models (and some Arabic dish names) use Arabic-Indic ones.
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_ARABIC_LETTER = re.compile(r"[\u0621-\u064A\u0671-\u06D3]")
_LATIN_LETTER = re.compile(r"[A-Za-z]")


def western_digits(text: str) -> str:
    return text.translate(_DIGITS)


def reply_language(message: str, site_lang: object = None) -> str:
    """"Arabic" or "English": the message's own script wins; otherwise (e.g. "2") the site language."""
    if _ARABIC_LETTER.search(message):
        return "Arabic"
    if _LATIN_LETTER.search(message):
        return "English"
    return "Arabic" if site_lang == "ar" else "English"


BLOCKED_MARKER = "[SUMAAT_BLOCKED]"  # the guardrail's blocked message (infra/agent_stack.py); never shown as text


class MarkerFilter:
    """Removes BLOCKED_MARKER from streamed text (also when split across chunks) and remembers that it was seen."""

    def __init__(self) -> None:
        self._buf = ""
        self.seen = False

    def feed(self, chunk: str) -> str:
        self._buf += chunk
        if BLOCKED_MARKER in self._buf:
            self.seen = True
            self._buf = self._buf.replace(BLOCKED_MARKER, "")
        keep = _partial_suffix(self._buf, BLOCKED_MARKER)
        out, self._buf = self._buf[: len(self._buf) - keep], self._buf[len(self._buf) - keep :]
        return out

    def flush(self) -> str:
        rest, self._buf = self._buf, ""
        return rest


def _partial_suffix(text: str, tag: str) -> int:
    """Length of the longest end of `text` that is the start of `tag` (a tag that may continue next chunk)."""
    for n in range(min(len(tag) - 1, len(text)), 0, -1):
        if text.endswith(tag[:n]):
            return n
    return 0


class ThinkingFilter:
    def __init__(self) -> None:
        self._buf = ""
        self._inside = False

    def feed(self, chunk: str) -> str:
        self._buf += chunk
        out = []
        while True:
            if self._inside:
                end = self._buf.find(CLOSE)
                if end < 0:
                    keep = _partial_suffix(self._buf, CLOSE)
                    self._buf = self._buf[len(self._buf) - keep :] if keep else ""
                    break
                self._buf = self._buf[end + len(CLOSE) :]
                self._inside = False
            else:
                start = self._buf.find(OPEN)
                if start < 0:
                    keep = _partial_suffix(self._buf, OPEN)
                    out.append(self._buf[: len(self._buf) - keep])
                    self._buf = self._buf[len(self._buf) - keep :]
                    break
                out.append(self._buf[:start])
                self._buf = self._buf[start + len(OPEN) :]
                self._inside = True
        return "".join(out)

    def flush(self) -> str:
        """Whatever is held back at the end (a lone '<' is text, an unclosed <thinking> is dropped)."""
        rest = "" if self._inside else self._buf
        self._buf, self._inside = "", False
        return rest
