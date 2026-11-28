"""Stage 1: pick the newest usable capture of each current instrument.

Captures come from one or more data roots shaped like Hawk's `data/` directory:

  <Category>/<anything>_<YYYY-MM-DD>.xml        Hawk's archive. Real XML up to Aug 2025; since then mostly the HTML page
                                                saved under an .xml name, or a firewall "Request Rejected" page.
  <Category>/<id>_<YYYY-MM-DD>/<stamp>.html     Per-change snapshots (Hawk's, or ones fetched locally into data/local).
  <Category>/<id>_<YYYY-MM-DD>/<stamp>.xml      Same, when real XML could be fetched.

Every file is sniffed rather than trusted by its extension. The version date of an HTML capture is TBS's own
"date modified" from the page; for XML it is the date in the file or folder name. The newest version wins; for the
same version, XML is preferred over a snapshot, and a snapshot over an HTML page from the archive.

"Current" means the instrument is listed in Hawk's feed (items.csv), in Hawk's policy hierarchy, or in a
locally scraped listing (listing.csv in any root). Instruments outside all three (rescinded, or old ids) are dropped.
"""
import re
from pathlib import Path

import pandas as pd
from lxml import etree

from . import sources
from .text import fix_text

DATE_IN_NAME = re.compile(r"_(\d{4}-\d{2}-\d{2})\.xml$")
# Folders in Hawk's data/ that hold things other than policy instruments. Any other top-level folder is scanned,
# so locally fetched captures can be filed under e.g. data/local/Uncategorized/.
NOT_INSTRUMENT_FOLDERS = {"PINs", "CabinetDirectives", "Hierarchy", "other", "policy_categories", "policy_currency"}
SNAPSHOT_DIR = re.compile(r"^(\d+)_(\d{4}-\d{2}-\d{2})$")
SOURCE_RANK = {"xml": 2, "snapshot": 1, "html": 0}
DEFAULT_ROOTS = ("data/hawk", "data/local")


def _data_dirs(roots):
    if isinstance(roots, (str, Path)):
        roots = [roots]
    for root in roots:
        root = Path(root)
        if (root / "data").is_dir():
            root = root / "data"
        if root.is_dir():
            yield root


def _read(path, folder, folder_id=None, folder_date="", captured_at=""):
    """One capture as a row, or None if it isn't a usable policy document."""
    kind = sources.sniff(path)
    if kind == "xml":
        try:
            root = etree.parse(str(path)).getroot()
        except etree.XMLSyntaxError:
            return None
        if root.tag != "doc" or not root.get("documentID"):
            return None
        m = DATE_IN_NAME.search(path.name)
        return dict(id=int(root.get("documentID")), title=fix_text(root.get("title")), folder=folder,
                    version=root.get("versionID") or "", version_date=folder_date or (m.group(1) if m else ""),
                    source="xml", captured_at=captured_at, path=str(path))
    if kind == "html":
        doc_id, title, modified = sources.html_meta(path)
        doc_id = folder_id or doc_id
        if not doc_id:
            return None
        m = DATE_IN_NAME.search(path.name)
        return dict(id=int(doc_id), title=title, folder=folder, version="",
                    version_date=modified or folder_date or (m.group(1) if m else ""),
                    source="snapshot" if folder_id else "html", captured_at=captured_at, path=str(path))
    return None  # firewall page, error page


def captures(roots=DEFAULT_ROOTS):
    """Every usable capture in the given roots, one row per file."""
    rows = []
    for data_dir in _data_dirs(roots):
        folders = sorted(p.name for p in data_dir.iterdir() if p.is_dir() and p.name not in NOT_INSTRUMENT_FOLDERS
                         and not p.name.startswith("."))
        for folder in folders:
            base = data_dir / folder
            for path in sorted(base.glob("*.xml")):
                row = _read(path, folder)
                if row:
                    rows.append(row)
            for snap in sorted(p for p in base.iterdir() if p.is_dir() and SNAPSHOT_DIR.match(p.name)):
                folder_id, folder_date = SNAPSHOT_DIR.match(snap.name).groups()
                for path in sorted(list(snap.glob("*.html")) + list(snap.glob("*.xml"))):
                    row = _read(path, folder, int(folder_id), folder_date, path.stem)
                    if row:
                        rows.append(row)
    return pd.DataFrame(rows, columns=["id", "title", "folder", "version", "version_date", "source", "captured_at", "path"])


def listings(roots=DEFAULT_ROOTS):
    """Ids TBS currently lists, with the feed date where there is one.

    Returns (DataFrame[id, listed_title, listed_category, feed_date, listed_in], found_any_listing).
    """
    frames = []
    for data_dir in _data_dirs(roots):
        feed = data_dir / "items.csv"
        if feed.exists():
            f = pd.read_csv(feed, dtype=str)
            f["id"] = pd.to_numeric(f.guid.str.split("_").str[0], errors="coerce")
            f["feed_date"] = f.guid.str.split("_").str[1]
            f = f.dropna(subset=["id"]).sort_values("feed_date").groupby("id").last().reset_index()
            frames.append(pd.DataFrame(dict(id=f.id.astype(int), listed_title=f.title, listed_category=f.category,
                                            feed_date=f.feed_date, listed_in="feed")))
        hierarchy = data_dir / "tbs_policy_hierarchy_full.csv"
        if hierarchy.exists():
            h = pd.read_csv(hierarchy, dtype=str)
            h["id"] = pd.to_numeric(h.ID, errors="coerce")
            h = h.dropna(subset=["id"])
            frames.append(pd.DataFrame(dict(id=h.id.astype(int), listed_title=h.Name, listed_in="hierarchy")))
        listing = data_dir / "listing.csv"
        if listing.exists():
            ls = pd.read_csv(listing, dtype=str)
            ls["id"] = pd.to_numeric(ls.id, errors="coerce")
            ls = ls.dropna(subset=["id"])
            frames.append(pd.DataFrame(dict(id=ls.id.astype(int), listed_title=ls.get("title"),
                                            listed_category=ls.get("category"),
                                            listed_in="listing:" + ls.get("source", pd.Series("", index=ls.index)).fillna(""))))
    if not frames:
        return pd.DataFrame(columns=["id", "listed_title", "listed_category", "feed_date", "listed_in"]), False
    allrows = pd.concat(frames, ignore_index=True)
    out = allrows.groupby("id").agg(
        listed_title=("listed_title", "first"),
        listed_category=("listed_category", lambda s: s.dropna().iloc[0] if s.notna().any() else None),
        feed_date=("feed_date", lambda s: s.dropna().max() if s.notna().any() else None),
        listed_in=("listed_in", lambda s: " ".join(sorted(set(s)))),
    ).reset_index()
    return out, True


def _best(caps):
    caps = caps.assign(_rank=caps.source.map(SOURCE_RANK))
    caps = caps.sort_values(["id", "version_date", "_rank", "captured_at", "version"])
    return caps.groupby("id").tail(1).drop(columns="_rank").reset_index(drop=True)


def build_index(roots=DEFAULT_ROOTS, current_only=True):
    """One row per current instrument: its newest usable capture, plus where TBS lists it."""
    caps = captures(roots)
    best = _best(caps) if len(caps) else caps
    listed, have_listing = listings(roots)
    idx = best.merge(listed, on="id", how="left")
    idx["current"] = idx.listed_in.notna() if have_listing else True
    if current_only:
        idx = idx[idx.current]
    hierarchy = [d / "tbs_policy_hierarchy_full.csv" for d in _data_dirs(roots) if (d / "tbs_policy_hierarchy_full.csv").exists()]
    if hierarchy and len(idx):
        h = pd.read_csv(hierarchy[0], dtype=str).rename(columns={"ID": "id", "Hierarchy Paths": "hierarchy_paths"})
        h["id"] = pd.to_numeric(h["id"], errors="coerce")
        h = h.dropna(subset=["id"]).astype({"id": int}).drop_duplicates("id")[["id", "hierarchy_paths"]]
        idx = idx.merge(h, on="id", how="left")
        idx["in_hierarchy"] = idx["id"].isin(h["id"])
    return idx.sort_values("id").reset_index(drop=True)


def coverage(roots=DEFAULT_ROOTS):
    """One row per listed instrument: the newest capture we have against the date TBS's feed gives.

    is_behind is True when there is no capture at all, or when the feed date is newer than the capture's version
    date. Instruments without a feed date (listed only in the hierarchy or a scraped listing) are behind only if
    there is no capture. This is the work list for fetching what Hawk is missing.
    """
    listed, _ = listings(roots)
    caps = captures(roots)
    best = _best(caps) if len(caps) else caps
    best = best.rename(columns={"version_date": "best_date", "source": "best_source", "path": "best_path"})
    cov = listed.merge(best[["id", "title", "folder", "best_date", "best_source", "best_path"]], on="id", how="left")
    cov["title"] = cov.title.fillna(cov.listed_title)
    cov["category"] = cov.listed_category.fillna(cov.folder)
    no_capture = cov.best_date.isna()
    newer_in_feed = cov.feed_date.notna() & cov.best_date.notna() & (cov.feed_date > cov.best_date.fillna(""))
    cov["is_behind"] = no_capture | newer_in_feed
    cols = ["id", "title", "category", "feed_date", "best_date", "best_source", "best_path", "is_behind", "listed_in"]
    return cov[cols].sort_values(["is_behind", "feed_date"], ascending=[False, False]).reset_index(drop=True)
