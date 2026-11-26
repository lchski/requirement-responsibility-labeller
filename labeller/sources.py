"""Read a captured instrument, XML or HTML, into the same XML shape.

TBS serves each instrument as XML (`&section=xml`) and as an HTML page (`&section=html`). The HTML page is a
rendering of the same document, with every structural element kept:

  XML                                         HTML
  <chapter anchor="4" title="Requirements">   <section class="pol-sec"><h2 id="cha4">4. Requirements</h2>
  <appendix anchor="A" title="Appendix A..">  <div class="pol-app"><section class="pol-sec"><h2 id="appA">Appendix A..</h2>
  <clauses>                                   <ul class="pol-cla">
  <clause anchor="4.1">                       <li class="pol-cla" id="cla4.1"><span class="pol-cla-id">4.1</span>
  <section anchor="6.1" title="6.1 ...">      <section class="pol-sub"><h3 id="sec6.1">6.1 ...</h3>

`html_to_doc` maps the HTML back onto the XML element names, so the parser only has one shape to read.
Since late 2025 Hawk has mostly saved HTML (under .xml names, and in per-change snapshot folders), so this is how
recent versions get in.
"""
import re

from lxml import etree, html

DATE_MODIFIED = re.compile(r"""dateModified\W+(\d{4}-\d{2}-\d{2})""")
DOC_ID = re.compile(r"doc-(?:eng|fra)\.aspx\?id=(\d+)")
# The language toggle ("Français") links to this same instrument; other links can point anywhere.
SELF_ID = re.compile(r"doc-fra\.aspx\?id=(\d+)(?:&amp;|&)section=html")
BLOCK = {"li", "p", "dt", "dd", "div", "br", "ul", "ol", "dl", "h2", "h3", "h4", "h5", "h6", "tr", "td", "th", "table", "section", "header"}
CHAPTER_NUMBER = re.compile(r"^\s*\d+(?:\.\d+)*\.?\s+")


def sniff(path):
    """'xml', 'html' (a TBS policy page) or None (firewall page, error page, something else)."""
    with open(path, "rb") as f:
        head = f.read(4000)
    if b"<doc" in head and b"documentID" in head:
        return "xml"
    with open(path, "rb") as f:
        body = f.read()
    if b'id="wb-cont"' in body and b"pol-sec" in body:
        return "html"
    return None


def html_meta(path):
    """(documentID, title, dateModified) read from a TBS policy page."""
    raw = open(path, "rb").read().decode("utf-8", errors="replace")
    own = SELF_ID.findall(raw)
    ids = own or DOC_ID.findall(raw)
    page = html.fromstring(raw)
    h1 = page.xpath('//h1[@id="wb-cont"]')
    title = re.sub(r"\s+", " ", h1[0].text_content()).strip() if h1 else ""
    m = DATE_MODIFIED.search(raw)
    return (int(max(set(ids), key=ids.count)) if ids else None), title, (m.group(1) if m else "")


def _classes(el):
    return (el.get("class") or "").split()


def _convert(el):
    """Copy an HTML subtree into XML, renaming the policy-structure elements on the way."""
    cls = _classes(el)
    tag = el.tag
    attrs = {}
    if tag in ("ul", "ol") and "pol-cla" in cls:
        tag = "clauses"
    elif tag == "li" and "pol-cla" in cls:
        tag = "clause"
        if (el.get("id") or "").startswith("cla"):
            attrs["anchor"] = el.get("id")[3:]
    elif tag == "section" and "pol-sub" in cls:
        hs = el.xpath("./*[self::h3 or self::h4 or self::h5] | ./header/*[self::h3 or self::h4 or self::h5]")
        if hs and (hs[0].get("id") or "").startswith("sec"):
            attrs = {"anchor": hs[0].get("id")[3:], "title": re.sub(r"\s+", " ", hs[0].text_content()).strip()}
    elif tag == "div" and "pol-content" in cls:
        tag = None  # transparent wrapper: children go straight into the parent
    for k in ("href", "datetime", "lang"):
        if el.get(k) is not None:
            attrs[k] = el.get(k)
    out = etree.Element(tag, attrs) if tag else etree.Element("_wrap")
    out.text = el.text
    for child in el:
        if not isinstance(child.tag, str):
            continue
        if child.tag == "span" and "pol-cla-id" in _classes(child):
            # The clause number is the anchor already; keep only what follows it.
            if len(out):
                out[-1].tail = (out[-1].tail or "") + (child.tail or "")
            else:
                out.text = (out.text or "") + (child.tail or "")
            continue
        if attrs.get("title") and (child.tag == "header" or (child.tag in ("h3", "h4", "h5") and (child.get("id") or "").startswith("sec"))):
            if len(out):
                out[-1].tail = (out[-1].tail or "") + (child.tail or "")
            else:
                out.text = (out.text or "") + (child.tail or "")
            continue  # the sub-section heading became its title attribute
        conv = _convert(child)
        if conv.tag == "_wrap":
            if len(out):
                out[-1].tail = (out[-1].tail or "") + (conv.text or "")
            else:
                out.text = (out.text or "") + (conv.text or "")
            for c in list(conv):
                out.append(c)
            if len(out):
                out[-1].tail = (out[-1].tail or "") + (child.tail or "")
            else:
                out.text = (out.text or "") + (child.tail or "")
        else:
            # XML captures are pretty-printed, so block elements are always separated by whitespace; the HTML
            # isn't ("...Act</li><li>Privacy Act"). Add a line break so list items don't run together.
            conv.tail = ("\n" if child.tag in BLOCK else "") + (child.tail or "")
            out.append(conv)
    return out


def html_to_doc(path, doc_id=None):
    """An XML <doc> equivalent to what TBS serves at &section=xml, rebuilt from the HTML page."""
    found_id, title, modified = html_meta(path)
    page = html.fromstring(open(path, "rb").read().decode("utf-8", errors="replace"))
    doc = etree.Element("doc", {"documentID": str(doc_id or found_id or ""), "title": title, "versionID": "",
                                "dateModified": modified, "source": "html"})
    chapters = etree.SubElement(doc, "chapters")
    appendices = etree.SubElement(doc, "appendices")
    for sec in page.xpath('//main//section[contains(concat(" ", normalize-space(@class), " "), " pol-sec ")]'):
        h2 = sec.find("h2")
        if h2 is None:
            continue
        hid = h2.get("id") or ""
        heading = re.sub(r"\s+", " ", h2.text_content()).strip()
        body = _convert(sec)
        # drop the h2 itself (it becomes the title), keep its tail text
        for c in list(body):
            if c.tag == "h2":
                body.text = (body.text or "") + (c.tail or "")
                body.remove(c)
                break
        if hid.startswith("app"):
            el = etree.SubElement(appendices, "appendix", {"anchor": hid[3:], "title": heading})
        else:
            anchor = hid[3:] if hid.startswith("cha") else ""
            # Current-schema XML titles drop the chapter number ("Requirements"); older ones keep it.
            current_schema = body.find(".//clause") is not None
            title_attr = CHAPTER_NUMBER.sub("", heading) if current_schema else heading
            el = etree.SubElement(chapters, "chapter", {"anchor": anchor, "title": title_attr})
        el.text = body.text
        for c in list(body):
            el.append(c)
    return doc


def load_doc(path, source=None, doc_id=None):
    """The instrument as an XML <doc> element, whichever format it was captured in."""
    source = source or sniff(path)
    if source == "xml":
        return etree.parse(str(path)).getroot()
    return html_to_doc(path, doc_id)
