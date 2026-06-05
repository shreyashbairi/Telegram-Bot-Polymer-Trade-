"""
Database module for storing and retrieving polymer price data
"""
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import config
from normalizer import (
    PolymerNormalizer,
    strip_emojis,
    collapse_separators,
    structural_key,
    clean_display_name,
    is_valid_polymer_name,
)

class PolymerDatabase:
    def __init__(self, db_path: str = None):
        """Initialize database connection"""
        self.db_path = db_path or config.DATABASE_PATH
        # Loads polymer_aliases.txt and maps alternative spellings to a single
        # canonical "original name". Reloads automatically when the file changes.
        self.normalizer = PolymerNormalizer()
        self.init_database()

    def _connect(self):
        """Create a connection with WAL mode for concurrent bot+scraper access"""
        conn = sqlite3.connect(self.db_path, timeout=30)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        return conn

    def init_database(self):
        """Create database tables if they don't exist"""
        conn = self._connect()
        cursor = conn.cursor()

        # Table for storing polymer prices
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS polymer_prices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                polymer_name TEXT NOT NULL,
                normalized_name TEXT NOT NULL,
                price REAL,
                status TEXT,
                date DATE NOT NULL,
                message_text TEXT,
                message_link TEXT,
                chat_id TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(normalized_name, date, message_link)
            )
        ''')

        # Migration: Add chat_id column if it doesn't exist
        try:
            cursor.execute("SELECT chat_id FROM polymer_prices LIMIT 1")
        except sqlite3.OperationalError:
            # Column doesn't exist, add it
            print("Migrating database: Adding chat_id column...")
            cursor.execute("ALTER TABLE polymer_prices ADD COLUMN chat_id TEXT")
            print("Migration complete!")

        # Index for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_normalized_name
            ON polymer_prices(normalized_name)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_date
            ON polymer_prices(date)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_chat_id
            ON polymer_prices(chat_id)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_polymer_date
            ON polymer_prices(normalized_name, date)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_message_link
            ON polymer_prices(message_link)
        ''')

        conn.commit()
        conn.close()

    def normalize_polymer_name(self, name: str) -> str:
        """Normalize a polymer name to a single, separator-invariant key so the
        same polymer always maps to one identity (multiple rows then differ only
        by date/price, never by spelling).

        Pipeline:
          0. Alias canonicalization via polymer_aliases.txt
             (e.g. "Uz-Kor Gas J-2200", "J2200" -> "2200").
          1. structural_key(): strip emojis/dots, lower-case, collapse spaces and
             hyphens, and remove vendor words ("Shurtan 0120" -> "0120").
          2. Empty-key guard: a name of only vendor words never yields "" (which
             would collide with every other vendor-only name).
        Runs for BOTH inserts and queries, keeping the two in sync.
        """
        canonical = self.normalizer.canonicalize(name)
        key = structural_key(canonical)
        if not key:
            # Name was only vendor words / emojis \u2014 fall back to the collapsed
            # raw form so the key is never empty.
            key = collapse_separators(strip_emojis(canonical).lower())
        return key

    def message_link_exists(self, message_link: str) -> bool:
        """Check if any record with this message_link already exists in the DB"""
        if not message_link:
            return False
        conn = self._connect()
        cursor = conn.cursor()
        cursor.execute(
            'SELECT 1 FROM polymer_prices WHERE message_link = ? LIMIT 1',
            (message_link,)
        )
        exists = cursor.fetchone() is not None
        conn.close()
        return exists

    def insert_price(self, polymer_name: str, price: Optional[float],
                    status: str, date: datetime, message_text: str,
                    message_link: str, chat_id: str = None) -> bool:
        """Insert a polymer price record"""
        try:
            conn = self._connect()
            cursor = conn.cursor()

            # Store under a clean canonical display name: apply aliases (e.g.
            # "Uz-Kor Gas J-2200" -> "2200") then drop vendor words from what is
            # shown to users ("Uz-Kor Gas J550" -> "J550").
            display_name = clean_display_name(self.normalizer.canonicalize(polymer_name))
            normalized_name = self.normalize_polymer_name(polymer_name)

            cursor.execute('''
                INSERT OR REPLACE INTO polymer_prices
                (polymer_name, normalized_name, price, status, date, message_text, message_link, chat_id)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            ''', (display_name, normalized_name, price, status, date.date(),
                  message_text, message_link, chat_id))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error inserting price: {e}")
            return False

    def get_price_on_date(self, polymer_name: str, target_date: datetime) -> Optional[Dict]:
        """Get price for a specific date"""
        conn = self._connect()
        cursor = conn.cursor()

        normalized_name = self.normalize_polymer_name(polymer_name)

        cursor.execute('''
            SELECT polymer_name, price, status, date, message_text, message_link, chat_id
            FROM polymer_prices
            WHERE normalized_name = ?
            AND date = ?
            ORDER BY created_at DESC
            LIMIT 1
        ''', (normalized_name, target_date.date()))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'polymer_name': row[0],
                'price': row[1],
                'status': row[2],
                'date': row[3],
                'message_text': row[4],
                'message_link': row[5],
                'chat_id': row[6]
            }
        return None

    def get_latest_price(self, polymer_name: str) -> Optional[Dict]:
        """Get the most recent price for a polymer"""
        conn = self._connect()
        cursor = conn.cursor()

        normalized_name = self.normalize_polymer_name(polymer_name)

        cursor.execute('''
            SELECT polymer_name, price, status, date, message_text, message_link, chat_id
            FROM polymer_prices
            WHERE normalized_name = ?
            ORDER BY date DESC, created_at DESC
            LIMIT 1
        ''', (normalized_name,))

        row = cursor.fetchone()
        conn.close()

        if row:
            return {
                'polymer_name': row[0],
                'price': row[1],
                'status': row[2],
                'date': row[3],
                'message_text': row[4],
                'message_link': row[5],
                'chat_id': row[6]
            }
        return None

    def get_price_stats_for_date(self, polymer_name: str, target_date: datetime) -> Optional[Dict]:
        """Get price statistics (min, max, mean) for a polymer on a specific date"""
        conn = self._connect()
        cursor = conn.cursor()

        normalized_name = self.normalize_polymer_name(polymer_name)

        # Get all prices for this polymer on this date
        cursor.execute('''
            SELECT price, message_link, chat_id
            FROM polymer_prices
            WHERE normalized_name = ?
            AND date = ?
            AND price IS NOT NULL
            ORDER BY price ASC
        ''', (normalized_name, target_date.date()))

        rows = cursor.fetchall()

        if not rows:
            conn.close()
            return None

        prices = [row[0] for row in rows]

        # Find lowest and highest with their links
        lowest_price = min(prices)
        highest_price = max(prices)

        # Get the message links and chat IDs for lowest and highest
        lowest_link = None
        highest_link = None
        lowest_chat_id = None
        highest_chat_id = None

        for row in rows:
            if row[0] == lowest_price and not lowest_link:
                lowest_link = row[1]
                lowest_chat_id = row[2]
            if row[0] == highest_price:
                highest_link = row[1]
                highest_chat_id = row[2]

        # Calculate mean as (highest + lowest) / 2
        mean_price = (highest_price + lowest_price) / 2
        diff = highest_price - lowest_price

        # Get latest price for this date
        cursor.execute('''
            SELECT price, message_link, chat_id
            FROM polymer_prices
            WHERE normalized_name = ?
            AND date = ?
            AND price IS NOT NULL
            ORDER BY created_at DESC
            LIMIT 1
        ''', (normalized_name, target_date.date()))

        latest_row = cursor.fetchone()
        conn.close()

        latest_price = latest_row[0] if latest_row else None
        latest_link = latest_row[1] if latest_row else None
        latest_chat_id = latest_row[2] if latest_row else None

        return {
            'lowest': lowest_price,
            'highest': highest_price,
            'mean': mean_price,
            'diff': diff,
            'lowest_link': lowest_link,
            'highest_link': highest_link,
            'lowest_chat_id': lowest_chat_id,
            'highest_chat_id': highest_chat_id,
            'latest_price': latest_price,
            'latest_link': latest_link,
            'latest_chat_id': latest_chat_id,
            'count': len(prices)
        }

    def get_unique_polymers_with_latest_date(self) -> List[Dict]:
        """Get unique polymers (one row per normalized name) with their most
        recent date. The display name is the most frequently used spelling for
        that polymer, so the menu shows one consistent name instead of an
        arbitrary variant."""
        conn = self._connect()
        cursor = conn.cursor()

        # Sub-select picks the most common polymer_name for each normalized_name.
        cursor.execute('''
            SELECT p.normalized_name,
                   (SELECT d.polymer_name FROM polymer_prices d
                    WHERE d.normalized_name = p.normalized_name
                    GROUP BY d.polymer_name
                    ORDER BY COUNT(*) DESC, d.polymer_name LIMIT 1) AS display_name,
                   MAX(p.date) AS latest_date
            FROM polymer_prices p
            GROUP BY p.normalized_name
            ORDER BY display_name
        ''')

        results = []
        for row in cursor.fetchall():
            results.append({
                'normalized_name': row[0],
                'display_name': row[1],
                'latest_date': row[2]
            })

        conn.close()
        return results

    def search_polymers(self, search_query: str) -> List[Dict]:
        """Search for polymers by name (case-insensitive). Matches the raw
        spelling and the separator-invariant key, so "y-130", "y 130" and
        "y130" all find the same polymer. Returns one row per polymer with its
        most common display spelling."""
        conn = self._connect()
        cursor = conn.cursor()

        raw_pattern = f"%{search_query.lower()}%"
        # Collapsed pattern matches the normalized key regardless of separators.
        collapsed_pattern = f"%{collapse_separators(search_query.lower())}%"

        cursor.execute('''
            SELECT p.normalized_name,
                   (SELECT d.polymer_name FROM polymer_prices d
                    WHERE d.normalized_name = p.normalized_name
                    GROUP BY d.polymer_name
                    ORDER BY COUNT(*) DESC, d.polymer_name LIMIT 1) AS display_name,
                   MAX(p.date) AS latest_date
            FROM polymer_prices p
            WHERE LOWER(p.polymer_name) LIKE ? OR p.normalized_name LIKE ?
            GROUP BY p.normalized_name
            ORDER BY display_name
            LIMIT 20
        ''', (raw_pattern, collapsed_pattern))

        results = []
        for row in cursor.fetchall():
            results.append({
                'normalized_name': row[0],
                'display_name': row[1],
                'latest_date': row[2]
            })

        conn.close()
        return results

    def get_all_polymers_for_date(self, target_date: datetime) -> List[Dict]:
        """Get all polymers priced on a date — ONE row per polymer (grouped by
        normalized name) with its price range and how many listings it had, so
        the daily view shows each polymer once instead of repeating it for every
        message/source."""
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT p.normalized_name,
                   (SELECT d.polymer_name FROM polymer_prices d
                    WHERE d.normalized_name = p.normalized_name AND d.date = p.date
                    GROUP BY d.polymer_name
                    ORDER BY COUNT(*) DESC, d.polymer_name LIMIT 1) AS display_name,
                   MIN(p.price) AS low, MAX(p.price) AS high, COUNT(*) AS listings,
                   (SELECT d2.message_link FROM polymer_prices d2
                    WHERE d2.normalized_name = p.normalized_name AND d2.date = p.date
                    AND d2.price IS NOT NULL
                    ORDER BY d2.created_at DESC LIMIT 1) AS latest_link
            FROM polymer_prices p
            WHERE p.date = ? AND p.price IS NOT NULL
            GROUP BY p.normalized_name
            ORDER BY display_name
        ''', (target_date.date(),))

        results = []
        for row in cursor.fetchall():
            results.append({
                'polymer_name': row[1],
                'low': row[2],
                'high': row[3],
                'listings': row[4],
                'message_link': row[5],
            })

        conn.close()
        return results

    def get_latest_date_with_data(self) -> Optional[str]:
        """Get the most recent date that has polymer data"""
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT MAX(date) as latest_date
            FROM polymer_prices
            WHERE price IS NOT NULL
        ''')

        row = cursor.fetchone()
        conn.close()

        if row and row[0]:
            return row[0]
        return None

    def delete_old_data(self, retention_days: int = None) -> int:
        """Delete data older than retention_days. Returns number of rows deleted."""
        if retention_days is None:
            retention_days = config.DATA_RETENTION_DAYS
        conn = self._connect()
        cursor = conn.cursor()

        cutoff_date = (datetime.now() - timedelta(days=retention_days)).date()

        # Count rows to be deleted
        cursor.execute(
            'SELECT COUNT(*) FROM polymer_prices WHERE date < ?',
            (cutoff_date,)
        )
        count = cursor.fetchone()[0]

        if count > 0:
            cursor.execute(
                'DELETE FROM polymer_prices WHERE date < ?',
                (cutoff_date,)
            )
            conn.commit()
            print(f"Deleted {count} records older than {cutoff_date}")
        else:
            print(f"No records older than {cutoff_date} to delete")

        conn.close()
        return count

    def get_data_date_range(self) -> Optional[Dict]:
        """Get the date range of data currently in the database"""
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute('''
            SELECT MIN(date) as oldest, MAX(date) as newest, COUNT(*) as total
            FROM polymer_prices
        ''')

        row = cursor.fetchone()
        conn.close()

        if row and row[0]:
            return {
                'oldest_date': row[0],
                'newest_date': row[1],
                'total_records': row[2]
            }
        return None

    def renormalize_existing_data(self) -> Dict:
        """Re-apply the alias canonicalization + normalization to every row
        already in the database.

        Run this once after editing polymer_aliases.txt so that historical rows
        merge under the new canonical names (new data is handled automatically
        on insert; this only backfills what is already stored).

        Only the polymer_name (display) and normalized_name columns are
        touched — prices, dates, links and chat ids are left intact. If
        re-labelling a row would collide with the UNIQUE(normalized_name, date,
        message_link) constraint (i.e. an alias and its original appeared for
        the same message+day), the duplicate is folded into the survivor via
        UPDATE OR REPLACE.

        Returns a summary dict: {'total', 'updated'}.
        """
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute('SELECT id, polymer_name, normalized_name FROM polymer_prices')
        rows = cursor.fetchall()

        updated = 0
        for row_id, polymer_name, normalized_name in rows:
            new_display = clean_display_name(self.normalizer.canonicalize(polymer_name))
            new_norm = self.normalize_polymer_name(polymer_name)

            if new_display == polymer_name and new_norm == normalized_name:
                continue  # nothing to change for this row

            try:
                cursor.execute(
                    'UPDATE OR REPLACE polymer_prices '
                    'SET polymer_name = ?, normalized_name = ? WHERE id = ?',
                    (new_display, new_norm, row_id)
                )
                updated += cursor.rowcount
            except Exception as e:
                print(f"  Skipped row {row_id} ({polymer_name!r}): {e}")

        conn.commit()
        conn.close()
        return {'total': len(rows), 'updated': updated}

    def delete_invalid_entries(self, dry_run: bool = False) -> Dict:
        """Remove rows whose polymer_name is not a real polymer (equipment
        listings, free-text descriptions, bare decimals, vendor-only names).

        Uses the same is_valid_polymer_name() rule the parser applies to new
        data, so this back-cleans junk that was stored before that rule existed.
        With dry_run=True nothing is deleted; the would-be-deleted names are
        still returned for inspection.

        Returns {'deleted', 'names': [(name, count), ...]}.
        """
        conn = self._connect()
        cursor = conn.cursor()

        cursor.execute('SELECT polymer_name, COUNT(*) FROM polymer_prices GROUP BY polymer_name')
        invalid = [(name, cnt) for name, cnt in cursor.fetchall()
                   if not is_valid_polymer_name(name)]

        deleted = 0
        if invalid and not dry_run:
            for name, _cnt in invalid:
                cursor.execute('DELETE FROM polymer_prices WHERE polymer_name = ?', (name,))
                deleted += cursor.rowcount
            conn.commit()

        conn.close()
        return {'deleted': deleted, 'names': invalid}
