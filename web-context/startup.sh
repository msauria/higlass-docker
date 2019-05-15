#!/bin/bash

mkdir -p /data/media
mkdir -p /data/log

# Create customized config file with correct trackServer in viewconfig
python ./setup_viewconf.py 2> /data/log/ie.log
cp ./default-viewconf-fixture.xml higlass-server/default-viewconf-fixture.xml

# Add function to clear sessionStorage (and the viewConfig) on leaving HiGlass
echo "" >> higlass-app/hglib.min.js
echo "window.onunload = function(){" >> higlass-app/hglib.min.js
echo "  sessionStorage.clear();" >> higlass-app/hglib.min.js
echo "};" >> higlass-app/hglib.min.js

# Digest tracks into database
python ./startup.py 2>> /data/log/ie.log &

supervisord -n