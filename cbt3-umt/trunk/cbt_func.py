# -*- coding: cp1250 -*-
#-----------------------------------------------------------------------------
# Name: 	   cbt_func.py
# Author:	   warp / visualvinyl
# RCS-ID:	   $Id: cbt_func.py 47 2004-08-20 23:18:20Z warp $
#-----------------------------------------------------------------------------

import wx

dummyapp = wx.PySimpleApp()
defFontB = wx.Font(8, wx.SWISS, wx.NORMAL, wx.BOLD, face="Tahoma")
defFontN = wx.Font(8, wx.SWISS, wx.NORMAL, wx.NORMAL, face="Tahoma")

def InsertColumns(lst, cols):
	info = wx.ListItem()
	info.m_mask = wx.LIST_MASK_TEXT | wx.LIST_MASK_FORMAT
	info.m_format = 0

	for c in cols:
		info.m_text = c[1]
		info.m_format = c[2]
		lst.InsertColumnInfo(c[0], info)
		lst.SetColumnWidth(c[0], c[3])

def size_format(s):
	if (s < 1024):
		r = str(s) + ' b'
	elif (s < 1048576):
		r = str(int(s/1024)) + ' kb'
	elif (s < 1073741824L):
		r = str(int(s/1048576)) + ' mb'
	elif (s < 1099511627776L):
		r = str(int((s/1073741824.0)*100.0)/100.0) + ' gb'
	else:
		r = str(int((s/1099511627776.0)*100.0)/100.0) + ' tb'
	return(r) 
