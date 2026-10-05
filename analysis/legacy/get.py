#!/usr/bin/env python3
"""
Read a SQLite database, extract metadata for DCO adverts, and save as NJSON.
All text is handled with strict UTF-8 encoding; Unicode escapes are converted
to actual characters in the output.
"""

import sqlite3
import json
import argparse
import sys


def serialize_metadata(value):
    """
    Convert any database value into a JSON string, ensuring:
    - UTF-8 characters are written directly (no \\uXXXX escapes)
    - None → null
    - bytes are decoded as UTF-8
    - If the value is a string that represents a JSON value, we parse it and
      re‑serialise to convert any Unicode escapes.
    - Otherwise, we serialise it as a plain JSON string.
    """
    if value is None:
        return "null"

    # Handle bytes (e.g., from BLOB columns)
    if isinstance(value, bytes):
        try:
            value = value.decode("utf-8")
        except UnicodeDecodeError as e:
            raise ValueError("metadata contains non-UTF-8 bytes") from e

    # For strings: try to parse as JSON, then re‑serialise with ensure_ascii=False
    if isinstance(value, str):
        try:
            parsed = json.loads(value)      # could be dict, list, str, int, etc.
            # Re‑serialise with ensure_ascii=False to keep Unicode characters
            return json.dumps(parsed, ensure_ascii=False)
        except json.JSONDecodeError:
            # Not a JSON value → treat as a plain string and quote it
            return json.dumps(value, ensure_ascii=False)

    # For any other Python type (dict, list, int, float, bool)
    return json.dumps(value, ensure_ascii=False)


def main():
    parser = argparse.ArgumentParser(
        description="Export metadata from SQLite as newline-delimited JSON."
    )
    parser.add_argument("database", help="Path to the SQLite database file")
    parser.add_argument("output", help="Path to the output NJSON file")
    args = parser.parse_args()

    query = """
        SELECT metadata
        FROM advert
        WHERE display_format = "DCO"
    """

    conn = None
    try:
        # Connect; text_factory = str ensures text is returned as Python str
        conn = sqlite3.connect(args.database)
        conn.text_factory = str
        cursor = conn.cursor()

        cursor.execute(query)

        # Open output file with explicit UTF‑8 encoding
        with open(args.output, "w", encoding="utf-8") as out_f:
            for row in cursor:
                metadata = row[0]
                json_line = serialize_metadata(metadata)
                out_f.write(json_line + "\n")

        print(f"Successfully wrote output to {args.output}")

    except sqlite3.Error as e:
        print(f"SQLite error: {e}", file=sys.stderr)
        sys.exit(1)
    except (IOError, OSError) as e:
        print(f"File error: {e}", file=sys.stderr)
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"JSON error: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Data encoding error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        sys.exit(1)
    finally:
        if conn:
            conn.close()


if __name__ == "__main__":
    main()