import tempfile
import unittest
from pathlib import Path
from contracts import check_csv, timestamp

NOW = timestamp("2026-01-02T12:00:00Z")


class ContractTests(unittest.TestCase):
    def check(self, text, columns, **extra):
        with tempfile.TemporaryDirectory() as directory:
            p = Path(directory) / "data.csv"
            p.write_text(text)
            return check_csv(p, {"version": 1, "columns": columns} | extra, NOW)

    def test_schema_drift_and_missing_column(self):
        r = self.check("x,y\n1,2\n", {"x": {"type": "integer"}, "z": {"type": "string"}})
        self.assertEqual({i["code"] for i in r["issues"]}, {"missing_column", "unexpected_column", "null"})

    def test_duplicate_values_and_numeric_conversion(self):
        r = self.check("id\n01\n1\n", {"id": {"type": "integer", "unique": True}})
        self.assertEqual(r["issues"][0]["code"], "duplicate")

    def test_freshness_boundaries_and_future(self):
        r = self.check("ts\n2026-01-01T12:00:00Z\n2026-01-01T11:59:59Z\n2026-01-03T00:00:00Z\n",
                       {"ts": {"type": "timestamp", "max_age_hours": 24}})
        self.assertEqual([i["code"] for i in r["issues"]], ["stale", "future_timestamp"])

    def test_nonfinite_and_fractional_numbers(self):
        r = self.check("n\nNaN\nInfinity\n", {"n": {"type": "number"}})
        self.assertEqual(r["issue_count"], 2)
        self.assertFalse(self.check("n\n1.2\n", {"n": {"type": "integer"}})["passed"])

    def test_nullable_and_empty_dataset(self):
        self.assertTrue(self.check('id,n\n1,\n', {"id": {"type": "integer"},
                                                "n": {"type": "number", "nullable": True}})["passed"])
        self.assertFalse(self.check("id\n", {"id": {"type": "integer"}})["passed"])

    def test_malformed_and_duplicate_headers(self):
        r = self.check("id,id\n1,2,3\n", {"id": {"type": "integer"}})
        self.assertEqual({i["code"] for i in r["issues"]}, {"duplicate_header", "malformed_row"})

    def test_unknown_rule_fails_closed(self):
        with self.assertRaises(ValueError):
            self.check("id\n1\n", {"id": {"type": "integer", "unqiue": True}})

    def test_invalid_contract_options(self):
        for rule in ({"type": "timestamp", "min": 0}, {"type": "integer", "nullable": "false"},
                     {"type": "number", "min": 2, "max": 1}):
            with self.assertRaises(ValueError):
                self.check("id\n1\n", {"id": rule})
        with self.assertRaises(ValueError):
            self.check("id\n1\n", {"id": {"type": "integer"}}, allow_extra_colums=True)


if __name__ == "__main__":
    unittest.main()
