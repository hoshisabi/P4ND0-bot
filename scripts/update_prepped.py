"""Record which adventures have been prepped for Foundry, for wishlist suggestions.

Scans the Foundry Transfer folder (one ``CODE Title.zip`` per adventure),
matches each file to the adventure catalog, and writes prepped_adventures.json
at the repo root. Commit that file so the bot on the server can read it.

    uv run python scripts/update_prepped.py ["D:\\Downloads\\Foundry Transfer"]
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from utils.adventure_catalog import (  # noqa: E402
    PREPPED_PATH,
    SUGGESTED_HOURS,
    catalog_names_for_product,
    fetch_catalog,
    match_prepped_file,
)

DEFAULT_SOURCE = Path(r"D:\Downloads\Foundry Transfer")

# Zips (without .zip) to leave off the prepped list.
SKIP = {
    "DDEP09-03 Liar's Night": "one-off, not a regular offering",
    "Liar's Night Wandering Monsters": "not an adventure",
    "PS-DC-DD-03 One Foot in the Grave": "unfinished Dungeoncraft; this prep is a playtest",
}

# Zips that hold a whole bundle: file name -> DMsGuild product ID.
BUNDLES = {
    "FR-DC-UCON25 Welcome to Basht": "545950",
}


def main() -> None:
    source = Path(sys.argv[1]) if len(sys.argv) > 1 else DEFAULT_SOURCE
    if not source.is_dir():
        sys.exit(f"Not a folder: {source}")

    catalog = fetch_catalog()
    by_name = {entry["name"]: entry for entry in catalog}

    adventures = []
    skipped = []
    for path in sorted(source.glob("*.zip"), key=lambda p: p.name.casefold()):
        if path.stem in SKIP:
            skipped.append(path)
            continue
        if path.stem in BUNDLES:
            names = catalog_names_for_product(BUNDLES[path.stem], catalog)
            if not names:
                sys.exit(f"Bundle {BUNDLES[path.stem]} for {path.name} is not in the catalog")
            adventures.extend({"name": name, "file": path.name, "matched": True} for name in names)
            continue
        name = match_prepped_file(path.stem, catalog)
        adventures.append({"name": name or path.stem, "file": path.name, "matched": bool(name)})
    adventures.sort(key=lambda item: item["name"].casefold())

    PREPPED_PATH.write_text(
        json.dumps({"adventures": adventures}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )

    matched = [item for item in adventures if item["matched"]]
    two_hour = [item for item in matched if by_name[item["name"]]["hours"] == SUGGESTED_HOURS]
    unmatched = [item for item in adventures if not item["matched"]]
    print(f"Wrote {PREPPED_PATH.name}: {len(adventures)} adventures, {len(matched)} matched to the catalog, "
          f"{len(two_hour)} of those are {SUGGESTED_HOURS}-hour (these get suggested first).")
    if skipped:
        print(f"\nSkipped ({len(skipped)}):")
        for path in skipped:
            print(f"  {path.name} - {SKIP[path.stem]}")
    if unmatched:
        print(f"\nNot matched to the catalog ({len(unmatched)}) - kept under their file names:")
        for item in unmatched:
            print(f"  {item['file']}")


if __name__ == "__main__":
    main()
