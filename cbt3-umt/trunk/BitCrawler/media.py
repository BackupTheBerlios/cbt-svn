from UserList import UserList
import copy,re
import socket,urllib2
from urllib import urlencode
import os

from BitQueue import timeoutsocket
from BitQueue.log import get_logger
from BitQueue import policy
from element import Element
from misc import asciiquote
from aurllib import urlopen

STRING = 0
INTEGER = 1
LONG = 2
FLOAT = 3
LIST = 4

class Generic:
    BASE_ATTRIBUTES = {}
    ATTRIBUTES = {}
    BASE_COMPARE_ORDER = []
    COMPARE_ORDER = []
    def __init__(self,tag=None,attrs={},content=''):
        if not tag:
            tag = self.__class__.__name__
        self.tag = tag
        self.content = content
        self.log = get_logger()
        self.attributes = copy.copy(self.BASE_ATTRIBUTES)
        self.attributes.update(self.ATTRIBUTES)
        self.compare_order = copy.copy(self.BASE_COMPARE_ORDER)
        self.compare_order.extend(copy.copy(self.COMPARE_ORDER))
        self.set_attributes(attrs)

    def __repr__(self):
        return '<%s %s>' % (self.tag,str(self.get_attributes()))

    def filename(self):
        torrent_path = policy.get_policy().get(policy.TORRENT_PATH)
        media_file = os.path.join(torrent_path,
                                  asciiquote(self.title)+'.torrent')
        return media_file

    def exists(self):
        return os.path.exists(self.filename())

    def set_attributes(self,attrs):
        keys = self.attributes.keys()
        for key in keys:
            if not attrs.has_key(key):
                value = ''
            else:
                value = attrs[key]
            atype = self.attributes[key]
            if atype == STRING:
                pass
            elif atype == INTEGER:
                try:
                    value = int(value)
                except ValueError:
                    value = 0
            elif atype == LONG:
                try:
                    value = long(value)
                except ValueError:
                    value = 0L
            elif atype == FLOAT:
                try:
                    value = float(value)
                except ValueError:
                    value = 0.0
            elif atype == LIST:
                value = value.split(',')
            self.__dict__[key] = value

    def get_attributes(self):
        keys = self.attributes.keys()
        dict = {}
        for key in keys:
            atype = self.attributes[key]
            value = self.__dict__[key]
            if atype == LIST:
                value = ','.join(value)
            else:
                value = str(value)
            dict[key] = value
        return dict

    def __cmp__(self,other):
        for attr in self.compare_order:
            try:
                ret = cmp(getattr(self,attr,''),getattr(other,attr,''))
                if ret != 0:
                    return ret
            except AttributeError:
                pass
        return 0

    def newer(self,other):
        return cmp(self,other) == 0

    def fetch(self):
        if self.exists():
            return

        try:
            web = urlopen(self.link)
            meta = web.read()
        except Exception,why:
            self.log.error('torrent failed: %s\n' % str(why))
            return

        try:
            torrent_file = self.filename()
            fo = open(torrent_file,'wb')
            fo.write(meta)
            fo.close()
        except IOError,why:
            self.log.error('IO failed: %s %s\n' % (self.filename(),str(why)))

    def to_element(self):
        e = Element(self.tag,self.get_attributes(),self.content)
        return e

class GenericMedia(Generic):
    BASE_ATTRIBUTES = {'title': STRING,
                       'link': STRING,
                       'type': STRING,
                       'description': STRING,
                       'publisher': STRING}
    ATTRIBUTES = {}
    BASE_COMPARE_ORDER = ['title','link','type','publisher']
    COMPARE_ORDER = []

class List(Generic,UserList):
    def __init__(self,tag=None,attrs={},content=''):
        Generic.__init__(self,tag,attrs,content)
        UserList.__init__(self) 

    def to_element(self):
        e = Generic.to_element(self)
        for item in self.data:
            e.add(item.to_element())
        return e

    def find_elements(self,tag,instances=0,default=None,content=0):
        if content and default is None:
            instances = 1
            default = ''
        l = []
        for item in self.data:
            if item.tag == tag:
                l.append(item)
        if instances == 1:
            if len(l) == 0:
                l = default
            else:
                l = l[0]
                if content:
                    l = l.content
        elif instances > 1:
            l = l[:instances]
        return l

    def update(self,item):
        try:
            idx = self.index(item)
            self[idx] = item
        except:
            self.append(item)

class MediaFactory:
    def __init__(self,default_media_class,default_list_class):
        self.known_media = {}
        self.default_media_class = default_media_class
        self.default_list_class = default_list_class

    def register(self,media_name,media_class):
        self.known_media[media_name] = media_class

    def unregister(self,media_name):
        if self.known_media.has_key(media_name):
            del self.known_media[media_name]

    def from_file(self,file):
        close_flag = 0
        if type(file) == type(''):
            fd = open(file,'r')
            close_flag = 1
        else:
            fd = file
        e = Element()
        e.load(fd)
        if close_flag:
            fd.close()
        return self.from_element(e)

    def from_element(self,element):
        tag = element.tag
        if self.known_media.has_key(tag):
            media_class = self.known_media[tag]
        else:
            if tag.endswith('List'):
                media_class = self.default_list_class
            else:
                media_class = self.default_media_class
        obj = media_class(tag,attrs=element.attrs,content=element.content)
        if len(element.children) > 0 and hasattr(obj,'append'):
            for e in element.children:
                 obj.append(factory.from_element(e))
        return obj

class Series(GenericMedia):
    ATTRIBUTES = {'episode': STRING}

    def filename(self):
        torrent_path = policy.get_policy().get(policy.TORRENT_PATH)
        name = asciiquote('%s-%s' % (self.title,self.episode))
        media_file = os.path.join(torrent_path,name+'.torrent')
        return media_file

    def newer(self,other):
        return cmp(self.episode,other.episode)
        # first, check for the form of episode
        eplist = [-1, -1]
        idx = 0
        for ep in [self.episode, other.episode] :
            ep = ep or '0'
            tmp1 = ep.split('-')
            tmp2 = ep.split('v')
            if len(tmp1) > len(tmp2):
                tmp = tmp1
            else:
                tmp = tmp2
            eplist[idx] = -1
            if len(tmp) > 1 :
                for subep in tmp :
                    if int(subep) > self_max :
                        eplist[idx] = int(subep)
            else :
                eplist[idx] = int(ep)
            idx = idx + 1
        return eplist[0] > eplist[1]

class Tracker(List):
    BASE_ATTRIBUTES = {'url': STRING,
                       'loader': STRING,
                       'filter': STRING,
                       'publisher': STRING,
                       'user': STRING,
                       'password': STRING}

class Url(List):
    BASE_ATTRIBUTES = {'name': STRING,
                       'url': STRING,
                       'user': STRING,
                       'password': STRING,
                       'method': STRING}

    def urlopen(self,url=None):
        url = url or self.url
        method = self.method or 'get'
        data = {}
        params = self.find_elements('Param')
        for param in params:
            data[param.name] = param.value
        return urlopen(self.url,
                       data=urlencode(data),
                       user=self.user,
                       passwd=self.password,
                       method=method)

class Param(List):
    BASE_ATTRIBUTES = {'name': STRING,
                       'value': STRING}

class Filter(Generic):
    BASE_ATTRIBUTES = {'name': STRING}

class Interest(Generic):
    BASE_ATTRIBUTES = {'attribute': STRING,
                       'mode': STRING,
                       'title': STRING}

    def __init__(self,tag=None,attrs={},content=''):
        Generic.__init__(self,tag,attrs,content)
        self.cre = re.compile(self.content,re.I|re.S|re.M)

    def is_interest(self,media):
        if not hasattr(media,self.attribute):
            return 0
        value = str(getattr(media,self.attribute))
        found = self.cre.search(value)
        if self.mode == 'include' and found:
            return 1
        elif self.mode == 'exclude' and found:
            return -1
        return 0

class InterestSet(List):
    BASE_ATTRIBUTES = {'mode': STRING,
                       'title': STRING}

    def is_interest(self,media):
        if not self.mode in ['and','or']:
            self.mode = 'and'
        result = [0,0,0]
        for inte in self.data:
            ret = inte.is_interest(media)
            result[ret+1] += 1
        if self.mode == 'and':
            return result[2] == len(self.data)
        elif self.mode == 'or':
            return result[2] > 0

class rssRSS(List):
    BASE_ATTRIBUTES = {'version': STRING}
    def channels(self):
        return self.find_elements('channel')

class rssChannel(List):
    def title(self,content=0):
        return self.find_elements('title',1,content=content)

    def link(self,content=0):
        return self.find_elements('link',1,content=content)

    def description(self,content=0):
        return self.find_elements('description',1,content=content)

    def language(self,content=0):
        return self.find_elements('language',1,content=content)

    def items(self,content=0):
        return self.find_elements('item',content=content)

class rssItem(List):
    def title(self,content=0):
        return self.find_elements('title',1,content=content)

    def description(self,content=0):
        return self.find_elements('description',1,content=content)

    def pubDate(self,content=0):
        return self.find_elements('pubDate',1,content=content)

    def guid(self,content=0):
        return self.find_elements('guid',1,content=content)

    def enclosure(self,content=0):
        return self.find_elements('enclosure',1,content=content)

class rssEnclosure(List):
    BASE_ATTRIBUTES = {'url': STRING,
                       'length': LONG,
                       'type': STRING}

factory = MediaFactory(GenericMedia,List)
factory.register('Series',Series)
factory.register('Anime',Series)
factory.register('Tracker',Tracker)
factory.register('Url',Url)
factory.register('Param',Param)
factory.register('Filter',Filter)
factory.register('Interest',Interest)
factory.register('InterestSet',InterestSet)
factory.register('rss',rssRSS)
factory.register('channel',rssChannel)
factory.register('item',rssItem)
factory.register('enclosure',rssEnclosure)

if __name__ == '__main__':
    import sys
    from cStringIO import StringIO
    mlist = List('MediaList')
    mlist.append(Generic('Media',{'title': 'test'}))
    mlist.append(Series('Anime',{'title': 'Gundam Seed','episode': 1}))
    fd = StringIO()
    mlist.to_element().save(fd)
    fd.seek(0,0)
    result = fd.read()
    print result
    fd.seek(0,0)
    element = Element()
    element.load(fd)
    mlist = factory.from_element(element)
    fd.close()
    mlist.to_element().save(sys.stdout)

    fd = StringIO('''<TrackerList>
    <Tracker publisher="th-torrent">
        <Url name="login" url="http://th-torrent.mine.nu/" method="post">
            <Param name="user" value="sugree"/>
            <Param name="password" value="xxxx"/>
        </Url>
        <Url name="catalog" url="http://th-torrent.mine.nu/">
            <Filter name="main"><![CDATA[<tr>\s*<td class="[^"]+" align="center"><img src="style_images/[^/]+/cat_(?P<category>[^\.]+).[^<]+" border="0" alt="[^"]+" width="\d+" height="\d+"/></td>\s*<td class="[^"]+" align="left"><a href="(?P<link>[^"]+)">(?P<title>[^<]+)</a></td>\s*<td class="[^"]+" align="right">(?P<files>\d+)</td>\s*<td class="[^"]+" align="center">[^<]+</td>\s*<td class="[^"]+" align="center" nowrap>(?P<date>[^<]+(<br/>| )[^<]*)</td>\s*<td class="[^"]+" align="center">[^<]+</td>\s*<td class="[^"]+" align="center">\d+</td>\s*<td class="[^"]+" align="right">\d+</td>\s*<td class="[^"]+" align="right">\d+</td>\s*<td class="[^"]+" align="center"><a href="[^"]+">(?P<publisher>[^<]+)</a></td>\s*</tr>]]></Filter>
            <Filter name="detail"><![CDATA[<a href="(?P<download>[^\?]+\?act=bt&func=download&id=\d+)">]]></Filter>
        </Url>
        <Url name="logout" url="http://th-torrent.mine.nu/"/>
    </Tracker>
</TrackerList>''')
    element.load(fd)
    tlist = factory.from_element(element)
    fd.close()
    tlist.to_element().save(sys.stdout)
    sys.exit()

    mlist = List('InterestList')
    mlist.append(Interest(attrs={'attribute': 'publisher',
                                 'mode': 'include'},content='loading'))
    mlist.append(Interest(attrs={'attribute': 'title',
                                 'mode': 'exclude'},content='trial'))
    fd = StringIO()
    mlist.to_element().save(fd)
    fd.seek(0,0)
    result = fd.read()
    print result

    m1 = GenericMedia('Media',attrs={'title': 'test1'})
    m2 = GenericMedia('Media',attrs={'title': 'test1'})
    m3 = GenericMedia('Media',attrs={'title': 'test 1'})
    m4 = Series('Media',attrs={'title': 'test 1','episode': '1'})
    m5 = Series('Media',attrs={'title': 'test 1','episode': '2'})
    m6 = Series('Media',attrs={'title': 'test 1','episode': '2v2'})
    print cmp(m1,m2)
    print cmp(m1,m3)
    print cmp(m3,m4),m3.newer(m4)
    print cmp(m4,m5),m4.newer(m5)
    print cmp(m5,m4),m5.newer(m4)
    print cmp(m5,m6),m6.newer(m6)

    mlist = List('MediaList')
    mlist.append(m1)
    mlist.append(m2)
    mlist.append(m3)
    print mlist[2]
    mlist.update(m4)
    print mlist[2]
