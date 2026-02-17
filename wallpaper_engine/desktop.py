"""
Windows desktop wallpaper embedding.

Uses the Win32 API to embed a pygame window behind the desktop icons,
turning it into a live animated wallpaper — the same technique used by
Wallpaper Engine.

How it works:
  1. Find the "Progman" window (the shell desktop).
  2. Send it message 0x052C to spawn a hidden WorkerW layer.
  3. Enumerate top-level windows to locate the WorkerW that sits
     between Progman and the icon layer.
  4. Re-parent our pygame window into that WorkerW so it renders
     as the desktop background.
"""

import sys
import time
import ctypes
import ctypes.wintypes as wintypes

# Only usable on Windows
if sys.platform != "win32":
    raise ImportError("desktop.py requires Windows")

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Win32 constants
GWL_STYLE = -16
GWL_EXSTYLE = -20
WS_CHILD = 0x40000000
WS_POPUP = 0x80000000
WS_VISIBLE = 0x10000000
WS_CAPTION = 0x00C00000
WS_THICKFRAME = 0x00040000
WS_SYSMENU = 0x00080000
WS_MAXIMIZEBOX = 0x00010000
WS_MINIMIZEBOX = 0x00020000
WS_EX_TOOLWINDOW = 0x00000080
SWP_NOACTIVATE = 0x0010
SWP_NOZORDER = 0x0004
SWP_SHOWWINDOW = 0x0040
SMTO_NORMAL = 0x0000

# Function signatures
SendMessageTimeoutW = user32.SendMessageTimeoutW
SendMessageTimeoutW.restype = wintypes.LPARAM
SendMessageTimeoutW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
    wintypes.UINT, wintypes.UINT, ctypes.POINTER(wintypes.DWORD)
]

EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)


def _find_worker_w_enum():
    """
    Enumerate all top-level windows to find the WorkerW that contains
    a SHELLDLL_DefView child — then grab the WorkerW *after* it.
    """
    found = [None]

    def callback(hwnd, lparam):
        shell_view = user32.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None)
        if shell_view:
            # The WorkerW we want is the NEXT sibling after this one
            found[0] = user32.FindWindowExW(None, hwnd, "WorkerW", None)
        return True  # keep enumerating

    # IMPORTANT: store the callback in a variable so it doesn't get
    # garbage-collected while EnumWindows is still calling it
    cb = EnumWindowsProc(callback)
    user32.EnumWindows(cb, 0)
    return found[0]


def find_worker_w():
    """
    Find (or create) the WorkerW window that sits behind the desktop icons.

    Sends the undocumented 0x052C message to Progman to spawn the WorkerW,
    then enumerates windows to find it. Retries a few times if needed since
    the WorkerW doesn't always appear instantly.

    Returns the HWND of the target WorkerW, or None on failure.
    """
    # Step 1: Find Progman
    progman = user32.FindWindowW("Progman", None)
    if not progman:
        print("[desktop] ERROR: Could not find Progman window")
        return None

    # Step 2: Send the undocumented 0x052C message to spawn WorkerW
    # Send it twice — some Windows versions need that
    result = wintypes.DWORD(0)
    SendMessageTimeoutW(progman, 0x052C, 0xD, 0, SMTO_NORMAL, 1000, ctypes.byref(result))
    SendMessageTimeoutW(progman, 0x052C, 0xD, 1, SMTO_NORMAL, 1000, ctypes.byref(result))

    # Step 3: Enumerate windows to find the right WorkerW
    # Retry a few times — WorkerW can take a moment to appear
    worker_w = None
    for attempt in range(5):
        worker_w = _find_worker_w_enum()
        if worker_w:
            break
        time.sleep(0.2)

    if not worker_w:
        # Fallback: try sending Progman to the bottom and rendering directly
        # into Progman's first WorkerW child
        worker_w = user32.FindWindowExW(progman, None, "WorkerW", None)

    if not worker_w:
        print("[desktop] ERROR: Could not find WorkerW window after retries")
        return None

    return worker_w


def embed_pygame_window(pygame_hwnd):
    """
    Embed a pygame window into the desktop WorkerW layer.

    Args:
        pygame_hwnd: The HWND of the pygame window (from pygame.display.get_wm_info).

    Returns:
        True on success, False on failure.
    """
    worker_w = find_worker_w()
    if not worker_w:
        return False

    # Strip window chrome — we want a bare frameless surface
    style = user32.GetWindowLongW(pygame_hwnd, GWL_STYLE)
    style &= ~(WS_CAPTION | WS_THICKFRAME | WS_SYSMENU | WS_MAXIMIZEBOX | WS_MINIMIZEBOX | WS_POPUP)
    style |= WS_CHILD | WS_VISIBLE
    user32.SetWindowLongW(pygame_hwnd, GWL_STYLE, style)

    # Remove tool-window extended style
    ex_style = user32.GetWindowLongW(pygame_hwnd, GWL_EXSTYLE)
    ex_style |= WS_EX_TOOLWINDOW
    user32.SetWindowLongW(pygame_hwnd, GWL_EXSTYLE, ex_style)

    # Re-parent into the WorkerW
    user32.SetParent(pygame_hwnd, worker_w)

    # Resize to fill the desktop
    rect = wintypes.RECT()
    user32.GetWindowRect(worker_w, ctypes.byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    user32.SetWindowPos(pygame_hwnd, None, 0, 0, w, h, SWP_NOZORDER | SWP_NOACTIVATE | SWP_SHOWWINDOW)

    print(f"[desktop] Embedded into desktop ({w}x{h})")
    return True


def get_desktop_resolution():
    """Return (width, height) of the primary monitor."""
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def detach_pygame_window(pygame_hwnd):
    """
    Remove the pygame window from the desktop layer (restore to normal window).
    """
    desktop = user32.GetDesktopWindow()
    user32.SetParent(pygame_hwnd, desktop)

    style = user32.GetWindowLongW(pygame_hwnd, GWL_STYLE)
    style &= ~WS_CHILD
    style |= WS_POPUP | WS_VISIBLE | WS_CAPTION | WS_SYSMENU | WS_THICKFRAME
    user32.SetWindowLongW(pygame_hwnd, GWL_STYLE, style)
