#
# This file is part of the PyRDP project.
# Copyright (C) 2018-2020 GoSecure Inc.
# Licensed under the GPLv3 or later.
#

from PySide2.QtCore import QObject
from PySide2.QtGui import QTextCursor
from PySide2.QtWidgets import QTextEdit

from pyrdp.pdu import BitmapUpdateData, PlayerPDU
from pyrdp.enum import BitmapFlags
from pyrdp.ui import QRemoteDesktop, RDPBitmapToQtImage
from pyrdp.player.RenderingEventHandler import RenderingEventHandler
from pyrdp.logging import log


class PlayerEventHandler(QObject, RenderingEventHandler):
    """
    Qt Rendering Sink.

    This class handles the video pipeline by rendering to a Qt widget.
    """

    def __init__(self, viewer: QRemoteDesktop, text: QTextEdit):
        QObject.__init__(self)
        RenderingEventHandler.__init__(self)

        self.viewer = viewer
        self.text = text

    def onPDUReceived(self, pdu: PlayerPDU, isMainThread=False):
        # Ensure we are on the main thread.
        if not isMainThread:
            self.viewer.mainThreadHook.emit(lambda: self.onPDUReceived(pdu, True))
            return

        log.debug("Received %(pdu)s", {"pdu": pdu})

        # Call the parent PDU Received method.
        super().onPDUReceived(pdu)

    def onDimensions(self, w, h):
        self.viewer.resize(w, h)

    def onMousePosition(self, x: int, y: int):
        self.viewer.setMousePosition(x, y)

    def onBitmap(self, bitmapData: BitmapUpdateData):
        image = RDPBitmapToQtImage(
            bitmapData.width,
            bitmapData.heigth,
            bitmapData.bitsPerPixel,
            bitmapData.flags & BitmapFlags.BITMAP_COMPRESSION != 0,
            bitmapData.bitmapData
        )

        self.viewer.notifyImage(
            bitmapData.destLeft,
            bitmapData.destTop,
            image,
            bitmapData.destRight - bitmapData.destLeft + 1,
            bitmapData.destBottom - bitmapData.destTop + 1)

    def writeText(self, text: str):
        self.text.moveCursor(QTextCursor.End)
        self.text.insertPlainText(text.rstrip("\x00"))

    def writeSeparator(self):
        self.writeText("\n--------------------\n")
