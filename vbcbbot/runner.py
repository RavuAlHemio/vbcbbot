from vbcbbot.chatbox_connector import ChatboxConnector

import configparser
import importlib
import logging
import sys

__author__ = 'ondra'

logger = logging.getLogger("vbcbbot.runner")


def run():
    # turn on logging
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)
    stderr_handler = logging.StreamHandler(stream=sys.stderr)
    stderr_handler.setLevel(logging.DEBUG)
    root_logger.addHandler(stderr_handler)

    try:
        # read the config
        config = configparser.ConfigParser()
        with open("vbcbbot.ini", "r") as f:
            config.read_file(f)

        section = config['forum']
        forum_url = section['url']
        forum_username = section['username']
        forum_password = section['password']

        stfu_command = None
        stfu_delay = 30
        if 'communication' in config:
            comm_section = config['communication']
            if 'stfu command' in comm_section:
                stfu_command = comm_section['stfu command']
            if 'stfu delay' in comm_section:
                stfu_delay = int(comm_section['stfu delay'])

        # create the connector
        conn = ChatboxConnector(forum_url, forum_username, forum_password, stfu_command)

        # load the modules
        loaded_modules = set()

        for module_name, class_name in config['modules'].items():
            logger.debug("instantiating {0}.{1}".format(module_name, class_name))
            module_section = {}
            if module_name in config:
                module_section = config[module_name]

            module = importlib.import_module("vbcbbot.modules." + module_name)
            class_ = getattr(module, class_name)
            instance = class_(conn, module_section)

            instance.start()

            loaded_modules.add(instance)

        conn.start()
    except:
        logger.exception("runner")
        raise

if __name__ == '__main__':
    run()
