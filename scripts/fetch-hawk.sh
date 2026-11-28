#!/usr/bin/env bash
# Download (or refresh) the policy XML archive from TBS Policy Hawk into data/hawk.
# Only the XML files are checked out, to keep the copy small.
set -euo pipefail

dest="${1:-data/hawk}"
repo="https://github.com/PatLittle/TBS-Policy-Hawk.git"

if [ -d "$dest/.git" ]; then
  git -C "$dest" fetch --depth 1 origin main
  git -C "$dest" reset --hard FETCH_HEAD
else
  git clone --depth 1 --filter=blob:none --sparse "$repo" "$dest"
fi

git -C "$dest" sparse-checkout set --no-cone '/data/*/*.xml'
echo "Hawk XML files: $(find "$dest/data" -name '*.xml' | wc -l)"
