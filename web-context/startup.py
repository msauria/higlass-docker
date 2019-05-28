#!/usr/bin/env python
import os
import shutil
from string import Template
import subprocess
import logging
import time
import copy

#import galaxy_ie_helpers
from bioblend.galaxy import objects
from bioblend.galaxy import GalaxyInstance
from bioblend.galaxy.histories import HistoryClient
from bioblend.galaxy.datasets import DatasetClient

DEBUG = os.environ.get('DEBUG', "False").lower() == 'true'
if DEBUG:
    logging.basicConfig(level=logging.DEBUG)
logging.getLogger("bioblend").setLevel(logging.CRITICAL)
log = logging.getLogger()

def _get_ip():
    """Get IP address for the docker host
    """
    cmd_netstat = ['netstat', '-nr']
    p1 = subprocess.Popen(cmd_netstat, stdout=subprocess.PIPE)
    cmd_grep = ['grep', '^0\.0\.0\.0']
    p2 = subprocess.Popen(cmd_grep, stdin=p1.stdout, stdout=subprocess.PIPE)
    cmd_awk = ['awk', '{ print $2 }']
    p3 = subprocess.Popen(cmd_awk, stdin=p2.stdout, stdout=subprocess.PIPE)
    galaxy_ip = p3.stdout.read().strip().decode('utf-8')
    log.debug('Host IP determined to be %s', galaxy_ip)
    return galaxy_ip


def _test_url(url, key, history_id, obj=True):
    """Test the functionality of a given galaxy URL, to ensure we can connect
    on that address."""
    log.debug("TestURL url=%s obj=%s", url, obj)
    try:
        if obj:
            gi = objects.GalaxyInstance(url, key)
            gi.histories.get(history_id)
        else:
            gi = GalaxyInstance(url=url, key=key)
            gi.histories.get_histories(history_id)
        log.debug("TestURL url=%s state=success", url)
        return gi
    except Exception:
        log.debug("TestURL url=%s state=failure", url)
        return None


def get_galaxy_connection(history_id=None, obj=True):
    """
        Given access to the configuration dict that galaxy passed us, we try and connect to galaxy's API.
        First we try connecting to galaxy directly, using an IP address given
        us by docker (since the galaxy host is the default gateway for docker).
        Using additional information collected by galaxy like the port it is
        running on and the application path, we build a galaxy URL and test our
        connection by attempting to get a history listing. This is done to
        avoid any nasty network configuration that a SysAdmin has placed
        between galaxy and us inside docker, like disabling API queries.
        If that fails, we failover to using the URL the user is accessing
        through. This will succeed where the previous connection fails under
        the conditions of REMOTE_USER and galaxy running under uWSGI.
    """
    history_id = history_id or os.environ['HISTORY_ID']
    key = os.environ['API_KEY']

    ### Customised/Raw galaxy_url ###
    galaxy_ip = _get_ip()
    # Substitute $DOCKER_HOST with real IP
    url = Template(os.environ['GALAXY_URL']).safe_substitute({'DOCKER_HOST': galaxy_ip})
    #url = url.replace('localhost', 'docker.for.mac.localhost')
    gi = _test_url(url, key, history_id, obj=obj)
    if gi is not None:
        return gi

    ### Failover, fully auto-detected URL ###
    # Remove trailing slashes
    app_path = os.environ['GALAXY_URL'].rstrip('/')
    # Remove protocol+host:port if included
    app_path = ''.join(app_path.split('/')[3:])

    if 'GALAXY_WEB_PORT' not in os.environ:
        # We've failed to detect a port in the config we were given by
        # galaxy, so we won't be able to construct a valid URL
        raise Exception("No port")
    else:
        # We should be able to find a port to connect to galaxy on via this
        # conf var: galaxy_paster_port
        galaxy_port = os.environ['GALAXY_WEB_PORT']

    built_galaxy_url = 'http://%s:%s/%s' % (galaxy_ip, galaxy_port, app_path.strip())
    url = built_galaxy_url.rstrip('/')

    gi = _test_url(url, key, history_id, obj=obj)
    if gi is not None:
        return gi

    ### Fail ###
    msg = "Could not connect to a galaxy instance. Please contact your SysAdmin for help with this error"
    raise Exception(msg)

def load_data():
    #hid = os.environ.get('DATASET_HID', None)
    history_id = os.environ['HISTORY_ID']

    #if hid not in ('None', None):
    #    galaxy_ie_helpers.get(int(hid))
    #    shutil.copy('/import/%s' % hid, '/import/ipython_galaxy_notebook.ipynb')

    datasets = []
    genomes = []
    additional_ids = os.environ.get("ADDITIONAL_IDS", "")
    if additional_ids:
        gi = get_galaxy_connection(history_id=history_id, obj=False)
        hc = HistoryClient(gi)
        history = hc.show_history(history_id, contents=True)
        additional_ids = additional_ids.split(",")
        for hda in history:
            if hda["id"] in additional_ids:
                metadata = gi.datasets.show_dataset(hda['id'])
                fname0 = "/import/[%i] %s.%s" % (metadata['hid'], metadata['name'], metadata['extension'])
                name = "%i_%s" % (metadata['hid'], metadata['name'].replace(' ', '_').replace('.', '_').replace('/', '_'))
                fname1 = "/data/media/%s" % (name)
                #galaxy_ie_helpers.get(int(hda["hid"]))
                try:
                    if hda["extension"] == "mcool":
                        filetype = 'cooler'
                        datatype = 'matrix'
                        tracktype = 'heatmap'
                    elif hda["extension"] == "bigwig":
                        filetype = 'bigwig'
                        datatype = 'vector'
                        tracktype = 'horizontal-bar'
                    elif hda['extension'] == "beddb.sqlite":
                        filetype = 'beddb'
                        datatype = 'bedlike'
                        tracktype = 'bedlike'
                    else:
                        log.debug("Invalid datatype. Skipping %s" % fname0.split('/')[-1])
                        continue
                    subprocess.Popen(['ln', '-s', fname0, fname1])
                    datasets.append({
                        'name': metadata['name'],
                        'uid': name,
                        'fname': fname1,
                        'filetype': filetype,
                        'datatype': datatype,
                        'tracktype': tracktype,
                        'genome': metadata["genome_build"],
                        })
                    if filetype == "bigwig":
                        genomes.append(metadata['genome_build'])
                except:
                    log.debug("Failed to link %s" % fname0)
    genomes = set(genomes)
    fetch_genomes(genomes)
    for dset in datasets:
        try:
            if dset["filetype"] == "bigwig":
                genome = dset['genome']
                if os.path.exists("/data/media/%s.chrom.sizes" % genome):
                    subprocess.Popen(["python", "/home/higlass/projects/higlass-server/manage.py",
                                      "ingest_tileset", "--filename", "/data/media/%s.chrom.sizes" % genome,
                                      "--filetype", "chromsizes-tsv", "--datatype", "chromsizes",
                                      "--coordSystem", genome])
                else:
                    log.debug("Missing chromosome sizes for %s" % dset['fname'])
                    continue
            subprocess.Popen(["python", "/home/higlass/projects/higlass-server/manage.py", "ingest_tileset",
                              "--filetype", dset['filetype'], "--datatype", dset['datatype'],
                              "--uid", dset['uid'], "--filename", dset['fname'], "--no-upload",
                              "--coordSystem", dset['genome']])
            log.debug("Loading %s" % dset['fname'])
        except:
            log.debug("Failed to load %s" % dset['fname'])
    return datasets

def fetch_genomes(genomes):
    for genome in genomes:
        try:
            subprocess.Popen([
                "wget", "http://hgdownload.soe.ucsc.edu/goldenPath/%s/bigZips/%s.chrom.sizes" % (genome, genome),
                "-O", "/data/media/%s.chrom.sizes" % genome]).wait()
        except:
            log.debug("Failed to retrieve chromosome sizes for %s" % genome)

def create_default_viewconf(datasets):
    if "PROXY_URL" in os.environ:
        PROXY_URL = "http://%s" % os.environ['PROXY_URL'].split('http://')[-1]
    else:
        PROXY_URL = ""
    viewconf = {"editable": True,
            "zoomFixed": False,
            "trackSourceServers": [
                "%s/api/v1" % PROXY_URL,
                "http://higlass.io/api/v1"
                ],
            "exportViewUrl": "/api/v1/viewconfs/",
            "views": [{
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
                    "moved": False,
                    "static": False
                    }
                }],
            "zoomLocks": {
                "locksByViewUid": {},
                "locksDict": {}
                },
            "locationLocks": {
                "locksByViewUid": {},
                "locksDict": {}
                }
            }
    track = {
        'uid': '',
        'type': '',
        'position': '',
        'contents': []
        }
    tile = {
        'name': "",
        'server': "%s/api/v1" % PROXY_URL,
        'tilesetUid': "",
        'type': "",
        'maxZoom': None,
        'width': 100,
        'height': 100,
        'transforms': [],
        'position': ''
        }
    for dset in datasets:
        if dset['datatype'] == 'matrix':
            if len(viewconf['views'][0]['tracks']['center']) == 0:
                ctrack = copy.deepcopy(track)
                ctrack['uid'] = 'center'
                ctrack['type'] = 'combined'
                ctrack['position'] = 'center'
                viewconf['views'][0]['tracks']['center'].append(ctrack)
            ctile = copy.deepcopy(tile)
            ctile['name'] = dset['name']
            ctile['tilesetUid'] = dset['uid']
            ctile['type'] = dset['tracktype']
            ctile['position'] = 'center'
            viewconf['views'][0]['tracks']['center'][0]['contents'].append(ctile)
        elif dset['datatype'] == 'vector':
            ctile = copy.deepcopy(tile)
            ctile['name'] = dset['name']
            ctile['tilesetUid'] = dset['uid']
            ctile['type'] = dset['tracktype'].replace('horizontal', 'vertical')
            ctile['position'] = 'left'
            viewconf['views'][0]['tracks']['left'].append(ctile)
            ctile = copy.deepcopy(tile)
            ctile['name'] = dset['name']
            ctile['tilesetUid'] = dset['uid']
            ctile['type'] = dset['tracktype']
            ctile['position'] = 'top'
            viewconf['views'][0]['tracks']['top'].append(ctile)
        elif dset['datatype'] == 'bedlike':
            ctile = copy.deepcopy(tile)
            ctile['name'] = dset['name']
            ctile['tilesetUid'] = dset['uid']
            ctile['type'] = "vertical-%s" % dset['tracktype']
            ctile['position'] = 'left'
            viewconf['views'][0]['tracks']['left'].append(ctile)
            ctile = copy.deepcopy(tile)
            ctile['name'] = dset['name']
            ctile['tilesetUid'] = dset['uid']
            ctile['type'] = dset['tracktype']
            ctile['position'] = 'top'
            viewconf['views'][0]['tracks']['top'].append(ctile)

    viewconf = str(viewconf).replace('False', 'false').replace('True', 'true').replace('None', 'null')
    viewconf = Template(viewconf).safe_substitute({"PROXY_URL": PROXY_URL})
    output = open('default-viewconf-fixture.xml', 'w')
    output.write(viewconf)
    output.close()

    output = open('higlass-app/config.js', 'w')
    output.write('window.HGAC_HOMEPAGE_DEMOS=false;\n')
    output.write('window.HGAC_SERVER="";\n')
    output.write('window.HGAC_DEFAULT_VIEW_CONFIG=%s;' % viewconf)
    output.close()


if __name__ == "__main__":
    # Wait until the database has been created before adding datasets
    wait = 0
    while wait < 10 and not os.path.exists('/data/db.sqlite3'):
        time.sleep(1)
    if os.path.exists('/data/db.sqlite3'):
        log.debug("Database exists")
    else:
        log.debug("Database does not exist")

    datasets = load_data()
    create_default_viewconf(datasets)

    # Update nginx configuration and restart
    subprocess.Popen(["mv", "/etc/nginx/sites-enabled/hgserver_nginx_final.conf",
                      "/etc/nginx/sites-enabled/hgserver_nginx.conf"]).wait()

    # Make sure page doesn't cache and make index.html available again
    index = open('higlass-app/temp_index.html').read()
    nocache = "<meta http-equiv='cache-control' content='no-cache'>" +\
              "<meta http-equiv='expires' content='0'>" +\
              "<meta http-equiv='pragma' content='no-cache'>"
    index.replace('<head>', "<head>%s" % nocache)
    output = open("higlass-app/index.html", 'w')
    output.write(index)
    output.close()

    # Reload nginx with new config
    subprocess.Popen(["service", "nginx", "reload"])
