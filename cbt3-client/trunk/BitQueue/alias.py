#!/usr/bin/python

alias = None

ALIAS_FILE = 'alias.conf'

import sys,os
import math,re
from ConfigParser import *

import policy

def get_alias(root_path=None,**kw):
    global alias
    if not alias:
        import sys
        if not root_path:
            root_path = os.path.dirname(os.path.abspath(sys.argv[0]))
        policy = apply(Alias,(root_path,),kw)
    return policy

class Alias:
    def __init__(self,updated=None):
        self.updated = updated
        self.share_path = os.path.join(sys.prefix,'share','BTQueue')
        self.program_path = os.path.dirname(os.path.abspath(sys.argv[0]))
        pol = policy.get_policy()
        self.file = pol.get_path(ALIAS_FILE,writable=1)
        if sys.platform == 'win32' or not os.environ.get('HOME'):
            default_path = self.program_path
        else:
            default_path = os.environ.get('HOME')
        self.aliases = ConfigParser()
        for prefix in [self.share_path,self.program_path]:
            self.load(os.path.join(prefix,ALIAS_FILE))
        self.load()
        self.save()

    def set_default(self):
        global alias
        alias = self

    def set_handler(self,updated):
        self.updated = updated

    def _extract(self,key):
        try:
            group,name = key.split('.',1)
        except:
            group,name = 'main',key
        return group,name

    def load(self,file=None):
        file = file or self.file
        try:
            self.aliases.read(file)
        except IOError:
            pass
        if not self.aliases.has_section('main'):
            self.aliases.add_section('main')

    def save(self):
        try:
            fd = open(self.file,'w')
            self.aliases.write(fd)
            fd.close()
        except Exception,why:
            return

    def set(self,key,value):
        group,name = self._extract(key)
        if not self.aliases.has_section(group):
            self.aliases.add_section(group)
        self.aliases.set(group,name,value)
        if self.updated:
            self.updated(key)

    def __call__(self,args):
        return self.get(args)

    def groups(self):
        return self.aliases.sections()

    def keys(self,group=None):
        if type(group) != type([]) and group is not None:
            group = [str(group)]
        groups = group or self.aliases.sections()
        keys = []
        for group in groups:
            for name in self.aliases.options(group):
                keys.append('%s.%s' % (group,name))
        return keys

    def has_key(self,key):
        try:
            self.get(key,raw=1)
            return 1
        except KeyError:
            return 0

    def get(self,key,args=[],raw=0):
        group,name = self._extract(key)
        vars = {}
        for i in xrange(len(args)):
            vars['arg%d' % (i+1)] = args[i]
        try:
            ret = self.aliases.get(group,name,raw,vars)
        except NoSectionError:
            raise KeyError,'%s not found' % group
        except NoOptionError:
            raise KeyError,'%s not found in %s' % (name,group)
        except (InterpolationError,ValueError):
            raise KeyError,'invalid arguments'
        return ret

    def remove(self,key):
        group,name = self._extract(key)
        try:
            self.aliases.remove_option(group,name)
            if len(self.aliases.options(group)) == 0:
                self.aliases.remove_section(group)
        except NoSectionError:
            pass

def test_alias():
    aliases = Alias()
    aliases.set('hongfire.baseurl','http://www.hongfire.com/')
    aliases.set('hongfire.login','wpost %(baseurl)slogin.php?vb_username=abc')
    aliases.set('hongfire.login2','wpost %(baseurl)slogin.php?vb_username=%(arg1)s')
    aliases.save()
    print aliases.get('hongfire.baseurl')
    print aliases.get('hongfire.login')
    print aliases.get('hongfire.login2',['abc','def'])

if __name__ == '__main__':
    test_alias()
