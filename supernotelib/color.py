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

"""Color classes."""

# color mode
MODE_GRAYSCALE = 'grayscale'
MODE_RGB = 'rgb'

# preset grayscale colors
BLACK = 0x00
DARK_GRAY = 0x9d
GRAY = 0xc9
WHITE = 0xfe
TRANSPARENT = 0xff

# preset RGB colors
RGB_BLACK = 0x000000
RGB_DARK_GRAY = 0x9d9d9d
RGB_GRAY = 0xc9c9c9
RGB_WHITE = 0xfefefe
RGB_TRANSPARENT = 0xffffff


def get_rgb(value):
    r = (value & 0xff0000) >> 16
    g = (value & 0x00ff00) >> 8
    b = value & 0x0000ff
    return (r, g, b)

def web_string(value, mode=MODE_RGB):
    if mode == MODE_GRAYSCALE:
        return '#' + (format(value & 0xff, '02x') * 3)
    else:
        r, g, b = get_rgb(value)
        return '#' + format(r & 0xff, '02x') + format(g & 0xff, '02x') + format(b & 0xff, '02x')


class ColorPalette:
    def __init__(self, mode=MODE_GRAYSCALE, colors=(BLACK, DARK_GRAY, GRAY, WHITE)):
        if mode not in [MODE_GRAYSCALE, MODE_RGB]:
            raise ValueError('mode must be MODE_GRAYSCALE or MODE_RGB')
        if len(colors) != 4:
            raise ValueError('colors must have 4 color values (black, darkgray, gray, white)')
        self.mode = mode
        self.black = colors[0]
        self.darkgray = colors[1]
        self.gray = colors[2]
        self.white = colors[3]
        if mode == MODE_GRAYSCALE:
            self.transparent = TRANSPARENT
        else:
            self.transparent = RGB_TRANSPARENT


DEFAULT_COLORPALETTE = ColorPalette(MODE_GRAYSCALE, (BLACK, DARK_GRAY, GRAY, WHITE))
DEFAULT_RGB_COLORPALETTE = ColorPalette(MODE_RGB, (RGB_BLACK, RGB_DARK_GRAY, RGB_GRAY, RGB_WHITE))
