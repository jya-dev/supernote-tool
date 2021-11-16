import os
import supernotelib as sn
import glob
import re
from pathlib import Path
from tqdm import tqdm

SUPERNOTE_PATH = '/run/user/1000/gvfs/mtp:host=rockchip_Supernote_A5_X_SN100B10004997/Supernote/Note'

OUTPUT_PATH = './out'


assert os.path.exists(SUPERNOTE_PATH)
assert os.path.exists(OUTPUT_PATH)


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


for p in tqdm(glob.glob(f'{SUPERNOTE_PATH}/**/*.note', recursive=True)):
    out_path = re.sub(SUPERNOTE_PATH, OUTPUT_PATH, p)
    out_path = re.sub(r'.note$', '.pdf', out_path)
    # make dirs if needed
    os.makedirs(Path(out_path).parent, exist_ok=True)
    # convert to pdf
    convert_to_pdf(
        notebook_path=p,
        output_path=out_path
    )
