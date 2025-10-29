# POS Demo Data Import Script

This script imports POS demo data from CSV files into ERPNext in the correct order with proper field mappings.

## Files to Import

The script imports data from these CSV files in order:

1. **01_uom_20251020_130909.csv** - Unit of Measure (UOM)
2. **02_item_groups_20251020_130909.csv** - Item Groups
3. **03_brands_20251020_130909.csv** - Brands
4. **04_items_20251020_130909.csv** - Items (main product data)
5. **05_item_prices_20251020_130928.csv** - Item Prices

## Field Mappings

### UOM
- `UOM Name` → `uom_name`
- `Enabled` → `enabled`

### Item Group
- `Item Group Name` → `item_group_name`
- `Parent Item Group` → `parent_item_group`
- `Is Group` → `is_group`

### Brand
- `Brand` → `brand`

### Item
- `Item Code` → `item_code`
- `Item Name` → `item_name`
- `Item Group` → `item_group`
- `Stock UOM` → `stock_uom`
- `Is Stock Item` → `is_stock_item`
- `Include Item In Manufacturing` → `include_item_in_manufacturing`
- `Opening Stock` → `opening_stock`
- `Valuation Rate` → `valuation_rate`
- `Standard Rate` → `standard_rate`
- `Is Purchase Item` → `is_purchase_item`
- `Is Sales Item` → `is_sales_item`
- `Brand` → `brand`
- `Description` → `description`
- `Weight Per Unit` → `weight_per_unit`
- `Weight UOM` → `weight_uom`
- `Disabled` → `disabled`
- `Allow Alternative Item` → `allow_alternative_item`

### Item Price
- `Item Code` → `item_code`
- `Price List` → `price_list`
- `Price List Rate` → `price_list_rate`
- `Currency` → `currency`

## How to Run

### Method 1: Using bench execute (Recommended)

```bash
cd /Volumes/TZARMORSP/wrk/pos/frappe-bench
bench --site [your-site-name] execute erpnext.posdemo.import_pos_data.main
```

Replace `[your-site-name]` with your actual site name.

### Method 2: Using bench console

```bash
cd /Volumes/TZARMORSP/wrk/pos/frappe-bench
bench --site [your-site-name] console
```

Then in the console:
```python
from erpnext.posdemo.import_pos_data import main
main()
```

## Features

- ✅ **Duplicate Detection**: Skips existing records automatically
- ✅ **Error Handling**: Continues import even if individual records fail
- ✅ **Progress Tracking**: Shows real-time progress with detailed messages
- ✅ **Summary Report**: Provides detailed statistics at the end
- ✅ **Proper Order**: Imports dependencies first (UOM, Item Groups, Brands before Items)
- ✅ **Field Validation**: Handles missing or invalid data gracefully
- ✅ **Transaction Safety**: Uses commits and rollbacks for data integrity

## Output

The script provides detailed output including:
- Progress indicators for each record
- Success (✓), Skip (⊙), and Error (✗) symbols
- Summary statistics for each doctype
- Final totals

Example output:
```
============================================================
Importing Items...
============================================================
  ⊙ [1] Item already exists: ITEM001
  ✓ [50] Created Item: ITEM050
  ✓ [100] Created Item: ITEM100
  
Item Import Summary: 95 created, 5 skipped, 0 errors
```

## Troubleshooting

### Permission Errors
If you get permission errors, make sure you're running as Administrator or have System Manager role.

### Missing Dependencies
- Make sure UOM exists before importing Items
- Make sure Item Groups exist before importing Items
- Make sure Brands exist before importing Items
- Make sure Items exist before importing Item Prices

### File Not Found
Ensure all CSV files are in the same directory as the script:
`/Volumes/TZARMORSP/wrk/pos/frappe-bench/apps/erpnext/erpnext/posdemo/`

## Re-running the Script

The script is safe to re-run. It will:
- Skip any records that already exist
- Only import new records
- Show count of skipped vs created records

## Support

For issues or questions, check the error messages in the output. The script provides detailed error information for debugging.

