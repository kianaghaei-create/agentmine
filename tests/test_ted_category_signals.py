import unittest
from src.ted_category_signals import summarize


def snap(rows, complete=True):
    return {"source_url": "https://api.ted.europa.eu/v3/notices/search",
            "observed_at": "2026-10-12T17:00:00Z", "query": "PD>=20261001",
            "complete": complete, "unique_notices_collected": len(rows), "notices": rows}


def notice(id, kind="cn-standard", cpv=None, buyer=None):
    return {"publication-number": id, "notice-type": kind,
            "classification-cpv": cpv, "buyer-name": buyer}


class SignalsTests(unittest.TestCase):
    def test_distinct_notices_per_division_and_overlap(self):
        result = summarize(snap([notice('a', cpv=['72000000','72200000','48000000'], buyer='A'),
                                 notice('b', cpv='72000000', buyer='B')]))
        self.assertEqual([(c['cpv_division_prefix'], c['contract_notice_count_in_sample'])
                          for c in result['categories']], [('72',2),('48',1)])
        self.assertEqual(result['categories'][0]['distinct_unverified_buyer_labels'], 2)

    def test_awards_and_other_types_excluded(self):
        r = summarize(snap([notice('a','can-standard','72000000'),
                            notice('b','pin-standard','72000000'),
                            notice('c',None,'72000000')]))
        self.assertEqual(r['categories'], [])
        self.assertEqual(r['notice_family_counts'], {'contract_award':1,'other':1,'unknown':1})

    def test_incomplete_flag_preserved(self):
        self.assertFalse(summarize(snap([notice('a',cpv='72000000')], False))['complete_for_query'])

    def test_buyer_label_hhi_not_verified(self):
        r = summarize(snap([notice('a',cpv='72000000',buyer={'eng':['ACME']}),
                            notice('b',cpv='72000000',buyer='acme'),
                            notice('c',cpv='72000000',buyer='Other'),
                            notice('d',cpv='72000000')]))
        c = r['categories'][0]
        self.assertEqual(c['distinct_unverified_buyer_labels'], 2)
        self.assertEqual(c['buyer_label_coverage'], .75)
        self.assertAlmostEqual(c['buyer_label_hhi_in_labeled_sample'], .5556, places=4)
        self.assertIsNone(r['verified_distinct_buyers'])
        self.assertIsNone(r['agentmine_revenue'])

    def test_empty_snapshot(self):
        self.assertEqual(summarize(snap([]))['categories'], [])

    def test_missing_cpv_counted_only_for_contract_notices(self):
        r = summarize(snap([notice('a'), notice('b','can-standard')]))
        self.assertEqual(r['contract_notices_without_cpv'], 1)

    def test_bad_cpv_rejected(self):
        for cpv in ('7200', '7200000X', 72000000, ['72000000', 1], {'code':'72000000'}):
            with self.subTest(cpv=cpv), self.assertRaises(ValueError):
                summarize(snap([notice('a',cpv=cpv)]))

    def test_duplicate_notice_rejected(self):
        with self.assertRaises(ValueError):
            summarize(snap([notice('a'),notice('a')]))

    def test_untrusted_source_rejected(self):
        s=snap([]);s['source_url']='https://example.com'
        with self.assertRaises(ValueError):summarize(s)

    def test_snapshot_integrity_rejected(self):
        for val in (True, 2, '0'):
            s=snap([]);s['unique_notices_collected']=val
            with self.subTest(val=val), self.assertRaises(ValueError):summarize(s)

    def test_threshold_validation(self):
        for val in (0,True,1.5):
            with self.subTest(val=val), self.assertRaises(ValueError):summarize(snap([]),min_notices=val)

    def test_threshold_filters_small_categories(self):
        self.assertEqual(summarize(snap([notice('a',cpv='72000000')]),min_notices=2)['categories'],[])

    def test_malformed_buyer_rejected(self):
        with self.assertRaises(ValueError):
            summarize(snap([notice('a',cpv='72000000',buyer={'eng':[1]})]))


if __name__ == '__main__': unittest.main()
