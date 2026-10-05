
import argparse
from pathlib import Path

import get_contents
import sql_manager


def count_table_rows(db, table_name):
    with db as conn:
        cursor = conn.cursor()
        query = f"SELECT COUNT(*) FROM {table_name}"
        cursor.execute(query)
        count = cursor.fetchone()[0]
        return count
    return None

def count_ads_by_display_format(conn):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT display_format, COUNT(*)
        FROM advert
        GROUP BY display_format
    """)
    return {row[0]: row[1] for row in cursor.fetchall()}

def count_shared_media(conn):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(DISTINCT hash)
        FROM (
            SELECT hash
            FROM ad_media
            GROUP BY hash
            HAVING COUNT(DISTINCT ad_archive_id) > 1
        )
    """)
    return cursor.fetchone()[0]

def count_ads_by_keyword(conn):
    cursor = conn.cursor()
    cursor.execute("""
        SELECT keyword, COUNT(*)
        FROM advert
        GROUP BY keyword
    """)
    return {row[0]: row[1] for row in cursor.fetchall()}

def db_report(db, inc_phish=False, inc_detail=False):
    conn = db.connection
    print("Total de anúncios: ", count_table_rows(conn, "advert"))
    print("Total de mídias: ", count_table_rows(conn, "ad_media"))
    print("Total de anunciantes: ", count_table_rows(conn, "advertiser"))
    if inc_phish:
        print("Total de anúncios com padrão de phishing: ", get_contents.query_db_phishing(db)["total"])
    
    if inc_detail:
        print("\nAnúncios por formato de exibição:")
        for fmt, total in count_ads_by_display_format(conn).items():
            print(f"  {fmt}: {total}")

        shared = count_shared_media(conn)
        print(f"\nMídias compartilhadas entre anúncios diferentes: {shared}")

        print("\nAnúncios por palavra-chave:")
        for kw, total in count_ads_by_keyword(conn).items():
            print(f"  {kw}: {total}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("-db", "--database", type=str, default="adbank", help="Name of .db file to store the colletion. Deault is 'adbank'.")
    parser.add_argument("-detail", default=False, action="store_true", help="Include stats about ad formats, shared media and keywords (may take longer for big DBs).")
    parser.add_argument("-phishing", default=False, action="store_true", help="Heuristic approximation of the amount of masked links.")
    args = parser.parse_args()
    
    if Path(args.database).is_file():
        db = sql_manager.Manager(args.database.replace(".db",""))
        db_report(db, args.phishing, args.detail)
    elif Path(args.database+".db").is_file():
        db = sql_manager.Manager(args.database)
        db_report(db, args.phishing, args.detail)
    else:
        print(f"File {args.database} not found.")
        db = sql_manager.Manager(args.database)
        db_report(db, args.phishing, args.detail)
