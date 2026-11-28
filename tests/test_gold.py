"""Accuracy against a hand-labelled sample of items.

Runs on the pipeline's output directory (LABELLER_OUTPUT, default ./output). Items are matched on
instrument id + the start of their text, so the test survives renumbering when Hawk picks up a new version.
"""
import os
from pathlib import Path

import pandas as pd
import pytest

HERE = Path(__file__).parent
OUTPUT = Path(os.environ.get("LABELLER_OUTPUT", "output"))
MIN_ROLE_ACCURACY = 0.80  # share of sampled responsibilities whose role matches the hand label
MIN_FOUND = 0.70          # share of sampled items still present (falls if instruments are rewritten)


def _key(text):
    return " ".join(str(text).split())[:80]


@pytest.fixture(scope="module")
def scored():
    path = OUTPUT / "responsibilities.csv"
    if not path.exists():
        pytest.skip(f"no pipeline output at {path}; run `python -m labeller` first")
    out = pd.read_csv(path, dtype=str).fillna("")
    out["key"] = out.text.map(_key)
    gold = pd.read_csv(HERE / "gold_sample.csv", dtype=str).fillna("")
    gold["key"] = gold.text.map(_key)
    # Prefer the same anchor (the same text can appear twice in one instrument); fall back to text alone.
    exact = gold.merge(out[["id", "anchor", "key", "role"]].drop_duplicates(["id", "anchor", "key"]), on=["id", "anchor", "key"], how="inner")
    rest = gold[~gold.set_index(["id", "anchor"]).index.isin(exact.set_index(["id", "anchor"]).index)]
    loose = rest.merge(out[["id", "key", "role"]].drop_duplicates(["id", "key"]), on=["id", "key"], how="left", indicator=True)
    exact["_merge"] = "both"
    return pd.concat([exact, loose], ignore_index=True)


def test_sample_still_found(scored):
    found = (scored._merge == "both").mean()
    assert found >= MIN_FOUND, f"only {found:.0%} of the gold sample is still in the output"


def test_role_accuracy(scored):
    resp = scored[(scored.is_responsibility == "yes") & (scored._merge == "both")]
    correct = (resp.role == resp.expected_role)
    misses = resp.loc[~correct, ["id", "expected_role", "role", "text"]]
    print(f"\nrole accuracy {correct.mean():.1%} on {len(resp)} sampled responsibilities")
    print(misses.to_string(max_colwidth=60))
    assert correct.mean() >= MIN_ROLE_ACCURACY
