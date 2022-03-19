#!/bin/bash

echo 'starting homefinder service'

python home_finder.py
cron -f