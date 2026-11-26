#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
"$DIR/scripts/start_mysql.sh"
exec /home/cse-sdpl/anaconda3/bin/python3 "$DIR/app.py"
