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

import base64
import json
import potrace
import svgwrite

from enum import Enum, auto
from io import BytesIO

from PIL import Image

from svglib.svglib import svg2rlg
from reportlab.lib.pagesizes import A4, portrait, landscape
from reportlab.graphics import renderPDF
from reportlab.pdfgen import canvas

from . import color
from . import decoder as Decoder
from . import exceptions
from . import fileformat
from . import utils


class VisibilityOverlay(Enum):
    DEFAULT = auto()
    VISIBLE = auto()
    INVISIBLE = auto()


class ImageConverter:
    SPECIAL_WHITE_STYLE_BLOCK_SIZE = 0x140e

    def __init__(self, notebook, palette=None):
        self.note = notebook
        self.palette = palette

    def convert(self, page_number, visibility_overlay=None):
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
            highres_grayscale = self.note.supports_highres_grayscale()
            converted_img = self._convert_layered_page(page, self.palette, visibility_overlay, highres_grayscale)
        else:
            converted_img = self._convert_nonlayered_page(page, self.palette, visibility_overlay)
        if visibility_overlay is not None and visibility_overlay.get('BGLAYER') == VisibilityOverlay.INVISIBLE:
            converted_img = self._make_transparent(converted_img)
        return converted_img

    def _convert_nonlayered_page(self, page, palette=None, visibility_overlay=None, highres_grayscale=False):
        binary = page.get_content()
        if binary is None:
            return Image.new('L', (fileformat.PAGE_WIDTH, fileformat.PAGE_HEIGHT), color=color.TRANSPARENT)
        decoder = self.find_decoder(page)
        return self._create_image_from_decoder(decoder, binary, palette=palette)

    def _convert_layered_page(self, page, palette=None, visibility_overlay=None, highres_grayscale=False):
        default_palette = color.DEFAULT_COLORPALETTE
        page = utils.WorkaroundPageWrapper.from_page(page)
        imgs = {}
        layers = page.get_layers()
        for layer in layers:
            layer_name = layer.get_name()
            binary = layer.get_content()
            if binary is None:
                imgs[layer_name] = None
                continue
            binary_size = len(binary)
            decoder = self.find_decoder(layer, highres_grayscale)
            page_style = page.get_style()
            all_blank = (layer_name == 'BGLAYER' and page_style is not None and page_style == 'style_white' and \
                         binary_size == self.SPECIAL_WHITE_STYLE_BLOCK_SIZE)
            custom_bg = (layer_name == 'BGLAYER' and page_style is not None and page_style.startswith('user_'))
            if custom_bg:
                decoder = Decoder.PngDecoder()
            horizontal = page.get_orientation() == fileformat.Page.ORIENTATION_HORIZONTAL
            plt = default_palette if layer_name == 'BGLAYER' else palette
            img = self._create_image_from_decoder(decoder, binary, palette=plt, blank_hint=all_blank, horizontal=horizontal)
            imgs[layer_name] = img
        return self._flatten_layers(page, imgs, visibility_overlay)

    def _flatten_layers(self, page, imgs, visibility_overlay=None):
        """flatten all layers if any"""
        def flatten(fg, bg):
            mask = fg.copy().convert('L')
            mask = mask.point(lambda x: 0 if x == color.TRANSPARENT else 1, mode='1')
            return Image.composite(fg, bg, mask)
        horizontal = page.get_orientation() == fileformat.Page.ORIENTATION_HORIZONTAL
        page_width, page_height = (fileformat.PAGE_WIDTH, fileformat.PAGE_HEIGHT)
        if horizontal:
            page_height, page_width = (page_width, page_height)
        flatten_img = Image.new('RGB', (page_width, page_height), color=color.RGB_TRANSPARENT)
        visibility = self._get_layer_visibility(page)
        layer_order = page.get_layer_order()
        for name in reversed(layer_order):
            is_visible = visibility.get(name)
            if visibility_overlay is not None:
                overlay = visibility_overlay.get(name)
                if overlay == VisibilityOverlay.INVISIBLE or (overlay == VisibilityOverlay.DEFAULT and not is_visible):
                    continue
            else:
                if not is_visible:
                    continue
            img_layer = imgs.get(name)
            if img_layer is not None:
                if name == 'BGLAYER':
                    # convert transparent to white for custom template
                    img_layer = self._whiten_transparent(img_layer)
                flatten_img = flatten(img_layer, flatten_img)
        return flatten_img

    def _whiten_transparent(self, img):
        img = img.convert('RGBA')
        newImg = Image.new('RGBA', img.size, color.RGB_WHITE)
        newImg.paste(img, mask=img)
        return newImg

    def _make_transparent(self, img):
        transparent_img = Image.new('RGBA', img.size, (255, 255, 255, 0))
        mask = img.copy().convert('L')
        mask = mask.point(lambda x: 1 if x == color.TRANSPARENT else 0, mode='1')
        img = img.convert('RGBA')
        return Image.composite(transparent_img, img, mask)

    def _create_image_from_decoder(self, decoder, binary, palette=None, blank_hint=False, horizontal=False):
        bitmap, size, bpp = decoder.decode(binary, palette=palette, all_blank=blank_hint, horizontal=horizontal)
        if bpp == 32:
            img = Image.frombytes('RGBA', size, bitmap)
        elif bpp == 24:
            img = Image.frombytes('RGB', size, bitmap)
        elif bpp == 16 and isinstance(decoder, Decoder.PngDecoder):
            img = Image.frombytes('LA', size, bitmap)
        elif bpp == 16:
            img = Image.frombytes('I;16', size, bitmap)
        else:
            img = Image.frombytes('L', size, bitmap)
        return img

    def _get_layer_visibility(self, page):
        visibility = {}
        info = page.get_layer_info()
        if info is None:
            return visibility
        info_array = json.loads(info)
        for layer in info_array:
            is_bg_layer = layer.get('isBackgroundLayer')
            layer_id = layer.get('layerId')
            is_main_layer = (layer_id == 0) and (not is_bg_layer)
            is_visible = layer.get('isVisible')
            if is_bg_layer:
                visibility['BGLAYER'] = is_visible
            elif is_main_layer:
                visibility['MAINLAYER'] = is_visible
            else:
                visibility['LAYER' + str(layer_id)] = is_visible
        # some old files don't include MAINLAYER info, so we set MAINLAYER visible
        if visibility.get('MAINLAYER') is None:
            visibility['MAINLAYER'] = True
        return visibility

    def find_decoder(self, page, highres_grayscale=False):
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
            if highres_grayscale:
                return Decoder.RattaRleX2Decoder()
            else:
                return Decoder.RattaRleDecoder()
        else:
            raise exceptions.UnknownDecodeProtocol(f'unknown decode protocol: {protocol}')

    @staticmethod
    def build_visibility_overlay(
            background=VisibilityOverlay.DEFAULT,
            main=VisibilityOverlay.DEFAULT,
            layer1=VisibilityOverlay.DEFAULT,
            layer2=VisibilityOverlay.DEFAULT,
            layer3=VisibilityOverlay.DEFAULT):
        return {
            'BGLAYER': background,
            'MAINLAYER': main,
            'LAYER1': layer1,
            'LAYER2': layer2,
            'LAYER3': layer3,
        }


class SvgConverter:
    def __init__(self, notebook, palette=None):
        self.note = notebook
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
        page = self.note.get_page(page_number)
        horizontal = page.get_orientation() == fileformat.Page.ORIENTATION_HORIZONTAL
        page_width, page_height = (fileformat.PAGE_WIDTH, fileformat.PAGE_HEIGHT)
        if horizontal:
            page_height, page_width = (page_width, page_height)
        dwg = svgwrite.Drawing('dummy.svg', profile='full', size=(page_width, page_height))

        vo_only_bg = ImageConverter.build_visibility_overlay(
            background=VisibilityOverlay.VISIBLE,
            main=VisibilityOverlay.INVISIBLE,
            layer1=VisibilityOverlay.INVISIBLE,
            layer2=VisibilityOverlay.INVISIBLE,
            layer3=VisibilityOverlay.INVISIBLE)
        bg_img = self.image_converter.convert(page_number, visibility_overlay=vo_only_bg)
        buffer = BytesIO()
        bg_img.save(buffer, format='png')
        bg_b64str = base64.b64encode(buffer.getvalue()).decode('ascii')
        dwg.add(dwg.image('data:image/png;base64,' + bg_b64str, insert=(0, 0), size=(page_width, page_height)))

        vo_except_bg = ImageConverter.build_visibility_overlay(background=VisibilityOverlay.INVISIBLE)
        img = self.image_converter.convert(page_number, visibility_overlay=vo_except_bg)

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


class PdfConverter:
    def __init__(self, notebook, palette=None):
        self.note = notebook
        self.palette = palette
        self.pagesize = A4

    def convert(self, page_number, vectorize=False, enable_link=False):
        """Returns PDF data of the given page.

        Parameters
        ----------
        page_number : int
            page number to convert
        vectorize : bool
            convert handwriting to vector
        enable_link : bool
            enable page links and web links

        Returns
        -------
        data : bytes
            bytes of PDF data
        """
        if vectorize:
            converter = SvgConverter(self.note, self.palette)
            renderer_class = PdfConverter.SvgPageRenderer
        else:
            converter = ImageConverter(self.note, self.palette)
            renderer_class = PdfConverter.ImgPageRenderer
        imglist = self._create_image_list(converter, page_number)
        pdf_data = BytesIO()
        self._create_pdf(pdf_data, imglist, renderer_class, enable_link)
        return pdf_data.getvalue()

    def _create_image_list(self, converter, page_number):
        imglist = []
        if page_number < 0:
            # convert all pages
            total = self.note.get_total_pages()
            for i in range(total):
                img = converter.convert(i)
                imglist.append(img)
        else:
            img = converter.convert(page_number)
            imglist.append(img)
        return imglist

    def _create_pdf(self, buf, imglist, renderer_class, enable_link):
        c = canvas.Canvas(buf, pagesize=self.pagesize)
        for n, img in enumerate(imglist):
            page = self.note.get_page(n)
            horizontal = page.get_orientation() == fileformat.Page.ORIENTATION_HORIZONTAL
            pagesize = landscape(self.pagesize) if horizontal else portrait(self.pagesize)
            c.setPageSize(pagesize)
            renderer = renderer_class(img, pagesize)
            renderer.draw(c)
            if enable_link:
                pageid = page.get_pageid()
                if pageid is not None:
                    c.bookmarkPage(pageid)
                    self._add_links(c, n, renderer.get_scale())
            c.showPage()
        c.save()

    def _add_links(self, cvs, page_number, scale):
        links = self.note.get_links()
        for link in links:
            if link.get_page_number() != page_number:
                continue
            if link.get_inout() == fileformat.Link.DIRECTION_IN:
                # ignore income link
                continue
            link_type = link.get_type()
            is_internal_link = link.get_fileid() == self.note.get_fileid()
            if link_type == fileformat.Link.TYPE_PAGE_LINK and is_internal_link:
                tag = link.get_pageid()
                scaled_rect = self._calc_link_rect(link.get_rect(), scale)
                cvs.linkAbsolute("Link", tag, scaled_rect)
            elif link_type == fileformat.Link.TYPE_WEB_LINK:
                encoded_url = link.get_filepath()
                url = base64.b64decode(encoded_url).decode()
                scaled_rect = self._calc_link_rect(link.get_rect(), scale)
                cvs.linkURL(url, scaled_rect)

    def _calc_link_rect(self, rect, scale):
        (left, top, right, bottom) = rect
        (scale_x, scale_y) = scale
        (w, h) = self.pagesize
        return (left * scale_x, h - top * scale_y, right * scale_x, h - bottom * scale_y)

    class SvgPageRenderer:
        def __init__(self, svg, pagesize):
            self.svg = svg
            self.pagesize = pagesize
            self.drawing = svg2rlg(BytesIO(bytes(svg, 'ascii')))
            (w, h) = pagesize
            (self.scale_x, self.scale_y) = (w / self.drawing.width, h / self.drawing.height)
            self.drawing.scale(self.scale_x, self.scale_y)

        def get_scale(self):
            return (self.scale_x, self.scale_y)

        def draw(self, cvs):
            renderPDF.draw(self.drawing, cvs, 0, 0)

    class ImgPageRenderer:
        def __init__(self, img, pagesize):
            self.img = img
            self.pagesize = pagesize

        def get_scale(self):
            (w, h) = self.pagesize
            return (w / self.img.width, h / self.img.height)

        def draw(self, cvs):
            (w, h) = self.pagesize
            cvs.drawInlineImage(self.img, 0, 0, width=w, height=h)


class TextConverter:
    def __init__(self, notebook, palette=None):
        self.note = notebook
        self.palette = palette

    def convert(self, page_number):
        """Returns text of the given page if available.

        Parameters
        ----------
        page_number : int
            page number to convert

        Returns
        -------
        string
            a recognized text if available, otherwise None
        """
        if not self.note.is_realtime_recognition():
            return None
        page = self.note.get_page(page_number)
        if page.get_recogn_status() != fileformat.Page.RECOGNSTATUS_DONE:
            return None
        binary = page.get_recogn_text()
        decoder = Decoder.TextDecoder()
        text_list = decoder.decode(binary)
        if text_list is None:
            return None
        return ' '.join(text_list)
