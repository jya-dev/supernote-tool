
import time
from PIL import Image, ImageChops
import zlib
from os.path import exists
import os
from io import BytesIO
from colour import Color
from io import BytesIO, StringIO
import base64
import supernotelib as sn


def img_to_base64_str(img):
    buffered = BytesIO()
    img.save(buffered, format="PNG")
    buffered.seek(0)
    img_64 = base64.b64encode(buffered.getvalue()).decode()
    img_str = f"data:image/png;base64,{img_64}"
    return img_str


def crc32(fileName):
    with open(fileName, 'rb') as fh:
        hash = 0
        while True:
            s = fh.read(65536)
            if not s:
                break
            hash = zlib.crc32(s, hash)
        return "%08X" % (hash & 0xFFFFFFFF)


def img_trim(im):
    bg = Image.new(im.mode, im.size, im.getpixel((0, 0)))
    diff = ImageChops.difference(im, bg)
    diff = ImageChops.add(diff, diff, 2.0, -100)
    bbox = diff.getbbox()
    if bbox:
        return im.crop(bbox)


sn_path = r"D:\Dropbox\Supernote\Note"
dest_path = r"D:\Dropbox\Notes"
zoom = 0.5


folders_found = []
files_found = []

for f_inf in os.walk(sn_path):

    new_path = dest_path + f_inf[0].replace(sn_path, '')

    for d in f_inf[1]:
        dir_path = new_path + '\\' + d
        if not os.path.exists(dir_path):
            os.mkdir(dir_path)
        folders_found += [dir_path]

    for f in f_inf[2]:

        note_path = f_inf[0] + '\\' + f
        n_name = f.replace('.note', '')
        html_path = new_path + '\\' + f.replace('.note', '.html')

        f_crc = crc32(note_path)

        if os.path.exists(html_path):
            with open(html_path) as f:
                crc_line = next(f)
                if len(crc_line) > 10:
                    crc_line = crc_line[4:-4]

            if crc_line == str(f_crc):
                #print(f"[CRC OK] {note_path}")
                files_found += [html_path]
                continue
            else:
                os.remove(html_path)

        file_str = StringIO()

        file_str.write(f"<!--{f_crc}-->\n<title>{n_name}</title>")
        file_str.write("""
        <style> 
        * {font-size:10px}
        img, .fail {background-color:white; padding:10px;border:1px solid #AAAAAA, font-size:20px;font-weight:bold}
        td {padding:5px;}
        
        </style>
        
        <body style=background-color:#EEEEEE><table>""")

        notebook = sn.load_notebook(note_path)
        total_pages = notebook.get_total_pages()

        converter = sn.converter.ImageConverter(notebook)
        for i in range(0, total_pages):
            try:

                img = converter.convert(i)
                img_w = int(img.width*zoom)
                img_h = int(img.height*zoom)

                #img = img_trim(img.resize((img_w, img_h)))

                img64 = img_to_base64_str(img)

                file_str.write(
                    f'<tr><td valign=top>{i}<td><img src="{img64}" width={img_w} height={img_h}>')

            except:
                file_str.write(
                    f'<tr><td valign=top>{i}<td><div class=fail>Failed</div>')
                print(f"[FAIL] {note_path} page {i}")

        with open(html_path, 'w') as f:
            f.write(file_str.getvalue())
            print(f"[OK] {note_path}")

        files_found += [html_path]


for f_inf in os.walk(dest_path):
    for d in f_inf[2]:
        f_path = f_inf[0] + '\\' + d
        if f_path not in files_found:
            os.remove(f_path)

for f_inf in os.walk(dest_path):
    for d in f_inf[1]:
        dir_path = f_inf[0] + '\\' + d
        if dir_path not in folders_found:
            os.rmdir(dir_path)


print(f"Notes synced")
time.sleep(0.5)

# %%
