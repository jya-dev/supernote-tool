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

from PIL import Image

from . import decoder
from . import exceptions
from . import fileformat


class ImageConverter:
    def __init__(self, notebook):
        self.note = notebook

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
            imgs = []
            layers = page.get_layers()
            for l in layers:
                binary = l.get_content()
                if binary is None:
                    imgs.append(None)
                    continue
                decoder = self.find_decoder(l)
                all_blank = (l.get_name() == 'BGLAYER' and page.get_style() == 'style_white')
                bitmap, size, bpp = decoder.decode(binary, all_blank)
                if bpp == 16:
                    img = Image.frombytes('I;16', size, bitmap)
                else:
                    img = Image.frombytes('L', size, bitmap)
                imgs.append(img)
            # flatten background and main layer
            img_bg = imgs[4]
            img_main = imgs[0]
            mask = img_main.copy().convert('L')
            mask = mask.point(lambda x: 0 if x == 0xff else 1, mode='1')
            img = Image.composite(img_main, img_bg, mask)
            for i in range(3):  # flatten layer1, layer2, layer3 if any
                img_layer = imgs[i + 1]
                if img_layer is not None:
                    mask = img_layer.copy().convert('L')
                    mask = mask.point(lambda x: 0 if x == 0xff else 1, mode='1')
                    img = Image.composite(img_layer, img, mask)
            return img
        else:
            binary = page.get_content()
            decoder = self.find_decoder(page)
            bitmap, size, bpp = decoder.decode(binary)
            if bpp == 16:
                img = Image.frombytes('I;16', size, bitmap)
            else:
                img = Image.frombytes('L', size, bitmap)
            return img

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
