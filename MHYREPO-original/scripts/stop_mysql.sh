#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
/home/cse-sdpl/anaconda3/bin/mysqladmin --defaults-file="$DIR/mysql.cnf" -u root shutdown
echo "MySQL stopped."
