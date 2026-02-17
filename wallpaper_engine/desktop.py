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

_worker_w = None


def _enum_callback(hwnd, lparam):
    """Callback for EnumWindows — find the WorkerW that has a SHELLDLL_DefView child."""
    global _worker_w
    shell_view = user32.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None)
    if shell_view:
        # The WorkerW we want is the one *after* this one
        _worker_w = user32.FindWindowExW(None, hwnd, "WorkerW", None)
    return True  # keep enumerating


def find_worker_w():
    """
    Find (or create) the WorkerW window that sits behind the desktop icons.

    Returns the HWND of the target WorkerW, or None on failure.
    """
    global _worker_w
    _worker_w = None

    # Step 1: Find Progman
    progman = user32.FindWindowW("Progman", None)
    if not progman:
        print("[desktop] ERROR: Could not find Progman window")
        return None

    # Step 2: Send the undocumented 0x052C message to spawn WorkerW
    result = wintypes.DWORD(0)
    SendMessageTimeoutW(progman, 0x052C, 0, 0, SMTO_NORMAL, 1000, ctypes.byref(result))

    # Step 3: Enumerate windows to find the right WorkerW
    user32.EnumWindows(EnumWindowsProc(_enum_callback), 0)

    if not _worker_w:
        print("[desktop] ERROR: Could not find WorkerW window")
        return None

    return _worker_w


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
