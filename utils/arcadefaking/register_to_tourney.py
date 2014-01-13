#!/usr/bin/env python3
from urllib.parse import urlencode, urljoin
import _utils


def fake(base_url, username, password, tourney_id):
    url_opener = _utils.login_and_enter_arcade(base_url, username, password)

    # calculate some more URLs
    tourneys_url = urljoin(base_url, "arcade.php?&do=viewtournaments")
    join_tourney_url = urljoin(base_url, "arcade.php?&do=registertourney&tid={0}".format(
        tourney_id
    ))
    #view_tourney_url = urljoin(base_url, "arcade.php?&do=viewtourney&tid={0}".format(
    #    tourney_id
    #))

    # go to tourneys
    print("entering tourneys page")
    tourneys_response = url_opener.open(tourneys_url)
    tourneys_response.read()

    # go to tourney creation form
    print("joining tourney")
    join_tourney_response = url_opener.open(join_tourney_url)
    join_tourney_response.read()

    # look at tourney to make sure it sticks
    #print("looking at tourney")
    #view_tourney_response = url_opener.open(view_tourney_url)
    #view_tourney_response.read()

    print("done")

if __name__ == '__main__':
    from argparse import ArgumentParser
    from getpass import getpass

    parser = ArgumentParser(
        description="Register to a running tourney on an ibProArcade-for-vBulletin instance."
    )
    _utils.add_common_arguments_to_parser(parser)
    parser.add_argument("-t", "--tourney-id", type=int, required=True, help="tourney ID")

    args = parser.parse_args()

    input_password = getpass()

    fake(args.base_url, args.username, input_password, args.tourney_id)
