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

"""Parser classes."""

import os
import re

from . import exceptions
from . import fileformat


def parse_metadata(file_name):
    """Parses a supernote file and returns metadata object.

    Parameters
    ----------
    file_name : str
        file path string

    Returns
    -------
    SupernoteMetadata
        metadata object
    """
    try:
        parser = SupernoteParser()
        metadata = parser.parse(file_name)
    except exceptions.UnsupportedFileFormat:
        # ignore this exception and try next parser
        pass
    else:
        return metadata

    try:
        parser = SupernoteXParser()
        metadata = parser.parse(file_name)
    except exceptions.UnsupportedFileFormat:
        # ignore this exception and try next parser
        pass
    else:
        return metadata

    # we cannot parse the file with any our parser.
    raise exceptions.UnsupportedFileFormat('unsupported file format')

def load_notebook(file_name, metadata=None):
    """Creates a Notebook object from the supernote file.

    Parameters
    ----------
    file_name : str
        file path string
    metadata : SupernoteMetadata
        metadata object

    Returns
    -------
    Notebook
        notebook object
    """
    if metadata is None:
        metadata = parse_metadata(file_name)

    note = fileformat.Notebook(metadata)

    with open(file_name, 'rb') as f:
        page_total = metadata.get_total_pages()
        for p in range(page_total):
            addresses = _get_bitmap_address(metadata, p)
            if len(addresses) == 1: # the page has no layers
                content = _get_content_at_address(f, addresses[0])
                note.get_page(p).set_content(content)
            else:
                for l, addr in enumerate(addresses):
                    content = _get_content_at_address(f, addr)
                    note.get_page(p).get_layer(l).set_content(content)
    return note

def _get_content_at_address(fobj, address):
    content = None
    if address != 0:
        fobj.seek(address, os.SEEK_SET)
        block_length = int.from_bytes(fobj.read(fileformat.LENGTH_FIELD_SIZE), 'little')
        content = fobj.read(block_length)
    return content

def _get_bitmap_address(metadata, page_number):
    """Returns bitmap address of the given page number.

    Returns
    -------
    list of int
        bitmap address
    """
    addresses = []
    layer_supported = metadata.is_layer_supported(page_number)
    if layer_supported:
        for l in range(5):      # TODO: use constant
            address = metadata.pages[page_number][fileformat.KEY_LAYERS][l].get('LAYERBITMAP')
            addresses.append(0 if address is None else int(address))
    else:
        addresses.append(int(metadata.pages[page_number]['DATA']))
    return addresses


class SupernoteParser:
    """Parser for original Supernote."""
    SN_SIGNATURES = ['SN_FILE_ASA_20190529']

    def parse(self, file_name):
        """Parses a Supernote file and returns SupernoteMetadata object.

        Parameters
        ----------
        file_name : str
            file path string

        Returns
        -------
        SupernoteMetadata
            metadata of the file
        """
        with open(file_name, 'rb') as f:
            # check file signature
            signature = self._find_matching_signature(f)
            if signature is None:
                raise exceptions.UnsupportedFileFormat(f'unknown signature: {signature}')
            # parse footer block
            f.seek(-fileformat.ADDRESS_SIZE, os.SEEK_END) # footer address is located at last 4-byte
            footer_address = int.from_bytes(f.read(fileformat.ADDRESS_SIZE), 'little')
            footer = self._parse_metadata_block(f, footer_address)
            # parse header block
            header_address = self._get_header_address(footer)
            header = self._parse_metadata_block(f, header_address)
            # parse page blocks
            page_addresses = self._get_page_addresses(footer)
            pages = list(map(lambda addr: self._parse_page_block(f, addr), page_addresses))
        metadata = fileformat.SupernoteMetadata()
        metadata.signature = signature
        metadata.header = header
        metadata.footer = footer
        metadata.pages = pages
        return metadata

    def _find_matching_signature(self, fobj):
        """Reads signature from file object and returns matching signature.

        Parameters
        ----------
        fobj : file
            file object

        Returns
        -------
        string
            matching signature or None if not found
        """
        for sig in self.SN_SIGNATURES:
            try:
                fobj.seek(0, os.SEEK_SET)
                signature = fobj.read(len(sig)).decode()
            except UnicodeDecodeError:
                # try next signature
                continue
            if signature == sig:
                return signature
        return None

    def _get_header_address(self, footer):
        """Returns header address.

        Parameters
        ----------
        footer : dict
            footer parameters

        Returns
        -------
        int
            header address
        """
        header_address = int(footer.get('FILE_FEATURE'))
        return header_address

    def _get_page_addresses(self, footer):
        """Returns list of page addresses.

        Parameters
        ----------
        footer : dict
            footer parameters

        Returns
        -------
        list of int
            list of page address
        """
        if type(footer.get('PAGE')) == list:
            page_addresses = list(map(lambda a: int(a), footer.get('PAGE')))
        else:
            page_addresses = [int(footer.get('PAGE'))]
        return page_addresses

    def _parse_page_block(self, fobj, address):
        """Returns parameters in a page block.

        Parameters
        ----------
        fobj : file
            file object
        address : int
            page block address

        Returns
        -------
        dict
            parameters in the page block
        """
        return self._parse_metadata_block(fobj, address)

    def _parse_metadata_block(self, fobj, address):
        """Converts metadata block into dict of parameters.

        Returns empty dict if address equals to 0.

        Parameters
        ----------
        fobj : file
            file object
        address : int
            metadata block address

        Returns
        -------
        dict
            extracted parameters
        """
        if address == 0:
            return {}
        fobj.seek(address, os.SEEK_SET)
        block_length = int.from_bytes(fobj.read(fileformat.LENGTH_FIELD_SIZE), 'little')
        contents = fobj.read(block_length)
        params = self._extract_parameters(contents.decode())
        return params

    def _extract_parameters(self, metadata):
        """Returns dict of parameters extracted from metadata.

        metadata is a repetition of key-value style parameter like
        `<KEY1:VALUE1><KEY2:VALUE2>...`.

        Parameters
        ----------
        metadata : str
            metadata string

        Returns
        -------
        dict
            extracted parameters
        """
        pattern = r'<([^:<>]+):([^:<>]*)>'
        result = re.finditer(pattern, metadata)
        params = {}
        for m in result:
            key = m[1]
            value = m[2]
            if params.get(key):
                # the key is duplicate.
                if type(params.get(key)) != list:
                    # To store duplicate parameters, we transform data structure
                    # from {key: value} to {key: [value1, value2, ...]}
                    first_value = params.pop(key)
                    params[key] = [first_value, value]
                else:
                    # Data structure have already been transformed.
                    # We simply append new value to the list.
                    params[key].append(value)
            else:
                params[key] = value
        return params


class SupernoteXParser(SupernoteParser):
    """Parser for Supernote X-series."""
    SN_SIGNATURES = [
        'noteSN_FILE_VER_20200001', # Firmware version C.053
        'noteSN_FILE_VER_20200005', # Firmware version C.077
        'noteSN_FILE_VER_20200006', # Firmware version C.130
        'noteSN_FILE_VER_20200007'  # Firmware version C.159
    ]
    LAYER_KEYS = ['MAINLAYER', 'LAYER1', 'LAYER2', 'LAYER3', 'BGLAYER']

    def _get_page_addresses(self, footer):
        """Returns list of page addresses.

        Parameters
        ----------
        footer : dict
            footer parameters

        Returns
        -------
        list of int
            list of page address
        """
        page_keys = filter(lambda k : k.startswith('PAGE'), footer.keys())
        page_addresses = list(map(lambda k: int(footer[k]), page_keys))
        return page_addresses

    def _parse_page_block(self, fobj, address):
        """Returns parameters in a page block.

        Parameters
        ----------
        fobj : file
            file object
        address : int
            page block address

        Returns
        -------
        dict
            parameters in the page block
        """
        page_info = super()._parse_page_block(fobj, address)
        layer_addresses = self._get_layer_addresses(page_info)
        layers = list(map(lambda addr: self._parse_layer_block(fobj, addr), layer_addresses))
        page_info[fileformat.KEY_LAYERS] = layers
        return page_info

    def _get_layer_addresses(self, page_info):
        """Returns list of layer addresses.

        Parameters
        ----------
        page_info : dict
            page parameters

        Returns
        -------
        list of int
            list of layer address
        """
        layer_keys = filter(lambda k : k in self.LAYER_KEYS, page_info)
        layer_addresses = list(map(lambda k: int(page_info[k]), layer_keys))
        return layer_addresses

    def _parse_layer_block(self, fobj, address):
        """Returns parameters in a layer block.

        Parameters
        ----------
        fobj : file
            file object
        address : int
            layer block address

        Returns
        -------
        dict
            parameters in the layer block
        """
        return self._parse_metadata_block(fobj, address)
