import logging
import re

__author__ = 'ondra'
youtube_embed_re = re.compile("^//www\\.youtube\\.com/([a-zA-Z0-9]+)\\?wmode=opaque$")

logger = logging.getLogger("vbcbbot.html_decompiler")


class Node:
    @staticmethod
    def is_element():
        return False

    @staticmethod
    def is_text():
        return False

    def has_children(self):
        return self.is_element()


class Element(Node):
    def __init__(self, name, children, attribute_value=None):
        self.name = name
        self.children = children
        self.attribute_value = attribute_value

    def __str__(self):
        if self.attribute_value is not None:
            av = "={0}".format(self.attribute_value)
        else:
            av = ""

        return "[{n}{av}]{c}[/{n}]".format(
            n=self.name, av=av, c="".join([str(child) for child in self.children])
        )

    def __repr__(self):
        return "Element({0}, {1}, {2})".format(repr(self.name), repr(self.children),
                                               repr(self.attribute_value))

    @staticmethod
    def is_element():
        return True


class ListItem(Node):
    def __init__(self, children):
        self.children = children

    def __str__(self):
        return "[*]" + "".join([str(child) for child in self.children])

    def __repr__(self):
        return "ListItem({0})".format(repr(self.children))


class Text(Node):
    def __init__(self, text):
        self.text = text

    def __str__(self):
        return self.text

    def __repr__(self):
        return "Text({0})".format(repr(self.text))

    @staticmethod
    def is_text():
        return True


def intercalate_text_and_matches_as_element(regex, string, element_tag="noparse"):
    ret = []
    last_unmatched_start_index = 0

    for match in regex.finditer(string):
        last_unmatched_string = string[last_unmatched_start_index:match.start()]
        if len(last_unmatched_string) > 0:
            ret.append(Text(last_unmatched_string))

        ret.append(Element(element_tag, [Text(match.group())]))

        last_unmatched_start_index = match.end()

    last_unmatched_string = string[last_unmatched_start_index:]
    if len(last_unmatched_string) > 0:
        ret.append(Text(last_unmatched_string))

    return ret


class HtmlDecompiler:
    """Decompiles HTML into the Chatbox DOM."""
    def __init__(self, smiley_url_to_symbol=None, tex_prefix=None):
        if smiley_url_to_symbol is None:
            smiley_url_to_symbol = {}
        self.smiley_url_to_symbol = smiley_url_to_symbol
        self.tex_prefix = tex_prefix

        regex_for_noparse_string = "\\[+"
        for smiley_string in sorted(smiley_url_to_symbol.values(), key=len, reverse=True):
            regex_for_noparse_string += "|" + re.escape(smiley_string)
        self.regex_for_noparse = re.compile(regex_for_noparse_string)

    @staticmethod
    def from_configuration(section):
        smiley_url_to_symbol = {}
        if "smiley url to symbol" in section:
            for line in section["smiley url to symbol"].split("\n"):
                bits = line.split(" ")
                if len(bits) != 2:
                    continue

                smiley_url_to_symbol[bits[0]] = bits[1]

        return HtmlDecompiler(smiley_url_to_symbol)

    def decompile_soup(self, soup):
        ret = []

        for child in soup.children:
            if hasattr(child, "children"):
                # it's a tag

                if child.name == "img" and child.has_attr("src"):
                    if child.attrs['src'] in self.smiley_url_to_symbol:
                        # it's a smiley
                        ret.append(Text(self.smiley_url_to_symbol[child.attrs['src']]))
                    elif self.tex_prefix is not None and \
                            child.attrs['src'].startswith(self.tex_prefix):
                        # TeX
                        tex_code = child.attrs['src'][len(self.tex_prefix):]
                        ret.append(Element("tex", [Text(tex_code)]))
                    else:
                        # icon?
                        ret.append(Element("icon", [Text(child.attrs['src'])]))

                elif child.name == "a" and child.has_attr("href"):
                    if child.attrs["href"].startswith("mailto:"):
                        # e-mail link
                        address = child.attrs["href"][len("mailto:"):]
                        ret.append(Element("email", self.decompile_soup(child), address))
                    else:
                        child_list = list(child.children)
                        if len(child_list) == 1 and child_list[0].name == "img" and \
                                child_list[0].has_attr("src") and \
                                child_list[0]['src'] == child.attrs['href']:
                            # icon -- let the img handler take care of it
                            ret += self.decompile_soup(child)
                        else:
                            # some other link -- do it manually
                            # this also catches [thread], [post], [rtfaq], [stfw] -- the difference
                            # to normal [url] is so minimal I decided not to implement it
                            ret.append(Element("url", self.decompile_soup(child),
                                               child.attrs["href"]))

                elif child.name in "biu":
                    # bold/italic/underline!
                    ret.append(Element(child.name, self.decompile_soup(child)))
                elif child.name == "sub":
                    ret.append(Element("t", self.decompile_soup(child)))
                elif child.name == "sup":
                    ret.append(Element("h", self.decompile_soup(child)))
                elif child.name == "strike":
                    ret.append(Element("strike", self.decompile_soup(child)))

                elif child.name == "font" and child.has_attr("color"):
                    # font color
                    ret.append(Element("color", self.decompile_soup(child), child.attrs['color']))

                elif child.name == "span" and child.has_attr("style"):
                    if child.attrs["style"] == "direction: rtl; unicode-bidi: bidi-override;":
                        ret.append(Element("flip", self.decompile_soup(child)))
                    elif child.attrs["style"].startswith("font-family: "):
                        font_family = child.attrs["style"][len("font-family: "):]
                        ret.append(Element("font", self.decompile_soup(child), font_family))

                elif child.name == "span" and child.has_attr("class"):
                    if child.attrs["class"] == "highlight":
                        ret.append(Element("highlight", self.decompile_soup(child)))
                    elif child.attrs["class"] == "IRONY":
                        ret.append(Element("irony", self.decompile_soup(child)))

                elif child.name == "div" and child.has_attr("style"):
                    if child.attrs["style"] == "margin-left:40px":
                        ret.append(Element("indent", self.decompile_soup(child)))
                    elif child.attrs["style"] == "text-align: left;":
                        ret.append(Element("left", self.decompile_soup(child)))
                    elif child.attrs["style"] == "text-align: center;":
                        ret.append(Element("center", self.decompile_soup(child)))
                    elif child.attrs["style"] == "text-align: right;":
                        ret.append(Element("right", self.decompile_soup(child)))

                elif child.name == "div" and child.has_attr("class"):
                    if child.attrs["class"] == "bbcode_container":
                        code_pre = child.find("pre", attrs={"class": "bbcode_code"},
                                              recursive=False)
                        quote_div = child.find("div", attrs={"class": "bbcode_quote"},
                                               recursive=False)
                        if code_pre is not None:
                            # [code]
                            # FIXME: is this correct (enough)?
                            code_string = child.find("pre").text
                            ret.append(Element("code", [Text(code_string)]))
                        elif quote_div is not None:
                            # [quote]
                            # find poster
                            post_number = None
                            poster_name = None
                            posted_by_div = quote_div.find("div",
                                                           attrs={"class": "bbcode_postedby"})
                            if posted_by_div is not None:
                                poster_name = posted_by_div.find("strong").text
                                poster_link_a = posted_by_div.find("a", href=True)
                                if poster_link_a is not None and \
                                        poster_link_a.attrs["href"].startswith("showthread.php?p="):
                                    post_href_rest = \
                                        poster_link_a.attrs["href"][len("showthread.php?p="):]
                                    post_number = post_href_rest[:post_href_rest.find("#")]

                            quote_attrib = None
                            if poster_name is not None:
                                quote_attrib = poster_name
                                if post_number is not None:
                                    quote_attrib += ";{0}".format(post_number)

                            message_div = quote_div.find("div", attrs={"class": "message"})

                            ret.append(Element("quote", self.decompile_soup(message_div),
                                               quote_attrib))

                elif child.name == "ul":
                    ret.append(Element("list", self.decompile_soup(child)))
                elif child.name == "ol" and child.has_attr("class") and \
                        child.attrs["class"] == "decimal":
                    ret.append(Element("list", self.decompile_soup(child), "1"))
                elif child.name == "li" and child.has_attr("style") and child.attrs["style"] == "":
                    ret.append(ListItem(self.decompile_soup(child)))

                elif child.name == "iframe" and child.has_attr("src"):
                    match = youtube_embed_re.match(child.attrs["src"])
                    if match is not None:
                        # YouTube embed
                        video_selector = "youtube;" + match.group(1)
                        ret.append(Element("video", [Text("a video")], video_selector))

                elif child.name == "br":
                    ret.append(Text("\n"))

                else:
                    logger.warning("skipping unknown HTML element {0}".format(child.name))

            else:
                # it's a string
                # put evil stuff (opening brackets and smiley triggers) into noparse tags
                escaped_children = intercalate_text_and_matches_as_element(
                    self.regex_for_noparse, child, "noparse"
                )
                ret += escaped_children

        return ret

if __name__ == '__main__':
    import bs4
    smilies = {
        "pics/nb/smilies/smile.gif": ":)"
    }
    decompiler = HtmlDecompiler(smilies, "http://www.rueckgr.at/cgi-bin/mimetex.cgi?")
    dom = decompiler.decompile_soup(bs4.BeautifulSoup(
        '<img src="http://www.rueckgr.at/cgi-bin/mimetex.cgi?\\leftarrow"/>' +
        ' ist eigentlich kein Bild, aber das hier schon: ' +
        '<img src="pics/nb/smilies/smile.gif" /> und das hier ist ein Icon: ' +
        '<a href="http://www.informatik-forum.at/images/smilies/_fluffy__by_cindre.gif">' +
        '<img style="max-height: 50px" ' +
        'src="http://www.informatik-forum.at/images/smilies/_fluffy__by_cindre.gif" /></a> und ' +
        'das hier ist ein escapter Smiley :) cool oder?',
        "html.parser"
    ))
    print(dom)
