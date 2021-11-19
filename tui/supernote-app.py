import os
import sys
from rich.panel import Panel

from textual.app import App
from textual.widget import Widget
from textual.reactive import Reactive
from textual.widgets import Header, Footer, FileClick, ScrollView, DirectoryTree, Placeholder, Button, ButtonPressed, TreeClick


class TextPanel(Widget):
    chosenpath = Reactive(None)

    def __init__(self, chosenpath=None) -> None:
        super().__init__()
        self.chosenpath = chosenpath

    def render(self) -> Panel:
        if self.chosenpath:
            return Panel(f"Chosen path: [bold cyan]{self.chosenpath}[/bold cyan]")
        return Panel("Chosen path: <no directory selected yet>")


class MyApp(App):

    async def on_load(self) -> None:
        """Sent before going in to application mode."""
        # Bind our basic keys
        await self.bind("b", "view.toggle('sidebar')", "Toggle sidebar")
        await self.bind("q", "quit", "Quit")

        # Get path to show
        try:
            self.path = sys.argv[1]
        except IndexError:
            self.path = os.path.abspath(
                os.path.join(os.path.basename(__file__), "../../")
            )

    async def on_mount(self) -> None:
        """Call after terminal goes in to application mode"""

        # Create our widgets
        # In this a scroll view for the code and a directory tree
        self.directory = DirectoryTree(self.path, "Code")
        self.chosen_folder_panel = TextPanel()

        # Dock our widgets
        await self.view.dock(Header(tall=False), edge="top")
        await self.view.dock(Footer(), edge="bottom")

        await self.view.dock(
            ScrollView(self.directory), edge="left", size=30, name="sidebar"
        )
        await self.view.dock(self.chosen_folder_panel, Placeholder(), Button(label="Sync"), edge="top")

    async def handle_file_click(self, message: FileClick) -> None:
        """A message sent by the directory tree when a file is clicked."""
        self.log(message.path)

    def handle_button_pressed(self, message: ButtonPressed) -> None:
        """A message sent by the button widget"""

        assert isinstance(message.sender, Button)
        self.log("hi")

    async def handle_tree_click(self, message: TreeClick) -> None:
        self.log("###########")
        self.log(message.node.data.is_dir)
        self.log(message.node.data.path)
        self.log("###########")
        if message.node.data.is_dir:
            self.chosen_folder_panel.chosenpath = message.node.data.path

        self.log("###########")


        # Run our app class
MyApp.run(title="Supernote sync", log="textual.log")
