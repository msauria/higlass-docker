#!/usr/bin/env python
import os
import sys
from string import Template
import subprocess

viewconf = open('default_viewconf.xml').read()
if "PROXY_URL" in os.environ:
	PROXY_URL = "http://%s" % os.environ['PROXY_URL'].split('http://')[-1]
else:
	PROXY_URL = ""
viewconf = Template(viewconf).safe_substitute({"PROXY_URL": PROXY_URL})
output = open('default-viewconf-fixture.xml', 'w')
output.write(viewconf)
output.close()

output = open('higlass-app/config.js', 'w')
output.write('window.HGAC_HOMEPAGE_DEMOS=false;\n')
output.write('window.HGAC_SERVER="";\n')
viewconf = """{
  "editable": true,
  "zoomFixed": false,
  "trackSourceServers": [
  "$PROXY_URL/api/v1",
  "http://higlass.io/api/v1"
  ],
  "exportViewUrl": "/api/v1/viewconfs/",
  "views": [
    {
      "tracks": {
        "top": [],
        "left": [],
        "center": [],
        "right": [],
        "bottom": []
      },
      "initialXDomain": [ 0, 3200000000 ],
      "initialYDomain": [ 0, 3200000000 ],
      "layout": {
        "w": 12,
        "h": 12,
        "x": 0,
        "y": 0,
        "moved": false,
        "static": false
      }
    }
  ],
  "zoomLocks": {
    "locksByViewUid": {},
    "locksDict": {}
  },
  "locationLocks": {
    "locksByViewUid": {},
    "locksDict": {}
  }}"""
viewconf = viewconf.replace('\n', '').replace(' ','')
viewconf = Template(viewconf).safe_substitute({"PROXY_URL": PROXY_URL})
output.write('window.HGAC_DEFAULT_VIEW_CONFIG={};'.format(viewconf))
output.close()
