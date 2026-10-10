"""Offline regressions: a short page is not necessarily the end of a crawl."""
import unittest
from unittest.mock import patch
from src.collect_x402 import collect


class PartialPageTests(unittest.TestCase):
    def test_short_page_with_reported_remaining_items_continues(self):
        offsets = []
        def fetch(url, token, offset, limit):
            offsets.append(offset)
            data = {0: ['a', 'b'], 2: ['c', 'd']}[offset]
            return {'items': [{'resource': 'https://example.org/' + n} for n in data],
                    'pagination': {'total': 4}}
        with patch('src.collect_x402.request_page', fetch):
            _, rows = collect('https://example.org/discovery', None,
                              max_items=10, page_size=5, delay=0)
        self.assertEqual(offsets, [0, 2])
        self.assertEqual(len(rows), 4)

    def test_empty_page_with_reported_remaining_items_fails_closed(self):
        with patch('src.collect_x402.request_page', return_value={
            'items': [], 'pagination': {'total': 4}}):
            with self.assertRaisesRegex(RuntimeError, 'empty page'):
                collect('https://example.org/discovery', None, delay=0)

    def test_invalid_total_is_not_silently_treated_as_completion(self):
        for total in (-1, 0, '5', True, 0.5):
            with self.subTest(total=total), patch('src.collect_x402.request_page',
                    return_value={'items': [{'resource': 'https://example.org/a'}],
                                  'pagination': {'total': total}}):
                with self.assertRaisesRegex(ValueError, 'pagination total'):
                    collect('https://example.org/discovery', None, delay=0)

    def test_malformed_pagination_rejected(self):
        with patch('src.collect_x402.request_page', return_value={
            'items': [{'resource': 'https://example.org/a'}], 'pagination': 'bad'}):
            with self.assertRaisesRegex(ValueError, 'invalid pagination'):
                collect('https://example.org/discovery', None, delay=0)

    def test_short_page_without_total_preserves_terminal_behavior(self):
        with patch('src.collect_x402.request_page', return_value={
            'items': [{'resource': 'https://example.org/a'}]}):
            _, rows = collect('https://example.org/discovery', None,
                              max_items=10, page_size=5, delay=0)
        self.assertEqual(len(rows), 1)


if __name__ == '__main__':
    unittest.main()
