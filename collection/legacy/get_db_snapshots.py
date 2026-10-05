
import argparse
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import List


def create_lightweight_copy(src_db: str, dest_db: str, logger=None):
    """
    Creates dest_db from src_db with all structure and data, but
    the media_card.media column is set to NULL.
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    dest = sqlite3.connect(dest_db)
    dest.execute("PRAGMA journal_mode = OFF")      # speed
    dest.execute("PRAGMA synchronous = OFF")
    dest.execute("PRAGMA foreign_keys = OFF")      # we’ll turn it on at the end

    try:
        # Attach source
        dest.execute("ATTACH DATABASE ? AS src", (src_db,))

        # Copy schema (tables & indexes)
        tables = dest.execute(
            "SELECT name, sql FROM src.sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()

        for table_name, create_sql in tables:
            if table_name == "media_card":
                new_sql = """
                CREATE TABLE media_card (
                    hash TEXT NOT NULL,
                    media_format TEXT NOT NULL,
                    media BLOB,          -- nullable
                    PRIMARY KEY(hash)
                )
                """
                logger.info("Creating table media_card (media nullable)")
            else:
                new_sql = create_sql
                logger.info(f"Creating table {table_name}")
            dest.execute(new_sql)

        # Copy indexes (none in your schema, but safe)
        indexes = dest.execute(
            "SELECT sql FROM src.sqlite_master WHERE type='index' AND sql IS NOT NULL"
        ).fetchall()
        for (idx_sql,) in indexes:
            if idx_sql:
                dest.execute(idx_sql)

        # ------ CRITICAL: one transaction for all inserts ------
        dest.execute("BEGIN")
        table_order = ["advertiser", "search_keyword", "advert", "media_card", "ad_media"]
        for table_name in table_order:
            logger.info(f"Copying data from {table_name} ...")
            if table_name == "media_card":
                cur = dest.execute(
                    f"INSERT INTO {table_name} (hash, media_format, media) "
                    f"SELECT hash, media_format, NULL FROM src.{table_name}"
                )
            else:
                cur = dest.execute(
                    f"INSERT INTO {table_name} SELECT * FROM src.{table_name}"
                )
            logger.info(f"  -> {cur.rowcount} rows copied")
        dest.execute("COMMIT")
        # -------------------------------------------------------

        # Now safe to detach
        dest.execute("DETACH DATABASE src")

        # Restore sensible defaults
        dest.execute("PRAGMA foreign_keys = ON")
        dest.execute("PRAGMA journal_mode = DELETE")
        dest.execute("PRAGMA synchronous = NORMAL")

        logger.info("Lightweight copy completed successfully.")

    except Exception as e:
        logger.error(f"Copy failed: {e}")
        raise
    finally:
        dest.close()

def extract_advertiser_subset(
    src_db: str, 
    dest_db: str, 
    page_ids: List[str], 
    include_media: bool = False, 
    logger: logging.Logger = None
):
    """
    Creates dest_db from src_db containing only data associated with the provided page_ids.
    If include_media is False, the media_card.media column will be set to NULL.
    """
    if logger is None:
        logger = logging.getLogger(__name__)

    dest = sqlite3.connect(dest_db, isolation_level=None)
    
    # Apply optimizations for massive bulk inserts
    dest.execute("PRAGMA journal_mode = OFF")
    dest.execute("PRAGMA synchronous = OFF")
    dest.execute("PRAGMA foreign_keys = OFF")

    try:
        # Attach source database
        dest.execute("ATTACH DATABASE ? AS src", (src_db,))

        # Copy schema (tables & indexes)
        tables = dest.execute(
            "SELECT name, sql FROM src.sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'"
        ).fetchall()

        for table_name, create_sql in tables:
            if table_name == "media_card":
                # Redefine media_card so the media blob can safely be null
                new_sql = """
                CREATE TABLE media_card (
                    hash TEXT NOT NULL,
                    media_format TEXT NOT NULL,
                    media BLOB,          -- nullable
                    PRIMARY KEY(hash)
                )
                """
                logger.info("Creating table media_card (media nullable)")
            else:
                new_sql = create_sql
                logger.info(f"Creating table {table_name}")
            
            dest.execute(new_sql)

        # Copy indexes
        indexes = dest.execute(
            "SELECT sql FROM src.sqlite_master WHERE type='index' AND sql IS NOT NULL"
        ).fetchall()
        
        for (idx_sql,) in indexes:
            dest.execute(idx_sql)

        # 1. Create a temporary table to hold the targeted page_ids. 
        # This prevents SQLite limits on maximum variables in an 'IN (?, ?, ...)' clause.
        logger.info(f"Loading {len(page_ids)} target page_ids into temporary table...")
        dest.execute("CREATE TEMP TABLE target_pages (page_id TEXT PRIMARY KEY)")
        dest.executemany(
            "INSERT OR IGNORE INTO target_pages (page_id) VALUES (?)", 
            [(pid,) for pid in page_ids]
        )

        dest.execute("BEGIN")

        # 2. Extract Advertiser
        logger.info("Extracting advertiser data...")
        cur = dest.execute("""
            INSERT INTO advertiser 
            SELECT * FROM src.advertiser 
            WHERE page_id IN (SELECT page_id FROM target_pages)
        """)
        logger.info(f"  -> {cur.rowcount} rows copied")

        # 3. Extract Search Keywords
        # Only copy keywords that actually yielded the ads we are extracting
        logger.info("Extracting search_keyword data...")
        cur = dest.execute("""
            INSERT INTO search_keyword 
            SELECT * FROM src.search_keyword 
            WHERE keyword IN (
                SELECT DISTINCT keyword FROM src.advert 
                WHERE advertiser_id IN (SELECT page_id FROM target_pages)
            )
        """)
        logger.info(f"  -> {cur.rowcount} rows copied")

        # 4. Extract Adverts
        logger.info("Extracting advert data...")
        cur = dest.execute("""
            INSERT INTO advert 
            SELECT * FROM src.advert 
            WHERE advertiser_id IN (SELECT page_id FROM target_pages)
        """)
        logger.info(f"  -> {cur.rowcount} rows copied")

        # 5. Extract Ad Media (Junction Table)
        # Using the local 'advert' table we just populated to speed up the subquery
        logger.info("Extracting ad_media junction data...")
        cur = dest.execute("""
            INSERT INTO ad_media 
            SELECT * FROM src.ad_media 
            WHERE ad_archive_id IN (SELECT ad_archive_id FROM advert)
        """)
        logger.info(f"  -> {cur.rowcount} rows copied")

        # 6. Extract Media Cards
        # Using the local 'ad_media' table we just populated to find the exact required hashes
        logger.info(f"Extracting media_card data (include_media={include_media})...")
        media_select_col = "media" if include_media else "NULL"
        cur = dest.execute(f"""
            INSERT INTO media_card (hash, media_format, media)
            SELECT hash, media_format, {media_select_col} 
            FROM src.media_card 
            WHERE hash IN (SELECT DISTINCT hash FROM ad_media)
        """)
        logger.info(f"  -> {cur.rowcount} rows copied")

        dest.execute("COMMIT")

        # Cleanup & Restore defaults
        dest.execute("DROP TABLE temp.target_pages")
        dest.execute("DETACH DATABASE src")
        
        dest.execute("PRAGMA foreign_keys = ON")
        dest.execute("PRAGMA journal_mode = DELETE")
        dest.execute("PRAGMA synchronous = NORMAL")

        logger.info("Subset extraction completed successfully.")

    except Exception as e:
        dest.execute("ROLLBACK")
        logger.error(f"Extraction failed: {e}")
        raise
    finally:
        dest.close()

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-db", "--database", type=str, default="adbank", help="Name of .db file to store the colletion. Deault is 'adbank'.")
    parser.add_argument("-lightsnap", default=False, action="store_true", help="Creates a lightweight snapshot of the DB, excluding media content.")
    parser.add_argument("-ownersnap", type=str, nargs="+", default=[], help="Creates a snapshot of specific advertisers content. Expects a list of advertiser IDs.")
    args = parser.parse_args()

    logging.basicConfig(
        format="[%(asctime)s: %(levelname)s]> %(message)s",
        style="%",
        datefmt="%Y-%m-%d %H:%M",
        level=logging.INFO,
    )

    snapshot_path = Path("data/snapshots/")
    if not snapshot_path.is_dir():
        snapshot_path.mkdir()
        
    cdate = datetime.now()
    if args.ownersnap:
        extract_advertiser_subset(
            src_db=f"data/{args.database}.db",
            dest_db=f"data/snapshots/{args.database} owners{'-light' if args.lightsnap else ''}-snapshot[{cdate.year}-{cdate.month}-{cdate.day} {cdate.hour}h{cdate.minute}m] .db",
            page_ids=args.ownersnap,
            include_media= not args.lightsnap
        )
    elif args.lightsnap:
        create_lightweight_copy(f"data/{args.database}.db", f"data/snapshots/{args.database} light-snapshot[{cdate.year}-{cdate.month}-{cdate.day} {cdate.hour}h{cdate.minute}m].db")
