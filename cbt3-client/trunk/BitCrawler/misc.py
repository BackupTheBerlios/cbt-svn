import string, urllib, types, socket, re, base64, os
import urllib2,socket
from urllib2 import URLError

from BitQueue import timeoutsocket
from aurllib import urlopen
from BitQueue import policy as qpolicy

policy = qpolicy.get_policy()

bt_mimetype = 'x-bittorrent'
content_dipo = re.compile('.*attachment;.*"filename=(?P<filename>.*)".*')

import sys
reserved_chars = [os.sep,'_']
if sys.platform != 'win32':
    reserved_chars.append(':')

def string(s):
    if type(s) == type(''):
        s = s.decode('iso-8859-1')
    return s

def asciiquote(s):
    s = urllib.unquote(s)
    n_s = ''
    for c in s:
        if ord(c) < 32 or ord(c) > 127 or c in reserved_chars:
            n_s += '+%02X' % ord(c)
        else:
            n_s += c
    return n_s.replace(' ','_')

def download_response(uri,title):
#    adress, loc, path, param, query, frag = urlparse(uri)
    torrent_path = policy(qpolicy.TORRENT_PATH)
    torrent_file = os.path.join(torrent_path,asciiquote(title)+'.torrent')
    if os.path.exists(torrent_file) :
        return
    try:
        fo = open(torrent_file,'w')
        web = urlopen(uri,user,passwd)
        fo.write(web.read())
        fo.close()
    except Exception:
        pass

def is_movie(url) :
    try :
        if type(url) in types.StringTypes:
            doc = urlopen(url)
        else :
            doc = url
        return doc.geturl().endswith('.avi') or doc.geturl().endswith('.ogm')
    except Exception:
        return 0

def is_torrent(url) :
    try :
        if type(url) in types.StringTypes:
            doc = urlopen(url)
        else :
            doc = url
        # basic check
        doc_type = doc.info().getsubtype()
        if (doc_type.lower() == bt_mimetype.lower()) :
            return 1
        elif doc.geturl().endswith('.torrent') :
            return 1
        else :
            return 0
    except Exception:
        return 0

def to_dict(attrs) :
    import copy

    ret = {}
    for key in attrs.keys() :
        ret[key] = attrs[key]
    return ret
