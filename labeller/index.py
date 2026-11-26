"""Stage 1: pick the latest valid XML capture of each instrument in a Hawk checkout."""
import re
from pathlib import Path

import pandas as pd
from lxml import etree

from .text import fix_text

# Hawk folders that hold policy instruments (Cabinet directives and PINs are left out).
INSTRUMENT_FOLDERS = ["Policy", "Directive", "Standard", "Guideline", "Guidelines", "Guide", "Framework", "Policy framework"]
DATE_IN_NAME = re.compile(r"_(\d{4}-\d{2}-\d{2})\.xml$")


def build_index(hawk_dir):
    """One row per documentID: the newest capture that parses as a policy <doc> (firewall pages are skipped)."""
    hawk_dir = Path(hawk_dir)
    data_dir = hawk_dir / "data" if (hawk_dir / "data").is_dir() else hawk_dir
    best = {}
    for folder in INSTRUMENT_FOLDERS:
        for path in sorted((data_dir / folder).glob("*.xml")):
            try:
                root = etree.parse(str(path)).getroot()
            except etree.XMLSyntaxError:
                continue
            if root.tag != "doc" or not root.get("documentID"):
                continue  # e.g. a "Request Rejected" page saved by mistake
            m = DATE_IN_NAME.search(path.name)
            row = dict(
                id=int(root.get("documentID")),
                title=fix_text(root.get("title")),
                folder=folder,
                version=root.get("versionID"),
                captured=m.group(1) if m else "",
                path=str(path),
            )
            prev = best.get(row["id"])
            if prev is None or (row["captured"], row["version"] or "") > (prev["captured"], prev["version"] or ""):
                best[row["id"]] = row
    idx = pd.DataFrame(sorted(best.values(), key=lambda r: r["id"]))
    hierarchy = data_dir / "tbs_policy_hierarchy_full.csv"
    if hierarchy.exists() and len(idx):
        h = pd.read_csv(hierarchy, dtype=str)
        h = h.rename(columns={"ID": "id", "Hierarchy Paths": "hierarchy_paths"})[["id", "hierarchy_paths"]]
        h["id"] = pd.to_numeric(h["id"], errors="coerce")
        idx = idx.merge(h.dropna(subset=["id"]).astype({"id": int}).drop_duplicates("id"), on="id", how="left")
        idx["in_hierarchy"] = idx["id"].isin(h["id"])
    return idx
