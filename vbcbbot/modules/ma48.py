from vbcbbot.modules import Module

import bs4
import logging
import re

__author__ = 'ondra'

logger = logging.getLogger("vbcbbot.modules.ma48")
right_arrows_to_left_arrows = {
    "->": "<-",
    "=>": "<=",
    "\u2192": "\u2190",
    "\u219d": "\u219c",
    "\u21a0": "\u219e",
    "\u21a3": "\u21a2",
    "\u21a6": "\u21a4",
    "\u21aa": "\u21a9",
    "\u21ac": "\u21ab",
    "\u21b1": "\u21b0",
    "\u21b3": "\u21b2",
    "\u21b7": "\u21b6",
    "\u21c0": "\u21bc",
    "\u21c1": "\u21bd",
    "\u21c9": "\u21c7",
    "\u21d2": "\u21d0",
    "\u21db": "\u21da",
    "\u21dd": "\u21dc",
    "\u21e2": "\u21e0",
    "\u21e5": "\u21e4",
    "\u21e8": "\u21e6",
    "\u21f4": "\u2b30",
    "\u21f6": "\u2b31",
    "\u21f8": "\u21f7",
    "\u21fb": "\u21fa",
    "\u21fe": "\u21fd",
    "\u27f4": "\u2b32",
    "\u27f6": "\u27f5",
    "\u27f9": "\u27f8",
    "\u27fc": "\u27fb",
    "\u27fe": "\u27fd",
    "\u27ff": "\u2b33",
    "\u2900": "\u2b34",
    "\u2901": "\u2b35",
    "\u2903": "\u2902",
    "\u2905": "\u2b36",
    "\u2907": "\u2906",
    "\u290d": "\u290c",
    "\u290f": "\u290e",
    "\u2910": "\u2b37",
    "\u2911": "\u2b38",
    "\u2914": "\u2b39",
    "\u2915": "\u2b3a",
    "\u2916": "\u2b3b",
    "\u2917": "\u2b3c",
    "\u2918": "\u2b3d",
    "\u291a": "\u2919",
    "\u291c": "\u291b",
    "\u291e": "\u291d",
    "\u2920": "\u291f",
    "\u2933": "\u2b3f",
    "\u2937": "\u2936",
    "\u2939": "\u2938",
    "\u293f": "\u293e",
    "\u2942": "\u2943",
    "\u2945": "\u2946",
    "\u2953": "\u2952",
    "\u2957": "\u2956",
    "\u295b": "\u295a",
    "\u295f": "\u295e",
    "\u2964": "\u2962",
    "\u296c": "\u296a",
    "\u296d": "\u296b",
    "\u2971": "\u2b40",
    "\u2972": "\u2b49",
    "\u2974": "\u2973",
    "\u2975": "\u2b4a",
    "\u2978": "\u2976",
    "\u2b43": "\u2977",
    "\u2979": "\u297b",
    "\u2b44": "\u297a",
    "\u297c": "\u297d",
    "\u27a1": "\u2b05",
    "\u2b0e": "\u2b10",
    "\u2b0f": "\u2b11",
    "\u2b46": "\u2b45",
    "\u2b47": "\u2b41",
    "\u2b48": "\u2b42",
    "\u2b4c": "\u2b4b",
}
right_arrows_delimited_by_pipes = "|".join(right_arrows_to_left_arrows.keys())
waste_bin_re = re.compile("[tT][oO][nN][nN][eE]")


class Ma48(Module):
    """Answers "something -> Tonne" with "something <- Tonne"."""

    def message_received(self, message):
        """Called by the communicator when a new message has been received."""

        if message.user_name == self.connector.username:
            # ignore my own bin throwing
            return

        body_lxml = message.body_lxml()
        if body_lxml is None:
            return
        body = "".join(body_lxml.itertext())

        match = waste_bin_re.search(body)
        if match is not None:
            # a waste bin has been found
            # make sure there is at least one arrow
            have_arrow = False
            for arrow in right_arrows_to_left_arrows.keys():
                if arrow in body:
                    have_arrow = True
                    break
            if not have_arrow:
                # don't bother
                return

            response = body
            old_response = None
            while response != old_response:
                old_response = response
                for (right, left) in right_arrows_to_left_arrows.items():
                    response = response.replace(right, left)
            # reached a fixed point
            self.connector.send_message(response)

    def __init__(self, connector, config_section):
        """
        Create a new MA48 responder.
        :param connector: The communicator used to communicate with the chatbox.
        :param config_section: A dictionary of configuration values for this module.
        """
        Module.__init__(self, connector, config_section)

        if config_section is None:
            config_section = {}
