import sys,os
import time

import policy

progname = os.path.basename(sys.argv[0])
logger = None

FINEST = 7
FINER = 6
FINE = 5
DEBUG = 4
VERBOSE = 3
INFO = 2
WARN = 1
ERROR = 0

def get_logger():
    global logger
    if not logger:
        logger = Logger(progname)
    return logger

class Logger:
    def __init__(self,progname,debug_level=WARN):
        pol = policy.get_policy()
        self.file = pol.get_path(progname+'.log')
        self.debug_level = pol(policy.DEBUG_LEVEL)

    def set_debug_level(self,level):
        self.debug_level = level

    def _log(self,level,msg,notime):
        if level <= self.debug_level:
            now = time.strftime('%Y%m%d-%H:%M:%S')
            try:
                fd = open(self.file,'a')
                if not notime:
                    fd.write(now+'\n')
                fd.write(msg)
                fd.close()
            except Exception,why:
                pass
            if level >= FINE:
                if not notime:
                    print now
                print msg

    def fine(self,msg,notime=0):
        self._log(FINE,msg,notime)

    def finer(self,msg,notime=0):
        self._log(FINER,msg,notime)

    def finest(self,msg,notime=0):
        self._log(FINEST,msg,notime)

    def verbose(self,msg,notime=0):
        self._log(VERBOSE,msg,notime)

    def debug(self,msg,notime=0):
        self._log(DEBUG,msg,notime)

    def info(self,msg,notime=0):
        self._log(INFO,msg,notime)

    def warn(self,msg,notime=0):
        self._log(WARN,msg,notime)

    def error(self,msg,notime=0):
        self._log(ERROR,msg,notime)
