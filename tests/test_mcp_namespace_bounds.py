import unittest
from src.mcp_namespace_bounds import analyze

OCT20 = [2365,1872,1114,897,375,354,333,231,213,190,155,152,127,125,119]
OCT23 = [2365,1894,1114,897,375,354,341,267,231,213,159,155,127,125,119]

class BoundsTests(unittest.TestCase):
    def test_actual_publisher_october_23_counts(self):
        result = analyze(server_names=49036, namespace_labels=30170, largest_namespace_counts=OCT23)
        self.assertEqual(result['top_namespace_server_names'], 8736)
        self.assertEqual(result['top_namespace_listing_share_pct'], '17.82')
        self.assertEqual(result['unreported_namespace_server_names'], 40300)
        self.assertEqual(result['hhi_lower_bound_floor_8dp'], '0.00496318')
        self.assertEqual(result['effective_namespace_count_upper_bound_ceiling_2dp'], '201.49')
        self.assertIsNone(result['verified_supplier_business_hhi'])
    def test_actual_publisher_october_20_counts(self):
        result = analyze(server_names=47066, namespace_labels=28901, largest_namespace_counts=OCT20)
        self.assertEqual(result['top_namespace_server_names'], 8622)
        self.assertEqual(result['top_namespace_listing_share_pct'], '18.32')
        self.assertEqual(result['hhi_lower_bound_floor_8dp'], '0.00532928')
    def test_known_full_distribution(self):
        result = analyze(server_names=10, namespace_labels=3, largest_namespace_counts=[6,3,1])
        self.assertEqual((result['hhi_lower_bound_exact_numerator'],result['hhi_lower_bound_exact_denominator']), (46,100))
    def test_balanced_integer_tail(self):
        result = analyze(server_names=14, namespace_labels=5, largest_namespace_counts=[7])
        self.assertEqual(result['hhi_lower_bound_exact_numerator'], 49+4+4+4+1)
    def test_reject_bad_counts(self):
        for kw in [
            {'server_names':True,'namespace_labels':2,'largest_namespace_counts':[2]},
            {'server_names':2,'namespace_labels':3,'largest_namespace_counts':[1]},
            {'server_names':10,'namespace_labels':3,'largest_namespace_counts':[9,2]},
            {'server_names':10,'namespace_labels':3,'largest_namespace_counts':[3,2]},
            {'server_names':10,'namespace_labels':3,'largest_namespace_counts':[4,5]},
            {'server_names':10,'namespace_labels':3,'largest_namespace_counts':[4,True]},
            {'server_names':10,'namespace_labels':3,'largest_namespace_counts':[]},
            {'server_names':10,'namespace_labels':3,'largest_namespace_counts':[1,1,1,1]},
        ]:
            with self.subTest(kw=kw), self.assertRaises(ValueError): analyze(**kw)

if __name__ == '__main__': unittest.main()
