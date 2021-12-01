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


# SUPERNOTE_PATH = '/run/user/1000/gvfs/mtp:host=rockchip_Supernote_A5_X_SN100B10004997/Supernote'
SUPERNOTE_PATH = '/home/rohan/Desktop/Supernote_files/Notes_synced'
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


class TrackState:
    chosen_dir = None
    sync_dir = None

    def __str__():
        print(
            f"chosen_dir:{TrackState.chosen_dir}\nchosen_dir:{TrackState.sync_dir}")


class TextPanel(Widget):
    text = Reactive(None)

    def __init__(self, label, text=SUPERNOTE_PATH, color='cyan') -> None:
        super().__init__()
        self.text = text
        self.label = label
        self.color = color

    def render(self) -> Panel:
        if self.text:
            return Panel(f"{self.label}: [bold {self.color}]{self.text}[/bold {self.color}]")
        return Panel(f"{self.label}: <no directory selected yet>")


class ConfirmButton(Widget):

    mouse_over = Reactive(False)

    def __init__(self, label, chosen_folder_panel: TextPanel, sync_dir_panel: TextPanel, quit_gui_fn) -> None:
        super().__init__()
        self.label = label
        self.chosen_folder_panel = chosen_folder_panel
        self.sync_dir_panel = sync_dir_panel
        self.quit_gui_fn = quit_gui_fn

    def on_enter(self) -> None:
        self.mouse_over = True

    def on_leave(self) -> None:
        self.mouse_over = False

    async def on_click(self) -> None:
        self.log(f"chosen dir is {self.chosen_folder_panel.text}")
        TrackState.chosen_dir = self.chosen_folder_panel.text
        TrackState.sync_dir = self.sync_dir_panel.text
        await self.quit_gui_fn()

    def render(self):
        return Button(label=self.label, style='black on cyan' if not self.mouse_over else 'black on rgb(16,132,199)')


class MyApp(App):

    async def on_load(self) -> None:
        # self.action_quit
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

    async def quit(self):
        await self.action_quit()

    async def on_mount(self) -> None:
        """Call after terminal goes in to application mode"""
        # Create our widgets
        # In this a scroll view for the code and a directory tree
        self.directory = DirectoryTree(self.path, "Code")
        self.chosen_folder_panel = TextPanel(
            label="Supernote folder")
        self.sync_dir_panel = TextPanel(
            label="Sync directory", text=SYNC_DIR, color="grey82")
        self.sync_button = ConfirmButton(
            label="select",
            chosen_folder_panel=self.chosen_folder_panel,
            sync_dir_panel=self.sync_dir_panel,
            quit_gui_fn=self.quit
        )
        # Dock our widgets
        await self.view.dock(Header(tall=False), edge="top")
        await self.view.dock(Footer(), edge="bottom")

        # await self.view.dock(
        #     ScrollView(self.directory), edge="left", name="sidebar"
        # )
        await self.view.dock(
            ScrollView(self.directory), edge="left", size=50, name="sidebar"
        )
        await self.view.dock(self.chosen_folder_panel, self.sync_dir_panel, self.sync_button, edge="top")

    # def handle_button_pressed(self, message: ButtonPressed) -> None:
    #     """A message sent by the button widget"""

    #     assert isinstance(message.sender, Button)
    #     self.log(self.chosen_folder_panel.text)

    async def handle_tree_click(self, message: TreeClick) -> None:
        if message.node.data.is_dir:
            self.chosen_folder_panel.text = message.node.data.path


if __name__ == '__main__':
    MyApp.run(title="Supernote sync", log="textual.log")
    print(TrackState.sync_dir)
    print(TrackState.chosen_dir)
