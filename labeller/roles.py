"""Stage 4: map the actor phrase as written onto a canonical role.

data/roles.csv        role_id, role, parent_role_id   (the canonical list; ids 1-74 are the 2019 actors)
data/role_aliases.csv alias, role_id                   (ways a role is written)

Matching is by longest alias that is a *prefix* of the phrase, after normalization (case, plurals,
parentheticals, "or their delegates"). Whatever follows the alias is kept as `role_qualifier`, so
"Heads of evaluation designated under subsection 4.3.12 of the policy" becomes role "Departmental heads
of evaluation" with qualifier "designated under subsection 4.3.12 of the policy": a subset of that role.
"""
import re

import pandas as pd

DROP = [
    r"\([^)]*\)",                                                     # (CFO), (s)
    r"\b(?:or|and)\s+(?:their|its|his or her)\s+(?:authorized\s+)?(?:delegates?|designates?|delegate\(s\)|designate\(s\))\b",
    r"\b(?:or|and)\s+(?:their|its)\s+equivalents?\b",
    r"\bor equivalent\b",
]


def _singular(w):
    if re.search(r"[a-z]{2}ies$", w):
        return w[:-3] + "y"
    if re.search(r"(ss|us|is|ics|ws)$", w) or len(w) <= 3:
        return w
    if w.endswith("s"):
        return w[:-1]
    return w


def tokens(phrase):
    """[(original word, normalized word)] for a phrase, with dropped bits removed."""
    s = phrase.replace("’", "'")
    for pat in DROP:
        s = re.sub(pat, " ", s, flags=re.I)
    s = re.sub(r"^\s*(?:(?:the|a|an|all|each|every|any)\s+)+", "", s, flags=re.I)
    s = re.sub(r"\bdepartment's\b", "departmental", s, flags=re.I)
    out = []
    for w in s.split():
        n = re.sub(r"[^a-z0-9]", "", w.lower())
        if n:
            out.append((w.strip(",;:"), _singular(n)))
    return out


def norm_key(phrase):
    return " ".join(n for _, n in tokens(phrase))


class RoleMap:
    def __init__(self, roles_csv, aliases_csv):
        self.roles = pd.read_csv(roles_csv, dtype={"role_id": int, "parent_role_id": "Int64"})
        self.by_id = self.roles.set_index("role_id")
        aliases = pd.read_csv(aliases_csv, dtype={"role_id": int})
        self.aliases = {}
        for a, rid in zip(aliases.alias, aliases.role_id):
            k = tuple(norm_key(a).split())
            if k:
                self.aliases.setdefault(k, rid)
        for rid, role in zip(self.roles.role_id, self.roles.role):  # a role's own name is always an alias
            self.aliases.setdefault(tuple(norm_key(role).split()), rid)
        self.max_len = max(len(k) for k in self.aliases)

    def match(self, phrase):
        """Return (role_id, role, parent_role, qualifier) or Nones."""
        if not isinstance(phrase, str) or not phrase.strip():
            return None, None, None, None
        toks = tokens(phrase)
        norm = tuple(n for _, n in toks)
        for n in range(min(self.max_len, len(norm)), 0, -1):
            rid = self.aliases.get(norm[:n])
            if rid is not None:
                qualifier = " ".join(w for w, _ in toks[n:]).strip(" ,") or None
                row = self.by_id.loc[rid]
                parent = row.parent_role_id
                parent_name = self.by_id.loc[int(parent), "role"] if pd.notna(parent) else None
                return rid, row.role, parent_name, qualifier
        return None, None, None, None
