from __future__ import annotations

import unittest
from unittest.mock import patch

from core.json_utils import (
    JSONParseError,
    chat_json_array,
    chat_json_object,
    parse_json_array,
    parse_json_object,
)


class TestParseJsonObject(unittest.TestCase):
    def test_plain_object(self):
        self.assertEqual(parse_json_object('{"a": 1}'), {"a": 1})

    def test_fenced_object(self):
        self.assertEqual(parse_json_object('```json\n{"a": 2}\n```'), {"a": 2})

    def test_prose_around_object(self):
        text = 'here is the result:\n{"x": "y", "z": [1, 2]}\nthanks'
        self.assertEqual(parse_json_object(text), {"x": "y", "z": [1, 2]})

    def test_missing_object_raises(self):
        with self.assertRaises(JSONParseError):
            parse_json_object("no json here")

    def test_array_rejected_for_object(self):
        with self.assertRaises(JSONParseError):
            parse_json_object("[1, 2, 3]")


class TestParseJsonArray(unittest.TestCase):
    def test_plain_array(self):
        self.assertEqual(parse_json_array('[{"a": 1}, {"b": 2}]'), [{"a": 1}, {"b": 2}])

    def test_fenced_array(self):
        self.assertEqual(parse_json_array('```\n[1, 2, 3]\n```'), [1, 2, 3])

    def test_missing_array_raises(self):
        with self.assertRaises(JSONParseError):
            parse_json_array("no array")


class TestChatJson(unittest.TestCase):
    @patch("core.json_utils.chat", return_value='{"k": "v"}')
    def test_chat_json_object(self, _mock):
        self.assertEqual(chat_json_object([{"role": "user", "content": "x"}]), {"k": "v"})

    @patch("core.json_utils.chat", return_value='[{"id": 1}]')
    def test_chat_json_array(self, _mock):
        self.assertEqual(chat_json_array([{"role": "user", "content": "x"}]), [{"id": 1}])


if __name__ == "__main__":
    unittest.main()
