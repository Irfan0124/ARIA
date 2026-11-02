
# import threading
# from http.server import BaseHTTPRequestHandler, HTTPServer
# aria_hwnd = None
# import pystray
# import win32gui
# import win32con
# import win32process
# import win32api
# import socket
# import threading
# from PIL import Image, ImageDraw


# WINDOW_TITLE = "ARIA"
# HOST = "127.0.0.1"
# PORT = 8766

# tray_icon = None


# def find_aria_window():
#     """Cari jendela game ARIA berdasarkan judul."""
#     windows = []

#     def callback(hwnd, _):
#         title = win32gui.GetWindowText(hwnd)

#         if title == WINDOW_TITLE:
#             windows.append(hwnd)

#     win32gui.EnumWindows(callback, None)

#     return windows[0] if windows else None


# def show_aria():
#     hwnd = find_aria_window()

#     if hwnd:
#         win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
#         win32gui.SetForegroundWindow(hwnd)


# def hide_aria():
#     hwnd = find_aria_window()

#     if hwnd:
#         win32gui.ShowWindow(hwnd, win32con.SW_HIDE)


# def exit_aria():
#     hwnd = find_aria_window()

#     if hwnd:
#         _, process_id = win32process.GetWindowThreadProcessId(hwnd)

#         handle = win32api.OpenProcess(
#             win32con.PROCESS_TERMINATE,
#             False,
#             process_id,
#         )

#         win32api.TerminateProcess(handle, 0)
#         win32api.CloseHandle(handle)

#     if tray_icon:
#         tray_icon.stop()


# def create_icon_image():
#     image = Image.new("RGB", (64, 64), (35, 30, 55))
#     draw = ImageDraw.Draw(image)

#     draw.ellipse(
#         (5, 5, 59, 59),
#         fill=(145, 100, 230),
#     )

#     draw.text(
#         (20, 17),
#         "A",
#         fill="white",
#     )

#     return image


# class TrayRequestHandler(BaseHTTPRequestHandler):
#     def do_GET(self):
#         if self.path == "/hide":
#             hide_aria()
#             self.send_response(200)
#             self.end_headers()
#             self.wfile.write(b"ARIA hidden")

#         elif self.path == "/show":
#             show_aria()
#             self.send_response(200)
#             self.end_headers()
#             self.wfile.write(b"ARIA shown")

#         else:
#             self.send_response(404)
#             self.end_headers()

#     def log_message(self, *_):
#         pass

# def find_window_by_pid(pid):
#     windows = []

#     def callback(hwnd, _):
#         if not win32gui.IsWindowVisible(hwnd):
#             return

#         _, window_pid = win32process.GetWindowThreadProcessId(hwnd)

#         if window_pid == pid:
#             windows.append(hwnd)

#     win32gui.EnumWindows(callback, None)

#     return windows[0] if windows else None


# def udp_server():
#     global aria_hwnd

#     server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
#     server.bind(("127.0.0.1", 8767))

#     while True:
#         data, _ = server.recvfrom(1024)
#         message = data.decode("utf-8", errors="ignore")

#         if message.startswith("hide:"):
#             try:
#                 pid = int(message.split(":")[1])
#                 hwnd = find_window_by_pid(pid)

#                 if hwnd:
#                     aria_hwnd = hwnd
#                     win32gui.ShowWindow(hwnd, win32con.SW_HIDE)
#                     print("ARIA disembunyikan:", hwnd)

#                 else:
#                     print("Jendela ARIA tidak ditemukan untuk PID:", pid)

#             except ValueError:
#                 print("PID tidak valid:", message)


# def show_aria():
#     global aria_hwnd

#     if aria_hwnd and win32gui.IsWindow(aria_hwnd):
#         win32gui.ShowWindow(aria_hwnd, win32con.SW_SHOW)
#         win32gui.SetForegroundWindow(aria_hwnd)
# def start_http_server():
#     server = HTTPServer((HOST, PORT), TrayRequestHandler)
#     server.serve_forever()


# def main():
#     global tray_icon

#     threading.Thread(
#         target=start_http_server,
#         daemon=True,
#     ).start()

#     menu = pystray.Menu(
#         pystray.MenuItem("Show ARIA", lambda: show_aria()),
#         pystray.MenuItem("Hide ARIA", lambda: hide_aria()),
#         pystray.MenuItem("Exit ARIA", lambda: exit_aria()),
#     )

#     tray_icon = pystray.Icon(
#         "ARIA",
#         create_icon_image(),
#         "ARIA Assistant",
#         menu,
#     )
#     threading.Thread(
#     target=udp_server,
#     daemon=True
# ).start()

#     tray_icon.run()


# if __name__ == "__main__":
#     main()

import threading
import socket
import pystray
import win32gui
import win32con
import win32process
import win32api

from http.server import BaseHTTPRequestHandler, HTTPServer
from PIL import Image, ImageDraw


WINDOW_TITLE = "ARIA"
HOST = "127.0.0.1"
PORT = 8766
UDP_HOST = "127.0.0.1"
UDP_PORT = 8767

tray_icon = None
aria_hwnd = None
running = True


def find_window_by_pid(pid):
    windows = []

    def callback(hwnd, _):
        if not win32gui.IsWindow(hwnd):
            return

        _, window_pid = win32process.GetWindowThreadProcessId(hwnd)

        if window_pid == pid:
            windows.append(hwnd)

    win32gui.EnumWindows(callback, None)

    return windows[0] if windows else None


def find_aria_window():
    windows = []

    def callback(hwnd, _):
        if win32gui.GetWindowText(hwnd) == WINDOW_TITLE:
            windows.append(hwnd)

    win32gui.EnumWindows(callback, None)

    return windows[0] if windows else None


def show_aria():
    global aria_hwnd

    if not aria_hwnd or not win32gui.IsWindow(aria_hwnd):
        aria_hwnd = find_aria_window()

    if aria_hwnd and win32gui.IsWindow(aria_hwnd):
        win32gui.ShowWindow(aria_hwnd, win32con.SW_SHOW)
        win32gui.ShowWindow(aria_hwnd, win32con.SW_RESTORE)
        win32gui.SetForegroundWindow(aria_hwnd)
        print("ARIA ditampilkan.")


def hide_aria():
    global aria_hwnd

    if not aria_hwnd or not win32gui.IsWindow(aria_hwnd):
        aria_hwnd = find_aria_window()

    if aria_hwnd and win32gui.IsWindow(aria_hwnd):
        win32gui.ShowWindow(aria_hwnd, win32con.SW_HIDE)
        print("ARIA disembunyikan.")


def exit_aria():
    global running

    running = False

    hwnd = aria_hwnd

    if not hwnd or not win32gui.IsWindow(hwnd):
        hwnd = find_aria_window()

    if hwnd and win32gui.IsWindow(hwnd):
        _, process_id = win32process.GetWindowThreadProcessId(hwnd)

        handle = win32api.OpenProcess(
            win32con.PROCESS_TERMINATE,
            False,
            process_id,
        )

        try:
            win32api.TerminateProcess(handle, 0)
        finally:
            win32api.CloseHandle(handle)

    if tray_icon:
        tray_icon.stop()


def create_icon_image():
    image = Image.new("RGB", (64, 64), (35, 30, 55))
    draw = ImageDraw.Draw(image)

    draw.ellipse(
        (5, 5, 59, 59),
        fill=(145, 100, 230),
    )

    draw.text((20, 17), "A", fill="white")

    return image


class TrayRequestHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        if self.path == "/hide":
            hide_aria()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ARIA hidden")

        elif self.path == "/show":
            show_aria()
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ARIA shown")

        else:
            self.send_response(404)
            self.end_headers()

    def log_message(self, *_):
        pass


def udp_server():
    global aria_hwnd, running

    server = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    server.bind((UDP_HOST, UDP_PORT))
    server.settimeout(1.0)

    try:
        while running:
            try:
                data, _ = server.recvfrom(1024)
            except socket.timeout:
                continue

            message = data.decode("utf-8", errors="ignore")

            if message.startswith("hide:"):
                try:
                    pid = int(message.split(":")[1])
                    hwnd = find_window_by_pid(pid)

                    if hwnd:
                        aria_hwnd = hwnd
                        hide_aria()
                    else:
                        print("Jendela ARIA tidak ditemukan:", pid)

                except ValueError:
                    print("PID tidak valid:", message)

    finally:
        server.close()


def start_http_server():
    server = HTTPServer((HOST, PORT), TrayRequestHandler)
    server.serve_forever()


def main():
    global tray_icon

    threading.Thread(
        target=start_http_server,
        daemon=True,
    ).start()

    threading.Thread(
        target=udp_server,
        daemon=True,
    ).start()

    menu = pystray.Menu(
        pystray.MenuItem("Show ARIA", lambda: show_aria()),
        pystray.MenuItem("Hide ARIA", lambda: hide_aria()),
        pystray.MenuItem("Exit ARIA", lambda: exit_aria()),
    )

    tray_icon = pystray.Icon(
        "ARIA",
        create_icon_image(),
        "ARIA Assistant",
        menu,
    )

    tray_icon.run()


if __name__ == "__main__":
    main()
