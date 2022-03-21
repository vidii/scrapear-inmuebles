#!/bin/bash
echo 'starting cron_job'
[ ! -f /app/.env ] || export $(grep -v '^#' /app/.env | xargs)

/usr/local/bin/python /app/home_finder.py