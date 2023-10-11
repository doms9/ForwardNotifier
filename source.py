#!/usr/bin/env python3

import base64
import binascii
import json
import platform
import shutil
from configparser import ConfigParser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from time import sleep

import requests
from winsdk.windows.data.xml import dom
from winsdk.windows.ui.notifications import ToastNotification, ToastNotificationManager

try:
    from ctypes import windll

    myappid = "d9_scratch.forwardnotifier"
    windll.shell32.SetCurrentProcessExplicitAppUserModelID(myappid)
except ImportError:
    pass

config = ConfigParser()


def check_internet() -> None:
    tries = 0

    while tries < 10:
        try:
            requests.get("https://example.com")
        except requests.ConnectionError:
            sendnotif(
                "Cannot connect to the internet!",
                "Trying again in 30 seconds.",
            )

            sleep(30)

            tries += 1

            continue
        else:
            break


def sendnotif(
    title: bytes | str,
    message: bytes | str,
) -> None:
    # decoding...
    try:
        title = base64.b64decode(title.encode("utf-8")).decode("utf-8")

        message = base64.b64decode(message.encode("utf-8")).decode("utf-8")
    except binascii.Error:
        pass

    # get python path
    py_path = Path(shutil.which("python")).resolve()

    # get device name
    config.read(Path(__file__).resolve().parent.parent / "config.ini")

    if (device_name := config.get("Apple Device", "name")) == "":
        device_name = "Apple Device"

    # create toast icon
    WINotifier = ToastNotificationManager.create_toast_notifier(str(py_path))

    # toast message
    toastring = f"""<toast duration='short'><audio src  = 'ms-winsoundevent:Notification.Reminder' loop = 'false' silent = 'false'/><visual><binding template='ToastText02'><text id="1">{title}</text><text id="2">{message}</text><text placement="attribution">via {device_name}</text></binding></visual></toast>"""

    # conversion
    xml = dom.XmlDocument()

    xml.load_xml(toastring)

    if str(message).lower() != "(null)":  # pseudo notifications...
        WINotifier.show(ToastNotification(xml))


def checkbody(body: str) -> list | list[bool]:
    try:
        body = json.loads(body)
    except json.JSONDecodeError:
        return [False, "Unable to parse json"]

    if "Title" not in body:
        return [False, "No 'Title' in body"]

    return [False, "No 'Message' in body"] if "Message" not in body else [True]


class Server(BaseHTTPRequestHandler):
    def send_res(
        self,
        args,
        code: int = 200,
        success: bool = True,
    ) -> None:
        self.send_response(code)

        self.send_header(
            "Content-type",
            "text/html",
        )

        self.send_header(
            "Access-Control-Allow-Origin",
            "*",
        )

        self.end_headers()

        out = {"Success": success, "value": args}

        self.wfile.write(json.dumps(out).encode("utf-8"))

    def do_GET(self) -> None:
        self.send_res("Send a Post with a title and a message in a json format")

    def do_POST(self) -> None:
        content_length = int(self.headers["Content-Length"])

        post_data = self.rfile.read(content_length)

        if content_length > 0:
            try:
                body = post_data.decode("utf-8")
            except UnicodeEncodeError:
                sendnotif(
                    "ForwardNotifierReciver Error:",
                    "invalid characters",
                )

            if checkbody(body)[0]:
                body = json.loads(body)

                sendnotif(
                    body["Title"],
                    body["Message"],
                )

                self.send_res("Sent!")

            else:
                self.send_res(
                    checkbody(body)[1],
                    success=False,
                    code=400,
                )

        else:
            self.send_res(
                f"POST request for {self.path} . Please send a body",
                success=False,
            )


def run() -> None:
    httpd = HTTPServer(
        ("", 8000),
        Server,
    )

    check_internet()

    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()


if platform.system() == "Windows":
    run()
