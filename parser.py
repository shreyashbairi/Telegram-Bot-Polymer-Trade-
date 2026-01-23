"""
Message parser using OpenAI to extract polymer prices from unstructured text
"""
import json
import re
import time
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

    def _remove_emojis(self, text: str) -> str:
        """
        Remove emojis and other non-standard Unicode characters from text
        Examples:
        - "0209 🔴 AKPC" -> "0209 AKPC"
        - "0209 🔴Amir Kabir" -> "0209 Amir Kabir"
        - "0209 🔵" -> "0209"
        - "0209 🔴 Iran" -> "0209 Iran"
        """
        # Define emoji pattern - matches most common emojis
        emoji_pattern = re.compile(
            "["
            "\U0001F1E0-\U0001F1FF"  # flags (iOS)
            "\U0001F300-\U0001F5FF"  # symbols & pictographs
            "\U0001F600-\U0001F64F"  # emoticons
            "\U0001F680-\U0001F6FF"  # transport & map symbols
            "\U0001F700-\U0001F77F"  # alchemical symbols
            "\U0001F780-\U0001F7FF"  # Geometric Shapes Extended
            "\U0001F800-\U0001F8FF"  # Supplemental Arrows-C
            "\U0001F900-\U0001F9FF"  # Supplemental Symbols and Pictographs
            "\U0001FA00-\U0001FA6F"  # Chess Symbols
            "\U0001FA70-\U0001FAFF"  # Symbols and Pictographs Extended-A
            "\U00002702-\U000027B0"  # Dingbats
            "\U000024C2-\U0001F251"
            "\U0001f926-\U0001f937"
            "\U00010000-\U0010ffff"
            "\u2640-\u2642"
            "\u2600-\u2B55"
            "\u200d"
            "\u23cf"
            "\u23e9"
            "\u231a"
            "\ufe0f"  # dingbats
            "\u3030"
            "]+",
            re.UNICODE
        )

        # Remove emojis
        text = emoji_pattern.sub('', text)

        # Clean up extra spaces
        text = ' '.join(text.split())

        return text.strip()

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
            # With emoji indicators (🔴, 🔵) followed by polymer name
            # Example: "0209 🔴 AKPC              14900" or "0209 🔵              14900"
            r'([A-Za-z0-9][A-Za-z0-9\s\-🔴🔵🟢🟡🟠🟣🟤⚪⚫]+[A-Za-z0-9]*)\s{2,}(\d{5}(?:[.,]\d+)?)',

            # Multiple spaces between name and price (most common in formatted messages)
            # Example: "Shurtan By456                15400"
            r'([A-Za-z][A-Za-z\s\-]+[A-Za-z0-9]+)\s{2,}(\d{5}(?:[.,]\d+)?)',

            # Tab or newline separated
            r'([A-Za-z0-9][A-Za-z0-9\s\-🔴🔵🟢🟡🟠🟣🟤⚪⚫]+[A-Za-z0-9]*)[\t\n]+(\d{5}(?:[.,]\d+)?)',

            # With country flags
            r'🇺🇿\s*([A-Za-z0-9][A-Za-z0-9\s\-🔴🔵🟢🟡🟠🟣🟤⚪⚫]+[A-Za-z0-9]*)\s+(\d{5}(?:[.,]\d+)?)',
            r'🇮🇷\s*([A-Za-z0-9][A-Za-z0-9\s\-🔴🔵🟢🟡🟠🟣🟤⚪⚫]+[A-Za-z0-9]*)\s+(\d{5}(?:[.,]\d+)?)',
            r'🇷🇺\s*([A-Za-z0-9][A-Za-z0-9\s\-🔴🔵🟢🟡🟠🟣🟤⚪⚫]+[A-Za-z0-9]*)\s+(\d{5}(?:[.,]\d+)?)',

            # With explicit price indicators
            r'([A-Za-z0-9][A-Za-z0-9\s\-🔴🔵🟢🟡🟠🟣🟤⚪⚫]+[A-Za-z0-9]*)\s+(\d{5}(?:[.,]\d+)?)\s*(?:сумм|sum)',
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

                    # Clean up the name - remove ALL emojis (including 🔴, 🔵, flags, etc.)
                    name = self._remove_emojis(name)
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
        """Use OpenAI GPT-4o-mini to parse complex messages with strict validation and retry logic"""
        max_retries = 3
        retry_delay = 2  # Start with 2 seconds

        for attempt in range(max_retries):
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
7. REMOVE ALL EMOJIS from polymer names (🔴, 🔵, 🟢, etc.) before returning
   - Example: "0209 🔴 AKPC" → return as "0209 AKPC"
   - Example: "0209 🔴Amir Kabir" → return as "0209 Amir Kabir"
   - Example: "0209 🔵" → return as "0209"
8. Ignore phone numbers (starting with +998, etc.), dates, and contact information
9. Return ONLY valid JSON array format

Examples of VALID entries (polymer WITH explicit price, emojis removed):
- "Uz-Kor Gas J150              14900" → {{"polymer_name": "Uz-Kor Gas J150", "price": 14900}}
- "Shurtan By456                15400" → {{"polymer_name": "Shurtan By456", "price": 15400}}
- "🇺🇿 Uz-Kor Gas Jm370       17600" → {{"polymer_name": "Uz-Kor Gas Jm370", "price": 17600}}
- "0209 🔴 AKPC                 14900" → {{"polymer_name": "0209 AKPC", "price": 14900}}
- "0209 🔴Amir Kabir            15400" → {{"polymer_name": "0209 Amir Kabir", "price": 15400}}
- "0209 🔵                      16800" → {{"polymer_name": "0209", "price": 16800}}

Examples of INVALID entries (NO price or price is part of name):
- "Uz-Kor Gas J150🔥🔥" → INVALID (no price, only status symbol)
- "Uz-Kor Gas Jm370" → INVALID (370 is part of name, not a price)
- "BL5200 UzKorGas" → INVALID (5200 is part of name, not a price)
- "Shurtan 1561" → INVALID (1561 is part of name, not a price)

Message:
{message_text}

Return a JSON array with ONLY entries that have explicit numeric prices >= 10000.
IMPORTANT: Remove ALL emojis from polymer names:
[
  {{"polymer_name": "Uz-Kor Gas J150", "price": 14900}},
  {{"polymer_name": "0209 AKPC", "price": 14900}}
]

If no polymers with explicit prices found, return an empty array: []
"""

                # Use GPT-4o-mini: Much cheaper (~60x) and faster than GPT-4, still accurate
                # Pricing: $0.150 per 1M input tokens vs $10 per 1M for GPT-4
                response = self.client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {"role": "system", "content": "You are a data extraction expert. Extract ONLY polymers with explicit numeric prices >= 10000. Numbers that are part of polymer names are NOT prices. Return only valid JSON."},
                        {"role": "user", "content": prompt}
                    ],
                    temperature=0.0,  # Use 0 for deterministic results
                    max_tokens=1500  # Reduced token limit to save costs
                )

                result_text = response.choices[0].message.content.strip()

                # Validate that we got a response
                if not result_text:
                    print("OpenAI returned empty response")
                    return []

                # Extract JSON from response (in case there's extra text)
                json_match = re.search(r'\[.*\]', result_text, re.DOTALL)
                if json_match:
                    result_text = json_match.group(0)
                else:
                    # No JSON array found, check if it's just an empty response
                    if 'no polymers' in result_text.lower() or 'empty array' in result_text.lower():
                        return []
                    print(f"No JSON array found in OpenAI response: {result_text[:200]}")
                    return []

                # Parse JSON
                try:
                    parsed_data = json.loads(result_text)
                except json.JSONDecodeError as je:
                    print(f"JSON decode error: {je}")
                    print(f"Response text: {result_text[:500]}")
                    return []

                # Validate and clean the data - ONLY include items with realistic prices
                validated_results = []
                for item in parsed_data:
                    if 'polymer_name' in item and item['polymer_name'] and item.get('price'):
                        try:
                            price = float(item.get('price'))

                            # Strict validation: price must be >= 10000
                            if price >= 10000:
                                polymer_name = item.get('polymer_name', '').strip()

                                # Clean emojis from polymer name
                                polymer_name = self._remove_emojis(polymer_name)

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
                error_msg = str(e)

                # Check if it's a rate limit error
                if '429' in error_msg or 'rate_limit' in error_msg.lower():
                    if attempt < max_retries - 1:
                        wait_time = retry_delay * (2 ** attempt)  # Exponential backoff
                        print(f"Rate limit hit, waiting {wait_time} seconds before retry {attempt + 1}/{max_retries}...")
                        time.sleep(wait_time)
                        continue
                    else:
                        print(f"Rate limit exceeded after {max_retries} retries: {e}")
                        return []
                else:
                    # Other errors, don't retry
                    print(f"Error parsing with OpenAI: {e}")
                    return []

        # If we exhausted all retries
        print("Max retries exceeded for OpenAI parsing")
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
