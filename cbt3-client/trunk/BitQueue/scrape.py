from sha import sha
#from string import substring
import re
import binascii
import sys,os
import urlparse,urllib

from BitTornado.bencode import *
from BitTornado.zurllib import urlopen as zurlopen
from BitCrawler.aurllib import urlopen as aurlopen

import timeoutsocket
import policy
timeout = policy.get_policy().get(policy.DEFAULT_SOCKET_TIMEOUT)
timeoutsocket.setDefaultSocketTimeout(timeout)
del timeout
del policy

def announce_to_scrape(url):
    items = list(urlparse.urlparse(url))
    path = items[2]
    return urlparse.urljoin(url,
                            os.path.basename(path).replace('announce','scrape'))

def get_scrape_by_announce_url(announce_url,infohash):
    seeder,peerer = '?','?'
    if not announce_url:
        return seeder,peerer
    scrape_url = announce_to_scrape(announce_url)

    len_hash = len(infohash)
    if len_hash == 40:
        infohash = binascii.a2b_hex(infohash)

    scrape_url += '?info_hash=%s' % urllib.quote(infohash)

    try:
        try:
            fd = zurlopen(scrape_url)
        except:
            fd = aurlopen(scrape_url)
        scrape_data = bdecode(fd.read())
        scrape_data = scrape_data['files']
        for i in scrape_data.keys():
            if i == infohash:
                seeder = str(scrape_data[i]['complete'])
                leecher = str(scrape_data[i]['incomplete'])
                break
    except:
        #import traceback
        #traceback.print_exc()
        seeder,leecher = '?','?'

    return seeder,leecher

def get_scrape_by_metadata(metadata):
    if metadata is None:
        return '?','?'

    info = metadata.get('info',None)
    if not info:
        return '?','?'

    infohash = sha(bencode(info)).digest()
    announce_url = metadata.get('announce',None)
    announce_list = metadata.get('announce-list',None)
    if not announce_url and not announce_list:
        return '?','?'

    if not announce_url:
        announce_url = announce_list[0][0]

    return get_scrape_by_announce_url(announce_url,infohash)

def getScrapeData(metadata,parent):
    seeder,leecher = get_scrape_by_metadata(metadata)
    parent.currentseed = seeder
    parent.currentpeer = leecher
