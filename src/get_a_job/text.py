from __future__ import annotations

import html
import re
from typing import Any


_ESCAPED_TAG = re.compile(r"\\+(?=</?[A-Za-z][^>]*>)")
_HTML_TAG = re.compile(r"<[^>]+>")


def plain_text(value: Any) -> str:
    """Return stable plain text from ATS HTML, entities, and escaped markup.

    Some boards return HTML directly, while others double-encode entities or prefix
    closing tags with JSON-style backslashes. Decode repeatedly before stripping tags
    so combinations such as ``&amp;nbsp;`` and ``\\</p>`` cannot leak into the UI.
    """
    text = str(value or "")
    for _ in range(3):
        decoded = html.unescape(text)
        if decoded == text:
            break
        text = decoded
    text = _ESCAPED_TAG.sub("", text)
    text = _HTML_TAG.sub(" ", text)
    return " ".join(text.split())
