
version = "Q-0.0.16 163 (BitQueue)"

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

def createPeerID(ins = '---'):
    assert type(ins) is StringType
    assert len(ins) == 3
    myid = version_short[0]
    for subver in version_short[2:].split('.'):
        try:
            subver = int(subver)
        except:
            subver = 0
        myid += mapbase64[subver]
    myid += ('-' * (6-len(myid)))
    myid += ins
    myid += encode_build(version_build)
    for i in sha(repr(time()) + str(getpid())).digest()[-8:]:
        myid += mapbase64[ord(i) & 0x3F]
    return myid

