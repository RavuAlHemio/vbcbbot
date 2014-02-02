from vbcbbot import chatbox_connector
from vbcbbot.modules import Module

import logging
import sqlite3
import time
import xml.dom as dom

__author__ = 'ondra'

logger = logging.getLogger("vbcbbot.modules.thanks")


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
        # parse and strip
        body = message.decompiled_body().strip()

        thank = False
        nickname = None
        if body.startswith("!thank "):
            thank = True
            nickname = body[len("!thank "):].strip()
        elif body.startswith("!thanks "):
            thank = True
            nickname = body[len("!thanks "):].strip()

        if thank:
            lower_nickname = nickname.lower()
            if lower_nickname == message.user_name.lower():
                self.connector.send_message("You are so full of yourself, {0}.".format(
                    message.user_name
                ))

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
                    "{0}: Alright! By the way, {1} has been thanked {2} until now.".format(
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
                    self.connector.send_message("I don't know '{0}'!".format(nickname))
                    return
            except chatbox_connector.TransferError:
                self.connector.send_message("I don't know '{0}'!".format(nickname))
                return

            cursor = self.database.cursor()
            cursor.execute(
                "SELECT COALESCE(SUM(thank_count), 0) FROM thanks WHERE thankee_folded=?",
                (lower_nickname,)
            )
            for row in cursor:
                self.connector.send_message(
                    "{0}: {1} has been thanked {2} until now.".format(
                        message.user_name, user_info[1],
                        "once" if row[0] == 1 else "{0} times".format(row[0])
                    )
                )
                return

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