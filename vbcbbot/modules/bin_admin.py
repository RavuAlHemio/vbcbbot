from vbcbbot.modules import Module

import bs4
import logging
import re

__author__ = 'ondra'

logger = logging.getLogger("vbcbbot.ma48")
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
        body = message.body_soup().text.strip()

        if body.startswith("!"):
            # bot trigger; ignore
            logger.debug("ignoring bot trigger " + repr(body[:16]))
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

            logger.debug("{0} tossed {1} into {2} using {3}".format(message.user_name, repr(what),
                                                                    repr(where), repr(arrow)))

            if where not in self.bins_contents:
                self.bins_contents[where] = []

            # put!
            self.bins_contents[where].append(BinItem(what, arrow, message.user_name))

    def message_received(self, message):
        """Called by the communicator when a new message has been received."""

        # extract text and strip
        body = message.body_soup().text.strip()

        if body == "!tonnen":
            logger.debug("bin overview request from " + message.user_name)
            if len(self.bins_contents) == 0:
                self.connector.send_message("Ich kenne keine Tonnen.")
                return
            elif len(self.bins_contents) == 1:
                msg = "Ich kenne folgende Tonne: "
            else:
                msg = "Ich kenne folgende Tonnen: "
            msg += ", ".join([repr(waste_bin) for waste_bin in self.bins_contents])
            self.connector.send_message(msg)
            return

        elif body.startswith("!tonneninhalt "):
            logger.debug("bin contents request from " + message.user_name)
            waste_bin_name = body[len("!tonneninhalt "):].strip().lower()
            logger.debug("requesting contents of " + repr(waste_bin_name))

            if waste_bin_name in self.bins_contents:
                this_bin_contents = self.bins_contents[waste_bin_name]
                if len(this_bin_contents) == 0:
                    self.connector.send_message("In dieser Tonne befindet sich nichts.")
                    return
                elif len(this_bin_contents) == 1:
                    msg = "In dieser Tonne befindet sich: "
                else:
                    msg = "In dieser Tonne befinden sich: "
                msg += ", ".join([item.item for item in this_bin_contents])
                self.connector.send_message(msg)
                return
            else:
                self.connector.send_message("Diese Tonne kenne ich nicht.")
                return

        elif body.startswith("!entleere "):
            logger.debug("bin emptying request from " + message.user_name)
            waste_bin_name = body[len("!entleere "):].strip().lower()
            logger.debug("requesting emptying of " + repr(waste_bin_name))
            if waste_bin_name in self.bins_contents:
                self.bins_contents[waste_bin_name].clear()
                self.connector.send_message("Tonne entleert.")
                return
            else:
                self.connector.send_message("Diese Tonne kenne ich nicht.")
                return

        elif body == "!m\u00fcllsammlung":
            logger.debug("bin removal request from " + message.user_name)
            self.bins_contents.clear()
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

        self.bins_contents = {}
