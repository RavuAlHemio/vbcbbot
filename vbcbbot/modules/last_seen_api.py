from vbcbbot.modules import Module

import base64
import logging
import re
import time
import urllib.parse as up
import urllib.request as ur

__author__ = 'ondra'

logger = logging.getLogger("vbcbbot.modules.last_seen_api")
seen_re = re.compile("^!(seen|lastseen) (.+)$")


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
        body = "".join(message.body_lxml().itertext()).strip()
        match = seen_re.match(body)
        if match is None:
            return

        nicknames = [nick.strip().replace("[/noparse]", "") for nick in match.group(2).split(";")]
        nicknames = [nick for nick in nicknames if len(nick) > 0]
        nicknames_times = {}

        if len(nicknames) == 0:
            return
        if len(nicknames) == 1 and len(nicknames[0]) == 0:
            return

        for nickname in nicknames:
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
                nicknames_times[nickname] = None
                continue

            try:
                timestamp = int(response_data)
            except ValueError:
                nicknames_times[nickname] = -1
                continue

            nicknames_times[nickname] = time.strftime("%Y-%m-%d %H:%M", time.localtime(timestamp))

        if len(nicknames) == 1:
            # single-user request
            nickname = nicknames[0]
            t = nicknames_times[nickname]

            if t is None:
                self.connector.send_message(
                    "{0}: The great and powerful [i]signanz[/i] doesn't remember seeing "
                    "[i]{1}[/i].".format(
                        message.user_name,
                        self.connector.escape_outgoing_text(nickname)
                    )
                )
            elif t == -1:
                self.connector.send_message(
                    "{0}: The great and powerful [i]signanz[/i]'s answer confused me\u2014sorry!".format(
                        message.user_name
                    )
                )
            else:
                self.connector.send_message(
                    "{0}: The last time the great and powerful [i]signanz[/i] saw "
                    "[i][noparse]{1}[/noparse][/i] was {2}.".format(
                        message.user_name, nickname, t
                    )
                )
        else:
            response_bits = []
            for nickname in nicknames:
                t = nicknames_times[nickname]

                if t is None:
                    t = "never"
                elif t == -1:
                    t = "o_O"

                response_bits.append("[i][noparse]{0}[/noparse][/i]: {1}".format(nickname, t))

            self.connector.send_message(
                "{0}: The great and powerful [i]signanz[/i] saw: ".format(message.user_name) +
                ", ".join(
                    response_bits
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
