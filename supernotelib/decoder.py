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

import base64
import json
import numpy as np
import png
import queue
import zlib

from . import color
from . import exceptions


class BaseDecoder:
    """Abstract decoder class."""
    def decode(self, data, palette=None, all_blank=False, horizontal=False):
        raise NotImplementedError('subclasses must implement decode method')


class FlateDecoder(BaseDecoder):
    """Decoder for SN_ASA_COMPRESS protocol."""
    COLORCODE_BLACK = 0x0000
    COLORCODE_BACKGROUND = 0xffff
    COLORCODE_DARK_GRAY = 0x2104
    COLORCODE_GRAY = 0xe1e2

    INTERNAL_PAGE_HEIGHT = 1888
    INTERNAL_PAGE_WIDTH = 1404

    def decode(self, data, page_width, page_height, palette=None, all_blank=False, horizontal=False):
        """Uncompress bitmap data.

        Parameters
        ----------
        data : bytes
            compressed bitmap data
        page_width : int
            page width
        page_height : int
            page height

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

        # change colors
        if palette is None:
            palette = color.DEFAULT_COLORPALETTE
        if palette.mode == color.MODE_RGB:
            bit_per_pixel = 32
            bitmap = bitmap.astype('>u4')
            alpha = 0xff
            bitmap[bitmap == self.COLORCODE_BLACK] = (palette.black << 8) | alpha
            bitmap[bitmap == self.COLORCODE_DARK_GRAY] = (palette.darkgray << 8) | alpha
            bitmap[bitmap == self.COLORCODE_GRAY] = (palette.gray << 8) | alpha
            bitmap[bitmap == self.COLORCODE_BACKGROUND] = (palette.white << 8) | alpha
        else:
            bit_per_pixel = 8
            bitmap[bitmap == self.COLORCODE_BLACK] = palette.black
            bitmap[bitmap == self.COLORCODE_DARK_GRAY] = palette.darkgray
            bitmap[bitmap == self.COLORCODE_GRAY] = palette.gray
            bitmap[bitmap == self.COLORCODE_BACKGROUND] = palette.white
            bitmap = bitmap.astype(np.uint8)
        return bitmap.tobytes(), (page_width, page_height), bit_per_pixel


class RattaRleDecoder(BaseDecoder):
    """Decoder for RATTA_RLE protocol."""
    COLORCODE_BLACK = 0x61
    COLORCODE_BACKGROUND = 0x62
    COLORCODE_DARK_GRAY = 0x63
    COLORCODE_GRAY = 0x64
    COLORCODE_WHITE = 0x65
    COLORCODE_MARKER_BLACK = 0x66
    COLORCODE_MARKER_DARK_GRAY = 0x67
    COLORCODE_MARKER_GRAY = 0x68

    SPECIAL_LENGTH_MARKER = 0xff
    SPECIAL_LENGTH = 0x4000
    SPECIAL_LENGTH_FOR_BLANK = 0x400

    def decode(self, data, page_width, page_height, palette=None, all_blank=False, horizontal=False):
        """Uncompress bitmap data.

        Parameters
        ----------
        data : bytes
            compressed bitmap data
        page_width : int
            page width
        page_height : int
            page height

        Returns
        -------
        bytes
            uncompressed bitmap data
        tuple(int, int)
            bitmap size (width, height)
        int
            bit per pixel
        """
        if palette is None:
            palette = color.DEFAULT_COLORPALETTE

        if palette.mode == color.MODE_RGB:
            bit_per_pixel = 24
        else:
            bit_per_pixel = 8

        colormap = self._create_colormap(palette)

        if horizontal:
            page_height, page_width = (page_width, page_height) # swap width and height

        expected_length = page_height * page_width * int(bit_per_pixel / 8)

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
                    uncompressed += self._create_color_bytearray(palette.mode, colormap, colorcode, length)
        except StopIteration:
            if len(holder) > 0:
                (colorcode, length) = holder
                length = self._adjust_tail_length(length, len(uncompressed), expected_length)
                if length > 0:
                    uncompressed += self._create_color_bytearray(palette.mode, colormap, colorcode, length)

        if len(uncompressed) != expected_length:
            raise exceptions.DecoderException(f'uncompressed bitmap length = {len(uncompressed)}, expected = {expected_length}')

        return bytes(uncompressed), (page_width, page_height), bit_per_pixel

    def _create_colormap(self, palette):
        colormap = {
            self.COLORCODE_BLACK: palette.black,
            self.COLORCODE_BACKGROUND: palette.transparent,
            self.COLORCODE_DARK_GRAY: palette.darkgray,
            self.COLORCODE_GRAY: palette.gray,
            self.COLORCODE_WHITE: palette.white,
            self.COLORCODE_MARKER_BLACK: palette.black,
            self.COLORCODE_MARKER_DARK_GRAY: palette.darkgray,
            self.COLORCODE_MARKER_GRAY: palette.gray,
        }
        return colormap

    def _create_color_bytearray(self, mode, colormap, color_code, length):
        if mode == color.MODE_RGB:
            c = colormap.get(color_code)
            r, g, b = color.get_rgb(c)
            return bytearray((r, g, b,)) * length
        else:
            c = colormap.get(color_code)
            return bytearray((c,)) * length

    def _adjust_tail_length(self, tail_length, current_length, total_length):
        gap = total_length - current_length
        for i in reversed(range(8)):
            l = ((tail_length & 0x7f) + 1) << i
            if l <= gap:
                return l
        return 0


class RattaRleX2Decoder(RattaRleDecoder):
    """Decoder for RATTA_RLE protocol of X2-series."""
    # 4 color codes were changed from X-series
    COLORCODE_DARK_GRAY = 0x9D
    COLORCODE_GRAY = 0xC9
    COLORCODE_MARKER_DARK_GRAY = 0x9E
    COLORCODE_MARKER_GRAY = 0xCA
    # color codes for X-series compatibility
    COLORCODE_DARK_GRAY_COMPAT = 0x63
    COLORCODE_GRAY_COMPAT = 0x64

    def _create_colormap(self, palette):
        colormap = {
            self.COLORCODE_BLACK: palette.black,
            self.COLORCODE_BACKGROUND: palette.transparent,
            self.COLORCODE_DARK_GRAY: palette.darkgray,
            self.COLORCODE_GRAY: palette.gray,
            self.COLORCODE_WHITE: palette.white,
            self.COLORCODE_MARKER_BLACK: palette.black,
            self.COLORCODE_MARKER_DARK_GRAY: palette.darkgray,
            self.COLORCODE_MARKER_GRAY: palette.gray,
            self.COLORCODE_DARK_GRAY_COMPAT: palette.darkgray_compat,
            self.COLORCODE_GRAY_COMPAT: palette.gray_compat,
        }
        return colormap

    def _create_color_bytearray(self, mode, colormap, color_code, length):
        if mode == color.MODE_RGB:
            c = colormap.get(color_code)
            if c is not None:
                r, g, b = color.get_rgb(c)
            else: # if the color_code is not included in colormap, use the value as color directly
                r, g, b = (color_code, color_code, color_code)
            return bytearray((r, g, b,)) * length
        else:
            c = colormap.get(color_code)
            if c is None:
                c = color_code
            return bytearray((c,)) * length


class PngDecoder(BaseDecoder):
    """Decoder for PNG."""

    def decode(self, data, page_width, page_height, palette=None, all_blank=False, horizontal=False):
        """Uncompress bitmap data.

        Parameters
        ----------
        data : bytes
            png data
        page_width : int
            page width
        page_height : int
            page height

        Returns
        -------
        bytes
            uncompressed bitmap data
        tuple(int, int)
            bitmap size (width, height)
        int
            bit per pixel
        """
        r = png.Reader(bytes=data)
        (width, height, rows, info) = r.asRGBA()
        if width != page_width or height != page_height:
            raise exceptions.DecoderException(f'invalid size = ({width}, {height}), expected = ({page_width}, {page_height})')
        values = [x for row in rows for x in row] # flatten rows
        depth = info['bitdepth']
        greyscale = info['greyscale']
        alpha = info['alpha']
        ch = 1 if greyscale else 3
        if alpha:
            ch = ch + 1
        bit_per_pixel = depth * ch
        return bytes(values), (page_width, page_height), bit_per_pixel


class TextDecoder(BaseDecoder):
    """Decoder for text."""

    def decode(self, data, palette=None, all_blank=False, horizontal=False):
        """Extract text from a realtime recognition data with spatial ordering.

        Parameters
        ----------
        data : bytes
            recognition text data (base64 encoded)

        Returns
        -------
        list of dict
            list of recognized text elements with spatial information.
            Each element is a dict with 'label' (str) and 'y' (int) keys.
            Returns None if no data available.
        """
        if data is None:
            return None
        recogn_json = base64.b64decode(data).decode('utf-8')
        recogn = json.loads(recogn_json)
        elements = recogn.get('elements')

        # Extract text elements with their y-position for spatial ordering
        result = []
        for elem in filter(lambda e: e.get('type') == 'Text', elements):
            label = elem.get('label', '')
            if not label:
                continue

            # Get y-position from first word's bounding box
            y = 0
            words = elem.get('words', [])
            if words:
                for word in words:
                    bbox = word.get('bounding-box')
                    if bbox:
                        y = bbox.get('y', 0)
                        break

            result.append({'label': label, 'y': y})

        return result if result else None
