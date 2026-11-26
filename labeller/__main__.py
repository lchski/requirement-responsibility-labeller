"""python -m labeller [--hawk data/hawk] [--local data/local] [--out output]"""
import argparse
import json

from .pipeline import run


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--hawk", default="data/hawk", help="checkout of TBS Policy Hawk (see scripts/fetch-hawk.sh)")
    ap.add_argument("--local", default="data/local", help="captures fetched locally, in Hawk's layout (skipped if missing)")
    ap.add_argument("--out", default="output", help="directory for the CSV outputs")
    ap.add_argument("--roles", default="data/roles.csv")
    ap.add_argument("--aliases", default="data/role_aliases.csv")
    args = ap.parse_args()
    summary = run([args.hawk, args.local], args.out, args.roles, args.aliases)
    print(json.dumps(summary, indent=2))
    if summary["items"] == 0:
        raise SystemExit("no responsibilities extracted; is the Hawk checkout empty?")


if __name__ == "__main__":
    main()
