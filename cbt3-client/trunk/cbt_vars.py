#-----------------------------------------------------------------------------
# Author:	   warp / visualvinyl
# RCS-ID:	   $Id: cbt_vars.py 110 2004-08-31 01:17:29Z warp $
#-----------------------------------------------------------------------------

PSYCO = 0
REMOTE = "xmlrpc"

prog_name_long = "communityBT"
prog_name = "cbt"
prog_ver = "0.3.1-dev"
prog_build = "65"

if PSYCO:
	prog_name_full = prog_name_long + " v" + prog_ver + " b" + prog_build + "-psyco"
else:
	prog_name_full = prog_name_long + " v" + prog_ver + " b" + prog_build
	
tracker_host = "tracker.umt.pl"
tracker_port = 2710
