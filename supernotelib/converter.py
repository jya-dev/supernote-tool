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

"""Converter classes."""

import json
import potrace
import svgwrite

from PIL import Image

from . import color
from . import decoder as Decoder
from . import exceptions
from . import fileformat


class ImageConverter:
    def __init__(self, notebook, palette=None):
        self.note = notebook
        self.palette = palette

    def convert(self, page_number, ignore_background=False):
        """Returns an image of the given page.

        Parameters
        ----------
        page_number : int
            page number to convert

        Returns
        -------
        PIL.Image.Image
            an image object
        """
        page = self.note.get_page(page_number)
        if page.is_layer_supported():
            return self._convert_layered_page(page, self.palette, ignore_background)
        else:
            return self._convert_nonlayered_page(page, self.palette, ignore_background)

    def _convert_nonlayered_page(self, page, palette=None, ignore_background=False):
        binary = page.get_content()
        decoder = self.find_decoder(page)
        return self._create_image_from_decoder(decoder, binary,palette=palette)

    def _convert_layered_page(self, page, palette=None, ignore_background=False):
        imgs = {}
        layers = page.get_layers()
        for layer in layers:
            layer_name = layer.get_name()
            binary = layer.get_content()
            if binary is None:
                imgs[layer_name] = None
                continue
            decoder = self.find_decoder(layer)
            page_style = page.get_style()
            all_blank = (layer_name == 'BGLAYER' and page_style is not None and page_style == 'style_white')
            custom_bg = (layer_name == 'BGLAYER' and page_style is not None and page_style.startswith('user_'))
            if custom_bg:
                decoder = Decoder.PngDecoder()
            img = self._create_image_from_decoder(decoder, binary, palette=palette, blank_hint=all_blank)
            imgs[layer_name] = img
        # flatten background and main layer
        img_main = imgs['MAINLAYER']
        if ignore_background:
            img = img_main
        else:
            img_bg = imgs['BGLAYER']
            img = self._flatten_layers(img_main, img_bg)
        # flatten layer1, layer2, layer3 if any
        visibility = self._get_additional_layers_visibility(page)
        layer_order = page.get_layer_order()
        layer_order.remove('MAINLAYER')
        for name in reversed(layer_order):
            is_visible = visibility.get(name)
            if not is_visible:
                continue
            img_layer = imgs.get(name)
            if img_layer is not None:
                img = self._flatten_layers(img_layer, img)
        return img

    def _flatten_layers(self, fg, bg):
        mask = fg.copy().convert('L')
        mask = mask.point(lambda x: 0 if x == color.TRANSPARENT else 1, mode='1')
        return Image.composite(fg, bg, mask)

    def _create_image_from_decoder(self, decoder, binary, palette=None, blank_hint=False):
        bitmap, size, bpp = decoder.decode(binary, palette=palette, all_blank=blank_hint)
        if bpp == 32:
            img = Image.frombytes('RGBA', size, bitmap)
        elif bpp == 24:
            img = Image.frombytes('RGB', size, bitmap)
        elif bpp == 16:
            img = Image.frombytes('I;16', size, bitmap)
        else:
            img = Image.frombytes('L', size, bitmap)
        return img

    def _get_additional_layers_visibility(self, page):
        visibility = {}
        info = page.get_layer_info()
        if info is None:
            return visibility
        info_array = json.loads(info)
        for layer in info_array:
            is_bg_layer = layer.get('isBackgroundLayer')
            if is_bg_layer:
                continue
            layer_id = layer.get('layerId')
            is_visible = layer.get('isVisible')
            visibility['LAYER' + str(layer_id)] = is_visible
        return visibility

    def find_decoder(self, page):
        """Returns a proper decoder for the given page.

        Parameters
        ----------
        page : Page
            page object

        Returns
        -------
        subclass of BaseDecoder
            a decoder
        """
        protocol = page.get_protocol()
        if protocol == 'SN_ASA_COMPRESS':
            return Decoder.FlateDecoder()
        elif protocol == 'RATTA_RLE':
            return Decoder.RattaRleDecoder()
        else:
            raise exceptions.UnknownDecodeProtocol(f'unknown decode protocol: {protocol}')


class SvgConverter:
    def __init__(self, notebook, palette=None):
        self.palette = palette if palette is not None else color.DEFAULT_COLORPALETTE
        self.image_converter = ImageConverter(notebook, palette=color.DEFAULT_COLORPALETTE) # use default pallete

    def convert(self, page_number):
        """Returns SVG string of the given page.

        Parameters
        ----------
        page_number : int
            page number to convert

        Returns
        -------
        string
            an SVG string
        """
        dwg = svgwrite.Drawing('dummy.svg', profile='full', size=(fileformat.PAGE_WIDTH, fileformat.PAGE_HEIGHT))

        img = self.image_converter.convert(page_number, ignore_background=True)

        def generate_color_mask(img, c):
            mask = img.copy().convert('L')
            return mask.point(lambda x: 0 if x == c else 1, mode='1')

        default_palette = color.DEFAULT_COLORPALETTE
        default_color_list = [default_palette.black, default_palette.darkgray, default_palette.gray, default_palette.white]
        user_color_list = [self.palette.black, self.palette.darkgray, self.palette.gray, self.palette.white]
        for i, c in enumerate(default_color_list):
            user_color = user_color_list[i]
            mask = generate_color_mask(img, c)
            # create a bitmap from the array
            bmp = potrace.Bitmap(mask)
            # trace the bitmap to a path
            path = bmp.trace()
            # iterate over path curves
            if len(path) > 0:
                svgpath = dwg.path(fill=color.web_string(user_color, mode=self.palette.mode))
                for curve in path:
                    start = curve.start_point
                    svgpath.push("M", start.x, start.y)
                    for segment in curve:
                        end = segment.end_point
                        if segment.is_corner:
                            c = segment.c
                            svgpath.push("L", c.x, c.y)
                            svgpath.push("L", end.x, end.y)
                        else:
                            c1 = segment.c1
                            c2 = segment.c2
                            svgpath.push("C", c1.x, c1.y, c2.x, c2.y, end.x, end.y)
                    svgpath.push("Z")
                dwg.add(svgpath)
        return dwg.tostring()
