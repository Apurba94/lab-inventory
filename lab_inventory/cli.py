"""Command-line interface for lab-inventory."""
import argparse

from .core import Inventory


def _fmt(r):
    return "%4d  %-30s %8g %-6s %-12s lot %-10s exp %s" % (r["id"], r["name"][:30], r["quantity"], r["unit"],
                                                         (r["location"] or "")[:12], r["lot"] or "-", r["expiry"] or "-")


def main(argv=None):
    ap = argparse.ArgumentParser(prog="lab-inventory", description="Lab reagent and consumable inventory.")
    ap.add_argument("--db", help="SQLite file (default inventory.sqlite or $LAB_INVENTORY_DB)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    a = sub.add_parser("add")
    a.add_argument("name")
    a.add_argument("quantity", type=float)
    a.add_argument("unit")
    for f in ("catalog-no", "supplier", "cas", "lot", "location", "expiry", "hazard", "notes"):
        a.add_argument("--" + f)
    a.add_argument("--min", type=float, default=0, help="reorder threshold")
    u = sub.add_parser("use")
    u.add_argument("id", type=int)
    u.add_argument("amount", type=float)
    u.add_argument("--user", default="")
    u.add_argument("--purpose", default="")
    r = sub.add_parser("restock")
    r.add_argument("id", type=int)
    r.add_argument("amount", type=float)
    r.add_argument("--lot")
    r.add_argument("--expiry")
    s = sub.add_parser("find")
    s.add_argument("text", nargs="?", default="")
    s.add_argument("--location")
    al = sub.add_parser("alerts")
    al.add_argument("--days", type=int, default=30)
    sub.add_parser("usage")
    im = sub.add_parser("import")
    im.add_argument("csvfile")
    ex = sub.add_parser("export")
    ex.add_argument("csvfile")
    args = ap.parse_args(argv)
    inv = Inventory(args.db)
    try:
        if args.cmd == "add":
            fields = {k.replace("-", "_"): getattr(args, k.replace("-", "_")) for k in
                      ("catalog-no", "supplier", "cas", "lot", "location", "expiry", "hazard", "notes")}
            fields = {k: v for k, v in fields.items() if v}
            print("added #%d" % inv.add(args.name, args.quantity, args.unit, min_quantity=args.min, **fields))
        elif args.cmd == "use":
            left = inv.use(args.id, args.amount, args.user, args.purpose)
            print("%g left" % left)
        elif args.cmd == "restock":
            inv.restock(args.id, args.amount, args.lot, args.expiry)
        elif args.cmd == "find":
            for row in inv.search(args.text, args.location):
                print(_fmt(row))
        elif args.cmd == "alerts":
            res = inv.alerts(args.days)
            for key, title in (("expired", "EXPIRED"), ("expiring", "EXPIRING within %d days" % args.days),
                               ("low_stock", "LOW STOCK")):
                if res[key]:
                    print(title)
                    for row in res[key]:
                        print("  " + _fmt(row))
            if not any(res.values()):
                print("no alerts")
            return 1 if res["expired"] or res["low_stock"] else 0
        elif args.cmd == "usage":
            for row in inv.usage_summary():
                print("%-30s %10g %-6s (%d withdrawals)" % (row["name"][:30], row["total"], row["unit"], row["n"]))
        elif args.cmd == "import":
            print("%d item(s) imported" % inv.import_csv(args.csvfile))
        elif args.cmd == "export":
            print("%d item(s) exported" % inv.export_csv(args.csvfile))
    except (KeyError, ValueError) as exc:
        print("error: %s" % exc)
        return 1
    finally:
        inv.close()
    return 0
