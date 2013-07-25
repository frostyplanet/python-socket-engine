#!/usr/bin/env python
# coding:utf-8

from os.path import dirname, abspath 
PREFIX = dirname(abspath(__file__))
import sys  
if PREFIX not in sys.path:
    sys.path.append(PREFIX)


# vim: tabstop=4 expandtab shiftwidth=4 softtabstop=4 :
