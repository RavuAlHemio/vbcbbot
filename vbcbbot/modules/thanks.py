from vbcbbot import chatbox_connector
from vbcbbot.modules import Module

import logging
import re
import sqlite3
import time
import xml.dom as dom

__author__ = 'ondra'

logger = logging.getLogger("vbcbbot.modules.thanks")
thank_re = re.compile("^!(thank|thanks|thx) (.+)$")


class Thanks(Module):
    """Keeps score of gratitude between users."""

    def message_received_on_new_connection(self, message):
        # don't do anything
        return

    def message_received(self, message):
        """
        Called by the communicator when a new message has been received.
        :type message: vbcbbot.chatbox_connector.ChatboxMessage
        """

        # ignore the bot's messages
        if message.user_name == self.connector.username:
            return

        # parse and strip
        body = message.decompiled_body().strip()

        thanks_match = thank_re.match(body)
        if thanks_match is not None:
            nickname = thanks_match.group(2).strip()
            lower_nickname = nickname.lower()
            if lower_nickname == message.user_name.lower():
                self.connector.send_message("You are so full of yourself, [noparse]{0}[/noparse].".format(
                    message.user_name
                ))
                return

            try:
                user_info = self.connector.get_user_id_and_nickname_for_uncased_name(nickname)
                if user_info is None:
                    self.connector.send_message("I don't know '{0}'!".format(nickname))
                    return
            except chatbox_connector.TransferError:
                self.connector.send_message("I don't know '{0}'!".format(nickname))
                return

            logger.debug("{0} thanks {1}".format(message.user_name, nickname))

            cursor = self.database.cursor()
            cursor.execute(
                "INSERT OR IGNORE INTO thanks (thanker, thankee_folded, thank_count) "
                "VALUES (?, ?, 0)",
                (message.user_name, lower_nickname)
            )
            cursor.execute(
                "UPDATE thanks SET thank_count=thank_count+1 WHERE thanker=? AND thankee_folded=?",
                (message.user_name, lower_nickname)
            )
            self.database.commit()

            cursor.execute(
                "SELECT SUM(thank_count) FROM thanks WHERE thankee_folded=?",
                (lower_nickname,)
            )
            for row in cursor:
                self.connector.send_message(
                    "[noparse]{0}[/noparse]: Alright! By the way, [noparse]{1}[/noparse] has been thanked {2} until "
                    "now.".format(
                        message.user_name, user_info[1],
                        "once" if row[0] == 1 else "{0} times".format(row[0])
                    )
                )
                return

        elif body.startswith("!thanked "):
            nickname = body[len("!thanked "):].strip()
            lower_nickname = nickname.lower()

            try:
                user_info = self.connector.get_user_id_and_nickname_for_uncased_name(nickname)
                if user_info is None:
                    self.connector.send_message("I don't know '[noparse]{0}[/noparse]'!".format(nickname))
                    return
            except chatbox_connector.TransferError:
                self.connector.send_message("I don't know '[noparse]{0}[/noparse]'!".format(nickname))
                return

            cursor = self.database.cursor()
            cursor.execute(
                "SELECT COALESCE(SUM(thank_count), 0) FROM thanks WHERE thankee_folded=?",
                (lower_nickname,)
            )

            count_phrase = None
            show_stats = True
            for row in cursor:
                if row[0] == 0:
                    count_phrase = "not been thanked"
                    show_stats = False
                elif row[0] == 1:
                    count_phrase = "been thanked once"
                else:
                    count_phrase = "been thanked {0} times".format(row[0])

            if count_phrase is None:
                return

            # fetch stats
            stat_string = ""
            if show_stats:
                cursor.execute(
                    "SELECT thanker, thank_count FROM thanks WHERE thankee_folded=? ORDER BY thank_count DESC LIMIT ?",
                    (lower_nickname, self.most_grateful_count)
                )
                grateful_counts = []
                for row in cursor:
                    grateful_counts.append("[noparse]{0}[/noparse]: {1}\u00D7".format(row[0], row[1]))

                # mention that the list is truncated if there might be more than self.most_grateful_count
                count_string = ""
                if len(grateful_counts) == self.most_grateful_count:
                    count_string = " {0}".format(self.most_grateful_count_text)

                stat_string = " (Most grateful{0}: {1})".format(count_string, ", ".join(grateful_counts))

            self.connector.send_message(
                "[noparse]{0}: {1}[/noparse] has {2} until now.{3}".format(
                    message.user_name, user_info[1], count_phrase, stat_string
                )
            )

        elif body == "!topthanked":
            cursor = self.database.cursor()
            cursor.execute(
                "SELECT thankee_folded, SUM(thank_count) AS thank_sum FROM thanks GROUP BY thankee_folded "
                "ORDER BY thank_sum DESC LIMIT ?",
                (self.most_thanked_count,)
            )

            pieces = []
            for row in cursor:
                actual_username = row[0]
                try:
                    user_info = self.connector.get_user_id_and_nickname_for_uncased_name(row[0])
                    if user_info is not None:
                        actual_username = user_info[1]
                except chatbox_connector.TransferError:
                    pass
                pieces.append("{0}: {1}".format(actual_username, row[1]))

            self.connector.send_message(
                "[noparse]{0}[/noparse]: {1}.".format(
                    message.user_name, ", ".join(pieces)
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

        self.database = None
        if "database" in config_section:
            self.database = sqlite3.connect(config_section["database"], check_same_thread=False)
        else:
            self.database = sqlite3.connect(":memory:", check_same_thread=False)

        self.most_grateful_count = 5
        self.most_grateful_count_text = "five"
        if "most grateful count" in config_section:
            self.most_grateful_count = int(config_section["most grateful count"])
            self.most_grateful_count_text = "{0}".format(self.most_grateful_count)
        if "most grateful count text" in config_section:
            self.most_grateful_count_text = config_section["most grateful count text"]

        self.most_thanked_count = 5
        if "most thanked count" in config_section:
            self.most_thanked_count = int(config_section["most thanked count"])

        cursor = self.database.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS thanks (
            thanker TEXT NOT NULL,
            thankee_folded TEXT NOT NULL,
            thank_count INT NOT NULL,
            PRIMARY KEY (thanker, thankee_folded)
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_thanks_thankee ON thanks (thankee_folded)")
        self.database.commit()
