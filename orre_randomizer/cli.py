"""Command line interface to the same pipeline used by the desktop app."""
import argparse
from dataclasses import fields, replace
import json
from pathlib import Path
import sys

from .engine.analyze_game import FormatError
from .service import Options, UserError, find_dolphin_tool, randomize
from .profiles import XD_SPOT_MIGRATION, load_profile
from .xd import XDOptions


def comma_ids(value):
    try:
        return tuple(int(part.strip()) for part in value.split(",")) if value.strip() else ()
    except ValueError as error:
        raise argparse.ArgumentTypeError("Utilisez des numéros séparés par des virgules.") from error


def add_options(parser, option_type, prefix=""):
    for item in fields(option_type):
        argument = "--" + prefix + item.name.replace("_", "-")
        kind = item.metadata["kind"]
        kwargs = {"default": argparse.SUPPRESS, "help": item.metadata["description"].replace("%", "%%")}
        if kind == "bool":
            kwargs["action"] = argparse.BooleanOptionalAction
        elif kind == "choice":
            kwargs["choices"] = [value for value, _ in item.metadata["choices"]]
        else:
            kwargs["type"] = {"float": float, "int": int, "species_set": comma_ids, "type_set": comma_ids}[kind]
        parser.add_argument(argument, **kwargs)


def main() -> int:
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description="Create a separate, seeded Pokémon Colosseum or XD ISO/RVZ.")
    parser.add_argument("source", type=Path)
    parser.add_argument("destination", type=Path)
    parser.add_argument("--game", choices=("colosseum", "xd"), default="colosseum")
    xd_group = parser.add_argument_group("Pokémon XD")
    xd_group.add_argument("--xd-copy", action="store_true", help="Create a byte-identical XD copy")
    add_options(xd_group, XDOptions, "xd-")
    parser.add_argument("--seed", help="Seed ; sinon utiliser celle du profil importé")
    parser.add_argument("--profile", type=Path, help="Profil JSON exporté par l’application")
    parser.add_argument("--journal-language", choices=("fr", "en", "de", "es", "it", "ja"), default="fr",
                        help="Langue du journal HTML ; ne change pas la langue du jeu")
    parser.add_argument("--dolphin-tool", type=Path, default=find_dolphin_tool())
    parser.add_argument("--keep-specials", action="store_true")
    parser.add_argument("--allow-shadow-family-duplicates", action="store_true")
    parser.add_argument("--keep-evolutions", action="store_true")
    parser.add_argument("--starter-base-forms", action=argparse.BooleanOptionalAction,
                        default=argparse.SUPPRESS,
                        help="Ancien nom : utilisez --starter-stage base ou --starter-stage any")
    add_options(parser, Options)
    args = parser.parse_args()
    last = [-1, ""]
    def progress(percent, message):
        if message != last[1] or percent // 10 != last[0] // 10:
            print(f"{percent:3d}% {message}", file=sys.stderr, flush=True)
            last[:] = percent, message
    try:
        xd_overrides = {item.name: getattr(args, f"xd_{item.name}") for item in fields(XDOptions)
                        if hasattr(args, f"xd_{item.name}")}
        if args.game == "xd":
            if (args.keep_specials or args.keep_evolutions or args.allow_shadow_family_duplicates
                    or hasattr(args, "starter_base_forms") or any(hasattr(args, item.name) for item in fields(Options))):
                parser.error("Colosseum options cannot be used with --game xd")
            if args.xd_copy and (xd_overrides or args.profile):
                parser.error("--xd-copy cannot be combined with XD randomizer options or a profile")
            profile = load_profile(args.profile, is_xd=True) if args.profile else None
            seed = args.seed if args.seed is not None else profile.seed if profile else "copy" if args.xd_copy else None
            if seed is None:
                parser.error("--game xd requires --seed, --profile or --xd-copy")
            xd_options = (XDOptions.unchanged() if args.xd_copy else
                          replace(profile.options if profile else XDOptions(), **xd_overrides))
            if profile and profile.xd_spot_migration and xd_options.randomize_poke_spots:
                print(XD_SPOT_MIGRATION, file=sys.stderr)
            report = randomize(args.source, args.destination, seed,
                               dolphin_tool=args.dolphin_tool, progress=progress,
                               journal_language=args.journal_language, xd_options=xd_options)
            print(json.dumps(report, ensure_ascii=False, indent=2))
            return 0
        if args.xd_copy or xd_overrides:
            parser.error("XD options require --game xd")
        profile = load_profile(args.profile) if args.profile else None
        seed = args.seed if args.seed is not None else profile.seed if profile else None
        if seed is None:
            parser.error("saisissez --seed ou importez --profile")
        overrides = {item.name: getattr(args, item.name) for item in fields(Options) if hasattr(args, item.name)}
        if hasattr(args, "starter_base_forms") and "starter_stage" not in overrides:
            overrides["starter_stage"] = "base" if args.starter_base_forms else "any"
        options = replace(profile.options if profile else Options(), **overrides)
        if args.keep_specials:
            from .options import SPECIAL_OPTIONS
            options = replace(options, **{name: False for name in SPECIAL_OPTIONS.values()})
        if args.keep_evolutions:
            options = replace(options, **{item.name: False for item in fields(Options)
                                         if item.name.startswith(("evolve_", "stones_"))})
        if args.allow_shadow_family_duplicates:
            options = replace(options, unique_shadows=False)
        report = randomize(args.source, args.destination, seed,
                           options, args.dolphin_tool, progress, journal_language=args.journal_language)
    except (UserError, FormatError, OSError) as error:
        print(f"Erreur : {error}", file=sys.stderr)
        return 1
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
