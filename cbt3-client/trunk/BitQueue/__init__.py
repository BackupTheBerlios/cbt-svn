
version = "Q-0.0.18 248 (BitQueue)"

version_short = version.split(' ')[0]
version_num = version.split(' ')[0].split('-')[1]
version_build = int(version.split(' ')[1])

from types import StringType
from sha import sha
from time import time
try:
    from os import getpid
except ImportError:
    def getpid():
        return 1

mapbase64 = '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz.-'

class BindException(Exception):
    pass

def cmp_version(a,b):
    ai = [int(i) for i in a.split('.')]
    bi = [int(i) for i in b.split('.')]
    l = min(len(ai),len(bi))
    for i in range(l):
        ret = cmp(ai[i],bi[i])
        if ret != 0:
            return ret
    return cmp(len(ai),len(bi))

def encode_build(build):
    x = ''
    for i in xrange(3):
        x = mapbase64[build & 0x3F]+x
        build >>= 6
    return x

def decode_build(build):
    build_num = 0
    for i in xrange(3):
        try:
            x = mapbase64.index(build[i])
        except ValueError:
            return 0
        build_num <<= 6
        build_num += x
    return build_num

def encode_version(ver):
    ver_str = ''
    for subver in ver.split('.'):
        try:
            subver = int(subver)
        except:
            subver = 0
        ver_str += mapbase64[subver]
    return ver_str

def decode_version(ver):
    for i in range(3):
        try:
            index = mapbase64.index(ver[i])
        except:
            index = 0
        ver[i] = str(index)
    return '.'.join(ver)

def createPeerID(ins = '---'):
    assert type(ins) is StringType
    assert len(ins) == 3
    myid = version_short[0]
    myid += encode_version(version_short[2:])
    myid += ('-' * (6-len(myid)))
    myid += ins
    myid += encode_build(version_build)
    for i in sha(repr(time()) + str(getpid())).digest()[-8:]:
        myid += mapbase64[ord(i) & 0x3F]
    return myid

