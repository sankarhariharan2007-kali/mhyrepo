#!/usr/bin/env bash
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PID_FILE="$DIR/mysql_data/mysql.pid"

if [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null; then
    echo "MySQL is already running (PID $(cat "$PID_FILE"))."
    exit 0
fi

nohup /home/cse-sdpl/anaconda3/bin/mysqld --defaults-file="$DIR/mysql.cnf" >/dev/null 2>&1 &
for i in {1..30}; do
    if /home/cse-sdpl/anaconda3/bin/mysqladmin --defaults-file="$DIR/mysql.cnf" -u root ping >/dev/null 2>&1; then
        echo "MySQL started on 127.0.0.1:3306 (PID $(cat "$PID_FILE"))."
        exit 0
    fi
    sleep 0.5
done
echo "Failed to start MySQL. Check $DIR/mysql_data/mysql_error.log"
exit 1
