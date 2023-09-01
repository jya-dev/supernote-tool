#!/usr/bin/env python3

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

import argparse
import io
import os
import sys

from colour import Color

import supernotelib as sn


def convert_all(converter, total, file_name, save_func):
    basename, extension = os.path.splitext(file_name)
    max_digits = len(str(total))
    for i in range(total):
        # append page number between filename and extention
        numbered_filename = basename + '_' + str(i).zfill(max_digits) + extension
        img = converter.convert(i)
        save_func(img, numbered_filename)

def convert_and_concat_all(converter, total, file_name, save_func):
    data = []
    for i in range(total):
        data.append(converter.convert(i))
    data = list(filter(lambda x : x is not None, data))
    if len(data) > 0:
        save_func('\n'.join(data), file_name)
    else:
        print('no data')

def subcommand_analyze(args):
    # show all metadata as JSON
    with open(args.input, 'rb') as f:
        metadata = sn.parse_metadata(f, policy=args.policy)
    print(metadata.to_json(indent=2))

def subcommand_convert(args):
    notebook = sn.load_notebook(args.input, policy=args.policy)
    total = notebook.get_total_pages()
    palette = None
    if args.color:
        try:
            colors = parse_color(args.color)
        except ValueError as e:
            print(e, file=sys.stderr)
            sys.exit(1)
        palette = sn.color.ColorPalette(sn.color.MODE_RGB, colors)
    if args.type == 'png':
        converter = sn.converter.ImageConverter(notebook, palette=palette)
        def save(img, file_name):
            img.save(file_name, format='PNG')
        if args.all:
            convert_all(converter, total, args.output, save)
        else:
            img = converter.convert(args.number)
            save(img, args.output)
    elif args.type == 'svg':
        converter = sn.converter.SvgConverter(notebook, palette=palette)
        def save(svg, file_name):
            if svg is not None:
                with open(file_name, 'w') as f:
                    f.write(svg)
            else:
                print('no path data')
        if args.all:
            convert_all(converter, total, args.output, save)
        else:
            svg = converter.convert(args.number)
            save(svg, args.output)
    elif args.type == 'pdf':
        vectorize = args.pdf_type == 'vector'
        use_link = not args.no_link
        converter = sn.converter.PdfConverter(notebook, palette=palette)
        def save(data, file_name):
            if data is not None:
                with open(file_name, 'wb') as f:
                    f.write(data)
            else:
                print('no data')
        if args.all:
            data = converter.convert(-1, vectorize, enable_link=use_link) # minus value means converting all pages
            save(data, args.output)
        else:
            data = converter.convert(args.number, vectorize, enable_link=use_link)
            save(data, args.output)
    elif args.type == 'txt':
        converter = sn.converter.TextConverter(notebook, palette=palette)
        def save(data, file_name):
            if data is not None:
                with open(file_name, 'w', encoding='utf-8') as f:
                    f.write(data)
            else:
                print('no data')
        if args.all:
            convert_and_concat_all(converter, total, args.output, save)
        else:
            data = converter.convert(args.number)
            save(data, args.output)

def subcommand_merge(args):
    num_input = len(args.input)
    if num_input == 1:          # reconstruct a note file
        notebook = sn.load_notebook(args.input[0])
        reconstructed_binary = sn.reconstruct(notebook)
        with open(args.output, 'wb') as f:
            f.write(reconstructed_binary)
    else:                       # merge multiple note files
        with open(args.input[0], 'rb') as f:
            merged_binary = f.read()
        for i in range(1, num_input):
            stream = io.BytesIO(merged_binary)
            merged_notebook = sn.load(stream)
            next_notebook = sn.load_notebook(args.input[i])
            merged_binary = sn.merge(merged_notebook, next_notebook)
        with open(args.output, 'wb') as f:
            f.write(merged_binary)

def subcommand_reconstruct(args):
    notebook = sn.load_notebook(args.input)
    reconstructed_binary = sn.reconstruct(notebook)
    with open(args.output, 'wb') as f:
        f.write(reconstructed_binary)

def parse_color(color_string):
    colorcodes = color_string.split(',')
    if len(colorcodes) != 4:
        raise ValueError(f'few color codes, 4 colors are required: {color_string}')
    black = int(Color(colorcodes[0]).hex_l[1:7], 16)
    darkgray = int(Color(colorcodes[1]).hex_l[1:7], 16)
    gray = int(Color(colorcodes[2]).hex_l[1:7], 16)
    white = int(Color(colorcodes[3]).hex_l[1:7], 16)
    return (black, darkgray, gray, white)


def main():
    parser = argparse.ArgumentParser(description='Unofficial python tool for Ratta Supernote')
    subparsers = parser.add_subparsers()

    # 'analyze' subcommand
    parser_analyze = subparsers.add_parser('analyze', help='analyze note file')
    parser_analyze.add_argument('input', type=str, help='input note file')
    parser_analyze.add_argument('--policy', choices=['strict', 'loose'], default='strict', help='select parser policy')
    parser_analyze.set_defaults(handler=subcommand_analyze)

    # 'convert' subcommand
    parser_convert = subparsers.add_parser('convert', help='image conversion')
    parser_convert.add_argument('input', type=str, help='input note file')
    parser_convert.add_argument('output', type=str, help='output image file')
    parser_convert.add_argument('-n', '--number', type=int, default=0, help='page number to be converted')
    parser_convert.add_argument('-a', '--all', action='store_true', default=False, help='convert all pages')
    parser_convert.add_argument('-c', '--color', type=str, help='colorize note with comma separated color codes in order of black, darkgray, gray and white.')
    parser_convert.add_argument('-t', '--type', choices=['png', 'svg', 'pdf', 'txt'], default='png', help='select conversion file type')
    parser_convert.add_argument('--pdf-type', choices=['original', 'vector'], default='original', help='select PDF conversion type')
    parser_convert.add_argument('--no-link', action='store_true', default=False, help='disable links in PDF')
    parser_convert.add_argument('--policy', choices=['strict', 'loose'], default='strict', help='select parser policy')
    parser_convert.set_defaults(handler=subcommand_convert)

    # 'merge' subcommand
    description = \
        '''
        (EXPERIMENTAL FEATURE)
        This command merge multiple note files to one.
        Backup your input files to save your data because you might get a corrupted output file.
        '''
    parser_merge = subparsers.add_parser('merge',
                                         description=description,
                                         help='merge multiple note files (EXPERIMENTAL FEATURE)')
    parser_merge.add_argument('input', type=str, nargs='+', help='input note files')
    parser_merge.add_argument('output', type=str, help='output note file')
    parser_merge.set_defaults(handler=subcommand_merge)

    # 'reconstruct' subcommand
    description = \
        '''
        (EXPERIMENTAL FEATURE)
        This command disassemble and reconstruct a note file for debugging and testing.
        Backup your input file to save your data because you might get a corrupted output file.
        '''
    parser_reconstruct = subparsers.add_parser('reconstruct',
                                               description=description,
                                               help='reconstruct a note file (EXPERIMENTAL FEATURE)')
    parser_reconstruct.add_argument('input', type=str, help='input note file')
    parser_reconstruct.add_argument('output', type=str, help='output note file')
    parser_reconstruct.set_defaults(handler=subcommand_reconstruct)

    args = parser.parse_args()
    if hasattr(args, 'handler'):
        args.handler(args)
    else:
        parser.print_help()

if __name__ == '__main__':
    main()
