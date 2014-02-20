from vbcbbot.modules import Module

import base64
import logging
import time
import urllib.parse as up
import urllib.request as ur

__author__ = 'ondra'

logger = logging.getLogger("vbcbbot.modules.last_seen_api")


class LastSeenApi(Module):
    """Checks when a user has most recently posted a message to the chatbox by consulting an API."""

    def message_received_on_new_connection(self, message):
        # don't do anything
        return

    def message_received(self, message):
        """
        Called by the communicator when a new message has been received.
        :type message: vbcbbot.chatbox_connector.ChatboxMessage
        """
        body = message.body_soup().text.strip()
        if not body.startswith("!lastseen "):
            return

        nickname = body[len("!lastseen "):].strip()
        url_escaped_nickname = up.quote_plus(nickname)

        # note: must be specified as "%%USERNAME%%" in the config file
        # due to variable substitution in configparse
        call_url = self.api_url.replace("%USERNAME%", url_escaped_nickname)

        request = ur.Request(call_url)

        # authenticate?
        if self.api_username != "":
            authentication_pair = "{0}:{1}".format(self.api_username, self.api_password)
            authentication_bytes = authentication_pair.encode("utf-8")
            authentication_b64_string = base64.b64encode(authentication_bytes).decode("us-ascii")
            request.add_header("Authorization", "Basic {0}".format(authentication_b64_string))

        response = ur.urlopen(request)
        response_data = response.read().decode("us-ascii")

        if response_data == "NULL":
            self.connector.send_message(
                "{0}: The great [i]signanz[/i] doesn't remember seeing " +
                "[i][noparse]{1}[/noparse][/i].".format(
                    message.user_name,
                    nickname
                )
            )
            return

        try:
            timestamp = int(response_data)
        except ValueError:
            self.connector.send_message(
                "{0}: The great [i]signanz[/i]'s answer confused me\u2014sorry!".format(
                    message.user_name
                )
            )
            return

        time_text = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(timestamp))

        self.connector(
            "{0}: The last time the great [i]signanz[/i] saw [i][noparse]{1}[/noparse][/i] "
            "was {2}.".format(
                message.user_name, nickname, time_text
            )
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

        self.api_username = ""
        if "username" in config_section:
            self.api_username = config_section["username"]

        self.api_password = ""
        if "password" in config_section:
            self.api_password = config_section["password"]
