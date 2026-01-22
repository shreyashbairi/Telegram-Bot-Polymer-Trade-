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

        # Pattern to match polymer name and price/status
        # Examples: "J150 14.900", "J150 BOR", "🐫 Uz-Kor Gas J 150 14.900"
        patterns = [
            r'([A-Za-z0-9🐫\s\-]+?)\s+(\d+\.?\d*)\s*(?:сумм|$)',  # Name followed by price
            r'([A-Za-z0-9🐫\s\-]+?)\s+(BOR|bor)(?:\s|🔥|$)',  # Name followed by BOR
            r'🐫\s*([A-Za-z\s\-]+?)\s+([A-Z]+\s*\d+)\s+(\d+\.?\d*)',  # Camel emoji format
            r'([A-Z]+\d+)\s*[.\s]+\s*(BOR|bor|\d+\.?\d*)',  # Compact format like "J150 BOR"
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, message_text, re.MULTILINE | re.IGNORECASE)
            for match in matches:
                groups = match.groups()

                if len(groups) >= 2:
                    # Extract name and price/status
                    if len(groups) == 3:
                        # Format: prefix name code price
                        name = f"{groups[0].strip()} {groups[1].strip()}"
                        price_or_status = groups[2].strip()
                    else:
                        name = groups[0].strip()
                        price_or_status = groups[1].strip()

                    # Clean up the name
                    name = name.replace('🐫', '').strip()
                    name = ' '.join(name.split())

                    # Skip if name is too short or looks like garbage
                    if len(name) < 2 or name.isdigit():
                        continue

                    # Determine if it's a price or status
                    if price_or_status.upper() == 'BOR':
                        results.append({
                            'polymer_name': name,
                            'price': None,
                            'status': 'AVAILABLE'
                        })
                    else:
                        try:
                            price = float(price_or_status.replace(',', '.'))
                            results.append({
                                'polymer_name': name,
                                'price': price,
                                'status': 'AVAILABLE'
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
You are a data extraction expert. Extract polymer names and their prices from the following message.
The message is from a Telegram group where traders post polymer prices.

Rules:
1. Extract each polymer name and its associated price or status
2. If a polymer shows "BOR" or "bor", it means "AVAILABLE" (no specific price)
3. Prices can be in format: 14.900, 14900, 14,900
4. Common polymer codes: J150, J160, J350, FR170, Y130, 0120, 0220, BL3, PE100, etc.
5. Ignore phone numbers, dates, and contact information
6. Return ONLY valid JSON array format

Message:
{message_text}

Return a JSON array of objects with this format:
[
  {{"polymer_name": "J150", "price": 14900, "status": "AVAILABLE"}},
  {{"polymer_name": "Y130", "price": null, "status": "AVAILABLE"}}
]

If no polymers found, return an empty array: []
"""

            response = self.client.chat.completions.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a data extraction expert. Return only valid JSON."},
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

            # Validate and clean the data
            validated_results = []
            for item in parsed_data:
                if 'polymer_name' in item and item['polymer_name']:
                    validated_results.append({
                        'polymer_name': item.get('polymer_name', '').strip(),
                        'price': item.get('price'),
                        'status': item.get('status', 'AVAILABLE')
                    })

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
