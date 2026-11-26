# MySQL 8.4 for Render (private service). Disk is mounted at /var/lib/mysql.
# Data lives in a subdirectory because a fresh ext4 mount contains lost+found,
# which makes MySQL's first-time initialisation fail if used as the datadir.
FROM mysql:8.4
CMD ["mysqld", "--datadir=/var/lib/mysql/data", "--character-set-server=utf8mb4", "--collation-server=utf8mb4_unicode_ci"]
