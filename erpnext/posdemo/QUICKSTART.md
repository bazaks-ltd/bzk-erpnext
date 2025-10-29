# Quick Start Guide - POS Data Import

## 🚀 Quick Import (Easiest Method)

```bash
cd /Volumes/TZARMORSP/wrk/pos/frappe-bench/apps/erpnext/erpnext/posdemo
./run_import.sh
```

The script will:
1. Show you available sites
2. Ask you to select one
3. Run the import automatically

## 📋 Alternative Methods

### Method 1: Direct bench command

```bash
cd /Volumes/TZARMORSP/wrk/pos/frappe-bench
bench --site your-site-name execute erpnext.posdemo.import_pos_data.main
```

### Method 2: Bench console (for debugging)

```bash
cd /Volumes/TZARMORSP/wrk/pos/frappe-bench
bench --site your-site-name console
```

Then run:
```python
from erpnext.posdemo.import_pos_data import main
main()
```

## 📊 What Gets Imported

| Order | DocType | File | Count (approx) |
|-------|---------|------|----------------|
| 1 | UOM | 01_uom_20251020_130909.csv | ~10 |
| 2 | Item Group | 02_item_groups_20251020_130909.csv | ~130 |
| 3 | Brand | 03_brands_20251020_130909.csv | ~1 |
| 4 | Item | 04_items_20251020_130909.csv | ~2,200 |
| 5 | Item Price | 05_item_prices_20251020_130928.csv | ~2,150 |

## ✅ Expected Output

```
============================================================
POS DEMO DATA IMPORT SCRIPT
============================================================
Site: your-site-name
============================================================

============================================================
Importing UOMs...
============================================================
  ✓ Created UOM: Gram
  ✓ Created UOM: Kg
  ⊙ UOM already exists: Nos

UOM Import Summary: 8 created, 2 skipped, 0 errors

... (continues for other doctypes)

============================================================
FINAL IMPORT SUMMARY
============================================================
UOM                 :    8 created,    2 skipped,    0 errors
ITEM_GROUPS         :  130 created,    0 skipped,    0 errors
BRANDS              :    1 created,    0 skipped,    0 errors
ITEMS               : 2200 created,    0 skipped,    0 errors
ITEM_PRICES         : 2150 created,    0 skipped,    0 errors
------------------------------------------------------------
TOTAL               : 4489 created,    2 skipped,    0 errors
============================================================

✅ Import completed successfully!
```

## 🔄 Re-running the Import

Safe to re-run anytime! The script will:
- ✅ Skip existing records
- ✅ Only create new records
- ✅ Show you what was skipped vs created

## ⚠️ Common Issues

### Issue: "Site not found"
**Solution:** Make sure you're using the correct site name. Run `bench --site` to see available sites.

### Issue: "Permission denied"
**Solution:** Make sure your user has System Manager or Administrator role.

### Issue: "Module not found"
**Solution:** Make sure you're running from the bench directory.

### Issue: "Item Group 'XYZ' does not exist"
**Solution:** The script imports Item Groups first. If you see this, some Item Groups might have failed. Check the Item Group import section in the output.

## 📝 Notes

- Import time: ~5-15 minutes depending on system
- Safe to interrupt (Ctrl+C) - just run again
- Check error messages for specific issues
- All data is committed per record, not in bulk

## 🔍 Verify Import

After import, check in ERPNext:
1. Go to **Stock** → **Item** → **Item** to see items
2. Go to **Stock** → **Item** → **Item Price** to see prices
3. Go to **Stock** → **Settings** → **UOM** to see units
4. Go to **Stock** → **Settings** → **Item Group** to see groups
5. Go to **Selling** → **Settings** → **Brand** to see brands

## 📧 Support Files

- `import_pos_data.py` - Main Python script
- `README_IMPORT.md` - Detailed documentation
- `run_import.sh` - Convenience bash script
- `QUICKSTART.md` - This file!

---

**Made with ❤️ for ERPNext POS Demo**

