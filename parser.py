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
        """Simple regex-based parsing for well-formatted messages with STRICT validation"""
        results = []

        # STRICT patterns to match polymer name and price
        # Key requirements:
        # 1. Price must be 5+ digits (10000+) to avoid matching polymer codes
        # 2. Clear separation between name and price (multiple spaces, tabs, or newlines)
        # 3. Price should NOT be part of the polymer name

        patterns = [
            # Multiple spaces between name and price (most common in formatted messages)
            # Example: "Shurtan By456                15400"
            r'([A-Za-z][A-Za-z\s\-]+[A-Za-z0-9]+)\s{2,}(\d{5}(?:[.,]\d+)?)',

            # Tab or newline separated
            r'([A-Za-z][A-Za-z\s\-]+[A-Za-z0-9]+)[\t\n]+(\d{5}(?:[.,]\d+)?)',

            # With country flags
            r'🇺🇿\s*([A-Za-z][A-Za-z\s\-]+[A-Za-z0-9]+)\s+(\d{5}(?:[.,]\d+)?)',
            r'🇮🇷\s*([A-Za-z][A-Za-z\s\-]+[A-Za-z0-9]+)\s+(\d{5}(?:[.,]\d+)?)',
            r'🇷🇺\s*([A-Za-z][A-Za-z\s\-]+[A-Za-z0-9]+)\s+(\d{5}(?:[.,]\d+)?)',

            # With explicit price indicators
            r'([A-Za-z][A-Za-z\s\-]+[A-Za-z0-9]+)\s+(\d{5}(?:[.,]\d+)?)\s*(?:сумм|sum)',
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, message_text, re.MULTILINE)
            for match in matches:
                try:
                    groups = match.groups()
                    if len(groups) < 2:
                        continue

                    name = groups[0].strip()
                    price_str = groups[1].strip()

                    # Clean up the name - remove flags and extra spaces
                    name = name.replace('🇺🇿', '').replace('🇮🇷', '').replace('🇷🇺', '').replace('🐫', '').strip()
                    name = ' '.join(name.split())

                    # Validation: ensure name is reasonable
                    if len(name) < 3 or name.isdigit():
                        continue

                    # CRITICAL CHECK: Ensure the price is NOT part of the polymer name
                    # This prevents "Uz-Kor Gas Jm370" from being parsed as price 370
                    # or "BL5200" from being parsed as price 5200

                    name_parts = name.split()
                    last_part = name_parts[-1] if name_parts else ""

                    # If the last part of the name contains digits, check for false matches
                    if last_part and any(char.isdigit() for char in last_part):
                        # Extract all digits from the last part of the name
                        digits_in_name = ''.join(c for c in last_part if c.isdigit())

                        # If the price matches the digits in the name, it's a false match - skip it
                        # Examples that will be rejected:
                        # - "Jm370" with price "370" or "3700"
                        # - "BL5200" with price "5200"
                        # - "1561" with price "1561"
                        if digits_in_name == price_str or price_str.startswith(digits_in_name):
                            continue
                        if price_str == digits_in_name or digits_in_name.startswith(price_str):
                            continue

                    # Parse and validate price
                    price = float(price_str.replace(',', '.'))

                    # STRICT: Only accept realistic polymer prices >= 10000
                    # Polymer prices typically range from 14000 to 20000
                    # This prevents matching small numbers that are polymer codes
                    if price >= 10000:
                        results.append({
                            'polymer_name': name,
                            'price': price,
                            'status': 'PRICED'
                        })

                except (ValueError, IndexError):
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
        """Use OpenAI GPT-4 to parse complex messages with strict validation"""
        try:
            prompt = f"""
You are a data extraction expert. Extract polymer names and their NUMERIC prices from the following message.
The message is from a Telegram group where traders post polymer prices.

CRITICAL RULES - FOLLOW THESE EXACTLY:
1. ONLY extract polymers that have EXPLICIT numeric prices shown in the message
2. IGNORE polymers with "BOR", "AVAILABLE", "🔥", or any status symbols
3. IGNORE polymers where no price is shown
4. Prices are typically 5-digit numbers: 14000-20000 range (e.g., 14900, 15800, 16700)
5. DO NOT extract the number from the polymer name as the price
   - Example: "Uz-Kor Gas Jm370" does NOT have a price (370 is part of the name)
   - Example: "BL5200" does NOT have a price (5200 is part of the name)
   - Example: "Shurtan 1561" does NOT have a price (1561 is part of the name)
6. Common polymer names include numbers: J150, J370, BL5200, 1561, etc. - these are NOT prices
7. Ignore phone numbers (starting with +998, etc.), dates, and contact information
8. Return ONLY valid JSON array format

Examples of VALID entries (polymer WITH explicit price):
- "Uz-Kor Gas J150              14900" → VALID (price 14900 is separate)
- "Shurtan By456                15400" → VALID (price 15400 is separate)
- "🇺🇿 Uz-Kor Gas Jm370       17600" → VALID (price 17600 is separate)

Examples of INVALID entries (NO price or price is part of name):
- "Uz-Kor Gas J150🔥🔥" → INVALID (no price, only status symbol)
- "Uz-Kor Gas Jm370" → INVALID (370 is part of name, not a price)
- "BL5200 UzKorGas" → INVALID (5200 is part of name, not a price)
- "Shurtan 1561" → INVALID (1561 is part of name, not a price)

Message:
{message_text}

Return a JSON array with ONLY entries that have explicit numeric prices >= 10000:
[
  {{"polymer_name": "Uz-Kor Gas J150", "price": 14900}},
  {{"polymer_name": "Shurtan By456", "price": 15400}}
]

If no polymers with explicit prices found, return an empty array: []
"""

            # Use GPT-4 for better accuracy
            response = self.client.chat.completions.create(
                model="o3-mini",
                messages=[
                    {"role": "system", "content": "You are a data extraction expert. Extract ONLY polymers with explicit numeric prices >= 10000. Numbers that are part of polymer names are NOT prices. Return only valid JSON."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.0,  # Use 0 for deterministic results
                max_tokens=2000
            )

            result_text = response.choices[0].message.content.strip()

            # Extract JSON from response (in case there's extra text)
            json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
            if json_match:
                result_text = json_match.group(0)

            parsed_data = json.loads(result_text)

            # Validate and clean the data - ONLY include items with realistic prices
            validated_results = []
            for item in parsed_data:
                if 'polymer_name' in item and item['polymer_name'] and item.get('price'):
                    try:
                        price = float(item.get('price'))

                        # Strict validation: price must be >= 10000
                        if price >= 10000:
                            polymer_name = item.get('polymer_name', '').strip()

                            # Double-check: ensure price is not derived from polymer name
                            name_parts = polymer_name.split()
                            last_part = name_parts[-1] if name_parts else ""

                            # Extract digits from last part of name
                            if last_part and any(c.isdigit() for c in last_part):
                                digits_in_name = ''.join(c for c in last_part if c.isdigit())
                                price_str = str(int(price))

                                # Skip if price matches digits in name
                                if digits_in_name == price_str or price_str.startswith(digits_in_name) or digits_in_name.startswith(price_str):
                                    continue

                            validated_results.append({
                                'polymer_name': polymer_name,
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
