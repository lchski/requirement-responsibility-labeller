"""HTML captures must parse to the same items as the XML of the same version, and the index must pick the right capture."""
from labeller import actors, parse, sources
from labeller.index import build_index, coverage

XML = """<doc documentID="7" title="Directive on Testing" versionID="1"><chapters>
<chapter anchor="4" title="Requirements"><clauses>
  <clause anchor="4.1">The chief audit executive is responsible for the following:
    <clauses>
      <clause anchor="4.1.1">Establishing a plan that is approved by the deputy head; and</clause>
    </clauses>
  </clause>
</clauses>
<h3>Reporting</h3>
<clauses><clause anchor="4.2">Deputy heads are responsible for reporting annually to the <a href="https://www.tbs-sct.canada.ca/pol/doc-eng.aspx?id=31300">Policy on Results</a> centre.</clause></clauses>
</chapter></chapters>
<appendices><appendix anchor="A" title="Appendix A: Mandatory procedures"><clauses>
  <clause anchor="A.1">Departments must keep the plan.</clause>
</clauses></appendix></appendices></doc>"""

HTML = """<!DOCTYPE html><html><head><title>Directive on Testing</title></head><body>
<script>wet.builder.footer({ preFooter: { dateModified: "2024-01-01" } })</script>
<a href="/pol/doc-fra.aspx?id=7&amp;section=html">Français</a>
<main class="container"><h1 id="wb-cont">Directive on Testing</h1><div class="pol-cha">
<section class="pol-sec"><h2 id="cha4">4. Requirements</h2><div class="pol-content">
<ul class="pol-cla list-unstyled"><li class="pol-cla" id="cla4.1"><span class="pol-cla-id">4.1</span>The chief audit executive is responsible for the following: <ul class="pol-cla list-unstyled"><li class="pol-cla" id="cla4.1.1"><span class="pol-cla-id">4.1.1</span>Establishing a plan that is approved by the deputy head; and</li></ul></li></ul>
<h3>Reporting</h3><ul class="pol-cla list-unstyled"><li class="pol-cla" id="cla4.2"><span class="pol-cla-id">4.2</span>Deputy heads are responsible for reporting annually to the <a href="https://www.tbs-sct.canada.ca/pol/doc-eng.aspx?id=31300">Policy on Results</a> centre.</li></ul>
</div></section></div><hr /><div class="pol-app mrgn-tp-md"><section class="pol-sec"><h2 id="appA">Appendix A: Mandatory procedures</h2><div class="pol-content">
<ul class="pol-cla list-unstyled"><li class="pol-cla" id="claA.1"><span class="pol-cla-id">A.1</span>Departments must keep the plan.</li></ul>
</div></section></div></main></body></html>"""

REJECTED = "<html><head><title>Request Rejected</title></head><body>The requested URL was rejected.</body></html>"


def _flat(doc):
    out = []
    for kind, el, title, match in parse.containers(doc):
        nodes = parse.parse_container(el, kind[0] + (el.get("anchor") or ""))
        actors.assign(nodes)
        out += [(kind, title, match, n["key"], n["parent_key"], n["kind"], n["text"], n["actor_raw"], n["topic"], n["links"])
                for n in nodes]
    return out


def test_html_parses_like_xml(tmp_path):
    from lxml import etree
    (tmp_path / "page.html").write_text(HTML, encoding="utf-8")
    assert sources.sniff(tmp_path / "page.html") == "html"
    assert sources.html_meta(tmp_path / "page.html") == (7, "Directive on Testing", "2024-01-01")
    assert _flat(sources.load_doc(tmp_path / "page.html")) == _flat(etree.fromstring(XML))


def _hawk(tmp_path):
    d = tmp_path / "data" / "Directive"
    d.mkdir(parents=True)
    (d / "Testing__Directive_on_7_2024-01-01.xml").write_text(XML, encoding="utf-8")
    (d / "Testing Directive on_2025-08-31.xml").write_text(HTML, encoding="utf-8")  # same version, as HTML
    (d / "Testing Directive on_2026-03-14.xml").write_text(REJECTED)
    (tmp_path / "data" / "items.csv").write_text(
        "guid,title,link,pubDate,category,filename,updated_date\n"
        "7_2026-03-01,\"Testing, Directive on\",x,x,Directive,x,x\n"
        "8_2025-01-01,\"Other, Directive on\",x,x,Directive,x,x\n")
    return d


def test_index_prefers_xml_for_same_version_and_newer_snapshot(tmp_path):
    d = _hawk(tmp_path)
    idx = build_index(tmp_path)
    assert list(idx.id) == [7] and idx.source.iloc[0] == "xml" and idx.version_date.iloc[0] == "2024-01-01"
    snap = d / "7_2026-03-01"
    snap.mkdir()
    (snap / "20260302T000000Z.html").write_text(HTML.replace("2024-01-01", "2026-03-01"), encoding="utf-8")
    idx = build_index(tmp_path)
    assert idx.source.iloc[0] == "snapshot" and idx.version_date.iloc[0] == "2026-03-01"


def test_unlisted_instruments_are_dropped_and_coverage_flags_gaps(tmp_path):
    d = _hawk(tmp_path)
    (d / "Old__Directive_on_9_2010-01-01.xml").write_text(XML.replace('documentID="7"', 'documentID="9"'), encoding="utf-8")
    assert list(build_index(tmp_path).id) == [7]
    cov = coverage(tmp_path).set_index("id")
    assert cov.loc[7, "is_behind"]  # feed says 2026-03-01, best capture is 2024-01-01
    assert cov.loc[8, "is_behind"] and cov.loc[8, "best_source"] != cov.loc[8, "best_source"]  # no capture (NaN)
    local = tmp_path / "local" / "Directive" / "7_2026-03-01"
    local.mkdir(parents=True)
    (local / "20260302T000000Z.html").write_text(HTML.replace("2024-01-01", "2026-03-01"), encoding="utf-8")
    cov = coverage([tmp_path, tmp_path / "local"]).set_index("id")
    assert not cov.loc[7, "is_behind"] and cov.loc[7, "best_source"] == "snapshot"


def test_local_listing_and_uncategorized_folder(tmp_path):
    _hawk(tmp_path)
    local = tmp_path / "local"
    local.mkdir()
    (local / "listing.csv").write_text("id,title,category,url,source\n12,Service outside Canada,,x,az\n")
    cov = coverage([tmp_path, local]).set_index("id")
    assert cov.loc[12, "is_behind"] and cov.loc[12, "feed_date"] != cov.loc[12, "feed_date"]  # listed only: no feed date
    snap = local / "Uncategorized" / "12_2026-01-01"
    snap.mkdir(parents=True)
    (snap / "20260102T000000Z.html").write_text(HTML.replace("id=7&", "id=12&").replace("2024-01-01", "2026-01-01"), encoding="utf-8")
    cov = coverage([tmp_path, local]).set_index("id")
    assert not cov.loc[12, "is_behind"]
    assert 12 in set(build_index([tmp_path, local]).id)
