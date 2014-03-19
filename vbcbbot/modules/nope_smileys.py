from vbcbbot.modules import Module

import logging
import queue
import threading
import time

__author__ = 'ondra'

logger = logging.getLogger("vbcbbot.modules.nope_smileys")


class NopeSmileys(Module):
    """Responds with "noped" versions of smileys to each smiley posted."""

    def message_received(self, message):
        """Called by the communicator when a new message has been received."""

        soup = message.body_soup()
        for image in soup.find_all("img", src=True):
            src = image['src']
            if src in self.nope_mapping:
                logger.debug("smiley {0} maps to nope smiley {1}".format(src,
                                                                         self.nope_mapping[src]))
                try:
                    self.nope_queue.put(self.nope_mapping[src], block=False)
                except queue.Full:
                    # never mind; skip the rest of this message too
                    return

    def nope_sender(self):
        try:
            while not self.stop_now:
                send_these = []
                try:
                    while True:
                        send_this = self.nope_queue.get(block=False)
                        send_these.append(send_this)
                        self.nope_queue.task_done()
                except queue.Empty:
                    # we jumped out of the inner loop
                    pass

                if len(send_these) > 0:
                    send_these_commands = ["[icon]{0}[/icon]".format(t) for t in send_these]
                    message = " ".join(send_these_commands)
                    self.connector.send_message(message)

                time.sleep(self.nap_time)
        except:
            logger.exception("nope sender")
            raise

    def __init__(self, connector, config_section=None):
        """
        Create a new no-devil-banana responder.
        :param connector: The communicator used to communicate with the chatbox.
        :type connector: vbcbbot.chatbox_connector.ChatboxConnector
        :param config_section: The configuration section for this module.
        """
        Module.__init__(self, connector, config_section)

        if config_section is None:
            config_section = {}

        smiley_to_nope = {}
        for line in config_section['smiley to nope'].split("\n"):
            key_val = line.split(" ")
            if len(key_val) != 2:
                continue
            smiley_to_nope[key_val[0]] = key_val[1]

        self.nap_time = 30
        self.stop_now = False
        self.nope_queue = queue.Queue(maxsize=128)

        self.nope_mapping = {}

        for (smiley, yes_url) in connector.smiley_codes_to_urls.items():
            if smiley in smiley_to_nope:
                self.nope_mapping[yes_url] = smiley_to_nope[smiley]

        self.nope_sender_thread = threading.Thread(None, self.nope_sender, "NopeSmileys sender")

    def start(self):
        self.nope_sender_thread.start()

    def stop(self):
        self.stop_now = True
