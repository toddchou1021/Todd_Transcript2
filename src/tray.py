from __future__ import annotations

import threading
from pathlib import Path
from typing import Callable

from PIL import Image
import pystray


class TrayController:
    def __init__(self, icon_path: Path, on_show: Callable[[], None], on_exit: Callable[[], None]) -> None:
        self.icon_path = icon_path
        self.on_show = on_show
        self.on_exit = on_exit
        self._icon: pystray.Icon | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._icon:
            return
        image = Image.open(self.icon_path)
        self._icon = pystray.Icon(
            "Todd Transcript",
            image,
            "Todd Transcript",
            menu=pystray.Menu(
                pystray.MenuItem("Show Todd Transcript", self._show, default=True),
                pystray.MenuItem("Exit", self._exit),
            ),
        )
        self._thread = threading.Thread(target=self._icon.run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._icon:
            self._icon.stop()
            self._icon = None

    def _show(self, _icon=None, _item=None) -> None:
        self.on_show()

    def _exit(self, _icon=None, _item=None) -> None:
        self.on_exit()
