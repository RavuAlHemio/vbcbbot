from vbcbbot.html_decompiler import SmileyText
from vbcbbot.modules import Module

import base64
import http.server
import logging
import threading
import time
from urllib.parse import unquote_plus, urljoin

__author__ = 'ondra'

logger = logging.getLogger("vbcbbot.modules.http_interface")


def html_escape(s, escape_quotes=True, escape_apostrophes=False):
    ret = ""
    strange = str(s)
    for c in strange:
        if c == "<":
            ret += "&lt;"
        elif c == ">":
            ret += "&gt;"
        elif c == "&":
            ret += "&amp;"
        elif escape_quotes and c == '"':
            ret += "&quot;"
        elif escape_apostrophes and c == "'":
            ret += "&apos;"
        elif ord(c) > 0x7E:
            ret += "&#{0};".format(ord(c))
        else:
            ret += c
    return ret


def dom_to_html(body_dom, base_url):
    ret = ""
    for node in body_dom:
        if node.is_element():
            if node.name == "url":
                ret += '<a class="url" href="{url}">{inside}</a>'.format(
                    url=html_escape(urljoin(base_url, node.attribute_value)),
                    inside=dom_to_html(node.children, base_url)
                )
            elif node.name == "icon":
                ret += '<img class="icon" src="{src}" />'.format(
                    src=html_escape(urljoin(base_url, node.children[0].text))
                )
            elif node.name in "biu":
                ret += '<{n}>{inside}</{n}>'.format(
                    n=node.name, inside=dom_to_html(node.children, base_url)
                )
            elif node.name == "strike":
                ret += '<span class="strike" style="text-decoration:line-through">{inside}</span>'.format(
                    inside=dom_to_html(node.children, base_url)
                )
            elif node.name == "color":
                ret += '<span class="color" style="color:{color}">{inside}</span>'.format(
                    inside=dom_to_html(node.children, base_url)
                )
            else:
                ret += html_escape(node)
        elif isinstance(node, SmileyText):
            ret += '<img class="smiley" src="{src}" alt="{smiley}" />'.format(
                src=html_escape(urljoin(base_url, node.smiley_url)), smiley=html_escape(node.text)
            )
        else:
            ret += html_escape(node)
    return ret


class RequestHandler(http.server.BaseHTTPRequestHandler):
    http_interface = None
    """:type: HttpInterface"""

    def check_auth(self):
        username_colon_password = "{0}:{1}".format(
            self.http_interface.username, self.http_interface.password
        )
        auth_bytes = base64.b64encode(username_colon_password.encode("utf-8"))
        auth_token = "Basic " + auth_bytes.decode("us-ascii")

        if "Authorization" not in self.headers or self.headers["Authorization"] != auth_token:
            self.send_response(401)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.send_header("WWW-Authenticate", "Basic realm=\"Chatbox\"")
            self.end_headers()
            self.wfile.write(b"Please authenticate!")
            return False

        return True

    def do_GET(self):
        if not self.check_auth():
            return

        if self.path == "/":
            # output the chatbox form
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()
            self.wfile.write(self.http_interface.page_template.encode("utf-8"))
        elif self.path == "/messages":
            # output the messages as a chunk
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.end_headers()

            with self.http_interface.message_lock:
                for message in self.http_interface.messages:
                    output_string = self.http_interface.post_template.format(
                        message_id=html_escape(message.id), sender_id=html_escape(message.user_id),
                        sender_name=html_escape(message.user_name),
                        time=time.strftime("%Y-%m-%d %H:%M", time.localtime(message.timestamp)),
                        body=dom_to_html(
                            message.decompiled_dom(),
                            self.http_interface.connector.base_url
                        )
                    )
                    self.wfile.write(output_string.encode("utf-8"))
        elif self.path[1:] in self.http_interface.allowed_files:
            # output the file
            self.send_response(200)
            self.end_headers()
            with open(self.path[1:], "rb") as f:
                self.wfile.write(f.read())
        else:
            self.send_response(404)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(b"No such file or directory!")

    def do_POST(self):
        if not self.check_auth():
            return

        if self.path == "/postmessage":
            length = int(self.headers["Content-Length"])
            post_body_bytes = self.rfile.read(length)
            post_body = post_body_bytes.decode("utf-8")

            values = {}
            for key_val_string in post_body.split("&"):
                key_val = key_val_string.split("=", 1)
                if len(key_val) == 2:
                    values[key_val[0]] = unquote_plus(key_val[1])

            if "message" not in values:
                return

            self.http_interface.connector.send_message(values["message"])

            self.send_response(303)
            self.send_header("Location", "/")
            self.end_headers()


class HttpInterface(Module):
    """Provides a simplistic HTTP interface to the chatbox."""

    def message_received(self, message):
        """Called by the communicator when a new message has been received."""

        # add it!
        with self.message_lock:
            self.messages.insert(0, message)
            while len(self.messages) > self.backlog:
                self.messages.pop()

    def __init__(self, connector, config_section):
        """
        Create a new HTTP interface.
        :param connector: The communicator used to communicate with the chatbox.
        :param config_section: A dictionary of configuration values for this module.
        """
        Module.__init__(self, connector, config_section)

        if config_section is None:
            config_section = {}

        port = 8099
        if "port" in config_section:
            port = int(config_section["port"])

        self.backlog = 50
        if "backlog" in config_section:
            self.backlog = int(config_section["backlog"])

        self.allowed_files = set()
        if "allowed files" in config_section:
            for f in config_section["allowed files"].split():
                self.allowed_files.add(f.strip())

        with open(config_section["page template"], "r") as f:
            self.page_template = f.read()

        with open(config_section["post template"], "r") as f:
            self.post_template = f.read()

        self.username = config_section["username"]
        self.password = config_section["password"]

        self.messages = []
        self.message_lock = threading.RLock()
        self.stop_now = False
        self.server_thread = threading.Thread(None, self.server_proc, "HttpInterface")

        RequestHandler.http_interface = self
        self.server = http.server.HTTPServer(('', port), RequestHandler)

    def server_proc(self):
        self.server.serve_forever()

    def start(self):
        self.server_thread.start()

    def stop(self):
        self.stop_now = True
