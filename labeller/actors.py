"""Stage 3: find the responsible actor for each clause.

An actor statement is recognized by sentence shape, not by a list of names:
    "<subject> is/are responsible|accountable|required ...", "<subject> is/are to ...",
    "<subject> must|shall|will ...", "<subject> ensure(s) that ..."
and the subject only counts if it contains a general role noun (head, officer, manager, secretariat...).
A clause without its own actor statement inherits one from its nearest ancestor.
"""
import re

VERB = (
    r"(?:is|are)\s+(?:also\s+|solely\s+|jointly\s+)?(?:responsible|accountable|required)\b"
    r"|(?:is|are)\s+to\b"
    r"|(?:must|shall|will)\b(?!\s+be\b)"
    r"|ensures?\s+that\b"
    r"|(?:can|may)\s+(?:initiate|undertake|approve|designate)\b"
)
ACTOR_STATEMENT = re.compile(rf"^(?P<actor>[A-Z(][^:;]{{1,250}}?)\s*,?\s+(?:{VERB})", re.S)

LEAD_IN = re.compile(
    r"^(?:in addition|in relation to|with respect to|with regard to|during|under|as part of|in support of|while|"
    r"further to|once|when|where|if|for|in order to|prior to|after|before|following|subject to|taking into)\b",
    re.I,
)

# General vocabulary of role nouns. Deliberately not tied to any one policy.
ROLE_NOUN = re.compile(
    r"\b(heads?|deputy|deputies|ministers?|secretary|president|board|committees?|secretariat|authorit(?:y|ies)|"
    r"administrators?|practitioners?|specialists?|owners?|sponsors?|departments?|institutions?|executives?|"
    r"officers?|officials?|managers?|employees?|supervisors?|persons?|individuals?|units?|organizations?|"
    r"agenc(?:y|ies)|centres?|offices?|branch|council|champions?|auditors?|comptroller|receiver|"
    r"cios?|cfos?|csos?|tbs|ocio|ochro|ssc|psc|statistics canada|canada school|people|delegates?|designates?|"
    r"leads?|chairs?|chairpersons?|coordinators?|staff|members?|personnel|participants?|providers?|"
    r"custodians?|cardholders?|advisors?|planners?|travell?ers?|recipients?|canada|secretaries|ombud\w*|commissioners?|clerk|registrar|general|experts?|equivalents?)\b",
    re.I,
)
LEADING_NUMBER = re.compile(r"^\(?\d+(?:\.\d+)*\)?\s*")
NOT_A_SUBJECT = {"in", "at", "to", "upon", "as", "prior", "whether", "that", "this", "these", "it", "there", "if", "when",
                 "where", "for", "by", "with", "on", "under", "after", "before", "once", "must", "should", "may", "be",
                 "inform", "collaborate", "annual", "objective", "role", "request", "application", "other"}


def clean_actor(phrase):
    """Trim an actor phrase to the role it names; None if it doesn't look like a role."""
    a = re.sub(r"\s+", " ", phrase).strip(" ,")
    if LEAD_IN.match(a) and "," in a:  # "Once a strike is called, departments ..." -> "departments"
        a = a.rsplit(",", 1)[1].strip()
    a = LEADING_NUMBER.sub("", a)
    a = re.sub(r"^(the|a|an)\s+", "", a, flags=re.I)
    a = re.split(
        r",\s*(?:in collaboration|in consultation|in cooperation|which|who|including|designated|for each|while|within|as)\b|,\s*$",
        a,
    )[0]
    a = re.split(r"\s+(?:in collaboration|in consultation|in cooperation|in coordination) with\b|\s+who\b|\s+that\b|\s+which\b"
                 r"|\s+(?:is|are|has|have|was|were)\s", a)[0]
    a = a.strip(" ,")
    if not a or len(a.split()) > 30:
        return None
    first = a.split()[0].lower()
    if first in NOT_A_SUBJECT:
        return None  # "Providing written approval ...", "In some cases ...": a task or a lead-in, not an actor
    # The head of the noun phrase (before "of", "for", "in" ...) must end in a role noun:
    # "Departmental managers responsible for ..." passes, "Treasury Board approval" does not.
    head = re.split(r"\s+(?:of|for|in|with|responsible|who|on|under|at|to|from|within|involved|that)\b", a, maxsplit=1)[0]
    # In a list ("Managers, functional specialists, and equivalents") any member may carry the role noun.
    for part in re.split(r",|\band\b|\bor\b", head):
        words = part.split()
        if words and ROLE_NOUN.fullmatch(re.sub(r"[^A-Za-z]", "", words[-1])):
            return a
    return None


def actor_in(text, is_heading=False):
    """The actor a clause names itself, if any."""
    t = LEADING_NUMBER.sub("", text)
    m = ACTOR_STATEMENT.match(t)
    if not m and ":" in t[:80]:  # "Standards are as follows: Cardholders are responsible for ..."
        m = ACTOR_STATEMENT.match(t.split(":", 1)[1].strip())
    if m:
        return clean_actor(m.group("actor"))
    if is_heading:  # a heading that is just a role, e.g. "6.1 Approval authorities are responsible for:" or "Deputy heads"
        h = t.strip(" :")
        if len(h.split()) <= 8 and ROLE_NOUN.search(h) and re.search(r"(s|ies)$", h, re.I) and not re.match(r"(monitoring|reporting|roles)\b", h, re.I):
            return h
    return None


def assign(nodes):
    """Add actor_raw, actor_clause and actor_how to each node of one container.

    actor_how is one of: self, ancestor, fill-down (legacy layouts, actor carried from an earlier sibling), or None.
    """
    for n in nodes:
        n["actor_here"] = actor_in(n["text"], n["kind"] == "heading")
    by_idx = {n["idx"]: n for n in nodes}
    last = None
    for n in nodes:
        chain, p = [n], by_idx.get(n["parent"])
        while p is not None:
            chain.append(p)
            p = by_idx.get(p["parent"])
        src = next((x for x in chain if x["actor_here"]), None)
        how = None if src is None else ("self" if src is n else "ancestor")
        if src is None and last is not None and last["depth"] <= n["depth"]:
            src, how = last, "fill-down"
        if n["actor_here"]:
            last = n
        n["actor_raw"] = src["actor_here"] if src else None
        n["actor_clause"] = src["key"] if src else None
        n["actor_how"] = how
        n["stem"] = " ".join(x["text"] for x in reversed(chain[1:]) if not x["actor_here"] and x["kind"] != "heading")


def appendix_label(title):
    m = re.match(r"\s*Appendix\s+([A-Z]{1,2}|[IVX]+|\d+)\b", title or "")
    return m.group(1) if m else None


def borrow_for_appendices(rows):
    """Imperative appendices ("Do not reactivate ...") name no actor. Use the actor of the requirements clause
    that cites the appendix, when exactly one actor cites it."""
    by_doc = {}
    for r in rows:
        if r["container"] == "chapter" and r["actor_raw"]:
            by_doc.setdefault(r["id"], []).append(r)
    cache = {}
    for r in rows:
        if r["container"] != "appendix" or r["actor_raw"]:
            continue
        label = appendix_label(r["container_title"])
        if not label:
            continue
        key = (r["id"], label)
        if key not in cache:
            pat = re.compile(rf"\bAppendix\s+{re.escape(label)}\b")
            hits = [c for c in by_doc.get(r["id"], []) if pat.search(c["text"])]
            actors = {c["actor_raw"] for c in hits}
            cache[key] = (hits[0]["actor_raw"], hits[0]["anchor"]) if len(actors) == 1 else None
        if cache[key]:
            r["actor_raw"], r["actor_clause"] = cache[key]
            r["actor_how"] = "appendix-reference"
