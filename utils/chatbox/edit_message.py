#!/usr/bin/env python3
from bs4 import BeautifulSoup
from time import sleep
from urllib.parse import urlencode, urljoin
import _utils

url_safe_characters = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.")
server_encoding = "windows-1252"


def encode_outgoing_message(outgoing_message):
    """
    Encode the outgoing message as it can be understood by the server.
    :param outgoing_message: The message that will be sent.
    :return: The bytes representing the message in a format understood by the chatbox.
    """
    ret = ""
    for c in outgoing_message:
        if c in url_safe_characters:
            # URL-safe character
            ret += c
        else:
            # character in the server's encoding?
            try:
                # URL-encode
                for b in c.encode(server_encoding):
                    ret += "%{0:02X}".format(b)
            except UnicodeEncodeError:
                # unsupported natively by the encoding; perform a URL-encoded HTML escape
                ret += "%26%23{0}%3B".format(ord(c))
    return ret


def edit_message(base_url, username, password, message_id, new_body):
    url_opener = _utils.login_and_go_to_faq(base_url, username, password)

    # calculate some more URLs
    faq_url = urljoin(base_url, "faq.php")
    edit_url = urljoin(base_url, "misc.php")

    # go to the FAQ page (page with low backend complexity) to get the security token
    print("fetching security token")
    faq_response = url_opener.open(faq_url)
    soup = BeautifulSoup(faq_response.read())
    token_field = soup.find("input", attrs={"name": "securitytoken"})
    security_token = token_field.attrs["value"]

    # encode the message
    request_string = \
        "do=vsacb_editmessage&s=&securitytoken={0}&id={1}&vsacb_editmessage={2}".format(
            security_token, message_id, encode_outgoing_message(new_body)
        )
    request_bytes = request_string.encode(server_encoding)

    print("updating message")
    edit_response = url_opener.open(edit_url, data=request_bytes)
    edit_response.read()

    print("done")

if __name__ == '__main__':
    from argparse import ArgumentParser
    from getpass import getpass

    parser = ArgumentParser(description="Modify a chatbox message in a vBulletin Chatbox.")
    _utils.add_common_arguments_to_parser(parser)
    parser.add_argument("-i", "--message-id", type=int, required=True,
                        help="the ID of the message to modify")
    parser.add_argument("-m", "--message", type=str, required=True,
                        help='the new body of the message')

    args = parser.parse_args()

    input_password = getpass()

    edit_message(args.base_url, args.username, input_password, args.message_id, args.message)
