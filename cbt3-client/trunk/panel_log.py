# -*- coding: cp1250 -*-
#-----------------------------------------------------------------------------
# Author:	   warp / visualvinyl
# RCS-ID:	   $Id: panel_chat.py 47 2004-08-20 23:18:20Z warp $
#-----------------------------------------------------------------------------

import wx, os, sys

from images import Images
from cbt_func import *
from time import time, strftime, localtime

class PanelLog(wx.MDIChildFrame):
	def __init__(self, parent, id):
		wx.MDIChildFrame.__init__(self, parent, id, title="Log programu", size = (560,340), style = wx.DEFAULT_FRAME_STYLE)
		
		self.list = wx.ListCtrl(self, -1, style=wx.LC_REPORT|wx.LC_AUTOARRANGE|wx.LC_VRULES|wx.SUNKEN_BORDER)
		
		cols = [ [0, "Godzina", wx.LIST_FORMAT_LEFT, 80],
				 [1, "Moduł", wx.LIST_FORMAT_LEFT, 80],
				 [2, "Msg", wx.LIST_FORMAT_LEFT, 300],
				 ]
				 
		InsertColumns(self.list, cols)
		
		self.__set_properties()
		self.__do_layout()

		self.parent = parent

		self.images = Images(".")
		self.SetIcon(self.images.GetImage("icn_cbt"))

		self.Activate()
		
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		self.Bind(wx.EVT_SET_FOCUS, self.OnActivate)

	def OnClose(self, evt):
		#~ self.parent.windows["log"] = 0
		#~ self.Destroy()
		pass
		
	def OnActivate(self, evt):
		self.images = Images(".")
		self.SetIcon(self.images.GetImage("icn_cbt"))
		
	def __set_properties(self):
		self.list.SetFont(wx.Font(8, wx.MODERN, wx.NORMAL, wx.NORMAL, 0, "Tahoma"))

	def __do_layout(self):
		sizer_1 = wx.BoxSizer(wx.VERTICAL)
		sizer_1.Add(self.list, 1, wx.EXPAND, 0)
		self.SetAutoLayout(1)
		self.SetSizer(sizer_1)
		sizer_1.Fit(self)
		sizer_1.SetSizeHints(self)
		self.Layout()
		
	def AddMsg(self, src, msg, type=None):

		t = localtime(time())
		timestamp = "%s" % (strftime("%H:%M:%S", t))

		item_idx = self.list.GetItemCount()
		self.list.InsertStringItem(item_idx, timestamp)
		self.list.SetStringItem(item_idx, 1, src)
		self.list.SetStringItem(item_idx, 2, msg)
		item = self.list.GetItem(item_idx)
		
		if type == "info":
			item.SetBackgroundColour( wx.Color(255,255,230) )
			item.SetTextColour( wx.Color(50,20,10) )
		if type == "error":
			item.SetBackgroundColour( wx.Color(255,180,180) )
			item.SetTextColour( wx.Color(0,0,0) )
			self.SetIcon(self.images.GetImage("icn_warn"))
			
		self.list.SetItem(item)
		self.list.ScrollList(0, 100)
