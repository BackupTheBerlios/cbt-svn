'''
Media database
'''
from xml.sax import parse, saxutils
from xml.sax.handler import ContentHandler
from xml.sax.saxlib import LexicalHandler
import string
import urllib
import misc

class Element:
    "Class represent each element"
    def __init__(self, tag=None, attrs={}, content='') :
        if not tag:
            tag = self.__class__.__name__
        self.tag = tag
        self.attrs = {}
        for key in attrs.keys():
            self.attrs[key] = misc.string(attrs[key])
        self.parent = None
        self.children = []
        self.content = content

    def __repr__(self) :
        return str(self.attrs)

    def __getitem__(self, index) :
        if self.attrs.has_key(index):
            return self.attrs[index]
        return None

    def __delitem__(self, index) :
        del self.attrs[index]

    def set_content(self,content):
        self.content = misc.string(content)

    def add(self,child):
        self.children.append(child)
        child.parent = self

    def save(self, file=None, handler=None, prefix='') :
        if not handler:
            if type(file) is type('') :
                out = open(file, 'w')
            else :
                out = file
            handler = saxutils.LexicalXMLGenerator(out)
            handler.startDocument()

        handler.ignorableWhitespace(prefix)
        handler.startElement(self.tag, self.attrs)
        if self.content.find('<') >= 0 or self.content.find('>') >= 0:
            handler.startCDATA()
        handler.characters(self.content)
        if self.content.find('<') >= 0 or self.content.find('>') >= 0:
            handler.endCDATA()
        if self.children:
            handler.ignorableWhitespace('\n')
            for node in self.children :
                node.save(handler=handler,prefix=prefix+'  ')
            handler.ignorableWhitespace(prefix)
        handler.endElement(self.tag)
        handler.ignorableWhitespace('\n')

        if type(file) is type('') :
            out.close()

    def load(self, file) :
        if type(file) is type('') :
            out = open(file, 'r')
        else :
            out = file
        self.children = []
        hd = ElementContentHandler()
        try :
            self.reader = parse(out, hd)
            self.tag = hd.root.tag
            self.attrs = hd.root.attrs
            self.content = hd.root.content
            self.children = hd.root.children
        except IOError :
            pass

class ElementContentHandler(ContentHandler,LexicalHandler) :
    def __init__(self) :
        self.root = None
        self.current = None
        self.data = ''
        self.in_cdata = 0
        self.stack = []

        self.push = self.stack.append
        self.pop = self.stack.pop

    def add(self,obj):
        if len(self.stack) > 0 and self.stack[-1]:
            self.stack[-1].add(obj)

    def startCDATA(self):
        self.in_cdata = 1
        self.data = ''

    def endCDATA(self):
        self.in_cdata = 0

    def startElement(self, tag, attrs={}) :
        self.push(self.current)
        dict = {}
        for key in attrs.keys():
            dict[key] = urllib.unquote(misc.string(attrs[key]))
        self.current = Element(tag,dict)
        if not self.root:
            self.root = self.current
        self.add(self.current)
        self.data = ''

    def endElement(self, tag) :
        self.current.set_content(self.data.strip())
        self.current = self.pop()
        self.data = ''

    def characters(self,content,*args):
        self.data += content
   
if __name__ == '__main__' :
    import sys

    u = """
    mlist = MediaList()
    anime = Media({M_TITLE: 'Gundam Seed', M_EPISODE : '1', \
            M_PUBL: 'AJ', 'date': '2003-08-01'})
    anime2 = Media({M_TITLE: 'Last Exile', M_EPISODE : '15', \
            M_PUBL: 'inf & af', 'date': '2003-07-01'})
    anime3 = Media({M_TITLE: 'Scrapped Princess', M_EPISODE : '2', M_PUBL: 'a-keep', 'date': '2002-08-01'})
    anime4 = Media({M_TITLE : ' Onegai Twins', M_EPISODE : '4', M_PUBL: 'a-keep & a-e', 'date': '2003-08-04'})
    anime5 = Media({M_TITLE : ' Onegai Twins', M_EPISODE : '5', M_PUBL: 'a-keep & a-e', 'date': '2003-08-04'})
    anime6 = Media({M_TITLE : ' Onegai Twins', M_EPISODE : '2', M_PUBL: 'lunar', 'date': '2003-08-04'})
    anime7 = Media({M_TITLE : ' Onegai Twins', M_EPISODE : '1', M_PUBL: 'lunar', 'date': '2003-08-04'})
    mlist.update(anime)
    mlist.update(anime2)
    mlist.update(anime3)
    mlist.update(anime4)
    mlist.update(anime5)
    mlist.update(anime6)
    out = open('out', 'w')
    mlist.save(out)
    out.close()
    file = open('out', 'r')
    print file.read()
    file.seek(0)
    mlist.load(file)
    file.close()
    for anime in mlist.list :
        print anime
    import os
    os.unlink('out')
    """
    test = '''
    mlist = MediaList()
    anime = Media({M_TITLE: 'Gundam Seed', M_EPISODE : '47', \
            M_PUBL: 'ShinSub', 'date': '2003-09-10'})
    anime2 = Media({M_TITLE: 'Last Exile', M_EPISODE : '22', \
            M_PUBL: 'inf & af', 'date': '2003-09-10'})
    anime3 = Media({M_TITLE : ' Onegai Twins', M_EPISODE : '7', M_PUBL: 'a-keep & a-e', 'date': '2003-09-10'})
    mlist.update(anime)
    mlist.update(anime2)
    mlist.update(anime3)
    out = open('out', 'w')
    mlist.save(out)
    out.close()

    mlist2 = MediaList()
    mlist2.load('out')
    '''
    test = '''
    mlist = Element('MediaList')
    mlist.add(Element('Media',{'title': 'Gundam Seed', 'episode': '47', 'publisher': 'ShinSub', 'date': '2003-09-10'}))
    mlist.add(Element('Media',{'title': 'Last Exile', 'episode': '22', 'publisher': 'inf & af', 'date': '2003-09-10'}))
    mlist.add(Element('Media',{'title': ' Onegai Twins', 'episode': '7', 'publisher': 'a-keep & a-e', 'date': '2003-09-10'}))
    '''
    mlist = Element('MediaList')
    mlist.add(Element('Media',{'title': 'Gundam Seed', 'episode': '47', 'publisher': 'ShinSub', 'date': '2003-09-10'},content='<table></table>'))
    import sys
    from cStringIO import StringIO
    fp = StringIO()
    mlist.save(fp)
    fp.seek(0,0)
    print fp.read()
    fp.seek(0,0)
    m = Element('')
    m.load(fp)
    m.save(sys.stdout)
