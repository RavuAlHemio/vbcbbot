from vbcbbot.modules import Module

import logging
import random
import re
import sqlite3
import time

__author__ = 'ondra'
logger = logging.getLogger("vbcbbot.modules.stfu")
time_re = re.compile(
    "^"
    "(?:([1-9][0-9]*)w)?"
    "(?:([1-9][0-9]*)d)?"
    "(?:([1-9][0-9]*)h)?"
    "(?:([1-9][0-9]*)min)?"
    "(?:([1-9][0-9]*)s)?"
    "$"
)
time_format = "%Y-%m-%d %H:%M:%S"


def duration_string_to_seconds(duration_string):
    """
    Returns the number of seconds described by the duration string.
    :param duration_string: The duration string to parse.
    :type duration_string: str
    :return: The number of seconds described by the duration string.
    """
    if duration_string == "forever":
        return -1

    match = time_re.match(duration_string)
    seconds = 0

    if match is None:
        return seconds

    if match.group(1) is not None:
        seconds += int(match.group(1)) * (60*60*24*7)

    if match.group(2) is not None:
        seconds += int(match.group(2)) * (60*60*24)

    if match.group(3) is not None:
        seconds += int(match.group(3)) * (60*60)

    if match.group(4) is not None:
        seconds += int(match.group(4)) * 60

    if match.group(5) is not None:
        seconds += int(match.group(5))

    return seconds


class Stfu(Module):
    """Processes the !stfu command and allows banning users from utilizing this functionality."""

    def send_snark(self, user_name):
        """Output a snarky message."""
        if len(self.snark) > 0:
            snarky_message = self.random.choice(self.snark)
            formatted_snarky_message = snarky_message.replace("&&USERNAME&&", user_name)
            self.connector.send_message(formatted_snarky_message)

    def message_received_on_new_connection(self, new_message):
        # do nothing
        return

    def message_received(self, new_message):
        """:type new_message: vbcbbot.chatbox_connector.ChatboxMessage"""

        if self.connector.username == new_message.user_name:
            # ignore my own messages
            return

        body = new_message.body_soup().text.strip()

        if body == "!stfu":
            # check for ban
            the_time = time.time()
            cursor = self.database.cursor()
            cursor.execute(
                "SELECT deadline FROM running_bans WHERE banned_user=?",
                (new_message.user_name,)
            )
            for row in cursor:
                if row[0] is None:
                    # ignore it
                    logger.debug("{0} wants to shut be up but they're permabanned".format(
                        new_message.user_name
                    ))
                    self.send_snark(new_message.user_name)
                    return
                elif int(row[0]) > the_time:
                    # ignore it
                    logger.debug("{0} wants to shut me up but they're banned until {1}".format(
                        new_message.user_name,
                        time.strftime(time_format, time.localtime(the_time))
                    ))
                    self.send_snark(new_message.user_name)
                    return

            # no ban -- STFU
            logger.info("{0} shut me up for {1} minutes".format(
                new_message.user_name, self.stfu_duration/60
            ))
            self.who_shut_me_up_last = new_message.user_name
            self.connector.stfu_deadline = the_time + self.stfu_duration

        elif body == "!unstfu":
            if new_message.user_name not in self.admins:
                logger.debug("{0} wants to un-stfu me, but they aren't an admin".format(
                    new_message.user_name
                ))
                return

            logger.info("{0} un-stfu-ed me".format(
                new_message.user_name
            ))
	    self.connector.stfu_deadline = None
            self.connector.send_message("I can speak again!")

        elif body.startswith("!stfuban "):
            if new_message.user_name not in self.admins:
                logger.debug("{0} wants to ban someone, but they aren't an admin".format(
                    new_message.user_name
                ))
                self.send_snark(new_message.user_name)
                return

            body_rest = body[len("!stfuban "):]
            next_space = body_rest.find(" ")
            if next_space == -1:
                self.connector.send_message("Usage: !stfuban timespec username")
                return

            time_spec = body_rest[:next_space]
            ban_this_user = body_rest[next_space+1:]

            seconds = duration_string_to_seconds(time_spec)
            if seconds == 0:
                self.connector.send_message("Invalid timespec!")
                return
            elif seconds == -1:
                deadline = None
            else:
                deadline = time.time() + seconds

            # insert it into the DB
            cursor = self.database.cursor()
            cursor.execute(
                "INSERT OR REPLACE INTO "
                "running_bans (banned_user, deadline, banner) "
                "VALUES (?, ?, ?)",
                (ban_this_user, deadline, new_message.user_name)
            )
            self.database.commit()

            if self.who_shut_me_up_last == ban_this_user:
                # un-STFU
                self.connector.stfu_deadline = None

            logger.info("{0} banned {1} from using !stfu for {2}".format(
                new_message.user_name, ban_this_user, time_spec
            ))
            if deadline is None:
                self.connector.send_message(
                    "Alright! Banning {0} from using the !stfu function.".format(
                        ban_this_user
                    ),
                    bypass_stfu=True
                )
            else:
                self.connector.send_message(
                    "Alright! Banning {0} from using the !stfu function until {1}.".format(
                        ban_this_user, time.strftime(time_format, time.localtime(deadline))
                    ),
                    bypass_stfu=True
                )

        elif body.startswith("!stfuunban "):
            if new_message.user_name not in self.admins:
                logger.debug("{0} wants to unban someone, but they aren't an admin".format(
                    new_message.user_name
                ))
                self.send_snark(new_message.user_name)
                return

            unban_this_user = body[len("!stfuunban "):]

            cursor = self.database.cursor()
            cursor.execute("DELETE FROM running_bans WHERE banned_user=?", (unban_this_user,))
            self.database.commit()

            logger.info("{0} unbanned {1} from using !stfu".format(
                new_message.user_name, unban_this_user
            ))
            if cursor.rowcount > 0:
                self.connector.send_message("Alright, {0} may use !stfu again.".format(
                    unban_this_user
                ))
            else:
                self.connector.send_message("{0} wasn't even banned...?".format(
                    unban_this_user
                ))

    def __init__(self, connector, config_section):
        """
        Create a new STFU responder.
        :param connector: The communicator used to communicate with the chatbox.
        :param config_section: A dictionary of configuration values for this module.
        """
        Module.__init__(self, connector, config_section)

        if config_section is None:
            config_section = {}

        self.stfu_duration = 30*60
        if "duration" in config_section:
            self.stfu_duration = int(config_section["duration"])

        self.database = None
        if "database" in config_section:
            self.database = sqlite3.connect(config_section["database"], check_same_thread=False)
        else:
            self.database = sqlite3.connect(":memory:", check_same_thread=False)

        self.snark = []
        if "snark" in config_section:
            for line in config_section["snark"].split("\n"):
                stripped_line = line.strip()
                if len(stripped_line) == 0:
                    continue
                self.snark.append(stripped_line)

        self.admins = set()
        if "admins" in config_section:
            for line in config_section["admins"].split("\n"):
                stripped_line = line.strip()
                if len(stripped_line) == 0:
                    continue
                self.admins.add(stripped_line)

        self.random = random.Random()
        self.who_shut_me_up_last = None

        cursor = self.database.cursor()
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS running_bans (
            banned_user TEXT NOT NULL,
            deadline INT,
            banner TEXT NOT NULL,
            PRIMARY KEY (banned_user)
        )
        """)
        self.database.commit()

        # clear out old bans
        cursor = self.database.cursor()
        cursor.execute(
            "DELETE FROM running_bans WHERE deadline < ?",
            (time.time(),)
        )
        self.database.commit()
