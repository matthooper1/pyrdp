#
# This file is part of the PyRDP project.
# Copyright (C) 2020 GoSecure Inc.
# Licensed under the GPLv3 or later.
#

from pyrdp.enum import SlowPathUpdateType
from pyrdp.parser import BitmapParser, FastPathOutputParser
from pyrdp.pdu import FastPathBitmapEvent, FastPathOutputEvent, UpdatePDU
from pyrdp.player.BaseEventHandler import BaseEventHandler


class RenderingEventHandler(BaseEventHandler):
    """Abstract class for video rendering sinks."""

    def __init__(self):
        BaseEventHandler.__init__(self)
        self._fastPath = FastPathOutputParser()
        self._bitmap = BitmapParser()

    def onBitmap(self, bmp):
        raise Exception('`onBitmap` must be implemented.')

    # Generic Video Parsing Routines.
    def onFastPathOutput(self, event: FastPathOutputEvent):
        print(event)
        if isinstance(event, FastPathBitmapEvent):
            parsed = self._fastPath.parseBitmapEvent(event)
            for bmp in parsed.bitmapUpdateData:
                self.onBitmap(bmp)

    def onSlowPathUpdate(self, pdu: UpdatePDU):
        if pdu.updateDtype == SlowPathUpdateType.SLOWPATH_UPDATETYPE_BITMAP:
            updates = self._bitmap.parseBitmapUpdateData(pdu.updateData)
            for bmp in updates:
                self.onBitmap(bmp)
