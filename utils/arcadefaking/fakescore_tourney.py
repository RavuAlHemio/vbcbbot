#!/usr/bin/env python3
from lxml.etree import HTML
from time import sleep
from urllib.parse import urlencode, urljoin
import _utils


def fake(base_url, username, password, game_id, time, score, tourney_id, game_name=None, rung=None,
         face_off=None):
    url_opener = _utils.login_and_enter_arcade(base_url, username, password)

    # calculate some more URLs
    tourneys_url = urljoin(base_url, "arcade.php?&do=viewtournaments")
    view_tourney_url = urljoin(base_url, "arcade.php?&act=Arcade&do=viewtourney&tid={0}".format(
        tourney_id
    ))
    play_tourney_game_url = urljoin(
        base_url,
        "arcade.php?&do=playtourney&gameid={0}&tid={1}{2}{3}".format(
            game_id, tourney_id,
            "&rung={0}".format(rung) if rung is not None else "",
            "&faceoff={0}".format(face_off) if face_off is not None else ""
        )
    )
    score_url = urljoin(base_url, "index.php?act=Arcade&do=newscore")

    # go to tourneys
    print("entering tourneys page")
    tourneys_response = url_opener.open(tourneys_url)
    tourneys_response.read()

    # view the tourney
    print("looking at the tourney")
    view_tourney_response = url_opener.open(view_tourney_url)
    view_tourney_response.read()

    # pretend to play the game
    print("playing the game")
    play_tourney_game_response = url_opener.open(play_tourney_game_url)
    play_tourney_game = HTML(play_tourney_game_response.read())

    if game_name is None:
        # (meanwhile, find the game's name)
        game_flash = play_tourney_game.find(".//embed[@type='application/x-shockwave-flash']")
        if game_flash is None:
            print("didn't find the flash plugin on the game page :'-(")
            return

        flash_vars = game_flash.attrib['flashvars'].split("&")
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
    post_data = _utils.encode_post_data(post_values)
    print("submitting fake score")
    score_response = url_opener.open(score_url, data=post_data)
    score_response.read()

    print("done")

if __name__ == '__main__':
    from argparse import ArgumentParser
    from getpass import getpass

    parser = ArgumentParser(
        description="Fake scores in a tourney on an ibProArcade-for-vBulletin instance."
    )
    _utils.add_common_arguments_to_parser(parser)
    parser.add_argument("-s", "--score", type=int, required=True, help="the score to fake")
    parser.add_argument("-t", "--time", metavar="SECONDS", type=int, required=True,
                        help='the time how long the game should be "played"')
    parser.add_argument("-g", "--game-id", type=int, required=True,
                        help="the numeric ID of the arcade game")
    parser.add_argument("-n", "--game-name", default=None,
                        help="the internal name of the arcade game")
    parser.add_argument("-T", "--tourney-id", type=int, required=True,
                        help="the numeric ID of the tourney")
    parser.add_argument("-r", "--rung", type=int, default=None, help="the rung (3 = quarterfinal" +
                        ", 2 = semifinal, 1 = final)")
    parser.add_argument("-f", "--face-off", type=int, default=None, help="the face-off number " +
                        "(horizontal block in the tree diagram, leftmost = 1)")

    args = parser.parse_args()

    input_password = getpass()

    fake(args.base_url, args.username, input_password, args.game_id, args.time, args.score,
         args.tourney_id, args.game_name, args.rung, args.face_off)
