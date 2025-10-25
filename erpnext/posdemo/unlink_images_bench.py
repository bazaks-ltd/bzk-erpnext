#!/usr/bin/env python3
"""
Frappe Bench Command: Unlink Images from Items
==============================================

This script removes image URLs from all items in ERPNext.
Useful for cleanup before re-linking or testing.

USAGE:
------
1. Upload this file to server:
   scp unlink_images_bench.py user@server:/path/to/frappe-bench/

2. Run on server:
   cd /path/to/frappe-bench
   bench --site yoursite execute unlink_images_bench.unlink_all_images --kwargs "{'dry_run': False}"

   Or for dry run:
   bench --site yoursite execute unlink_images_bench.unlink_all_images --kwargs "{'dry_run': True}"

SAFETY:
-------
- Uses SQL for performance
- Parameterized queries (SQL injection safe)
- Transaction support (rollback on error)
- Dry run mode for testing

"""

import frappe


def unlink_all_images(dry_run=False, filter_private_files_only=True):
    """
    Remove image URLs from all items
    
    Args:
        dry_run: If True, don't make changes (default: False)
        filter_private_files_only: If True, only unlink /private/files images (default: True)
    """
    
    print("\n" + "="*80)
    print("UNLINK IMAGES FROM ITEMS")
    print("="*80)
    print(f"Dry run: {dry_run}")
    print(f"Filter private files only: {filter_private_files_only}")
    print()
    
    stats = {
        'total_items': 0,
        'items_with_images': 0,
        'items_unlinked': 0,
        'errors': 0
    }
    
    if not dry_run:
        frappe.db.begin()
    
    try:
        # First, get count of all items
        total_count = frappe.db.sql("""
            SELECT COUNT(*) as count 
            FROM tabItem
        """, as_dict=True)[0].count
        
        stats['total_items'] = total_count
        print(f"Total items in database: {total_count:,}")
        
        # Build WHERE clause based on filter
        if filter_private_files_only:
            where_clause = "WHERE image IS NOT NULL AND image LIKE '/private/files/%'"
            print("Filtering: Only items with /private/files/ images")
        else:
            where_clause = "WHERE image IS NOT NULL AND image != ''"
            print("Filtering: All items with any image URL")
        
        # Get items with images
        items_with_images = frappe.db.sql(f"""
            SELECT name, image 
            FROM tabItem 
            {where_clause}
        """, as_dict=True)
        
        stats['items_with_images'] = len(items_with_images)
        print(f"Items with images to unlink: {stats['items_with_images']:,}")
        print()
        
        if stats['items_with_images'] == 0:
            print("No items found with images to unlink.")
            return stats
        
        # Show some examples
        print("Examples of items to be unlinked:")
        print("-" * 60)
        for i, item in enumerate(items_with_images[:10]):
            print(f"  {item.name} → {item.image}")
        
        if len(items_with_images) > 10:
            print(f"  ... and {len(items_with_images) - 10} more")
        print()
        
        if not dry_run:
            # Confirm before proceeding
            print("⚠️  WARNING: This will remove image URLs from all matching items!")
            print("   Items will no longer show images in ERPNext interface.")
            print("   File records will remain - only Item.image field cleared.")
            print()
        
        # Perform the unlinking
        if dry_run:
            print("[DRY RUN] Would unlink images from items...")
            stats['items_unlinked'] = stats['items_with_images']
        else:
            print("Unlinking images from items...")
            
            # Use SQL for bulk update
            if filter_private_files_only:
                result = frappe.db.sql("""
                    UPDATE tabItem 
                    SET image = NULL 
                    WHERE image IS NOT NULL 
                    AND image LIKE '/private/files/%'
                """)
            else:
                result = frappe.db.sql("""
                    UPDATE tabItem 
                    SET image = NULL 
                    WHERE image IS NOT NULL 
                    AND image != ''
                """)
            
            stats['items_unlinked'] = stats['items_with_images']
            print(f"✓ Unlinked images from {stats['items_unlinked']:,} items")
        
        if not dry_run:
            frappe.db.commit()
            print("✓ Changes committed to database")
        
    except Exception as e:
        if not dry_run:
            frappe.db.rollback()
        print(f"\n✗ Error: {e}")
        stats['errors'] += 1
        frappe.log_error(message=str(e), title='Unlink Images Error')
        raise
    
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    print(f"Total items:          {stats['total_items']:,}")
    print(f"Had images:           {stats['items_with_images']:,}")
    print(f"Images unlinked:      {stats['items_unlinked']:,}")
    print(f"Errors:               {stats['errors']:,}")
    print("="*80)
    print()
    
    if dry_run:
        print("This was a DRY RUN. Run again with dry_run=False to apply changes.")
    else:
        print(f"✓ Successfully unlinked images from {stats['items_unlinked']} items!")
        print("Note: File records still exist - only Item.image field was cleared.")
    
    return stats


def unlink_specific_items(item_codes, dry_run=False):
    """
    Remove image URLs from specific items
    
    Args:
        item_codes: List of item codes to unlink
        dry_run: If True, don't make changes (default: False)
    """
    
    print("\n" + "="*80)
    print("UNLINK IMAGES FROM SPECIFIC ITEMS")
    print("="*80)
    print(f"Items to process: {len(item_codes)}")
    print(f"Dry run: {dry_run}")
    print()
    
    stats = {
        'requested': len(item_codes),
        'found': 0,
        'had_images': 0,
        'unlinked': 0,
        'errors': 0
    }
    
    if not dry_run:
        frappe.db.begin()
    
    try:
        for i, item_code in enumerate(item_codes):
            # Check if item exists and has image
            item_data = frappe.db.sql("""
                SELECT name, image 
                FROM tabItem 
                WHERE name = %s
            """, (item_code,), as_dict=True)
            
            if not item_data:
                if i < 10:  # Show first 10 errors
                    print(f"  ⚠ Item not found: {item_code}")
                continue
            
            stats['found'] += 1
            current_image = item_data[0].image
            
            if not current_image:
                continue
            
            stats['had_images'] += 1
            
            if dry_run:
                if i < 10:
                    print(f"  [DRY RUN] Would unlink: {item_code} → {current_image}")
                stats['unlinked'] += 1
            else:
                try:
                    frappe.db.sql("""
                        UPDATE tabItem 
                        SET image = NULL 
                        WHERE name = %s
                    """, (item_code,))
                    
                    stats['unlinked'] += 1
                    
                    if i < 10:
                        print(f"  ✓ Unlinked: {item_code}")
                    
                except Exception as e:
                    print(f"  ✗ Error unlinking {item_code}: {e}")
                    stats['errors'] += 1
        
        if not dry_run:
            frappe.db.commit()
            print("✓ Changes committed to database")
        
    except Exception as e:
        if not dry_run:
            frappe.db.rollback()
        print(f"\n✗ Error: {e}")
        stats['errors'] += 1
        frappe.log_error(message=str(e), title='Unlink Specific Items Error')
        raise
    
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    print(f"Items requested:      {stats['requested']:,}")
    print(f"Items found:          {stats['found']:,}")
    print(f"Had images:           {stats['had_images']:,}")
    print(f"Images unlinked:      {stats['unlinked']:,}")
    print(f"Errors:               {stats['errors']:,}")
    print("="*80)
    
    return stats


if __name__ == '__main__':
    # For direct execution via bench execute
    pass