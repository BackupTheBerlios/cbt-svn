#-----------------------------------------------------------------------------
# Name: 	   winsetup.py
# Author:	   warp / visualvinyl
# RCS-ID:	   $Id: winsetup.py 49 2004-08-20 23:40:41Z warp $
#-----------------------------------------------------------------------------

from distutils.core import setup
import py2exe

#~ try:
    #~ import psyco
    #~ psyco.log()
    #~ psyco.full()
#~ except:
    #~ print 'psyco not installed, proceeding as normal'

manifest_template = '''
<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<assembly xmlns="urn:schemas-microsoft-com:asm.v1" manifestVersion="1.0">
<assemblyIdentity
    version="0.64.1.0"
    processorArchitecture="x86"
    name="%(prog)s"
    type="win32"
/>
<description>%(prog)s Program</description>
<dependency>
    <dependentAssembly>
        <assemblyIdentity
            type="win32"
            name="Microsoft.Windows.Common-Controls"
            version="6.0.0.0"
            processorArchitecture="X86"
            publicKeyToken="6595b64144ccf1df"
            language="*"
        />
    </dependentAssembly>
</dependency>
</assembly>
'''

RT_MANIFEST = 24

setup(

	name='communityBT',
	
	options = {"py2exe": {"compressed": 1, "optimize": 2, "dist_dir": "../../cbt3-bin/trunk", "packages": ["encodings"]}},
		
	windows = [ 
			{ 'other_resources': [(RT_MANIFEST, 1, manifest_template % dict(prog="cbt"))],
			'script': 'cbt.py', 
			'excludes': ["pywin", "pywin.debugger", "pywin.debugger.dbgcon", "pywin.dialogs", "pywin.dialogs.list", "Tkconstants","Tkinter","tcl" ]
			'icon_resources': [(1, "data/icn_cbt.ico")] },
				
			#~ { "script": "cbt_update.py",
			  #~ "icon_resources": [(1, "data/icn_cbt1.ico")] },

			#~ { "other_resources": [(RT_MANIFEST, 1, manifest_template % dict(prog="cbt"))],
			#~ "script": "cbt_options.py", 
			#~ "icon_resources": [(1, "data/conf.ico")] },

			#~ { "other_resources": [(RT_MANIFEST, 1, manifest_template % dict(prog="cbtupd"))],
			#~ "script": "update.py", 
			#~ "icon_resources": [(1, "_va/app.ico")] }
	],
	
	#~ console = [ 
			#~ { "script": "btqueue.py", "icon_resources": [(1, "_va/torrent.ico")] },
			#~ { "script": "urlqueue.py", "icon_resources": [(1, "_va/torrent.ico")] }
		#~ ],

	#~ zipfile = "lib.pyz",
	zipfile = None,
	
	data_files = [
		("", ["panels.xrc", "tpl.html", "ip2cc.db"])
	]
	
	#~ data_files=[
	
	#~ ("data",["data/cbt.ico","data/crt.ico","data/app.ico","data/folder.png", "data/folder_red.png", "data/about.ico", "data/chat.ico", "data/conf.ico", "data/down.ico", "data/idea.ico", "data/img0.xpm", "data/info.ico", "data/my.ico", "data/pause24.xpm", "data/public.ico", "data/remove24.xpm", "data/resume24.xpm", "data/warn.ico", "data/myedit24.xpm", "data/mydelete24.xpm", "data/mynew24.xpm", "data/refresh24.xpm", "data/conf24.xpm", "data/myupload24.xpm", "data/confupl24.xpm", "data/up1.xpm", "data/up2.xpm", "data/dn1.xpm", "data/dn2.xpm"]),
	
	#~ ("", ["gui.xrc", "announce.lst", "torrent.lst", "cbt.conf", "list.conf"])
	
	#~ ],

)
