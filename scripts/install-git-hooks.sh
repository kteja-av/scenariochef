#!/bin/sh
# Install tracked git hooks into .git/hooks (does not modify git config).
set -e

root="$(cd "$(dirname "$0")/.." && pwd)"
hooks_src="$root/.githooks"
hooks_dst="$root/.git/hooks"

if [ ! -d "$hooks_dst" ]; then
  echo "error: not a git repository (.git/hooks missing)" >&2
  exit 1
fi

for hook in commit-msg; do
  src="$hooks_src/$hook"
  dst="$hooks_dst/$hook"
  if [ ! -f "$src" ]; then
    echo "error: missing hook source $src" >&2
    exit 1
  fi
  cp "$src" "$dst"
  chmod +x "$dst"
  echo "installed $hook"
done

echo "Git hooks installed. Co-authored-by Cursor lines will be stripped on commit."
