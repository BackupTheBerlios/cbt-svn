import sys,os

import policy

progname = os.path.basename(sys.argv[0])
logger = None

DEBUG = 3
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
        self.file = policy.get_policy().get_path(progname+'.log')
        self.debug_level = debug_level

    def _log(self,level,msg):
        if self.debug_level >= level:
            try:
                fd = open(self.file,'a')
                fd.write(msg)
                fd.close()
            except Exception,why:
                pass

    def debug(self,msg):
        self._log(DEBUG,msg)

    def info(self,msg):
        self._log(INFO,msg)

    def warn(self,msg):
        self._log(WARN,msg)

    def error(self,msg):
        self._log(ERROR,msg)
