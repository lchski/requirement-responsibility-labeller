"""Optional LLM pass over the rules output (python -m labeller.llm).

Three narrow jobs, each sent only what the rules couldn't settle:

1. classify  - is each item a responsibility, or an entitlement / definition / criterion / context?
2. actors    - for items with no actor, pick the responsible actor from the actors the same
               instrument already names, quoting the evidence (or say there is none).
3. roles     - for actor phrases with no canonical role, suggest an existing role or a new one.
               Written to output/role_suggestions.csv for a person to review; never applied silently.

Every answer is cached in data/llm_cache.jsonl, keyed on a hash of the model, prompt version and
input, so a scheduled run only pays for items that are new or changed. Every value the LLM supplies
lands in an llm_* column next to the rules columns, so it can always be told apart or filtered out.
"""
import argparse
import hashlib
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import Literal, Optional

import pandas as pd
from pydantic import BaseModel

from .roles import RoleMap

MODEL = os.environ.get("LABELLER_MODEL", "claude-haiku-5-5")
# Models that accept the server-side refusal fallback (Haiku has none; a refusal is simply not cached).
FALLBACK_MODELS = ("claude-opus-5-5", "claude-opus-5", "claude-sonnet-5-5", "claude-fable-5-2", "claude-fable-5-1")
PROMPT_VERSION = "1"
CLASSIFY_BATCH = 40   # items per request
ACTOR_BATCH = 25
ROLE_BATCH = 60

ItemType = Literal["responsibility", "entitlement", "definition", "criterion", "context"]


# ---------- response schemas (structured outputs) ----------

class ItemLabel(BaseModel):
    key: str
    item_type: ItemType


class ClassifyOut(BaseModel):
    labels: list[ItemLabel]


class ActorPick(BaseModel):
    key: str
    actor: Optional[str]  # verbatim from the candidate list, or null when the text names none
    evidence: str         # short quote from the instrument that supports the pick


class ActorOut(BaseModel):
    picks: list[ActorPick]


class RoleSuggestion(BaseModel):
    phrase: str
    is_role: bool                   # false when the phrase isn't really an actor (a document, an event...)
    role_id: Optional[int]          # an existing role from the list, if one fits
    new_role: Optional[str]         # otherwise a proposed canonical name
    parent_role_id: Optional[int]   # for a new role that is a subset of an existing one
    rationale: str


class RoleOut(BaseModel):
    suggestions: list[RoleSuggestion]


# ---------- prompts ----------

CLASSIFY_SYSTEM = """You label items extracted from Government of Canada Treasury Board policy instruments \
(policies, directives, standards, guidelines). Each item is one leaf clause, shown with the parent text it \
completes ("stem"), its heading and the instrument it comes from.

Label every item with exactly one item_type:
- responsibility: something a person or organization must, should or may do, or must ensure (a duty, \
  task, requirement or authority to act), including list items that complete such a duty.
- entitlement: what someone is entitled to or receives (pay, leave, benefits, allowances, eligibility).
- definition: defines a term or describes what something is.
- criterion: a condition, threshold, element or piece of content that something must meet or contain, \
  where the item itself is not an action (e.g. "The total cost does not exceed the approved authority").
- context: background, purpose, scope, effective dates, references, examples or other descriptive text.

When an item is a list entry, read it together with its stem: "Ensuring that products are:" + "non-partisan;" \
is a responsibility. Return one label per key, using the keys exactly as given."""

ACTOR_SYSTEM = """You find who is responsible for items in Government of Canada Treasury Board policy \
instruments, for items where a rules-based parser found no actor. For each item you get its text, the \
parent text it completes, its heading and the section it sits in, plus the list of actor statements that \
the same instrument makes elsewhere (for example "4.1 The chief security officer is to:").

For each item, set actor to the one candidate actor, copied exactly as written in the candidate list, \
that the instrument makes responsible for it. Typical evidence: an appendix of procedures that a \
requirements clause tells that actor to follow, or a heading that names the actor. If the instrument does \
not make any candidate responsible for the item, or the item is not a duty at all, set actor to null. \
Keep evidence to one short quote or reference (e.g. 'Clause 4.1.6: "following the procedures in Appendix B"'). \
Do not guess."""

ROLE_SYSTEM = """You maintain a list of canonical roles used to label responsibilities in Government of \
Canada Treasury Board policy instruments. You get the list of existing roles (id, name, parent id) and \
actor phrases that matched none of them.

For each phrase:
- is_role: false if the phrase is not an actor at all (a document, an amount, a sentence fragment).
- role_id: the existing role it means, if any. Prefer an existing role; qualifiers such as "in a custodian \
  department" or "designated under subsection 4.3.12" don't make a new role.
- new_role: only when no existing role fits, a short plural canonical name in the style of the list.
- parent_role_id: for a new role that is a kind of an existing role (e.g. a kind of manager), that role's id.
- rationale: one sentence.
Return one suggestion per phrase, copying the phrase exactly."""


# ---------- cache and calls ----------

class Cache:
    def __init__(self, path):
        self.path = Path(path)
        self.data = {}
        if self.path.exists():
            for line in self.path.read_text(encoding="utf-8").splitlines():
                if line.strip():
                    rec = json.loads(line)
                    self.data[rec["k"]] = rec["v"]
        self.new = {}

    @staticmethod
    def key(job, payload):
        blob = json.dumps([job, MODEL, PROMPT_VERSION, payload], sort_keys=True, ensure_ascii=False)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:32]

    def get(self, k):
        return self.data.get(k)

    def put(self, k, v):
        self.data[k] = v
        self.new[k] = v

    def save(self):
        """Rewrite the cache sorted by key, so the committed file diffs cleanly."""
        self.path.parent.mkdir(parents=True, exist_ok=True)
        lines = [json.dumps({"k": k, "v": self.data[k]}, sort_keys=True, ensure_ascii=False) for k in sorted(self.data)]
        self.path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")


def anthropic_caller(effort):
    """Return call(system, user, schema) -> parsed model or None (refusal). The SDK is imported and the
    client created on first use, so the rules pipeline, tests and cache-only runs need neither.
    call.usage accumulates the tokens reported by the API."""
    client = None
    usage = {"input_tokens": 0, "output_tokens": 0}

    def call(system, user, schema):
        nonlocal client
        if client is None:
            import anthropic
            client = anthropic.Anthropic()
        extra = {}
        if MODEL in FALLBACK_MODELS:
            extra = dict(betas=["server-side-fallback-2026-07-01"], fallbacks="default")
        response = client.beta.messages.parse(
            model=MODEL,
            max_tokens=16000,
            system=system,
            messages=[{"role": "user", "content": user}],
            output_format=schema,
            output_config={"effort": effort},
            **extra,
        )
        usage["input_tokens"] += response.usage.input_tokens or 0
        usage["output_tokens"] += response.usage.output_tokens or 0
        if response.stop_reason == "refusal":
            return None
        return response.parsed_output

    call.usage = usage
    return call


class Budget:
    def __init__(self, max_requests):
        self.left = max_requests
        self.used = 0
        self.skipped = 0

    def take(self):
        if self.left <= 0:
            self.skipped += 1
            return False
        self.left -= 1
        self.used += 1
        return True


def _run_batches(batches, call, budget, workers):
    """batches: [(cache_key, system, user, schema)] -> {cache_key: parsed or None}."""
    todo = [b for b in batches if budget.take()]

    def one(b):
        k, system, user, schema = b
        try:
            return k, call(system, user, schema)
        except Exception as e:  # one failed request shouldn't sink the run; it is retried next time
            print(f"request failed: {type(e).__name__}: {e}", file=sys.stderr)
            return k, None

    with ThreadPoolExecutor(max_workers=workers) as pool:
        return dict(pool.map(one, todo))


def _chunks(seq, n):
    return [seq[i:i + n] for i in range(0, len(seq), n)]


def _content(p):
    """Cache on content, not on the item key: positional keys shift when an instrument is renumbered."""
    return {k: v for k, v in p.items() if k != "key"}


def _item_payload(r):
    return {"key": r["item_key"], "instrument": r["instrument"], "section": r["container_title"],
            "heading": r["topic"], "stem": r["stem"], "text": r["text"]}


# ---------- jobs ----------

def classify(items, cache, call, budget, workers):
    """Adds llm_item_type."""
    payloads = {r["item_key"]: _item_payload(r) for r in items.to_dict("records")}
    labels, pending = {}, []
    for key, p in payloads.items():
        hit = cache.get(Cache.key("classify", _content(p)))
        if hit is not None:
            labels[key] = hit
        else:
            pending.append(p)
    batches = []
    for chunk in _chunks(pending, CLASSIFY_BATCH):
        user = "Label these items:\n" + json.dumps(chunk, ensure_ascii=False, separators=(",", ":"))
        batches.append((tuple(p["key"] for p in chunk), CLASSIFY_SYSTEM, user, ClassifyOut))
    results = _run_batches([(json.dumps(k), s, u, sc) for k, s, u, sc in batches], call, budget, workers)
    for kjson, out in results.items():
        if out is None:
            continue
        keys = set(json.loads(kjson))
        for lab in out.labels:
            if lab.key in keys:
                labels[lab.key] = lab.item_type
                cache.put(Cache.key("classify", _content(payloads[lab.key])), lab.item_type)
    return items["item_key"].map(labels)


def fill_actors(items, clauses, cache, call, budget, workers):
    """For items with no rules actor, pick one from the instrument's own actor statements.
    Returns (llm_actor, llm_actor_evidence) Series."""
    missing = items[items.actor_raw.isna()]
    stmts = clauses[clauses.actor_how.eq("self")].groupby("id")
    actor, evidence, pending = {}, {}, []
    for iid, group in missing.groupby("id"):
        if iid not in stmts.groups:
            continue
        cand = stmts.get_group(iid)
        candidates = [{"actor": a, "statement": f"{anc}: {t}"} for a, anc, t in
                      cand.drop_duplicates("actor_raw")[["actor_raw", "anchor", "text"]].itertuples(index=False)]
        names = {c["actor"] for c in candidates}
        for r in group.to_dict("records"):
            p = _item_payload(r)
            ck = Cache.key("actors", {"item": _content(p), "candidates": candidates})
            hit = cache.get(ck)
            if hit is not None:
                actor[r["item_key"]], evidence[r["item_key"]] = hit
            else:
                pending.append((iid, candidates, names, p, ck))
    batches, meta = [], {}
    by_inst = {}
    for iid, candidates, names, p, ck in pending:
        by_inst.setdefault(iid, (candidates, names, []))[2].append((p, ck))
    for iid, (candidates, names, rows) in by_inst.items():
        for chunk in _chunks(rows, ACTOR_BATCH):
            user = ("Candidate actors named in this instrument:\n" + json.dumps(candidates, ensure_ascii=False, separators=(",", ":"))
                    + "\n\nItems:\n" + json.dumps([p for p, _ in chunk], ensure_ascii=False, separators=(",", ":")))
            bk = Cache.key("actors-batch", [ck for _, ck in chunk])
            meta[bk] = (names, {p["key"]: ck for p, ck in chunk})
            batches.append((bk, ACTOR_SYSTEM, user, ActorOut))
    for bk, out in _run_batches(batches, call, budget, workers).items():
        if out is None:
            continue
        names, keymap = meta[bk]
        for pick in out.picks:
            if pick.key not in keymap:
                continue
            a = pick.actor if pick.actor in names else None  # only accept an actor the instrument actually names
            actor[pick.key], evidence[pick.key] = a, pick.evidence
            cache.put(keymap[pick.key], [a, pick.evidence])
    return items["item_key"].map(actor), items["item_key"].map(evidence)


def suggest_roles(phrases, roles, cache, call, budget, workers):
    """phrases: DataFrame with normalized_phrase, example, items. Returns a suggestions DataFrame."""
    role_list = roles[["role_id", "role", "parent_role_id"]].astype({"parent_role_id": "object"}).where(roles.notna(), None)
    role_json = json.dumps(role_list.to_dict("records"), ensure_ascii=False)
    out_rows, pending = {}, []
    for r in phrases.to_dict("records"):
        ck = Cache.key("roles", {"phrase": r["example"], "roles": role_json})
        hit = cache.get(ck)
        if hit is not None:
            out_rows[r["example"]] = hit
        else:
            pending.append((r["example"], ck))
    batches, meta = [], {}
    for chunk in _chunks(pending, ROLE_BATCH):
        user = ("Existing roles:\n" + role_json + "\n\nUnmatched phrases:\n"
                + json.dumps([p for p, _ in chunk], ensure_ascii=False, separators=(",", ":")))
        bk = Cache.key("roles-batch", [ck for _, ck in chunk])
        meta[bk] = dict(chunk)
        batches.append((bk, ROLE_SYSTEM, user, RoleOut))
    for bk, out in _run_batches(batches, call, budget, workers).items():
        if out is None:
            continue
        for s in out.suggestions:
            if s.phrase in meta[bk]:
                v = s.model_dump()
                out_rows[s.phrase] = v
                cache.put(meta[bk][s.phrase], v)
    rows = []
    for r in phrases.to_dict("records"):
        s = out_rows.get(r["example"])
        if s:
            rows.append(dict(normalized_phrase=r["normalized_phrase"], example=r["example"], items=r["items"], **{k: s[k] for k in
                        ("is_role", "role_id", "new_role", "parent_role_id", "rationale")}))
    return pd.DataFrame(rows, columns=["normalized_phrase", "example", "items", "is_role", "role_id", "new_role",
                                       "parent_role_id", "rationale"])


# ---------- driver ----------

def run(out_dir="output", cache_path="data/llm_cache.jsonl", roles_csv="data/roles.csv",
        aliases_csv="data/role_aliases.csv", max_requests=400, workers=4, call=None, jobs=("classify", "actors", "roles")):
    out = Path(out_dir)
    items = pd.read_csv(out / "responsibilities.csv", dtype=str)
    clauses = pd.read_csv(out / "clauses.csv", dtype=str)
    for df in (items, clauses):
        df[["topic", "stem", "container_title"]] = df[["topic", "stem", "container_title"]].fillna("")
    items["item_key"] = items["id"] + "|" + items["container"] + "|" + items["anchor"]
    cache = Cache(cache_path)
    budget = Budget(max_requests)
    if call is None:
        call = {"classify": anthropic_caller("low"), "actors": anthropic_caller("medium"), "roles": anthropic_caller("medium")}
    elif callable(call):
        call = {j: call for j in jobs}

    rolemap = RoleMap(roles_csv, aliases_csv)
    if "classify" in jobs:
        items["llm_item_type"] = classify(items, cache, call["classify"], budget, workers)
    if "actors" in jobs:
        items["llm_actor"], items["llm_actor_evidence"] = fill_actors(items, clauses, cache, call["actors"], budget, workers)
        matched = items.llm_actor.map(rolemap.match)
        items["llm_role"] = matched.map(lambda m: m[1])
        items["llm_role_qualifier"] = matched.map(lambda m: m[3])
        # Convenience columns: the rules answer where there is one, else the LLM's, and where it came from.
        items["role_final"] = items.role.where(items.role.notna(), items.llm_role)
        items["role_source"] = items.role.notna().map({True: "rules", False: None})
        items.loc[items.role.isna() & items.llm_role.notna(), "role_source"] = "llm"
    if "roles" in jobs:
        queue = pd.read_csv(out / "role_review_queue.csv", dtype={"normalized_phrase": str, "example": str})
        llm_unmatched = pd.DataFrame()
        if "llm_actor" in items:
            u = items[items.llm_actor.notna() & items.llm_role.isna()]
            if len(u):
                from .roles import norm_key
                llm_unmatched = (u.assign(normalized_phrase=u.llm_actor.map(norm_key))
                                 .groupby("normalized_phrase").agg(items=("text", "size"), example=("llm_actor", "first")).reset_index())
        phrases = pd.concat([queue[["normalized_phrase", "example", "items"]], llm_unmatched], ignore_index=True)
        phrases = phrases.groupby("normalized_phrase", as_index=False).agg(example=("example", "first"), items=("items", "sum"))
        suggest_roles(phrases.sort_values("items", ascending=False), rolemap.roles, cache, call["roles"], budget, workers) \
            .to_csv(out / "role_suggestions.csv", index=False)

    items.drop(columns=["item_key"]).to_csv(out / "responsibilities.csv", index=False)
    cache.save()
    summary_path = out / "summary.json"
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    llm = dict(model=MODEL, requests=budget.used, requests_skipped_over_budget=budget.skipped, new_cache_entries=len(cache.new))
    if "llm_item_type" in items:
        llm["items_classified"] = int(items.llm_item_type.notna().sum())
        llm["items_by_type"] = {k: int(v) for k, v in items.llm_item_type.value_counts().items()}
    if "llm_actor" in items:
        llm["actors_filled"] = int(items.llm_actor.notna().sum())
        llm["items_with_role_final"] = int(items.role_final.notna().sum())
    usage = {}
    for c in {id(c): c for c in call.values()}.values():
        for k, v in getattr(c, "usage", {}).items():
            usage[k] = usage.get(k, 0) + v
    if usage:
        llm["usage"] = usage
    summary["llm"] = llm
    summary_path.write_text(json.dumps(summary, indent=2) + "\n")
    return llm


def main():
    ap = argparse.ArgumentParser(description="Optional LLM pass over output/ (needs ANTHROPIC_API_KEY).")
    ap.add_argument("--out", default="output")
    ap.add_argument("--cache", default="data/llm_cache.jsonl")
    ap.add_argument("--max-requests", type=int, default=int(os.environ.get("LABELLER_LLM_MAX_REQUESTS", 400)),
                    help="cap on API requests this run; items over the cap wait for the next run")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--jobs", default="classify,actors,roles")
    args = ap.parse_args()
    print(json.dumps(run(args.out, args.cache, max_requests=args.max_requests, workers=args.workers,
                         jobs=tuple(args.jobs.split(","))), indent=2))


if __name__ == "__main__":
    main()
