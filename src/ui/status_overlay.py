from __future__ import annotations

import queue
import ctypes
import threading
import time
import tkinter as tk
import sys
from collections import deque
from typing import Any


class RecordingOverlay:
    def __init__(self):
        self._queue: queue.Queue[tuple[str, Any]] = queue.Queue()
        self._ready = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=3)

    def show(self, mode: str) -> None:
        self.start()
        self._queue.put(("show", mode))

    def update_level(self, level: float) -> None:
        self._queue.put(("level", max(0.0, min(1.0, float(level)))))

    def set_status(self, status: str) -> None:
        self._queue.put(("status", status))

    def hide(self) -> None:
        self._queue.put(("hide", None))

    def destroy(self) -> None:
        self._queue.put(("destroy", None))

    def _run(self) -> None:
        root = tk.Tk()
        root.withdraw()
        window = _OverlayWindow(root, self._queue)
        self._ready.set()
        root.protocol("WM_DELETE_WINDOW", window.hide)
        root.mainloop()


class _OverlayWindow:
    WIDTH = 320
    HEIGHT = 78

    def __init__(self, root: tk.Tk, messages: queue.Queue[tuple[str, Any]]):
        self.root = root
        self.messages = messages
        self.visible = False
        self.mode = "transcribe"
        self.status = "Recording"
        self.levels: deque[float] = deque([0.0] * 24, maxlen=24)
        self.last_level_at = time.time()
        self.user_position: tuple[int, int] | None = None
        self._drag_offset: tuple[int, int] | None = None

        self.window = tk.Toplevel(root)
        self.window.withdraw()
        self.window.overrideredirect(True)
        self.window.attributes("-topmost", True)
        self.window.attributes("-alpha", 0.94)
        self.window.configure(bg="#101214")

        self.canvas = tk.Canvas(
            self.window,
            width=self.WIDTH,
            height=self.HEIGHT,
            highlightthickness=0,
            bg="#101214",
        )
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<ButtonPress-1>", self._start_drag)
        self.canvas.bind("<B1-Motion>", self._drag)
        self.canvas.bind("<ButtonRelease-1>", self._stop_drag)
        self.window.bind("<ButtonPress-1>", self._start_drag)
        self.window.bind("<B1-Motion>", self._drag)
        self.window.bind("<ButtonRelease-1>", self._stop_drag)

        self._place()
        self._poll()
        self._animate()

    def show(self, mode: str) -> None:
        self.mode = mode
        self.status = "Recording"
        self.visible = True
        self._place()
        self.window.deiconify()
        self.window.lift()
        self.draw()

    def hide(self) -> None:
        self.visible = False
        self.window.withdraw()

    def _place(self) -> None:
        if self.user_position is not None:
            x, y = self.user_position
            self._move_to(x, y)
            return
        _, _, screen_w, screen_h = self._screen_bounds()
        x = int((screen_w - self.WIDTH) / 2)
        y = min(int(screen_h * 0.76), screen_h - self.HEIGHT - 84)
        self._move_to(x, y)

    def _start_drag(self, event: tk.Event) -> None:
        cursor_x, cursor_y = self._cursor_position(event)
        window_x, window_y = self._window_position()
        self._drag_offset = (int(cursor_x - window_x), int(cursor_y - window_y))

    def _drag(self, event: tk.Event) -> None:
        if self._drag_offset is None:
            return
        offset_x, offset_y = self._drag_offset
        screen_x, screen_y, screen_w, screen_h = self._screen_bounds()
        visible_grip = 10
        min_x = screen_x - self.WIDTH + visible_grip
        max_x = screen_x + screen_w - visible_grip
        min_y = screen_y - self.HEIGHT + visible_grip
        max_y = screen_y + screen_h - visible_grip
        cursor_x, cursor_y = self._cursor_position(event)
        x = max(min_x, min(int(cursor_x - offset_x), max_x))
        y = max(min_y, min(int(cursor_y - offset_y), max_y))
        self.user_position = (x, y)
        self._move_to(x, y)

    def _stop_drag(self, event: tk.Event) -> None:
        self._drag_offset = None

    def _move_to(self, x: int, y: int) -> None:
        self.window.geometry(f"{self.WIDTH}x{self.HEIGHT}{x:+d}{y:+d}")
        if sys.platform == "win32":
            try:
                hwnd = int(self.window.winfo_id())
                hwnd_topmost = -1
                swp_nosize = 0x0001
                swp_noactivate = 0x0010
                ctypes.windll.user32.SetWindowPos(
                    hwnd,
                    hwnd_topmost,
                    int(x),
                    int(y),
                    0,
                    0,
                    swp_nosize | swp_noactivate,
                )
            except Exception:
                pass

    def _screen_bounds(self) -> tuple[int, int, int, int]:
        if sys.platform == "win32":
            try:
                user32 = ctypes.windll.user32
                old_context = None
                try:
                    old_context = user32.SetThreadDpiAwarenessContext(ctypes.c_void_p(-4))
                except Exception:
                    old_context = None
                bounds = (
                    int(user32.GetSystemMetrics(76)),
                    int(user32.GetSystemMetrics(77)),
                    int(user32.GetSystemMetrics(78)),
                    int(user32.GetSystemMetrics(79)),
                )
                if old_context:
                    try:
                        user32.SetThreadDpiAwarenessContext(old_context)
                    except Exception:
                        pass
                return bounds
            except Exception:
                pass
        return (0, 0, self.window.winfo_screenwidth(), self.window.winfo_screenheight())

    def _cursor_position(self, event: tk.Event) -> tuple[int, int]:
        if sys.platform == "win32":
            try:
                class POINT(ctypes.Structure):
                    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

                point = POINT()
                ctypes.windll.user32.GetCursorPos(ctypes.byref(point))
                return int(point.x), int(point.y)
            except Exception:
                pass
        return int(event.x_root), int(event.y_root)

    def _window_position(self) -> tuple[int, int]:
        if sys.platform == "win32":
            try:
                class RECT(ctypes.Structure):
                    _fields_ = [
                        ("left", ctypes.c_long),
                        ("top", ctypes.c_long),
                        ("right", ctypes.c_long),
                        ("bottom", ctypes.c_long),
                    ]

                rect = RECT()
                hwnd = int(self.window.winfo_id())
                ctypes.windll.user32.GetWindowRect(hwnd, ctypes.byref(rect))
                return int(rect.left), int(rect.top)
            except Exception:
                pass
        return int(self.window.winfo_x()), int(self.window.winfo_y())

    def _poll(self) -> None:
        while True:
            try:
                kind, payload = self.messages.get_nowait()
            except queue.Empty:
                break
            if kind == "show":
                self.show(str(payload or "transcribe"))
            elif kind == "level":
                self.levels.append(float(payload))
                self.last_level_at = time.time()
                if self.visible:
                    self.draw()
            elif kind == "status":
                self.status = str(payload or "Recording")
                if self.visible:
                    self.draw()
            elif kind == "hide":
                self.hide()
            elif kind == "destroy":
                self.root.quit()
                return
        self.root.after(30, self._poll)

    def _animate(self) -> None:
        if self.visible:
            if time.time() - self.last_level_at > 0.2:
                self.levels.append(max(0.0, self.levels[-1] * 0.82))
            self.draw()
        self.root.after(80, self._animate)

    def draw(self) -> None:
        c = self.canvas
        c.delete("all")
        self._round_rect(5, 5, self.WIDTH - 5, self.HEIGHT - 5, 28, fill="#171a1d", outline="#3b494b")
        self._round_rect(7, 7, self.WIDTH - 7, self.HEIGHT - 7, 26, fill="#171a1d", outline="#55d7ff")

        c.create_text(38, 38, text="TT", fill="#55d7ff", font=("Segoe UI", 22, "bold"))
        c.create_text(
            82,
            24,
            anchor="w",
            text=self.status,
            fill="#e7ecef",
            font=("Segoe UI", 11, "bold"),
        )
        c.create_text(
            82,
            45,
            anchor="w",
            text=("Translate" if self.mode == "translate" else "Transcribe"),
            fill="#8fa2aa",
            font=("Consolas", 9),
        )

        bars = list(self.levels)
        bar_w = 4
        gap = 4
        wave_left = 188
        wave_right = self.WIDTH - 24
        stride = bar_w + gap
        bar_count = max(1, int((wave_right - wave_left) / stride) + 1)
        center_y = 39
        for i, level in enumerate(bars[-bar_count:]):
            pulse = 0.18 if i % 3 == 0 else 0.0
            h = 7 + min(1.0, level + pulse) * 30
            x = wave_left + i * stride
            if x > wave_right:
                break
            c.create_line(x, center_y - h / 2, x, center_y + h / 2, fill="#55d7ff", width=bar_w, capstyle=tk.ROUND)

    def _round_rect(self, x1: int, y1: int, x2: int, y2: int, radius: int, **kwargs: Any) -> None:
        points = [
            x1 + radius,
            y1,
            x2 - radius,
            y1,
            x2,
            y1,
            x2,
            y1 + radius,
            x2,
            y2 - radius,
            x2,
            y2,
            x2 - radius,
            y2,
            x1 + radius,
            y2,
            x1,
            y2,
            x1,
            y2 - radius,
            x1,
            y1 + radius,
            x1,
            y1,
        ]
        self.canvas.create_polygon(points, smooth=True, splinesteps=24, **kwargs)
