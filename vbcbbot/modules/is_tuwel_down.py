from vbcbbot.modules import Module
from vbcbbot.utils import remove_control_characters_and_strip

import logging
import random
import time
import urllib.request as ur

__author__ = 'ondra'

logger = logging.getLogger("vbcbbot.modules.is_tuwel_down")

parse_messages = lambda value: [ln.strip() for ln in value.split("\n") if len(ln.strip()) > 0]


class IsTuwelDown(Module):
    """Checks TUWEL is down by consulting an API."""

    def process_message(self, message, modified=False, initial_salvo=False, user_banned=False):
        if modified or initial_salvo or user_banned:
            return

        body = remove_control_characters_and_strip(message.decompiled_body())
        if body not in ("!istuweldown", "!isttuweldown"):
            return

        response = ur.urlopen(self.api_url)
        response_data = response.read().decode("us-ascii")

        pieces = response_data.split(" ")
        if len(pieces) != 3:
            logger.debug("unexpected server answer {0} for nickname {1}".format(
                repr(response_data)
            ))
            self.connector.send_message(
                random.choice(self.unknown_messages).format(sender=message.user_name)
            )
            return

        (status, since_string, last_update_string) = pieces

        try:
            since = time.strftime("%Y-%m-%d %H:%M", time.localtime(int(since_string)))
        except ValueError:
            since = -1

        try:
            last_update = time.strftime("%Y-%m-%d %H:%M", time.localtime(int(last_update_string)))
        except ValueError:
            last_update = -1

        pick_one = self.unknown_messages
        if status == "0":
            pick_one = self.up_messages
        elif status == "1":
            pick_one = self.down_messages

        outgoing = random.choice(pick_one)

        self.connector.send_message(
            outgoing.format(sender=message.user_name, since=since, last_update=last_update)
        )

    def __init__(self, connector, config_section):
        """
        Create a new messaging responder.
        :param connector: The communicator used to communicate with the chatbox.
        :param config_section: A dictionary of configuration values for this module.
        """
        Module.__init__(self, connector, config_section)

        if config_section is None:
            config_section = {}

        self.api_url = config_section["api url"]

        self.down_messages = ["[noparse]{sender}[/noparse]: TUWEL is down since {since}. (Last checked {last_update}.)"]
        if "down messages" in config_section:
            self.down_messages = parse_messages(config_section["down messages"])

        self.up_messages = ["[noparse]{sender}[/noparse]: TUWEL is up since {since}. (Last checked {last_update}.)"]
        if "up messages" in config_section:
            self.up_messages = parse_messages(config_section["up messages"])

        self.unknown_messages = ["[noparse]{sender}[/noparse]: I don\u2019 know either..."]
        if "unknown messages" in config_section:
            self.unknown_messages = parse_messages(config_section["unknown messages"])
