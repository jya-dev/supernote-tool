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


def parse_metadata(stream, policy='strict'):
    """Parses a supernote binary stream and returns metadata object.

    Policy:
    - 'strict': raise exception for unknown signature (default)
    - 'loose': try to parse for unknown signature

    Parameters
    ----------
    stream : file-like object
        supernote binary stream
    policy : str
        signature check policy

    Returns
    -------
    SupernoteMetadata
        metadata object
    """
    try:
        parser = SupernoteXParser()
        metadata = parser.parse_stream(stream, policy)
    except exceptions.UnsupportedFileFormat:
        # ignore this exception and try next parser
        pass
    else:
        return metadata

    try:
        parser = SupernoteParser()
        metadata = parser.parse_stream(stream, policy)
    except exceptions.UnsupportedFileFormat:
        # ignore this exception and try next parser
        pass
    else:
        return metadata

    # we cannot parse the file with any our parser.
    raise exceptions.UnsupportedFileFormat('unsupported file format')

def load(stream, metadata=None, policy='strict'):
    """Creates a Notebook object from the supernote binary stream.

    Policy:
    - 'strict': raise exception for unknown signature (default)
    - 'loose': try to parse for unknown signature

   Parameters
    ----------
    stream : file-like object
        supernote binary stream
    metadata : SupernoteMetadata
        metadata object
    policy : str
        signature check policy

    Returns
    -------
    Notebook
        notebook object
    """
    if metadata is None:
        metadata = parse_metadata(stream, policy)

    note = fileformat.Notebook(metadata)

    cover_address = _get_cover_address(metadata)
    if cover_address > 0:
        content = _get_content_at_address(stream, cover_address)
        note.get_cover().set_content(content)
    # store keyword data to notebook object
    for keyword in note.get_keywords():
        address = _get_keyword_address(keyword)
        content = _get_content_at_address(stream, address)
        keyword.set_content(content)
    # store title data to notebook object
    page_numbers = _get_page_number_from_footer_property(note.get_metadata().footer, 'TITLE_')
    for i, title in enumerate(note.get_titles()):
        address = _get_title_address(title)
        content = _get_content_at_address(stream, address)
        title.set_content(content)
        title.set_page_number(page_numbers[i])
    # store link data to notebook object
    page_numbers = _get_page_number_from_footer_property(note.get_metadata().footer, 'LINK')
    for i, link in enumerate(note.get_links()):
        address = _get_link_address(link)
        content = _get_content_at_address(stream, address)
        link.set_content(content)
        link.set_page_number(page_numbers[i])
    page_total = metadata.get_total_pages()
    for p in range(page_total):
        addresses = _get_bitmap_address(metadata, p)
        if len(addresses) == 1: # the page has no layers
            content = _get_content_at_address(stream, addresses[0])
            note.get_page(p).set_content(content)
        else:
            for l, addr in enumerate(addresses):
                content = _get_content_at_address(stream, addr)
                note.get_page(p).get_layer(l).set_content(content)
        # store path data to notebook object
        totalpath_address = _get_totalpath_address(metadata, p)
        if totalpath_address > 0:
            content = _get_content_at_address(stream, totalpath_address)
            note.get_page(p).set_totalpath(content)
        # store recogn file data to notebook object
        recogn_file_address = _get_recogn_file_address(metadata, p)
        if recogn_file_address > 0:
            content = _get_content_at_address(stream, recogn_file_address)
            note.get_page(p).set_recogn_file(content)
        # store recogn text data to notebook object
        recogn_text_address = _get_recogn_text_address(metadata, p)
        if recogn_text_address > 0:
            content = _get_content_at_address(stream, recogn_text_address)
            note.get_page(p).set_recogn_text(content)
    return note

def load_notebook(file_name, metadata=None, policy='strict'):
    """Creates a Notebook object from the supernote file.

    Policy:
    - 'strict': raise exception for unknown signature (default)
    - 'loose': try to parse for unknown signature

   Parameters
    ----------
    file_name : str
        file path string
    metadata : SupernoteMetadata
        metadata object
    policy : str
        signature check policy

    Returns
    -------
    Notebook
        notebook object
    """
    with open(file_name, 'rb') as f:
        note = load(f, metadata, policy)
    return note

def _get_content_at_address(fobj, address):
    content = None
    if address != 0:
        fobj.seek(address, os.SEEK_SET)
        block_length = int.from_bytes(fobj.read(fileformat.LENGTH_FIELD_SIZE), 'little')
        content = fobj.read(block_length)
    return content

def _get_cover_address(metadata):
    """Returns cover address.

    Returns
    -------
    int
        cover address
    """
    if 'COVER_2' in metadata.footer:
        address = int(metadata.footer['COVER_2'])
    elif 'COVER_1' in metadata.footer:
        address = int(metadata.footer['COVER_1'])
    else:
        address = 0
    return address

def _get_keyword_address(keyword):
    """Returns keyword content address.

    Returns
    -------
    int
        keyword content address
    """
    return int(keyword.metadata['KEYWORDSITE'])

def _get_title_address(title):
    """Returns title content address.

    Returns
    -------
    int
        title content address
    """
    return int(title.metadata['TITLEBITMAP'])

def _get_link_address(link):
    """Returns link content address.

    Returns
    -------
    int
        link content address
    """
    return int(link.metadata['LINKBITMAP'])

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

def _get_totalpath_address(metadata, page_number):
    """Returns total path address of the given page number.

    Returns
    -------
    int
        total path address
    """
    if 'TOTALPATH' in metadata.pages[page_number]:
        address = int(metadata.pages[page_number]['TOTALPATH'])
    else:
        address = 0
    return address

def _get_recogn_file_address(metadata, page_number):
    """Returns recogn file address of the given page number.

    Returns
    -------
    int
        recogn file address
    """
    if 'RECOGNFILE' in metadata.pages[page_number]:
        address = int(metadata.pages[page_number]['RECOGNFILE'])
    else:
        address = 0
    return address

def _get_recogn_text_address(metadata, page_number):
    """Returns recogn text address of the given page number.

    Returns
    -------
    int
        recogn text address
    """
    if 'RECOGNTEXT' in metadata.pages[page_number]:
        address = int(metadata.pages[page_number]['RECOGNTEXT'])
    else:
        address = 0
    return address

def _get_page_number_from_footer_property(footer, prefix):
    keys = filter(lambda k : k.startswith(prefix), footer.keys())
    page_numbers = []
    for k in keys:
        if type(footer[k]) == list:
            for _ in range(len(footer[k])):
                page_numbers.append(int(k[6:10]) - 1)
        else:
            page_numbers.append(int(k[6:10]) - 1) # e.g. get '0123' from 'TITLE_01234567'
    return page_numbers


class SupernoteParser:
    """Parser for original Supernote."""
    SN_SIGNATURE_OFFSET = 0
    SN_SIGNATURE_PATTERN = r'SN_FILE_ASA_\d{8}'
    SN_SIGNATURES = ['SN_FILE_ASA_20190529']

    def parse(self, file_name, policy='strict'):
        """Parses a Supernote file and returns SupernoteMetadata object.

        Policy:
        - 'strict': raise exception for unknown signature (default)
        - 'loose': try to parse for unknown signature

        Parameters
        ----------
        file_name : str
            file path string
        policy : str
            signature check policy

        Returns
        -------
        SupernoteMetadata
            metadata of the file
        """
        with open(file_name, 'rb') as f:
            metadata = self.parse_stream(f, policy)
        return metadata

    def parse_stream(self, stream, policy='strict'):
        """Parses a Supernote file stream and returns SupernoteMetadata object.

        Policy:
        - 'strict': raise exception for unknown signature (default)
        - 'loose': try to parse for unknown signature

        Parameters
        ----------
        file_name : str
            file path string
        policy : str
            signature check policy

        Returns
        -------
        SupernoteMetadata
            metadata of the file
        """
        # parse file type
        filetype = self._parse_filetype(stream)
        # check file signature
        signature = self._find_matching_signature(stream)
        if signature is None:
            compatible = self._check_signature_compatible(stream)
            if policy != 'loose' or not compatible:
                raise exceptions.UnsupportedFileFormat(f'unknown signature: {signature}')
            else:
                signature = self.SN_SIGNATURES[-1] # treat as latest supported signature
        # parse footer block
        stream.seek(-fileformat.ADDRESS_SIZE, os.SEEK_END) # footer address is located at last 4-byte
        footer_address = int.from_bytes(stream.read(fileformat.ADDRESS_SIZE), 'little')
        footer = self._parse_footer_block(stream, footer_address)
        # parse header block
        header_address = self._get_header_address(footer)
        header = self._parse_metadata_block(stream, header_address)
        # parse page blocks
        page_addresses = self._get_page_addresses(footer)
        pages = list(map(lambda addr: self._parse_page_block(stream, addr), page_addresses))

        metadata = fileformat.SupernoteMetadata()
        metadata.type = filetype
        metadata.signature = signature
        metadata.header = header
        metadata.footer = footer
        metadata.pages = pages
        return metadata

    def _parse_filetype(self, fobj):
        fobj.seek(0, os.SEEK_SET)
        filetype = fobj.read(4).decode()
        return filetype

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
                fobj.seek(self.SN_SIGNATURE_OFFSET, os.SEEK_SET)
                signature = fobj.read(len(sig)).decode()
            except UnicodeDecodeError:
                # try next signature
                continue
            if signature == sig:
                return signature
        return None

    def _check_signature_compatible(self, fobj):
        latest_signature = self.SN_SIGNATURES[-1]
        try:
            fobj.seek(0, os.SEEK_SET)
            signature = fobj.read(len(latest_signature)).decode()
        except Exception:
            return False
        else:
            if re.match(self.SN_SIGNATURE_PATTERN, signature):
                return True
            else:
                return False

    def _parse_footer_block(self, fobj, address):
        return self._parse_metadata_block(fobj, address)

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
        pattern = r'<([^:<>]+):(.*?)>'
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
    SN_SIGNATURE_OFFSET = 4
    SN_SIGNATURE_PATTERN = r'SN_FILE_VER_\d{8}'
    SN_SIGNATURES = [
        'SN_FILE_VER_20200001', # Firmware version C.053
        'SN_FILE_VER_20200005', # Firmware version C.077
        'SN_FILE_VER_20200006', # Firmware version C.130
        'SN_FILE_VER_20200007', # Firmware version C.159
        'SN_FILE_VER_20200008', # Firmware version C.237
        'SN_FILE_VER_20210009', # Firmware version C.291
        'SN_FILE_VER_20210010', # Firmware version Chauvet 2.1.6
        'SN_FILE_VER_20220011', # Firmware version Chauvet 2.5.17
        'SN_FILE_VER_20220013', # Firmware version Chauvet 2.6.19
        'SN_FILE_VER_20230014', # Firmware version Chauvet 2.10.25
        'SN_FILE_VER_20230015'  # Firmware version Chauvet 3.14.27
    ]
    LAYER_KEYS = ['MAINLAYER', 'LAYER1', 'LAYER2', 'LAYER3', 'BGLAYER']

    def _parse_footer_block(self, fobj, address):
        footer = super()._parse_metadata_block(fobj, address)
        # parse keywords
        keyword_addresses = self._get_keyword_addresses(footer)
        keywords = list(map(lambda addr: self._parse_keyword_block(fobj, addr), keyword_addresses))
        if keywords:
            # Workaround: Replacing keyword content due to inaccurate parsing.
            for keyword in keywords:
                address = int(keyword['KEYWORDSITE'])
                content = _get_content_at_address(fobj, address)
                keyword['KEYWORD'] = content.decode()
            footer[fileformat.KEY_KEYWORDS] = keywords
        # parse titles
        title_addresses = self._get_title_addresses(footer)
        titles = list(map(lambda addr: self._parse_title_block(fobj, addr), title_addresses))
        if titles:
            footer[fileformat.KEY_TITLES] = titles
        # parse links
        link_addresses = self._get_link_addresses(footer)
        links = list(map(lambda addr: self._parse_link_block(fobj, addr), link_addresses))
        if links:
            footer[fileformat.KEY_LINKS] = links
        return footer

    def _get_keyword_addresses(self, footer):
        keyword_keys = filter(lambda k : k.startswith('KEYWORD_'), footer.keys())
        keyword_addresses = []
        for k in keyword_keys:
            if type(footer[k]) == list:
                keyword_addresses.extend(list(map(int, footer[k])))
            else:
                keyword_addresses.append(int(footer[k]))
        return keyword_addresses

    def _parse_keyword_block(self, fobj, address):
        return self._parse_metadata_block(fobj, address)

    def _get_title_addresses(self, footer):
        title_keys = filter(lambda k : k.startswith('TITLE_'), footer.keys())
        title_addresses = []
        for k in title_keys:
            if type(footer[k]) == list:
                title_addresses.extend(list(map(int, footer[k])))
            else:
                title_addresses.append(int(footer[k]))
        return title_addresses

    def _parse_title_block(self, fobj, address):
        return self._parse_metadata_block(fobj, address)

    def _get_link_addresses(self, footer):
        link_keys = filter(lambda k : k.startswith('LINK'), footer.keys())
        link_addresses = []
        for k in link_keys:
            if type(footer[k]) == list:
                link_addresses.extend(list(map(int, footer[k])))
            else:
                link_addresses.append(int(footer[k]))
        return link_addresses

    def _parse_link_block(self, fobj, address):
        return self._parse_metadata_block(fobj, address)

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
