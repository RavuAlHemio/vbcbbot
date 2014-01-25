from vbcbbot.modules import Module

import logging
import re
import sqlite3
import time

__author__ = 'ondra'

logger = logging.getLogger("vbcbbot.modules.bin_admin")
special_right_arrows = "\u2192\u219d\u21a0\u21a3\u21a6\u21aa\u21ac\u21b1\u21b3\u21b7\u21c0" + \
    "\u21c1\u21c9\u21d2\u21db\u21dd\u21e2\u21e5\u21e8\u21f4\u21f6\u21f8\u21fb\u21fe\u27f4" + \
    "\u27f6\u27f9\u27fc\u27fe\u27ff\u2900\u2901\u2903\u2905\u2907\u290d\u290f\u2910\u2911" + \
    "\u2914\u2915\u2916\u2917\u2918\u291a\u291c\u291e\u2920\u2933\u2937\u2939\u293f\u2942" + \
    "\u2945\u2953\u2957\u295b\u295f\u2964\u296c\u296d\u2971\u2972\u2974\u2975\u2978\u2b43" + \
    "\u2979\u2b44\u297c\u27a1\u2b0e\u2b0f\u2b46\u2b47\u2b48\u2b4c"

arrow_re_string = "((?:[-=~>]*[>{sra}]+[-=~>]*)+)".format(sra=special_right_arrows)
arrow_re = re.compile(arrow_re_string)
arrow_waste_bin_re = re.compile(
    "^" +  # beginning of the line
    "(.+?)" +  # what to throw out
    arrow_re_string +  # arrows
    "(.*[tT][oO][nN][nN][eE].*)" +  # where to throw it out
    "$"  # end of the line
)


class BinItem:
    def __init__(self, item, arrow, thrower):
        self.item = item
        self.arrow = arrow
        self.thrower = thrower


class BinAdmin(Module):
    """Remembers "something -> somethingTonneSomething"."""

    def message_received_on_new_connection(self, message):
        body = message.decompiled_body()

        if body.startswith("!"):
            # bot trigger; ignore
            trigger = body[:16]
            if len(body) > 16:
                trigger += "..."
            logger.debug("ignoring bot trigger {0}".format(repr(trigger)))
            return

        match = arrow_waste_bin_re.match(body)
        if match is not None:
            # a waste bin toss has been found
            what = match.group(1).strip()
            arrow = match.group(2)
            where = match.group(3).strip().lower()

            if arrow_re.search(what) is not None or arrow_re.search(where) is not None:
                # this might get recursive...
                logger.debug("{0} is trying to trick us by throwing {1} into {2}".format(
                    message.user_name, repr(what), repr(where))
                )
                return

            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())

            logger.debug("{0} tossed {1} into {2} using {3}".format(message.user_name, repr(what),
                                                                    repr(where), repr(arrow)))

            # put!
            cur = self.database.cursor()
            cur.execute("INSERT OR IGNORE INTO bins (bin) VALUES (?)", (where,))
            cur.execute(
                """
                INSERT OR IGNORE INTO bin_items (bin, item, arrow, thrower, timestamp)
                VALUES (?, ?, ?, ?, ?)
                """,
                (where, what, arrow, message.user_name, timestamp)
            )
            self.database.commit()

    def bin_exists(self, bin_name):
        cur = self.database.cursor()
        cur.execute("SELECT bin FROM bins WHERE bin=?", (bin_name,))
        bin_row = cur.fetchone()
        return bin_row is not None

    def message_received(self, message):
        """Called by the communicator when a new message has been received."""

        # extract text and strip
        body = message.body_soup().text.strip()

        if body == "!tonnen":
            logger.debug("bin overview request from " + message.user_name)

            cur = self.database.cursor()
            cur.execute("SELECT bin FROM bins")
            bins = set()
            for bin_row in cur:
                bins.add(bin_row[0])

            if len(bins) == 0:
                self.connector.send_message("Ich kenne keine Tonnen.")
                return
            elif len(bins) == 1:
                msg = "Ich kenne folgende Tonne: "
            else:
                msg = "Ich kenne folgende Tonnen: "
            msg += ", ".join([repr(waste_bin) for waste_bin in bins])
            self.connector.send_message(msg)
            return

        elif body.startswith("!tonneninhalt "):
            logger.debug("bin contents request from " + message.user_name)
            waste_bin_name = body[len("!tonneninhalt "):].strip().lower()
            logger.debug("requesting contents of " + repr(waste_bin_name))

            if not self.bin_exists(waste_bin_name):
                self.connector.send_message("Diese Tonne kenne ich nicht.")
                return

            cur = self.database.cursor()
            cur.execute("SELECT item FROM bin_items WHERE bin=?", (waste_bin_name,))
            items = set()
            for item_row in cur:
                items.add(item_row[0])

            if len(items) == 0:
                self.connector.send_message("In dieser Tonne befindet sich nichts.")
                return
            elif len(items) == 1:
                msg = "In dieser Tonne befindet sich: "
            else:
                msg = "In dieser Tonne befinden sich: "
            msg += ", ".join(items)
            self.connector.send_message(msg)
            return

        elif body.startswith("!entleere "):
            logger.debug("bin emptying request from " + message.user_name)
            waste_bin_name = body[len("!entleere "):].strip().lower()
            logger.debug("requesting emptying of " + repr(waste_bin_name))

            if not self.bin_exists(waste_bin_name):
                self.connector.send_message("Diese Tonne kenne ich nicht.")
                return

            cur = self.database.cursor()
            cur.execute("DELETE FROM bin_items WHERE bin=?", (waste_bin_name,))

            self.connector.send_message("Tonne entleert.")

        elif body == "!m\u00fcllsammlung":
            logger.debug("bin removal request from " + message.user_name)

            cur = self.database.cursor()
            cur.execute("DELETE FROM bin_items")
            cur.execute("DELETE FROM bins")

            self.connector.send_message("Tonnen abgesammelt.")
            return

        # forward this
        self.message_received_on_new_connection(message)

    def __init__(self, connector, config_section):
        """
        Create a new MA48 responder.
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
        CREATE TABLE IF NOT EXISTS bins (
            bin TEXT,
            PRIMARY KEY (bin)
        )
        """)
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS bin_items (
            bin TEXT REFERENCES bins (bin),
            item TEXT,
            arrow TEXT,
            thrower TEXT,
            timestamp TEXT,
            PRIMARY KEY (bin, item)
        )
        """)
        self.database.commit()
