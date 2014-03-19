import vbcbbot.modules.messenger as m
import unittest

__author__ = 'ondra'


class TestSplitRecipientAndMessage(unittest.TestCase):
    def test_simple(self):
        self.assertEqual(
            m.split_recipient_and_message("root: sup"),
            ("root", " sup")
        )

    def test_spaces_in_nick(self):
        self.assertEqual(
            m.split_recipient_and_message("The Irony: hi"),
            ("The Irony", " hi")
        )

    def test_spaces_in_message(self):
        self.assertEqual(
            m.split_recipient_and_message("chef: What's the story, morning glory?"),
            ("chef", " What's the story, morning glory?")
        )

    def test_spaces_in_nick_and_message(self):
        self.assertEqual(
            m.split_recipient_and_message("Alexander the Great: What's the story, morning glory?"),
            ("Alexander the Great", " What's the story, morning glory?")
        )

    def test_second_colon(self):
        self.assertEqual(
            m.split_recipient_and_message("fps doug: jeremy: uber micro"),
            ("fps doug", " jeremy: uber micro")
        )

    def test_escaped_colon(self):
        self.assertEqual(
            m.split_recipient_and_message("colon\\:cancer: Weird nickname."),
            ("colon:cancer", " Weird nickname.")
        )

    def test_escaped_backslash(self):
        self.assertEqual(
            m.split_recipient_and_message("backslash\\\\: r u a l33t h4x0r?"),
            ("backslash\\", " r u a l33t h4x0r?")
        )

    def test_invalid_escape(self):
        with self.assertRaises(ValueError):
            m.split_recipient_and_message("test\\a: lol")

    def test_no_colon(self):
        with self.assertRaises(ValueError):
            m.split_recipient_and_message("one two three five")

    def test_all_colons_escaped(self):
        with self.assertRaises(ValueError):
            m.split_recipient_and_message("one\\: two\\: three\\\\\\: four\\:")

    def test_smiley(self):
        self.assertEqual(
            m.split_recipient_and_message("user: :multihail:"),
            ("user", " :multihail:")
        )