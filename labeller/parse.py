"""Stage 2: turn an instrument's XML into a flat table of clauses with explicit parent links.

TBS publishes two generations of the policy schema:
  * current: nested <clause anchor="4.1.2"> elements, sub-topics in <section><header>
  * legacy:  <section anchor title> holding a <p> stem followed by a <ul>/<ol> of numbered items
Both are flattened into the same node shape so later stages don't care which one they got.
"""
import re

from lxml import etree

from .text import element_text, fix_text

# Containers whose title says they carry requirements. Matched against chapter titles.
REQUIREMENT_CHAPTER = re.compile(r"requirement|responsibilit|procedure|^\W*[\d.]*\W*standards?\W*$", re.I)
# "Roles of other government organizations" describes other bodies' mandates, not this instrument's requirements.
OTHER_ORGS_CHAPTER = re.compile(r"roles (and responsibilities )?of (other )?government organi", re.I)
REQUIREMENT_APPENDIX = re.compile(r"mandatory|standard|requirement|procedure", re.I)
# A standard published on its own: "Appendix I. Standard on Security Event Reporting" in the HTML, "Standard on
# Security Event Reporting" in the XML. Judged like an appendix title.
APPENDIX_TITLE = re.compile(r"^\W*(appendix|standard)\b", re.I)
# Sub-sections of a requirements container that hold no requirements ("I.1 Effective date" in a standard).
NON_REQUIREMENT_TOPIC = re.compile(r"^\W*[A-Z]?[\d.]*\W*(effective date|application|authorit(y|ies)|definitions|references|enquiries|context|objectives? and expected results)\W*$", re.I)
LEADING_NUMBER = re.compile(r"^\(?(\d+(?:\.\d+)+)\.?\)?\s+")


def _heading_text(section):
    title = fix_text(section.get("title", ""))
    if title:
        return title
    for name in ("header", "title"):  # <title> is used by nested appendices ("A.1 Effective date")
        child = section.find(name)
        if child is not None:
            return fix_text(etree.tostring(child, method="text", encoding="unicode", with_tail=False))
    return ""


def _links(el):
    ids = []
    for a in el.iter("a"):
        m = re.search(r"[?&]id=(\d+)", a.get("href", ""))
        if m and m.group(1) not in ids:
            ids.append(m.group(1))
    return ids


class _Builder:
    def __init__(self, prefix):
        self.prefix = prefix
        self.nodes = []

    def add(self, el, text, parent, depth, topic, kind, anchor=None):
        if anchor is None:
            m = LEADING_NUMBER.match(text)
            anchor = m.group(1) if m else None
        node = dict(anchor=anchor, parent=parent, depth=depth, text=text, topic=topic, kind=kind, el=el, idx=len(self.nodes))
        self.nodes.append(node)
        return node

    def walk(self, el, parent, depth, topic):
        last_p = None
        base_parent, base_depth = parent, depth
        for child in el:
            tag = child.tag if isinstance(child.tag, str) else ""
            if tag in ("h2", "h3", "h4", "h5", "h6"):
                # A bare heading inside a legacy section ("<h4>6.3.1 The senior departmental official ... is
                # responsible for the following:</h4>") parents the paragraphs and lists that follow it.
                text = element_text(child)
                if text:
                    node = self.add(child, text, base_parent, base_depth, topic, "heading")
                    parent, depth, last_p = node["idx"], base_depth + 1, None
                continue
            if tag in ("section", "appendix", "chapter"):  # nested <chapter>/<appendix> elements are sub-sections
                heading = _heading_text(child)
                if heading:
                    node = self.add(child, heading, parent, depth, topic, "heading", child.get("anchor"))
                    self.walk(child, node["idx"], depth + 1, heading)
                else:
                    self.walk(child, parent, depth, topic)
                last_p = None
            elif tag in ("clauses", "div"):
                self.walk(child, parent, depth, topic)
            elif tag == "clause":
                text = element_text(child, skip={"clauses", "section", "header"})
                node = self.add(child, text, parent, depth, topic, "clause", child.get("anchor"))
                self.walk(child, node["idx"], depth + 1, topic)
            elif tag == "p":
                text = element_text(child)
                if text:
                    last_p = self.add(child, text, parent, depth, topic, "paragraph")
            elif tag in ("ul", "ol"):
                stem = last_p["idx"] if last_p is not None else parent
                self.walk_list(child, stem, depth + (1 if last_p is not None else 0), topic)

    def walk_list(self, listel, parent, depth, topic):
        for li in listel.findall("li"):
            text = element_text(li, skip={"ul", "ol"})
            if not text:
                continue
            node = self.add(li, text, parent, depth, topic, "item")
            for sub in li:
                if sub.tag in ("ul", "ol"):
                    self.walk_list(sub, node["idx"], depth + 1, topic)


def containers(doc):
    """Yield (kind, element, title, title_says_requirements) for every chapter and appendix."""
    for ch in doc.iter("chapter"):
        if ch.getparent() is not None and ch.getparent().tag == "chapter":
            continue  # nested chapters ("5.1 Objective" inside "5. Directive statement") are walked with their parent
        title = _heading_text(ch)
        if APPENDIX_TITLE.match(title):
            match = bool(REQUIREMENT_APPENDIX.search(title))
        else:
            match = bool(REQUIREMENT_CHAPTER.search(title)) and not OTHER_ORGS_CHAPTER.search(title)
        yield "chapter", ch, title, match
    for ap in doc.iter("appendix"):
        if ap.getparent() is not None and ap.getparent().tag == "appendix":
            continue  # nested appendices are sub-sections of their parent, walked with it
        title = _heading_text(ap)
        yield "appendix", ap, title, bool(REQUIREMENT_APPENDIX.search(title))


def parse_container(el, prefix):
    """Flatten one chapter or appendix. Returns nodes with `key`, `parent_key`, `has_children` and `links`."""
    b = _Builder(prefix)
    b.walk(el, None, 0, "")
    nodes = b.nodes
    used = set()
    for n in nodes:
        key = fix_text(n["anchor"]) or f"{prefix}#{n['idx']}"
        if key in used:
            key = f"{key}~{n['idx']}"
        used.add(key)
        n["key"] = key
    parents = {n["parent"] for n in nodes if n["parent"] is not None}
    for n in nodes:
        n["parent_key"] = nodes[n["parent"]]["key"] if n["parent"] is not None else None
        n["has_children"] = n["idx"] in parents
        n["links"] = _links(n["el"]) if not n["has_children"] else []
    return nodes
