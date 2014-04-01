import vbcbbot.html_decompiler as hd

from lxml.etree import HTML
import unittest

__author__ = 'ondra'


class TestDecompileHtml(unittest.TestCase):
    def test_smiley(self):
        s2s = {"img/smiley/multihail.gif": ":multihail:"}
        dec = hd.HtmlDecompiler(s2s)
        dom = dec.decompile_lxml(HTML(
            b'!msg user: <img src="img/smiley/multihail.gif">'
        ))

        self.assertEqual(len(dom), 2)
        self.assertTrue(isinstance(dom[0], hd.Text))
        self.assertEqual(dom[0].text, "!msg user: ")
        self.assertTrue(isinstance(dom[1], hd.SmileyText))
        self.assertEqual(dom[1].text, ":multihail:")
        self.assertEqual(dom[1].smiley_url, "img/smiley/multihail.gif")
