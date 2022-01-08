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

from . import parser


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
        prop = f'<{k}:{v}>'
        block_data += prop
    return block_data

def _extract_background_properties(footer):
    props = {}
    for k, v in footer.items():
        if k.startswith('STYLE_'):
            props[k] = int(v)
    return props

def _get_background_content_from_page(page):
    if not page.is_layer_supported():
        return None
    layers = page.get_layers()
    for l in layers:
        if l.get_name() == 'BGLAYER':
            return l.get_content()
    # TODO: handle files that have duplicated MAINLAYER (no BGLAYER)
    return None
