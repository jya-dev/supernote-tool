import os
from rich.padding import Padding
from rich.panel import Panel
from rich.console import Console, ConsoleOptions, RenderResult, RenderableType
from rich.text import Text

from textual.app import App
from textual.widget import Widget
from textual.reactive import Reactive
from textual.widgets import Header, Footer, FileClick, ScrollView, DirectoryTree, Placeholder, Button, ButtonPressed, TreeClick

import re
import time
import glob
from pathlib import Path
import supernotelib as sn


SUPERNOTE_PATH = '/run/user/1000/gvfs/mtp:host=rockchip_Supernote_A5_X_SN100B10004997/Supernote'
SYNC_DIR = '/home/rohan/Desktop/Supernote_files/Notes_synced'


def convert_to_pdf(notebook_path, output_path, pdf_type='original'):
    notebook = sn.load_notebook(notebook_path)
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


class TextPanel(Widget):
    text = Reactive(None)

    def __init__(self, label, text=SUPERNOTE_PATH) -> None:
        super().__init__()
        self.text = text
        self.label = label

    def render(self) -> Panel:
        if self.text:
            return Panel(f"{self.label}: [bold cyan]{self.text}[/bold cyan]")
        return Panel(f"{self.label}: <no directory selected yet>")


class CustomButton(Widget):

    mouse_over = Reactive(False)
    label = Reactive("")

    def __init__(self, label, chosen_folder_panel: TextPanel, sync_dir_panel: TextPanel) -> None:
        super().__init__()
        self.label = label
        self.chosen_folder_panel = chosen_folder_panel
        self.sync_dir_panel = sync_dir_panel
        # self.console = console

    def on_enter(self) -> None:
        self.mouse_over = True

    def on_leave(self) -> None:
        self.mouse_over = False

    def on_click(self) -> None:
        self.log("#####SYNCING########")
        chosen_path = self.chosen_folder_panel.text
        sync_path = self.sync_dir_panel.text
        paths = glob.glob(f'{chosen_path}/**/*.note', recursive=True)
        self.log(paths)
        self.label = f'syncing {len(paths)} `.note` files'
        for i, p in enumerate(paths[:5]):
            # self.label = f'syncing {len(paths)} `.note` files\n{i+1}/{len(paths)} converted'
            time.sleep(1)
            # out_path = re.sub(chosen_path, sync_path, p)
            # out_path = re.sub(r'.note$', '.pdf', out_path)
            # # make dirs if needed
            # os.makedirs(Path(out_path).parent, exist_ok=True)
            # # convert to pdf
            # convert_to_pdf(
            #     notebook_path=p,
            #     output_path=out_path
            # )
        self.label = f'syncing {len(paths)} `.note` files complete!'

    def render(self):
        return Button(label=self.label, style='black on cyan' if not self.mouse_over else 'black on rgb(16,132,199)')


class MyApp(App):

    async def on_load(self) -> None:
        """Sent before going in to application mode."""
        # Bind our basic keys
        await self.bind("b", "view.toggle('sidebar')", "Toggle sidebar")
        await self.bind("q", "quit", "Quit")

        # Get path to show
        if os.path.isdir(SUPERNOTE_PATH):
            self.path = SUPERNOTE_PATH
        else:
            raise FileExistsError(
                f"Path {SUPERNOTE_PATH} doesn't exist. Is your supernote plugged in?")

    async def on_mount(self) -> None:
        """Call after terminal goes in to application mode"""
        # Create our widgets
        # In this a scroll view for the code and a directory tree
        self.directory = DirectoryTree(self.path, "Code")
        self.chosen_folder_panel = TextPanel(label="Supernote folder")
        self.sync_dir_panel = TextPanel(label="Sync directory", text=SYNC_DIR)
        self.sync_button = CustomButton(
            label="sync",
            chosen_folder_panel=self.chosen_folder_panel,
            sync_dir_panel=self.sync_dir_panel,
        )
        # Dock our widgets
        await self.view.dock(Header(tall=False), edge="top")
        await self.view.dock(Footer(), edge="bottom")

        await self.view.dock(
            ScrollView(self.directory), edge="left", size=30, name="sidebar"
        )
        await self.view.dock(self.chosen_folder_panel, self.sync_dir_panel, self.sync_button, edge="top")

    # def handle_button_pressed(self, message: ButtonPressed) -> None:
    #     """A message sent by the button widget"""

    #     assert isinstance(message.sender, Button)
    #     self.log(self.chosen_folder_panel.text)

    async def handle_tree_click(self, message: TreeClick) -> None:
        if message.node.data.is_dir:
            self.chosen_folder_panel.text = message.node.data.path


MyApp.run(title="Supernote sync", log="textual.log")
