# -*- coding: cp1250 -*-
#-----------------------------------------------------------------------------
# Author:	   warp / visualvinyl
# RCS-ID:	   $Id: cbt_vars.py 110 2004-08-31 01:17:29Z warp $
#-----------------------------------------------------------------------------

PSYCO = 0
LOCAL = 1

prog_name_long = "communityBT [UMT.pl edit]"
prog_name = "cbt"
prog_ver = "0.3-dev-test"
prog_build = "55"

if PSYCO:
	prog_name_full = prog_name_long + " v" + prog_ver + " b" + prog_build + "-psyco"
else:
	prog_name_full = prog_name_long + " v" + prog_ver + " b" + prog_build

tracker_host = "tracker.umt.pl"
tracker_port = 2710

if LOCAL:
	pyroloc = "PYROLOC://127.0.0.1:7766/cBTS"
	jabserv = "127.0.0.1"
else:
	pyroloc = "PYROLOC://umt.pl:7766/cBTS"
	jabserv = "umt.pl"
