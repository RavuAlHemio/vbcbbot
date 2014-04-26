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

    def verbatim_string(self):
        raise NotImplementedError("this subclass didn't implement verbatim_string")


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

    def verbatim_string(self):
        if self.attribute_value is not None:
            av = "={0}".format(self.attribute_value.replace("[", "[noparse][[/noparse]"))
        else:
            av = ""

        return "[noparse][[/noparse]{n}{av}]{c}[noparse][[/noparse]/{n}]".format(
            n=self.name, av=av, c="".join([child.verbatim_string for child in self.children])
        )


class ListItem(Node):
    def __init__(self, children):
        self.children = children

    def __str__(self):
        return "[*]" + "".join([str(child) for child in self.children])

    def __repr__(self):
        return "ListItem({0})".format(repr(self.children))

    def verbatim_string(self):
        return "[noparse][*][/noparse]" + "".join([child.verbatim_string for child in self.children])


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

    def verbatim_string(self):
        return self.text.replace("[", "[noparse][[/noparse]")


class SmileyText(Text):
    def __init__(self, text, smiley_url=None):
        Text.__init__(self, text)
        self.smiley_url = smiley_url

    def __repr__(self):
        return "SmileyText({0}, {1})".format(repr(self.text), repr(self.smiley_url))

    def verbatim_string(self):
        return "[noparse]{0}[/noparse]".format(self.text)


def join_adjacent_text_nodes(dom_list):
    text_nodes_to_join = []
    ret = []
    for item in dom_list:
        if type(item) == Text:
            text_nodes_to_join.append(item)
        else:
            texts = "".join([n.text for n in text_nodes_to_join])
            if len(texts) > 0:
                ret.append(Text(texts))
            ret.append(item)
            text_nodes_to_join = []
    if len(text_nodes_to_join) > 0:
        texts = "".join([n.text for n in text_nodes_to_join])
        if len(texts) > 0:
            ret.append(Text(texts))
    return ret


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

    @property
    def smiley_url_to_symbol(self):
        return self.internal_smiley_url_to_symbol

    @smiley_url_to_symbol.setter
    def smiley_url_to_symbol(self, new_value):
        self.internal_smiley_url_to_symbol = new_value

        # update noparse string regex
        regex_for_noparse_string = "\\[+"
        for smiley_string in sorted(self.internal_smiley_url_to_symbol.values(), key=len, reverse=True):
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

    def decompile_lxml(self, elem, watch_out_for_p=False):
        ret = []
        for child in elem.xpath("./node()"):
            if hasattr(child, "iterchildren"):
                # it's a tag

                if child.tag == "body":
                    # lxml insists on packing everything into /html/body; work around this
                    return self.decompile_lxml(child, True)

                elif watch_out_for_p and child.tag == "p":
                    # lxml insisted on packing this even further: /html/body/p; work around this too
                    return self.decompile_lxml(child)

                elif child.tag == "img" and "src" in child.attrib:
                    if child.attrib['src'] in self.smiley_url_to_symbol:
                        # it's a smiley
                        ret.append(SmileyText(self.smiley_url_to_symbol[child.attrib['src']], child.attrib['src']))
                    elif self.tex_prefix is not None and \
                            child.attrib['src'].startswith(self.tex_prefix):
                        # TeX
                        tex_code = child.attrib['src'][len(self.tex_prefix):]
                        ret.append(Element("tex", [Text(tex_code)]))
                    else:
                        # icon?
                        ret.append(Element("icon", [Text(child.attrib['src'])]))

                elif child.tag == "a" and "href" in child.attrib:
                    if child.attrib["href"].startswith("mailto:"):
                        # e-mail link
                        address = child.attrib["href"][len("mailto:"):]
                        ret.append(Element("email", self.decompile_lxml(child), address))
                    else:
                        child_list = list(child.iterchildren())
                        if len(child_list) == 1 and child_list[0].tag == "img" and \
                                "src" in child_list[0].attrib and \
                                child_list[0].attrib['src'] == child.attrib['href']:
                            # icon -- let the img handler take care of it
                            ret += self.decompile_lxml(child)
                        else:
                            # some other link -- do it manually
                            # this also catches [thread], [post], [rtfaq], [stfw] -- the difference
                            # to normal [url] is so minimal I decided not to implement it
                            ret.append(Element("url", self.decompile_lxml(child),
                                               child.attrib["href"]))

                elif child.tag in ("b", "i", "u"):
                    # bold/italic/underline!
                    ret.append(Element(child.tag, self.decompile_lxml(child)))
                elif child.tag == "sub":
                    ret.append(Element("t", self.decompile_lxml(child)))
                elif child.tag == "sup":
                    ret.append(Element("h", self.decompile_lxml(child)))
                elif child.tag == "strike":
                    ret.append(Element("strike", self.decompile_lxml(child)))

                elif child.tag == "font" and "color" in child.attrib:
                    # font color
                    ret.append(Element("color", self.decompile_lxml(child), child.attrib['color']))

                elif child.tag == "span" and "style" in child.attrib:
                    if child.attrib["style"] == "direction: rtl; unicode-bidi: bidi-override;":
                        ret.append(Element("flip", self.decompile_lxml(child)))
                    elif child.attrib["style"].startswith("font-family: "):
                        font_family = child.attrib["style"][len("font-family: "):]
                        ret.append(Element("font", self.decompile_lxml(child), font_family))

                elif child.tag == "span" and "class" in child.attrib:
                    if child.attrib["class"] == "highlight":
                        ret.append(Element("highlight", self.decompile_lxml(child)))
                    elif child.attrib["class"] == "IRONY":
                        ret.append(Element("irony", self.decompile_lxml(child)))

                elif child.tag == "div" and "style" in child.attrib:
                    if child.attrib["style"] == "margin-left:40px":
                        ret.append(Element("indent", self.decompile_lxml(child)))
                    elif child.attrib["style"] == "text-align: left;":
                        ret.append(Element("left", self.decompile_lxml(child)))
                    elif child.attrib["style"] == "text-align: center;":
                        ret.append(Element("center", self.decompile_lxml(child)))
                    elif child.attrib["style"] == "text-align: right;":
                        ret.append(Element("right", self.decompile_lxml(child)))
                    elif child.attrib["style"] == "margin:5px; margin-top:5px;width:auto":
                        # why don't spoilers have a rational CSS class? -.-
                        spoiler_marker_elements = child.xpath("./div[@class='smallfont']")
                        if len(spoiler_marker_elements) > 0 and "Spoiler" in "".join(spoiler_marker_elements[0].itertext()):
                            spoiler_pre_elements = child.xpath("./pre[@class='alt2']")
                            if len(spoiler_pre_elements) > 0:
                                spoiler_text = "".join(spoiler_pre_elements[0].itertext())
                                ret.append(Element("spoiler", [Text(spoiler_text)]))

                elif child.tag == "div" and "class" in child.attrib:
                    if child.attrib["class"] == "bbcode_container":
                        code_pre = child.find("./pre[@class='bbcode_code']")
                        quote_div = child.find("./div[@class='bbcode_quote']")
                        if code_pre is not None:
                            # [code]
                            # FIXME: is this correct (enough)?
                            code_string = "".join(child.find(".//pre").itertext())
                            ret.append(Element("code", [Text(code_string)]))
                        elif quote_div is not None:
                            # [quote]
                            # find poster
                            post_number = None
                            poster_name = None
                            posted_by_div = quote_div.find(".//div[@class='bbcode_postedby']")
                            if posted_by_div is not None:
                                poster_name = "".join(posted_by_div.find(".//strong").itertext())
                                poster_link_a = posted_by_div.find(".//a[@href]")
                                if poster_link_a is not None and \
                                        poster_link_a.attrib["href"].startswith("showthread.php?p="):
                                    post_href_rest = \
                                        poster_link_a.attrib["href"][len("showthread.php?p="):]
                                    post_number = post_href_rest[:post_href_rest.find("#")]

                            quote_attrib = None
                            if poster_name is not None:
                                quote_attrib = poster_name
                                if post_number is not None:
                                    quote_attrib += ";{0}".format(post_number)

                            message_div = quote_div.find(".//div[@class='message']")

                            ret.append(Element("quote", self.decompile_lxml(message_div),
                                               quote_attrib))

                elif child.tag == "ul":
                    ret.append(Element("list", self.decompile_lxml(child)))
                elif child.tag == "ol" and "class" in child.attrib and \
                        child.attrib["class"] == "decimal":
                    ret.append(Element("list", self.decompile_lxml(child), "1"))
                elif child.tag == "li" and "style" in child.attrib and child.attrib["style"] == "":
                    ret.append(ListItem(self.decompile_lxml(child)))

                elif child.tag == "iframe" and "src" in child.attrib:
                    match = youtube_embed_re.match(child.attrib["src"])
                    if match is not None:
                        # YouTube embed
                        video_selector = "youtube;" + match.group(1)
                        ret.append(Element("video", [Text("a video")], video_selector))

                elif child.tag == "br":
                    ret.append(Text("\n"))

                else:
                    logger.warning("skipping unknown HTML element {0}".format(child.tag))

            else:
                # it's a string
                # put evil stuff (opening brackets and smiley triggers) into noparse tags
                escaped_children = intercalate_text_and_matches_as_element(
                    self.regex_for_noparse, child, "noparse"
                )
                ret += escaped_children

        return join_adjacent_text_nodes(ret)

if __name__ == '__main__':
    from lxml.etree import HTML
    smilies = {
        "pics/nb/smilies/smile.gif": ":)"
    }
    decompiler = HtmlDecompiler(smilies, "http://www.rueckgr.at/cgi-bin/mimetex.cgi?")
    dom = decompiler.decompile_lxml(HTML(
        '<img src="http://www.rueckgr.at/cgi-bin/mimetex.cgi?\\leftarrow"/>' +
        ' ist eigentlich kein Bild, aber das hier schon: ' +
        '<img src="pics/nb/smilies/smile.gif" /> und das hier ist ein Icon: ' +
        '<a href="http://www.informatik-forum.at/images/smilies/_fluffy__by_cindre.gif">' +
        '<img style="max-height: 50px" ' +
        'src="http://www.informatik-forum.at/images/smilies/_fluffy__by_cindre.gif" /></a> und ' +
        'das hier ist ein escapter Smiley :) cool oder?'
    ))
    print(dom)
