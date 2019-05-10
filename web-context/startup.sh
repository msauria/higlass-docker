#!/bin/bash

mkdir -p /data/media
mkdir -p /data/log

python ./setup_viewconf.py 2> /data/log/ie.log
cp ./default-viewconf-fixture.xml higlass-server/default-viewconf-fixture.xml

python ./startup.py 2>> /data/log/ie.log &

supervisord -n