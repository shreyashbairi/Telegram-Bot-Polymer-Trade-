"""
Back-clean the database so it matches the current normalization rules.

New messages are normalized automatically as they are scraped. This one-off
script fixes rows that were stored before a rule changed, by:

  1. Removing junk rows (equipment, descriptions, bare vendor names) using the
     same validity rule the parser now applies to new data.
  2. Re-normalizing every remaining row so all spellings of a polymer collapse
     to one identity (separator-invariant key + polymer_aliases.txt).

Only the polymer_name and normalized_name columns are rewritten — prices,
dates, message links and chat ids are never touched. A timestamped backup of
the database file is taken first.

Usage:
    python apply_normalization.py
"""
import shutil
from datetime import datetime

import config
from database import PolymerDatabase


def main():
    db = PolymerDatabase()
    print(f"Loaded {db.normalizer.alias_count} registered alias spellings "
          f"from {config.POLYMER_ALIASES_FILE}\n")

    # ---- Backup first -------------------------------------------------
    stamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_path = f"{config.DATABASE_PATH}.bak_{stamp}"
    try:
        shutil.copy2(config.DATABASE_PATH, backup_path)
        print(f"Backup written to: {backup_path}\n")
    except FileNotFoundError:
        print(f"No existing database at {config.DATABASE_PATH} — nothing to migrate.")
        return
    except Exception as e:
        print(f"WARNING: could not create backup ({e}). Aborting to be safe.")
        return

    before = db.get_data_date_range()
    if before:
        print(f"Before: {before['total_records']} records "
              f"({before['oldest_date']} -> {before['newest_date']})")
    distinct_before = len(db.get_unique_polymers_with_latest_date())
    print(f"Before: {distinct_before} distinct polymers (by normalized name)\n")

    # ---- Step 1: remove junk -----------------------------------------
    print("Removing non-polymer (junk) rows...")
    junk = db.delete_invalid_entries()
    if junk['names']:
        for name, cnt in junk['names']:
            print(f"   - {name!r} ({cnt})")
    print(f"  Deleted {junk['deleted']} junk row(s) across {len(junk['names'])} name(s).\n")

    # ---- Step 2: re-normalize remaining rows -------------------------
    print("Re-normalizing remaining rows...")
    summary = db.renormalize_existing_data()
    print(f"  Examined {summary['total']} rows, updated {summary['updated']}.\n")

    # ---- Result -------------------------------------------------------
    after = db.get_data_date_range()
    distinct_after = len(db.get_unique_polymers_with_latest_date())
    if after:
        print(f"After:  {after['total_records']} records "
              f"({after['oldest_date']} -> {after['newest_date']})")
    print(f"After:  {distinct_after} distinct polymers (by normalized name)")
    merged = distinct_before - distinct_after
    if merged > 0:
        print(f"  -> {merged} duplicate/junk polymer name(s) collapsed away.")

    print("\nDone. New scraped data is normalized automatically on insert.")
    print(f"If anything looks wrong, restore the backup: {backup_path}")


if __name__ == "__main__":
    main()
