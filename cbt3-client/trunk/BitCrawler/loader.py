import socket,urllib2
from urlparse import urljoin,urlsplit,urlunsplit
from urllib import urlencode

from BitQueue import timeoutsocket
from aurllib import urlopen,CookieAURLOpener
from media import List
from misc import is_movie,is_torrent
from BitQueue.log import get_logger
from BitQueue import policy

def get_loader(name):
    if not name:
        name = 'TrackerLoader'
    return eval(name)

class TrackerLoader:
    def __init__(self,tracker,filter):
        self.tracker = tracker
        self.url = tracker.url
        self.user = tracker.user
        self.passwd = tracker.password
        self.filter = filter
        self.log = get_logger()

    def prefetch(self):
        urlopener = CookieAURLOpener(self.user,self.passwd)
        urlopener.set_default()

    def fetch(self):
        self.prefetch()

        media_list = self.filter.process(self.tracker)
        for media in media_list:
            if not (is_movie(media.link) or is_torrent(media.link)) :
                self.log.warn('link failed: link is not movie or torrent: %s\n' % str(media.link))
        return media_list

class TorrentBitsLoader(TrackerLoader):
    def __init__(self,tracker,filter):
        TrackerLoader.__init__(self,tracker,filter)
        self.login_url = urljoin(self.url,'takelogin.php')

    def prefetch(self):
        TrackerLoader.prefetch(self)
        try:
            fd = urlopen(self.login_url,urlencode({'username': self.user,
                                              'password': self.passwd}))
        except Exception,why:
            self.log.error('prefetch failed: %s' % str(why))

class InvisionBTLoader(TrackerLoader):
    def __init__(self,tracker,filter):
        TrackerLoader.__init__(self,tracker,filter)
        self.login_url = urlunsplit(urlsplit(self.url)[:3]+('',''))

    def prefetch(self):
        TrackerLoader.prefetch(self)
        try:
            fd = urlopen(self.login_url,urlencode({'act': 'Login',
                                              'CODE': '01',
                                              'CookieDate': '1',
                                              'UserName': self.user,
                                              'PassWord': self.passwd}),
                         method='post')
        except Exception,why:
            self.log.error('prefetch failed: %s' % str(why))

class MetaLoader:
    def __init__(self,tracker,media):
        self.user = tracker.user
        self.passwd = tracker.password
        self.url = media.link
        self.title = media.title
        pol = policy.get_policy()
        torrent_path = pol(policy.TORRENT_PATH)

    def fetch(self):
        try:
            urlopener = AURLOpener(self.user,self.passwd)
            urlopener.set_default()
            web = urlopen(self.url)
            meta = web.read()
        except Exception,why:
            self.log.error('torrent failed: %s\n' % str(why))
            return

        try:
            publisher = self.publisher or 'unknown'
            try:
                episode = self.episode or 'xx'
            except AttributeError:
                episode = 'xx'
            filename = '%s-%s-%s.torrent' % (publisher,self.title,episode)
            torrent_file = os.path.join(torrent_path,asciiquote(filename))
            if os.path.exists(torrent_file):
                return
            fo = open(torrent_file,'w')
            fo.write(meta)
            fo.close()
        except IOError:
            pass

if __name__ == '__main__' :
    import sys
    from media import Tracker,Interest
    from filter import BNBTFilter,TorrentBitsFilter,InvisionBTFilter,RSSFilter,UserDefinedFilter
    logger = get_logger()

    ilist = List('InterestList')
    ilist.append(Interest(attrs={'attribute': 'publisher',
                                 'mode': 'include'},content='Admin'))
    ilist.append(Interest(attrs={'attribute': 'publisher',
                                 'mode': 'exclude'},content='gummy'))

    from getpass import getpass
    user = raw_input('user: ')
    passwd = getpass('password: ')

    def test_bnbt(ilist):
    filter = BNBTFilter(ilist)
    loader = TrackerLoader(Tracker('Media',
                           attrs={'url': 'http://th-torrent.mine.nu:6969/',
                                  'user': 'xxx',
                                  'password': 'yyy'}),
                           filter)
    #loader.fetch().to_element().save(sys.stdout)

    def test_tb(ilist):
    filter = TorrentBitsFilter(ilist)
    loader = TorrentBitsLoader(Tracker('Media',
                           attrs={'url': 'http://th-torrent.homeip.net:6969/browse.php',
                                  'user': user,
                                  'password': passwd}),
                           filter)
    #loader.fetch().to_element().save(sys.stdout)

    def test_rss(ilist):
    filter = RSSFilter(ilist)
    loader = TrackerLoader(Tracker('Media',
                           attrs={'url': 'http://www.legaltorrents.com/rss.xml'}),
                           filter)
        #loader.fetch().to_element().save(sys.stdout)

    def test_ibbt(ilist):
        filter = InvisionBTFilter(ilist)
        loader = InvisionBTLoader(Tracker('Media',
                               attrs={'url': 'http://forums.btthai.com/?act=bt&func=browse',
                                      'user': user,
                                      'password': passwd}),
                               filter)
    loader.fetch().to_element().save(sys.stdout)

    def test_ud(ilist):
        filter = UserDefinedFilter(ilist)

        from cStringIO import StringIO
        from element import Element
        from media import MediaFactory,GenericMedia,List
        fd = StringIO('''<TrackerList>
    <Tracker publisher="th-torrent">
        <Url name="login" url="http://forums.btthai.com/" method="post">
            <Param name="UserName" value="%(user)s"/>
            <Param name="PassWord" value="%(password)s"/>
            <Param name="act" value="Login"/>
            <Param name="CODE" value="01"/>
            <Param name="CookieDate" value="1"/>
        </Url>
        <Url name="catalog" url="http://forums.btthai.com/" method="get">
            <Param name="act" value="bt"/>
            <Param name="func" value="browse"/>
            <Filter name="main"><![CDATA[<tr>\s*<td class="[^"]+" align="center"><img src="style_images/[^/]+/cat_(?P<category>[^\.]+).[^<]+" border="0" alt="[^"]+" width="\d+" height="\d+"/></td>\s*<td class="[^"]+" align="left"><a href="(?P<link>[^"]+)">(?P<title>[^<]+)</a></td>\s*<td class="[^"]+" align="right">(?P<files>\d+)</td>\s*<td class="[^"]+" align="center">[^<]+</td>\s*<td class="[^"]+" align="center" nowrap>(?P<date>[^<]+(<br/>| )[^<]*)</td>\s*<td class="[^"]+" align="center">[^<]+</td>\s*<td class="[^"]+" align="center">\d+</td>\s*<td class="[^"]+" align="right">\d+</td>\s*<td class="[^"]+" align="right">\d+</td>\s*<td class="[^"]+" align="center"><a href="[^"]+">(?P<publisher>[^<]+)</a></td>\s*</tr>]]></Filter>
            <Filter name="detail"><![CDATA[<tr><td align="left" class='pformleft'>Name</td><td class='pformright'><a href="index.php\?showtopic=\d+">(?P<description>[^<]+)</a></td></tr>\s*<tr><td align="left" class='pformleft'>Info Hash</td><td class='pformright'>[^<]+</td></tr>\s*<tr><td align="left" class='pformleft'>Download</td><td class='pformright'><a href="(?P<download>[^\?]+\?act=bt&func=download&id=\d+)">[^<]+</a></td></tr>]]></Filter>
        </Url>
        <Url name="logout" url="http://th-torrent.mine.nu/"/>
    </Tracker>
</TrackerList>''' % {'user': user,
                     'password': passwd})
        element = Element()
        element.load(fd)
        factory = MediaFactory(GenericMedia,List)
        tlist = factory.from_element(element)
        fd.close()

        loader = TrackerLoader(tlist[0],filter)
        loader.fetch().to_element().save(sys.stdout)

    test_ud(ilist)
