from http.cookiejar import CookieJar
from urllib.parse import urlencode, urljoin
from urllib.request import build_opener, HTTPCookieProcessor

__author__ = 'ondra'


def encode_post_data(dictionary):
    return urlencode(dictionary, encoding="utf-8").encode("us-ascii")


def login_and_go_to_faq(base_url, username, password):
    # prepare a cookie-enabled URL opener
    cookie_jar = CookieJar()
    url_opener = build_opener(HTTPCookieProcessor(cookie_jar))

    # calculate some URLs
    login_url = urljoin(base_url, "login.php?do=login")

    # log in
    post_values = {
        "vb_login_username": username,
        "vb_login_password": password,
        "cookieuser": "1",
        "s": "",
        "do": "login",
        "vb_login_md5password": "",
        "vb_login_md5password_utf": ""
    }
    post_data = encode_post_data(post_values)
    print("logging in")
    login_response = url_opener.open(login_url, data=post_data)
    login_response.read()

    # return the opener for further usage
    return url_opener


def add_common_arguments_to_parser(parser):
    parser.add_argument("-u", "--username", required=True, help="the username with which to log in")
    parser.add_argument("-b", "--base-url", required=True, help="the base URL of the forum")