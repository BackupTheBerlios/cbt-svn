import base64
from urllib import addinfourl
import urllib2
from cgi import parse_qs
from httpsession import HTTPSession

urlopener = None

def urldecode(data):
    dict = parse_qs(data)
    ret = {}
    for key in dict.keys():
        ret[key] = dict[key][0]
    return ret

class AURLOpener:
    def __init__(self,user=None,passwd=None):
        self.user = user
        self.passwd = passwd

    def set_default(self):
        global urlopener
        urlopener = self

    def urlopen(self,url,data=None):
        if self.user and self.passwd:
            req = urllib2.Request(url)
            raw = '%s:%s' % (self.user,self.passwd)
            auth = 'Basic %s' % base64.encodestring(raw).strip()
            req.add_header('Authorization',auth)
            opener = urllib2.build_opener()
            web = opener.open(req,data)
        else:
            web = urllib2.urlopen(url,data)
        return web

class CookieAURLOpener(AURLOpener):
    def __init__(self,user=None,passwd=None):
        AURLOpener.__init__(self,user,passwd)
        self.session = HTTPSession(debug_level=0)
        if self.user and self.passwd:
            self.session.set_basic_auth(self.user,self.passwd)

    def urlopen(self,url,data=None,method='get'):
        if method == 'post':
            req = self.session.post(url)
        else:
        req = self.session.get(url)
        if data:
            params = urldecode(data)
            req.add_params(params)
        rc,msg,hdr = req.getreply()
        fd = req.getfile()
        return addinfourl(fd,hdr,req.url)

def urlopen(uri,data=None,user=None,passwd=None,method='get'):
    global urlopener
    if not urlopener:
        urlopener = CookieAURLOpener(user,passwd)
    return urlopener.urlopen(uri,data,method=method)
