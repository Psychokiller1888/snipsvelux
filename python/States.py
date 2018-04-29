#!/usr/bin/python
# -*- coding: utf-8 -*-

from enum import Enum

class State(Enum):
	WAITING_REPLY = 0
	REGISTERED = 1
	REFUSED = 2
	NEW = 3
	BOOTING = 4
	BUSY = 5
	READY = 6