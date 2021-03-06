from vbcbbot.html_decompiler import HtmlDecompiler

from datetime import datetime
from dateutil.tz import tzlocal
import http.client as hcl
import http.cookiejar as cj
import io
from itertools import islice
import logging
from lxml import etree
from lxml.cssselect import CSSSelector
import re
import socket
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
xml_char_escape_pattern = re.compile("[&][#]([0-9]+|x[0-9a-fA-F]+)[;]")
dst_setting_pattern = re.compile("var tzOffset = ([0-9]+) [+] ([0-9]+)[;]")


def fish_out_id(element, url_piece):
    """
    Fishes out an ID following the URL piece from a link containing a given URL piece.
    :param element: The element at which to root the search for the ID.
    :param url_piece: The URL piece to search for; it is succeeded directly by the ID.
    :return: The ID fished out of the message.
    """
    for link_element in element.iterfind(".//a[@href]"):
        href = link_element.attrib["href"]
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


def sub_invalid_xml_escape(match):
    """
    Substitutes invalid XML escapes with nothing.
    :param match: The regular expression match object.
    :return: The string to replace the match with.
    :rtype: str
    """
    number = match.group(1)
    if number is None:
        return match.group(0)
    elif number[0] == "x":
        # hex escape
        c = int(number[1:], 16)
    else:
        # decimal escape
        c = int(number, 10)

    if c == 0:
        return ""
    elif c >= 0xD800 and c <= 0xDFFF:
        return ""
    else:
        return match.group(0)


def filter_invalid_xml(string):
    """
    Removes characters and XML character escapes that are forbidden by the XML
    standard.
    :param string: The string to filter.
    :type string: str
    :return: The filtered string.
    :rtype: str
    """
    # (NUL and surrogates are invalid)
    # filter verbatim characters first
    verbesc = []
    for c in string:
        if ord(c) == 0:
            pass
        elif ord(c) >= 0xD800 and ord(c) <= 0xDFFF:
            pass
        else:
            verbesc.append(c)

    # filter escapes
    ret = xml_char_escape_pattern.sub(sub_invalid_xml_escape, "".join(verbesc))

    return ret


def ajax_url_encode_string(string):
    """
    Encode the string in the escape method used by vB AJAX.
    :param string: The string to send.
    :return: The string escaped correctly for vB AJAX.
    """
    ret = ""
    for c in string:
        if c in url_safe_characters:
            ret += c
        elif ord(c) <= 0x7f:
            ret += "%{0:02x}".format(ord(c))
        else:
            # escape it as UTF-16 with %u
            utf16_bytes = c.encode("utf-16be")
            for (top_byte, bottom_byte) in zip(islice(utf16_bytes, 0, None, 2), islice(utf16_bytes, 1, None, 2)):
                ret += "%u{0:02X}{1:02X}".format(top_byte, bottom_byte)
    return ret


def children_to_string(lxml_tree):
    """
    Encode the element and text children of an lxml element into a string.
    :param lxml_tree: The tree.
    :return: The string.
    :rtype: str
    """
    ret = []
    for child in lxml_tree.xpath("./node()"):
        if hasattr(child, "iterchildren"):
            ret.append(etree.tostring(child, encoding="unicode", with_tail=False))
        else:
            new_child = ""
            for c in child:
                if c == "&":
                    new_child += "&amp;"
                elif c == '"':
                    new_child += "&quot;"
                elif c == "'":
                    new_child += "&apos;"
                elif c == "<":
                    new_child += "&lt;"
                elif c == ">":
                    new_child += "&gt;"
                elif ord(c) > 0x7E:
                    new_child += "&#{0};".format(ord(c))
                else:
                    new_child += c
            ret.append(new_child)
    return "".join(ret)


class TransferError(Exception):
    """An error when sending a message to or receiving a message from the chatbox."""
    pass


class ChatboxMessage:
    """A message posted into the chatbox."""
    def __init__(self, message_id, user_id, user_name_body, body, timestamp=None,
                 html_decompiler=None):
        """
        Initialize a new message.
        :param message_id: The ID of the message.
        :param user_id: The ID of the user who posted this message.
        :param user_name_body: The name of the user who posted this message, with tags.
        :param body: The body of the message (a HTML string).
        :param timestamp: The time at which the message was posted.
        :return: The new message.
        """
        self.id = message_id
        self.user_id = user_id
        self.user_name_body = user_name_body
        self.body = body
        if timestamp is None:
            timestamp = time.time()
        self.timestamp = timestamp
        if html_decompiler is None:
            self.html_decompiler = HtmlDecompiler()
        else:
            self.html_decompiler = html_decompiler

    def user_name_io(self):
        """
        Return a new string I/O object for the username.
        :return: A new string I/O object for the username.
        :rtype: io.StringIO
        """
        return io.StringIO(self.user_name_body)

    def user_name_lxml(self):
        """
        Return a new lxml HTML instance for the username.
        :return: A new lxml HTML instance for the username.
        :rtype: lxml.etree.HTML
        """
        return etree.HTML(self.user_name_body)

    @property
    def user_name(self):
        """
        The name of the user who posted this message.
        :rtype: str
        """
        return "".join(self.user_name_lxml().itertext())

    def decompiled_user_name_dom(self):
        """
        Return the Document Oblect Model of the username decompiled using HtmlDecompiler.
        :return: The DOM of the username decompiled using HtmlDecompiler.
        :rtype: list[vbcbbot.html_decompiler.Node]
        """
        return self.html_decompiler.decompile_lxml(self.user_name_lxml())

    def decompiled_user_name(self):
        """
        Return the username decompiled using HtmlDecompiler.
        :return: The username decompiled using HtmlDecompiler.
        :rtype: str
        """
        return "".join(str(e) for e in self.decompiled_user_name_dom())

    def body_io(self):
        """
        Return a new string I/O object for the body of the message.
        :return: A new string I/O object for the body of the message.
        :rtype: io.StringIO
        """
        return io.StringIO(self.body)

    def body_lxml(self):
        """
        Return a new lxml HTML instance for the body of the message.
        :return: A new lxml HTML instance for the body of the message, or None if the body is
        empty.
        :rtype: lxml.etree.HTML|None
        """
        if len(self.body) == 0:
            return None
        return etree.HTML(self.body)

    def decompiled_body_dom(self):
        """
        Return the Document Object Model of the message body decompiled using HtmlDecompiler.
        :return: The DOM of the message body decompiled using HtmlDecompiler.
        :rtype: list[vbcbbot.html_decompiler.Node]
        """
        return self.html_decompiler.decompile_lxml(self.body_lxml())

    def decompiled_body(self):
        """
        Return the body of the message decompiled using HtmlDecompiler.
        :return: The body of the message decompiled using HtmlDecompiler.
        :rtype: str
        """
        return "".join(str(e) for e in self.decompiled_body_dom())


class ChatboxConnector:
    """Facilitates communication with a vBulletin chatbox."""

    def __init__(self, base_url, username, password, html_decompiler=None, timeout=30):
        """
        Connect to a vBulletin chatbox.
        :param base_url: The base URL of the chatbox, down to the subdirectory containing vBulletin.
        :param username: The forum username with which to log in.
        :param password: The forum password with which to log in.
        :param html_decompiler: A correctly configured HTML decompiler, or None.
        :return: A new chatbox connector.
        """
        self.base_url = base_url
        self.username = username
        self.password = password
        self.html_decompiler = html_decompiler
        self.timeout = timeout

        # assume a good default for these
        self.server_encoding = "windows-1252"
        self.time_between_reads = 5
        self.dst_update_minute = 3
        self.message_id_piece = "misc.php?ccbloc="
        self.user_id_piece = "member.php?u="

        # precompute the relevant URLs
        self.login_url = up.urljoin(self.base_url, "login.php?do=login")
        self.cheap_page_url = up.urljoin(self.base_url, "faq.php")
        self.post_edit_url = up.urljoin(self.base_url, "misc.php")
        self.messages_url = up.urljoin(self.base_url, "misc.php?show=ccbmessages")
        self.smilies_url = up.urljoin(self.base_url, "misc.php?do=showsmilies")
        self.ajax_url = up.urljoin(self.base_url, "ajax.php")
        self.dst_url = up.urljoin(self.base_url, "profile.php?do=dst")

        # prepare the cookie jar, its lock, and the URL opener
        self.cookie_jar = cj.CookieJar()
        self.cookie_jar_lid = threading.RLock()
        self.url_opener = ur.build_opener(ur.HTTPCookieProcessor(self.cookie_jar))
        self.reading_thread = threading.Thread(None, self.perform_reading,
                                               name="ChatboxConnector reading")

        # "declare" these variables for later
        self.banned_nicknames = set()
        self.subscribers = set()
        self.old_message_ids_to_bodies = {}
        self.lowercase_usernames_to_user_id_name_pairs = {}
        self.forum_smiley_codes_to_urls = {}
        self.forum_smiley_urls_to_codes = {}
        self.custom_smiley_codes_to_urls = {}
        self.custom_smiley_urls_to_codes = {}
        self.initial_salvo = True
        self.security_token = None
        self.last_message_received = -1
        self.stop_reading = False
        self.stfu_deadline = None
        """:type: int|None"""
        self.last_dst_update_hour_utc = -1

    @property
    def smiley_codes_to_urls(self):
        ret = {}
        ret.update(self.forum_smiley_codes_to_urls)
        ret.update(self.custom_smiley_codes_to_urls)
        return ret

    @property
    def smiley_urls_to_codes(self):
        ret = {}
        ret.update(self.forum_smiley_urls_to_codes)
        ret.update(self.custom_smiley_urls_to_codes)
        return ret

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
            login_response = self.url_opener.open(self.login_url, data=post_data,
                                                  timeout=self.timeout)
            login_response.read()

        # fetch the security token too
        self.fetch_security_token()

        # update smilies
        self.update_smilies()

        logger.info("ready")

    def fetch_security_token(self):
        """
        Fetch and update the security token required for most operations from the forum.
        """
        logger.info("fetching new security token")
        # fetch a (computationally cheap) page from the server
        with self.cookie_jar_lid:
            cheap_response = self.url_opener.open(self.cheap_page_url, timeout=self.timeout)
            cheap_page_data = cheap_response.read()
            cheap_page_string = cheap_page_data.decode(self.server_encoding)

        # load it into lxml
        cheap_page = etree.HTML(cheap_page_string)
        token_field = cheap_page.find(".//input[@name='securitytoken']")
        self.security_token = token_field.attrib["value"]
        logger.debug("new security token: {0}".format(repr(self.security_token)))

    def update_smilies(self):
        """
        Fetches an up-to-date list of available smilies.
        """
        logger.info("updating smilies")
        with self.cookie_jar_lid:
            smileys_response = self.url_opener.open(self.smilies_url, timeout=self.timeout)
            smileys_page_data = smileys_response.read()
            smileys_page_string = smileys_page_data.decode(self.server_encoding)

        # lxml!
        smileys = etree.HTML(smileys_page_string)

        sel_smilie_bit = CSSSelector("li.smiliebit")
        sel_smilie_text = CSSSelector("div.smilietext")
        sel_smilie_image = CSSSelector("div.smilieimage img")

        code_to_url = {}
        url_to_code = {}

        for smilie_bit in sel_smilie_bit(smileys):
            code = "".join(sel_smilie_text(smilie_bit)[0].itertext())
            image = sel_smilie_image(smilie_bit)[0]
            url = image.attrib["src"]

            code_to_url[code] = url
            url_to_code[url] = code

        if len(code_to_url) > 0 and len(url_to_code) > 0:
            self.forum_smiley_codes_to_urls = code_to_url
            self.forum_smiley_urls_to_codes = url_to_code

            # update this one too (to the combination)
            self.html_decompiler.smiley_url_to_symbol = self.smiley_urls_to_codes

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

    def escape_outgoing_text(self, text):
        """
        Escape questionable content (BBCode and smilies) from the given outgoing message.
        :param text: The text to escape.
        :return: The escaped text
        """
        ret = text.replace("[", "[noparse][[/noparse]")

        smilies_by_length = sorted(self.forum_smiley_codes_to_urls.keys(), key=lambda k: (-len(k), k))
        for smiley in smilies_by_length:
            ret = ret.replace(smiley, "[noparse]{0}[/noparse]".format(smiley))

        return ret

    def retry(self, retry_count, func, *pos_args, **kw_args):
        """
        Renew some information and try calling the function again.
        :param retry_count: How many times have we retried already?
        :param func: The function to call once the information has been renewed.
        :param pos_args: Positional arguments to pass to func.
        :param kw_args: Keyword arguments to pass to func. The function will also pass "retry=n"
        where n equals retry_count increased by 1.
        :return: Whatever func returns.
        """
        if pos_args is None:
            pos_args = []
        if kw_args is None:
            kw_args = {}

        if retry_count == 0:
            # renew the token
            try:
                self.fetch_security_token()
            except:
                pass
        elif retry_count == 1:
            # login anew
            try:
                self.login()
            except:
                    pass
        else:
            raise TransferError()

        return func(*pos_args, retry=retry_count+1, **kw_args)

    def should_stfu(self):
        if self.stfu_deadline is None:
            return False
        if time.time() < self.stfu_deadline:
            return True
        return False

    def ajax(self, operation, parameters=None, retry=0):
        """
        Perform an AJAX request.
        :param operation: The name of the operation to perform.
        :type operation: str
        :param parameters: The parameters to supply.
        :type parameters: dict[str, str]
        :return: The result XML DOM.
        :rtype: lxml.etree.XML
        """
        post_values = {
            "securitytoken": self.security_token,
            "do": operation,
        }
        if parameters is not None:
            post_values.update(parameters)

        post_pieces = []
        for (key, value) in post_values.items():
            encoded_key = ajax_url_encode_string(key)
            encoded_value = ajax_url_encode_string(value)
            post_pieces.append("{0}={1}".format(encoded_key, encoded_value))
        post_string = "&".join(post_pieces)
        post_data = post_string.encode("us-ascii")

        with self.cookie_jar_lid:
            response = self.url_opener.open(self.ajax_url, data=post_data, timeout=self.timeout)
            ajax_bytes = response.read()

        if response.status != 200 or len(ajax_bytes) == 0:
            # something failed
            return self.retry(retry, self.ajax, operation, parameters)

        try:
            return etree.XML(ajax_bytes)
        except:
            logger.exception("AJAX response parse")
            return self.retry(retry, self.ajax, operation, parameters)

    def send_message(self, message, bypass_stfu=False, bypass_filters=False, custom_smileys=False, retry=0):
        """
        Send the given message to the server.
        :param message: The message to send.
        :param retry: Level of desperation to post the new message.
        """
        if not bypass_stfu and self.should_stfu():
            logger.debug("I've been shut up; not posting message {0}".format(repr(message)))
            return

        if custom_smileys:
            message = self.substitute_custom_smileys(message)

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
                post_response = self.url_opener.open(self.post_edit_url, data=request_bytes,
                                                     timeout=self.timeout)
            except (ue.URLError, hcl.HTTPException, socket.timeout, ConnectionError):
                logger.exception("sending message")
                # don't send the message -- fixing this might take longer
                return
            post_response_body = post_response.read()

        if post_response.status != 200 or len(post_response_body) != 0:
            # something failed
            self.retry(retry, self.send_message, message, bypass_stfu, bypass_filters, custom_smileys)
            return

    def edit_message(self, message_id, new_body, bypass_stfu=True, bypass_filters=False, custom_smileys=False):
        """
        Edits a previously posted chatbox message.
        :param message_id: The ID of the message to modify.
        :return: The new body of the message.
        """
        if not bypass_stfu and self.should_stfu():
            logger.debug("I've been shut up; not editing message {0} to {1}".format(repr(message_id, new_body)))
            return

        if custom_smileys:
            new_body = self.substitute_custom_smileys(new_body)

        if not bypass_filters:
            new_body = filter_combining_mark_clusters(new_body)

        logger.debug("editing message {0} to {1}".format(message_id, repr(new_body)))
        request_string = \
            "do=vsacb_editmessage&s=&securitytoken={0}&id={1}&vsacb_editmessage={2}".format(
                self.security_token, message_id, self.encode_outgoing_message(new_body)
            )
        request_bytes = request_string.encode(self.server_encoding)

        # send!
        with self.cookie_jar_lid:
            edit_response = self.url_opener.open(self.post_edit_url, data=request_bytes,
                                                 timeout=self.timeout)
            edit_response.read()

    def fetch_new_messages(self, retry=0):
        """
        Fetches new messages from the chatbox.
        :param retry: Level of desperation fetching the new messages.
        """
        with self.cookie_jar_lid:
            try:
                messages_response = self.url_opener.open(self.messages_url, timeout=self.timeout)
                messages_bytes = messages_response.read()
            except:
                logger.exception("fetching new messages failed, retry {0}".format(retry))
                # try harder
                self.retry(retry, self.fetch_new_messages)
                return
        messages_string = messages_bytes.decode(self.server_encoding)
        messages = etree.HTML(filter_invalid_xml(messages_string))

        all_trs = list(messages.iterfind("./body/tr"))
        if len(all_trs) == 0:
            # aw crap
            self.retry(retry, self.fetch_new_messages)
            return

        new_last_message = self.last_message_received
        visible_message_ids = set()
        new_and_edited_messages = []

        # for each message
        for tr in all_trs:
            # pick out the TDs
            tds = list(tr.iterfind("./td"))

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
            timestamp_match = timestamp_pattern.search(etree.tostring(meta_td, encoding="unicode"))
            if timestamp_match is not None:
                time_string = timestamp_match.group(1)
                try:
                    timestamp = time.mktime(time.strptime(time_string, "%d-%m-%y, %H:%M"))
                except ValueError:
                    # meh
                    pass

            # get the nickname
            nick_element = None
            for link_element in meta_td.iterfind(".//a[@href]"):
                if self.user_id_piece in link_element.attrib["href"]:
                    nick_element = link_element

            if nick_element is None:
                # bah, humbug
                continue

            nick = "".join(nick_element.itertext())
            nick_code = children_to_string(nick_element)

            is_banned = (nick.lower() in self.banned_nicknames)

            # cache the nickname
            self.lowercase_usernames_to_user_id_name_pairs[nick.lower()] = (user_id, nick)

            message_body = children_to_string(tds[1]).strip()
            message = ChatboxMessage(message_id, user_id, nick_code, message_body, timestamp,
                                     self.html_decompiler)

            if message_id in self.old_message_ids_to_bodies:
                old_body = self.old_message_ids_to_bodies[message_id]
                if old_body != message_body:
                    self.old_message_ids_to_bodies[message_id] = message_body
                    new_and_edited_messages.insert(0, (True, is_banned, message))
            else:
                self.old_message_ids_to_bodies[message_id] = message_body
                new_and_edited_messages.insert(0, (False, is_banned, message))

        # cull the bodies of messages that aren't visible anymore
        for message_id in list(self.old_message_ids_to_bodies.keys()):
            if message_id not in visible_message_ids:
                del self.old_message_ids_to_bodies[message_id]

        # distribute the news and modifications
        for (is_edited, is_banned, new_message) in new_and_edited_messages:
            self.distribute_message(new_message, is_edited, self.initial_salvo, is_banned)

        self.initial_salvo = False
        self.last_message_received = new_last_message

    def distribute_message(self, message, modified=False, initial_salvo=False, user_banned=False):
        """Distributes a message to the subscribers."""
        for subscriber in self.subscribers:
            try:
                subscriber(message, modified=modified, initial_salvo=initial_salvo, user_banned=user_banned)
            except:
                logger.exception("distribute_message(modified={0}, initial_salvo={1}, user_banned={2}): subscriber".format(
                    modified, initial_salvo, user_banned
                ))

    def subscribe_to_message_updates(self, new_subscriber):
        """
        Adds a new subscriber to be notified when a (new or updated) message is received.
        :param new_subscriber: A callable object (with one positional and three keyword arguments)
        that will receive the new message (a ChatboxMessage instance). The three keyword arguments
        are booleans: modified, initial_salvo and user_banned.
        """
        self.subscribers.add(new_subscriber)

    def perform_reading(self):
        """
        Processes incoming messages.
        """
        penalty_coefficient = 1
        while not self.stop_reading:
            try:
                self.fetch_new_messages()
                penalty_coefficient = 1
            except:
                logger.exception("exception fetching messages; penalty coefficient is {0}".format(penalty_coefficient))
            try:
                self.potential_dst_fix()
            except:
                logger.exception("potential DST fixing failed")
            penalty_coefficient += 1
            time.sleep(self.time_between_reads * penalty_coefficient)

    def get_user_id_for_name(self, username):
        """
        Returns the user ID of the user with the given name.
        :return: The user ID of the user with the given name, or -1 if the user does not exist.
        :rtype: int
        """
        result = self.get_user_id_and_nickname_for_uncased_name(username)
        return result[0] if result is not None else -1

    def get_user_id_and_nickname_for_uncased_name(self, username):
        """
        Returns the user ID and real nickname of the user with the given case-insensitive name.
        :rtype: (int, str)|None
        """
        lower_username = username.lower()
        if lower_username in self.lowercase_usernames_to_user_id_name_pairs:
            return self.lowercase_usernames_to_user_id_name_pairs[lower_username]

        if len(username) < 3:
            # vB doesn't allow usernames shorter than three characters
            return None

        result = self.ajax("usersearch", {"fragment": username})
        for child in result.iterfind("./user[@userid]"):
            user_id = child.attrib["userid"]
            username_text = "".join(child.itertext())

            if username.lower() == username_text.lower():
                # cache!
                self.lowercase_usernames_to_user_id_name_pairs[lower_username] = \
                    (user_id, username_text)
                return (user_id, username_text)

        # not found
        return None

    def substitute_custom_smileys(self, message):
        ret = message
        for (code, url) in self.custom_smiley_codes_to_urls.items():
            ret = ret.replace(code, "[icon]{0}[/icon]".format(url))
        return ret

    def potential_dst_fix(self):
        """
        Update Daylight Savings Time settings if necessary (to make the forum shut up).
        """
        utc_now = datetime.utcnow()
        if self.last_dst_update_hour_utc == utc_now.hour:
            # we already checked this hour
            return

        if utc_now.minute < self.dst_update_minute:
            # too early to check
            return

        # update hour to this one
        self.last_dst_update_hour_utc = utc_now.hour

        logger.debug("checking for DST update")

        # fetch a (computationally cheap) page from the server
        with self.cookie_jar_lid:
            cheap_response = self.url_opener.open(self.cheap_page_url, timeout=self.timeout)
            cheap_page_data = cheap_response.read()
            cheap_page_string = cheap_page_data.decode(self.server_encoding)

        # load it into lxml
        cheap_page = etree.HTML(cheap_page_string)
        dst_form = cheap_page.find(".//form[@name='dstform']")
        if dst_form is None:
            return

        logger.info("performing DST update")

        # find the forum's DST settings (they're hidden in JavaScript)
        first, second = None, None
        for match in dst_setting_pattern.finditer(cheap_page_string):
            first = int(match.group(1))
            second = int(match.group(2))
            break

        if first is None or second is None:
            logger.error("can't perform DST update: timezone calculation not found")
            return

        forum_offset = first + second
        local_tz = tzlocal()
        local_delta = local_tz.utcoffset(datetime.now(local_tz))
        local_offset = local_delta.total_seconds() // 3600

        if (forum_offset - local_offset) not in (1, -1):
            # DST hasn't changed
            logger.info("DST already correct")
            return

        # fish out all the necessary fields
        post_fields = {
            "s": dst_form.find(".//input[@name='s']").attrib['value'],
            "securitytoken": dst_form.find(".//input[@name='securitytoken']").attrib['value'],
            "do": "dst"
        }
        post_data = up.urlencode(post_fields, encoding="utf-8").encode("us-ascii")

        # call the update page
        with self.cookie_jar_lid:
            dst_response = self.url_opener.open(self.dst_url, data=post_data, timeout=self.timeout)
            dst_response.read()

        logger.info("DST updated")


if __name__ == '__main__':
    def message_received(message):
        print("[{t}] <{n}> {m}".format(t=message.timestamp, n=message.user_name, m=message.body))

    def message_modified(message):
        print("[{t}] * <{n}> {m}".format(t=message.timestamp, n=message.user_name, m=message.body))

    #import getpass
    #my_password = getpass.getpass()
    my_password = "ThisIsNotMyRealPassword;-)"

    conn = ChatboxConnector("http://forum.example.com/", "User Name", my_password)
    conn.subscribe_to_message_updates(message_received)
    conn.start()
