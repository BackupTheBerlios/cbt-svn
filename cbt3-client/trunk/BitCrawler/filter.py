import re,urllib,urllib2,string,os,sys
import HTMLParser
import traceback

#import interest
#from tag import *
#from misc import *
#from pool import *
import socket

import urlparse
try:
    from cStringIO import StringIO
except ImportError:
    from StringIO import StringIO

from aurllib import urlopen
from BitQueue import timeoutsocket,log
from media import List,GenericMedia,Series,factory
from misc import is_movie,is_torrent
import misc

link_re = re.compile(r'(?P<title>.*[_\-. ]+)(ep|episode)?(?P<episode>\d+)[\[\(_\-. ]+.*', re.IGNORECASE | re.DOTALL)
content_dispo_re = re.compile(r'.*attachment;.*filename="(?P<filename>[^"]+).*')

def get_filter(name):
    if not name:
        name = 'Filter'
    return eval(name)

class BTListHtmlParser(HTMLParser.HTMLParser) :
    def __init__(self, baseurl) :
        HTMLParser.HTMLParser.__init__(self)
        self.link_list = []
        self.href = 0
        self.cur_link = ()
        self.cur_data = ''
        self.baseurl = baseurl

    def handle_starttag(self, tag, attrs) :
        if tag == 'a' :
            for attr in attrs :
                if attr[0] == 'href' :
                    joined = urlparse.urljoin(self.baseurl, attr[1])
                    #print joined
                    if not joined.startswith('http') :
                        break
                    if joined.endswith('.torrent') :
                        # ok, this should be torrent
                        self.href = 1
                        self.cur_link = (joined, None)
                    else :
                        try :
                            link = urlopen(joined,referer=self.baseurl)
                        except Exception:
                            break
                        if is_torrent(link):
                            self.href = 1
                            m = None
                            if link.info().has_key('Content-Disposition') :
                                m = content_dispo_re.search(link.info()['Content-Disposition'])
                            if m :
                                self.cur_link = (joined, m.group('filename'))
                            else :
                                self.cur_link = (joined, None)
                    break

    def handle_data(self, data) :
        if self.href :
            self.cur_data = self.cur_data + data

    def handle_endtag(self, tag) :
        if self.href :
            self.link_list.append( (string.replace(self.cur_data, '\n', ' '), self.cur_link[0], self.cur_link[1]) )
            self.href = 0
            self.cur_link = ()
            self.cur_data = ''

class BaseFilter:
    def __init__(self,interest_list=[],publisher=None,preload=1):
        self.interest_list = interest_list
        self.publisher = publisher
        self.log = log.get_logger()
        self.preload = preload

    def do_interest(self,interest,media):
        if interest.title:
            media.title = interest.title

    def filter(self,media):
        if not media:
            return 0
        for interest in self.interest_list:
            okay = interest.is_interest(media)
            if okay == 1:
                self.do_interest(interest,media)
                return 1
            elif okay == -1:
                return 0
        return 1

    def process(self,tracker):
        self.tracker = tracker
        self.baseurl = tracker.url
        self.content = ''
        try:
            if self.preload:
                webfd = urlopen(self.baseurl)
                self.content = webfd.read()
            media_list = self._process()
        except Exception,why:
            self.log.error('tracker failed: %s\n' % str(why))
            import traceback
            traceback.print_exc()
            media_list = List('MediaList')
        return media_list

    def _process(self):
        return List('MediaList')

class ListFilter(BaseFilter):
    def _process(self):
        parser = BTListHtmlParser(baseurl)
        parser.feed(self.content)
        # mangle the link list
        media_list = List('MediaList')
        # reformat the list
        i = 0
        for link in parser.link_list :
            # normalized the link
            i = i + 1
            if not link[2] :
                parsed_url = os.path.basename(urlparse.urlparse(urllib2.unquote(link[1]))[2])
            else :
                # content-dispo only yield file name
                parsed_url = os.path.basename(link[2])
                
            m = link_re.search(parsed_url)
            if m:
                #print m.groupdict()
                episode = str(int(m.group('episode')))
                attrs = {'title': m.group('title'),
                         'episode': episode,
                         'publisher': self.publisher,
                         'link': link[1]}
                media = Series('Anime',attrs=attrs)
                if self.filter(media):
                    media_list.append(media)
            else :
                self.log.warn('unparseable link = %s\n' % link[1])
        return media_list

class BTAFilter(BaseFilter):

    table_item_reg = r'<tr>\s*<td bgcolor="#[^\"]+"><center><b>(?P<id>\d+)</b></center></td>\s*<td bgcolor="#[^\"]+">(?P<date>[^<]+)</td>'+ \
         r'\s*<td bgcolor="#[^\"]+">(<a href="[^\"]+">)?(<b>)?(?P<title>[^<]+)(</a>)? - (?P<episode>\d+)</td>'+ \
         r'\s*<td bgcolor="#[^\"]+">(?P<publisher>[^<]+)?</td>'+ \
         r'\s*<td bgcolor="#[^\"]+"><a href="(?P<dllink>[^"]+)" target="outhere">Here</a></td><tr>'

    table_item_cre = re.compile(table_item_reg,re.IGNORECASE | re.MULTILINE)

    def _process(self):
        media_list = List('MediaList')
        m = self.table_item_cre.search(self.content)
        while m:
            self.log.debug('%s %s\n' % \
                           (m.group('title'),
                            m.group('publisher')))
            link = urlparse.urljoin(self.baseurl,m.group('dllink'))
            attrs = {'title': urllib.quote(m.group('title')),
                     'episode': m.group('episode'),
                     'link': link}

            if m.group('publisher') :
                attrs['publisher'] = urllib.quote(m.group('publisher'))
            else :
                attrs['publisher'] = urllib.quote('none')

            media = Series('Anime',attrs=attrs)
            if self.filter(media):
                media_list.append(media)
            m = self.table_item_cre.search(self.content,
                                           m.start(0)+len(m.group(0)))
        return media_list


class BNBTFilter(BaseFilter):

    table_item_reg = r'<tr class="[^\"]+"><td><img src="/files/images/bytemonsoon.small/(?P<category>[^\.]+).jpg"></td>'+ \
                     r'<td class="name"><a class="stats" href="(?P<stlink>[^\"]+)">(?P<title>[^\<]+)</a></td>'+ \
                     r'<td class="download"><a class="download" href="(?P<dllink>[^\"]+)">DL</a></td>'+ \
                     r'<td class="[^\"]+"><a href="[^\"]+">[^\"]+</a></td>'+ \
                     r'<td class="date">(?P<date>[^\<]+)</td><td class="bytes">(?P<size>[^\<]+)</td><td class="[^\"]+">(?P<files>[^\<]+)</td>'+ \
                     r'<td class="[^\"]+">(?P<seeders>[^\<]+)</td><td class="[^\"]+">(?P<leechers>[^\<]+)</td><td class="[^\"]+">(?P<completed>[^\<]+)</td>'+ \
                     r'<td class="bytes">(?P<transferred>[^\<]+)</td>'+ \
                     r'<td class="percent">(?P<progress>N/A|'+ \
                     r'[^\<]+<br><img src="/files/images/imagebarfill.jpg" width=\d+ height=\d+><img src="/files/images/imagebartrans.jpg" width=\d+ height=\d+></td>|'+ \
                     r'[^\<]+<br><img src="/files/images/imagebartrans.jpg" width=\d+ height=\d+></td>)'+ \
                     r'<td class="name">(?P<publisher>[^\<]+)</td>'+ \
                     r'<td class="infolink"><a href="(?P<infolink>[^\"]+)">Link</a></td></tr>'

    table_item_cre = re.compile(table_item_reg,re.IGNORECASE | re.MULTILINE)

    def _process(self):
        media_list = List('MediaList')
        m = self.table_item_cre.search(self.content)
        while m:
            self.log.debug('%s %s %s\n' % \
                           (m.group('title'),
                            m.group('publisher'),
                            m.group('category')))
            link = urlparse.urljoin(self.baseurl,m.group('dllink'))
            attrs = {'title': urllib.quote(m.group('title')),
                     'publisher': urllib.quote(m.group('publisher')),
                     'link': link,
                     'type': m.group('category')}
            media = GenericMedia('Media',attrs=attrs)
            if self.filter(media):
                media_list.append(media)
            m = self.table_item_cre.search(self.content,
                                           m.start(0)+len(m.group(0)))
        return media_list


class TorrentBitsFilter(BaseFilter):

    table_item_reg = r'<tr>'+ \
                     r'''\s*<td align="?center"? style='padding: 0px'><a href="browse.php\?cat=\d+"><img border="0" src="/?pic/cat_(?P<category>[^\.]+).gif" alt="[^"]+" /></a></td>'''+ \
                     r'\s*<td align="?left"?><a href="(?P<link>details.php\?id=\d+&amp;hit=1)"><b>(?P<title>[^<]+)</b></a>'+ \
                     r'\s*</td>'+ \
                     r'\s*<td align="?right"?><b><a href="details.php\?id=\d+&amp;hit=1&amp;filelist=1">(?P<files>\d+)</a></b></td>'+ \
                     r'\s*<td align="?right"?>(\d+|<b><a href="details.php\?id=\d+&amp;hit=1&amp;tocomm=1">\d+</a></b>)</td>'+ \
                     r'\s*<td align="?center"?>(---|<img src="/?pic/[\d\.]+.gif" border="0" alt="[^"]+" />)</td>'+ \
                     r'\s*<td align="?center"?><nobr>(?P<date>[^<]+)<br />[^<]+</nobr></td>'+ \
                     r'\s*<td align="?center"?>(?P<size>[^<]+)<br>[^<]+</td>'+ \
                     r'\s*<td align="?center"?>\d+<br>times?</td>'+ \
                     r'\s*<td align="?right"?>((<span class="[^"]+">)?\d+(</span>)?|<b><a href=details.php\?id=\d+&amp;hit=1&amp;toseeders=1><font color=#[^>]+>\d+</font></a></b>)</td>'+ \
                     r'\s*<td align="?right"?>(\d+|<b><a href=details.php\?id=\d+&amp;hit=1&amp;todlers=1>\d+</b>)</td>'+ \
                     r'\s*<td align="?center"?><a href=userdetails.php\?id=\d+><b>(?P<publisher>[^<]+)</b></a></td>'+ \
                     r'\s*</tr>'
    table_item_cre = re.compile(table_item_reg,re.IGNORECASE | re.MULTILINE)

    def _process(self):
        media_list = List('MediaList')
        m = self.table_item_cre.search(self.content)
        while m:
            self.log.debug('%s %s %s\n' % \
                           (m.group('title'),
                            m.group('publisher'),
                            m.group('category')))
            try:
                fd = urlopen(urlparse.urljoin(self.baseurl,m.group('link')))
                detail = fd.read()
            except Exception,why:
                self.log.warn('unexpected error: %s\n' % str(why))
                detail = ''
            d = re.search(r'<a class="index" href="([^"]+)">',detail,re.I)
            if d:
                link = urlparse.urljoin(self.baseurl,d.group(1))
                attrs = {'title': urllib.quote(m.group('title')),
                         'publisher': urllib.quote(m.group('publisher')),
                         'link': link,
                         'type': m.group('category')}
                media = GenericMedia('Media',attrs=attrs)
                if self.filter(media):
                    media_list.append(media)
            m = self.table_item_cre.search(self.content,
                                           m.start(0)+len(m.group(0)))
        return media_list

class InvisionBTFilter(BaseFilter):

    table_item_reg = r'<tr>'+ \
                     r'\s*<td class="[^"]+" align="center"><img src="style_images/[^/]+/cat_(?P<category>[^\.]+).[^<]+" border="0" alt="[^"]+" width="\d+" height="\d+"/></td>'+ \
                     r'\s*<td class="[^"]+" align="left"><a href="(?P<link>[^"]+)">(?P<title>[^<]+)</a></td>'+ \
                     r'\s*<td class="[^"]+" align="right">(?P<files>\d+)</td>'+ \
                     r'\s*<td class="[^"]+" align="center">[^<]+</td>'+ \
                     r'\s*<td class="[^"]+" align="center" nowrap>(?P<date>[^<]+(<br/>| )[^<]*)</td>'+ \
                     r'\s*<td class="[^"]+" align="center">[^<]+</td>'+ \
                     r'\s*<td class="[^"]+" align="center">\d+</td>'+ \
                     r'\s*<td class="[^"]+" align="right">\d+</td>'+ \
                     r'\s*<td class="[^"]+" align="right">\d+</td>'+ \
                     r'\s*<td class="[^"]+" align="center"><a href="[^"]+">(?P<publisher>[^<]+)</a></td>'+ \
                     r'\s*</tr>'
    table_item_cre = re.compile(table_item_reg,re.IGNORECASE | re.MULTILINE)

    def _process(self):
        media_list = List('MediaList')
        m = self.table_item_cre.search(self.content)
        while m:
            self.log.debug('%s %s %s\n' % \
                           (m.group('title'),
                            m.group('publisher'),
                            m.group('category')))
            try:
                fd = urlopen(urlparse.urljoin(self.baseurl,m.group('link')))
                detail = fd.read()
            except Exception,why:
                self.log.warn('unexpected error: %s\n' % str(why))
                detail = ''
            d = re.search(r'<a href="([^\?]+\?act=bt&func=download&id=\d+)">',detail,re.I)
            if d:
                link = urlparse.urljoin(self.baseurl,d.group(1))
                attrs = {'title': urllib.quote(m.group('title')),
                         'publisher': urllib.quote(m.group('publisher')),
                         'link': link,
                         'type': m.group('category')}
                media = GenericMedia('Media',attrs=attrs)
                if self.filter(media):
                    media_list.append(media)
            m = self.table_item_cre.search(self.content,
                                           m.start(0)+len(m.group(0)))
        return media_list

class RSSFilter(BaseFilter):
    def _process(self):
        fd = StringIO(self.content)
        rss = factory.from_file(fd)
        media_list = List('MediaList')
        for channel in rss.channels():
            publisher = channel.title(content=1)
            for item in channel.items():
                enclosure = item.enclosure()
                if enclosure is None:
                    continue
                self.log.debug('%s %s %s\n' % \
                               (item.title(content=1),
                                publisher,
                                enclosure.url))
                attrs = {'title': item.title(content=1),
                         'publisher': publisher,
                         'link': enclosure.url,
                         'type': ''}
                media = GenericMedia('Media',attrs=attrs)
                if self.filter(media):
                    media_list.append(media)

        return media_list

class UserDefinedFilter(BaseFilter):
    def __init__(self,interest_list=[],publisher=None):
        BaseFilter.__init__(self,interest_list,publisher,0)
        self.attributes = {}

    def _search(self,cre):
        m = cre.search(self.content)
        while m:
            for name in m.groups():
                self.attributes[name] = m.group(name)
            m = cre.search(self.content,
                           m.start(0)+len(m.group(0)))

    def _update_attributes(self,g,url):
        for name in g.groupdict().keys():
            value = g.group(name)
            if name == 'link' or name == 'download':
                value = urlparse.urljoin(url,value)
            self.attributes[name] = value

    def _process(self):
        media_list = List('MediaList')
        url_list = self.tracker.find_elements('Url')
        media_name = self.tracker.media or 'GenericMedia'
        media_tag = self.tracker.tag or 'Media'
        for url in url_list:
            content = url.urlopen(referer=self.tracker.url).read()
            filter_list = url.find_elements('Filter')
            if len(filter_list) == 0:
                continue
            self.log.finer(content+'\n')
            self.log.finest(filter_list[0].content+'\n')
            cre = re.compile(filter_list[0].content,re.IGNORECASE|re.MULTILINE)
            m = cre.search(content)
            while m:
                self.attributes = {}
                self._update_attributes(m,url.url)
                referer = url.url
                for filter in filter_list[1:]:
                    fcre = re.compile(filter.content,re.IGNORECASE|re.MULTILINE)
                    link = self.attributes.get('link','')
                    if not link:
                        break
                    temp_content = urlopen(link,referer=url.url).read()
                    self.log.finer(temp_content+'\n')
                    self.log.finest(filter.content+'\n')
                    n = fcre.search(temp_content)
                    if not n:
                        break
                    self._update_attributes(n,link)
                    if 'download' in n.groupdict().keys():
                        referer = link

                keys = self.attributes.keys()
                self.log.fine('filter: %s\n' % str(self.attributes))
                if 'title' in keys and \
                   'download' in keys:
                    self.log.debug('filter: %s %s %s\n' % \
                                   (misc.string(self.attributes.get('title','')),
                                    misc.string(self.attributes.get('publisher','')),
                                    misc.string(self.attributes.get('download',''))))
                    self.attributes['type'] = self.attributes.get('category',
                                                  self.attributes.get('type',''))
                    self.attributes['link'] = self.attributes.get('download','')
                    media = factory.create(media_name,media_tag,attrs=self.attributes)
                    if self.filter(media):
                        media.fetch(referer=referer)
                        media_list.append(media)

                m = cre.search(content,
                               m.start(0)+len(m.group(0)))
        return media_list

if __name__ == '__main__' :
    pass
