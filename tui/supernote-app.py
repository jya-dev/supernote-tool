import os
import sys
from rich.console import RenderableType
from logging import getLogger
from rich.syntax import Syntax
from rich.traceback import Traceback

from textual.app import App
from textual.widgets import Header, Footer, FileClick, ScrollView, DirectoryTree, Placeholder, Button, ButtonPressed
log = getLogger("rich")


class MyApp(App):
    """An example of a very simple Textual App"""

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

        # Dock our widgets
        await self.view.dock(Header(), edge="top")
        await self.view.dock(Footer(), edge="bottom")

        # Note the directory is in a scroll view
        await self.view.dock(
            ScrollView(self.directory), edge="left", size=48, name="sidebar"
        )
        await self.view.dock(Placeholder(), Placeholder(), Button(label="Sync"), edge="top")

    async def handle_file_click(self, message: FileClick) -> None:
        """A message sent by the directory tree when a file is clicked."""
        print(message.path)

    def handle_button_pressed(self, message: ButtonPressed) -> None:
        """A message sent by the button widget"""

        assert isinstance(message.sender, Button)


# Run our app class
MyApp.run(title="Supernote sync", log="textual.log")
