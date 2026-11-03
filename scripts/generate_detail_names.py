"""Generate six-language BSD name fallbacks from locally supplied pinned CSVs."""
from pathlib import Path
import argparse
import csv
import hashlib
import json
import pprint

ROOT = Path(__file__).resolve().parents[1]
LANGUAGES = {"fr": 5, "en": 9, "de": 6, "es": 7, "it": 8, "ja": 1}
SOURCES = {
    "move_names.csv": "99e23ee38ea53d1473474d463b87651deac3cd4928750f8186feae66da45c147",
    "ability_names.csv": "8acb80c42210f86ae747dc3347b060d69cd2574a9dbfaf74774ae632ca6348da",
    "item_names.csv": "c4ad0b446e395c378d8ba75d6900f051cc9ebb99431d4000adeac35f492852f0",
}
# These are native Gen III item IDs, not PokeAPI item IDs.
EVOLUTION_ITEMS = {93: "Sun Stone", 94: "Moon Stone", 95: "Fire Stone",
                   96: "Thunder Stone", 97: "Water Stone", 98: "Leaf Stone",
                   187: "King’s Rock", 192: "Deep Sea Tooth", 193: "Deep Sea Scale",
                   199: "Metal Coat", 201: "Dragon Scale", 218: "Upgrade"}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("csv_directory", type=Path)
    args = parser.parse_args()
    sources = {}
    for name, digest in SOURCES.items():
        data = (args.csv_directory / name).read_bytes()
        assert hashlib.sha256(data).hexdigest() == digest, name
        sources[name] = list(csv.DictReader(data.decode("utf8").splitlines()))
    result = {}
    for name, key, maximum in (("move_names.csv", "move_id", 354),
                                ("ability_names.csv", "ability_id", 77)):
        result[key] = {language: {int(row[key]): row["name"] for row in sources[name]
                                 if int(row["local_language_id"]) == identifier
                                 and 1 <= int(row[key]) <= maximum}
                       for language, identifier in LANGUAGES.items()}
        assert all(set(rows) == set(range(1, maximum + 1)) for rows in result[key].values())
    english_items = {row["name"]: int(row["item_id"]) for row in sources["item_names.csv"]
                     if row["local_language_id"] == "9"}
    item_ids = {native: english_items[name] for native, name in EVOLUTION_ITEMS.items()}
    result["item_id"] = {language: {native: next(row["name"] for row in sources["item_names.csv"]
        if int(row["local_language_id"]) == identifier and int(row["item_id"]) == source)
        for native, source in item_ids.items()} for language, identifier in LANGUAGES.items()}
    target = ROOT / "colosseum_randomizer/locales/detail_names.py"
    target.write_text('"""BSD name fallbacks for the UI; see licenses/pokeapi-details.json."""\n\n'
        + "MOVE_NAMES = " + pprint.pformat(result["move_id"], sort_dicts=False, width=110)
        + "\n\nABILITY_NAMES = " + pprint.pformat(result["ability_id"], sort_dicts=False, width=110)
        + "\n\nEVOLUTION_ITEM_NAMES = " + pprint.pformat(result["item_id"], sort_dicts=False, width=110)
        + "\n", encoding="utf8")
    provenance = {"license": "pokeapi.txt", "generated": "2026-11-03", "languages": LANGUAGES,
        "sources": {name: {"url": "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/" + name,
                             "sha256": digest} for name, digest in SOURCES.items()},
        "output": str(target.relative_to(ROOT)).replace('\\', '/'),
        "output_sha256": hashlib.sha256(target.read_bytes()).hexdigest(),
        "selection": "Moves 1..354; abilities 1..77; twelve native Gen III evolution item names, six languages.",
        "policy": "Fallback presentation names only; actual move and evolution properties come from final ROM bytes. Native names take precedence when the ROM has that language.",
        "native_evolution_item_to_pokeapi": item_ids}
    (ROOT / "licenses/pokeapi-details.json").write_text(json.dumps(provenance, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print(json.dumps({"generated": str(target), "bytes": target.stat().st_size}))


if __name__ == "__main__":
    main()
