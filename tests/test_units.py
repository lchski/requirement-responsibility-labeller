"""Small, self-contained checks of each stage, using hand-written XML in both schema generations."""
from pathlib import Path

from lxml import etree

from labeller import actors, parse
from labeller.index import build_index
from labeller.roles import RoleMap
from labeller.text import fix_text

DATA = Path(__file__).resolve().parents[1] / "data"

CURRENT = """<doc documentID="1" title="Directive on Testing" versionID="1"><chapters>
<chapter anchor="4" title="Requirements"><clauses>
  <clause anchor="4.1">The chief audit executive is responsible for the following:
    <clauses>
      <clause anchor="4.1.1">Establishing a plan that:
        <clauses><clause anchor="4.1.1.1">Is approved by the deputy head; and</clause></clauses>
      </clause>
      <section><header><h3>Reporting</h3></header>
        <clauses><clause anchor="4.1.2">Reporting annually to the committee, following Appendix B.</clause></clauses>
      </section>
    </clauses>
  </clause>
</clauses></chapter></chapters>
<appendices><appendix anchor="B" title="Appendix B: Mandatory procedures"><clauses>
  <clause anchor="B.1">Do not share the plan.</clause>
</clauses></appendix></appendices></doc>"""

LEGACY = """<doc documentID="2" title="Policy on Testing" versionID="1"><chapters>
<chapter anchor="6" title="6. Policy Requirements">
  <section anchor="6.1" title="6.1 Approval authorities are responsible for:">
    <p><strong>6.1.1 Decision making</strong>: Making decisions on requests.</p>
  </section>
  <section anchor="6.2" title="6.2 Governance">
    <p>Deputy heads are responsible for the following:</p>
    <ul><li>6.2.1 Designating an official.<ul><li>Who reports to the deputy head.</li></ul></li></ul>
    <h4>6.2.2 The senior departmental official is responsible for:</h4>
    <p><strong>6.2.2.1</strong> Testing applications.</p>
  </section>
</chapter></chapters></doc>"""


def _items(xml):
    doc = etree.fromstring(xml)
    out = {}
    for kind, el, title, match in parse.containers(doc):
        nodes = parse.parse_container(el, kind[0] + (el.get("anchor") or ""))
        actors.assign(nodes)
        for n in nodes:
            out[n["key"]] = n
    return out


def test_current_schema_inherits_actor_from_ancestor():
    items = _items(CURRENT)
    assert items["4.1.1.1"]["actor_raw"] == "chief audit executive"
    assert items["4.1.1.1"]["actor_how"] == "ancestor"
    assert items["4.1.1.1"]["stem"] == "Establishing a plan that:"
    assert items["4.1.2"]["topic"] == "Reporting"
    assert not items["4.1.1.1"]["has_children"] and items["4.1.1"]["has_children"]


def test_legacy_schema_section_titles_lists_and_headings():
    items = _items(LEGACY)
    assert items["6.1.1"]["actor_raw"] == "Approval authorities"
    assert items["6.2.1"]["actor_raw"] == "Deputy heads"
    nested = next(n for n in items.values() if n["text"].startswith("Who reports"))
    assert nested["actor_raw"] == "Deputy heads" and nested["parent_key"] == "6.2.1"
    assert items["6.2.2.1"]["actor_raw"] == "senior departmental official"


def test_appendix_borrows_actor_from_citing_clause():
    doc = etree.fromstring(CURRENT)
    rows = []
    for kind, el, title, match in parse.containers(doc):
        nodes = parse.parse_container(el, kind[0] + (el.get("anchor") or ""))
        actors.assign(nodes)
        rows += [dict(id=1, container=kind, container_title=title, anchor=n["key"], text=n["text"],
                      actor_raw=n["actor_raw"], actor_clause=n["actor_clause"], actor_how=n["actor_how"]) for n in nodes]
    actors.borrow_for_appendices(rows)
    b1 = next(r for r in rows if r["anchor"] == "B.1")
    assert b1["actor_raw"] == "chief audit executive" and b1["actor_how"] == "appendix-reference"


def test_actor_detection_rejects_non_roles():
    assert actors.actor_in("Treasury Board approval is required for new programs.") is None
    assert actors.actor_in("Providing written approval for publication must occur first.") is None
    assert actors.actor_in("The telework agreement must include the following:") is None
    assert actors.actor_in("Managers, functional specialists, and equivalents responsible for Web pages are responsible for:") \
        == "Managers, functional specialists, and equivalents responsible for Web pages"
    assert actors.actor_in("Once a strike is declared, departments must notify TBS.") == "departments"


def test_roles_match_longest_prefix_and_keep_qualifier():
    m = RoleMap(DATA / "roles.csv", DATA / "role_aliases.csv")
    rid, role, parent, qualifier = m.match("Heads of evaluation designated under subsection 4.3.12 of the policy")
    assert role == "Departmental heads of evaluation"
    assert qualifier == "designated under subsection 4.3.12 of the policy"
    assert m.match("Deputy heads or their delegates")[1] == "Deputy heads"
    assert m.match("the chief financial officer (CFO)")[1] == "Departmental Chief Financial Officer"
    assert m.match("Departmental managers responsible for preparing funding agreements")[2] == "Managers"
    assert m.match("Some unknown body")[0] is None


def test_fix_text_undoes_double_encoding():
    assert fix_text("Ministerâ\u0080\u0099s  office") == "Minister’s office"


def test_index_skips_firewall_pages(tmp_path):
    d = tmp_path / "data" / "Directive"
    d.mkdir(parents=True)
    (d / "Testing_Directive_on_1_2024-01-01.xml").write_text(CURRENT, encoding="utf-8")
    (d / "Testing Directive on_2025-01-01.xml").write_text("<html><head><title>Request Rejected</title></head></html>")
    idx = build_index(tmp_path)
    assert list(idx.id) == [1] and idx.captured.iloc[0] == "2024-01-01"
