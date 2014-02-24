from vbcbbot import chatbox_connector
from vbcbbot.modules import Module

import logging
import re
import sqlite3
import time

__author__ = 'ondra'

logger = logging.getLogger("vbcbbot.modules.messenger")
msg_trigger = re.compile("^!(msg|mail) (.+)$")


class Messenger(Module):
    """Delivers messages to users when they return."""

    def message_received_on_new_connection(self, message):
        # don't do anything
        return

    def potential_message_send(self, message, body, lower_sender_name):
        match = msg_trigger.match(body)
        if match is None:
            return

        recipient_and_message = match.group(2)

        semicolon_index = recipient_and_message.find(";")
        if semicolon_index == -1:
            self.connector.send_message(
                "You need to put a semicolon between the nickname and the message!"
            )
            return

        target_name = recipient_and_message[:semicolon_index].strip()
        lower_target_name = target_name.lower()
        send_body = recipient_and_message[semicolon_index+1:].strip()

        if lower_target_name == self.connector.username.lower():
            self.connector.send_message("Sorry, I don\u2019t deliver to myself!")
            return

        user_info = None
        try:
            user_info = self.connector.get_user_id_and_nickname_for_uncased_name(target_name)
        except chatbox_connector.TransferError:
            pass

        if user_info is None:
            self.connector.send_message("Sorry, I don\u2019t know \u201c{0}\u201d.".format(target_name))
            return

        logger.debug("{0} sending message {1} to {2}".format(
            repr(message.user_name), repr(send_body), repr(target_name)
        ))

        cursor = self.database.cursor()
        cursor.execute(
            "INSERT INTO messages "
            "(timestamp, sender_original, recipient_folded, body) "
            "VALUES (?, ?, ?, ?)",
            (message.timestamp, message.user_name, lower_target_name, send_body)
        )
        self.database.commit()

        if lower_target_name == lower_sender_name:
            self.connector.send_message(
                "Talking to ourselves? Well, no skin off my back. I\u2019ll deliver "
                "your message to you right away. ;)"
            )
        else:
            sent_template = "Aye-aye! I\u2019ll deliver your message to " + \
                "[i][noparse]{0}[/noparse][/i] next time I see \u2019em!"
            self.connector.send_message(sent_template.format(user_info[1]))

    def message_received(self, message):
        """
        Called by the communicator when a new message has been received.
        :type message: vbcbbot.chatbox_connector.ChatboxMessage
        """
        lower_sender_name = message.user_name.lower()

        # parse and strip
        body = message.decompiled_body().strip()

        # process potential message sends
        self.potential_message_send(message, body, lower_sender_name)

        if self.connector.should_stfu():
            # don't bother just yet
            return

        # check if the sender should get any messages
        cursor = self.database.cursor()
        cursor.execute(
            "SELECT timestamp, sender_original, body FROM messages "
            "WHERE recipient_folded=? ORDER BY timestamp ASC",
            (lower_sender_name,)
        )
        messages = []
        for bin_row in cursor:
            messages.append((bin_row[0], bin_row[1], bin_row[2]))
        cursor.close()

        if len(messages) == 0:
            # meh
            return
        elif len(messages) == 1:
            # one message
            (the_timestamp, the_sender, the_body) = messages[0]
            logger.debug("delivering {0}'s message {1} to {2}".format(
                repr(the_sender), repr(the_body), repr(message.user_name)
            ))
            self.connector.send_message(
                "Message for [noparse]{0}[/noparse]! [{1}] <[noparse]{2}[/noparse]> {3}".format(
                    message.user_name,
                    time.strftime("%Y-%m-%d %H:%M", time.localtime(the_timestamp)),
                    the_sender,
                    the_body
                )
            )
        else:
            # multiple messages
            self.connector.send_message("{0} messages for [noparse]{1}[/noparse]!".format(
                len(messages), message.user_name
            ))
            for (the_timestamp, the_sender, the_body) in messages:
                logger.debug("delivering {0}'s message {1} to {2} as part of a chunk".format(
                    repr(the_sender), repr(the_body), repr(message.user_name)
                ))
                self.connector.send_message("[{0}] <[noparse]{1}[/noparse]> {2}".format(
                    time.strftime("%Y-%m-%d %H:%M", time.localtime(the_timestamp)),
                    the_sender,
                    the_body
                ))
            self.connector.send_message("Have a nice day!")

        # delete those messages
        cursor = self.database.cursor()
        cursor.execute("DELETE FROM messages WHERE recipient_folded=?", (lower_sender_name,))
        self.database.commit()
        cursor.close()

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
        CREATE TABLE IF NOT EXISTS messages (
            timestamp INT NOT NULL,
            sender_original TEXT NOT NULL,
            recipient_folded TEXT NOT NULL,
            body TEXT NOT NULL
        )
        """)
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_recipient_timestamp
        ON messages (recipient_folded, timestamp ASC)
        """)
        self.database.commit()
