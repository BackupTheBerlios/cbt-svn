#-----------------------------------------------------------------------------
# Author:	   warp / visualvinyl (based on g3torrent source)
# RCS-ID:	   $Id: images.py 47 2004-08-20 23:18:20Z warp $
#-----------------------------------------------------------------------------

import wx, os
from os.path import join, normpath
from wxPython.wx import wxImageFromStream, wxBitmapFromImage

class Images:
	def __init__(self, path = ""):
		wx.InitAllImageHandlers()
		self.LoadImages(path)

	def LoadImages(self, path):

		icons = {}
		iconslist = os.listdir( join(path, normpath("data/")) )
		for icon in iconslist:
			try:
				if icon.split('.')[1] == 'ico':
					icons[icon.split('.')[0]] = wx.Icon(join(path, normpath("data/%s" % icon)), wx.BITMAP_TYPE_ICO)
				if icon.split('.')[1] == 'png':
					icons[icon.split('.')[0]] = wx.Bitmap(join(path, normpath("data/%s" % icon)), wx.BITMAP_TYPE_PNG)
				if icon.split('.')[1] == 'xpm':
					icons[icon.split('.')[0]] = wx.Bitmap(join(path, normpath("data/%s" % icon)), wx.BITMAP_TYPE_XPM)
			except:
				pass

		flags = {}
		flagslist = os.listdir( join(path, normpath("data/flags/")) )
		for icon in flagslist:
			try:
				if icon.split('.')[1] == 'png':
					flags[icon.split('.')[0]] = wx.Bitmap(join(path, normpath("data/flags/%s" % icon)), wx.BITMAP_TYPE_PNG)
			except:
				pass		
		
		icons['flags'] = flags
		self.images = icons
	

	def GetImage(self, key):
		if self.images.has_key(key):
			return self.images[key]
		else:
			return self.images['blank']
