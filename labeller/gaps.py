"""Find instruments that Hawk is missing or behind on, and fetch them from TBS into data/local/.

TBS's firewall rejects requests from GitHub runners and cloud machines, so Hawk misses some captures.
Run this on your own computer, where TBS's site loads normally:

    uv run python -m labeller.gaps --list-only     # just print the gap list
    uv run python -m labeller.gaps                 # print it, then download each gap into data/local/
    uv run python -m labeller.gaps --check-all     # also ask TBS for every instrument's current date
    uv run python -m labeller.gaps --import ~/Downloads/*.html   # file pages you saved from a browser

Captures go in Hawk's snapshot layout, so the pipeline reads them alongside Hawk:
    data/local/<Category>/<id>_<date modified>/<UTC stamp>.html   (and .xml, when TBS still serves real XML)
"""
import argparse
import csv
import re
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from html import unescape
from pathlib import Path

from lxml import etree

BASE = "https://www.tbs-sct.canada.ca/pol/"
LISTINGS = {"hierarchy": BASE + "hierarch-eng.aspx", "az": BASE + "a-z-eng.aspx"}
USER_AGENT = "Mozilla/5.0 (compatible; requirement-responsibility-labeller; manual run)"
LISTING_COLUMNS = ["id", "title", "category", "url", "source"]

# Folder names the index reads. Order matters: "Guideline" is checked before "Guide".
CATEGORIES = [
    ("Policy framework", r"\bpolicy framework\b"),
    ("Framework", r"\bframework\b"),
    ("Standard", r"\bstandards?\b"),
    ("Directive", r"\bdirectives?\b"),
    ("Guidelines", r"\bguidelines\b"),
    ("Guideline", r"\bguideline\b"),
    ("Guide", r"\bguide\b"),
    ("Policy", r"\bpolicy\b"),
]

LINK = re.compile(r'<a[^>]*href="[^"]*doc-eng\.aspx\?id=(\d+)[^"]*"[^>]*>(.*?)</a>', re.S | re.I)
DATE_MODIFIED = re.compile(r'dateModified:\s*"(\d{4}-\d{2}-\d{2})"')
FRENCH_LINK = re.compile(r"doc-fra\.aspx\?id=(\d+)")
H1 = re.compile(r"<h1[^>]*>(.*?)</h1>", re.S | re.I)


class Blocked(Exception):
    """TBS answered with its firewall page (or an error) instead of the page we asked for."""


class NotAnInstrument(Exception):
    """TBS answered, but not with an instrument page (e.g. an id that redirects elsewhere)."""


def doc_url(doc_id, section="html"):
    return f"{BASE}doc-eng.aspx?id={doc_id}&section={section}"


def get(url, timeout=30):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT, "Accept-Language": "en-CA,en;q=0.8"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            text = resp.read().decode("utf-8-sig", errors="replace")
    except (urllib.error.URLError, TimeoutError) as e:
        raise Blocked(f"{url}: {e}") from e
    if "Request Rejected" in text[:500]:
        raise Blocked(f"{url}: TBS firewall rejected the request")
    return text


def strip_tags(s):
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", " ", s))).strip()


def category_for(title):
    t = (title or "").lower()
    for name, pattern in CATEGORIES:
        if re.search(pattern, t):
            return name
    return ""


# --- Listings: the union of TBS's hierarchical and A-Z lists ---

def parse_listing(html):
    """{id: title} for every instrument link on a TBS listing page."""
    found = {}
    for doc_id, label in LINK.findall(html):
        title = strip_tags(label)
        if title and doc_id not in found:
            found[doc_id] = title
    return found


def read_listing(path):
    if not Path(path).exists():
        return []
    with open(path, newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def refresh_listing(local_dir, fetch=None):
    """Fetch both listings and write data/local/listing.csv. Keeps the previous file if either fetch fails."""
    fetch = fetch or get
    path = Path(local_dir) / "listing.csv"
    seen = {}
    for source, url in LISTINGS.items():
        try:
            found = parse_listing(fetch(url))
        except Blocked as e:
            print(f"! Could not read the {source} listing ({e}); keeping the previous listing.csv", file=sys.stderr)
            return read_listing(path)
        for doc_id, title in found.items():
            row = seen.setdefault(doc_id, dict(id=doc_id, title=title, category=category_for(title),
                                               url=f"{BASE}doc-eng.aspx?id={doc_id}", source=source))
            if row["source"] != source:
                row["source"] = "both"
    rows = sorted(seen.values(), key=lambda r: int(r["id"]))
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LISTING_COLUMNS)
        w.writeheader()
        w.writerows(rows)
    counts = {s: sum(r["source"] == s for r in rows) for s in ("both", "hierarchy", "az")}
    print(f"Listings: {len(rows)} instruments ({counts['both']} in both, {counts['hierarchy']} hierarchy only, "
          f"{counts['az']} A-Z only)")
    return rows


# --- Pages ---

def inspect_page(html):
    """id, title, category and date modified of a TBS instrument page, or None if it isn't one."""
    if "Request Rejected" in html[:500]:
        return None
    date, doc_id, h1 = DATE_MODIFIED.search(html), FRENCH_LINK.search(html), H1.search(html)
    if not (date and doc_id and h1):
        return None
    title = strip_tags(h1.group(1))
    return dict(id=doc_id.group(1), title=title, category=category_for(title), date=date.group(1))


def is_policy_xml(text, doc_id):
    try:
        root = etree.fromstring(text.encode("utf-8"))
    except etree.XMLSyntaxError:
        return False
    return root.tag == "doc" and root.get("documentID") == str(doc_id)


def save(local_dir, info, ext, text, stamp=None):
    stamp = stamp or datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    folder = Path(local_dir) / (info["category"] or "Uncategorized") / f"{info['id']}_{info['date']}"
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{stamp}.{ext}"
    path.write_text(text, encoding="utf-8")
    return path


def fetch_instrument(doc_id, local_dir, category="", fetch=None, delay=3.0, newer_than=""):
    """Download the HTML page (and real XML, if served). Returns (info, saved paths); saves nothing if TBS's
    page isn't newer than `newer_than`."""
    fetch = fetch or get
    html = fetch(doc_url(doc_id, "html"))
    if "Request Rejected" in html[:500]:
        raise Blocked(f"id {doc_id}: TBS firewall rejected the request")
    info = inspect_page(html)
    if info is None or info["id"] != str(doc_id):
        raise NotAnInstrument(f"id {doc_id}: TBS's page isn't a policy instrument page; skipped")
    info["category"] = category or info["category"]  # Hawk's feed knows types that titles don't show
    if newer_than and info["date"] <= newer_than:
        return info, []
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    paths = [save(local_dir, info, "html", html, stamp)]
    time.sleep(delay)
    try:
        xml = fetch(doc_url(doc_id, "xml"))
        if is_policy_xml(xml, doc_id):
            paths.append(save(local_dir, info, "xml", xml, stamp))
    except Blocked:
        pass  # the HTML is enough
    return info, paths


def import_files(paths, local_dir, categories=None):
    """File pages saved from a browser ("Save Page As", HTML only) into data/local/.
    `categories` maps id -> folder name, for instruments whose title doesn't say their type."""
    categories = categories or {}
    saved = []
    for p in paths:
        text = Path(p).read_text(encoding="utf-8-sig", errors="replace")
        info = inspect_page(text)
        if info is None:
            print(f"! {p}: not a TBS instrument page (or a firewall page); skipped", file=sys.stderr)
            continue
        info["category"] = categories.get(info["id"]) or info["category"]
        if not info["category"]:
            print(f"! {p}: couldn't tell the instrument type from '{info['title']}'; filed under Uncategorized",
                  file=sys.stderr)
        out = save(local_dir, info, "html", text)
        print(f"  {info['id']} {info['title']} ({info['date']}) -> {out}")
        saved.append(out)
    return saved


# --- Gap list ---

def find_gaps(roots, check_all=False):
    from .index import coverage  # from the HTML reader: one row per current instrument

    cov = coverage(roots)
    if check_all:
        return cov
    return cov[cov["is_behind"]]


def describe(row):
    if not row.get("best_date"):
        return "missing"
    if row.get("feed_date") and row["best_date"] < row["feed_date"]:
        return f"behind: have {row['best_date']}, feed says {row['feed_date']}"
    return f"have {row['best_date']}"


def print_gaps(rows):
    if not rows:
        print("No gaps: every listed instrument has a capture at least as new as Hawk's feed.")
        return
    print(f"{len(rows)} instrument(s) to fetch:")
    for r in rows:
        print(f"  {r['id']:>6}  {(r.get('category') or '?'):<16} {str(r.get('title') or '')[:60]:<60}  {describe(r)}")


def print_browser_fallback(rows, local_dir):
    print("\nTBS refused the script. Fetch the rest in your browser instead:")
    print("  1. Open each link below.")
    print("  2. Save the page (File > Save Page As..., format 'Webpage, HTML Only') into one folder, e.g. ~/Downloads/tbs.")
    print(f"  3. Run: uv run python -m labeller.gaps --import ~/Downloads/tbs/*.html --local {local_dir}")
    for r in rows:
        print(f"     {doc_url(r['id'])}")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--hawk", default="data/hawk", help="checkout of TBS Policy Hawk (see scripts/fetch-hawk.sh)")
    ap.add_argument("--local", default="data/local", help="where downloaded captures go")
    ap.add_argument("--list-only", action="store_true", help="print the gap list without downloading")
    ap.add_argument("--check-all", action="store_true",
                    help="ask TBS for every instrument's date, to catch revisions Hawk's feed hasn't seen (slow)")
    ap.add_argument("--no-listing", action="store_true", help="don't refresh the hierarchy and A-Z listings")
    ap.add_argument("--delay", type=float, default=3.0, help="seconds between requests to TBS")
    ap.add_argument("--import", dest="imports", nargs="+", metavar="FILE", help="file pages saved from a browser")
    args = ap.parse_args(argv)

    hawk = Path(args.hawk)
    roots = [hawk, Path(args.local)]
    if args.imports:
        cov = find_gaps(roots, check_all=True)
        cats = {str(i): c for i, c in zip(cov["id"], cov["category"].fillna("")) if c}
        saved = import_files(args.imports, args.local, cats)
        print(f"Imported {len(saved)} of {len(args.imports)} file(s).")
        return

    if not args.no_listing:
        refresh_listing(args.local)
    cov = find_gaps(roots, check_all=args.check_all)
    rows = cov.fillna("").astype(str).to_dict("records")
    rows = [dict(r, title=strip_tags(r.get("title", "")), category=r.get("category") or category_for(r.get("title")),
                 best_date=r.get("best_date", ""), feed_date=r.get("feed_date", "")) for r in rows]
    if args.check_all:
        print(f"Checking all {len(rows)} instruments against TBS ({args.delay:.0f}s apart).")
    else:
        print_gaps(rows)
    if args.list_only or not rows:
        return

    fetched = 0
    for i, r in enumerate(rows):
        try:
            info, paths = fetch_instrument(r["id"], args.local, category=r.get("category", ""), delay=args.delay,
                                           newer_than=r["best_date"] if args.check_all else "")
        except NotAnInstrument as e:
            print(f"! {e}", file=sys.stderr)
            continue
        except Blocked as e:
            print(f"! {e}", file=sys.stderr)
            print_browser_fallback(rows[i:], args.local)
            break
        if paths:
            fetched += 1
            print(f"  saved {r['id']} {info['title']} ({info['date']}): {', '.join(p.name for p in paths)}")
            if not args.check_all and r["feed_date"] and info["date"] < r["feed_date"]:
                print(f"    note: TBS's page says {info['date']}, older than the feed's {r['feed_date']}")
        time.sleep(args.delay)
    print(f"\nDownloaded {fetched} instrument(s) into {args.local}/.")
    if fetched:
        print("Next: uv run python -m labeller, then commit data/local/ so the scheduled run picks them up.")


if __name__ == "__main__":
    main()
