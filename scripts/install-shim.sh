#!/usr/bin/env bash
# One-shot installer that puts `design-intel` on your PATH.
#
# After running this, you can type `design-intel` from anywhere without
# the `.venv/bin/` prefix. Safe to re-run (idempotent — replaces any
# existing symlink).
#
# Usage:
#   ./scripts/install-shim.sh
#   ./scripts/install-shim.sh --prefix ~/.local/bin   # alternative location

set -euo pipefail

# Defaults
PREFIX="/usr/local/bin"
SHIM_NAME="design-intel"

# Parse args
while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix)
      PREFIX="$2"
      shift 2
      ;;
    --name)
      SHIM_NAME="$2"
      shift 2
      ;;
    -h|--help)
      echo "Usage: $0 [--prefix /path/to/bin] [--name design-intel]"
      echo ""
      echo "  --prefix  Where to install the symlink (default: /usr/local/bin)"
      echo "  --name    Name of the command (default: design-intel)"
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 1
      ;;
  esac
done

# Resolve the project root (the directory containing this script's parent)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
VENV_BINARY="$PROJECT_ROOT/.venv/bin/design-intel"

# Sanity check: venv binary must exist
if [ ! -x "$VENV_BINARY" ]; then
  echo "Error: can't find $VENV_BINARY" >&2
  echo "" >&2
  echo "Did you install the project into a venv? Try:" >&2
  echo "  cd $PROJECT_ROOT" >&2
  echo "  python3 -m venv .venv" >&2
  echo "  .venv/bin/pip install -e ." >&2
  exit 1
fi

# Sanity check: target directory exists
if [ ! -d "$PREFIX" ]; then
  echo "Error: $PREFIX doesn't exist" >&2
  echo "Pass --prefix with a directory that does (e.g. ~/.local/bin)" >&2
  exit 1
fi

TARGET="$PREFIX/$SHIM_NAME"

# Warn if the target exists and isn't a symlink we put there
if [ -e "$TARGET" ] && [ ! -L "$TARGET" ]; then
  echo "Error: $TARGET already exists and isn't a symlink." >&2
  echo "Move it out of the way first, or pick a different --prefix." >&2
  exit 1
fi

# Install (replace any existing symlink — idempotent)
if [ -L "$TARGET" ]; then
  rm "$TARGET"
fi

# Check if we need sudo for this prefix
if [ -w "$PREFIX" ]; then
  ln -s "$VENV_BINARY" "$TARGET"
else
  echo "Requesting sudo to write to $PREFIX ..."
  sudo ln -s "$VENV_BINARY" "$TARGET"
fi

echo ""
echo "Installed: $TARGET -> $VENV_BINARY"
echo ""
echo "Try it:"
echo "  $SHIM_NAME"
echo ""
echo "If '$SHIM_NAME' isn't found, $PREFIX is probably not on your PATH."
echo "Add this to your ~/.zshrc or ~/.bashrc:"
echo "  export PATH=\"$PREFIX:\$PATH\""
