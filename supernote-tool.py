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
import os

import supernotelib as sn


def subcommand_analyze(args):
    # show all metadata as JSON
    metadata = sn.parse_metadata(args.input)
    print(metadata.to_json(indent=2))

def subcommand_convert(args):
    notebook = sn.load_notebook(args.input)
    converter = sn.converter.ImageConverter(notebook)
    if args.all:
        basename, extension = os.path.splitext(args.output)
        total = notebook.get_total_pages()
        max_digits = len(str(total))
        for i in range(total):
            # append page number between filename and extension
            numbered_filename = basename + '_' + str(i).zfill(max_digits) + extension
            img = converter.convert(i)
            img.save(numbered_filename)
    else:
        img = converter.convert(args.number)
        img.save(args.output)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description='Unofficial python tool for Ratta Supernote')
    subparsers = parser.add_subparsers()

    # 'analyze' subcommand
    parser_analyze = subparsers.add_parser('analyze', help='analyze note file')
    parser_analyze.add_argument('input', type=str, help='input note file')
    parser_analyze.set_defaults(handler=subcommand_analyze)

    # 'convert' subcommand
    parser_convert = subparsers.add_parser('convert', help='image conversion')
    parser_convert.add_argument('input', type=str, help='input note file')
    parser_convert.add_argument('output', type=str, help='output image file')
    parser_convert.add_argument('-n', '--number', type=int, default=0, help='page number to be converted')
    parser_convert.add_argument('-a', '--all', action='store_true', default=False, help='convert all pages')
    parser_convert.set_defaults(handler=subcommand_convert)

    args = parser.parse_args()
    if hasattr(args, 'handler'):
        args.handler(args)
    else:
        parser.print_help()
