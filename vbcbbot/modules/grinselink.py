from vbcbbot.modules import Module

import logging

__author__ = 'ondra'

logger = logging.getLogger("vbcbbot.modules.grinselink")
remember_this_many_posts = 30


class Grinselink(Module):
    """Responds to links posted by a specific user with a specific message."""

    def message_modified(self, message):
        if message.user_name != self.username_to_monitor:
            return

        logging.debug("{0}'s message edited!".format(message.user_name))

        if message.id in self.known_grinselink_ids:
            # we already reacted to this
            return

        soup = message.body_soup()
        for _ in soup.find_all("a", href=True):
            logging.info("detected stealth Grinselink")
            self.known_grinselink_ids.add(message.id)
            self.connector.send_message(self.message_to_post_stealth)
            return

    def message_received(self, message):
        """Called by the communicator when a new message has been received."""

        # cull old posts
        for known_message_id in list(self.known_grinselink_ids):
            if abs(known_message_id - message.id) > remember_this_many_posts:
                self.known_grinselink_ids.remove(known_message_id)

        if message.user_name != self.username_to_monitor:
            return

        logging.debug("message posted by {0}!".format(message.user_name))

        soup = message.body_soup()
        for _ in soup.find_all("a", href=True):
            logging.info("detected Grinselink")
            self.known_grinselink_ids.add(message.id)
            self.connector.send_message(self.message_to_post)
            return

    def __init__(self, connector, config_section):
        """
        Create a new grinselink responder.
        :param connector: The communicator used to communicate with the chatbox.
        :param config_section: A dictionary of configuration values for this module.
        """
        Module.__init__(self, connector, config_section)

        if config_section is None:
            config_section = {}

        self.username_to_monitor = config_section["username to monitor"]
        self.message_to_post = config_section["message to post"]
        self.message_to_post_stealth = config_section["message to post stealth"]

        self.known_grinselink_ids = set()
