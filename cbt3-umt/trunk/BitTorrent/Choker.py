# Written by Bram Cohen and Jeremy Arendt
# see LICENSE.txt for license information

from random import randrange


class Choker:
    def __init__(self, max_uploads, schedule, friendfunc, infohash, done = lambda: False, min_uploads = None):
        self.max_uploads = max_uploads
        if min_uploads is None:
            min_uploads = max_uploads
        self.min_uploads = min_uploads
        self.schedule = schedule
        self.getfriends = friendfunc
        self.connections = []
        self.infohash = infohash
        self.count = 0
        self.done = done
        self.choke_delay = 10
        self.optimistic_uchoke_period = 3
        self.min_rate = 0.0
        self._SelectChokeAlgo(0, [10, 3, 0])
        schedule(self._OnChoke, self.choke_delay)
    
    #d: [choke_delay, optimistic_uchoke_period, self.min_rate]    
    def SelectChokeAlgo(self, newval, d):
        def foo(self=self, newval=newval, d=d):
            self._SelectChokeAlgo(newval, d)
        self.schedule(foo, 0);        
    
    def _SelectChokeAlgo(self, s, d):
        self.choke_delay = d[0]
        self.min_rate = d[2]
        if self.choke_delay >= self.optimistic_uchoke_period:
            self.optimistic_uchoke_period = 1
        else:
            self.optimistic_uchoke_period = int(self.optimistic_uchoke_period / self.choke_delay)
        
        if s == 0:
            self._rechoke = self._g3_rechoke
            self._shuffler = self._round_robin
        elif s == 1:
            self._rechoke = self._BT34_rechoke
            self._shuffler = self._round_robin
        elif s == 2:
            self._rechoke = self._L33CH_rechoke
            self._shuffler = self._no_shuffle
        else:
            self._rechoke = self._BT34_rechoke
            self._shuffler = self._round_robin
        
    def _OnChoke(self):
        self.schedule(self._OnChoke, self.choke_delay)
        self.count += 1
        self._shuffler()        # call a shuffler
        self._rechoke()         # call a choker        

    def _no_shuffle(self):
        pass
                    
    def _round_robin(self):
        if self.count % self.optimistic_uchoke_period == 0:
            for i in xrange(len(self.connections)):
                u = self.connections[i].get_upload()
                if u.is_choked() and u.is_interested():
                    self.connections = self.connections[i:] + self.connections[:i]
                    break

    def _g3_rechoke(self):
        preferred = []
        friends = []
        friends_ip, foes_ip = self.getfriends(self.infohash)
        
        if len(friends_ip) > 0:
            for c in self.connections:
                if not self._snubbed(c) and c.get_upload().is_interested():
                    try:
                        if friends_ip.has_key(c.get_ip()):
                            friends.append(c)
                    except:
                        print "could not get connection's ip"

        del friends[self.max_uploads-1:]
        
        for c in self.connections:
            if not self._snubbed(c) and c.get_upload().is_interested() \
                and self._rate(c) >= self.min_rate:
                    preferred.append((-self._rate(c), c))
        preferred.sort()

        nperferred = max(0, self.max_uploads - (len(friends) + 1))
        try:
            del preferred[nperferred:]
        except TypeError:
            print 'DEBUG: slice index was not an integer',  nperferred
        preferred = [x[1] for x in preferred]

        preferred = friends + preferred
        count = len(preferred)
        hit = False
        
        j = 0
        for c in self.connections:
            u = c.get_upload()
            if foes_ip.has_key(c.get_ip()):
                self.close_connection(c)
                continue
            if c in preferred:
                j+=1
                u.unchoke()
            else:
                if count < self.min_uploads or not hit:
                    j+=1
                    u.unchoke()
                    if u.is_interested():
                        count += 1
                        hit = True
                else:
                    u.choke()
        
    def _L33CH_rechoke(self):
        for c in self.connections:
            if self._snubbed(c) and c.get_upload().is_interested():
                self.close_connection(c)
                        
    def _BT34_rechoke(self):
        preferred = []
        for c in self.connections:
            if not self._snubbed(c) and c.get_upload().is_interested():
                preferred.append((-self._rate(c), c))
        preferred.sort()
        del preferred[self.max_uploads - 1:]
        preferred = [x[1] for x in preferred]
        count = len(preferred)
        hit = False
        for c in self.connections:
            u = c.get_upload()
            if c in preferred:
                u.unchoke()
            else:
                if count < self.min_uploads or not hit:
                    u.unchoke()
                    if u.is_interested():
                        count += 1
                        hit = True
                else:
                    u.choke()

    def _snubbed(self, c):
        if self.done():
            return False
        return c.get_download().is_snubbed()

    def _rate(self, c):
        if self.done():
            return c.get_upload().get_rate()
        else:
            return c.get_download().get_rate()

    def connection_made(self, connection, p = None):
        if p is None:
            p = randrange(-2, len(self.connections) + 1)
        self.connections.insert(max(p, 0), connection)
        self._rechoke()

    def connection_lost(self, connection):
        self.connections.remove(connection)
        if connection.get_upload().is_interested() and not connection.get_upload().is_choked():
            self._rechoke()

    def interested(self, connection):
        if not connection.get_upload().is_choked():
            self._rechoke()

    def not_interested(self, connection):
        if not connection.get_upload().is_choked():
            self._rechoke()

    def close_connection(self, c):
        def foo(self=self, c=c):
            c.close()
        self.schedule(foo, 0);
        
    def change_max_uploads(self, newval):
        def foo(self=self, newval=newval):
            self._change_max_uploads(newval)
        self.schedule(foo, 0);
    
    def rechoke(self):
        def foo(self=self):
            self._rechoke()
        self.schedule(foo, 0);
                
    def _change_max_uploads(self, newval):
        self.max_uploads = newval
        self.min_uploads = max(2, newval)
        #self._rechoke()

class DummyScheduler:
    def __init__(self):
        self.s = []

    def __call__(self, func, delay):
        self.s.append((func, delay))

class DummyConnection:
    def __init__(self, v = 0):
        self.u = DummyUploader()
        self.d = DummyDownloader(self)
        self.v = v
    
    def get_upload(self):
        return self.u

    def get_download(self):
        return self.d

class DummyDownloader:
    def __init__(self, c):
        self.s = False
        self.c = c

    def is_snubbed(self):
        return self.s

    def get_rate(self):
        return self.c.v

class DummyUploader:
    def __init__(self):
        self.i = False
        self.c = True

    def choke(self):
        if not self.c:
            self.c = True

    def unchoke(self):
        if self.c:
            self.c = False

    def is_choked(self):
        return self.c

    def is_interested(self):
        return self.i

def test_round_robin_with_no_downloads():
    s = DummyScheduler()
    Choker(2, s)
    assert len(s.s) == 1
    assert s.s[0][1] == 10
    s.s[0][0]()
    del s.s[0]
    assert len(s.s) == 1
    assert s.s[0][1] == 10
    s.s[0][0]()
    del s.s[0]
    s.s[0][0]()
    del s.s[0]
    s.s[0][0]()
    del s.s[0]

def test_resort():
    s = DummyScheduler()
    choker = Choker(1, s)
    c1 = DummyConnection()
    c2 = DummyConnection(1)
    c3 = DummyConnection(2)
    c4 = DummyConnection(3)
    c2.u.i = True
    c3.u.i = True
    choker.connection_made(c1)
    assert not c1.u.c
    choker.connection_made(c2, 1)
    assert not c1.u.c
    assert not c2.u.c
    choker.connection_made(c3, 1)
    assert not c1.u.c
    assert c2.u.c
    assert not c3.u.c
    c2.v = 2
    c3.v = 1
    choker.connection_made(c4, 1)
    assert not c1.u.c
    assert c2.u.c
    assert not c3.u.c
    assert not c4.u.c
    choker.connection_lost(c4)
    assert not c1.u.c
    assert c2.u.c
    assert not c3.u.c
    s.s[0][0]()
    assert not c1.u.c
    assert c2.u.c
    assert not c3.u.c

def test_interest():
    s = DummyScheduler()
    choker = Choker(1, s)
    c1 = DummyConnection()
    c2 = DummyConnection(1)
    c3 = DummyConnection(2)
    c2.u.i = True
    c3.u.i = True
    choker.connection_made(c1)
    assert not c1.u.c
    choker.connection_made(c2, 1)
    assert not c1.u.c
    assert not c2.u.c
    choker.connection_made(c3, 1)
    assert not c1.u.c
    assert c2.u.c
    assert not c3.u.c
    c3.u.i = False
    choker.not_interested(c3)
    assert not c1.u.c
    assert not c2.u.c
    assert not c3.u.c
    c3.u.i = True
    choker.interested(c3)
    assert not c1.u.c
    assert c2.u.c
    assert not c3.u.c
    choker.connection_lost(c3)
    assert not c1.u.c
    assert not c2.u.c

def test_robin_interest():
    s = DummyScheduler()
    choker = Choker(1, s)
    c1 = DummyConnection(0)
    c2 = DummyConnection(1)
    c1.u.i = True
    choker.connection_made(c2)
    assert not c2.u.c
    choker.connection_made(c1, 0)
    assert not c1.u.c
    assert c2.u.c
    c1.u.i = False
    choker.not_interested(c1)
    assert not c1.u.c
    assert not c2.u.c
    c1.u.i = True
    choker.interested(c1)
    assert not c1.u.c
    assert c2.u.c
    choker.connection_lost(c1)
    assert not c2.u.c

def test_skip_not_interested():
    s = DummyScheduler()
    choker = Choker(1, s)
    c1 = DummyConnection(0)
    c2 = DummyConnection(1)
    c3 = DummyConnection(2)
    c1.u.i = True
    c3.u.i = True
    choker.connection_made(c2)
    assert not c2.u.c
    choker.connection_made(c1, 0)
    assert not c1.u.c
    assert c2.u.c
    choker.connection_made(c3, 2)
    assert not c1.u.c
    assert c2.u.c
    assert c3.u.c
    f = s.s[0][0]
    f()
    assert not c1.u.c
    assert c2.u.c
    assert c3.u.c
    f()
    assert not c1.u.c
    assert c2.u.c
    assert c3.u.c
    f()
    assert c1.u.c
    assert c2.u.c
    assert not c3.u.c

def test_connection_lost_no_interrupt():
    s = DummyScheduler()
    choker = Choker(1, s)
    c1 = DummyConnection(0)
    c2 = DummyConnection(1)
    c3 = DummyConnection(2)
    c1.u.i = True
    c2.u.i = True
    c3.u.i = True
    choker.connection_made(c1)
    choker.connection_made(c2, 1)
    choker.connection_made(c3, 2)
    f = s.s[0][0]
    f()
    assert not c1.u.c
    assert c2.u.c
    assert c3.u.c
    f()
    assert not c1.u.c
    assert c2.u.c
    assert c3.u.c
    f()
    assert c1.u.c
    assert not c2.u.c
    assert c3.u.c
    f()
    assert c1.u.c
    assert not c2.u.c
    assert c3.u.c
    f()
    assert c1.u.c
    assert not c2.u.c
    assert c3.u.c
    choker.connection_lost(c3)
    assert c1.u.c
    assert not c2.u.c
    f()
    assert not c1.u.c
    assert c2.u.c
    choker.connection_lost(c2)
    assert not c1.u.c

def test_connection_made_no_interrupt():
    s = DummyScheduler()
    choker = Choker(1, s)
    c1 = DummyConnection(0)
    c2 = DummyConnection(1)
    c3 = DummyConnection(2)
    c1.u.i = True
    c2.u.i = True
    c3.u.i = True
    choker.connection_made(c1)
    choker.connection_made(c2, 1)
    f = s.s[0][0]
    assert not c1.u.c
    assert c2.u.c
    f()
    assert not c1.u.c
    assert c2.u.c
    f()
    assert not c1.u.c
    assert c2.u.c
    choker.connection_made(c3, 1)
    assert not c1.u.c
    assert c2.u.c
    assert c3.u.c
    f()
    assert c1.u.c
    assert c2.u.c
    assert not c3.u.c

def test_round_robin():
    s = DummyScheduler()
    choker = Choker(1, s)
    c1 = DummyConnection(0)
    c2 = DummyConnection(1)
    c1.u.i = True
    c2.u.i = True
    choker.connection_made(c1)
    choker.connection_made(c2, 1)
    f = s.s[0][0]
    assert not c1.u.c
    assert c2.u.c
    f()
    assert not c1.u.c
    assert c2.u.c
    f()
    assert not c1.u.c
    assert c2.u.c
    f()
    assert c1.u.c
    assert not c2.u.c
    f()
    assert c1.u.c
    assert not c2.u.c
    f()
    assert c1.u.c
    assert not c2.u.c
    f()
    assert not c1.u.c
    assert c2.u.c
    
def test_multi():
    s = DummyScheduler()
    choker = Choker(4, s)
    c1 = DummyConnection(0)
    c2 = DummyConnection(0)
    c3 = DummyConnection(0)
    c4 = DummyConnection(8)
    c5 = DummyConnection(0)
    c6 = DummyConnection(0)
    c7 = DummyConnection(6)
    c8 = DummyConnection(0)
    c9 = DummyConnection(9)
    c10 = DummyConnection(7)
    c11 = DummyConnection(10)
    choker.connection_made(c1, 0)
    choker.connection_made(c2, 1)
    choker.connection_made(c3, 2)
    choker.connection_made(c4, 3)
    choker.connection_made(c5, 4)
    choker.connection_made(c6, 5)
    choker.connection_made(c7, 6)
    choker.connection_made(c8, 7)
    choker.connection_made(c9, 8)
    choker.connection_made(c10, 9)
    choker.connection_made(c11, 10)
    c2.u.i = True
    c4.u.i = True
    c6.u.i = True
    c8.u.i = True
    c10.u.i = True
    c2.d.s = True
    c6.d.s = True
    c8.d.s = True
    s.s[0][0]()
    assert not c1.u.c
    assert not c2.u.c
    assert not c3.u.c
    assert not c4.u.c
    assert not c5.u.c
    assert not c6.u.c
    assert c7.u.c
    assert c8.u.c
    assert c9.u.c
    assert not c10.u.c
    assert c11.u.c


