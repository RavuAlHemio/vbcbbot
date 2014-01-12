import logging

__author__ = 'ondra'

logger = logging.getLogger("vbcbbot.html_decompiler")


class Node:
    @staticmethod
    def is_element():
        return False

    @staticmethod
    def is_text():
        return True

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
            n=self.name, av=av, c="".join(self.children)
        )

    def __repr__(self):
        return "Element({0}, {1}, {2})".format(repr(self.name), repr(self.children),
                                               repr(self.attribute_value))

    @staticmethod
    def is_element():
        return True


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


class HtmlDecompiler:
    """Decompiles HTML into the Chatbox DOM."""
    def __init__(self, smiley_url_to_symbol=None, tex_prefix=None):
        if smiley_url_to_symbol is None:
            smiley_url_to_symbol = {}
        self.smiley_url_to_symbol = smiley_url_to_symbol
        self.tex_prefix = tex_prefix

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
                    child_list = list(child.children)
                    if len(child_list) == 1 and child_list[0].name == "img" and \
                            child_list[0].has_attr("src") and \
                            child_list[0]['src'] == child['href']:
                        # icon -- let the img handler take care of it
                        ret += self.decompile_soup(child)
                    else:
                        # some other link -- do it manually
                        ret.append(Element("url", self.decompile_soup(child), child["href"]))

                elif child.name in "biu":
                    # bold/italic/underline!
                    ret.append(Element(child.name, self.decompile_soup(child)))

                elif child.name == "font" and child.has_attr("color"):
                    # font color
                    ret.append(Element("color", self.decompile_soup(child), child['color']))

                else:
                    logger.warning("skipping unknown HTML element {0}".format(child.name))

            else:
                # it's a string
                ret.append(Text(child))

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
        'src="http://www.informatik-forum.at/images/smilies/_fluffy__by_cindre.gif" /></a>',
        "html.parser"
    ))
    print(dom)
