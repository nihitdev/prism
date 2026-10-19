#!/usr/bin/env bash
# Local installer and raw.githubusercontent.com bootstrap for Prism.
set -euo pipefail
command -v python3 >/dev/null || { echo 'Prism needs Python 3.11 or newer.' >&2; exit 1; }
python3 -c 'import sys; sys.exit(sys.version_info < (3, 11))' || {
    echo 'Prism needs Python 3.11 or newer.' >&2; exit 1;
}
source_dir=''
if [[ -n ${BASH_SOURCE[0]:-} ]]; then
    source_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
fi
if [[ -n $source_dir && -f $source_dir/scripts/install.py && -d $source_dir/payload ]]; then
    exec python3 "$source_dir/scripts/install.py" "$@"
fi
command -v curl >/dev/null || { echo 'curl is required for remote installation.' >&2; exit 1; }
command -v tar >/dev/null || { echo 'tar is required for remote installation.' >&2; exit 1; }
repository=${PRISM_REPOSITORY:-nihitdev/prism}
[[ $repository =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] || { echo 'Invalid PRISM_REPOSITORY' >&2; exit 2; }
work=$(mktemp -d)
trap 'rm -rf -- "$work"' EXIT
# Resolve main once so all files in this installation come from the same commit.
curl --proto '=https' --tlsv1.2 -fsSL --retry 3 \
    "https://api.github.com/repos/$repository/commits/main" -o "$work/commit.json"
revision=$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["sha"])' "$work/commit.json")
[[ $revision =~ ^[0-9a-f]{40}$ ]] || { echo 'Invalid GitHub commit response' >&2; exit 1; }
curl --proto '=https' --tlsv1.2 -fsSL --retry 3 \
    "https://codeload.github.com/$repository/tar.gz/$revision" -o "$work/prism.tar.gz"
mkdir "$work/source"
tar -xzf "$work/prism.tar.gz" --strip-components=1 -C "$work/source"
python3 "$work/source/scripts/install.py" "$@"
