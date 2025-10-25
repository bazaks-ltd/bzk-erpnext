#!/usr/bin/env python3
"""
Frappe Bench Command: Delete File Records
=========================================

This script deletes File doctype records from ERPNext database.
Useful for cleanup before re-importing or testing.

⚠️  WARNING: This is DESTRUCTIVE! Always backup before running!

USAGE:
------
1. Upload this file to server:
   scp delete_files_bench.py user@server:/path/to/frappe-bench/

2. Run on server:
   cd /path/to/frappe-bench
   bench --site yoursite execute delete_files_bench.delete_file_records --kwargs "{'dry_run': False}"

   Or for dry run:
   bench --site yoursite execute delete_files_bench.delete_file_records --kwargs "{'dry_run': True}"

SAFETY:
-------
- Uses SQL for performance
- Parameterized queries (SQL injection safe)
- Transaction support (rollback on error)
- Dry run mode for testing
- Multiple filter options

"""

import frappe


def delete_file_records(dry_run=False, 
                       attached_to_item_only=True, 
                       private_files_only=True,
                       specific_filenames=None):
    """
    Delete File doctype records from database
    
    Args:
        dry_run: If True, don't make changes (default: False)
        attached_to_item_only: If True, only delete files attached to Items (default: True)
        private_files_only: If True, only delete /private/files URLs (default: True)
        specific_filenames: List of specific filenames to delete (default: None)
    """
    
    print("\n" + "="*80)
    print("DELETE FILE RECORDS")
    print("="*80)
    print(f"Dry run: {dry_run}")
    print(f"Item attachments only: {attached_to_item_only}")
    print(f"Private files only: {private_files_only}")
    print(f"Specific filenames: {len(specific_filenames) if specific_filenames else 0}")
    print()
    
    if not dry_run:
        print("⚠️  WARNING: This will PERMANENTLY DELETE File records!")
        print("   The actual image files on disk will remain.")
        print("   Only database records will be removed.")
        print()
    
    stats = {
        'total_files': 0,
        'matching_files': 0,
        'deleted': 0,
        'errors': 0
    }
    
    if not dry_run:
        frappe.db.begin()
    
    try:
        # Get total File count
        total_count = frappe.db.sql("""
            SELECT COUNT(*) as count 
            FROM tabFile
        """, as_dict=True)[0].count
        
        stats['total_files'] = total_count
        print(f"Total File records in database: {total_count:,}")
        
        # Build WHERE clause based on filters
        where_conditions = []
        params = []
        
        if attached_to_item_only:
            where_conditions.append("attached_to_doctype = %s")
            params.append('Item')
        
        if private_files_only:
            where_conditions.append("file_url LIKE %s")
            params.append('/private/files/%')
        
        if specific_filenames:
            placeholders = ','.join(['%s'] * len(specific_filenames))
            where_conditions.append(f"file_name IN ({placeholders})")
            params.extend(specific_filenames)
        
        where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
        
        # Get matching files
        files_to_delete = frappe.db.sql(f"""
            SELECT name, file_name, file_url, attached_to_doctype, attached_to_name
            FROM tabFile 
            {where_clause}
            ORDER BY creation DESC
        """, tuple(params), as_dict=True)
        
        stats['matching_files'] = len(files_to_delete)
        print(f"File records matching criteria: {stats['matching_files']:,}")
        print()
        
        if stats['matching_files'] == 0:
            print("No File records found matching the criteria.")
            return stats
        
        # Show some examples
        print("Examples of File records to be deleted:")
        print("-" * 80)
        for i, file_record in enumerate(files_to_delete[:10]):
            attachment_info = ""
            if file_record.attached_to_doctype and file_record.attached_to_name:
                attachment_info = f" → {file_record.attached_to_doctype}: {file_record.attached_to_name}"
            
            print(f"  {file_record.name}: {file_record.file_name}{attachment_info}")
        
        if len(files_to_delete) > 10:
            print(f"  ... and {len(files_to_delete) - 10} more")
        print()
        
        # Perform the deletion
        if dry_run:
            print("[DRY RUN] Would delete File records...")
            stats['deleted'] = stats['matching_files']
        else:
            print("Deleting File records...")
            
            # Delete in batches for better performance
            batch_size = 100
            for i in range(0, len(files_to_delete), batch_size):
                batch = files_to_delete[i:i + batch_size]
                file_names = [f.name for f in batch]
                
                # Use SQL for bulk delete
                placeholders = ','.join(['%s'] * len(file_names))
                frappe.db.sql(f"""
                    DELETE FROM tabFile 
                    WHERE name IN ({placeholders})
                """, tuple(file_names))
                
                stats['deleted'] += len(file_names)
                
                if i % 500 == 0:  # Progress every 500
                    print(f"  Progress: {stats['deleted']:,} / {stats['matching_files']:,} deleted")
            
            print(f"✓ Deleted {stats['deleted']:,} File records")
        
        if not dry_run:
            frappe.db.commit()
            print("✓ Changes committed to database")
        
    except Exception as e:
        if not dry_run:
            frappe.db.rollback()
        print(f"\n✗ Error: {e}")
        stats['errors'] += 1
        frappe.log_error(message=str(e), title='Delete File Records Error')
        raise
    
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    print(f"Total File records:   {stats['total_files']:,}")
    print(f"Matching criteria:    {stats['matching_files']:,}")
    print(f"Records deleted:      {stats['deleted']:,}")
    print(f"Errors:               {stats['errors']:,}")
    print("="*80)
    print()
    
    if dry_run:
        print("This was a DRY RUN. Run again with dry_run=False to apply changes.")
    else:
        print(f"✓ Successfully deleted {stats['deleted']} File records!")
        print("Note: Actual image files on disk were NOT deleted.")
    
    return stats


def delete_orphan_files(dry_run=False):
    """
    Delete File records that are not attached to any document
    
    Args:
        dry_run: If True, don't make changes (default: False)
    """
    
    print("\n" + "="*80)
    print("DELETE ORPHAN FILE RECORDS")
    print("="*80)
    print(f"Dry run: {dry_run}")
    print()
    
    stats = {
        'total_files': 0,
        'orphan_files': 0,
        'deleted': 0,
        'errors': 0
    }
    
    if not dry_run:
        frappe.db.begin()
    
    try:
        # Get total File count
        total_count = frappe.db.sql("""
            SELECT COUNT(*) as count 
            FROM tabFile
        """, as_dict=True)[0].count
        
        stats['total_files'] = total_count
        print(f"Total File records in database: {total_count:,}")
        
        # Get orphan files (not attached to anything)
        orphan_files = frappe.db.sql("""
            SELECT name, file_name, file_url
            FROM tabFile 
            WHERE (attached_to_doctype IS NULL OR attached_to_doctype = '')
            AND (attached_to_name IS NULL OR attached_to_name = '')
            ORDER BY creation DESC
        """, as_dict=True)
        
        stats['orphan_files'] = len(orphan_files)
        print(f"Orphan File records found: {stats['orphan_files']:,}")
        print()
        
        if stats['orphan_files'] == 0:
            print("No orphan File records found.")
            return stats
        
        # Show some examples
        print("Examples of orphan File records to be deleted:")
        print("-" * 60)
        for i, file_record in enumerate(orphan_files[:10]):
            print(f"  {file_record.name}: {file_record.file_name}")
        
        if len(orphan_files) > 10:
            print(f"  ... and {len(orphan_files) - 10} more")
        print()
        
        # Perform the deletion
        if dry_run:
            print("[DRY RUN] Would delete orphan File records...")
            stats['deleted'] = stats['orphan_files']
        else:
            print("Deleting orphan File records...")
            
            # Use SQL for bulk delete
            frappe.db.sql("""
                DELETE FROM tabFile 
                WHERE (attached_to_doctype IS NULL OR attached_to_doctype = '')
                AND (attached_to_name IS NULL OR attached_to_name = '')
            """)
            
            stats['deleted'] = stats['orphan_files']
            print(f"✓ Deleted {stats['deleted']:,} orphan File records")
        
        if not dry_run:
            frappe.db.commit()
            print("✓ Changes committed to database")
        
    except Exception as e:
        if not dry_run:
            frappe.db.rollback()
        print(f"\n✗ Error: {e}")
        stats['errors'] += 1
        frappe.log_error(message=str(e), title='Delete Orphan Files Error')
        raise
    
    print("\n" + "="*80)
    print("RESULTS")
    print("="*80)
    print(f"Total File records:   {stats['total_files']:,}")
    print(f"Orphan files found:   {stats['orphan_files']:,}")
    print(f"Records deleted:      {stats['deleted']:,}")
    print(f"Errors:               {stats['errors']:,}")
    print("="*80)
    
    return stats


def show_file_statistics():
    """
    Show statistics about File records in the database
    """
    
    print("\n" + "="*80)
    print("FILE RECORDS STATISTICS")
    print("="*80)
    
    # Total files
    total = frappe.db.sql("""
        SELECT COUNT(*) as count 
        FROM tabFile
    """, as_dict=True)[0].count
    
    # Files attached to Items
    item_files = frappe.db.sql("""
        SELECT COUNT(*) as count 
        FROM tabFile 
        WHERE attached_to_doctype = 'Item'
    """, as_dict=True)[0].count
    
    # Private files
    private_files = frappe.db.sql("""
        SELECT COUNT(*) as count 
        FROM tabFile 
        WHERE file_url LIKE '/private/files/%'
    """, as_dict=True)[0].count
    
    # Orphan files
    orphan_files = frappe.db.sql("""
        SELECT COUNT(*) as count 
        FROM tabFile 
        WHERE (attached_to_doctype IS NULL OR attached_to_doctype = '')
    """, as_dict=True)[0].count
    
    # Duplicates (same file_name)
    duplicates = frappe.db.sql("""
        SELECT COUNT(*) as count
        FROM (
            SELECT file_name
            FROM tabFile
            GROUP BY file_name
            HAVING COUNT(*) > 1
        ) as dups
    """, as_dict=True)[0].count
    
    print(f"Total File records:        {total:,}")
    print(f"Attached to Items:         {item_files:,}")
    print(f"Private files (/private/): {private_files:,}")
    print(f"Orphan files:              {orphan_files:,}")
    print(f"Duplicate filenames:       {duplicates:,}")
    print("="*80)
    
    return {
        'total': total,
        'item_files': item_files,
        'private_files': private_files,
        'orphan_files': orphan_files,
        'duplicates': duplicates
    }


if __name__ == '__main__':
    # For direct execution via bench execute
    pass