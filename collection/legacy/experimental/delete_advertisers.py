
import sqlite3 as sql

def delete_unwanted_advertisers(db_path, keep_advertisers):
    keep_advertisers = list(keep_advertisers)  # ensure it's a list

    conn = sql.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    cursor = conn.cursor()

    try:
        # 1. Find page_ids to delete
        placeholders = ",".join("?" * len(keep_advertisers))
        cursor.execute(
            f"SELECT page_id FROM advertiser WHERE page_id NOT IN ({placeholders})",
            keep_advertisers
        )
        ids_to_delete = [row[0] for row in cursor.fetchall()]

        if not ids_to_delete:
            print("No advertisers to delete.")
            return

        # 2. Delete adverts (cascades to ad_media)
        placeholders_del = ",".join("?" * len(ids_to_delete))
        cursor.execute(
            f"DELETE FROM advert WHERE advertiser_id IN ({placeholders_del})",
            ids_to_delete
        )

        # 3. Delete advertisers themselves
        cursor.execute(
            f"DELETE FROM advertiser WHERE page_id IN ({placeholders_del})",
            ids_to_delete
        )

        # 4. Remove orphaned media_card rows
        cursor.execute("""
            DELETE FROM media_card
            WHERE hash NOT IN (SELECT DISTINCT hash FROM ad_media)
        """)

        # 5. (Optional) Remove orphaned search_keyword rows
        cursor.execute("""
            DELETE FROM search_keyword
            WHERE keyword NOT IN (SELECT DISTINCT keyword FROM advert)
        """)

        conn.commit()
        print(f"Deleted {len(ids_to_delete)} advertisers and their linked data.")

    except Exception as e:
        conn.rollback()
        print("Error during deletion:", e)
    finally:
        conn.close()

if __name__ == "__main__":
    db_file = "../hidden.db"
    keep_advertisers = ["107744255765263","262976362260250","1094480183729092","108502755363783","1016991278170086","107690995500910","100794799009319","106386435545919","109982691400872","100776272338168","390173370840409","1046636715197193","1038961279304024","107346882148033","1054646117724737","180265275161245","1041852985672059","107454715474087","1086525454536551","179863521868154","156623825158689","108861908660743","100984265016449","110464951335358","1090596030799584","124307067423686","116085481586255","104737498593894","124117869859625","730681293451432","1052605314599116","590240497515715"]
    delete_unwanted_advertisers(db_file, keep_advertisers)
