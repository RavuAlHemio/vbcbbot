from vbcbbot.modules import Module
from vbcbbot.utils import remove_control_characters_and_strip

import logging
import re
import sqlite3

__author__ = 'ondra'

logger = logging.getLogger("vbcbbot.modules.echelon")
spy_trigger = re.compile("^!(echelon trigger) ([^;]+)[;](.+)$")
stats_trigger = re.compile("^!(echelon incidents) (.+)$")


class Trigger:
    """A trigger describing a username/pattern pair."""

    def __init__(self, trigger_id, user_name, pattern_string):
        self.trigger_id = trigger_id
        self.user_name_lower = user_name.lower()
        self.pattern_string = pattern_string
        self.pattern = re.compile(pattern_string)

    def __repr__(self):
        return "Trigger({0}, {1}, {2})".format(
            repr(self.trigger_id),
            repr(self.user_name_lower),
            repr(self.pattern_string)
        )


class Echelon(Module):
    """Not a part of the NSA's ECHELON program."""

    def potential_stats(self, message, body):
        stats_match = stats_trigger.match(body)
        if stats_match is None:
            return

        cursor = self.database.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM incidents WHERE trigger_id IN ("
            "SELECT trigger_id FROM triggers WHERE target_name_lower=?"
            ")",
            (stats_match.group(2).lower(),)
        )
        the_count = None
        for row in cursor:
            the_count = row[0]

        salutation = "Spymaster" if message.user_name in self.spymasters else "Agent"

        if the_count is None:
            self.connector.send_message(
                "{2} {0}: Subject {1} may or may not have caused any incident.".format(
                    message.user_name, stats_match.group(2), salutation
                )
            )
        else:
            self.connector.send_message(
                "{4} {0}: Subject {1} may or may not have caused {2} {3}.".format(
                    message.user_name,
                    stats_match.group(2),
                    the_count,
                    "incident" if the_count == 1 else "incidents",
                    salutation
                )
            )

    def potential_spy(self, message, body):
        spy_match = spy_trigger.match(body)
        if spy_match is None:
            return

        if message.user_name not in self.spymasters:
            self.connector.send_message(
                "Agent {0}: Your rank is insufficient for this operation.".format(
                    message.user_name
                )
            )
            return

        username = spy_match.group(2).strip()
        regex = spy_match.group(3).strip()

        cursor = self.database.cursor()
        cursor.execute(
            "INSERT INTO triggers (target_name_lower, regex, spymaster_name) VALUES (?, ?, ?)",
            (username.lower(), regex, message.user_name)
        )
        self.database.commit()

        self.connector.send_message("Spymaster {0}: Done.".format(message.user_name))

    def process_message(self, message, modified=False, initial_salvo=False, user_banned=False):
        """
        Called by the communicator when a new or updated message has been received.
        :type message: vbcbbot.chatbox_connector.ChatboxMessage
        """
        if modified or initial_salvo:
            return

        lower_sender_name = message.user_name.lower()

        # parse and strip
        body = remove_control_characters_and_strip(message.decompiled_body())

        if not user_banned:
            self.potential_stats(message, body)
            self.potential_spy(message, body)

        # spy on messages from banned users too

        if lower_sender_name in self.lowercase_user_names_to_triggers:
            for trigger in self.lowercase_user_names_to_triggers[lower_sender_name]:
                m = trigger.pattern.search(body)
                if m is None:
                    continue

                # trigger matched. log this.
                cursor = self.database.cursor()
                cursor.execute(
                    "INSERT INTO incidents (trigger_id, message_id, timestamp) VALUES (?, ?, ?)",
                    (trigger.trigger_id, message.id, message.timestamp)
                )
                self.database.commit()


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

        self.spymasters = set()
        if "spymasters" in config_section:
            for line in config_section["spymasters"].split("\n"):
                stripped_line = line.strip()
                if len(stripped_line) == 0:
                    continue
                self.spymasters.add(stripped_line)

        cursor = self.database.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS triggers (
            trigger_id INTEGER PRIMARY KEY AUTOINCREMENT,
            target_name_lower TEXT NOT NULL,
            regex TEXT NOT NULL,
            spymaster_name TEXT NOT NULL
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS incidents (
            incident_id INTEGER PRIMARY KEY AUTOINCREMENT,
            trigger_id INTEGER NOT NULL REFERENCES triggers (trigger_id),
            message_id INTEGER NOT NULL,
            timestamp INTEGER NOT NULL
        )
        """)
        cursor.execute("CREATE INDEX IF NOT EXISTS index_target_name_lower ON triggers (target_name_lower)")
        self.database.commit()

        self.lowercase_user_names_to_triggers = {}
        cursor.execute("SELECT trigger_id, target_name_lower, regex FROM triggers")
        for row in cursor:
            trig = Trigger(row[0], row[1], row[2])
            if trig.user_name_lower not in self.lowercase_user_names_to_triggers:
                self.lowercase_user_names_to_triggers[trig.user_name_lower] = [trig]
            else:
                self.lowercase_user_names_to_triggers[trig.user_name_lower].append(trig)
        cursor.close()
