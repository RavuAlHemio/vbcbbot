#!/usr/bin/env python3
from urllib.parse import urlencode, urljoin
import _utils


def fake(base_url, username, password, game_id, player_count, attempt_count):
    url_opener = _utils.login_and_enter_arcade(base_url, username, password)

    # calculate some more URLs
    tourneys_url = urljoin(base_url, "arcade.php?&do=viewtournaments")
    create_tourney_url = urljoin(base_url, "arcade.php?&act=Arcade&do=createtourney")
    submit_tourney_url = urljoin(base_url, "arcade.php")

    # go to tourneys
    print("entering tourneys page")
    tourneys_response = url_opener.open(tourneys_url)
    tourneys_response.read()

    # go to tourney creation form
    print("opening tourney creation page")
    create_tourney_response = url_opener.open(create_tourney_url)
    create_tourney_response.read()

    # fill it out and submit it
    post_values = {
        "act": "Arcade",
        "do": "docreatetourney",
        "the_game": game_id,
        "nbjoueurs": player_count,
        "nbtries": attempt_count,
    }
    post_data = _utils.encode_post_data(post_values)
    print("creating tourney")
    submit_tourney_response = url_opener.open(submit_tourney_url, data=post_data)
    submit_tourney_response.read()

    print("done")

if __name__ == '__main__':
    from argparse import ArgumentParser
    from getpass import getpass

    parser = ArgumentParser(
        description="Start a possibly-bogus tourney on an ibProArcade-for-vBulletin instance."
    )
    _utils.add_common_arguments_to_parser(parser)
    parser.add_argument("-p", "--players", type=int, required=True, help="number of players")
    parser.add_argument("-a", "--attempts", type=int, required=True,
                        help='number of attempts per round')
    parser.add_argument("-g", "--game-id", type=int, required=True,
                        help="the numeric ID of the arcade game")

    args = parser.parse_args()

    input_password = getpass()

    fake(args.base_url, args.username, input_password, args.game_id, args.players, args.attempts)
