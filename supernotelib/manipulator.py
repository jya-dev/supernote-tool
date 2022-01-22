# Copyright (c) 2021 jya
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

"""Note manipulator classes."""

import os
import re

from . import fileformat
from . import utils

class NotebookBuilder:
    def __init__(self, offset=0):
        self.total_size = offset
        self.toc = {}
        self.blocks = []

    def get_total_size(self):
        return self.total_size

    def get_block_address(self, label):
        if type(self.toc.get(label)) == list:
            address = self.toc.get(label)[0] # use first one
        else:
            address = self.toc.get(label)
        return address if address is not None else 0

    def get_duplicate_block_address_list(self, label):
        if type(self.toc.get(label)) == list:
            return self.toc.get(label)
        else:
            return [self.toc.get(label)]

    def get_labels(self):
        return self.toc.keys()

    def append(self, label, block, skip_block_size=False, allow_duplicate=False):
        if not label or block is None:
            raise ValueError('empty label or block is not allowed')
        label_duplicated = label in self.toc
        if label_duplicated and not allow_duplicate:
            return False
        block_size = len(block)
        if not skip_block_size:
            self.blocks.append(block_size.to_bytes(fileformat.LENGTH_FIELD_SIZE, 'little'))
        self.blocks.append(block)
        if label_duplicated:
            if type(self.toc[label]) == list:
                self.toc[label].append(self.total_size)
            else:
                self.toc[label] = [self.toc[label], self.total_size]
        else:
            self.toc.setdefault(label, self.total_size)
        self.total_size += block_size
        if not skip_block_size:
            self.total_size += fileformat.LENGTH_FIELD_SIZE
        return True

    def build(self):
        return b''.join(self.blocks)

    def dump(self):
        print('# NotebookBuilder Dump:')
        print(f'# total_size = {self.total_size}')
        print(f'# toc = {self.toc}')


def reconstruct(notebook):
    """Reconstruct a notebook for debug."""
    expected_signature = 'noteSN_FILE_VER_20210010'
    metadata = notebook.get_metadata()
    if metadata.signature != expected_signature:
        raise ValueError(f'Only latest file format version is supported ({metadata.signature} != {expected_signature})')

    builder = NotebookBuilder()
    _pack_signature(builder, notebook)
    _pack_header(builder, notebook)
    _pack_cover(builder, notebook)
    _pack_keywords(builder, notebook)
    _pack_titles(builder, notebook)
    _pack_backgrounds(builder, notebook)
    _pack_pages(builder, notebook)
    _pack_footer(builder)
    _pack_footer_address(builder)
    return builder.build()

def merge(notebook1, notebook2):
    """Merge multiple notebooks to one."""
    # TODO: support non-X series
    metadata1 = notebook1.get_metadata()
    metadata2 = notebook2.get_metadata()
    expected_signature = 'noteSN_FILE_VER_20210010'
    if metadata1.signature != expected_signature:
        raise ValueError(f'Only latest file format version is supported ({metadata1.signature} != {expected_signature})')
    if metadata1.signature != metadata2.signature:
        raise ValueError(f'File signature must be same between merging files ({metadata1.signature} != {metadata2.signature})')
    # check header properties are same to avoid generating a corrupted note file
    _verify_header_property('FILE_TYPE', metadata1, metadata2)
    _verify_header_property('APPLY_EQUIPMENT', metadata1, metadata2)
    _verify_header_property('DEVICE_DPI', metadata1, metadata2)
    _verify_header_property('SOFT_DPI', metadata1, metadata2)
    _verify_header_property('FILE_PARSE_TYPE', metadata1, metadata2)
    _verify_header_property('RATTA_ETMD', metadata1, metadata2)
    _verify_header_property('APP_VERSION', metadata1, metadata2)

    builder = NotebookBuilder()
    _pack_signature(builder, notebook1)
    _pack_header(builder, notebook1)
    _pack_cover(builder, notebook1)
    _pack_keywords(builder, notebook1)
    _pack_keywords(builder, notebook2, offset=notebook1.get_total_pages())
    _pack_titles(builder, notebook1)
    _pack_titles(builder, notebook2, offset=notebook1.get_total_pages())
    _pack_backgrounds(builder, notebook1)
    _pack_backgrounds(builder, notebook2)
    _pack_pages(builder, notebook1)
    _pack_pages(builder, notebook2, offset=notebook1.get_total_pages())
    _pack_footer(builder)
    _pack_footer_address(builder)
    return builder.build()

def _pack_signature(builder, notebook):
    metadata = notebook.get_metadata()
    builder.append('__signature__', metadata.signature.encode('ascii'), skip_block_size=True)

def _pack_header(builder, notebook):
    metadata = notebook.get_metadata()
    header_block = _construct_metadata_block(metadata.header)
    builder.append('__header__', header_block)

def _pack_cover(builder, notebook):
    metadata = notebook.get_metadata()
    cover_block = notebook.get_cover().get_content()
    if cover_block is not None:
        builder.append('COVER_1', cover_block)

def _pack_keywords(builder, notebook, offset=0):
    for keyword in notebook.get_keywords():
        page_number = keyword.get_page_number() + 1 + offset
        if page_number > 9999:
            # the number of digits is limited to 4, so we ignore this keyword
            continue
        position = keyword.get_position()
        id = f'{page_number:04d}{position:04d}'
        content = keyword.get_content()
        if content is not None:
            builder.append(f'KEYWORD_{id}', content, allow_duplicate=True)
            keyword_metadata = keyword.metadata
            keyword_metadata['KEYWORDPAGE'] = page_number
            address_list = builder.get_duplicate_block_address_list(f'KEYWORD_{id}')
            if len(address_list) == 1:
                keyword_metadata['KEYWORDSITE'] = str(address_list[0])
            else:
                keyword_metadata['KEYWORDSITE'] = str(address_list[-1]) # use last address
            keyword_metadata_block = _construct_metadata_block(keyword_metadata)
            builder.append(f'KEYWORD_{id}/metadata', keyword_metadata_block, allow_duplicate=True)

def _pack_titles(builder, notebook, offset=0):
    for title in notebook.get_titles():
        page_number = title.get_page_number() + 1 + offset
        if page_number > 9999:
            # the number of digits is limited to 4, so we ignore this keyword
            continue
        position = title.get_position()
        id = f'{page_number:04d}{position:04d}'
        content = title.get_content()
        if content is not None:
            builder.append(f'TITLE_{id}', content, allow_duplicate=True)
            title_metadata = title.metadata
            address_list = builder.get_duplicate_block_address_list(f'TITLE_{id}')
            if len(address_list) == 1:
                title_metadata['TITLEBITMAP'] = str(address_list[0])
            else:
                title_metadata['TITLEBITMAP'] = str(address_list[-1]) # use last address
            title_metadata_block = _construct_metadata_block(title_metadata)
            builder.append(f'TITLE_{id}/metadata', title_metadata_block, allow_duplicate=True)

def _pack_backgrounds(builder, notebook):
    for i in range(notebook.get_total_pages()):
        page = notebook.get_page(i)
        style = page.get_style()
        if style.startswith('user_'):
            style += page.get_style_hash()
        content = _find_background_content_from_page(page)
        if content is not None:
            builder.append(f'STYLE_{style}', content)

def _pack_pages(builder, notebook, offset=0):
    for i in range(notebook.get_total_pages()):
        page_number = i + 1 + offset
        page = notebook.get_page(i)
        page = utils.WorkaroundPageWrapper.from_page(page)
        # layers
        layers = page.get_layers()
        for layer in layers:
            layer_name = layer.get_name()
            if layer_name is None:
                continue
            if layer_name == 'BGLAYER':
                style = page.get_style()
                if style.startswith('user_'):
                    style += page.get_style_hash()
                layer_metadata = layer.metadata
                layer_metadata['LAYERNAME'] = layer_name
                layer_metadata['LAYERBITMAP'] = str(builder.get_block_address(f'STYLE_{style}'))
                layer_metadata_block = _construct_metadata_block(layer_metadata)
                builder.append(f'PAGE{page_number}/{layer_name}/metadata', layer_metadata_block)
            else:
                content = layer.get_content()
                builder.append(f'PAGE{page_number}/{layer_name}/LAYERBITMAP', content)
                layer_metadata = layer.metadata
                layer_metadata['LAYERNAME'] = layer_name
                layer_metadata['LAYERBITMAP'] = str(builder.get_block_address(f'PAGE{page_number}/{layer_name}/LAYERBITMAP'))
                layer_metadata_block = _construct_metadata_block(layer_metadata)
                builder.append(f'PAGE{page_number}/{layer_name}/metadata', layer_metadata_block)
        # totalpath
        totalpath_block = page.get_totalpath()
        if totalpath_block is not None:
            builder.append(f'PAGE{page_number}/TOTALPATH', totalpath_block)
        # page metadata
        page_metadata = page.metadata
        del page_metadata['__layers__']
        for prop in ['MAINLAYER', 'LAYER1', 'LAYER2', 'LAYER3', 'BGLAYER']:
            address = builder.get_block_address(f'PAGE{page_number}/{prop}/metadata')
            page_metadata[prop] = address
        page_metadata['TOTALPATH'] = builder.get_block_address(f'PAGE{page_number}/TOTALPATH')
        page_metadata_block = _construct_metadata_block(page_metadata)
        builder.append(f'PAGE{page_number}/metadata', page_metadata_block)

def _pack_footer(builder):
    metadata_footer = {}
    metadata_footer.setdefault('FILE_FEATURE', builder.get_block_address('__header__'))
    address = builder.get_block_address('COVER_1')
    if address == 0:
        metadata_footer['COVER_0'] = 0
    else:
        metadata_footer['COVER_1'] = address
    for label in builder.get_labels():
        if re.match(r'KEYWORD_\d{8}/metadata', label):
            address_list = builder.get_duplicate_block_address_list(label)
            label = label[:-len('/metadata')]
            if len(address_list) == 1:
                metadata_footer.setdefault(label, address_list[0])
            else:
                metadata_footer[label] = address_list
    for label in builder.get_labels():
        if re.match(r'TITLE_\d{8}/metadata', label):
            address_list = builder.get_duplicate_block_address_list(label)
            label = label[:-len('/metadata')]
            if len(address_list) == 1:
                metadata_footer.setdefault(label, address_list[0])
            else:
                metadata_footer[label] = address_list
    for label in builder.get_labels():
        if label.startswith('STYLE_'):
            address = builder.get_block_address(label)
            metadata_footer.setdefault(label, address)
    for label in builder.get_labels():
        if re.match(r'PAGE\d+/metadata', label):
            address = builder.get_block_address(label)
            label = label[:-len('/metadata')]
            metadata_footer.setdefault(label, address)
    footer_block = _construct_metadata_block(metadata_footer)
    builder.append('__footer__', footer_block)

def _pack_footer_address(builder):
    footer_address = builder.get_block_address('__footer__')
    builder.append('__footer_address__', footer_address.to_bytes(4, 'little'), skip_block_size=True)

def _verify_header_property(prop_name, metadata1, metadata2):
    if metadata1.header.get(prop_name) != metadata2.header.get(prop_name):
        raise ValueError(f'<{prop_name}> property must be same between merging files')

def _construct_metadata_block(info):
    block_data = ''
    for k, v in info.items():
        if type(v) == list:
            for e in v:
                block_data += f'<{k}:{e}>'
        else:
            block_data += f'<{k}:{v}>'
    return block_data.encode('utf-8')

def _find_background_content_from_page(page):
    page = utils.WorkaroundPageWrapper.from_page(page)
    if not page.is_layer_supported():
        return None
    layers = page.get_layers()
    for l in layers:
        if l.get_name() == 'BGLAYER':
            return l.get_content()
    return None
