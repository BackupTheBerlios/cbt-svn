from sha import sha
#from string import substring
import re
import binascii
import sys

try:
    from BitTornado.bencode import *
    from BitTornado.zurllib import urlopen
except ImportError:
    from BitTorrent.bencode import *
    from BitTorrent.zurllib import urlopen

import timeoutsocket
import policy
timeout = policy.get_policy().get(policy.DEFAULT_SOCKET_TIMEOUT)
timeoutsocket.setDefaultSocketTimeout(timeout)
del timeout
del policy

def getScrapeData(metainfo, parent):
    announce = None
    
    # connect scrape at tracker and get data
    # save at self.currentpeer, self.currentseed
    # if error put '?'
    if metainfo is None:
        parent.currentseed = "?"
        parent.currentpeer = "?"
    else:
        info = metainfo['info']
        info_hash = sha(bencode(info))
        if metainfo.has_key('announce'):
            announce = metainfo['announce']
        else:
            announce = None
        if metainfo.has_key('announce-list'):
            announce_list = metainfo['announce-list']
        else:
            announce_list = None
        if announce is None and announce_list is not None :
            announce = annouce_list[0][0]
                        
        if announce is not None:
	    #sys.stderr.write('Announce URL: ' + announce + '\n');
            p = re.compile( '(.*/)[^/]+')
            surl = p.sub (r'\1', announce)
	    #sys.stderr.write('sURL1: ' + surl + '\n')
	    #Fix this to comply with scrape standards.
	    ix = announce.rindex('/')
	    #tmp = 'ix: '.join(ix)
	    #sys.stderr.write('ix: ' + str(ix) + '\n')
	    if (ix + 9) > len(announce):
	      ix2 = len(announce)
	    else:
	      ix2 = ix + 9
            #sys.stderr.write('ix: ' + announce[(ix + 1):(ix2)] + '\n')
	    if announce[(ix + 1):(ix2)].endswith("announce", 0):
	    #  sys.stderr.write('!!!VALID SRAPE URL!!!' + '\n')
	    #  sys.stderr.write('sURLTrue: ' + surl + 'scrape' + announce[(ix2):] + '\n');
	      surl = surl + 'scrape' + announce[(ix2):] + '?info_hash='
	    #end new Scrape URL Code
            #surl = surl + "scrape.php?info_hash="
	    #sys.stderr.write('sURL2: ' + surl + '\n')
            info_hash_hex = info_hash.hexdigest()
            hashlen = len(info_hash_hex)
            for i in range(0, hashlen):
                if (i % 2 == 0):
                    surl = surl + "%"
                surl = surl + info_hash_hex[i]
            # connect scrape URL
	    #sys.stderr.write('sURLlast: ' + surl + '\n')
            try :
                h = urlopen(surl)
                scrapedata = h.read()
                h.close()
                scrapedata = bdecode(scrapedata)
                scrapedata = scrapedata['files']
                for i in scrapedata.keys():
                    if binascii.b2a_hex(i) == info_hash_hex:
                        parent.currentpeer = str(scrapedata[i]['incomplete'])
                        parent.currentseed = str(scrapedata[i]['complete'])
                        break
            except:
                parent.currentpeer = "?"
                parent.currentseed = "?"
        else:
            parent.currentpeer = "?"
            parent.currentseed = "?"
    
