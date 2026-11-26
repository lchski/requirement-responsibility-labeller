"""Text helpers shared by the pipeline stages."""
import re

from lxml import etree


def fix_text(s):
    """Normalize whitespace and undo Hawk's double encoding (UTF-8 bytes once decoded as Latin-1)."""
    if not s:
        return ""
    try:
        s = s.encode("latin-1").decode("utf-8")
    except (UnicodeEncodeError, UnicodeDecodeError):
        pass  # already clean
    return re.sub(r"\s+", " ", s.replace("\xa0", " ")).strip()


def element_text(el, skip=()):
    """Text of an element, leaving out the subtrees of children whose tag is in `skip` (but keeping their tails)."""
    parts = [el.text or ""]
    for child in el:
        if not isinstance(child.tag, str):  # comments, processing instructions
            parts.append(child.tail or "")
            continue
        if child.tag not in skip:
            parts.append(etree.tostring(child, method="text", encoding="unicode", with_tail=False))
        parts.append(child.tail or "")
    return fix_text(" ".join(parts))
