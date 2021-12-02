import os
from rich.padding import Padding
from rich.panel import Panel
from rich import print as richprint
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
from tqdm import tqdm


SUPERNOTE_PATH = '/run/user/1000/gvfs/mtp:host=rockchip_Supernote_A5_X_SN100B10004997/Supernote/Note'
# SUPERNOTE_PATH = '/home/rohan/Desktop/Supernote_files/Notes_synced'
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

        await self.view.dock(
            ScrollView(self.directory), edge="left", size=50, name="sidebar"
        )
        await self.view.dock(self.chosen_folder_panel, self.sync_dir_panel, self.sync_button, edge="top")

    async def handle_tree_click(self, message: TreeClick) -> None:
        if message.node.data.is_dir:
            self.chosen_folder_panel.text = message.node.data.path


def get_user_input(prompt: str) -> bool:
    x = input(prompt)
    while x.lower() not in ['y', 'n']:
        x = input(prompt)
    return True if x.lower() == 'y' else False


def main():
    if not os.path.exists(SYNC_DIR):
        richprint(
            f"[red]Local sync directory path not found. Double check the path in the config file.[red]")
        return
    if os.path.exists(SUPERNOTE_PATH):
        richprint(
            f"Path to local sync folder: [bold cyan]{SYNC_DIR}[/bold cyan]")
        richprint(
            f"Path to supernote folder: [bold cyan]{SUPERNOTE_PATH}[/bold cyan]")
        change_supernote_path = get_user_input(
            "Change folder to sync in supernote? (y/n): ")
        chosen_dir = SUPERNOTE_PATH
        sync_dir = SYNC_DIR

        if change_supernote_path:
            MyApp.run(title="Supernote sync", log="textual.log")
            if TrackState.sync_dir == None or TrackState.chosen_dir == None:
                richprint(
                    f"[red]No folder selected in supernote[red]")
                return

            sync_dir = TrackState.sync_dir
            chosen_dir = TrackState.chosen_dir
        richprint(
            f"Path to supernote folder: [bold cyan]{chosen_dir}[/bold cyan]")
        for p in tqdm(glob.glob(f'{chosen_dir}/**/*.note', recursive=True)):
            out_path = re.sub(SUPERNOTE_PATH, sync_dir, p)
            out_path = re.sub(r'.note$', '.pdf', out_path)
            # make dirs if needed
            os.makedirs(Path(out_path).parent, exist_ok=True)
            # convert to pdf
            convert_to_pdf(
                notebook_path=p,
                output_path=out_path
            )
        richprint(f"[bold cyan]Sync complete[/bold cyan]")
    else:
        richprint(
            f"[red]Supernote path not found. Double check the path in the config file.[red]")


if __name__ == '__main__':
    main()
