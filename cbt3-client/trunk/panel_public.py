#-----------------------------------------------------------------------------
# Author:	   warp / visualvinyl
# RCS-ID:	   $Id: panel_public.py 106 2004-08-31 00:13:34Z warp $
#-----------------------------------------------------------------------------

import wx, os, sys, feedparser, urllib
from wxPython.xrc import *

from images import Images
from cbt_func import InsertColumns
from cbt_vars import *

class PanelPublic(wx.MDIChildFrame):
	def __init__(self, parent, id, btq=None):
		wx.MDIChildFrame.__init__(self, parent, id, title=_("Public torrents"), style = wx.DEFAULT_FRAME_STYLE)
		
		self.images = Images(".")
		self.SetIcon(self.images.GetImage("icn_public"))
		
		self.btq = btq
		self.parent = parent
		
		self.xrc = wxXmlResource('panels.xrc')
		self.xrc.LoadPanel(self, "panelPub")
		
		#~ self.panelPub = XRCCTRL(self, "panelPub")
		self.treePub = XRCCTRL(self, "treePub")
		self.listPub = XRCCTRL(self, "listPub")
		#~ self.listPub.SetWindowStyleFlag(wx.LC_REPORT | wx.LC_SINGLE_SEL)
		self.btnPubRefresh = XRCCTRL(self, "btnPubRefresh")
		self.chkPubSeeds = XRCCTRL(self, "chkPubSeeds")
		
		cols = [ [0, _("Date"), wx.LIST_FORMAT_LEFT, 120],
			[1, _("Title"), wx.LIST_FORMAT_LEFT, 200],
			[2, _("Size"), wx.LIST_FORMAT_LEFT, 70],
			[3, _("Seeds"), wx.LIST_FORMAT_LEFT, 48],
			[4, _("Peers"), wx.LIST_FORMAT_LEFT, 48],
			[5, _("Downloaded"), wx.LIST_FORMAT_LEFT, 48],
			[6, _("Uploader"), wx.LIST_FORMAT_LEFT, 80] ]
	
		InsertColumns(self.listPub, cols)

		self.Activate()
		self.PublicLoadFeeds()
		
		self.Bind(wx.EVT_CLOSE, self.OnClose)
		self.Bind(wx.EVT_TREE_SEL_CHANGED, self.PublicChanged, id=XRCID("treePub"))

		#~ EVT_TREE_SEL_CHANGED(self, XRCID("treePub"), self.PublicChanged)
		#~ EVT_CHECKBOX(self, XRCID("chkPubSeeds"), self.PublicChanged) 

	def OnClose(self, evt):
		self.parent.windows["public"] = 0
		self.Destroy()

	def PublicLoadFeeds(self):
		
		self.btnPubRefresh.Enable(False)

		imglist = wx.ImageList(16, 16, True, 2)
		imglist.Add(self.images.GetImage('pub_folder'))
		imglist.Add(self.images.GetImage('pub_folder_red'))
	
		self.treePub.DeleteAllItems()
		self.listPub.DeleteAllItems()

		self.cbtFeeds = []
		self.cbtFeeds.append(self.LoadFeed('pub', cat='0'))
		self.cbtFeeds.append(self.LoadFeed('pub', cat='1'))
		self.cbtFeeds.append(self.LoadFeed('pub', cat='2'))
		self.cbtFeeds.append(self.LoadFeed('pub', cat='3'))
		self.cbtFeeds.append(self.LoadFeed('pub', cat='4'))
		self.cbtFeeds.append(self.LoadFeed('pub', cat='5'))
		self.cbtFeeds.append(self.LoadFeed('pub', cat='6'))
		
		self.treePub.AssignImageList(imglist)
		root = self.treePub.AddRoot(_('Torrents'), 0, 1, data=wx.TreeItemData('-1'))
		umt = self.treePub.AppendItem(root, 'umt.pl', 0, 1, data=wx.TreeItemData('own'))
		self.treePub.AppendItem(umt, 'mp3 (ep) [%s]' % len(self.cbtFeeds[0]['torrents']), 0, 1, data=wx.TreeItemData('0'))
		self.treePub.AppendItem(umt, 'mp3 (cd) [%s]' % len(self.cbtFeeds[1]['torrents']), 0, 1, data=wx.TreeItemData('1'))
		self.treePub.AppendItem(umt, 'mp3 (mix) [%s]' % len(self.cbtFeeds[2]['torrents']), 0, 1, data=wx.TreeItemData('2'))
		self.treePub.AppendItem(umt, 'video [%s]' % len(self.cbtFeeds[3]['torrents']), 0, 1, data=wx.TreeItemData('3'))
		self.treePub.AppendItem(umt, 'wypociny [%s]' % len(self.cbtFeeds[4]['torrents']), 0, 1, data=wx.TreeItemData('4'))
		self.treePub.AppendItem(umt, 'programy [%s]' % len(self.cbtFeeds[5]['torrents']), 0, 1, data=wx.TreeItemData('5'))
		self.treePub.AppendItem(umt, 'inne [%s]' % len(self.cbtFeeds[6]['torrents']), 0, 1, data=wx.TreeItemData('6'))
		
		self.treePub.Expand(root)
		self.treePub.Expand(umt)

		#~ self.statusBar.SetStatusText("", 0)
		self.btnPubRefresh.Enable(True)
		
	def LoadFeed(self, mode, cat=None, user=None):
		try:
			if mode == 'pub':
				#~ feed = feedparser.parse(rss_url+'?mode=cat_pub&cat='+cat)
				feed = self.parent.cBTS.ListPublic(self.parent.cbt_login, self.parent.cbt_password, cat)
			if mode == 'priv':
				#~ feed = feedparser.parse(rss_url+'?mode=all_priv&user='+user)
				feed = self.parent.cBTS.ListPrivate(self.parent.cbt_login, self.parent.cbt_password, self.parent.userid, user)
		except:
			feed = ''
		
		return feed
		
	def PublicShowFeed(self, lst, data):
		try:
			lst.DeleteAllItems()
			id = 0
			for d in data:
				if self.chkPubSeeds.IsChecked():
					try:
						if int(d['seeds'])>0: self.PublicListAddTorrent(lst, d, id)
					except:
						pass
				else:
					self.PublicListAddTorrent(lst, d, id)
				print id
				id = id + 1
		except:
			pass
			
	def PublicListAddTorrent(self, lst, msg, id):

		try:
			name = urllib.unquote(msg['title'])
			if not name:
				name = urllib.unquote(msg['comment'])
		except:
			name = ''

		item_idx = lst.GetItemCount()
		lst.InsertStringItem(item_idx, msg['date'])
		lst.SetStringItem(item_idx, 1, name)
		lst.SetStringItem(item_idx, 2, str( self.size_format( int (msg['size']) ) ))
		lst.SetStringItem(item_idx, 3, msg['seeds'])
		lst.SetStringItem(item_idx, 4, msg['peers'])
		lst.SetStringItem(item_idx, 5, msg['downloaded'])
		lst.SetStringItem(item_idx, 6, msg['author'])
		
		lst.SetItemData(item_idx, int(id))

	def PublicChanged(self, event):
		try:
			sel = self.treePub.GetSelection()
			parent = self.treePub.GetItemParent(sel)
			
			pdata = self.treePub.GetPyData(parent)
			sdata = int(self.treePub.GetPyData(sel))
			
			if pdata == 'own':
				self.PublicShowFeed(self.listPub, self.cbtFeeds[sdata]['torrents'])
		except:
			pass
			
		
