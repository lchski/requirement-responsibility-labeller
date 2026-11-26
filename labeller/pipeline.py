"""Run every stage: Hawk XML -> clauses, responsibilities, instruments and a role review queue."""
import json
from pathlib import Path

import pandas as pd
from lxml import etree

from . import actors, enrich, parse
from .index import build_index
from .roles import RoleMap, norm_key

CLAUSE_COLUMNS = [
    "id", "instrument", "type", "version", "captured", "container", "container_title", "anchor", "parent_anchor",
    "depth", "kind", "topic", "is_item", "actor_raw", "actor_how", "actor_clause", "role_id", "role", "role_parent",
    "role_qualifier", "modality", "frequency", "other_actors", "links", "stem", "text",
]


def extract_instrument(inst):
    doc = etree.parse(inst["path"]).getroot()
    rows = []
    for kind, el, title, title_match in parse.containers(doc):
        nodes = parse.parse_container(el, f"{kind[0]}{el.get('anchor') or ''}")
        if not nodes:
            continue
        actors.assign(nodes)
        if not (title_match or (kind == "appendix" and any(n["actor_here"] for n in nodes))):
            continue
        for n in nodes:
            rows.append(dict(
                id=inst["id"], instrument=inst["title"], type=inst["folder"], version=inst["version"],
                captured=inst["captured"], container=kind, container_title=title, anchor=n["key"],
                parent_anchor=n["parent_key"], depth=n["depth"], kind=n["kind"], topic=n["topic"] or None,
                is_item=not n["has_children"] and n["kind"] != "heading", actor_raw=n["actor_raw"],
                actor_how=n["actor_how"], actor_clause=n["actor_clause"], links=" ".join(n["links"]) or None,
                stem=n["stem"] or None, text=n["text"],
            ))
    return rows


def run(hawk_dir, out_dir, roles_csv="data/roles.csv", aliases_csv="data/role_aliases.csv"):
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    idx = build_index(hawk_dir)
    rows = []
    for inst in idx.to_dict("records"):
        rows.extend(extract_instrument(inst))
    actors.borrow_for_appendices(rows)
    df = pd.DataFrame(rows)

    rolemap = RoleMap(roles_csv, aliases_csv)
    matched = df.actor_raw.map(rolemap.match)
    df["role_id"] = matched.map(lambda m: m[0]).astype("Int64")
    df["role"] = matched.map(lambda m: m[1])
    df["role_parent"] = matched.map(lambda m: m[2])
    df["role_qualifier"] = matched.map(lambda m: m[3])

    full = (df.stem.fillna("") + " " + df.text).str.strip()
    df["modality"] = full.map(enrich.modality)
    df["frequency"] = df.text.map(enrich.frequency)
    df["other_actors"] = df.text.map(enrich.other_actors)

    df = df[CLAUSE_COLUMNS].sort_values(["id", "container", "anchor"], kind="stable")
    items = df[df.is_item].drop(columns=["is_item", "kind"])

    counts = items.groupby("id").agg(items=("text", "size"), items_with_role=("role", lambda s: int(s.notna().sum())),
                                     items_with_actor=("actor_raw", lambda s: int(s.notna().sum())))
    instruments = idx.drop(columns=["path"]).merge(counts, left_on="id", right_index=True, how="left")
    instruments[["items", "items_with_actor", "items_with_role"]] = instruments[["items", "items_with_actor", "items_with_role"]].fillna(0).astype(int)

    unmatched = items[items.actor_raw.notna() & items.role.isna()].copy()
    unmatched["key"] = unmatched.actor_raw.map(norm_key)
    queue = (unmatched.groupby("key")
             .agg(items=("text", "size"), instruments=("id", "nunique"), example=("actor_raw", "first"),
                  example_instrument=("id", "first"))
             .sort_values("items", ascending=False).reset_index().rename(columns={"key": "normalized_phrase"}))

    df.drop(columns=["is_item"]).to_csv(out / "clauses.csv", index=False)
    items.to_csv(out / "responsibilities.csv", index=False)
    instruments.to_csv(out / "instruments.csv", index=False)
    queue.to_csv(out / "role_review_queue.csv", index=False)
    summary = dict(
        instruments=len(idx), instruments_with_items=int(items.id.nunique()), items=len(items),
        items_with_actor=int(items.actor_raw.notna().sum()), items_with_role=int(items.role.notna().sum()),
        distinct_roles=int(items.role.nunique()), unmatched_phrases=len(queue),
    )
    summary["hawk_latest_capture"] = str(idx.captured.max()) if len(idx) else None
    (out / "summary.json").write_text(json.dumps(summary, indent=2) + "\n")
    return summary
