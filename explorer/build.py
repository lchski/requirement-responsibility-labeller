"""Build the policy explorer's data file from the labeller's output.

Reads output/responsibilities.csv, output/instruments.csv, output/summary.json, data/roles.csv
and explorer/role_groups.csv, and writes explorer/site/data/explorer.json. Standard library only,
so it runs with any Python 3.10+ (no `uv sync` needed).

    python explorer/build.py                      # defaults
    python explorer/build.py --out _site/data     # somewhere else
"""

import argparse
import csv
import json
import re
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TBS_DOC = "https://www.tbs-sct.canada.ca/pol/doc-eng.aspx?id={id}"

# Instruments that set requirements, as opposed to guidance (TBS's own split).
MANDATORY_TYPES = {"Policy", "Directive", "Standard", "Framework"}
TYPE_ORDER = ["Policy", "Directive", "Standard", "Framework", "Guideline", "Guide"]
GROUP_ORDER = [
    "Employees",
    "Managers and executives",
    "Deputy heads and heads of institutions",
    "Departmental leads and committees",
    "Functional specialists and practitioners",
    "Ministers and central agencies",
    "Organizations",
    "Other roles",
]

NUMBERED = re.compile(r"^[0-9A-Z]+(\.[0-9A-Za-z]+)*$")  # 4.1.2, A.2.1, A.I.1.2
CHAPTER_POS = re.compile(r"^c([0-9A-Za-z]+)#")  # positional key inside a chapter
APPENDIX_POS = re.compile(r"^a(?:app)?([0-9A-Za-z]+)#")  # positional key inside an appendix


def fragment(anchor):
    """The element id on TBS's page for an item's anchor, or "" when there isn't one."""
    if not anchor:
        return ""
    if NUMBERED.match(anchor):
        return "cla" + anchor
    if m := CHAPTER_POS.match(anchor):
        return "cha" + m.group(1)
    if m := APPENDIX_POS.match(anchor):
        return "app" + m.group(1)
    return ""


def norm_type(t):
    t = (t or "").strip()
    return "Guideline" if t == "Guidelines" else t


def read_csv(path):
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def build(output_dir, roles_csv, groups_csv):
    items_rows = read_csv(output_dir / "responsibilities.csv")
    inst_rows = read_csv(output_dir / "instruments.csv")
    summary_path = output_dir / "summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}

    groups = {r["role_id"]: r["group"] for r in read_csv(groups_csv)}
    roles = []
    role_by_name = {}
    for r in read_csv(roles_csv):
        role = {
            "id": int(r["role_id"]),
            "name": r["role"],
            "parent": int(r["parent_role_id"]) if r["parent_role_id"] else None,
            "group": groups.get(r["role_id"], "Other roles"),
            "n": 0,
        }
        roles.append(role)
        role_by_name[r["role"].strip().lower()] = role

    # Instruments, and the parent/child links from TBS's policy hierarchy.
    instruments = []
    by_id = {}
    by_listed_title = {}
    for r in inst_rows:
        inst = {
            "id": int(r["id"]),
            "title": r["title"],
            "type": norm_type(r["folder"] or r["listed_category"]),
            "date": r["version_date"],
            "url": TBS_DOC.format(id=r["id"]),
            "parents": [],
            "children": [],
            "n": 0,
            "nRole": 0,
        }
        inst["mandatory"] = inst["type"] in MANDATORY_TYPES
        instruments.append(inst)
        by_id[inst["id"]] = inst
        if r["listed_title"]:
            by_listed_title[r["listed_title"].strip()] = inst
    for r in inst_rows:
        inst = by_id[int(r["id"])]
        own = (r["listed_title"] or "").strip()
        for path in filter(None, (p.strip() for p in (r["hierarchy_paths"] or "").split("||"))):
            steps = [s.strip() for s in path.split(" > ") if s.strip() and s.strip() != own]
            parent = next((by_listed_title[s] for s in reversed(steps) if s in by_listed_title), None)
            if parent and parent is not inst and parent["id"] not in inst["parents"]:
                inst["parents"].append(parent["id"])
                parent["children"].append(inst["id"])

    # Items, kept in document order. Stored as arrays to keep the file small; the field
    # order is in "itemFields".
    index_of = {inst["id"]: i for i, inst in enumerate(instruments)}
    fields = [
        "inst", "anchor", "frag", "section", "topic", "stem", "text", "role", "qualifier",
        "actor", "actorHow", "roleSource", "modality", "frequency", "others", "itemType",
    ]
    items = []
    unknown_roles = set()
    for r in items_rows:
        inst_id = int(r["id"])
        if inst_id not in index_of:
            continue
        role_name = (r.get("role_final") or r.get("role") or "").strip()
        role = role_by_name.get(role_name.lower()) if role_name else None
        if role_name and not role:
            unknown_roles.add(role_name)
        qualifier = r.get("role_qualifier", "") if r.get("role_source", "rules") != "llm" else r.get("llm_role_qualifier", "")
        actor = r.get("actor_raw") or r.get("llm_actor") or ""
        inst = instruments[index_of[inst_id]]
        inst["n"] += 1
        if role:
            role["n"] += 1
            inst["nRole"] += 1
        items.append([
            index_of[inst_id],
            r["anchor"],
            fragment(r["anchor"]),
            r["container_title"],
            r["topic"],
            r["stem"],
            r["text"],
            role["id"] if role else None,
            qualifier,
            actor,
            r["actor_how"] or ("llm" if r.get("role_source") == "llm" else ""),
            r.get("role_source", "") if role else "",
            r["modality"],
            r["frequency"],
            r["other_actors"],
            r.get("llm_item_type", ""),
        ])

    types = sorted({i["type"] for i in instruments}, key=lambda t: (TYPE_ORDER.index(t) if t in TYPE_ORDER else 99, t))
    return {
        "built": datetime.now(timezone.utc).strftime("%Y-%m-%d"),
        "latestVersionDate": summary.get("latest_version_date") or max((i["date"] for i in instruments), default=""),
        "summary": {
            "instruments": len(instruments),
            "instrumentsWithItems": sum(1 for i in instruments if i["n"]),
            "items": len(items),
            "itemsWithRole": sum(1 for it in items if it[7] is not None),
            "listedInstruments": summary.get("listed_instruments"),
            "listedBehindOrMissing": summary.get("listed_behind_or_missing"),
        },
        "types": types,
        "mandatoryTypes": sorted(MANDATORY_TYPES),
        "groups": GROUP_ORDER,
        "roles": roles,
        "instruments": instruments,
        "itemFields": fields,
        "items": items,
        "unknownRoles": sorted(unknown_roles),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--output-dir", type=Path, default=ROOT / "output", help="the labeller's output folder")
    ap.add_argument("--roles", type=Path, default=ROOT / "data" / "roles.csv")
    ap.add_argument("--groups", type=Path, default=ROOT / "explorer" / "role_groups.csv")
    ap.add_argument("--out", type=Path, default=ROOT / "explorer" / "site" / "data")
    args = ap.parse_args()

    data = build(args.output_dir, args.roles, args.groups)
    args.out.mkdir(parents=True, exist_ok=True)
    path = args.out / "explorer.json"
    path.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    s = data["summary"]
    print(f"Wrote {path} ({path.stat().st_size / 1e6:.1f} MB): {s['items']} items, "
          f"{s['instrumentsWithItems']} of {s['instruments']} instruments with items, {len(data['roles'])} roles")
    ungrouped = [r["name"] for r in data["roles"] if r["group"] == "Other roles"]
    if ungrouped:
        print("Roles with no group in explorer/role_groups.csv (shown under Other roles):", ", ".join(ungrouped))
    if data["unknownRoles"]:
        print("Roles in the output that aren't in roles.csv (shown as unassigned):", ", ".join(data["unknownRoles"]))


if __name__ == "__main__":
    main()
