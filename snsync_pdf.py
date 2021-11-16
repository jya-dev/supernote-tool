
import time
from PIL import Image, ImageChops
import os
from io import BytesIO
from colour import Color
from io import BytesIO, StringIO
import base64
import supernotelib as sn
import glob

SUPERNOTE_PATH = '/run/user/1000/gvfs/mtp:host=rockchip_Supernote_A5_X_SN100B10004997/Supernote/Note'

OUTPUT_PATH = './out'


assert os.path.exists(SUPERNOTE_PATH)


def convert_all(converter, total, file_name, save_func):
    basename, extension = os.path.splitext(file_name)
    max_digits = len(str(total))
    for i in range(total):
        # append page number between filename and extention
        numbered_filename = basename + '_' + \
            str(i).zfill(max_digits) + extension
        img = converter.convert(i)
        save_func(img, numbered_filename)


def subcommand_analyze(args):
    # show all metadata as JSON
    metadata = sn.parse_metadata(args.input)
    print(metadata.to_json(indent=2))


def convert_to_pdf(notebook_path, output_path, pdf_type='original'):
    notebook = sn.load_notebook(notebook_path)
    total = notebook.get_total_pages()
    palette = None
    vectorize = pdf_type == 'vector'
    converter = sn.converter.PdfConverter(notebook, palette=palette)

    def save(data, file_name):
        if data is not None:
            with open(file_name, 'wb') as f:
                f.write(data)
        else:
            print('no data')
    data = converter.convert(-1, vectorize)
    save(data, output_path)


for p in glob.glob(f'{SUPERNOTE_PATH}/**/*.note', recursive=True):
    print(p)
    filename = os.path.split(p)[-1].replace('.note', '')
    convert_to_pdf(p, f'{OUTPUT_PATH}/{filename}.pdf')
    break
