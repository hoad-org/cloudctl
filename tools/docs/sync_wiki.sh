#!/bin/bash
set -euo pipefail

WIKI_DIR="wiki_temp_sync"
CURRENT_SHA=$(git rev-parse --short HEAD)

rm -rf "$WIKI_DIR"
mkdir "$WIKI_DIR"
cd "$WIKI_DIR"

git init
git config user.name "github-actions[bot]"
git config user.email "github-actions[bot]@users.noreply.github.com"

# Update provenance deterministically
sed -E "s/^_Last synced from commit:.*/_Last synced from commit: $CURRENT_SHA/" \
  ../docs/wiki/Home.md > Home.md

# Copy wiki content
rsync -av ../docs/wiki/ ./

git add .
git commit -m "docs: sync from $CURRENT_SHA"

git remote add origin "https://x-access-token:${GITHUB_TOKEN}@github.com/${GITHUB_REPOSITORY}.wiki.git"

# Wiki now exists — force-sync to canonical branch
git branch -M master
git push --force origin master

cd ..
rm -rf "$WIKI_DIR"
