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

from PIL import Image

from . import color
from . import decoder
from . import exceptions
from . import fileformat


class ImageConverter:
    def __init__(self, notebook, palette=None):
        self.note = notebook
        self.palette = palette

    def convert(self, page_number):
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
            return self._convert_layered_page(page, self.palette)
        else:
            return self._convert_nonlayered_page(page, self.palette)

    def _convert_nonlayered_page(self, page, palette=None):
        binary = page.get_content()
        decoder = self.find_decoder(page)
        return self._create_image_from_decoder(decoder, binary,palette=palette)

    def _convert_layered_page(self, page, palette=None):
        imgs = {}
        layers = page.get_layers()
        for layer in layers:
            layer_name = layer.get_name()
            binary = layer.get_content()
            if binary is None:
                imgs[layer_name] = None
                continue
            decoder = self.find_decoder(layer)
            all_blank = (layer_name == 'BGLAYER' and page.get_style() == 'style_white')
            img = self._create_image_from_decoder(decoder, binary, palette=palette, blank_hint=all_blank)
            imgs[layer_name] = img
        # flatten background and main layer
        img_main = imgs['MAINLAYER']
        img_bg = imgs['BGLAYER']
        img = self._flatten_layers(img_main, img_bg)
        # flatten layer1, layer2, layer3 if any
        visibility = self._get_additional_layers_visibility(page)
        for name in ['LAYER1', 'LAYER2', 'LAYER3']:
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
            return decoder.FlateDecoder()
        elif protocol == 'RATTA_RLE':
            return decoder.RattaRleDecoder()
        else:
            raise exceptions.UnknownDecodeProtocol(f'unknown decode protocol: {protocol}')
