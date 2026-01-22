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
                message_id INTEGER,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(normalized_name, date, message_id)
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
                    message_id: int) -> bool:
        """Insert a polymer price record"""
        try:
            conn = sqlite3.connect(self.db_path)
            cursor = conn.cursor()

            normalized_name = self.normalize_polymer_name(polymer_name)

            cursor.execute('''
                INSERT OR REPLACE INTO polymer_prices
                (polymer_name, normalized_name, price, status, date, message_text, message_id)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', (polymer_name, normalized_name, price, status, date.date(),
                  message_text, message_id))

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
            SELECT polymer_name, price, status, date, message_text
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
                'message_text': row[4]
            })

        conn.close()
        return results

    def get_price_on_date(self, polymer_name: str, target_date: datetime) -> Optional[Dict]:
        """Get price for a specific date"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        normalized_name = self.normalize_polymer_name(polymer_name)

        cursor.execute('''
            SELECT polymer_name, price, status, date, message_text
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
                'message_text': row[4]
            }
        return None

    def get_latest_price(self, polymer_name: str) -> Optional[Dict]:
        """Get the most recent price for a polymer"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        normalized_name = self.normalize_polymer_name(polymer_name)

        cursor.execute('''
            SELECT polymer_name, price, status, date, message_text
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
                'message_text': row[4]
            }
        return None

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
