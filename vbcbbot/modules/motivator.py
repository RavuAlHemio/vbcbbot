from vbcbbot.modules import Module

import logging
import random

__author__ = 'ondra'

logger = logging.getLogger("vbcbbot.modules.motivator")


class Motivator(Module):
    """Motivates those who ask for it."""

    def message_received_on_new_connection(self, message):
        return

    def message_received(self, message):
        """Called by the communicator when a new message has been received."""

        # extract text and strip
        body = message.body_soup().text.strip()

        if body == "!motivate me":
            # pick a category
            category_list = list(self.categories)
            category = self.random.choice(category_list)
            motivator = self.random.choice(self.categories[category])

            self.connector.send_message("{0}: {1}".format(message.user_name, motivator))

        elif body.startswith("!motivate me using "):
            category = body[len("!motivate me using "):].strip()
            if category not in self.categories:
                self.connector.send_message("{0}: I don\u2019 know that motivator category.")
                return
            motivator = self.random.choice(self.categories[category])
            self.connector.send_message("{0}: {1}".format(message.user_name, motivator))

        elif body.startswith("!how can you motivate me"):
            self.connector.send_message("{0}: I can motivate you using: ".format(message.user_name)
                                        + ", ".join(sorted(self.categories.keys())))

    def __init__(self, connector, config_section):
        """
        Create a new Motivator responder.
        :param connector: The communicator used to communicate with the chatbox.
        :param config_section: A dictionary of configuration values for this module.
        """
        Module.__init__(self, connector, config_section)

        if config_section is None:
            config_section = {}

        self.categories = {}
        for (category, phrase_string) in config_section.items():
            phrases = []
            for phrase_line in phrase_string.split("\n"):
                phrase = phrase_line.strip()
                if len(phrase) == 0:
                    continue
                phrases.append(phrase)
            self.categories[category] = phrases

        self.random = random.Random()
