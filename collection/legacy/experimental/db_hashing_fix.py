
import sqlite3 as sql
import hashlib

def fix_hashing_bug_massive_db(db_name="adbank", batch_size=500):
    conn = sql.connect(f"data/{db_name}.db")
    cursor = conn.cursor()
    cursor.execute("PRAGMA foreign_keys = OFF;")
    
    print("Beginning sequential migration for massive database...")
    
    updated_count = 0
    last_rowid = 0  # We will track the physical row ID
    
    while True:
        # 1. Fetch rows sequentially by their physical location on disk
        # This prevents random-access jumping and cache thrashing.
        cursor.execute('''
            SELECT rowid, hash, media_format, media 
            FROM media_card 
            WHERE rowid > ? 
            ORDER BY rowid 
            LIMIT ?
        ''', (last_rowid, batch_size))
        
        rows = cursor.fetchall()
        
        # If no more rows are returned, we've reached the end of the table
        if not rows:
            break
            
        conn.execute("BEGIN TRANSACTION;")
        
        for row in rows:
            current_rowid, old_hash, media_format, media_bytes = row
            last_rowid = current_rowid # Update our tracker for the next batch
            
            new_hash = hashlib.blake2b(media_bytes).hexdigest()
            if old_hash == new_hash:
                continue
                
            cursor.execute('''
                INSERT OR IGNORE INTO media_card ("hash", "media_format", "media")
                VALUES (?, ?, ?)
            ''', (new_hash, media_format, media_bytes))
            
            cursor.execute('''
                UPDATE OR IGNORE ad_media
                SET hash = ?
                WHERE hash = ?
            ''', (new_hash, old_hash))
            
            cursor.execute('DELETE FROM ad_media WHERE hash = ?', (old_hash,))
            cursor.execute('DELETE FROM media_card WHERE hash = ?', (old_hash,))
            
            updated_count += 1
            
        # Commit the physical chunk
        conn.commit()
        print(f"Processed up to rowid {last_rowid}... (Updated {updated_count} so far)")

    cursor.execute("PRAGMA foreign_keys = ON;")
    
    print("Vacuuming database to reclaim space... (This WILL read and write the entire DB size once)")
    cursor.execute("VACUUM;")
    
    conn.close()
    print(f"Migration complete! Successfully fixed {updated_count} media hashes.")

def full_verify(db_name="adbank", batch_size=2000):
    conn = sql.connect(f"data/{db_name}.db")
    cursor = conn.cursor()
    
    last_rowid = 0
    correct = 0
    incorrect = 0
    
    print("Starting full sequential read-only verification...")
    
    while True:
        cursor.execute('''
            SELECT rowid, hash, media 
            FROM media_card 
            WHERE rowid > ? 
            ORDER BY rowid 
            LIMIT ?
        ''', (last_rowid, batch_size))
        
        rows = cursor.fetchall()
        if not rows:
            break
            
        for current_rowid, db_hash, media_bytes in rows:
            last_rowid = current_rowid
            
            real_hash = hashlib.blake2b(media_bytes).hexdigest()
            if db_hash == real_hash:
                correct += 1
            else:
                incorrect += 1
                
        print(f"Checked up to rowid {last_rowid}... (Found {incorrect} bad hashes so far)", end="\r")

    print("\n\n--- FINAL REPORT ---")
    print(f"Total Correct: {correct}")
    print(f"Total Incorrect: {incorrect}")

if __name__ == "__main__":
    fix_hashing_bug_massive_db("hidden")
