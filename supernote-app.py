import os
from rich.padding import Padding
from rich.panel import Panel
from rich.console import Console, ConsoleOptions, RenderResult, RenderableType
from rich.text import Text

from textual.app import App
from textual.widget import Widget
from textual.reactive import Reactive
from textual.widgets import Header, Footer, FileClick, ScrollView, DirectoryTree, Placeholder, Button, ButtonPressed, TreeClick
from pyfiglet import Figlet

import re
import glob
from pathlib import Path
from tqdm import tqdm
import supernotelib as sn


SUPERNOTE_PATH = '/run/user/1000/gvfs/mtp:host=rockchip_Supernote_A5_X_SN100B10004997/Supernote'
SYNC_DIR = '/home/rohan/Desktop/Supernote_files/Notes_synced'


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


class FigletText:
    """A renderable to generate figlet text that adapts to fit the container."""

    def __init__(self, text: str) -> None:
        self.text = text

    def __rich_console__(
        self, console: Console, options: ConsoleOptions
    ) -> RenderResult:
        """Build a Rich renderable to render the Figlet text."""
        size = min(options.max_width / 2, options.max_height)
        if size < 4:
            yield Text(self.text, style="bold")
        else:
            if size < 7:
                font_name = "mini"
            elif size < 8:
                font_name = "small"
            elif size < 10:
                font_name = "standard"
            else:
                font_name = "big"
            font = Figlet(font=font_name, width=options.max_width)
            yield Text(font.renderText(self.text).rstrip("\n"), style="bold")


class CustomButton(Widget):

    mouse_over = Reactive(False)

    def __init__(self, label, chosen_folder_panel: TextPanel) -> None:
        super().__init__()
        self.label = label
        self.chosen_folder_panel = chosen_folder_panel

    def on_enter(self) -> None:
        self.mouse_over = True

    def on_leave(self) -> None:
        self.mouse_over = False

    def on_click(self) -> None:
        self.log(self.chosen_folder_panel.text)

    def render(self):
        return Button(label=FigletText(
            self.label), style='black on cyan' if not self.mouse_over else 'black on rgb(16,132,199)')


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
            label="sync", chosen_folder_panel=self.chosen_folder_panel)
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
