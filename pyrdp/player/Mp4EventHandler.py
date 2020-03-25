#
# This file is part of the PyRDP project.
# Copyright (C) 2020 GoSecure Inc.
# Licensed under the GPLv3 or later.
#

from pyrdp.enum import BitmapFlags
from pyrdp.pdu import BitmapUpdateData
from pyrdp.player.RenderingEventHandler import RenderingEventHandler
from pyrdp.ui import RDPBitmapToQtImage

import av
from PIL import ImageQt
from PySide2.QtGui import QImage, QPainter


FPS = 24


class Mp4EventHandler(RenderingEventHandler):

    def __init__(self, filename: str):
        """Construct an event handler that outputs to an Mp4 file."""

        super().__init__()
        self.mp4 = f = av.open(filename, 'w')
        self.stream = f.add_stream('h264', rate=FPS)
        self.stream.pix_fmt = 'yuv420p'
        self.scale = False

        self.surface = None
        self.paint = None

        # Keep track of mouse position to draw the pointer.
        self.mouse = (0, 0)

    def cleanup(self):
        # FIXME: Need to flush here to avoid hanging.
        self.mp4.close()

    def onDimensions(self, w: int, h: int):
        # TODO: Change this once drawing orders are merged.
        self.surface = QImage(w, h, QImage.Format_RGB888)

        if w % 2 != 0:
            self.scale = True
            w += 1
        if h % 2 != 0:
            self.scale = True
            h += 1

        self.stream.width = w
        self.stream.height = h

    def onBeginRender(self):
        if not self.paint:
            self.paint = QPainter(self.surface)
        else:
            self.paint.begin(self.surface)

    def onBitmap(self, bmp: BitmapUpdateData):
        x = bmp.destLeft
        y = bmp.destTop
        w = bmp.width
        h = bmp.heigth

        img = RDPBitmapToQtImage(w, h, bmp.bitsPerPixel,
                                 bmp.flags & BitmapFlags.BITMAP_COMPRESSION != 0,
                                 bmp.bitmapData)
        self.paint.drawImage(x, y, img, 0, 0, w, h)

    def onFinishRender(self):
        self.paint.end()
        # Write to the mp4 container.
        w = self.stream.width
        h = self.stream.height

        surface = self.surface.scaled(w, h) if self.scale else self.surface
        frame = av.VideoFrame.from_image(ImageQt.fromqimage(surface))

        for packet in self.stream.encode(frame):
            self.mp4.mux(packet)
            # TODO: Add progress callback.
