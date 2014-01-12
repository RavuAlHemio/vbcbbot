__author__ = 'ondra'


class Module:
    """An abstract module which handles chatbox events."""
    def message_modified(self, modified_message):
        """
        Act upon a modification of a message currently visible in the chatbox. Called by the
        communicator.
        :type modified_message: ChatboxMessage
        :param modified_message: The updated message object.
        """
        pass

    def message_received(self, new_message):
        """
        Act upon the reception of a new message. Called by the communicator.
        :type new_message: ChatboxMessage
        :param new_message: The new message object.
        """
        pass

    def message_received_on_new_connection(self, new_message):
        """
        Act upon the reception of a new message that arrived as part of the "just connected" salvo.
        Called by the communicator. Calls message_received by default.
        :type new_message: ChatboxMessage
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
        self.connector.subscribe_to_new_messages(self.message_received)
        self.connector.subscribe_to_modified_messages(self.message_modified)
        self.connector.subscribe_to_new_messages_from_salvo(self.message_received_on_new_connection)

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
