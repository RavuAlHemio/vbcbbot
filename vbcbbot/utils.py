import re
import unicodedata

__author__ = 'ondra'


class RegexMatcher:
    def __init__(self, *args, **kwargs):
        self.regex = re.compile(*args, **kwargs)
        self.last_match = None

    def match(self, *args, **kwargs):
        self.last_match = self.regex.match(*args, **kwargs)
        return self.last_match is not None


def remove_control_characters_and_strip(text):
    ret = ""
    for c in text:
        if unicodedata.category(c)[0] != 'C':
            ret += c
    return ret.strip()
