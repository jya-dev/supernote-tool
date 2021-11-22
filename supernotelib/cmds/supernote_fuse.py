#!/usr/bin/env python3

# Copyright (c) 2020 Ted M Lin
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

import logging

from collections import defaultdict
from errno import EACCES
from threading import Lock

import sys
import io

import os
import os.path

from fuse import FUSE, FuseOSError, Operations, LoggingMixIn

import supernotelib as sn

def is_pdf_note(path):
    if not path.endswith('.pdf') or os.path.exists(path):
        return False
    return os.path.exists(path[:-3] + 'note')

def path_from_pdf_note(path):
    if is_pdf_note(path):
        return path[:-3] + 'note'
    return path

class NoteToPdf(LoggingMixIn, Operations):
    def __init__(self, root):
        self.root = os.path.realpath(root)
        self.rwlock = Lock()
        self.files = {}
        self.data = defaultdict(bytes)

    def __call__(self, op, path, *args):
        return super(NoteToPdf, self).__call__(op, self.root + path, *args)

    def access(self, path, mode):
        path = path_from_pdf_note(path)
        if not os.access(path, mode):
            raise FuseOSError(EACCES)

    chmod = None
    chown = None
    create = None
    flush = None
    fsync = None

    def getattr(self, path, fh=None):
        if path in self.files:
            return self.files[path]

        path = path_from_pdf_note(path)
        st = os.lstat(path)
        return dict((key, getattr(st, key)) for key in ('st_atime', 'st_ctime',
            'st_gid', 'st_mode', 'st_mtime', 'st_nlink', 'st_size', 'st_uid'))

    getxattr = None
    link = None
    mkdir = None
    mknod = None

    def open(self, path, flags):
        if is_pdf_note(path):
            pdfpath = path
            path = path_from_pdf_note(path)

            # check if underlying file has changed
            updatecache = True
            if pdfpath in self.files:
                st = os.lstat(path)
                if st.st_mtime == self.files[pdfpath]['st_mtime']:
                    updatecache = False

            if updatecache:
                notebook = sn.load_notebook(path)
                converter = sn.converter.ImageConverter(notebook)

                imglist = []
                total = notebook.get_total_pages()
                for i in range(total):
                    img = converter.convert(i)
                    imglist.append(img.convert('RGB'))

                # TODO: can a note have zero pages? or fail?
                # ... generate a pdf with "error message"?
                buf = io.BytesIO()
                imglist[0].save(buf, format='PDF', save_all=True, append_images=imglist[1:])

                self.data[pdfpath] = buf.getvalue()

                self.files[pdfpath] = self.getattr(path)
                self.files[pdfpath]['st_size'] = len(self.data[pdfpath])

        # always open the original file (to get a handle)
        return os.open(path, flags)

    def read(self, path, size, offset, fh):
        with self.rwlock:
            if path in self.data:
                return self.data[path][offset:offset + size]

            os.lseek(fh, offset, 0)
            return os.read(fh, size)

    def readdir(self, path, fh):
        entries = []
        with os.scandir(path) as it:
            for entry in it:
                # passthrough all files, making a special pdf note
                entries.append(entry.name)
                if entry.name.endswith('.note'):
                    entries.append(entry.name[:-4] + 'pdf')
        return entries

    readlink = None

    def release(self, path, fh):
        return os.close(fh)

    rename = None
    rmdir = None

    def statfs(self, path):
        path = path_from_pdf_note(path)
        stv = os.statvfs(path)
        return dict((key, getattr(stv, key)) for key in ('f_bavail', 'f_bfree',
            'f_blocks', 'f_bsize', 'f_favail', 'f_ffree', 'f_files', 'f_flag',
            'f_frsize', 'f_namemax'))

    symlink = None
    truncate = None
    unlink = None
    utimens = os.utime
    write = None

def main():
    if len(sys.argv) != 3:
        print('usage: %s <root> <mountpoint>' % sys.argv[0])
        sys.exit(1)

    logging.basicConfig(level=logging.INFO)
    fuse = FUSE(NoteToPdf(sys.argv[1]), sys.argv[2], foreground=True)

if __name__ == '__main__':
    main()
