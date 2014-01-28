from vbcbbot.modules import Module

import configparser
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

        # find the verb
        for (verb, categories_to_motivators) in self.verbs_to_categories_to_motivators.items():
            if body == "!{0} me".format(verb):
                # pick a category
                category_list = list(categories_to_motivators.keys())
                category = self.random.choice(category_list)

                # pick a motivator
                motivator_list = list(categories_to_motivators[category])
                motivator = self.random.choice(motivator_list)

                # personalize
                motivator = motivator.replace("&&USERNAME&&", message.user_name)

                self.connector.send_message("{0}: {1}".format(message.user_name, motivator))

            elif body.startswith("!{0} me using ".format(verb)):
                category = body[len("!{0} me using ".format(verb)):].strip()
                if category not in categories_to_motivators:
                    self.connector.send_message("{0}: I don\u2019t now that category.")
                    return

            elif body == "!how can you {0} me".format(verb):
                categories_string = ", ".join(sorted(categories_to_motivators.keys()))
                self.connector.send_message("{0}: I can {2} you using {1}".format(
                    message.user_name, categories_string, verb
                ))

    def __init__(self, connector, config_section):
        """
        Create a new Motivator responder.
        :param connector: The communicator used to communicate with the chatbox.
        :param config_section: A dictionary of configuration values for this module.
        """
        Module.__init__(self, connector, config_section)

        if config_section is None:
            config_section = {}

        config = configparser.ConfigParser()
        with open(config_section["config file"], "r") as f:
            config.read_file(f)

        self.verbs_to_categories_to_motivators = {}
        for (verb, section) in config.items():
            if verb == "DEFAULT":
                continue

            categories_to_motivators = {}
            for (category, motivators_string) in section.items():
                motivators = set()
                for line in motivators_string.split("\n"):
                    motivator = line.strip()
                    if len(motivator) == 0:
                        continue
                    motivators.add(motivator)
                categories_to_motivators[category] = motivators
            self.verbs_to_categories_to_motivators[verb] = categories_to_motivators

        logger.debug(self.verbs_to_categories_to_motivators)

        self.random = random.Random()
