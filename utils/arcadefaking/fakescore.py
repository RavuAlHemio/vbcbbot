#!/usr/bin/env python3
from bs4 import BeautifulSoup
from http.cookiejar import CookieJar
from time import sleep
from urllib.request import build_opener, HTTPCookieProcessor
from urllib.parse import urlencode, urljoin, unquote


def fake(base_url, username, password, game_id, time, score):
    # prepare a cookie-enabled URL opener
    cookie_jar = CookieJar()
    url_opener = build_opener(HTTPCookieProcessor(cookie_jar))

    # calculate some URLs
    login_url = urljoin(base_url, "login.php?do=login")
    arcade_url = urljoin(base_url, "arcade.php")
    play_game_url = urljoin(base_url, "arcade.php?do=play&gameid={0}".format(game_id))
    score_url = urljoin(base_url, "index.php?act=Arcade&do=newscore")

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
    post_data = urlencode(post_values, encoding="utf-8").encode("us-ascii")
    print("logging in")
    login_response = url_opener.open(login_url, data=post_data)
    login_response.read()

    # enter the arcade
    print("entering the arcade")
    arcade_response = url_opener.open(arcade_url)
    arcade_response.read()

    # play the game
    print("playing the game")
    play_game_response = url_opener.open(play_game_url)
    soup = BeautifulSoup(play_game_response.read())

    # find the game's name
    game_flash = soup.find("embed", type="application/x-shockwave-flash")
    if game_flash is None:
        print("didn't find the flash plugin on the game page :'-(")
        return

    flash_vars = game_flash['flashvars'].split("&")
    game_name = None
    for var in flash_vars:
        if var.startswith("gamename="):
            game_name = var[len("gamename="):]

    if game_name is None:
        print("game name not found :'-(")
        return

    # wait the given time
    print("waiting")
    sleep(time)

    post_values = {
        "gscore": score,
        "gname": game_name
    }
    post_data = urlencode(post_values, encoding="utf-8").encode("us-ascii")
    print("submitting fake high score")
    score_response = url_opener.open(score_url, data=post_data)
    score_response.read()

    print("done")

if __name__ == '__main__':
    from argparse import ArgumentParser
    from getpass import getpass

    parser = ArgumentParser(description="Fake scores on an ibProArcade-for-vBulletin instance.")
    parser.add_argument("-u", "--username", required=True, help="the username with which to log in")
    parser.add_argument("-b", "--base-url", required=True, help="the base URL of the forum")
    parser.add_argument("-s", "--score", type=int, required=True, help="the score to fake")
    parser.add_argument("-t", "--time", metavar="SECONDS", type=int, required=True,
                        help='the time how long the game should be "played"')
    parser.add_argument("-g", "--game-id", type=int, required=True,
                        help="the numeric ID of the arcade game")

    args = parser.parse_args()

    input_password = getpass()

    fake(args.base_url, args.username, input_password, args.game_id, args.time, args.score)