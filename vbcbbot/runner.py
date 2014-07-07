from vbcbbot.chatbox_connector import ChatboxConnector
from vbcbbot.html_decompiler import HtmlDecompiler

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
    formatter = logging.Formatter("{name}: {message}", style="{")
    stderr_handler = logging.StreamHandler(stream=sys.stderr)
    stderr_handler.setFormatter(formatter)
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

        bans = set()
        if 'banned' in section:
            for nick_line in section['banned'].split("\n"):
                nick = nick_line.strip().lower()
                bans.add(nick)

        custom_smiley_to_url = {}
        custom_url_to_smiley = {}
        if 'custom smileys' in section:
            for smiley_line in section['custom smileys'].split("\n"):
                pieces = smiley_line.strip().split(" ")
                if len(pieces) != 2:
                    continue
                smiley, url = pieces
                custom_smiley_to_url[smiley] = url
                custom_url_to_smiley[url] = smiley

        refresh_time = 5
        if 'refresh time' in section:
            refresh_time = int(section['refresh time'])

        html_decompiler = None
        if 'html decompiler' in config:
            hd_section = config['html decompiler']
            urls_to_smileys = {}
            tex_prefix = None
            if 'tex prefix' in hd_section:
                tex_prefix = hd_section['tex prefix']
            html_decompiler = HtmlDecompiler(urls_to_smileys, tex_prefix)

        # create the connector
        conn = ChatboxConnector(forum_url, forum_username, forum_password, html_decompiler)
        conn.banned_nicknames = bans
        conn.custom_smiley_codes_to_urls = custom_smiley_to_url
        conn.custom_smiley_urls_to_codes = custom_url_to_smiley
        conn.time_between_reads = refresh_time

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
