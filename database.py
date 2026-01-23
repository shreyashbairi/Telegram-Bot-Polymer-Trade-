"""
Database module for storing and retrieving polymer price data
"""
import sqlite3
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import config

class PolymerDatabase:
    def __init__(self, db_path: str = None):
        """Initialize database connection"""
        self.db_path = db_path or config.DATABASE_PATH
        self.init_database()

    def init_database(self):
        """Create database tables if they don't exist"""
        conn = sqlite3.connect(self.db_path)
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
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(normalized_name, date, message_link)
            )
        ''')

        # Index for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_normalized_name
            ON polymer_prices(normalized_name)
        ''')

        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_date
            ON polymer_prices(date)
        ''')

        conn.commit()
        conn.close()

    def normalize_polymer_name(self, name: str) -> str:
        """Normalize polymer name for consistent matching"""
        # Remove emojis, extra spaces, and convert to lowercase
        normalized = name.strip().lower()
        # Remove common prefixes and suffixes
        normalized = normalized.replace('uz-kor gas', '').replace('uzkorgas', '')
        normalized = normalized.replace('shurtan', '').replace('iran', '')
        normalized = ' '.join(normalized.split())
        return normalized.strip()

    def insert_price(self, polymer_name: str, price: Optional[float],
                    status: str, date: datetime, message_text: str,
                    message_link: str) -> bool:
        """Insert a polymer price record"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            normalized_name = self.normalize_polymer_name(polymer_name)

            cursor.execute('''
                INSERT OR REPLACE INTO polymer_prices
                (polymer_name, normalized_name, price, status, date, message_text, message_link)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (polymer_name, normalized_name, price, status, date.date(),
                  message_text, message_link))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Error inserting price: {e}")
            return False

    def get_polymer_history(self, polymer_name: str, days: int = 7) -> List[Dict]:
        """Get price history for a polymer for the last N days"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        normalized_name = self.normalize_polymer_name(polymer_name)
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)

        cursor.execute('''
            SELECT polymer_name, price, status, date, message_text, message_link
            FROM polymer_prices
            WHERE normalized_name = ?
            AND date BETWEEN ? AND ?
            ORDER BY date DESC
        ''', (normalized_name, start_date, end_date))

        results = []
        for row in cursor.fetchall():
            results.append({
                'polymer_name': row[0],
                'price': row[1],
                'status': row[2],
                'date': row[3],
                'message_text': row[4],
                'message_link': row[5]
            })

        conn.close()
        return results

    def get_price_on_date(self, polymer_name: str, target_date: datetime) -> Optional[Dict]:
        """Get price for a specific date"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        normalized_name = self.normalize_polymer_name(polymer_name)

        cursor.execute('''
            SELECT polymer_name, price, status, date, message_text, message_link
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
                'message_link': row[5]
            }
        return None

    def get_latest_price(self, polymer_name: str) -> Optional[Dict]:
        """Get the most recent price for a polymer"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        normalized_name = self.normalize_polymer_name(polymer_name)

        cursor.execute('''
            SELECT polymer_name, price, status, date, message_text, message_link
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
                'message_link': row[5]
            }
        return None

    def get_price_stats_for_date(self, polymer_name: str, target_date: datetime) -> Optional[Dict]:
        """Get price statistics (min, max, mean) for a polymer on a specific date"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        normalized_name = self.normalize_polymer_name(polymer_name)

        # Get all prices for this polymer on this date
        cursor.execute('''
            SELECT price, message_link
            FROM polymer_prices
            WHERE normalized_name = ?
            AND date = ?
            AND price IS NOT NULL
            ORDER BY price ASC
        ''', (normalized_name, target_date.date()))

        rows = cursor.fetchall()
        conn.close()

        if not rows:
            return None

        prices = [row[0] for row in rows]

        # Find lowest and highest with their links
        lowest_price = min(prices)
        highest_price = max(prices)

        # Get the message links for lowest and highest
        lowest_link = None
        highest_link = None

        for row in rows:
            if row[0] == lowest_price and not lowest_link:
                lowest_link = row[1]
            if row[0] == highest_price:
                highest_link = row[1]

        # Calculate mean as (highest + lowest) / 2
        mean_price = (highest_price + lowest_price) / 2

        return {
            'lowest': lowest_price,
            'highest': highest_price,
            'mean': mean_price,
            'lowest_link': lowest_link,
            'highest_link': highest_link,
            'count': len(prices)
        }

    def get_all_polymers(self) -> List[str]:
        """Get list of all unique polymer names"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT DISTINCT polymer_name
            FROM polymer_prices
            ORDER BY polymer_name
        ''')

        polymers = [row[0] for row in cursor.fetchall()]
        conn.close()
        return polymers

    def get_unique_polymers_with_latest_date(self) -> List[Dict]:
        """Get unique polymers with their most recent dates"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT DISTINCT normalized_name, polymer_name, MAX(date) as latest_date
            FROM polymer_prices
            GROUP BY normalized_name
            ORDER BY polymer_name
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
        """Search for polymers by name (case-insensitive)"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Search in both polymer_name and normalized_name
        search_pattern = f"%{search_query.lower()}%"

        cursor.execute('''
            SELECT DISTINCT normalized_name, polymer_name, MAX(date) as latest_date
            FROM polymer_prices
            WHERE LOWER(polymer_name) LIKE ? OR LOWER(normalized_name) LIKE ?
            GROUP BY normalized_name
            ORDER BY polymer_name
            LIMIT 20
        ''', (search_pattern, search_pattern))

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
        """Get all polymers with prices for a specific date"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT polymer_name, price, status, message_link, created_at
            FROM polymer_prices
            WHERE date = ?
            AND price IS NOT NULL
            ORDER BY polymer_name, created_at
        ''', (target_date.date(),))

        results = []
        for row in cursor.fetchall():
            results.append({
                'polymer_name': row[0],
                'price': row[1],
                'status': row[2],
                'message_link': row[3],
                'created_at': row[4]
            })

        conn.close()
        return results

    def get_latest_date_with_data(self) -> Optional[str]:
        """Get the most recent date that has polymer data"""
        conn = sqlite3.connect(self.db_path)
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

    def get_price_range_for_polymer(self, polymer_name: str, days: int = 7) -> Optional[Dict]:
        """Get the highest and lowest prices for a polymer over the last N days"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        normalized_name = self.normalize_polymer_name(polymer_name)
        end_date = datetime.now().date()
        start_date = end_date - timedelta(days=days)

        cursor.execute('''
            SELECT MIN(price) as lowest, MAX(price) as highest
            FROM polymer_prices
            WHERE normalized_name = ?
            AND date BETWEEN ? AND ?
            AND price IS NOT NULL
        ''', (normalized_name, start_date, end_date))

        row = cursor.fetchone()
        conn.close()

        if row and row[0] and row[1]:
            return {
                'lowest': row[0],
                'highest': row[1]
            }
        return None
