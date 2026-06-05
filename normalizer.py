"""
Polymer name normalization via a human-editable alias file.

The alias file (default: ``polymer_aliases.txt``) lets a person declare that
several spellings of a polymer are the same product. Any price posted under an
"alternative name" is then stored and displayed under the canonical "original
name" -- e.g. "J2210", "j-2210" and "Uz-Kor Gas J-2210" all collapse to
"J-2210".

The file is re-read automatically when it changes on disk (checked cheaply via
mtime), so edits take effect for NEW data without restarting the bot or
scraper. To relabel rows already in the database, run ``apply_normalization.py``.

See ``polymer_aliases.txt`` for the file format.
"""
import os
import re

import config

# Emoji / pictograph stripper -- shared with the matching logic so a name like
# "Uz-Kor Gas J-2210 <red-circle>" still matches the alias "Uz-Kor Gas J-2210".
# (Kept in sync with the pattern used in database.py / parser.py.)
_EMOJI_RE = re.compile(
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
    "♀-♂"
    "☀-⭕"
    "‍"
    "⏏"
    "⏩"
    "⌚"
    "️"
    "〰"
    "]+",
    re.UNICODE,
)


def strip_emojis(text: str) -> str:
    """Remove emojis / pictographs / flags from a name."""
    return _EMOJI_RE.sub('', text or '')


def collapse_separators(text: str) -> str:
    """Remove spaces and hyphens so that separator-only spelling differences
    collapse to one key: "Y-130", "Y 130" and "Y130" all become "y130".
    This is what makes a polymer's normalized key separator-invariant."""
    return re.sub(r'[\s\-]+', '', text)


# Producer / origin words that are not, by themselves, a polymer grade. Stored
# in separator-collapsed lower-case form so they can be stripped from a name
# regardless of how the vendor was spaced or hyphenated ("Uz-Kor Gas",
# "uz kor gas", "UzKorGas", "Uzkor" all collapse before stripping). Order
# matters: longer forms first so "uzkorgas" is removed before bare "uzkor".
VENDOR_WORDS = ('uzkorgas', 'uzkorgaz', 'uzkor', 'shurtan', 'iran')


def structural_key(name: str) -> str:
    """The separator/vendor-invariant identity of a polymer name: emoji-free,
    lower-cased, with spaces+hyphens collapsed and vendor words removed.
    "Uz-Kor Gas J-550", "uzkor j550" and "J550" all map to "j550"."""
    s = strip_emojis(name or '').strip().rstrip('.').lower()
    s = collapse_separators(s)
    for vendor in VENDOR_WORDS:
        s = s.replace(vendor, '')
    return s


# Vendor/origin words as they appear in a *display* name (separators kept), so
# they can be stripped while preserving the grade code's casing and hyphens.
# Longer phrases first. Bounded so "uzkor" inside a larger token is left alone.
# "ga[sz]" tolerates the "Uz-Kor Gaz" spelling; the boundaries forbid only an
# adjacent LETTER (digits are allowed) so a vendor glued to a code like
# "Y-130UzKor-Gas" is still stripped.
_VENDOR_DISPLAY_RE = re.compile(
    r'(?<![A-Za-zА-Яа-я])'
    r'(?:uz[\s\-]*kor[\s\-]*ga[sz]|uzkorga[sz]|uz[\s\-]*kor|uzkor|shurtan|iran)'
    r'(?![A-Za-zА-Яа-я])',
    re.IGNORECASE,
)


def clean_display_name(name: str) -> str:
    """Human-readable display name with vendor/origin words removed but the
    grade code's original casing and separators preserved:
    "Uz-Kor Gas J-550" -> "J-550", "Shurtan 0120" -> "0120". Never returns
    empty — falls back to the trimmed original if stripping removed everything."""
    s = strip_emojis(name or '').strip().rstrip('.')
    s = _VENDOR_DISPLAY_RE.sub(' ', s)
    s = ' '.join(s.split()).strip(' -')
    return s if s else (name or '').strip()

# Substrings that mark a listing as machinery or a free-text advert rather than
# a polymer grade (these groups also sell extruders, granulators, moulds...).
# Matched case-insensitively anywhere in the name. Both common (mis)spellings
# are listed. Extend this tuple if new equipment/advert wording shows up.
NON_POLYMER_TERMS = (
    # machinery
    'термопласт', 'гранул', 'грянул', 'экструдер', 'шредир', 'шредер',
    'драбилка', 'дробилка', 'пресформ', 'формалар',
    # advert / offer wording
    'сотилади', 'таклиф', 'заказга', 'отходан', 'деталар',
)


def _match_key(name: str) -> str:
    """Reduce a name to a comparison key: emoji-stripped, lower-cased, with
    trailing dots and redundant whitespace removed. Two names with the same
    match key are considered the same spelling for alias purposes."""
    s = strip_emojis(name)
    s = s.strip().rstrip('.').strip()
    s = s.lower()
    s = ' '.join(s.split())
    return s


def is_valid_polymer_name(name: str) -> bool:
    """Return False for obvious non-polymer entries so they never reach the
    database. High-precision by design — it only rejects patterns that are
    clearly not a polymer grade, to avoid dropping real (if unusual) products
    such as "25% TiO2" or "15% HALS-783" masterbatches.

    Rejects:
      * free-text / equipment descriptions (longer than 40 chars)
      * bare decimal numbers like "0.4" or "1,5"
      * machinery listings carrying a power rating (kw / кв / квт)
      * names made of nothing but vendor words / punctuation (e.g. "Shurtan")
    """
    if not name:
        return False
    n = ' '.join(name.split()).strip()
    if not n:
        return False
    if len(n) > 40:
        return False
    if re.fullmatch(r'\d+[.,]\d+', n):
        return False
    if re.search(r'\d+([.,]\d+)?\s*(kw|kvt|кв|квт)\b', n, re.IGNORECASE):
        return False
    low = n.lower()
    if any(term in low for term in NON_POLYMER_TERMS):
        return False
    # Strip vendor words and punctuation; anything left means it's a real grade.
    core = collapse_separators(n.lower())
    for w in VENDOR_WORDS:
        core = core.replace(w, '')
    core = re.sub(r'[^0-9a-zа-я]', '', core)
    return bool(core)


class PolymerNormalizer:
    """Loads ``polymer_aliases.txt`` and maps alternative spellings to their
    canonical original name. Reloads automatically when the file changes."""

    def __init__(self, alias_file: str = None):
        self.alias_file = alias_file or getattr(
            config, 'POLYMER_ALIASES_FILE', 'polymer_aliases.txt'
        )
        self._alias_to_original = {}    # exact match_key -> canonical original
        self._digit_grades = {}         # "0209" -> canonical (digit-token fold)
        self._substr_grades = {}        # "bl3"  -> canonical (prefixed-code fold)
        self._mtime = None
        self._load()

    # ------------------------------------------------------------------ #
    #  Public API
    # ------------------------------------------------------------------ #

    def canonicalize(self, name: str) -> str:
        """Return the canonical grade name for ``name`` if it matches a declared
        grade; otherwise return ``name`` unchanged.

        First an exact (case/space/emoji-insensitive) match, then grade folding
        (see _fold_grade) which collapses any producer/tier wording around a
        registered grade number — so "Uz-Kor Gas J-2200", "2200 repack" and
        "LLDPE 0209 Amir Kabir" resolve to "2200" / "0209"."""
        if not name:
            return name
        self._maybe_reload()
        hit = self._alias_to_original.get(_match_key(name))
        if hit is not None:
            return hit
        folded = self._fold_grade(name, structural_key(name))
        if folded is not None:
            return folded
        return name

    def _fold_grade(self, name: str, sk: str = None):
        """Collapse a name to a registered bare grade number when that number is
        the name's grade code — folding producer and quality-tier wording
        ("52518 original repack" -> "52518", "Xitoy 1003" -> "1003",
        "BL3 Jam" -> "3"). Returns the canonical number, or None if no single
        registered grade applies.

        Long-enough numbers match as a standalone digit-run (a "%" right after
        is skipped so "30% TiO2" is never grade 30). Short numbers like 3 / 30
        are too ambiguous on their own (they collide with "SG3", "CK-30"), so
        they only match through a prefixed code such as "bl3" / "d30".
        """
        if not self._digit_grades and not self._substr_grades:
            return None
        hits = set()
        for m in re.finditer(r'\d+', name):
            if re.match(r'\s*%', name[m.end():]):   # a percentage, not a grade
                continue
            canon = self._digit_grades.get(m.group())
            if canon:
                hits.add(canon)
        if self._substr_grades:
            if sk is None:
                sk = structural_key(name)
            for token, canon in self._substr_grades.items():
                if token in sk:
                    hits.add(canon)
        if len(hits) == 1:
            return next(iter(hits))
        return None

    @property
    def alias_count(self) -> int:
        """Number of registered spellings (originals + alternatives)."""
        self._maybe_reload()
        return len(self._alias_to_original)

    # ------------------------------------------------------------------ #
    #  Internals
    # ------------------------------------------------------------------ #

    def _maybe_reload(self):
        """Reload the file if its modification time changed since last load."""
        try:
            mtime = os.path.getmtime(self.alias_file)
        except OSError:
            # File missing/unreadable -- keep the last-good map. If it was
            # previously present, note that it's gone so a later re-create
            # triggers a reload.
            self._mtime = None
            return
        if mtime != self._mtime:
            self._load()

    def _load(self):
        """Parse the alias file into the match_key -> original mapping.

        A malformed file never raises: on any error we keep the previous
        (or empty) mapping so the bot/scraper keep running.
        """
        match_map = {}
        digit_grades = {}
        substr_grades = {}

        def register(spelling, canonical):
            match_map[_match_key(spelling)] = canonical
            sk = structural_key(spelling)
            if not sk:
                return
            # Grade-number folding: classify the token so _fold_grade() can
            # collapse every producer/tier variant to this canonical number.
            if sk.isdigit():
                # A bare number >= 3 digits is specific enough to match on its
                # own. Shorter ones (3, 30) are ambiguous and only fold via a
                # prefixed alternative below.
                if len(sk) >= 3:
                    digit_grades[sk] = canonical
            else:
                substr_grades[sk] = canonical

        def commit():
            self._alias_to_original = match_map
            self._digit_grades = digit_grades
            self._substr_grades = substr_grades

        try:
            self._mtime = os.path.getmtime(self.alias_file)
            with open(self.alias_file, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except OSError:
            # No alias file yet -> no aliases. The system behaves exactly as it
            # did before this feature existed.
            self._mtime = None
            commit()
            return
        except Exception as e:  # pragma: no cover - defensive
            print(f"[normalizer] Could not read {self.alias_file}: {e}")
            return  # keep whatever mapping we already had

        original = None        # current block's canonical name
        section = None         # 'original' | 'alternatives' | None

        for raw in lines:
            line = raw.strip()
            if not line or line.startswith('#'):
                continue

            low = line.lower()

            if line == '---':                       # block separator
                original = None
                section = None
                continue
            if low.startswith('[original'):         # [Original Name]
                section = 'original'
                original = None
                continue
            if low.startswith('[alternativ') or low.startswith('[alias'):
                section = 'alternatives'            # [Alternative Names]
                continue

            # --- content line ---
            if section == 'original':
                if original is None:
                    # First line under [Original Name] is the canonical name;
                    # it is also an alias of itself so queries for it resolve.
                    original = line
                    register(line, line)
                else:
                    # Extra lines under [Original Name] (no explicit
                    # [Alternative Names] header) are treated as alternatives.
                    register(line, original)
            elif section == 'alternatives':
                if original is not None:
                    register(line, original)
                # else: alternatives listed before any original -- ignore safely
            # section is None (content before any header) -> ignore

        commit()
