#!/usr/bin/python

policy = None

QUEUE_FILE = 'torrent.lst'
POLICY_FILE = 'policy.conf'
HISTORY_FILE = 'history.lst'
IP2CC_FILE = 'ip2cc.db'
UNKNOWN_ID_FILE = 'unknownid.log'

DEBUG_LEVEL = 'debug_level'
REASSIGN_ID = 'reassign_id'
USE_LOCAL_POLICY = 'use_local_policy'
USE_SINGLE_PORT = 'use_single_port'
DEFAULT_SOCKET_TIMEOUT = 'default_socket_timeout'
MAX_JOB_RUN = 'max_run_job'
DEFAULT_PRIORITY = 'default_priority'
SCHEDULING_INTERVAL = 'scheduling_interval'
REREQUEST_INTERVAL = 'rerequest_interval'
REPORT_IP = 'report_ip'
BIND_IP = 'bind_ip'
IPV6_BINDS_V4 = 'ipv6_binds_v4'
UPNP_NAT_ACCESS = 'upnp_nat_access'
MIN_PORT = 'min_port'
MAX_PORT = 'max_port'
RANDOM_PORT = 'random_port'
MIN_PEER = 'min_peer'
MAX_PEER = 'max_peer'
MAX_INITIATE = 'max_initiate'
MAX_UPLOAD_RATE = 'max_upload_rate'
MAX_DOWNLOAD_RATE = 'max_download_rate'
MAX_SEED_RATE = 'max_seed_rate'
DEST_PATH = 'dest_path'
TORRENT_PATH = 'torrent_path'
MIN_SHARE_RATIO = 'min_share_ratio'
LOG_UNKNOWN_ID = 'log_unknown_id'
IGNORE_WAITING_MEDIA = 'ignore_waiting_media'
ALLOW_ACL = 'allow_acl'
DENY_ACL = 'deny_acl'
ORDER_ACL = 'order_acl'
MAX_LAST_BANNED = 'max_last_banned'
VERIFY_LINK = 'verify_link'

WEBSERVICE_ID = 'webservice_id'
WEBSERVICE_IP = 'webservice_ip'
WEBSERVICE_PORT = 'webservice_port'
WEBSERVICE_ = 'webservice_'
WEBSERVICE_CLOSE = 'webservice_close'
WEBSERVICE_QUERY = 'webservice_query'
WEBSERVICE_ADD = 'webservice_add'
WEBSERVICE_DELETE = 'webservice_delete'
WEBSERVICE_PAUSE = 'webservice_pause'
WEBSERVICE_RESUME = 'webservice_resume'
WEBSERVICE_QUEUE = 'webservice_queue'
WEBSERVICE_VERSION = 'webservice_version'
WEBSERVICE_GSET = 'webservice_gset'

CBT_LOGIN = 'cbt_login'
CBT_PASSWORD = 'cbt_password'
CBT_SHOWSPLASH = 'cbt_showsplash'
CBT_RPCURL = 'cbt_rpcurl'
CBT_LANG = 'cbt_lang'

import sys,os
import math,re
from ConfigParser import NoOptionError
from ip2cc import inet_aton

def get_policy(root_path=None,**kw):
    global policy
    if not policy:
        import sys
        if not root_path:
            root_path = os.path.dirname(os.path.abspath(sys.argv[0]))
        policy = apply(Policy,(root_path,),kw)
    return policy

def ip_to_int(ip):
    n = 0
    for i in ip.split('.'):
        n *= 256
        n += int(i) & 0xff
    return n

def int_to_ip(n):
    return '%d.%d.%d.%d' % (n>>24&0xff,n>>16&0xff,n>>8&0xff,n&0xff)

class AccessControl:
    def __init__(self,acl):
        self.update(acl)

    def update(self,acl):
        self.acl = acl

    def exists(self,ip):
        return self.acl == ip

class AllAC(AccessControl):
    def exists(self,ip):
        return 1

class NoneAC(AccessControl):
    def exists(self,ip):
        return 1

class IPRangeAC(AccessControl):
    def update(self,acl):
        try:
            network,prefix = acl.split('/')
            self.netmask = ~long(math.pow(2,32-int(prefix))-1) & 4294967295L
            self.network = ip_to_int(network)
        except ValueError:
            try:
                self.network = ip_to_int(acl)
            except ValueError:
                self.network = 0
            self.netmask = 4294967295L

    def exists(self,ip):
        try:
            ipn = ip_to_int(ip)
        except ValueError:
            return 0
        return (ipn & self.netmask) == self.network

class NetNameAC(AccessControl):
    def __init__(self,acl,ipdb=None):
        AccessControl.__init__(self,acl)
        self.ipdb = ipdb

    def update(self,acl):
        self.acl = acl.upper()

    def exists(self,ip):
        try:
            cc,netname = self.ipdb[ip].split(':')
        except (KeyError,AssertionError,TypeError,IndexError):
            return 0
        else:
            return self.acl == netname

class CountryAC(AccessControl):
    def __init__(self,acl,ipdb=None):
        AccessControl.__init__(self,acl)
        self.ipdb = ipdb

    def update(self,acl):
        self.acl = acl.upper()

    def exists(self,ip):
        try:
            cc,netname = self.ipdb[ip].split(':')
        except (KeyError,AssertionError):
            return 0
        else:
            return self.acl == cc

class ACL(AccessControl):

    ip_cre = re.compile(r'\d+\.\d+\.\d+\.\d+(/\d+)?',re.I)

    def __init__(self,acl,ipdb=None):
        self.ipdb = ipdb
        AccessControl.__init__(self,acl)

    def update(self,acl):
        self.acls = []
        for item in acl.split(','):
            item = item.strip()
            if not item:
                continue
            if len(item) == 2:
                o = CountryAC(item,self.ipdb)
            elif item.upper() == 'ALL':
                o = AllAC(item)
            elif item.upper() == 'NONE':
                o = NoneAC(item)
            elif self.ip_cre.match(item):
                o = IPRangeAC(item)
            else:
                o = NetNameAC(item,self.ipdb)
            self.acls.append(o)

    def exists(self,ip):
        for o in self.acls:
            if o.exists(ip):
                return 1
        return 0

class EntryPolicy:
    def __init__(self,conf=None,section=None):
        self.params = {MIN_SHARE_RATIO: 1.0,
                       USE_LOCAL_POLICY: 0,
                      }
        pol = get_policy()
        for key in self.params.keys():
            value = pol(key)
            if value != None:
                self.params[key] = value
        if conf and section:
            self.load(conf,section)

    def load(self,conf,section):
        for key in self.params.keys():
            try:
                self.update(key,conf.get(section,key))
            except NoOptionError: 
                pass

    def save(self,conf,section):
        for key in self.params.keys():
            conf.set(section,key,str(self.params[key]))

    def update(self,key,value):
        if not self.params.has_key(key):
            self.params[key] = value
            return
        if type(self.params[key]) == type(0):
            self.params[key] = int(value)
        elif type(self.params[key]) == type(0.0):
            self.params[key] = float(value)
        else:
            self.params[key] = value

    def __call__(self,args):
        return self.get(args)

    def keys(self):
        return self.params.keys()

    def get(self,key):
        try:
            ret = self.params[key]
        except KeyError:
            ret = None
        return ret

class Policy:
    def __init__(self,root_path,updated=None):
        self.root_path = root_path
        self.updated = updated
        self.share_path = os.path.join(sys.prefix,'share','BTQueue')
        self.program_path = os.path.dirname(os.path.abspath(sys.argv[0]))
        self.file = self.get_path(POLICY_FILE)
        if sys.platform == 'win32' or not os.environ.get('HOME'):
            default_path = self.program_path
        else:
            default_path = os.environ.get('HOME')
        self.params = {MAX_JOB_RUN: 5,
                       USE_SINGLE_PORT: 1,
                       DEFAULT_SOCKET_TIMEOUT: 10,
                       DEFAULT_PRIORITY: 5,
                       SCHEDULING_INTERVAL: 10,
                       REREQUEST_INTERVAL: 5*60,
                       DEBUG_LEVEL: 0,
                       REASSIGN_ID: 1,
                       LOG_UNKNOWN_ID: 0,
                       REPORT_IP: '',
                       BIND_IP: '',
                       IPV6_BINDS_V4: 0,
                       UPNP_NAT_ACCESS: 1,
                       MIN_PORT: 16881,
                       MAX_PORT: 16999,
                       RANDOM_PORT: 1,
                       MIN_PEER: 20,
                       MAX_PEER: 90,
                       MAX_INITIATE: 40,
                       MAX_UPLOAD_RATE: 10,
                       MAX_DOWNLOAD_RATE: 0,
                       MAX_SEED_RATE: 10,
                       MIN_SHARE_RATIO: 1.0,
                       DEST_PATH: os.path.join(default_path,'incoming'),
                       TORRENT_PATH: os.path.join(default_path,'torrent'),
                       IGNORE_WAITING_MEDIA: 0,
                       ALLOW_ACL: 'ALL',
                       DENY_ACL: 'NONE',
                       ORDER_ACL: 'allow,deny',
                       MAX_LAST_BANNED: 20,
                       VERIFY_LINK: 0,
                       WEBSERVICE_IP: '127.0.0.1',
                       WEBSERVICE_PORT: 19428,
                       WEBSERVICE_ID: 'cbt',
                       WEBSERVICE_CLOSE: False,
                       WEBSERVICE_QUERY: True,
                       WEBSERVICE_ADD: True,
                       WEBSERVICE_DELETE: True,
                       WEBSERVICE_PAUSE: True,
                       WEBSERVICE_RESUME: True,
                       WEBSERVICE_QUEUE: True,
                       WEBSERVICE_VERSION: True,
                       WEBSERVICE_GSET: False,

                       CBT_LOGIN: '',
                       CBT_PASSWORD: '',
                       CBT_SHOWSPLASH: 1,
                       CBT_RPCURL: '',
                       CBT_LANG: '',
                      }
        self.load()

    def set_default(self):
        global policy
        policy = self

    def set_handler(self,updated):
        self.updated = updated

    def load(self):
        try:
            fd = open(self.file,'r')
            while 1:
                line = fd.readline()
                if not line:
                    break
                if line.strip()[0] == '#':
                    continue
                try:
                    key,value = line.split('=')
                except ValueError:
                    continue
                key = key.strip()
                value = value.strip()
                self.update(key,value)
            fd.close()
        except IOError:
            return

    def save(self):
        try:
            fd = open(self.file,'w')
            for key in self.params.keys():
                fd.write('%s=%s\n' % (key,str(self.params[key])))
            fd.close()
        except Exception,why:
            return

    def update(self,key,value):
        if not self.params.has_key(key):
            return
        if type(self.params[key]) == type(0):
            self.params[key] = int(value)
        elif type(self.params[key]) == type(0.0):
            self.params[key] = float(value)
        else:
            self.params[key] = value
        if self.updated:
            self.updated(key)

    def __call__(self,args):
        return self.get(args)

    def keys(self):
        return self.params.keys()

    def get(self,key):
        try:
            ret = self.params[key]
        except KeyError:
            ret = None
        return ret

    def get_path(self,basename):
        if not os.path.exists(self.root_path):
            os.mkdir(self.root_path)
        for prefix in [self.root_path,self.share_path,self.program_path]:
            path = os.path.join(prefix,basename)
            if os.path.exists(path):
                return path
        return os.path.join(self.root_path,basename)

def test_acl():
    import ip2cc
    ipdb = ip2cc.CountryByIP('ip2cc.db')
    acl = IPRangeAC('158.108.0.0/16')
    print acl.exists('158.108.34.1')
    print acl.exists('158.109.34.1')
    acl = NetNameAC('teleglobe-as',ipdb)
    print acl.exists('203.113.22.1')
    print acl.exists('158.108.34.1')
    acl = CountryAC('th',ipdb)
    print acl.exists('203.113.22.1')
    print acl.exists('158.108.34.1')
    acl = ACL('teleglobe-as',ipdb)
    print acl.exists('203.113.22.1')
    print acl.exists('158.108.34.1')

if __name__ == '__main__':
    test_acl()
