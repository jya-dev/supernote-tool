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


class NotebookBuilder:
    def __init__(self, offset=0):
        self.total_size = offset
        self.toc = {}
        self.blocks = []

    def get_total_size(self):
        return self.total_size

    def get_block_address(self, label):
        address = self.toc.get(label)
        return address if address is not None else 0

    def get_labels(self):
        return self.toc.keys()

    def append(self, label, block, skip_block_size=False):
        if block is None:
            return
        block_size = len(block)
        if not skip_block_size:
            self.blocks.append(block_size.to_bytes(fileformat.LENGTH_FIELD_SIZE, 'little'))
        self.blocks.append(block)
        self.toc.setdefault(label, self.total_size)
        self.total_size += block_size
        if not skip_block_size:
            self.total_size += fileformat.LENGTH_FIELD_SIZE

    def build(self):
        return b''.join(self.blocks)

    def dump(self):
        print('# NotebookBuilder Dump:')
        print(f'# total_size = {self.total_size}')
        print(f'# toc = {self.toc}')


def reconstruct(notebook):
    """Reconstruct a notebook for debug."""
    metadata = notebook.get_metadata()
    if metadata.signature != 'noteSN_FILE_VER_20210010':
        raise ValueError('Only latest file format version is supported')

    builder = NotebookBuilder()

    # signature
    builder.append('__signature__', metadata.signature.encode('ascii'), skip_block_size=True)

    # header
    header_block = _construct_metadata_block(metadata.header)
    builder.append('__header__', header_block)

    # background images
    for i in range(notebook.get_total_pages()):
        page = notebook.get_page(i)
        style = page.get_style()
        content = _get_background_content_from_page(page)
        if content is not None:
            builder.append(f'STYLE_{style}', content)

    # pages
    for i in range(notebook.get_total_pages()):
        page = notebook.get_page(i)
        # layers
        visited_mainlayer = False # workaround for dulicated layer name
        layers = page.get_layers()
        for layer in layers:
            layer_name = layer.get_name()
            if layer_name is None:
                continue
            if visited_mainlayer and layer_name == 'MAINLAYER':
                # this layer has duplicated name, so we guess this layer is BGLAYER
                layer_name = 'BGLAYER'
            elif layer_name == 'MAINLAYER':
                visited_mainlayer = True
            if layer_name == 'BGLAYER':
                style = page.get_style()
                layer_metadata = layer.metadata
                layer_metadata['LAYERNAME'] = layer_name
                layer_metadata['LAYERBITMAP'] = str(builder.get_block_address(f'STYLE_{style}'))
                layer_metadata_block = _construct_metadata_block(layer_metadata)
                builder.append(f'PAGE{i+1}/{layer_name}/metadata', layer_metadata_block)
            else:
                content = layer.get_content()
                builder.append(f'PAGE{i+1}/{layer_name}/LAYERBITMAP', content)
                layer_metadata = layer.metadata
                layer_metadata['LAYERNAME'] = layer_name
                layer_metadata['LAYERBITMAP'] = str(builder.get_block_address(f'PAGE{i+1}/{layer_name}/LAYERBITMAP'))
                layer_metadata_block = _construct_metadata_block(layer_metadata)
                builder.append(f'PAGE{i+1}/{layer_name}/metadata', layer_metadata_block)
        # totalpath
        totalpath_block = page.get_totalpath()
        if totalpath_block is not None:
            builder.append(f'PAGE{i+1}/TOTALPATH', totalpath_block)

        # page metadata
        page_metadata = page.metadata
        del page_metadata['__layers__']
        for prop in ['MAINLAYER', 'LAYER1', 'LAYER2', 'LAYER3', 'BGLAYER']:
            address = builder.get_block_address(f'PAGE{i+1}/{prop}/metadata')
            page_metadata[prop] = address
        page_metadata['TOTALPATH'] = builder.get_block_address(f'PAGE{i+1}/TOTALPATH')
        page_metadata_block = _construct_metadata_block(page_metadata)
        builder.append(f'PAGE{i+1}/metadata', page_metadata_block)

    # footer
    metadata_footer = {}
    metadata_footer.setdefault('FILE_FEATURE', builder.get_block_address('__header__'))
    for label in builder.get_labels():
        if label.startswith('STYLE_'):
            address = builder.get_block_address(label)
            metadata_footer.setdefault(label, address)
    for label in builder.get_labels():
        if re.match(r'PAGE\d+/metadata', label):
            address = builder.get_block_address(label)
            label = label[:-len('/metadata')]
            metadata_footer.setdefault(label, address)
    # TODO: support COVER, KEYWORD, TITLE, custom template (STYLE_user_...)
    footer_block = _construct_metadata_block(metadata_footer)
    builder.append('__footer__', footer_block)

    # footer address
    footer_address = builder.get_block_address('__footer__')
    builder.append('__footer_address__', footer_address.to_bytes(4, 'little'), skip_block_size=True)

    return builder.build()


def merge(notebook1, notebook2):
    """Merge multiple notebooks to one."""
    # TODO: support non-X series
    metadata1 = notebook1.get_metadata()
    metadata2 = notebook2.get_metadata()
    if metadata1.signature != metadata2.signature:
        raise ValueError('File signature must be same between merging files')
    # check header properties are same to avoid generating a corrupted note file
    _verify_header_property('FILE_TYPE', metadata1, metadata2)
    _verify_header_property('APPLY_EQUIPMENT', metadata1, metadata2)
    _verify_header_property('DEVICE_DPI', metadata1, metadata2)
    _verify_header_property('SOFT_DPI', metadata1, metadata2)
    _verify_header_property('FILE_PARSE_TYPE', metadata1, metadata2)
    _verify_header_property('RATTA_ETMD', metadata1, metadata2)
    _verify_header_property('APP_VERSION', metadata1, metadata2)

    merging_blocks = []
    merging_blocks.append(metadata1.signature)
    merging_blocks.append(_construct_metadata_block(metadata1.header))

    bg_table = {}
    total_pages1 = notebook1.get_total_pages()
    for i in range(total_pages1):
        page = notebook1.get_page(i)
        style = page.get_style()
        bg_binary = _get_background_content_from_page(page)
        bg_table.setdefault(style, bg_binary)
    total_pages2 = metadata2.get_total_pages()
    for i in range(total_pages2):
        page = notebook2.get_page(i)
        style = page.get_style()
        bg_binary = _get_background_content_from_page(page)
        bg_table.setdefault(style, bg_binary)

    for style, content in bg_table.items():
        merging_blocks.append(content)

    # NOTE: we don't need this?
    background_props1 = _extract_background_properties(metadata1.footer)
    background_props2 = _extract_background_properties(metadata2.footer)

    # TODO: implement here
    total_pages1 = metadata1.get_total_pages()

    merged_total_pages = metadata1.get_total_pages() + metadata2.get_total_pages()

    print(merged_metadata.to_json(indent=2))

    return notebook1

def save_as_note(notebook, filename):
    """Save a notebook object as a note file."""
    raise NotImplementedError('function is not implemented yet')

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
    return block_data.encode('ascii')

def _extract_background_properties(footer):
    props = {}
    for k, v in footer.items():
        if k.startswith('STYLE_'):
            props[k] = int(v)
    return props

def _get_background_content_from_page(page):
    if not page.is_layer_supported():
        return None
    visited_mainlayer = False # workaround for dulicated layer name
    layers = page.get_layers()
    for l in layers:
        layer_name = l.get_name()
        if visited_mainlayer and layer_name == 'MAINLAYER':
            # this layer has duplicated name, so we guess this layer is BGLAYER
            layer_name = 'BGLAYER'
        elif layer_name == 'MAINLAYER':
            visited_mainlayer = True
        if layer_name == 'BGLAYER':
            return l.get_content()
    return None
