from vbcbbot.html_decompiler import HtmlDecompiler

import bs4
import http.cookiejar as cj
import io
import logging
import re
import threading
import time
import unicodedata
import urllib.error as ue
import urllib.parse as up
import urllib.request as ur

__author__ = 'ondra'

logger = logging.getLogger("vbcbbot.chatbox_connector")
url_safe_characters = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789-_.")
timestamp_pattern = re.compile("[[]([0-9][0-9]-[0-9][0-9]-[0-9][0-9], [0-9][0-9]:[0-9][0-9])[]]")


def fish_out_id(element, url_piece):
    """
    Fishes out an ID following the URL piece from a link containing a given URL piece.
    :param element: The element at which to root the search for the ID.
    :param url_piece: The URL piece to search for; it is succeeded directly by the ID.
    :return: The ID fished out of the message.
    """
    for link_element in element.find_all("a", href=True):
        href = link_element["href"]
        piece_index = href.find(url_piece)
        if piece_index >= 0:
            return int(href[(piece_index + len(url_piece)):])
    return None


def filter_combining_mark_clusters(string, maximum_marks=4):
    """
    Reduces the number of combining marks on a single character to a specific value.
    :param string: The string to filter.
    :param maximum_marks: Maximum number of combining marks on a character.
    :return: The filtered string.
    """
    ret = ""
    mark_count = 0
    for c in string:
        if unicodedata.category(c) == 'Mn':
            # non-spacing mark
            mark_count += 1
            if mark_count <= maximum_marks:
                ret += c
        elif unicodedata.category(c) == 'Cf':
            # these characters don't have a width
            # add them, but don't reset the mark counter
            ret += c
        else:
            mark_count = 0
            ret += c
    return ret


class TransferError(Exception):
    """An error when sending a message to or receiving a message from the chatbox."""
    pass


class ChatboxMessage:
    """A message posted into the chatbox."""
    def __init__(self, message_id, user_id, user_name, body, timestamp=None, html_decompiler=None):
        """
        Initialize a new message.
        :param message_id: The ID of the message.
        :param user_id: The ID of the user who posted this message.
        :param user_name: The name of the user who posted this message.
        :param body: The body of the message (a HTML string).
        :param timestamp: The time at which the message was posted.
        :return: The new message.
        """
        self.id = message_id
        self.user_id = user_id
        self.user_name = user_name
        self.body = body
        if timestamp is None:
            timestamp = time.time()
        self.timestamp = timestamp
        if html_decompiler is None:
            self.html_decompiler = HtmlDecompiler()
        else:
            self.html_decompiler = html_decompiler

    def body_io(self):
        """
        Return a new string I/O object for the body of the message.
        :return: A new string I/O object for the body of the message.
        """
        return io.StringIO(self.body)

    def body_soup(self):
        """
        Return a new BeautifulSoup instance for the body of the message.
        :return: A new BeautifulSoup instance for the body of the message.
        """
        return bs4.BeautifulSoup(self.body_io(), "html.parser")

    def decompiled_body(self):
        """
        Return the body of the message decompiled using HtmlDecompiler.
        :return: The body of the message decompiled using HtmlDecompiler.
        """
        return "".join([str(e) for e in self.html_decompiler.decompile_soup(self.body_soup())])


class ChatboxConnector:
    """Facilitates communication with a vBulletin chatbox."""

    def __init__(self, base_url, username, password, stfu_command=None, stfu_delay=30,
                 html_decompiler=None):
        """
        Connect to a vBulletin chatbox.
        :param base_url: The base URL of the chatbox, down to the subdirectory containing vBulletin.
        :param username: The forum username with which to log in.
        :param password: The forum password with which to log in.
        :param stfu_command: The command to silence outgoing communication.
        :param stfu_delay: How long to shut up for, in minutes.
        :param html_decompiler: A correctly configured HTML decompiler, or None.
        :return: A new chatbox connector.
        """
        self.base_url = base_url
        self.username = username
        self.password = password
        self.stfu_command = stfu_command
        self.stfu_delay = stfu_delay
        self.html_decompiler = html_decompiler

        # assume a good default for these
        self.server_encoding = "iso-8859-1"
        self.time_between_reads = 5
        self.message_id_piece = "misc.php?ccbloc="
        self.user_id_piece = "member.php?u="

        # precompute the relevant URLs
        self.login_url = up.urljoin(self.base_url, "login.php?do=login")
        self.cheap_page_url = up.urljoin(self.base_url, "faq.php")
        self.post_edit_url = up.urljoin(self.base_url, "misc.php")
        self.messages_url = up.urljoin(self.base_url, "misc.php?show=ccbmessages")
        self.ajax_url = up.urljoin(self.base_url, "ajax.php")

        # prepare the cookie jar, its lock, and the URL opener
        self.cookie_jar = cj.CookieJar()
        self.cookie_jar_lid = threading.Lock()
        self.url_opener = ur.build_opener(ur.HTTPCookieProcessor(self.cookie_jar))
        self.reading_thread = threading.Thread(None, self.perform_reading,
                                               name="ChatboxConnector reading")

        # "declare" these variables for later
        self.new_message_subscribers = set()
        self.new_message_from_salvo_subscribers = set()
        self.message_modified_subscribers = set()
        self.old_message_ids_to_bodies = {}
        self.initial_salvo = True
        self.security_token = None
        self.last_message_received = -1
        self.stop_reading = False
        self.stfu_start = None
        """:type: int|None"""

    def start(self):
        self.login()
        self.reading_thread.start()

    def login(self):
        """
        Login to the vBulletin chatbox using the credentials contained in this object.
        """
        logger.info("logging in as {0}".format(repr(self.username)))
        post_values = {
            "vb_login_username": self.username,
            "vb_login_password": self.password,
            "cookieuser": "1",
            "s": "",
            "do": "login",
            "vb_login_md5password": "",
            "vb_login_md5password_utf": ""
        }
        post_data = up.urlencode(post_values, encoding="utf-8").encode("us-ascii")

        with self.cookie_jar_lid:
            # empty the cookie jar
            self.cookie_jar.clear()

            # log in
            login_response = self.url_opener.open(self.login_url, data=post_data)
            login_response.read()

        # fetch the security token too
        self.fetch_security_token()

    def fetch_security_token(self):
        """
        Fetch and update the security token required for most operations from the forum.
        """
        logger.info("fetching new security token")
        # fetch a (computationally cheap) page from the server
        with self.cookie_jar_lid:
            cheap_response = self.url_opener.open(self.cheap_page_url)
            cheap_page_data = cheap_response.read()
            cheap_page_string = cheap_page_data.decode(self.server_encoding)

        # load it into Beautiful Soup
        soup = bs4.BeautifulSoup(io.StringIO(cheap_page_string))
        token_field = soup.find("input", attrs={"name": "securitytoken"})
        self.security_token = token_field["value"]
        logger.debug("new security token: {0}".format(repr(self.security_token)))

    def encode_outgoing_message(self, outgoing_message):
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
                    for b in c.encode(self.server_encoding):
                        ret += "%{0:02X}".format(b)
                except UnicodeEncodeError:
                    # unsupported natively by the encoding; perform a URL-encoded HTML escape
                    ret += "%26%23{0}%3B".format(ord(c))
        return ret

    def retry(self, retry_count, func, *pos_args, **kw_args):
        """
        Renew some information and try calling the function again.
        :param retry_count: How many times have we retried already?
        :param func: The function to call once the information has been renewed.
        :param pos_args: Positional arguments to pass to func.
        :param kw_args: Keyword arguments to pass to func. The function will also pass "retry=n"
        where n equals retry_count increased by 1.
        :return:
        """
        if pos_args is None:
            pos_args = []
        if kw_args is None:
            kw_args = {}

        if retry_count == 0:
            # renew the token
            self.fetch_security_token()
        elif retry_count == 1:
            # login anew
            self.login()
        else:
            raise TransferError()

        func(*pos_args, retry=retry_count+1, **kw_args)

    def should_stfu(self):
        if self.stfu_start is None:
            return False
        if time.time() < self.stfu_start + 60*self.stfu_delay:
            return True
        return False

    def ajax(self, operation, parameters=None):
        """
        Perform an AJAX request.
        :param operation: The name of the operation to perform.
        :type operation: str
        :param parameters: The parameters to supply.
        :type parameters: dict[str, str]
        :return: The result soup.
        :rtype: bs4.BeautifulSoup
        """
        post_values = {
            "securitytoken": self.security_token,
            "do": operation,
        }
        if parameters is not None:
            post_values.update(parameters)
        post_data = up.urlencode(post_values, encoding="utf-8").encode("us-ascii")

        with self.cookie_jar_lid:
            response = self.url_opener.open(self.ajax_url, data=post_data)
            ajax_bytes = response.read()

        return bs4.BeautifulSoup(ajax_bytes, "xml")

    def send_message(self, message, bypass_stfu=False, bypass_filters=False, retry=0):
        """
        Send the given message to the server.
        :param message: The message to send.
        :param retry: Level of desperation to post the new message.
        """
        if not bypass_stfu and self.should_stfu():
            logger.debug("I've been shut up; not posting message {0}".format(repr(message)))
            return

        if not bypass_filters:
            message = filter_combining_mark_clusters(message)

        logger.debug("posting message {0} (retry {1})".format(repr(message), retry))
        request_string = "do=cb_postnew&securitytoken={0}&vsacb_newmessage={1}".format(
            self.security_token, self.encode_outgoing_message(message)
        )
        request_bytes = request_string.encode(self.server_encoding)

        # send!
        with self.cookie_jar_lid:
            try:
                post_response = self.url_opener.open(self.post_edit_url, data=request_bytes)
            except ue.URLError:
                logger.exception("sending message")
                # don't send the message -- fixing this might take longer
                return
            post_response_body = post_response.read()

        if post_response.status != 200 or len(post_response_body) != 0:
            # something failed
            self.retry(retry, self.send_message, message, bypass_stfu, bypass_filters)

    def edit_message(self, message_id, new_body):
        """
        Edits a previously posted chatbox message.
        :param message_id: The ID of the message to modify.
        :return: The new body of the message.
        """
        logger.debug("editing message {0} to {1}".format(message_id, repr(new_body)))
        request_string = \
            "do=vsacb_editmessage&s=&securitytoken={0}&id={1}&vsacb_editmessage={2}".format(
                self.security_token, message_id, self.encode_outgoing_message(new_body)
            )
        request_bytes = request_string.encode(self.server_encoding)

        # send!
        with self.cookie_jar_lid:
            edit_response = self.url_opener.open(self.post_edit_url, data=request_bytes)
            edit_response.read()

    def fetch_new_messages(self, retry=0):
        """
        Fetches new messages from the chatbox.
        :param retry: Level of desperation fetching the new messages.
        """
        try:
            messages_response = self.url_opener.open(self.messages_url)
        except ue.URLError:
            logger.exception("fetching new messages failed")
            # try again next time
            return
        messages_string = messages_response.read().decode(self.server_encoding)
        messages_soup = bs4.BeautifulSoup(io.StringIO(messages_string), "html.parser")

        all_trs = messages_soup.find_all("tr", recursive=False)
        if len(all_trs) == 0:
            # aw crap
            self.retry(retry, self.fetch_new_messages)

        new_last_message = self.last_message_received
        visible_message_ids = set()
        new_and_edited_messages = []

        # for each message
        for tr in all_trs:
            # pick out the TDs
            tds = tr.find_all("td")

            # pick out the first (metadata)
            meta_td = tds[0]

            # find the link to the message and to the user
            message_id = fish_out_id(meta_td, self.message_id_piece)
            user_id = fish_out_id(meta_td, self.user_id_piece)

            if message_id is None:
                # bah, humbug
                continue

            #if (self.last_message_received >= message_id
            #        and self.last_message_received - message_id < 3000):
            #    # seen this already
            #    continue

            if new_last_message < message_id:
                new_last_message = message_id

            visible_message_ids.add(message_id)

            # fetch the timestamp
            timestamp = time.time()
            timestamp_match = timestamp_pattern.search(meta_td.decode_contents())
            if timestamp_match is not None:
                time_string = timestamp_match.group(1)
                try:
                    timestamp = time.mktime(time.strptime(time_string, "%d-%m-%y, %H:%M"))
                except ValueError:
                    # meh
                    pass

            # get the nickname
            nick = None
            for link_element in meta_td.find_all("a", href=True):
                if self.user_id_piece in link_element["href"]:
                    nick = link_element.text

            if nick is None:
                # bah, humbug
                continue

            message_body = tds[1].decode_contents().strip()
            message = ChatboxMessage(message_id, user_id, nick, message_body, timestamp,
                                     self.html_decompiler)

            if message_id in self.old_message_ids_to_bodies:
                old_body = self.old_message_ids_to_bodies[message_id]
                if old_body != message_body:
                    self.old_message_ids_to_bodies[message_id] = message_body
                    new_and_edited_messages.insert(0, (True, message))
            else:
                self.old_message_ids_to_bodies[message_id] = message_body
                new_and_edited_messages.insert(0, (False, message))

                if not self.initial_salvo and self.stfu_command is not None and \
                        message.user_name != self.username and message_body == self.stfu_command:
                    # STFU
                    logger.info("{0} shut me up for {1} minutes".format(nick, self.stfu_delay))
                    self.stfu_start = time.time()

        # cull the bodies of messages that aren't visible anymore
        for message_id in list(self.old_message_ids_to_bodies.keys()):
            if message_id not in visible_message_ids:
                del self.old_message_ids_to_bodies[message_id]

        # distribute the news and modifications
        for (is_edited, new_message) in new_and_edited_messages:
            if self.initial_salvo:
                self.distribute_new_message_from_salvo(new_message)
            elif is_edited:
                self.distribute_modified_message(new_message)
            else:
                self.distribute_new_message(new_message)

        self.initial_salvo = False
        self.last_message_received = new_last_message

    def distribute_new_message(self, new_message):
        """Distributes a new message to the subscribers."""
        for subscriber in self.new_message_subscribers:
            try:
                subscriber(new_message)
            except:
                logger.exception("distribute_new_message: subscriber")

    def distribute_new_message_from_salvo(self, new_message):
        """Distributes a new message to the subscribers."""
        for subscriber in self.new_message_from_salvo_subscribers:
            try:
                subscriber(new_message)
            except:
                logger.exception("distribute_new_message_from_salvo: subscriber")

    def distribute_modified_message(self, modified_message):
        """Distributes a modified message to the subscribers."""
        for subscriber in self.message_modified_subscribers:
            try:
                subscriber(modified_message)
            except:
                logger.exception("distribute_modified_message: subscriber")

    def subscribe_to_new_messages(self, new_subscriber):
        """
        Add a new subscriber to be notified when a new message is received.
        :param new_subscriber: A callable object with one positional argument that will receive the
        new message (a ChatboxMessage instance).
        """
        self.new_message_subscribers.add(new_subscriber)

    def subscribe_to_modified_messages(self, new_subscriber):
        """
        Add a new subscriber to be notified when a visible message is modified.
        :param new_subscriber: A callable object with one positional argument that will receive the
        updated message (a ChatboxMessage instance).
        """
        self.message_modified_subscribers.add(new_subscriber)

    def subscribe_to_new_messages_from_salvo(self, new_subscriber):
        """
        Add a new subscriber to be notified when a new message from the initial salvo is received.
        :param new_subscriber: A callable object with one positional argument that will receive the
        new message (a ChatboxMessage instance).
        """
        self.new_message_from_salvo_subscribers.add(new_subscriber)

    def perform_reading(self):
        """
        Processes incoming messages.
        """
        try:
            while not self.stop_reading:
                self.fetch_new_messages()
                time.sleep(self.time_between_reads)
        except:
            logger.exception("perform reading")
            raise

if __name__ == '__main__':
    def message_received(message):
        print("[{t}] <{n}> {m}".format(t=message.timestamp, n=message.user_name, m=message.body))

    def message_modified(message):
        print("[{t}] * <{n}> {m}".format(t=message.timestamp, n=message.user_name, m=message.body))

    #import getpass
    #my_password = getpass.getpass()
    my_password = "ThisIsNotMyRealPassword;-)"

    conn = ChatboxConnector("http://forum.example.com/", "User Name", my_password)
    conn.subscribe_to_new_messages(message_received)
    conn.subscribe_to_modified_messages(message_modified)
    conn.start()
