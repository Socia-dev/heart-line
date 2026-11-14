import sqlite3
import unittest

from tests import _db  # noqa: F401


class InheritanceTest(unittest.TestCase):
    def test_children_of_one_carrier_parent_about_half(self):
        con = sqlite3.connect(_db.COPY)
        rows = con.execute("""
            SELECT tc.fh > 0 FROM people c
            JOIN truth tc ON tc.person_id = c.id
            JOIN truth tm ON tm.person_id = c.mother_id
            JOIN truth tf ON tf.person_id = c.father_id
            WHERE (tm.fh > 0) + (tf.fh > 0) = 1 AND tm.fh + tf.fh = 1""").fetchall()
        n = len(rows)
        rate = sum(r[0] for r in rows) / n
        self.assertGreater(n, 200)
        self.assertTrue(0.42 <= rate <= 0.58, f"carrier rate {rate:.3f} over {n} children")

    def test_truth_kept_out_of_people(self):
        con = sqlite3.connect(_db.COPY)
        cols = {r[1] for r in con.execute("PRAGMA table_info(people)")}
        self.assertFalse(cols & {"fh", "variant", "true_ldl"})


if __name__ == "__main__":
    unittest.main()
