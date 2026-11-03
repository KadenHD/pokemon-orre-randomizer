"""Rebuild BSD-licensed selector names from the pinned PokeAPI CSV.

Supply pokemon_species_names.csv locally; never downloads at runtime.
"""
import argparse
import csv
import hashlib
import json
from pathlib import Path
import pprint

ROOT = Path(__file__).resolve().parents[1]
SOURCE_SHA256 = "820cde17074cdb1c2b0595c997fb8f998e773bd5da3bb525dec85703c86c5fd9"
LANGUAGES = {"fr": 5, "en": 9, "de": 6, "es": 7, "it": 8, "ja": 1}
# Native Colosseum type IDs; 9 (Mystery) has no species and is omitted.
TYPE_IDS = tuple(i for i in range(18) if i != 9)
TYPE_NAMES = {
    "fr": "Normal,Combat,Vol,Poison,Sol,Roche,Insecte,Spectre,Acier,Feu,Eau,Plante,Électrik,Psy,Glace,Dragon,Ténèbres",
    "en": "Normal,Fighting,Flying,Poison,Ground,Rock,Bug,Ghost,Steel,Fire,Water,Grass,Electric,Psychic,Ice,Dragon,Dark",
    "de": "Normal,Kampf,Flug,Gift,Boden,Gestein,Käfer,Geist,Stahl,Feuer,Wasser,Pflanze,Elektro,Psycho,Eis,Drache,Unlicht",
    "es": "Normal,Lucha,Volador,Veneno,Tierra,Roca,Bicho,Fantasma,Acero,Fuego,Agua,Planta,Eléctrico,Psíquico,Hielo,Dragón,Siniestro",
    "it": "Normale,Lotta,Volante,Veleno,Terra,Roccia,Coleottero,Spettro,Acciaio,Fuoco,Acqua,Erba,Elettro,Psico,Ghiaccio,Drago,Buio",
    "ja": "ノーマル,かくとう,ひこう,どく,じめん,いわ,むし,ゴースト,はがね,ほのお,みず,くさ,でんき,エスパー,こおり,ドラゴン,あく",
}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("source", type=Path)
    args = parser.parse_args()
    if hashlib.sha256(args.source.read_bytes()).hexdigest() != SOURCE_SHA256:
        raise ValueError("source CSV differs from the pinned hash")
    rows = list(csv.DictReader(args.source.read_text("utf-8").splitlines()))
    names = {language: {int(row["pokemon_species_id"]): row["name"] for row in rows
                       if int(row["local_language_id"]) == code and 1 <= int(row["pokemon_species_id"]) <= 386}
             for language, code in LANGUAGES.items()}
    assert all(set(values) == set(range(1, 387)) for values in names.values())
    types = {language: dict(zip(TYPE_IDS, text.split(","), strict=True)) for language, text in TYPE_NAMES.items()}
    target = ROOT / "colosseum_randomizer/locales/selection_names.py"
    target.write_text('"""Pokémon and type names from PokeAPI (BSD); see licenses/pokeapi-names.json."""\n\n'
                      + 'SPECIES_NAMES = ' + pprint.pformat(names, sort_dicts=False, width=100) + '\n\n'
                      + 'TYPE_NAMES = ' + pprint.pformat(types, sort_dicts=False, width=100) + '\n', encoding="utf-8")
    provenance = ROOT / "licenses/pokeapi-names.json"
    data = json.loads(provenance.read_text("utf-8"))
    data.update(selection="local_language_id=1,5,6,7,8,9; national species IDs 1..386; name only",
                output="colosseum_randomizer/locales/selection_names.py", languages=LANGUAGES,
                type_names={"source": "https://raw.githubusercontent.com/PokeAPI/pokeapi/master/data/v2/csv/type_names.csv",
                            "selection": "17 Gen III types, same six languages; native ID 9 omitted",
                            "verified": "2026-11-01", "data_sha256": hashlib.sha256(json.dumps(types, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()})
    provenance.write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n', encoding="utf-8")


if __name__ == "__main__":
    main()
