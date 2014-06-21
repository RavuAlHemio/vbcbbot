from vbcbbot import chatbox_connector
from vbcbbot.modules import Module

import logging
import re
import sqlite3
import time
import unicodedata

__author__ = 'ondra'

logger = logging.getLogger("vbcbbot.modules.messenger")
msg_trigger = re.compile("^!(msg|mail) (.+)$")
deliver_trigger = re.compile("^!(delivermsg) ([0-9]+)$")


def split_recipient_and_message(text):
    """
    Split recipient and message on a colon boundary. Allow escaping of colons using backslashes,
    as well as escaping backslashes by doubling.
    :param text: The text to escape.
    :type text: str
    :return: A tuple consisting of the recipient's username and the body text of the message.
    :rtype: (str, str)
    """
    recipient = ""
    escaping = False
    for (i, c) in enumerate(text):
        if escaping:
            if c in (":", "\\"):
                recipient += c
            else:
                raise ValueError("Invalid escape sequence: \\{c}".format(c=c))
            escaping = False
        else:
            if c == "\\":
                escaping = True
            elif c == ":":
                return recipient, text[i+1:]
            else:
                recipient += c
    raise ValueError("You need to put a colon between the nickname and the message!")


def remove_control_characters_and_strip(text):
    ret = ""
    for c in text:
        if unicodedata.category(c)[0] != 'C':
            ret += c
    return ret.strip()


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
        try:
            (target_name, send_body) = split_recipient_and_message(recipient_and_message)
        except ValueError as e:
            self.connector.send_message(str(e))
            return

        target_name = remove_control_characters_and_strip(target_name)
        lower_target_name = target_name.lower()
        send_body = remove_control_characters_and_strip(send_body)

        if len(lower_target_name) == 0:
            self.connector.send_message("You must specify a name to deliver to!")
            return
        elif len(send_body) == 0:
            self.connector.send_message("You must specify a message to deliver!")
            return
        elif lower_target_name == self.connector.username.lower():
            self.connector.send_message("Sorry, I don\u2019t deliver to myself!")
            return
        elif lower_target_name in self.connector.banned_nicknames:
            self.connector.send_message("Sorry, but I\u2019ve been told to ignore \u201c{0}\u201d.".format(target_name))
            return

        try:
            user_info = self.connector.get_user_id_and_nickname_for_uncased_name(target_name)
        except chatbox_connector.TransferError:
            self.connector.send_message(
                "Sorry, I couldn\u2019t verify if \u201c{0}\u201d exists because the forum isn\u2019t being "
                "cooperative. Please try again later!".format(target_name)
            )
            return

        if user_info is None:
            colon_info = ""
            if ":" in send_body:
                colon_info = " (You may escape colons in usernames using a backslash.)"
            elif len(target_name) > 32:
                colon_info = " (You must place a colon between the username and the message.)"
            self.connector.send_message(
                "Sorry, I don\u2019t know \u201c{0}\u201d.".format(target_name) + colon_info
            )
            return

        logger.debug("{0} sending message {1} to {2}".format(
            repr(message.user_name), repr(send_body), repr(target_name)
        ))

        cursor = self.database.cursor()
        cursor.execute(
            "INSERT INTO messages "
            "(message_id, timestamp, sender_original, recipient_folded, body) "
            "VALUES (?, ?, ?, ?, ?)",
            (message.id, message.timestamp, message.user_name, lower_target_name, send_body)
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

    def format_timestamp(self, message_id, the_timestamp):
        timestamp_format = "[{0}]"
        timestamp_link_url = ""
        if self.timestamp_link is not None:
            timestamp_format = "[url={1}][{0}][/url]"
            timestamp_link_url = self.timestamp_link.format(message_id)
        return timestamp_format.format(
            time.strftime("%Y-%m-%d %H:%M", time.localtime(the_timestamp)),
            timestamp_link_url
        )

    def potential_deliver_request(self, message, body, lower_sender_name):
        match = deliver_trigger.match(body)
        if match is None:
            return

        fetch_count = int(match.group(2))
        if fetch_count > 1000:
            self.connector.send_message(
                "{0}: I am absolutely not delivering that many messages at once.".format(message.user_name)
            )
            return

        # fetch messages
        cursor = self.database.cursor()
        cursor.execute(
            "SELECT timestamp, sender_original, body, message_id FROM messages_on_retainer WHERE recipient_folded=? "
            "ORDER BY timestamp ASC LIMIT ?",
            (lower_sender_name, fetch_count)
        )
        messages = []
        delete_row_ids = []
        for row in cursor:
            messages.append((row[0], row[1], row[2], row[3]))
            delete_row_ids.append(row[3])
        cursor.close()

        # delete them
        cursor = self.database.cursor()
        for row_id in delete_row_ids:
            cursor.execute(
                "DELETE FROM messages_on_retainer WHERE message_id=?",
                (row_id,)
            )
        self.database.commit()
        cursor.close()

        # check how many are left
        cursor = self.database.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM messages_on_retainer WHERE recipient_folded=?",
            (lower_sender_name,)
        )
        remaining = 0
        for row in cursor:
            remaining = row[0]
        cursor.close()

        # output them, if any
        if len(messages) > 0:
            self.connector.send_message(
                "Replaying {0} messages for {1}!".format(len(messages), message.user_name)
            )
            for (the_timestamp, the_sender, the_body, the_message_id) in messages:
                logger.debug("delivering {0}'s retained message {1} to {2} as part of a chunk".format(
                    repr(the_sender), repr(the_body), repr(message.user_name)
                ))
                self.connector.send_message("{0} <[noparse]{1}[/noparse]> {2}".format(
                    self.format_timestamp(the_message_id, the_timestamp),
                    the_sender,
                    the_body
                ))

        # output remaining messages count
        if remaining == 0:
            if len(messages) > 0:
                self.connector.send_message("{0} has no more messages left to deliver!".format(message.user_name))
            else:
                self.connector.send_message("{0} has no messages to deliver!".format(message.user_name))
        else:
            self.connector.send_message("{0} has {1} messages left to deliver!".format(message.user_name, remaining))

    def message_received(self, message):
        """
        Called by the communicator when a new message has been received.
        :type message: vbcbbot.chatbox_connector.ChatboxMessage
        """
        lower_sender_name = message.user_name.lower()

        # parse and strip
        body = remove_control_characters_and_strip(message.decompiled_body())

        # process potential message sends
        self.potential_message_send(message, body, lower_sender_name)

        # process potential deliver request
        self.potential_deliver_request(message, body, lower_sender_name)

        if self.connector.should_stfu():
            # don't bother just yet
            return

        # check if the sender should get any messages
        cursor = self.database.cursor()
        cursor.execute(
            "SELECT timestamp, sender_original, body, message_id FROM messages "
            "WHERE recipient_folded=? ORDER BY timestamp ASC",
            (lower_sender_name,)
        )
        messages = []
        for bin_row in cursor:
            messages.append((bin_row[0], bin_row[1], bin_row[2], bin_row[3]))
        cursor.close()

        # check how many messages the user has on retainer
        cursor = self.database.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM messages_on_retainer WHERE recipient_folded=?",
            (lower_sender_name,)
        )
        on_retainer = 0
        for row in cursor:
            on_retainer = row[0]

        retainer_text = ""
        if on_retainer > 0:
            retainer_text = " (and {0} pending !delivermsg)".format(on_retainer)

        if len(messages) == 0:
            # meh
            return
        elif len(messages) == 1:
            # one message
            (the_timestamp, the_sender, the_body, the_message_id) = messages[0]
            logger.debug("delivering {0}'s message #{3} {1} to {2}".format(
                repr(the_sender), repr(the_body), repr(message.user_name), repr(the_message_id)
            ))
            self.connector.send_message(
                "Message for [noparse]{0}[/noparse]{4}! {1} <[noparse]{2}[/noparse]> {3}".format(
                    message.user_name,
                    self.format_timestamp(the_message_id, the_timestamp),
                    the_sender,
                    the_body,
                    retainer_text
                )
            )
        elif len(messages) >= self.too_many_messages:
            logger.debug("{0} got {1} messages; putting on retainer".format(message.user_name, len(messages)))
            self.connector.send_message(
                "{0} new messages for [noparse]{1}[/noparse]{2}! Use \u201c!delivermsg [i]maxnumber[/i]\u201d to get "
                "them!".format(
                    len(messages),
                    message.user_name,
                    retainer_text
                )
            )

            # put on retainer
            cursor = self.database.cursor()
            cursor.execute(
                "INSERT INTO messages_on_retainer SELECT * FROM messages WHERE recipient_folded=? "
                "ORDER BY timestamp ASC",
                (lower_sender_name,)
            )
            self.database.commit()
            cursor.close()
            # non-retained messages will be deleted below
        else:
            # multiple messages
            self.connector.send_message("{0} new messages for [noparse]{1}[/noparse]{2}!".format(
                len(messages),
                message.user_name,
                retainer_text
            ))
            for (the_timestamp, the_sender, the_body, the_message_id) in messages:
                logger.debug("delivering {0}'s message #{3} {1} to {2} as part of a chunk".format(
                    repr(the_sender), repr(the_body), repr(message.user_name), repr(message_id)
                ))
                self.connector.send_message("{0} <[noparse]{1}[/noparse]> {2}".format(
                    self.format_timestamp(the_message_id, the_timestamp),
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

        self.too_many_messages = 10
        if "too many messages" in config_section:
            self.too_many_messages = int(config_section["too many messages"])

        self.timestamp_link = None
        if "timestamp link" in config_section:
            self.timestamp_link = config_section["timestamp link"]

        cursor = self.database.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            message_id INT NOT NULL PRIMARY KEY,
            timestamp INT NOT NULL,
            sender_original TEXT NOT NULL,
            recipient_folded TEXT NOT NULL,
            body TEXT NOT NULL
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages_on_retainer (
            message_id INT NOT NULL PRIMARY KEY,
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
        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_on_retainer_recipient_timestamp
        ON messages_on_retainer (recipient_folded, timestamp ASC)
        """)
        self.database.commit()
