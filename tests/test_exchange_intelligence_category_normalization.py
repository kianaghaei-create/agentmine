import unittest
from src.exchange_intelligence import Request, aggregate


class CategoryNormalizationTests(unittest.TestCase):
    def test_case_and_outer_whitespace_do_not_fragment_demand(self):
        rows = [Request('CPV-72', False, 100), Request(' cpv-72 ', True, 300)]
        result = aggregate(rows, minimum_count=2)
        self.assertEqual(len(result), 1)
        self.assertEqual(result[0]['category'], 'cpv-72')
        self.assertEqual(result[0]['requests'], 2)
        self.assertEqual(result[0]['unmatched'], 1)
        self.assertEqual(result[0]['fill_rate'], 0.5)
        self.assertFalse(result[0]['provenance_verified'])

    def test_free_text_unicode_labels_are_rejected(self):
        for category in ('STRASSE', 'Straße'):
            with self.subTest(category=category), self.assertRaisesRegex(ValueError, 'structured taxonomy'):
                aggregate([Request(category, True, 100)], minimum_count=2)

    def test_currencies_remain_separate_after_category_normalization(self):
        rows = [Request('CPV-72', True, 100, 'USD'), Request(' cpv-72 ', False, 200, 'EUR')]
        self.assertEqual(aggregate(rows, minimum_count=2), [])

    def test_empty_category_remains_rejected(self):
        with self.assertRaises(ValueError):
            aggregate([Request(' \t ', True, 100)])


if __name__ == '__main__':
    unittest.main()
