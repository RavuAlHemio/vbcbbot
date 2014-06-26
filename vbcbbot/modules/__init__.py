__author__ = 'ondra'


class Module:
    """An abstract module which handles chatbox events."""
    def process_message(self, message, modified=False, initial_salvo=False, user_banned=False):
        """
        Act upon a new or modified message.
        :param message: The new or updated message object.
        :type message: vbcbbot.chatbox_connector.ChatboxMessage
        :param modified: True if this is a modified message, False if this is a new message.
        :type modified: bool
        :param initial_salvo: True if this message is part of the "just connected" salvo.
        :type initial_salvo: bool
        :param user_banned: True if the user who sent this message is currently banned.
        :type user_banned: False
        """

        # default behavior ensures compatibility

        if user_banned:
            return

        if initial_salvo:
            self.message_received_on_new_connection(message)
        elif modified:
            self.message_modified(message)
        else:
            self.message_received(message)

    def message_modified(self, modified_message):
        """
        Act upon a modification of a message currently visible in the chatbox. Called by the
        communicator.
        :type modified_message: vbcbbot.chatbox_connector.ChatboxMessage
        :param modified_message: The updated message object.
        """
        pass

    def message_received(self, new_message):
        """
        Act upon the reception of a new message. Called by the communicator.
        :type new_message: vbcbbot.chatbox_connector.ChatboxMessage
        :param new_message: The new message object.
        """
        pass

    def message_received_on_new_connection(self, new_message):
        """
        Act upon the reception of a new message that arrived as part of the "just connected" salvo.
        Called by the communicator. Calls message_received by default.
        :type new_message: vbcbbot.chatbox_connector.ChatboxMessage
        :param new_message: The new message object.
        """
        self.message_received(new_message)

    def __init__(self, connector, config_section=None):
        """
        Construct a new instance of the bot. Stores the connector and subscribes to the relevant
        events.
        :type connector: ChatboxConnector
        :param connector: The connector which facilitates communication with the chatbox.
        :param config_section: A dictionary of configuration values for this module.
        """
        self.connector = connector
        self.connector.subscribe_to_message_updates(self.process_message)

    def start(self):
        """
        Starts background processing if the module requires it. Does nothing by default.
        """
        pass

    def stop(self):
        """
        Stops background processing if any was started using start(). Does nothing by default.
        """
        pass

    @staticmethod
    def fetch_configuration_value_default(section, value_name, default):
        if value_name not in section:
            return default
        return section[value_name]
