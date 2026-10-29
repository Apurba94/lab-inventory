# lab-inventory

**A simple, local inventory for reagents and consumables: locations, lots, quantities, expiry
dates, a usage log, and alerts for expired, soon-expiring and low-stock items.**

Part of the *Research Automation Toolkit*: 100 open tools for daily research work.

## Why

Small labs track reagents in shared spreadsheets that nobody updates, so experiments stall on an
empty bottle and expired antibodies silently ruin results. Commercial LIMS are expensive and heavy.
A single SQLite file with a command-line interface (and an easy CSV import/export) is enough for most groups.

## Features

- Items with catalogue number, supplier, CAS, lot, location, unit, quantity, reorder threshold, expiry,
  opening date, hazard and notes
- `use` withdraws amounts (never below zero) and logs who used how much for what; `restock` with new lot/expiry
- `alerts`: expired, expiring within N days, at or below minimum stock (exit 1 for expired/low stock, so it can
  run as a scheduled check)
- Search by name, catalogue number, CAS or notes, filtered by location prefix; usage summary for ordering
- CSV import/export for spreadsheets

## Usage

```bash
pip install .
lab-inventory add "Tris base" 500 g --catalog-no T1503 --location "Shelf A2" --expiry 2027-01-01 --min 100
lab-inventory use 1 25 --user ana --purpose "Buffer prep"
lab-inventory find tris
lab-inventory alerts --days 30
lab-inventory import existing_spreadsheet.csv
```

## Testing

```bash
python -m unittest discover -s tests -t .
```

## License

MIT (c) JANIN A APURBA
