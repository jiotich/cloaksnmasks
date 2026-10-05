
import json
import time
import hashlib
import sqlite3 as sql
from collections import defaultdict

init_tables_query = """
PRAGMA foreign_keys = ON;

BEGIN TRANSACTION;
CREATE TABLE IF NOT EXISTS "advertiser" (
    "page_id" TEXT NOT NULL,
    "page_name" TEXT NOT NULL,
    "metadata" TEXT,
    PRIMARY KEY ("page_id")
);

CREATE TABLE IF NOT EXISTS advert (
    ad_archive_id TEXT PRIMARY KEY,
    advertiser_id TEXT NOT NULL,
    display_format TEXT NOT NULL,
    metadata TEXT NOT NULL,
    keyword TEXT NOT NULL,
    insertion_timestamp TEXT,
    FOREIGN KEY (advertiser_id) REFERENCES advertiser(page_id),
    FOREIGN KEY (keyword) REFERENCES "search_keyword"("keyword")
);

CREATE TABLE IF NOT EXISTS "ad_media" (
    "hash" TEXT NOT NULL,
    "ad_archive_id" TEXT NOT NULL,
    "url_filename" TEXT NOT NULL,
    PRIMARY KEY ("hash", "ad_archive_id", "url_filename"),
    FOREIGN KEY ("hash") REFERENCES "media_card"("hash")
        ON DELETE CASCADE,
    FOREIGN KEY ("ad_archive_id") REFERENCES "advert"("ad_archive_id")
        ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS "media_card" (
    "hash" TEXT NOT NULL,
	"media_format"	TEXT NOT NULL,
	"media"	BLOB NOT NULL,
	PRIMARY KEY("hash")
);

CREATE TABLE IF NOT EXISTS "search_keyword" (
    "keyword" TEXT PRIMARY KEY,
    "start_cursor" TEXT,
    "last_cursor" TEXT
);

COMMIT;
"""

class Manager():
    def __init__(self, db_name="adbank", logger=None):
        self.connection = sql.connect(f"data/{db_name}.db")
        self.new_media_session = defaultdict(int)
        self.new_ads_session = defaultdict(int)
        self.logger = logger
        self.create_tables()

    def advertiser_exists(self, page_id):
        query = "SELECT 1 FROM advertiser WHERE page_id = ? LIMIT 1"
        result = self.connection.execute(query, (page_id,))
        return result.fetchone() is not None

    def advert_exists(self, ad_id, page_id):
        query = "SELECT 1 FROM advert WHERE ad_archive_id = ? AND advertiser_id = ? LIMIT 1"
        result = self.connection.execute(query, (ad_id, page_id))
        return result.fetchone() is not None
    
    def media_exists(self, hash):
        query = f"SELECT hash FROM media_card WHERE hash = '{hash}'"
        result = self.connection.execute(query)
        result = result.fetchone()
        if result:
            return result[0]
        return ""

    def media_url_exists_return_hash(self, filename):
        query = f"SELECT hash FROM ad_media WHERE url_filename = '{filename}'"
        result = self.connection.execute(query)
        result = result.fetchone()
        if result:
            return result[0]
        return ""
    
    def media_ad_exists_return_hash(self, ad_id):
        query = f"SELECT hash FROM ad_media WHERE ad_archive_id = '{ad_id}'"
        result = self.connection.execute(query)
        result = result.fetchone()
        if result:
            return result[0]
        return ""
    
    def keyword_exists(self, keyword):
        query = f"SELECT * FROM search_keyword WHERE keyword = '{keyword}'"
        result = self.connection.execute(query)
        return bool(result.fetchall())

    def insert_media_return_hash(self, media_id, media_bytes: bytes):
        media_format = media_id.split('.')[-1]
        media_hash = hashlib.blake2b(media_bytes).hexdigest()
        if self.media_exists(media_hash):
            return media_hash
        query = f'INSERT INTO media_card ("hash", "media_format", "media") VALUES (?, ?, ?)'
        self.connection.execute(query, (media_hash, media_format, media_bytes))
        #self.connection.execute("COMMIT;")
        self.new_media_session[media_format]+=1
        return media_hash
    
    def insert_keyword_and_cursors(self, keyword, start_cursor="", last_cursor=""):
        if not self.keyword_exists(keyword):
            self.connection.execute(
                "INSERT INTO search_keyword (keyword, start_cursor, last_cursor) VALUES (?, ?, ?)",
                (keyword, None, None)
            )
            #self.connection.execute("COMMIT;")
        updates = []
        params = []
        if start_cursor:
            updates.append("start_cursor = ?")
            params.append(start_cursor)
        if last_cursor:
            updates.append("last_cursor = ?")
            params.append(last_cursor)
        
        if updates:
            sql = f"UPDATE search_keyword SET {', '.join(updates)} WHERE keyword = ?"
            params.append(keyword)
            self.connection.execute(sql, params)
            #self.connection.execute("COMMIT;")

    def insert_advertiser(self, page_id, page_name, metadata):
        try:
            query = f"INSERT INTO advertiser (page_id, page_name, metadata) VALUES (?, ?, ?);"
            self.connection.execute(query, (page_id, page_name, str(metadata)))
        except Exception as e:
            print(f"[SQL advertiser INSERTION ERROR {e}]> {query}")
            return

    def insert_advert(self, page_id: str, advert: dict, keyword:str, media_urls: list[str]=[], hashes: dict={}):
        parts = {
            "advertiser_id":page_id,
            "ad_archive_id":advert.get("ad_archive_id"),
            "display_format":advert.get("snapshot").get("display_format"),
            "metadata":  json.dumps(advert),
            "keyword": keyword,
            "insertion_timestamp": str(time.time())
        }
        k,v = parts.keys(), parts.values()
        try:
            query = f"INSERT INTO advert {tuple(k)} VALUES ({('?,'*len(v))[:-1]});"
            self.connection.execute(query, tuple(v))
            #self.connection.execute("COMMIT;")
        except Exception as e:
            print(f"[SQL advert INSERTION ERROR {e}]\t> {query}\n\t> {tuple(v)}")
        
        for media in media_urls:
            media_url_in_db = self.media_url_exists_return_hash(media)
            ad_content_in_db = self.media_ad_exists_return_hash(parts['ad_archive_id'])
            if (media_url_in_db and ad_content_in_db) or not hashes[media]:
                # url and content in db means the ad was already previously indexed
                # not hashes means the ad either has no media or returned an error
                continue
            try:
                query = f"INSERT INTO ad_media (hash, ad_archive_id, url_filename) VALUES ('{hashes[media]}','{parts['ad_archive_id']}','{media}');"
                self.connection.execute(query)
                #self.connection.execute("COMMIT;")
            except Exception as e:
                print(f"[SQL ad_media INSERTION ERROR {e}]> {query}")

        self.new_ads_session[parts["display_format"]]+=1

    def commit_session(self):
        self.connection.commit()

    def get_ad(self, ad_archive_id: str):
        query = f"SELECT * FROM advert WHERE ad_archive_id = '{ad_archive_id}'"
        result = self.connection.execute(query)
        return result.fetchall()
    
    def get_media_url_hash(self, media_url: str):
        query = f"SELECT * FROM ad_media WHERE ad_archive_id = '{media_url}'"
        result = self.connection.execute(query)
        return result.fetchall()

    def get_last_cursor(self, kw):
        query = f"SELECT last_cursor FROM search_keyword WHERE keyword = '{kw}'"
        result = self.connection.execute(query)
        return result.fetchone()
    
    def get_last_cursor_keywords(self, kws):
        cursors = defaultdict(str)
        for kw in kws:
            query = f"SELECT last_cursor FROM search_keyword WHERE keyword = '{kw}'"
            result = self.connection.execute(query)
            content = result.fetchone()
            if content:
                cursors[kw] = content[0]
        return cursors
    
    def get_all_kws(self):
        query = f"SELECT keyword FROM search_keyword"
        result = self.connection.execute(query)
        return [res[0] for res in result.fetchall()]

    def get_all_advertisers(self):
        query = f"SELECT page_id FROM advertiser"
        result = self.connection.execute(query)
        return [res[0] for res in result.fetchall()]

    def create_tables(self):
        self.connection.executescript(init_tables_query)

    def session_report(self):
        return self.new_media_session, self.new_ads_session

if __name__ == "__main__":
    db = Manager()
