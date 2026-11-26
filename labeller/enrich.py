"""Stage 5: cheap, reliable extras pulled from each item's text with rules."""
import re

from .actors import clean_actor

MODALITY = [
    ("must", re.compile(r"\bmust\b|\bshall\b|\b(?:is|are) required\b|\b(?:is|are) to\b", re.I)),
    ("should", re.compile(r"\bshould\b", re.I)),
    ("may", re.compile(r"\bmay\b", re.I)),
]
FREQUENCY = re.compile(
    r"\b(annually|yearly|quarterly|monthly|biennially|every (?:\w+ )?years?|at least (?:once )?(?:a|every|per|each) \w+|"
    r"within \d+ (?:calendar |business |working )?(?:days|months|years)|no later than [^,;.]+)",
    re.I,
)
OTHER_ACTOR = re.compile(
    r"\b(?:in (?:collaboration|consultation|coordination|cooperation|conjunction) with|with the (?:approval|agreement) of|"
    r"approved by|on the recommendation of|reviewed by|reporting to)\s+([^,;:.]+)",
    re.I,
)


def modality(text):
    return next((name for name, pat in MODALITY if pat.search(text)), None)


def frequency(text):
    return "; ".join(dict.fromkeys(m.group(0) for m in FREQUENCY.finditer(text))) or None


def other_actors(text):
    found = [clean_actor(m.group(1)) for m in OTHER_ACTOR.finditer(text)]
    return "; ".join(dict.fromkeys(a for a in found if a)) or None
