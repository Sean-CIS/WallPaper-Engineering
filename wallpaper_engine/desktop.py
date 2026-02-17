"""
Windows desktop wallpaper embedding.

Uses the Win32 API to embed a pygame window behind the desktop icons,
turning it into a live animated wallpaper — the same technique used by
Wallpaper Engine and Lively Wallpaper.

How it works:
  1. Find the "Progman" window (the shell desktop).
  2. Send it message 0x052C to spawn a WorkerW layer.
  3. Enumerate top-level windows to find the empty WorkerW that sits
     below the icon layer but above Progman's static wallpaper.
  4. Re-parent our pygame window into that WorkerW so it renders
     behind desktop icons but above the static wallpaper.
"""

import sys
import time
import struct
import ctypes
import ctypes.wintypes as wintypes

# Only usable on Windows
if sys.platform != "win32":
    raise ImportError("desktop.py requires Windows")

user32 = ctypes.windll.user32
kernel32 = ctypes.windll.kernel32

# Make this process DPI-aware so we get real physical pixel sizes
# instead of logical (scaled) sizes. Must be called BEFORE any
# GetSystemMetrics / GetWindowRect calls.
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        user32.SetProcessDPIAware()  # Fallback for older Windows
    except Exception:
        pass

# Detect 64-bit Python (need SetWindowLongPtrW on 64-bit)
_is_64bit = struct.calcsize("P") == 8

# Win32 constants
GWLP_STYLE = -16
GWLP_EXSTYLE = -20
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


def _get_window_long(hwnd, index):
    """Get window long value — uses Ptr variant on 64-bit."""
    if _is_64bit:
        user32.GetWindowLongPtrW.restype = ctypes.c_longlong
        user32.GetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int]
        return user32.GetWindowLongPtrW(hwnd, index)
    else:
        user32.GetWindowLongW.restype = wintypes.LONG
        user32.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        return user32.GetWindowLongW(hwnd, index)


def _set_window_long(hwnd, index, value):
    """Set window long value — uses Ptr variant on 64-bit."""
    if _is_64bit:
        user32.SetWindowLongPtrW.restype = ctypes.c_longlong
        user32.SetWindowLongPtrW.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_longlong]
        return user32.SetWindowLongPtrW(hwnd, index, value)
    else:
        user32.SetWindowLongW.restype = wintypes.LONG
        user32.SetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int, wintypes.LONG]
        return user32.SetWindowLongW(hwnd, index, value)


def _find_wallpaper_worker_w():
    """
    Enumerate top-level windows to find the WorkerW we should parent into.

    After the 0x052C message, the desktop Z-order (top to bottom) is:

        WorkerW  (contains SHELLDLL_DefView — the icon layer)
        WorkerW  (empty — sits BELOW icons, ABOVE Progman's wallpaper)
        Progman  (bottom — paints the static wallpaper)

    We find the WorkerW that holds SHELLDLL_DefView, then grab its next
    sibling WorkerW. That empty sibling is the correct parent for our
    pygame window — anything rendered inside it appears behind the desktop
    icons but above the static wallpaper.  This is the technique used by
    Lively Wallpaper, Wallpaper Engine, and every other live wallpaper app.
    """
    found = [None]

    def callback(hwnd, lparam):
        shell_view = user32.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None)
        if shell_view:
            # The empty WorkerW is the NEXT sibling after this one
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
        worker_w = _find_wallpaper_worker_w()
        if worker_w:
            break
        time.sleep(0.2)

    if not worker_w:
        print("[desktop] ERROR: Could not find WorkerW window after retries")
        return None

    return worker_w


def get_worker_w_size():
    """
    Find the WorkerW and return its (hwnd, width, height) in physical pixels.
    Returns (None, 0, 0) if WorkerW can't be found.
    """
    worker_w = find_worker_w()
    if not worker_w:
        return None, 0, 0
    rect = wintypes.RECT()
    user32.GetWindowRect(worker_w, ctypes.byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    return worker_w, w, h


def embed_pygame_window(pygame_hwnd, worker_w, width, height):
    """
    Embed a pygame window as the desktop wallpaper behind icons.

    No windows need to be hidden — the empty WorkerW is already
    positioned correctly in the Z-order.

    Args:
        pygame_hwnd: The HWND of the pygame window.
        worker_w: The HWND of the target WorkerW.
        width: Physical pixel width of the WorkerW.
        height: Physical pixel height of the WorkerW.

    Returns:
        True on success, False on failure.
    """
    if not worker_w:
        return False

    # Strip window chrome — we want a bare frameless surface
    style = _get_window_long(pygame_hwnd, GWLP_STYLE)
    style &= ~(WS_CAPTION | WS_THICKFRAME | WS_SYSMENU | WS_MAXIMIZEBOX | WS_MINIMIZEBOX | WS_POPUP)
    style |= WS_CHILD | WS_VISIBLE
    _set_window_long(pygame_hwnd, GWLP_STYLE, style)

    # Strip extended styles that can interfere with rendering
    ex_style = _get_window_long(pygame_hwnd, GWLP_EXSTYLE)
    ex_style &= ~(0x00020000 | 0x00000200 | 0x00000100 | 0x00080000 | 0x00000001)
    # WS_EX_DLGMODALFRAME | WS_EX_CLIENTEDGE | WS_EX_STATICEDGE | WS_EX_LAYERED | WS_EX_COMPOSITED
    ex_style |= WS_EX_TOOLWINDOW
    _set_window_long(pygame_hwnd, GWLP_EXSTYLE, ex_style)

    # Parent into the empty WorkerW (behind icons, above wallpaper)
    user32.SetParent(pygame_hwnd, worker_w)

    # Resize to fill the desktop
    user32.SetWindowPos(pygame_hwnd, None, 0, 0, width, height,
                        SWP_NOZORDER | SWP_NOACTIVATE | SWP_SHOWWINDOW)

    print(f"[desktop] Embedded into WorkerW ({width}x{height})")
    return True


def get_desktop_resolution():
    """Return (width, height) of the primary monitor in physical pixels."""
    return user32.GetSystemMetrics(0), user32.GetSystemMetrics(1)


def detach_pygame_window(pygame_hwnd):
    """
    Remove the pygame window from the desktop layer (restore to normal window).
    """
    desktop = user32.GetDesktopWindow()
    user32.SetParent(pygame_hwnd, desktop)

    style = _get_window_long(pygame_hwnd, GWLP_STYLE)
    style &= ~WS_CHILD
    style |= WS_POPUP | WS_VISIBLE | WS_CAPTION | WS_SYSMENU | WS_THICKFRAME
    _set_window_long(pygame_hwnd, GWLP_STYLE, style)
