#-----------------------------------------------------------------------------
# Author:	   warp / visualvinyl
# RCS-ID:	   $Id: cbt_widgets.py 98 2004-08-30 21:28:34Z warp $
#-----------------------------------------------------------------------------

import wx, sys
from images import Images
from cbt_func import *

class CbtNavbar(wx.ListCtrl):
	def __init__(self, parent, id, act=None):
		#~ wx.ListCtrl.__init__(self, parent, id, style = wx.LC_ICON|wx.LC_SINGLE_SEL|wx.GROW) # large icons
		wx.ListCtrl.__init__(self, parent, id, style = wx.LC_REPORT|wx.LC_NO_HEADER|wx.LC_SINGLE_SEL|wx.GROW) # report
		
		self.images = Images(".")

		il = wx.ImageList(32, 32)
		il.Add(self.images.GetImage("nav_transfer"))
		il.Add(self.images.GetImage("nav_chat"))
		il.Add(self.images.GetImage("nav_public"))
		il.Add(self.images.GetImage("nav_my"))
		il.Add(self.images.GetImage("nav_options"))
		#~ il
		
		#~ self.AssignImageList(il, wx.IMAGE_LIST_NORMAL) # large icons
		self.AssignImageList(il, wx.IMAGE_LIST_SMALL) # report
				
		self.SetBackgroundColour(wx.Colour(28,57,104))
		self.SetTextColour(wx.Colour(240,240,240))
		self.SetFont(defFontB)
		
		self.InsertColumn(0, ".")
		self.SetColumnWidth(0, 150)

		imID = 0
		self.items = [ (_("Transfers"), 0, "pub"), (_("Chat"), 1, "log"), (_("Public torrents"), 2, "log"), (_("My torrents"), 3, "log"), (_("Options"), 4, "pub") ]
		
		self.Update("pub")
			
		self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, act)
		
		#~ self.SetColumnWidth(0, -1) # report
		
	def Update(self, show=None):
		imID = 0
		
		self.DeleteAllItems()
		
		for item in self.items:
			if (show=="pub" and item[2]=="pub") or (show=="all"):
				self.InsertImageStringItem(imID, item[0], item[1])
				self.SetItemData(imID, item[1])
				imID = imID + 1
		

class CbtToolBar(wx.ToolBar):
	def __init__(self, parent, id=-1, size=wx.DefaultSize, style=(wx.TB_HORIZONTAL|wx.NO_BORDER|wx.TB_FLAT|wx.TB_TEXT)):
		wx.ToolBar.__init__(self, parent, id, size = size, style = style)

		self.SetToolBitmapSize((24,24))
		self.SetToolPacking(3)
		
		self.Bind(wx.EVT_SIZE, self.OnReSize)
		
	def OnReSize(self, event):
		self.Refresh(False)
		self.Update()
