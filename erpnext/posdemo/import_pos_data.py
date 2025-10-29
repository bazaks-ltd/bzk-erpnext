#!/usr/bin/env python3
"""
Import POS Demo Data Script
Imports UOM, Item Groups, Brands, Items, and Item Prices from CSV files into ERPNext
"""

import frappe
from frappe import _
import csv
import os
from pathlib import Path


def get_csv_path(filename):
    """Get the full path to a CSV file"""
    script_dir = Path(__file__).parent
    return script_dir / filename


def import_uom(csv_file):
    """Import UOM (Unit of Measure) from CSV"""
    print(f"\n{'='*60}")
    print("Importing UOMs...")
    print(f"{'='*60}")
    
    success_count = 0
    error_count = 0
    skip_count = 0
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get('UOM Name') or not row['UOM Name'].strip():
                continue
                
            uom_name = row['UOM Name'].strip()
            enabled = int(row.get('Enabled', 1))
            
            try:
                if frappe.db.exists('UOM', uom_name):
                    print(f"  ⊙ UOM already exists: {uom_name}")
                    skip_count += 1
                    continue
                
                doc = frappe.get_doc({
                    'doctype': 'UOM',
                    'uom_name': uom_name,
                    'enabled': enabled
                })
                doc.insert(ignore_permissions=True)
                frappe.db.commit()
                print(f"  ✓ Created UOM: {uom_name}")
                success_count += 1
                
            except Exception as e:
                error_count += 1
                print(f"  ✗ Error creating UOM {uom_name}: {str(e)}")
                frappe.db.rollback()
    
    print(f"\nUOM Import Summary: {success_count} created, {skip_count} skipped, {error_count} errors")
    return success_count, skip_count, error_count


def import_item_groups(csv_file):
    """Import Item Groups from CSV"""
    print(f"\n{'='*60}")
    print("Importing Item Groups...")
    print(f"{'='*60}")
    
    success_count = 0
    error_count = 0
    skip_count = 0
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get('Item Group Name') or not row['Item Group Name'].strip():
                continue
                
            item_group_name = row['Item Group Name'].strip()
            parent_item_group = row.get('Parent Item Group', 'All Item Groups').strip()
            is_group = int(row.get('Is Group', 0))
            
            try:
                if frappe.db.exists('Item Group', item_group_name):
                    print(f"  ⊙ Item Group already exists: {item_group_name}")
                    skip_count += 1
                    continue
                
                doc = frappe.get_doc({
                    'doctype': 'Item Group',
                    'item_group_name': item_group_name,
                    'parent_item_group': parent_item_group,
                    'is_group': is_group
                })
                doc.insert(ignore_permissions=True)
                frappe.db.commit()
                print(f"  ✓ Created Item Group: {item_group_name}")
                success_count += 1
                
            except Exception as e:
                error_count += 1
                print(f"  ✗ Error creating Item Group {item_group_name}: {str(e)}")
                frappe.db.rollback()
    
    print(f"\nItem Group Import Summary: {success_count} created, {skip_count} skipped, {error_count} errors")
    return success_count, skip_count, error_count


def import_brands(csv_file):
    """Import Brands from CSV"""
    print(f"\n{'='*60}")
    print("Importing Brands...")
    print(f"{'='*60}")
    
    success_count = 0
    error_count = 0
    skip_count = 0
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if not row.get('Brand') or not row['Brand'].strip():
                continue
                
            brand = row['Brand'].strip()
            
            try:
                if frappe.db.exists('Brand', brand):
                    print(f"  ⊙ Brand already exists: {brand}")
                    skip_count += 1
                    continue
                
                doc = frappe.get_doc({
                    'doctype': 'Brand',
                    'brand': brand
                })
                doc.insert(ignore_permissions=True)
                frappe.db.commit()
                print(f"  ✓ Created Brand: {brand}")
                success_count += 1
                
            except Exception as e:
                error_count += 1
                print(f"  ✗ Error creating Brand {brand}: {str(e)}")
                frappe.db.rollback()
    
    print(f"\nBrand Import Summary: {success_count} created, {skip_count} skipped, {error_count} errors")
    return success_count, skip_count, error_count


def import_items(csv_file):
    """Import Items from CSV"""
    print(f"\n{'='*60}")
    print("Importing Items...")
    print(f"{'='*60}")
    
    success_count = 0
    error_count = 0
    skip_count = 0
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            if not row.get('Item Code') or not row['Item Code'].strip():
                continue
            
            item_code = row['Item Code'].strip()
            
            try:
                if frappe.db.exists('Item', item_code):
                    print(f"  ⊙ [{idx}] Item already exists: {item_code}")
                    skip_count += 1
                    continue
                
                # Prepare item data
                item_data = {
                    'doctype': 'Item',
                    'item_code': item_code,
                    'item_name': row.get('Item Name', item_code).strip(),
                    'item_group': row.get('Item Group', 'All Item Groups').strip(),
                    'stock_uom': row.get('Stock UOM', 'Nos').strip(),
                    'is_stock_item': int(row.get('Is Stock Item', 1)),
                    'include_item_in_manufacturing': int(row.get('Include Item In Manufacturing', 0)),
                    'is_purchase_item': int(row.get('Is Purchase Item', 1)),
                    'is_sales_item': int(row.get('Is Sales Item', 1)),
                    'disabled': int(row.get('Disabled', 0)),
                    'allow_alternative_item': int(row.get('Allow Alternative Item', 0)),
                }
                
                # Add optional fields if present
                if row.get('Brand') and row['Brand'].strip():
                    item_data['brand'] = row['Brand'].strip()
                
                if row.get('Description') and row['Description'].strip():
                    item_data['description'] = row['Description'].strip()
                
                if row.get('Standard Rate') and row['Standard Rate'].strip():
                    try:
                        item_data['standard_rate'] = float(row['Standard Rate'])
                    except ValueError:
                        pass
                
                if row.get('Opening Stock') and row['Opening Stock'].strip():
                    try:
                        item_data['opening_stock'] = float(row['Opening Stock'])
                    except ValueError:
                        pass
                
                if row.get('Valuation Rate') and row['Valuation Rate'].strip():
                    try:
                        item_data['valuation_rate'] = float(row['Valuation Rate'])
                    except ValueError:
                        pass
                
                if row.get('Weight Per Unit') and row['Weight Per Unit'].strip():
                    try:
                        item_data['weight_per_unit'] = float(row['Weight Per Unit'])
                    except ValueError:
                        pass
                
                if row.get('Weight UOM') and row['Weight UOM'].strip():
                    item_data['weight_uom'] = row['Weight UOM'].strip()
                
                doc = frappe.get_doc(item_data)
                doc.insert(ignore_permissions=True)
                frappe.db.commit()
                
                if idx % 50 == 0:
                    print(f"  ✓ [{idx}] Created Item: {item_code}")
                    
                success_count += 1
                
            except Exception as e:
                error_count += 1
                print(f"  ✗ [{idx}] Error creating Item {item_code}: {str(e)}")
                frappe.db.rollback()
    
    print(f"\nItem Import Summary: {success_count} created, {skip_count} skipped, {error_count} errors")
    return success_count, skip_count, error_count


def import_item_prices(csv_file):
    """Import Item Prices from CSV"""
    print(f"\n{'='*60}")
    print("Importing Item Prices...")
    print(f"{'='*60}")
    
    success_count = 0
    error_count = 0
    skip_count = 0
    
    with open(csv_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for idx, row in enumerate(reader, start=1):
            if not row.get('Item Code') or not row['Item Code'].strip():
                continue
            
            item_code = row['Item Code'].strip()
            price_list = row.get('Price List', 'Standard Selling').strip()
            
            try:
                # Check if item exists
                if not frappe.db.exists('Item', item_code):
                    print(f"  ⊙ [{idx}] Item does not exist: {item_code}, skipping price")
                    skip_count += 1
                    continue
                
                # Check if item price already exists
                existing_price = frappe.db.exists('Item Price', {
                    'item_code': item_code,
                    'price_list': price_list
                })
                
                if existing_price:
                    print(f"  ⊙ [{idx}] Item Price already exists: {item_code} - {price_list}")
                    skip_count += 1
                    continue
                
                # Parse price
                price_list_rate = 0
                if row.get('Price List Rate') and row['Price List Rate'].strip():
                    try:
                        price_list_rate = float(row['Price List Rate'])
                    except ValueError:
                        print(f"  ✗ [{idx}] Invalid price for {item_code}: {row['Price List Rate']}")
                        error_count += 1
                        continue
                
                currency = row.get('Currency', 'MUR').strip()
                
                doc = frappe.get_doc({
                    'doctype': 'Item Price',
                    'item_code': item_code,
                    'price_list': price_list,
                    'price_list_rate': price_list_rate,
                    'currency': currency
                })
                doc.insert(ignore_permissions=True)
                frappe.db.commit()
                
                if idx % 100 == 0:
                    print(f"  ✓ [{idx}] Created Item Price: {item_code} - {price_list_rate} {currency}")
                    
                success_count += 1
                
            except Exception as e:
                error_count += 1
                print(f"  ✗ [{idx}] Error creating Item Price for {item_code}: {str(e)}")
                frappe.db.rollback()
    
    print(f"\nItem Price Import Summary: {success_count} created, {skip_count} skipped, {error_count} errors")
    return success_count, skip_count, error_count


def main():
    """Main import function"""
    print("\n" + "="*60)
    print("POS DEMO DATA IMPORT SCRIPT")
    print("="*60)
    print(f"Site: {frappe.local.site}")
    print("="*60)
    
    # Define CSV files
    csv_files = {
        'uom': '01_uom_20251020_130909.csv',
        'item_groups': '02_item_groups_20251020_130909.csv',
        'brands': '03_brands_20251020_130909.csv',
        'items': '04_items_20251020_130909.csv',
        'item_prices': '05_item_prices_20251020_130928.csv'
    }
    
    # Verify all files exist
    missing_files = []
    for key, filename in csv_files.items():
        filepath = get_csv_path(filename)
        if not filepath.exists():
            missing_files.append(filename)
    
    if missing_files:
        print("\n❌ ERROR: The following CSV files are missing:")
        for file in missing_files:
            print(f"  - {file}")
        return
    
    # Summary statistics
    total_stats = {
        'uom': (0, 0, 0),
        'item_groups': (0, 0, 0),
        'brands': (0, 0, 0),
        'items': (0, 0, 0),
        'item_prices': (0, 0, 0)
    }
    
    try:
        # Import in correct order
        total_stats['uom'] = import_uom(get_csv_path(csv_files['uom']))
        total_stats['item_groups'] = import_item_groups(get_csv_path(csv_files['item_groups']))
        total_stats['brands'] = import_brands(get_csv_path(csv_files['brands']))
        total_stats['items'] = import_items(get_csv_path(csv_files['items']))
        total_stats['item_prices'] = import_item_prices(get_csv_path(csv_files['item_prices']))
        
        # Print final summary
        print("\n" + "="*60)
        print("FINAL IMPORT SUMMARY")
        print("="*60)
        
        for doc_type, (success, skipped, errors) in total_stats.items():
            print(f"{doc_type.upper():20s}: {success:4d} created, {skipped:4d} skipped, {errors:4d} errors")
        
        total_created = sum(s[0] for s in total_stats.values())
        total_skipped = sum(s[1] for s in total_stats.values())
        total_errors = sum(s[2] for s in total_stats.values())
        
        print("-"*60)
        print(f"{'TOTAL':20s}: {total_created:4d} created, {total_skipped:4d} skipped, {total_errors:4d} errors")
        print("="*60)
        
        if total_errors == 0:
            print("\n✅ Import completed successfully!")
        else:
            print(f"\n⚠️  Import completed with {total_errors} errors")
        
    except Exception as e:
        print(f"\n❌ Fatal error during import: {str(e)}")
        import traceback
        traceback.print_exc()
        frappe.db.rollback()


if __name__ == '__main__':
    # This script should be run with: bench execute erpnext.posdemo.import_pos_data.main
    main()

