import sys
import sqlite3
import base64
import os
import time
import threading
import requests
from requests.adapters import HTTPAdapter
from urllib3.util import Retry
from concurrent.futures import ThreadPoolExecutor, as_completed

MAX_WORKERS = 20
DEFAULT_RESULTS_DB = "openrouter_results.db"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"

# --- Thread-safe Media Cache with Bounded Memory ---
class BoundedMediaCache:
    """Thread-safe cache holding up to max_items media blobs in RAM."""
    def __init__(self, db_path, max_items=40):
        self.db_path = db_path
        self.max_items = max_items
        self._cache = {}
        self._lock = threading.Lock()

    def get(self, hash_value):
        with self._lock:
            if hash_value in self._cache:
                return self._cache[hash_value]

        # Extract outside the lock to avoid blocking other workers
        data_url, mime_type, byte_size = extract_media(self.db_path, hash_value)

        with self._lock:
            if len(self._cache) >= self.max_items:
                # Evict oldest entry (FIFO / LRU-like)
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
            self._cache[hash_value] = (data_url, mime_type, byte_size)
            return self._cache[hash_value]

def build_session(api_key, pool_size):
    """Build a thread-safe Session with connection pooling & auto-retry on dropped sockets."""
    session = requests.Session()
    session.headers.update({
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    })
    
    # Cloudflare drops idle connections; retries handle dead sockets automatically
    retry_strategy = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["POST"]
    )
    adapter = HTTPAdapter(
        pool_connections=pool_size,
        pool_maxsize=pool_size,
        max_retries=retry_strategy
    )
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session

def detect_mime_type(media_bytes):
    if not media_bytes:
        raise ValueError("Empty media data")
    if media_bytes.startswith(b'\xff\xd8\xff'):
        return "image/jpeg"
    if media_bytes.startswith(b'\x89PNG\r\n\x1a\n'):
        return "image/png"
    if len(media_bytes) >= 8 and media_bytes[4:8] == b'ftyp':
        return "video/mp4"
    if media_bytes.startswith((b'GIF87a', b'GIF89a')):
        return "image/gif"
    if len(media_bytes) >= 12 and media_bytes[:4] == b'RIFF' and media_bytes[8:12] == b'WEBP':
        return "image/webp"
    raise ValueError("Unsupported media type")

def extract_media(db_path, hash_value):
    # URI read-only mode avoids read lock overhead
    uri = f"file:{os.path.abspath(db_path)}?mode=ro"
    conn = sqlite3.connect(uri, uri=True, timeout=10)
    try:
        cur = conn.cursor()
        cur.execute("SELECT media FROM media_card WHERE hash = ?", (hash_value,))
        row = cur.fetchone()
        if row is None:
            raise ValueError(f"No media found for hash: {hash_value}")
        media_bytes = row[0]
    finally:
        conn.close()

    mime_type = detect_mime_type(media_bytes)
    byte_size = len(media_bytes)
    encoded = base64.b64encode(media_bytes).decode("ascii")
    data_url = f"data:{mime_type};base64,{encoded}"
    return data_url, mime_type, byte_size

def process_single_task(session, cache, hash_value, model, prompt):
    """Executed concurrently by worker threads."""
    try:
        data_url, mime_type, byte_size = cache.get(hash_value)
    except Exception as e:
        return hash_value, model, None, None, None, f"Media extraction error: {e}"

    if mime_type.startswith("image/"):
        media_part = {"type": "image_url", "image_url": {"url": data_url}}
    elif mime_type.startswith("video/"):
        media_part = {"type": "video_url", "video_url": {"url": data_url}}
    else:
        return hash_value, model, byte_size, mime_type, None, f"Unsupported MIME type: {mime_type}"

    payload = {
        "model": model,
        "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, media_part]}]
    }

    try:
        r = session.post(OPENROUTER_URL, json=payload, timeout=120)
        if r.status_code != 200:
            return hash_value, model, byte_size, mime_type, None, f"OpenRouter HTTP {r.status_code}: {r.text}"
        content = r.json()["choices"][0]["message"]["content"]
        return hash_value, model, byte_size, mime_type, content, None
    except Exception as e:
        return hash_value, model, byte_size, mime_type, None, str(e)

def init_results_db(path):
    conn = sqlite3.connect(path, timeout=60, isolation_level=None)
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    conn.execute("""
        CREATE TABLE IF NOT EXISTS media_info (
            hash TEXT PRIMARY KEY,
            byte_size INTEGER,
            format TEXT,
            mime_type TEXT,
            error TEXT,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS results (
            hash TEXT NOT NULL,
            model TEXT NOT NULL,
            prompt TEXT,
            byte_size INTEGER,
            format TEXT,
            response TEXT,
            error TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (hash, model)
        )
    """)
    return conn

def save_media_info(conn, hash_value, byte_size, fmt, mime_type, error=None):
    conn.execute("""
        INSERT INTO media_info (hash, byte_size, format, mime_type, error, updated_at)
        VALUES (?,?,?,?,?, CURRENT_TIMESTAMP)
        ON CONFLICT(hash) DO UPDATE SET
            byte_size=excluded.byte_size,
            format=excluded.format,
            mime_type=excluded.mime_type,
            error=excluded.error,
            updated_at=CURRENT_TIMESTAMP
    """, (hash_value, byte_size, fmt, mime_type, error))

def save_result(conn, hash_value, model, prompt, byte_size, fmt, response, error):
    conn.execute("""
        INSERT INTO results (hash, model, prompt, byte_size, format, response, error, updated_at)
        VALUES (?,?,?,?,?,?,?, CURRENT_TIMESTAMP)
        ON CONFLICT(hash, model) DO UPDATE SET
            prompt=excluded.prompt,
            byte_size=excluded.byte_size,
            format=excluded.format,
            response=excluded.response,
            error=excluded.error,
            updated_at=CURRENT_TIMESTAMP
    """, (hash_value, model, prompt, byte_size, fmt, response, error))

def format_duration(seconds):
    if seconds is None or seconds < 0 or seconds == float("inf"):
        return "--:--:--"
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    return f"{h:d}:{m:02d}:{s:02d}"

def progress_line(done, total, session_start, session_done_at_start):
    if total <= 0:
        return f"\r[{done}/{total}] 100.0%  ETA 0:00:00"
    elapsed = time.time() - session_start
    session_done = done - session_done_at_start
    pct = done / total * 100.0
    if session_done > 0:
        rate = elapsed / session_done
        eta_str = format_duration(rate * (total - done))
    else:
        eta_str = "--:--:--"
    return f"\r[{done}/{total}] {pct:5.1f}%  ETA {eta_str}  ({session_done} this session)"

def pop_flag_value(argv, flag, cast=str):
    if flag not in argv:
        return None
    idx = argv.index(flag)
    if idx + 1 >= len(argv):
        print(f"Error: {flag} requires a value", file=sys.stderr)
        sys.exit(1)
    raw = argv[idx + 1]
    try:
        value = cast(raw)
    except (ValueError, TypeError):
        print(f"Error: {flag} expected {cast.__name__}, got {raw!r}", file=sys.stderr)
        sys.exit(1)
    del argv[idx:idx + 2]
    return value

if __name__ == "__main__":
    argv = sys.argv[1:]
    limit = pop_flag_value(argv, "--limit", int)
    workers = pop_flag_value(argv, "--workers", int) or MAX_WORKERS
    api_key_flag = pop_flag_value(argv, "--api-key", str)

    if len(argv) < 4:
        print(
            f"Usage: {sys.argv[0]} <db_path> <hashes_file> <prompt_file> "
            f"<model1,model2> [results_db_path] [--limit N] [--workers N] [--api-key KEY]",
            file=sys.stderr,
        )
        sys.exit(1)

    db_path = argv[0]
    hashes_file = argv[1]
    prompt_file = argv[2]
    models = [m.strip() for m in argv[3].split(",") if m.strip()]
    results_db_path = argv[4] if len(argv) >= 5 else DEFAULT_RESULTS_DB

    api_key = api_key_flag or os.environ.get("OPENROUTER_API_KEY")
    if not api_key:
        print("Error: no API key. Pass --api-key KEY or set OPENROUTER_API_KEY.", file=sys.stderr)
        sys.exit(1)

    with open(hashes_file, "r", encoding="utf-8") as f:
        hashes = [line.strip() for line in f if line.strip()]
    with open(prompt_file, "r", encoding="utf-8") as f:
        prompt = f.read().strip()

    res_conn = init_results_db(results_db_path)

    # Check existing successes
    existing_results = set()
    for r in res_conn.execute("SELECT hash, model FROM results WHERE response IS NOT NULL AND error IS NULL"):
        existing_results.add((r[0], r[1]))

    # Determine pending work
    pending_tasks = []
    for h in hashes:
        for m in models:
            if (h, m) not in existing_results:
                pending_tasks.append((h, m))

    total_tasks = len(hashes) * len(models)
    done_tasks = total_tasks - len(pending_tasks)

    if limit is not None:
        pending_hashes_all = sorted({h for h, _ in pending_tasks})
        if len(pending_hashes_all) > limit:
            keep = set(pending_hashes_all[:limit])
            pending_tasks = [(h, m) for (h, m) in pending_tasks if h in keep]

    # Group tasks by hash so all models for a single hash hit the cache back-to-back
    pending_tasks.sort(key=lambda x: x[0])

    sys.stderr.write(
        f"Resuming: {done_tasks}/{total_tasks} done. "
        f"{len(pending_tasks)} queued. Workers={workers}. DB: {results_db_path}\n"
    )

    session_start = time.time()
    session_done_at_start = done_tasks
    sys.stderr.write(progress_line(done_tasks, total_tasks, session_start, session_done_at_start))
    sys.stderr.flush()

    # Bounded cache holds 2x the worker count in RAM
    media_cache = BoundedMediaCache(db_path, max_items=workers * 2)
    session = build_session(api_key, pool_size=workers)

    # Continuous work stream: As soon as 1 worker finishes, it picks up the next task immediately
    with ThreadPoolExecutor(max_workers=workers) as executor:
        futures = {
            executor.submit(process_single_task, session, media_cache, h, m, prompt): (h, m)
            for h, m in pending_tasks
        }

        for fut in as_completed(futures):
            hv, model, byte_size, mime_type, resp, err = fut.result()

            # Immediate save on the main thread (thread-safe, WAL mode)
            save_result(res_conn, hv, model, prompt, byte_size, mime_type, resp, err)
            if byte_size is not None or err:
                save_media_info(res_conn, hv, byte_size, mime_type, mime_type, err if not byte_size else None)

            done_tasks += 1
            sys.stderr.write(progress_line(done_tasks, total_tasks, session_start, session_done_at_start))
            sys.stderr.flush()

    sys.stderr.write("\n")