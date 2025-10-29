#!/usr/bin/env python3
"""
CSV File Validation Script
Validates CSV files before import and shows statistics
"""

import csv
from pathlib import Path
from collections import Counter


def validate_csv_file(filename, required_columns):
    """Validate a CSV file and return statistics"""
    filepath = Path(__file__).parent / filename
    
    if not filepath.exists():
        return {
            'exists': False,
            'error': f'File not found: {filename}'
        }
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames
            
            # Check required columns
            missing_columns = []
            for col in required_columns:
                if col not in headers:
                    missing_columns.append(col)
            
            # Count rows
            rows = list(reader)
            total_rows = len(rows)
            empty_rows = sum(1 for row in rows if not any(row.values()))
            valid_rows = total_rows - empty_rows
            
            # Get sample data (first 3 non-empty rows)
            sample_rows = []
            count = 0
            for row in rows:
                if any(row.values()) and count < 3:
                    sample_rows.append(row)
                    count += 1
            
            return {
                'exists': True,
                'filename': filename,
                'headers': headers,
                'required_columns': required_columns,
                'missing_columns': missing_columns,
                'total_rows': total_rows,
                'empty_rows': empty_rows,
                'valid_rows': valid_rows,
                'sample_rows': sample_rows,
                'is_valid': len(missing_columns) == 0
            }
    
    except Exception as e:
        return {
            'exists': True,
            'error': f'Error reading file: {str(e)}'
        }


def print_validation_result(result):
    """Print validation result in a formatted way"""
    if 'error' in result:
        print(f"  ❌ {result['error']}")
        return False
    
    print(f"  📄 File: {result['filename']}")
    print(f"  📊 Rows: {result['valid_rows']} valid, {result['empty_rows']} empty, {result['total_rows']} total")
    print(f"  📋 Columns: {', '.join(result['headers'][:5])}{'...' if len(result['headers']) > 5 else ''}")
    
    if result['missing_columns']:
        print(f"  ❌ Missing required columns: {', '.join(result['missing_columns'])}")
        return False
    else:
        print(f"  ✅ All required columns present")
    
    if result['sample_rows']:
        print(f"  📝 Sample data (first row):")
        first_row = result['sample_rows'][0]
        for key, value in list(first_row.items())[:3]:
            if value:
                print(f"     - {key}: {value[:50]}{'...' if len(str(value)) > 50 else ''}")
    
    return result['is_valid']


def main():
    """Main validation function"""
    print("\n" + "="*60)
    print("CSV FILES VALIDATION")
    print("="*60)
    print()
    
    # Define files and their required columns
    files_to_validate = {
        '01_uom_20251020_130909.csv': ['UOM Name', 'Enabled'],
        '02_item_groups_20251020_130909.csv': ['Item Group Name', 'Parent Item Group', 'Is Group'],
        '03_brands_20251020_130909.csv': ['Brand'],
        '04_items_20251020_130909.csv': [
            'Item Code', 'Item Name', 'Item Group', 'Stock UOM', 
            'Is Stock Item', 'Is Purchase Item', 'Is Sales Item'
        ],
        '05_item_prices_20251020_130928.csv': ['Item Code', 'Price List', 'Price List Rate', 'Currency']
    }
    
    all_valid = True
    results = {}
    
    # Validate each file
    for filename, required_cols in files_to_validate.items():
        print(f"\n{'─'*60}")
        print(f"Validating: {filename}")
        print(f"{'─'*60}")
        
        result = validate_csv_file(filename, required_cols)
        results[filename] = result
        is_valid = print_validation_result(result)
        
        if not is_valid:
            all_valid = False
    
    # Print summary
    print("\n" + "="*60)
    print("VALIDATION SUMMARY")
    print("="*60)
    
    total_records = 0
    for filename, result in results.items():
        if 'valid_rows' in result:
            status = "✅ PASS" if result['is_valid'] else "❌ FAIL"
            print(f"{status} {filename:45s} {result['valid_rows']:5d} records")
            total_records += result['valid_rows']
        else:
            print(f"❌ FAIL {filename:45s} ERROR")
    
    print("─"*60)
    print(f"Total records to import: {total_records}")
    print("="*60)
    
    if all_valid:
        print("\n✅ All files are valid and ready for import!")
        print("\nTo import, run:")
        print("  ./run_import.sh")
        print("  OR")
        print("  bench --site [site-name] execute erpnext.posdemo.import_pos_data.main")
    else:
        print("\n❌ Some files have errors. Please fix them before importing.")
    
    print()
    return all_valid


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)

