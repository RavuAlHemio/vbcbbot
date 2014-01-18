from vbcbbot.modules import Module

import logging
import random
import threading
import time

__author__ = 'ondra'

logger = logging.getLogger("vbcbbot.modules.no_devil_banana")


class NoDevilBanana(Module):
    """Responds with :nodb: to a whole collection of devil banana types."""

    def message_modified(self, message):
        """Called by the communicator when a visible message has been modified."""

        soup = message.body_soup()
        for image in soup.find_all("img", src=True):
            if image['src'] == self.no_devil_banana_url:
                logger.debug(":nodb: found in {0}'s edited message {1}".format(
                    message.user_name, message.id
                ))
                with self.last_lock:
                    if self.last_nodb_message < message.id:
                        self.last_nodb_message = message.id
            elif image['src'] in self.devil_banana_urls:
                if message.user_name == self.connector.username:
                    # ignore my own devil banana messages
                    return
                logger.debug("devil banana {2} found in {0}'s edited message {1}".format(
                    message.user_name, message.id, image['src']
                ))
                with self.last_lock:
                    if self.last_banana_message < message.id:
                        self.last_banana_message_due_to_edit = True
                        self.last_banana_message = message.id

    def message_received(self, message):
        """Called by the communicator when a new message has been received."""

        soup = message.body_soup()
        for image in soup.find_all("img", src=True):
            if image['src'] == self.no_devil_banana_url:
                logger.debug(":nodb: found in {0}'s message {1}".format(
                    message.user_name, message.id
                ))
                with self.last_lock:
                    self.last_nodb_message = message.id
            elif image['src'] in self.devil_banana_urls:
                if message.user_name == self.connector.username:
                    # ignore my own devil banana messages
                    return
                logger.debug("devil banana {2} found in {0}'s message {1}".format(
                    message.user_name, message.id, image['src']
                ))
                with self.last_lock:
                    self.last_banana_message_due_to_edit = False
                    self.last_banana_message = message.id

    def nodb_sender(self):
        try:
            while not self.stop_now:

                send_nodb = False
                addendum = False
                with self.last_lock:
                    if self.last_banana_message > self.last_nodb_message:
                        logger.debug(
                            "last banana message {0} later than last :nodb: message {1}".format(
                                self.last_banana_message, self.last_nodb_message
                            )
                        )
                        send_nodb = True
                        if self.last_banana_message_due_to_edit:
                            addendum = True

                if send_nodb:
                    outgoing = ":nodb:"
                    if addendum:
                        outgoing += " " + self.randomizer.choice(self.addenda_banana_edited_in)
                    self.connector.send_message(outgoing)

                time.sleep(self.nap_time)
        except:
            logger.exception("nodb sender")
            raise

    def __init__(self, connector, config_section=None):
        """
        Create a new no-devil-banana responder.
        :param connector: The communicator used to communicate with the chatbox.
        :param config_section: The configuration section for this module.
        """
        Module.__init__(self, connector, config_section)

        if config_section is None:
            config_section = {}

        self.no_devil_banana_url = config_section['no devil banana url']
        self.devil_banana_urls = config_section['devil banana urls']
        self.addenda_banana_edited_in = config_section['addenda banana edited in'].split("\n")

        self.nap_time = 10
        self.stop_now = False
        self.last_nodb_message = -1
        self.last_banana_message = -1
        self.last_banana_message_due_to_edit = False
        self.last_lock = threading.Lock()
        self.randomizer = random.Random()

        self.nodb_sender_thread = threading.Thread(None, self.nodb_sender, "NoDevilBanana sender")

    def start(self):
        self.nodb_sender_thread.start()

    def stop(self):
        self.stop_now = True
