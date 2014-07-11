from vbcbbot.modules import Module

import configparser
import logging
import random

__author__ = 'ondra'

logger = logging.getLogger("vbcbbot.modules.motivator")


class Motivator(Module):
    """Motivates those who ask for it."""

    def send_random_motivator_from_list(self, motivator_list, request_message):
        # pick a motivator
        motivator = self.random.choice(motivator_list)

        # personalize
        motivator = motivator.replace("&&USERNAME&&", request_message.user_name)

        # send
        self.connector.send_message("{0}: {1}".format(request_message.user_name, motivator))

    def message_received_on_new_connection(self, message):
        return

    def message_received(self, message):
        """Called by the communicator when a new message has been received."""

        # extract text, strip and make lowercase
        body_lxml = message.body_lxml()
        if body_lxml is None:
            return
        body = "".join(body_lxml.itertext()).strip().lower()

        # find the verb
        for (verb, categories_to_motivators) in self.verbs_to_categories_to_motivators.items():
            if body == "!{0} me".format(verb):
                # unite the motivators from all categories
                motivator_list = []
                for motivators in categories_to_motivators.values():
                    motivator_list.extend(motivators)

                # pick a motivator
                self.send_random_motivator_from_list(motivator_list, message)

            elif body.startswith("!{0} me using ".format(verb)):
                category = body[len("!{0} me using ".format(verb)):].strip()
                if category not in categories_to_motivators:
                    self.connector.send_message("{0}: I don\u2019t know that category.")
                    return

                motivator_list = list(categories_to_motivators[category])
                self.send_random_motivator_from_list(motivator_list, message)

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
                categories_to_motivators[category.lower()] = motivators
            self.verbs_to_categories_to_motivators[verb.lower()] = categories_to_motivators

        self.random = random.Random()
