#!/bin/sh

# Requires environmente variables PGHOST, PGPASSWORD, AND PGDB
# Requires a filesystem mounted at /pgdump

date=`date -Iminutes`
/usr/bin/pg_dump --format=c -h $PGHOST -U postgres --file=/pgdump/tom_${date}.sqlc $PGDB
