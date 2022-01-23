# Copyright (c) 2021 jya
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

"""Utility classes."""

from . import fileformat

class WorkaroundPageWrapper(fileformat.Page):
    """Workaround for duplicated layer name."""
    def __init__(self, page_info):
        super().__init__(page_info)
        self._override_layer_name()

    @staticmethod
    def from_page(page):
        wrapped_page = WorkaroundPageWrapper(page.metadata)
        # copy contents from the original page object
        wrapped_page.set_content(page.get_content())
        wrapped_page.set_totalpath(page.get_totalpath())
        for i, layer in enumerate(page.get_layers()):
            wrapped_page.get_layer(i).set_content(layer.get_content())
        return wrapped_page

    def _override_layer_name(self):
        mainlayer_visited = False
        for layer in self.get_layers():
            name = layer.get_name()
            if name is None:
                continue
            if mainlayer_visited and name == 'MAINLAYER':
                # this layer has duplicated name, so we guess this layer is BGLAYER
                layer.metadata['LAYERNAME'] = 'BGLAYER'
            elif name == 'MAINLAYER':
                mainlayer_visited = True
