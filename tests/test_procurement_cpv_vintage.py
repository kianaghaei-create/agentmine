"""Regression checks on official source-vintage CPV bid-intensity evidence."""
import copy
import json
from pathlib import Path
import unittest
from src.procurement_cpv_vintage import analyze

EVIDENCE = Path(__file__).resolve().parents[1] / 'data/evidence/procurement_cpv_vintage_2026-10-24.json'

class CPVReportVintageTests(unittest.TestCase):
    def setUp(self):
        self.evidence = json.loads(EVIDENCE.read_text(encoding='utf-8'))

    def test_latest_report_comparable_2023_2024(self):
        out = analyze(self.evidence)
        self.assertEqual([out['cpv48_2023_mean'],out['cpv48_2024_mean']], ['2.3','2.3'])
        self.assertEqual([out['cpv72_2023_mean'],out['cpv72_2024_mean']], ['4.5','3.7'])
        self.assertEqual(out['cpv48_2023_to_2024_change'], '0.0')
        self.assertEqual(out['cpv72_2023_to_2024_change'], '-0.8')
        self.assertEqual(out['cpv72_minus_cpv48_2024'], '1.4')
        self.assertEqual(out['cpv48_to_cpv72_2024_ratio'], '0.622')

    def test_retrospective_revision_is_not_growth(self):
        revisions = analyze(self.evidence)['retrospective_revisions']
        self.assertEqual(revisions,[
            {'cpv':'48','reference_year':2023,'previous_report_mean':'2.2','latest_report_mean':'2.3','revision_bids_per_procurement':'0.1'},
            {'cpv':'72','reference_year':2023,'previous_report_mean':'4.7','latest_report_mean':'4.5','revision_bids_per_procurement':'-0.2'}])

    def test_missing_latest_vintage_fails(self):
        self.evidence['observations'] = [r for r in self.evidence['observations'] if not (r['source_id']=='uhm_report_2025' and r['cpv']=='48' and r['reference_year']==2023)]
        with self.assertRaises(ValueError): analyze(self.evidence)

    def test_wrong_pdf_or_vintage_provenance_fails(self):
        for key, value in [('source_url','https://example.com'),('pdf_page',True),('pdf_page',0),('reference_year',2025)]:
            bad=copy.deepcopy(self.evidence)
            bad['observations'][0][key]=value
            with self.subTest(key=key),self.assertRaises(ValueError): analyze(bad)

    def test_duplicate_report_row_fails(self):
        self.evidence['observations'].append(copy.deepcopy(self.evidence['observations'][0]))
        with self.assertRaises(ValueError): analyze(self.evidence)

    def test_non_numeric_and_nonfinite_means_fail(self):
        for val in ('NaN','Infinity','-1.0','4','4.55',4.5,True,'100.0'):
            bad=copy.deepcopy(self.evidence)
            bad['observations'][0]['mean_bids']=val
            with self.subTest(val=val),self.assertRaises(ValueError): analyze(bad)

    def test_no_claims_about_customers_or_coverage(self):
        out=analyze(self.evidence)
        for key in ('cpv_bid_count_coverage','cpv48_one_bid_share','distinct_suppliers','verified_paying_buyers','agentmine_revenue'):
            self.assertIsNone(out[key])
        for key in ('bid_count_coverage_by_cpv_verified','paying_buyers_verified'):
            bad=copy.deepcopy(self.evidence)
            bad[key]=True
            with self.assertRaises(ValueError): analyze(bad)

    def test_order_independence(self):
        original=analyze(self.evidence)
        self.evidence['observations'].reverse()
        self.assertEqual(analyze(self.evidence),original)

if __name__=='__main__': unittest.main()
