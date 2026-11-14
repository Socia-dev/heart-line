import unittest

from heartline import dlcn

BASE = dict(ldl_untreated=None, premature_cad=False, xanthoma=False, arcus_under_45=False,
            fhx_premature_cad=False, fhx_high_ldl=False)


def score(**kw):
    return dlcn.score(**{**BASE, **kw})


class DLCNTest(unittest.TestCase):
    def test_ldl_only(self):
        r = score(ldl_untreated=7.0)
        self.assertEqual((r["total"], r["band"]), (5, "Possible"))

    def test_ldl_bands(self):
        for ldl, pts in ((3.9, 0), (4.0, 1), (5.0, 3), (6.5, 5), (8.5, 8), (12.0, 8)):
            self.assertEqual(score(ldl_untreated=ldl)["total"], pts, ldl)

    def test_hand_worked_probable(self):
        # LDL 5.2 (3) + early heart disease (2) + relative with early heart disease (1) = 6
        r = score(ldl_untreated=5.2, premature_cad=True, fhx_premature_cad=True)
        self.assertEqual((r["total"], r["band"]), (6, "Probable"))

    def test_hand_worked_definite(self):
        # LDL 9.0 (8) + tendon xanthoma (6) = 14
        r = score(ldl_untreated=9.0, xanthoma=True)
        self.assertEqual((r["total"], r["band"]), (14, "Definite"))

    def test_only_highest_item_per_group_counts(self):
        self.assertEqual(score(xanthoma=True, arcus_under_45=True)["total"], 6)
        self.assertEqual(score(fhx_premature_cad=True, fhx_high_ldl=True)["total"], 1)

    def test_band_edges(self):
        self.assertEqual(score(ldl_untreated=8.6)["band"], "Probable")  # 8 is probable
        self.assertEqual(score(ldl_untreated=8.6, fhx_high_ldl=True)["band"], "Definite")  # 9
        self.assertEqual(score(ldl_untreated=5.0)["band"], "Possible")  # 3
        self.assertEqual(score(ldl_untreated=4.5)["band"], "Unlikely")  # 1

    def test_dna(self):
        self.assertEqual(score(variant_found=True)["total"], 8)

    def test_statin_correction(self):
        self.assertAlmostEqual(dlcn.untreated(3.5, True, "high"), 7.0)
        self.assertAlmostEqual(dlcn.untreated(3.5, True, "moderate"), 5.0)
        self.assertEqual(dlcn.untreated(3.5, False, None), 3.5)


if __name__ == "__main__":
    unittest.main()
