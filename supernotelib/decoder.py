# Copyright (c) 2020 jya
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Decoder classes."""

import numpy as np
import queue
import zlib

from . import exceptions
from . import fileformat


class BaseDecoder:
    """Abstract decoder class."""
    def decode(self, data):
        raise NotImplementedError('subclasses must implement decode method')


class FlateDecoder(BaseDecoder):
    """Decoder for SN_ASA_COMPRESS protocol."""
    INTERNAL_PAGE_HEIGHT = 1888
    INTERNAL_PAGE_WIDTH = 1404
    BIT_PER_PIXEL = 16

    def decode(self, data):
        """Uncompress bitmap data.

        Parameters
        ----------
        data : bytes
            compressed bitmap data

        Returns
        -------
        bytes
            uncompressed bitmap data
        tuple(int, int)
            bitmap size (width, height)
        int
            bit per pixel
        """
        uncompressed = zlib.decompress(data)
        bitmap = np.frombuffer(uncompressed, dtype=np.uint16)
        bitmap = np.reshape(bitmap, (self.INTERNAL_PAGE_WIDTH, self.INTERNAL_PAGE_HEIGHT))
        bitmap = np.rot90(bitmap, -1) # rotate 90 degrees clockwise
        bitmap = np.delete(bitmap, slice(-16, None), axis=0) # delete bottom 16 lines
        return bitmap.tobytes(), (fileformat.PAGE_WIDTH, fileformat.PAGE_HEIGHT), self.BIT_PER_PIXEL


class RattaRleDecoder(BaseDecoder):
    """Decoder for RATTA_RLE protocol."""
    BIT_PER_PIXEL = 8

    COLOR_BLACK = 0x00
    COLOR_DARK_GRAY = 0x9d
    COLOR_GRAY = 0xc9
    COLOR_WHITE = 0xfe

    COLORCODE_BLACK = 0x61
    COLORCODE_BACKGROUND = 0x62
    COLORCODE_DARK_GRAY = 0x63
    COLORCODE_GRAY = 0x64
    COLORCODE_WHITE = 0x65

    colormap = {
        COLORCODE_BLACK: COLOR_BLACK,
        COLORCODE_BACKGROUND: COLOR_WHITE,
        COLORCODE_DARK_GRAY: COLOR_DARK_GRAY,
        COLORCODE_GRAY: COLOR_GRAY,
        COLORCODE_WHITE: COLOR_WHITE,
    }

    SPECIAL_LENGTH_MARKER = 0xff
    SPECIAL_LENGTH = 0x4000
    SPECIAL_LENGTH_FOR_BLANK = 0x400

    def decode(self, data, all_blank=False):
        """Uncompress bitmap data.

        Parameters
        ----------
        data : bytes
            compressed bitmap data

        Returns
        -------
        bytes
            uncompressed bitmap data
        tuple(int, int)
            bitmap size (width, height)
        int
            bit per pixel
        """
        uncompressed = bytearray()
        bin = iter(data)
        try:
            holder = ()
            waiting = queue.Queue()
            while True:
                colorcode = next(bin)
                length = next(bin)
                data_pushed = False

                if len(holder) > 0:
                    (prev_colorcode, prev_length) = holder
                    holder = ()
                    if colorcode == prev_colorcode:
                        length = 1 + length + (((prev_length & 0x7f) + 1) << 7)
                        waiting.put((colorcode, length))
                        data_pushed = True
                    else:
                        prev_length = ((prev_length & 0x7f) + 1) << 7
                        waiting.put((prev_colorcode, prev_length))

                if not data_pushed:
                    if length == self.SPECIAL_LENGTH_MARKER:
                        if all_blank:
                            length = self.SPECIAL_LENGTH_FOR_BLANK
                        else:
                            length = self.SPECIAL_LENGTH
                        waiting.put((colorcode, length))
                        data_pushed = True
                    elif length & 0x80 != 0:
                        holder = (colorcode, length)
                        # holded data are processed at next loop
                    else:
                        length += 1
                        waiting.put((colorcode, length))
                        data_pushed = True

                while not waiting.empty():
                    (colorcode, length) = waiting.get()
                    color = self.colormap[colorcode]
                    uncompressed += bytearray((color,)) * length
        except StopIteration:
           if len(holder) > 0:
                (colorcode, length) = holder
                length = ((length & 0x7f) + 1) << 3
                color = self.colormap[colorcode]
                uncompressed += bytearray((color,)) * length

        expected_length = fileformat.PAGE_HEIGHT * fileformat.PAGE_WIDTH
        if len(uncompressed) != expected_length:
            raise exceptions.DecoderException(f'uncompressed bitmap length = {len(uncompressed)}, expected = {expected_length}')

        return bytes(uncompressed), (fileformat.PAGE_WIDTH, fileformat.PAGE_HEIGHT), self.BIT_PER_PIXEL
