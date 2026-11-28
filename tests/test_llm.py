"""The LLM pass, with a fake model standing in for the API: caching, budget, and how answers are merged."""
import json
import shutil
from pathlib import Path

import pandas as pd
import pytest

from labeller import llm

DATA = Path(__file__).resolve().parents[1] / "data"


def _write_output(d):
    items = pd.DataFrame([
        dict(id="1", instrument="Directive on Testing", container="chapter", container_title="Requirements", anchor="4.1.1",
             topic="", stem="", text="Approving the plan.", actor_raw="Deputy heads", actor_how="ancestor", role="Deputy heads"),
        dict(id="1", instrument="Directive on Testing", container="chapter", container_title="Requirements", anchor="4.1.2",
             topic="", stem="", text="Two weeks of leave with pay.", actor_raw="Deputy heads", actor_how="ancestor", role="Deputy heads"),
        dict(id="1", instrument="Directive on Testing", container="appendix", container_title="Appendix B: Procedures", anchor="B.1",
             topic="", stem="", text="Do not share the plan.", actor_raw=None, actor_how=None, role=None),
    ])
    clauses = pd.DataFrame([
        dict(id="1", container="chapter", container_title="Requirements", anchor="4.1", topic="", stem="",
             text="The chief audit executive is to:", actor_raw="chief audit executive", actor_how="self"),
    ])
    items.to_csv(d / "responsibilities.csv", index=False)
    clauses.to_csv(d / "clauses.csv", index=False)
    pd.DataFrame([dict(normalized_phrase="audit oracle", items=3, instruments=1, example="Audit oracles", example_instrument=1)]) \
        .to_csv(d / "role_review_queue.csv", index=False)
    (d / "summary.json").write_text("{}")


class FakeModel:
    def __init__(self):
        self.calls = 0

    def __call__(self, system, user, schema):
        self.calls += 1
        if schema is llm.ClassifyOut:
            items = json.loads(user.split("\n", 1)[1])
            return llm.ClassifyOut(labels=[llm.ItemLabel(key=i["key"], item_type="entitlement" if "leave" in i["text"] else "responsibility")
                                           for i in items])
        if schema is llm.ActorOut:
            items = json.loads(user.split("Items:\n", 1)[1])
            return llm.ActorOut(picks=[llm.ActorPick(key=i["key"], actor="chief audit executive", evidence="4.1") for i in items])
        if schema is llm.RoleOut:
            phrases = json.loads(user.split("Unmatched phrases:\n", 1)[1])
            return llm.RoleOut(suggestions=[llm.RoleSuggestion(phrase=p, is_role=True, role_id=None, new_role="Audit oracles",
                                                               parent_role_id=None, rationale="test") for p in phrases])
        raise AssertionError(schema)


@pytest.fixture
def workdir(tmp_path):
    _write_output(tmp_path)
    return tmp_path


def _run(d, fake, **kw):
    return llm.run(out_dir=d, cache_path=d / "cache.jsonl", roles_csv=DATA / "roles.csv", aliases_csv=DATA / "role_aliases.csv",
                   call=fake, workers=1, **kw)


def test_merges_answers_into_llm_columns(workdir):
    _run(workdir, FakeModel())
    out = pd.read_csv(workdir / "responsibilities.csv", dtype=str)
    assert list(out.llm_item_type) == ["responsibility", "entitlement", "responsibility"]
    b1 = out[out.anchor == "B.1"].iloc[0]
    assert b1.llm_actor == "chief audit executive" and b1.llm_role == "Departmental chief audit executive"
    assert b1.role_final == "Departmental chief audit executive" and b1.role_source == "llm"
    assert out[out.anchor == "4.1.1"].iloc[0].role_source == "rules"
    sugg = pd.read_csv(workdir / "role_suggestions.csv")
    assert sugg.new_role.tolist() == ["Audit oracles"]


def test_second_run_is_served_from_cache(workdir):
    first = FakeModel()
    _run(workdir, first)
    _write_output(workdir)  # the rules pipeline rewrites output/ on every run
    second = FakeModel()
    summary = _run(workdir, second)
    assert first.calls == 3 and second.calls == 0 and summary["new_cache_entries"] == 0


def test_budget_caps_requests(workdir):
    fake = FakeModel()
    summary = _run(workdir, fake, max_requests=1)
    assert fake.calls == 1 and summary["requests_skipped_over_budget"] == 2


def test_rejects_actor_the_instrument_does_not_name(workdir):
    class Inventive(FakeModel):
        def __call__(self, system, user, schema):
            if schema is llm.ActorOut:
                items = json.loads(user.split("Items:\n", 1)[1])
                return llm.ActorOut(picks=[llm.ActorPick(key=i["key"], actor="The Prime Minister", evidence="?") for i in items])
            return super().__call__(system, user, schema)

    _run(workdir, Inventive(), jobs=("actors",))
    out = pd.read_csv(workdir / "responsibilities.csv", dtype=str)
    assert out[out.anchor == "B.1"].llm_actor.isna().all()


def test_refusal_is_not_cached(workdir):
    _run(workdir, lambda system, user, schema: None, jobs=("classify",))
    assert not (workdir / "cache.jsonl").read_text().strip()
