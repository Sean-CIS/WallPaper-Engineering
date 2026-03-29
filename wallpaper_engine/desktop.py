"""
Windows desktop wallpaper embedding.

Uses the Win32 API to embed a pygame window behind the desktop icons,
turning it into a live animated wallpaper — the same technique used by
Wallpaper Engine and Lively Wallpaper.

How it works:
  1. Find the "Progman" window (the shell desktop).
  2. Send it message 0x052C to spawn a WorkerW layer.
  3. Detect the desktop layout:

     Layout A (Win10, some Win11):
         Top-level WorkerW  (contains SHELLDLL_DefView — icons)
         Top-level WorkerW  (empty — our target, below icons)
         Progman            (bottom)
       → Parent into the empty top-level WorkerW.

     Layout B (Win11 24H2+):
         Progman
           ├── SHELLDLL_DefView  (icons)
           └── WorkerW           (static wallpaper)
       → Parent into Progman directly, position below icons,
         and HIDE the WorkerW to stop the static wallpaper from
         painting over our content.

  4. Re-parent our pygame window so it renders behind desktop icons.
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
GW_CHILD = 5
GW_HWNDNEXT = 2
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
SW_HIDE = 0
SW_SHOW = 5

# Function signatures
SendMessageTimeoutW = user32.SendMessageTimeoutW
SendMessageTimeoutW.restype = wintypes.LPARAM
SendMessageTimeoutW.argtypes = [
    wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM,
    wintypes.UINT, wintypes.UINT, ctypes.POINTER(wintypes.DWORD)
]

EnumWindowsProc = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

# Module-level state for cleanup
_hidden_worker_w = None  # WorkerW we hid in Layout B (must restore on exit)
_embed_layout = None      # "A" or "B"


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


def _get_class_name(hwnd):
    """Get the window class name."""
    buf = ctypes.create_unicode_buffer(256)
    user32.GetClassNameW(hwnd, buf, 256)
    return buf.value


def _detect_layout():
    """
    Detect which desktop layout is active and return the embed target.

    Returns:
        ("A", worker_w_hwnd):  Layout A — target is a top-level empty WorkerW
        ("B", progman_hwnd, sdv_hwnd, worker_w_hwnd):
                               Layout B — target is Progman; SDV and WorkerW are children
        (None,):               Could not detect layout
    """
    progman = user32.FindWindowW("Progman", None)
    if not progman:
        return (None,)

    # --- Layout A: SHELLDLL_DefView inside a top-level WorkerW ---
    found_a = [None]

    def callback(hwnd, lparam):
        shell_view = user32.FindWindowExW(hwnd, None, "SHELLDLL_DefView", None)
        if shell_view:
            # The NEXT top-level WorkerW after this one is our target
            found_a[0] = user32.FindWindowExW(None, hwnd, "WorkerW", None)
        return True

    cb = EnumWindowsProc(callback)
    user32.EnumWindows(cb, 0)

    if found_a[0]:
        return ("A", found_a[0])

    # --- Layout B: SHELLDLL_DefView is a direct child of Progman ---
    sdv = user32.FindWindowExW(progman, None, "SHELLDLL_DefView", None)
    worker_w = user32.FindWindowExW(progman, None, "WorkerW", None)

    if sdv and worker_w:
        return ("B", progman, sdv, worker_w)

    # Fallback: just a WorkerW child of Progman, no SDV found yet
    if worker_w:
        return ("B", progman, None, worker_w)

    return (None,)


def find_worker_w():
    """
    Find (or create) the desktop embed target.

    Sends the undocumented 0x052C message to Progman to spawn the WorkerW,
    then detects the layout. Retries a few times since WorkerW doesn't
    always appear instantly.

    Returns the target HWND (WorkerW for Layout A, Progman for Layout B),
    or None on failure.
    """
    global _embed_layout

    progman = user32.FindWindowW("Progman", None)
    if not progman:
        print("[desktop] ERROR: Could not find Progman window")
        return None

    # Send the undocumented 0x052C message to spawn WorkerW
    result = wintypes.DWORD(0)
    SendMessageTimeoutW(progman, 0x052C, 0xD, 0, SMTO_NORMAL, 1000, ctypes.byref(result))
    SendMessageTimeoutW(progman, 0x052C, 0xD, 1, SMTO_NORMAL, 1000, ctypes.byref(result))

    # Retry a few times — WorkerW can take a moment to appear
    layout = (None,)
    for attempt in range(5):
        layout = _detect_layout()
        if layout[0] is not None:
            break
        time.sleep(0.2)

    if layout[0] is None:
        print("[desktop] ERROR: Could not detect desktop layout after retries")
        return None

    _embed_layout = layout[0]

    if layout[0] == "A":
        print(f"[desktop] Layout A: top-level WorkerW 0x{layout[1]:08x}")
        return layout[1]
    else:
        print(f"[desktop] Layout B (Win11 24H2+): Progman 0x{layout[1]:08x}")
        return layout[1]


def get_worker_w_size():
    """
    Find the embed target and return its (hwnd, width, height) in physical pixels.
    Returns (None, 0, 0) if target can't be found.
    """
    target = find_worker_w()
    if not target:
        return None, 0, 0
    rect = wintypes.RECT()
    user32.GetWindowRect(target, ctypes.byref(rect))
    w = rect.right - rect.left
    h = rect.bottom - rect.top
    return target, w, h


def embed_pygame_window(pygame_hwnd, target_hwnd, width, height):
    """
    Embed a pygame window as the desktop wallpaper behind icons.

    Handles both Layout A and Layout B automatically based on the
    layout detected during find_worker_w().

    Args:
        pygame_hwnd: The HWND of the pygame window.
        target_hwnd: The HWND returned by find_worker_w().
        width: Physical pixel width.
        height: Physical pixel height.

    Returns:
        True on success, False on failure.
    """
    global _hidden_worker_w

    if not target_hwnd:
        return False

    # Strip window chrome — we want a bare frameless surface
    style = _get_window_long(pygame_hwnd, GWLP_STYLE)
    style &= ~(WS_CAPTION | WS_THICKFRAME | WS_SYSMENU | WS_MAXIMIZEBOX | WS_MINIMIZEBOX | WS_POPUP)
    style |= WS_CHILD | WS_VISIBLE
    _set_window_long(pygame_hwnd, GWLP_STYLE, style)

    # Strip extended styles that can interfere with rendering
    ex_style = _get_window_long(pygame_hwnd, GWLP_EXSTYLE)
    ex_style &= ~(0x00020000 | 0x00000200 | 0x00000100 | 0x00080000 | 0x00000001)
    ex_style |= WS_EX_TOOLWINDOW
    _set_window_long(pygame_hwnd, GWLP_EXSTYLE, ex_style)

    if _embed_layout == "B":
        # Layout B: parent into Progman, position below icons
        progman = target_hwnd
        sdv = user32.FindWindowExW(progman, None, "SHELLDLL_DefView", None)
        worker_w = user32.FindWindowExW(progman, None, "WorkerW", None)

        user32.SetParent(pygame_hwnd, progman)

        # Position our window AFTER SHELLDLL_DefView in Z-order
        # (below icons but above WorkerW / static wallpaper)
        if sdv:
            user32.SetWindowPos(pygame_hwnd, sdv, 0, 0, width, height,
                                SWP_NOACTIVATE | SWP_SHOWWINDOW)
        else:
            user32.SetWindowPos(pygame_hwnd, None, 0, 0, width, height,
                                SWP_NOZORDER | SWP_NOACTIVATE | SWP_SHOWWINDOW)

        # Hide WorkerW to stop Progman from painting the static wallpaper
        # over our content. We restore it in detach_pygame_window().
        if worker_w:
            user32.ShowWindow(worker_w, SW_HIDE)
            _hidden_worker_w = worker_w
            print(f"[desktop] Layout B: hid WorkerW 0x{worker_w:08x}")

        print(f"[desktop] Embedded into Progman ({width}x{height})")
    else:
        # Layout A: parent into the empty top-level WorkerW
        user32.SetParent(pygame_hwnd, target_hwnd)
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
    Also restores any hidden WorkerW from Layout B.
    """
    global _hidden_worker_w

    # Restore the hidden WorkerW first (Layout B cleanup)
    if _hidden_worker_w:
        user32.ShowWindow(_hidden_worker_w, SW_SHOW)
        print(f"[desktop] Restored WorkerW 0x{_hidden_worker_w:08x}")
        _hidden_worker_w = None

    desktop = user32.GetDesktopWindow()
    user32.SetParent(pygame_hwnd, desktop)

    style = _get_window_long(pygame_hwnd, GWLP_STYLE)
    style &= ~WS_CHILD
    style |= WS_POPUP | WS_VISIBLE | WS_CAPTION | WS_SYSMENU | WS_THICKFRAME
    _set_window_long(pygame_hwnd, GWLP_STYLE, style)
