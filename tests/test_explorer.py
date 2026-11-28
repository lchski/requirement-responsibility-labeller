"""The explorer's data build (explorer/build.py) runs on the committed output."""

import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location("explorer_build", ROOT / "explorer" / "build.py")
build = importlib.util.module_from_spec(spec)
spec.loader.exec_module(build)


def test_fragment():
    assert build.fragment("4.1.2") == "cla4.1.2"
    assert build.fragment("A.2.1") == "claA.2.1"
    assert build.fragment("c4#11") == "cha4"
    assert build.fragment("aB#3") == "appB"
    assert build.fragment("aappA#1") == "appA"
    assert build.fragment("") == ""


def test_build_on_committed_output():
    d = build.build(ROOT / "output", ROOT / "data" / "roles.csv", ROOT / "explorer" / "role_groups.csv")
    assert d["summary"]["items"] == len(d["items"]) > 0
    assert all(len(row) == len(d["itemFields"]) for row in d["items"])
    role_ids = {r["id"] for r in d["roles"]}
    assert all(row[d["itemFields"].index("role")] in role_ids | {None} for row in d["items"])
