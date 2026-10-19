#!/usr/bin/env bash
set -euo pipefail
repo=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
export PYTHONPATH="$repo${PYTHONPATH:+:$PYTHONPATH}"
exec python3 -m cms_od.launch "$@"
