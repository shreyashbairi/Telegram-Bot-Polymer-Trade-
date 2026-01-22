"""
Message parser using OpenAI to extract polymer prices from unstructured text
"""
import json
import re
from typing import List, Dict
from openai import OpenAI
import config

class PolymerParser:
    def __init__(self):
        """Initialize OpenAI client"""
        self.client = OpenAI(
            api_key=config.OPENAI_API_KEY,
            organization=config.OPENAI_ORG_ID
        )

    def parse_message(self, message_text: str) -> List[Dict]:
        """
        Parse a message to extract polymer names and prices
        Returns a list of dictionaries with polymer_name, price, and status
        """
        # First try simple regex parsing
        simple_results = self._simple_parse(message_text)

        # If simple parsing gives good results, return them
        if simple_results and len(simple_results) > 3:
            return simple_results

        # Otherwise, use OpenAI for complex parsing
        return self._openai_parse(message_text)

    def _simple_parse(self, message_text: str) -> List[Dict]:
        """Simple regex-based parsing for well-formatted messages"""
        results = []

        # Pattern to match polymer name and price (only numeric prices, not BOR)
        # Examples: "J150 14.900", "🐫 Uz-Kor Gas J 150 14.900"
        patterns = [
            r'🇺🇿\s*([A-Za-z0-9\s\-]+?)\s+(\d{4,}(?:\.\d+)?)',  # Uzbekistan flag format
            r'🇮🇷\s*([A-Za-z0-9\s\-]+?)\s+(\d{4,}(?:\.\d+)?)',  # Iran flag format
            r'🇷🇺\s*([A-Za-z0-9\s\-]+?)\s+(\d{4,}(?:\.\d+)?)',  # Russia flag format
            r'🐫\s*([A-Za-z\s\-]+?)\s+([A-Z]+\s*\d+)\s+(\d{4,}(?:\.\d+)?)',  # Camel emoji format
            r'([A-Za-z][A-Za-z0-9\s\-]{2,40}?)\s+(\d{4,}(?:\.\d+)?)\s*(?:сумм|$|\n)',  # Generic name + price
            r'([A-Z][a-z]+\s+[A-Z0-9]+)\s+(\d{4,}(?:\.\d+)?)',  # "Shurtan 0754" format
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, message_text, re.MULTILINE | re.IGNORECASE)
            for match in matches:
                groups = match.groups()

                if len(groups) >= 2:
                    # Extract name and price
                    if len(groups) == 3:
                        # Format: emoji + prefix + code + price
                        name = f"{groups[0].strip()} {groups[1].strip()}"
                        price_str = groups[2].strip()
                    else:
                        name = groups[0].strip()
                        price_str = groups[1].strip()

                    # Clean up the name
                    name = name.replace('🇺🇿', '').replace('🇮🇷', '').replace('🇷🇺', '').replace('🐫', '').strip()
                    name = ' '.join(name.split())

                    # Skip if name is too short or looks like garbage
                    if len(name) < 2 or name.isdigit():
                        continue

                    # Only accept numeric prices (4+ digits for valid prices like 14500, 15.800, etc.)
                    try:
                        price = float(price_str.replace(',', '.'))
                        # Only store if price is realistic (> 1000)
                        if price > 1000:
                            results.append({
                                'polymer_name': name,
                                'price': price,
                                'status': 'PRICED'
                            })
                    except ValueError:
                        continue

        # Remove duplicates while preserving order
        seen = set()
        unique_results = []
        for item in results:
            key = item['polymer_name'].lower()
            if key not in seen:
                seen.add(key)
                unique_results.append(item)

        return unique_results

    def _openai_parse(self, message_text: str) -> List[Dict]:
        """Use OpenAI to parse complex messages"""
        try:
            prompt = f"""
You are a data extraction expert. Extract polymer names and their NUMERIC prices from the following message.
The message is from a Telegram group where traders post polymer prices.

CRITICAL RULES:
1. ONLY extract polymers that have actual numeric prices (like 14900, 15.800, 16700)
2. IGNORE polymers with "BOR", "AVAILABLE", or no price
3. IGNORE polymers with empty prices or status-only entries
4. Prices can be in format: 14.900, 14900, 14,900
5. Common polymer codes: J150, J160, J350, FR170, Y130, 0120, 0220, BL3, PE100, Shurtan, Uz-Kor Gas, etc.
6. Ignore phone numbers, dates, and contact information
7. Return ONLY valid JSON array format

Message:
{message_text}

Return a JSON array of objects with this format (ONLY include entries with numeric prices):
[
  {{"polymer_name": "Uz-Kor Gas J150", "price": 14900}},
  {{"polymer_name": "Shurtan By456", "price": 15400}}
]

If no polymers with prices found, return an empty array: []
"""

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a data extraction expert. Extract ONLY polymers with numeric prices. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.1,
                max_tokens=2000
            )

            result_text = response.choices[0].message.content.strip()

            # Extract JSON from response (in case there's extra text)
            json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
            if json_match:
                result_text = json_match.group(0)

            parsed_data = json.loads(result_text)

            # Validate and clean the data - ONLY include items with numeric prices
            validated_results = []
            for item in parsed_data:
                if 'polymer_name' in item and item['polymer_name'] and item.get('price'):
                    try:
                        price = float(item.get('price'))
                        # Only include if price is realistic (> 1000)
                        if price > 1000:
                            validated_results.append({
                                'polymer_name': item.get('polymer_name', '').strip(),
                                'price': price,
                                'status': 'PRICED'
                            })
                    except (ValueError, TypeError):
                        continue

            return validated_results

        except Exception as e:
            print(f"Error parsing with OpenAI: {e}")
            # Fall back to simple parsing
            return []

    def extract_date_from_message(self, message_text: str) -> str:
        """Extract date from message if present"""
        # Pattern for dates like "19.01.2026" or "1️⃣9️⃣.0️⃣1️⃣.2️⃣0️⃣2️⃣6️⃣"
        date_patterns = [
            r'(\d{1,2})\.(\d{1,2})\.(\d{4})',
            r'(\d)️⃣(\d)️⃣\.(\d)️⃣(\d)️⃣\.(\d)️⃣(\d)️⃣(\d)️⃣(\d)️⃣'
        ]

        for pattern in date_patterns:
            match = re.search(pattern, message_text)
            if match:
                return match.group(0)

        return None
