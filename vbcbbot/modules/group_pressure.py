from vbcbbot.modules import Module
import logging

__author__ = 'ondra'
logger = logging.getLogger("vbcbbot.modules.group_pressure")


class GroupPressure(Module):
    """
    Submit to group pressure: if enough people say a specific thing in the last X messages, join in
    on the fray!
    """

    def process_message(self, message, modified=False, initial_salvo=False, user_banned=False):
        if user_banned:
            return

        body = message.decompiled_body().strip()
        if len(body) == 0:
            # nope
            return

        # clean out the backlog
        if len(self.backlog) >= self.backlog_size:
            difference = len(self.backlog) - self.backlog_size
            self.backlog = self.backlog[difference:]

        if modified:
            # find the message in the backlog and modify it
            new_backlog = []
            for (message_id, message_sender, message_body) in self.backlog:
                if message_id == message.id:
                    # store the updated version
                    new_backlog.append((message.id, message.user_name, body))
                else:
                    # port it unchanged
                    new_backlog.append((message_id, message_sender, message_body))
            self.backlog = new_backlog
        else:
            # simply append the message
            self.backlog.append((message.id, message.user_name, body))

        if initial_salvo:
            return

        # perform accounting
        message_senders = {}
        for (message_id, sender, message) in self.backlog:
            if sender == self.connector.username:
                # this is my message -- start counting from zero, so to speak
                message_senders[message] = set()
            elif message not in message_senders:
                # one occurrence
                message_senders[message] = {sender}
            else:
                # add this message's sender to the set of senders
                # (ignores dupes)
                message_senders[message].add(sender)

        # find some group pressure to bow to
        for (message, senders) in message_senders.items():
            if len(senders) >= self.trigger_count:
                logger.debug("bowing to the group pressure of {0} sending {1}".format(
                    repr(senders), repr(message)
                ))
                # submit to group pressure
                self.connector.send_message(message)

                # fake this message into the backlog to prevent duplicates
                self.backlog.append((-1, self.connector.username, message))

    def __init__(self, connector, config_section):
        Module.__init__(self, connector, config_section)

        self.backlog_size = 20
        self.trigger_count = 3
        if "backlog size" in config_section:
            self.backlog_size = int(config_section["backlog size"])
        if "trigger count" in config_section:
            self.trigger_count = int(config_section["trigger count"])

        self.backlog = []
