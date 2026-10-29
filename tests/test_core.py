import datetime
import io
import os
import tempfile
import unittest
from contextlib import redirect_stdout

from lab_inventory.cli import main
from lab_inventory.core import Inventory

D = datetime.date(2026, 6, 1)


class InventoryTests(unittest.TestCase):
    def setUp(self):
        self.inv = Inventory(":memory:", today=D)

    def test_add_get_and_validation(self):
        i = self.inv.add("Tris base", 500, "g", catalog_no="T1503", location="Shelf A2", expiry="2027-01-01", min_quantity=100)
        self.assertEqual(self.inv.get(i)["location"], "Shelf A2")
        with self.assertRaises(ValueError):
            self.inv.add("x", 1, "g", colour="red")
        with self.assertRaises(ValueError):
            self.inv.add("x", 1, "g", expiry="01/02/2026")

    def test_use_and_restock(self):
        i = self.inv.add("Ethanol", 2.5, "L")
        self.assertAlmostEqual(self.inv.use(i, 0.5, "ana", "PCR cleanup"), 2.0)
        self.assertEqual(self.inv.get(i)["opened"], "2026-06-01")
        with self.assertRaises(ValueError):
            self.inv.use(i, 10)
        self.inv.restock(i, 2.5, lot="L2", expiry="2028-01-01")
        self.assertEqual((self.inv.get(i)["quantity"], self.inv.get(i)["lot"]), (4.5, "L2"))

    def test_alerts(self):
        self.inv.add("Old antibody", 1, "vial", expiry="2026-05-01")
        self.inv.add("Soon enzyme", 1, "vial", expiry="2026-06-20")
        self.inv.add("Gloves M", 2, "box", min_quantity=5)
        self.inv.add("Empty expired", 0, "vial", expiry="2020-01-01")
        a = self.inv.alerts(30)
        self.assertEqual([r["name"] for r in a["expired"]], ["Old antibody"])
        self.assertEqual([r["name"] for r in a["expiring"]], ["Soon enzyme"])
        self.assertEqual([r["name"] for r in a["low_stock"]], ["Gloves M"])

    def test_search_and_usage(self):
        a = self.inv.add("Agarose", 100, "g", location="Shelf B1")
        self.inv.add("Agar", 50, "g", location="Shelf C")
        self.assertEqual(len(self.inv.search("Agar")), 2)
        self.assertEqual(len(self.inv.search("Agar", location="Shelf B")), 1)
        self.inv.use(a, 10)
        self.inv.use(a, 5)
        self.assertEqual(self.inv.usage_summary()[0], {"name": "Agarose", "unit": "g", "total": 15.0, "n": 2})

    def test_csv_and_cli(self):
        with tempfile.TemporaryDirectory() as d:
            db, src, out = (os.path.join(d, n) for n in ("i.sqlite", "in.csv", "out.csv"))
            with open(src, "w", encoding="utf-8") as fh:
                fh.write("name,quantity,unit,location,expiry\nNaCl,1000,g,Shelf A,2030-01-01\nKCl,500,g,,\n")
            with redirect_stdout(io.StringIO()) as buf:
                main(["--db", db, "import", src])
                main(["--db", db, "use", "1", "200"])
                main(["--db", db, "export", out])
                self.assertEqual(main(["--db", db, "use", "2", "9999"]), 1)
            self.assertIn("2 item(s) imported", buf.getvalue())
            self.assertIn("800 left", buf.getvalue())
            with open(out, encoding="utf-8") as fh:
                self.assertIn("NaCl", fh.read())


if __name__ == "__main__":
    unittest.main()
