"""The local gap-filler, with TBS replaced by canned pages (no network)."""
import csv

import pytest

from labeller import gaps

PAGE = """<!DOCTYPE html><html><head><title>Directive on Testing</title></head><body>
<a href="doc-fra.aspx?id={id}&amp;section=html">Français</a>
<h1 id="wb-cont" property="name">{title}</h1>
<section id="cla4.1">The deputy head is responsible for testing.</section>
<script>wet.builder.footer({{ preFooter: {{ dateModified: "{date}", showFeedback: false }} }});</script>
</body></html>"""
REJECTED = "<html><head><title>Request Rejected</title></head><body>The requested URL was rejected.</body></html>"
XML = '<doc documentID="{id}" title="Directive on Testing" versionID="3"><chapters/></doc>'


def page(doc_id="111", title="Directive on Testing", date="2026-09-04"):
    return PAGE.format(id=doc_id, title=title, date=date)


def test_parse_listing_and_category():
    html = ('<li><a href="doc-eng.aspx?id=111">Testing, Directive on</a></li>'
            '<li><a href="https://www.tbs-sct.canada.ca/pol/doc-eng.aspx?id=222&amp;section=html">Guide to <b>Things</b></a></li>'
            '<li><a href="doc-eng.aspx?id=111">duplicate</a></li>')
    assert gaps.parse_listing(html) == {"111": "Testing, Directive on", "222": "Guide to Things"}
    assert gaps.category_for("Testing, Directive on") == "Directive"
    assert gaps.category_for("Guidelines on Section 91") == "Guidelines"
    assert gaps.category_for("Guide to Things") == "Guide"
    assert gaps.category_for("Policy Framework for Testing") == "Policy framework"
    assert gaps.category_for("Notice about a program") == ""


def test_refresh_listing_unions_both_lists(tmp_path):
    pages = {gaps.LISTINGS["hierarchy"]: '<a href="doc-eng.aspx?id=1">Policy on A</a><a href="doc-eng.aspx?id=2">Directive on B</a>',
             gaps.LISTINGS["az"]: '<a href="doc-eng.aspx?id=2">B, Directive on</a><a href="doc-eng.aspx?id=3">C, Guide to</a>'}
    rows = gaps.refresh_listing(tmp_path, fetch=pages.__getitem__)
    assert [(r["id"], r["source"], r["category"]) for r in rows] == [
        ("1", "hierarchy", "Policy"), ("2", "both", "Directive"), ("3", "az", "Guide")]
    with open(tmp_path / "listing.csv", newline="") as f:
        assert [r["id"] for r in csv.DictReader(f)] == ["1", "2", "3"]


def test_refresh_listing_keeps_previous_when_blocked(tmp_path):
    (tmp_path / "listing.csv").write_text("id,title,category,url,source\n9,Old,Policy,u,az\n")

    def blocked(url):
        raise gaps.Blocked("nope")

    assert [r["id"] for r in gaps.refresh_listing(tmp_path, fetch=blocked)] == ["9"]


def test_inspect_page():
    assert gaps.inspect_page(page()) == dict(id="111", title="Directive on Testing", category="Directive", date="2026-09-04")
    assert gaps.inspect_page(REJECTED) is None
    assert gaps.inspect_page("<html><body>Not a policy</body></html>") is None


def test_fetch_instrument_saves_html_and_real_xml_in_hawk_layout(tmp_path):
    pages = {gaps.doc_url(111, "html"): page(), gaps.doc_url(111, "xml"): XML.format(id=111)}
    info, paths = gaps.fetch_instrument(111, tmp_path, fetch=pages.__getitem__, delay=0)
    assert info["date"] == "2026-09-04"
    assert {p.suffix for p in paths} == {".html", ".xml"}
    assert all(p.parent == tmp_path / "Directive" / "111_2026-09-04" for p in paths)
    assert paths[0].stem == paths[1].stem  # same UTC stamp


def test_fetch_instrument_skips_html_served_as_xml(tmp_path):
    pages = {gaps.doc_url(111, "html"): page(), gaps.doc_url(111, "xml"): page()}
    _, paths = gaps.fetch_instrument(111, tmp_path, fetch=pages.__getitem__, delay=0)
    assert [p.suffix for p in paths] == [".html"]


def test_fetch_instrument_not_newer_saves_nothing(tmp_path):
    pages = {gaps.doc_url(111, "html"): page(date="2026-01-01")}
    _, paths = gaps.fetch_instrument(111, tmp_path, fetch=pages.__getitem__, delay=0, newer_than="2026-01-01")
    assert paths == [] and not any(tmp_path.iterdir())


def test_fetch_instrument_raises_on_firewall(tmp_path):
    with pytest.raises(gaps.Blocked):
        gaps.fetch_instrument(111, tmp_path, fetch=lambda url: REJECTED, delay=0)


def test_import_files(tmp_path):
    good = tmp_path / "saved.html"
    good.write_text(page(doc_id="32800", title="Guidelines on Section 91", date="2026-10-01"))
    bad = tmp_path / "rejected.html"
    bad.write_text(REJECTED)
    saved = gaps.import_files([good, bad], tmp_path / "local")
    assert len(saved) == 1
    assert saved[0].parent == tmp_path / "local" / "Guidelines" / "32800_2026-10-01"


def test_main_fetches_gaps_then_falls_back_to_browser(tmp_path, monkeypatch, capsys):
    import pandas as pd

    cov = pd.DataFrame([
        dict(id=111, title="Testing, Directive on", category="Directive", feed_date="2026-09-04", best_date="2026-01-01", is_behind=True),
        dict(id=222, title="Things, Guide to", category="Guide", feed_date="", best_date="", is_behind=True),
        dict(id=333, title="Current, Policy on", category="Policy", feed_date="2025-01-01", best_date="2025-01-01", is_behind=False),
    ])
    monkeypatch.setattr(gaps, "find_gaps", lambda roots, check_all=False: cov if check_all else cov[cov.is_behind])
    pages = {gaps.doc_url(111, "html"): page(), gaps.doc_url(111, "xml"): REJECTED}

    def fetch(url):
        if url in pages:
            return pages[url]
        raise gaps.Blocked(f"{url}: TBS firewall rejected the request")

    monkeypatch.setattr(gaps, "get", fetch)
    monkeypatch.setattr(gaps.time, "sleep", lambda s: None)
    gaps.main(["--local", str(tmp_path), "--no-listing", "--delay", "0"])
    out = capsys.readouterr().out
    assert "2 instrument(s) to fetch" in out and "missing" in out and "behind: have 2026-01-01" in out
    assert (tmp_path / "Directive" / "111_2026-09-04").is_dir()
    assert "Fetch the rest in your browser" in out and gaps.doc_url(222) in out and gaps.doc_url(111) not in out.split("browser")[1]


def test_fetch_instrument_non_instrument_page_is_skippable(tmp_path):
    with pytest.raises(gaps.NotAnInstrument):
        gaps.fetch_instrument(111, tmp_path, fetch=lambda url: "<html><body>Moved</body></html>", delay=0)
