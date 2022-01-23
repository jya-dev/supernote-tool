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

"""Classes for Suernote file format."""

import json

from . import exceptions


#### Constants

PAGE_HEIGHT = 1872
PAGE_WIDTH = 1404

ADDRESS_SIZE = 4
LENGTH_FIELD_SIZE = 4

KEY_SIGNATURE = '__signature__'
KEY_HEADER = '__header__'
KEY_FOOTER = '__footer__'
KEY_PAGES = '__pages__'
KEY_LAYERS = '__layers__'
KEY_KEYWORDS = '__keywords__'
KEY_TITLES = '__titles__'


class SupernoteMetadata:
    """Represents Supernote file structure."""
    def __init__(self):
        self.__note = {
            KEY_SIGNATURE: None,
            KEY_HEADER: None,
            KEY_FOOTER: None,
            KEY_PAGES: None,
        }

    @property
    def signature(self):
        return self.__note[KEY_SIGNATURE]

    @signature.setter
    def signature(self, value):
        self.__note[KEY_SIGNATURE] = value

    @property
    def header(self):
        return self.__note[KEY_HEADER]

    @header.setter
    def header(self, value):
        self.__note[KEY_HEADER] = value

    @property
    def footer(self):
        return self.__note[KEY_FOOTER]

    @footer.setter
    def footer(self, value):
        self.__note[KEY_FOOTER] = value

    @property
    def pages(self):
        return self.__note[KEY_PAGES]

    @pages.setter
    def pages(self, value):
        self.__note[KEY_PAGES] = value

    def get_total_pages(self):
        """Returns total page number.

        Returns
        -------
        int
            total page number
        """
        return len(self.__note[KEY_PAGES])

    def is_layer_supported(self, page_number):
        """Returns true if the page supports layer.

        Parameters
        ----------
        page_number : int
            page number to check

        Returns
        -------
        bool
            true if the page supports layer.
        """
        if page_number < 0 or page_number >= self.get_total_pages():
            raise IndexError(f'page number out of range: {page_number}')
        return self.__note[KEY_PAGES][page_number].get(KEY_LAYERS) is not None

    def to_json(self, indent=None):
        """Returns file structure as JSON format string.

        Parameters
        ----------
        indent : int
            optional indent level

        Returns
        -------
        str
            JSON format string
        """
        return json.dumps(self.__note, indent=indent, ensure_ascii=False)


class Notebook:
    def __init__(self, metadata):
        self.metadata = metadata
        self.signature = metadata.signature
        self.cover = Cover()
        self.keywords = []
        has_keywords = metadata.footer.get(KEY_KEYWORDS) is not None
        if has_keywords:
            for k in metadata.footer.get(KEY_KEYWORDS):
                self.keywords.append(Keyword(k))
        self.titles = []
        has_titles = metadata.footer.get(KEY_TITLES) is not None
        if has_titles:
            for t in metadata.footer.get(KEY_TITLES):
                self.titles.append(Title(t))
        self.pages = []
        total = metadata.get_total_pages()
        for i in range(total):
            self.pages.append(Page(metadata.pages[i]))

    def get_metadata(self):
        return self.metadata

    def get_signature(self):
        return self.signature

    def get_total_pages(self):
        return len(self.pages)

    def get_page(self, number):
        if number < 0 or number >= len(self.pages):
            raise IndexError(f'page number out of range: {number}')
        return self.pages[number]

    def get_cover(self):
        return self.cover

    def get_keywords(self):
        return self.keywords

    def get_titles(self):
        return self.titles

class Cover:
    def __init__(self):
        self.content = None

    def set_content(self, content):
        self.content = content

    def get_content(self):
        return self.content

class Keyword:
    def __init__(self, keyword_info):
        self.metadata = keyword_info
        self.content = None
        self.page_number = int(self.metadata['KEYWORDPAGE']) - 1
        self.position = int(self.metadata['KEYWORDRECT'].split(',')[1]) # get top value from "left,top,width,height"

    def set_content(self, content):
        self.content = content

    def get_content(self):
        return self.content

    def get_page_number(self):
        return self.page_number

    def get_position(self):
        return self.position

class Title:
    def __init__(self, title_info):
        self.metadata = title_info
        self.content = None
        self.page_number = 0
        self.position = int(self.metadata['TITLERECTORI'].split(',')[1]) # get top value from "left,top,width,height"

    def set_content(self, content):
        self.content = content

    def get_content(self):
        return self.content

    def set_page_number(self, page_number):
        self.page_number = page_number

    def get_page_number(self):
        return self.page_number

    def get_position(self):
        return self.position

class Page:
    def __init__(self, page_info):
        self.metadata = page_info
        self.content = None
        self.totalpath = None
        self.layers = []
        layer_supported = page_info.get(KEY_LAYERS) is not None
        if layer_supported:
            for i in range(5):
                self.layers.append(Layer(self.metadata[KEY_LAYERS][i]))

    def set_content(self, content):
        self.content = content

    def get_content(self):
        return self.content

    def is_layer_supported(self):
        """Returns True if this page supports layer.

        Returns
        -------
        bool
            True if this page supports layer.
        """
        return self.metadata.get(KEY_LAYERS) is not None

    def get_layers(self):
        return self.layers

    def get_layer(self, number):
        if number < 0 or number >= len(self.layers):
            raise IndexError(f'layer number out of range: {number}')
        return self.layers[number]

    def get_protocol(self):
        if self.is_layer_supported():
            # currently MAINLAYER is only supported
            protocol = self.get_layer(0).metadata.get('LAYERPROTOCOL')
        else:
            protocol = self.metadata.get('PROTOCOL')
        return protocol

    def get_style(self):
        return self.metadata.get('PAGESTYLE')

    def get_style_hash(self):
        hashcode = self.metadata.get('PAGESTYLEMD5')
        if hashcode == '0':
            return ''
        return hashcode

    def get_layer_info(self):
        info = self.metadata.get('LAYERINFO')
        if info is None or info == 'none':
            return None
        return info.replace('#', ':')

    def get_layer_order(self):
        seq = self.metadata.get('LAYERSEQ')
        if seq is None:
            return []
        order = seq.split(',')
        return order

    def set_totalpath(self, totalpath):
        self.totalpath = totalpath

    def get_totalpath(self):
        return self.totalpath

class Layer:
    def __init__(self, layer_info):
        self.metadata = layer_info
        self.content = None

    def set_content(self, content):
        self.content = content

    def get_content(self):
        return self.content

    def get_name(self):
        return self.metadata.get('LAYERNAME')

    def get_protocol(self):
        return self.metadata.get('LAYERPROTOCOL')
