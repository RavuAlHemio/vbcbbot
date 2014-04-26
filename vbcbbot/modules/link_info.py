from vbcbbot import chatbox_connector
from vbcbbot.modules import Module

import logging
from lxml import etree
import time
import urllib.request as ur

__author__ = 'ondra'

logger = logging.getLogger("vbcbbot.modules.link_info")


def find_links(node_list):
    ret = []
    for node in node_list:
        if node.is_element() and node.name == 'url':
            ret.append(node.attribute_value)
        if node.has_children():
            ret += find_links(node.children)
    return ret


def obtain_link_info(url):
    try:
        if not url.startswith("http://") and not url.startswith("https://"):
            return "(I only access HTTP and HTTPS URLs)"

        response_object = ur.urlopen(url, timeout=5)
        if response_object.code != 200:
            return "(HTTP {0})".format(response_object.code)
        response_bytes = response_object.read()
        response_headers = response_object.getheaders()

        # find content-type
        content_type = "application/octet-stream"
        for (n, v) in response_headers:
            if n == "Content-Type":
                # application/x-blahblah; charset=utf-32
                content_type = v.split(";")[0]

        if content_type == "application/octet-stream":
            return "(can't figure out the content type, sorry)"

        if content_type in ("text/html", "application/xhtml+xml"):
            # HTML? parse it and get the title
            html = etree.HTML(response_bytes)
            title_element = html.find(".//title")
            if title_element is not None:
                return "".join(title_element.itertext())
            h1_element = html.find(".//h1")
            if h1_element is not None:
                return "".join(h1_element.itertext())
            return "(HTML without a title O_o)"
        elif content_type == "image/png":
            return "PNG image"
        elif content_type == "image/jpeg":
            return "JPEG image"
        elif content_type == "image/gif":
            return "GIF image"
        elif content_type == "application/json":
            return "JSON"
        elif content_type in ("text/xml", "application/xml"):
            return "XML"

        return "file of type {0}".format(content_type)

    except:
        logger.exception("link info")
        return "(an error occurred)"


class LinkInfo(Module):
    """Shows information about a link."""

    def message_received_on_new_connection(self, message):
        # don't do anything
        return

    def message_received(self, message):
        """
        Called by the communicator when a new message has been received.
        :type message: vbcbbot.chatbox_connector.ChatboxMessage
        """

        # respond?
        body = message.decompiled_body().strip()
        if not body.startswith("!link "):
            return

        # find all the links
        dom = message.decompiled_body_dom()
        links = find_links(dom)

        # fetch their info
        links_infos = [(link, obtain_link_info(link)) for link in links]

        for (link, link_info) in links_infos:
            # clear out [noparse] tags
            previous = None
            while link_info != previous:
                previous = link_info
                link_info.replace("[noparse]", "").replace("[/noparse]", "")

            outgoing = "[url]{0}[/url]: [noparse]{1}[/noparse]".format(link, link_info)
            self.connector.send_message(outgoing)

    def __init__(self, connector, config_section):
        """
        Create a new messaging responder.
        :param connector: The communicator used to communicate with the chatbox.
        :param config_section: A dictionary of configuration values for this module.
        """
        Module.__init__(self, connector, config_section)

        if config_section is None:
            config_section = {}
