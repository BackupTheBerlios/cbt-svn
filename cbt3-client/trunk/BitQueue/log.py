import sys,os

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

    def _log(self,level,msg):
        if level <= self.debug_level:
            try:
                fd = open(self.file,'a')
                fd.write(msg)
                fd.close()
            except Exception,why:
                pass

    def fine(self,msg):
        self._log(FINE,msg)
        print msg

    def finer(self,msg):
        self._log(FINER,msg)
        print msg

    def finest(self,msg):
        self._log(FINEST,msg)
        print msg

    def verbose(self,msg):
        self._log(VERBOSE,msg)

    def debug(self,msg):
        self._log(DEBUG,msg)

    def info(self,msg):
        self._log(INFO,msg)

    def warn(self,msg):
        self._log(WARN,msg)

    def error(self,msg):
        self._log(ERROR,msg)
