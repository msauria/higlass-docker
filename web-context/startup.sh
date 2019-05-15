#!/bin/bash

mkdir -p /data/media
mkdir -p /data/log

# Ensure that until data is digested and config.js is created, server returns 502
mv higlass-app/index.html higlass-app/temp_index.html

# Add function to clear sessionStorage (and the viewConfig) on leaving HiGlass
echo "" >> higlass-app/hglib.min.js
echo "window.onunload = function(){" >> higlass-app/hglib.min.js
echo "  sessionStorage.clear();" >> higlass-app/hglib.min.js
echo "};" >> higlass-app/hglib.min.js

# Digest tracks into database
python ./startup.py 2> /data/log/ie.log &

supervisord -n