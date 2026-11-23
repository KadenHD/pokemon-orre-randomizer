"""Real v2.1.0 exports migrate without rewriting their checksummed settings.

Profiles/challenge codes were exported by the retained v2.1.0 source archive;
its profiles.py was checked byte-for-byte (LF-normalized) against tag v2.1.0.
The source profile module SHA256 is PROFILE_MODULE_SHA256 below. Report fixtures
are actual v2.1.0 startup QA reports reduced to the public parser's required
fields, excluding all local paths and personal content. No current Options
object was used to reconstruct or complete a historical fixture.
"""
from copy import deepcopy
from dataclasses import asdict
import hashlib
import json
import unittest

from orre_randomizer import profiles
from orre_randomizer.challenges import decode_challenge
from orre_randomizer.service import UserError

PROFILE_MODULE_SHA256 = '033187152f654517d31ad868243bf07a1952e08378966016bd40d9a9daf633cf'
SOURCE_ARCHIVE_SHA256 = '3e2e085d8f0a890357c25e23249dbe05dcedb12a5ac040c6314561c2d6146e37'
EXPORTED = json.loads(r'''{
  "profiles": {
    "colosseum-natural": {
      "profile": {
        "format": "colosseum-randomizer-profile",
        "schema_version": 1,
        "app_version": "2.1.0",
        "engine_version": "natural-encounter-moves-v27",
        "game": {
          "id": "pokemon-colosseum",
          "roms": [
            {
              "id": "GC6P01",
              "revision": 0,
              "iso_sha256": "1e3b4aa806ac3367cca13496f7701137e9437e7bac0101f75b9b137633a10aa9"
            },
            {
              "id": "GC6E01",
              "revision": 0,
              "iso_sha256": "78c4074429fa598b97bfac296bf8e0f7e93f5cb6d8679f8d2653ca902820f6c5"
            },
            {
              "id": "GC6J01",
              "revision": 0,
              "iso_sha256": "17c284ab2592083b91d33229ea03384ccdd397eab5db5d3a6ddf5b1f9685368f"
            }
          ]
        },
        "seed": "v210-migration-étoile ",
        "options": {
          "randomize_trainers": true,
          "randomize_shadows": true,
          "randomize_legendary_shadows": false,
          "unique_shadows": true,
          "trainer_theme_mode": "none",
          "trainer_force_evolved": false,
          "trainer_evolution_level": 40,
          "custom_shinies": true,
          "seeded_shinies": true,
          "keep_shadow_lugia_after_purification": false,
          "shiny_chance_percent": 17.5,
          "starter_umbreon": true,
          "starter_espeon": true,
          "starter_umbreon_species": 129,
          "starter_espeon_species": 0,
          "starter_stage": "any",
          "starter_three_stage_families": false,
          "starter_balance_pair": false,
          "starter_distinct_families": true,
          "diverse_story_families": true,
          "starter_complementary_types": false,
          "gift_plusle": true,
          "gift_hooh": true,
          "event_celebi": true,
          "event_pikachu": true,
          "accessible_event_gifts": true,
          "postgame_shadow_lugia": true,
          "postgame_randomize_team": false,
          "postgame_randomize_lugia": false,
          "event_pikachu_purifications": 10,
          "event_celebi_purifications": 25,
          "event_pikachu_level": 30,
          "event_celebi_level": 45,
          "evolve_trade": true,
          "evolve_trade_items": true,
          "evolve_coquiperl": true,
          "evolve_day_night": true,
          "evolve_beauty": true,
          "stones_phenac": true,
          "stones_pyrite": true,
          "readable_stone_names": true,
          "randomize_trainer_moves": "natural",
          "randomize_starter_moves": "natural",
          "randomize_gift_moves": false,
          "randomize_learnsets": false,
          "ensure_damaging_move": true,
          "ensure_stab_move": false,
          "no_duplicate_moves": true,
          "ban_self_destruct": true,
          "ban_ohko": true,
          "moves_mode": "chaos",
          "randomize_abilities": true,
          "abilities_family_consistent": true,
          "randomize_stats": false,
          "preserve_stat_totals": true,
          "randomize_types": false,
          "types_family_consistent": true,
          "allow_gen1": true,
          "allow_gen2": true,
          "allow_gen3": true,
          "allow_legendaries": false,
          "randomize_preserved_properties": true,
          "excluded_species": [],
          "excluded_types": [],
          "balance_species": false,
          "randomize_held_items": false,
          "useful_held_items_only": true,
          "trainer_level_multiplier": 1.0,
          "progressive_levels": false,
          "early_level_multiplier": 1.0,
          "mid_level_multiplier": 1.0,
          "late_level_multiplier": 1.0,
          "experience_multiplier": 1.0,
          "purification_multiplier": 1,
          "capture_rate_multiplier": 1.0,
          "minimum_catch_rate": 0,
          "randomize_tm_moves": false,
          "tm_compatibility_mode": "original",
          "tm_ensure_offensive": true,
          "randomize_field_items": false,
          "items_similar_value": false,
          "keep_capture_items": false,
          "randomize_shop_items": false,
          "shop_keep_capture_items": true,
          "legacy_shop_scope": false,
          "shop_keep_healing": true,
          "boss_stronger": false,
          "boss_team_variety": true,
          "boss_shadow_legendary_mode": "any",
          "boss_shadow_power_mode": "global",
          "boss_shadow_min_bst": 0
        },
        "configuration_sha256": "def7fb4b64d171d0d14b2599b6a260cd9de9cb1fd39aef959f3653cad2adc1da"
      },
      "challenge": "ORRE1.eNqFkmtqwzAMx68y9DkpsWvn0auUUhRbSQOOXeIkUMYOtHPsYnPpI25ZOwhCln7W4-98Ah6P-5kG3zkLG-ArtsogAbJtZylKWBynAU1KVrnJjjSkvZvJpzMvAt50ZLTf-wNymQdaMyY0MaolrSWKRlRMo6pKibIuco11leeibPIGGyyLWnGutZJcIbKyENW5ZIs9hUrKGec9TX0IeXWgHmHDgkukQ3bmLEv7rh1wDGOmP9-j6wx9BHZGM5GHzXYcJkr-Mg0af7NLFNCeIMlCf-NqNBADQZqIvJ8iQsiEy4u7zhKWJS-7b3fn77FiPNHFnvOLF6ZSB3Qe3i1wxV9VfHfp9sjwQC3R520vMhQr-a-q2VXXWExexbK7oQt_3L2LiPcG6yzBk4K7r1972u0f.fcadcf727e64ac4e"
    },
    "colosseum-random": {
      "profile": {
        "format": "colosseum-randomizer-profile",
        "schema_version": 1,
        "app_version": "2.1.0",
        "engine_version": "natural-encounter-moves-v27",
        "game": {
          "id": "pokemon-colosseum",
          "roms": [
            {
              "id": "GC6P01",
              "revision": 0,
              "iso_sha256": "1e3b4aa806ac3367cca13496f7701137e9437e7bac0101f75b9b137633a10aa9"
            },
            {
              "id": "GC6E01",
              "revision": 0,
              "iso_sha256": "78c4074429fa598b97bfac296bf8e0f7e93f5cb6d8679f8d2653ca902820f6c5"
            },
            {
              "id": "GC6J01",
              "revision": 0,
              "iso_sha256": "17c284ab2592083b91d33229ea03384ccdd397eab5db5d3a6ddf5b1f9685368f"
            }
          ]
        },
        "seed": "v210-migration-étoile ",
        "options": {
          "randomize_trainers": true,
          "randomize_shadows": true,
          "randomize_legendary_shadows": false,
          "unique_shadows": true,
          "trainer_theme_mode": "none",
          "trainer_force_evolved": false,
          "trainer_evolution_level": 40,
          "custom_shinies": true,
          "seeded_shinies": true,
          "keep_shadow_lugia_after_purification": false,
          "shiny_chance_percent": 5.0,
          "starter_umbreon": true,
          "starter_espeon": true,
          "starter_umbreon_species": 0,
          "starter_espeon_species": 0,
          "starter_stage": "any",
          "starter_three_stage_families": false,
          "starter_balance_pair": false,
          "starter_distinct_families": true,
          "diverse_story_families": true,
          "starter_complementary_types": false,
          "gift_plusle": true,
          "gift_hooh": true,
          "event_celebi": true,
          "event_pikachu": true,
          "accessible_event_gifts": true,
          "postgame_shadow_lugia": true,
          "postgame_randomize_team": false,
          "postgame_randomize_lugia": false,
          "event_pikachu_purifications": 10,
          "event_celebi_purifications": 25,
          "event_pikachu_level": 30,
          "event_celebi_level": 45,
          "evolve_trade": true,
          "evolve_trade_items": true,
          "evolve_coquiperl": true,
          "evolve_day_night": true,
          "evolve_beauty": true,
          "stones_phenac": true,
          "stones_pyrite": true,
          "readable_stone_names": true,
          "randomize_trainer_moves": true,
          "randomize_starter_moves": true,
          "randomize_gift_moves": true,
          "randomize_learnsets": true,
          "ensure_damaging_move": true,
          "ensure_stab_move": false,
          "no_duplicate_moves": true,
          "ban_self_destruct": true,
          "ban_ohko": true,
          "moves_mode": "chaos",
          "randomize_abilities": true,
          "abilities_family_consistent": true,
          "randomize_stats": false,
          "preserve_stat_totals": true,
          "randomize_types": false,
          "types_family_consistent": true,
          "allow_gen1": true,
          "allow_gen2": true,
          "allow_gen3": true,
          "allow_legendaries": false,
          "randomize_preserved_properties": false,
          "excluded_species": [],
          "excluded_types": [],
          "balance_species": false,
          "randomize_held_items": true,
          "useful_held_items_only": true,
          "trainer_level_multiplier": 1.0,
          "progressive_levels": false,
          "early_level_multiplier": 1.0,
          "mid_level_multiplier": 1.0,
          "late_level_multiplier": 1.0,
          "experience_multiplier": 1.0,
          "purification_multiplier": 1,
          "capture_rate_multiplier": 1.0,
          "minimum_catch_rate": 0,
          "randomize_tm_moves": true,
          "tm_compatibility_mode": "random",
          "tm_ensure_offensive": true,
          "randomize_field_items": true,
          "items_similar_value": false,
          "keep_capture_items": false,
          "randomize_shop_items": true,
          "shop_keep_capture_items": true,
          "legacy_shop_scope": false,
          "shop_keep_healing": true,
          "boss_stronger": false,
          "boss_team_variety": true,
          "boss_shadow_legendary_mode": "any",
          "boss_shadow_power_mode": "global",
          "boss_shadow_min_bst": 0
        },
        "configuration_sha256": "ff7b60490821c97043431d0b7a1fde06f26a230507896ae99ebb04aa791b5531"
      },
      "challenge": "ORRE1.eNqVUG1qwzAMvcrQb6fErp2vq5RSFFtpA45d4iRQxg60c-xic2i3emUdDIyQn56k9_QKeD4fFhpD7x00IDZ8kwMDcsfeUVJwOM0j2oyc9rObaMwGv1DIFlFGeteTNeEQTihUEdmGc2mIU6toq1B2suYGdV0pVG1ZGGzropBVV3TYYVW2WghjtBIakVelrNeRRxwoTtLe-hBoHiIU9IkGhIbHlMjE6iJ4ng39ccQpysw-3iffW3qJ3AXtTAGa3TTOxH4LHdrwFe8ooLsAy-N-61u0kBLiaRLm9y9hSMWEuqbbnPGcPd2-26_v58RU0TWu9XsWVekT-gB_GbjR2T99Pzp5Dqqnmu9ofrtjgqdNMKIzfrj5kKlHcN4RPGjYv30Cz8DnOg.549a13dc3d73eeb6"
    },
    "xd-natural": {
      "profile": {
        "format": "pokemon-xd-randomizer-profile",
        "schema_version": 1,
        "engine_version": "xd-natural-encounter-moves-v17",
        "seed": "v210-migration-étoile ",
        "options": {
          "randomize_starter": true,
          "randomize_trainers": true,
          "randomize_shadows": true,
          "randomize_legendary_shadows": false,
          "randomize_tutorial_shadow": true,
          "randomize_poke_spots": true,
          "poke_spots_full_pokedex": true,
          "custom_poke_spot_shinies": true,
          "poke_spot_shiny_chance_percent": 5.0,
          "accessible_evolutions": true,
          "unique_shadow_families": true,
          "randomize_gifts": true,
          "randomize_hordel_gift": true,
          "stone_shops": true,
          "starter_species": 129,
          "starter_stage": "any",
          "starter_three_stage_families": false,
          "diverse_story_families": true,
          "balance_species": false,
          "allow_gen1": true,
          "allow_gen2": true,
          "allow_gen3": true,
          "allow_legendaries": false,
          "randomize_preserved_properties": true,
          "excluded_species": [],
          "excluded_types": [],
          "custom_shinies": true,
          "custom_shadow_shinies": true,
          "keep_shadow_lugia_after_purification": false,
          "shiny_chance_percent": 17.5,
          "trainer_theme_mode": "none",
          "trainer_force_evolved": false,
          "trainer_evolution_level": 40,
          "randomize_trainer_moves": "natural",
          "randomize_starter_moves": "natural",
          "randomize_gift_moves": false,
          "randomize_learnsets": false,
          "ensure_damaging_move": true,
          "ensure_stab_move": false,
          "no_duplicate_moves": true,
          "ban_self_destruct": true,
          "ban_ohko": true,
          "moves_mode": "chaos",
          "randomize_abilities": true,
          "abilities_family_consistent": true,
          "randomize_stats": false,
          "preserve_stat_totals": true,
          "randomize_types": false,
          "types_family_consistent": true,
          "randomize_held_items": false,
          "useful_held_items_only": true,
          "trainer_level_multiplier": 1.0,
          "progressive_levels": false,
          "early_level_multiplier": 1.0,
          "mid_level_multiplier": 1.0,
          "late_level_multiplier": 1.0,
          "capture_rate_multiplier": 1.0,
          "minimum_catch_rate": 0,
          "experience_multiplier": 1.0,
          "purification_multiplier": 1,
          "randomize_tm_moves": false,
          "tm_compatibility_mode": "original",
          "tm_ensure_offensive": true,
          "randomize_field_items": false,
          "randomize_shop_items": false,
          "shop_keep_healing": true,
          "shop_keep_capture_items": true,
          "items_similar_value": false,
          "keep_capture_items": false,
          "boss_stronger": false,
          "boss_team_variety": true,
          "boss_shadow_legendary_mode": "any",
          "boss_shadow_power_mode": "global",
          "boss_shadow_min_bst": 0
        },
        "configuration_sha256": "4f135deecb4179b9e1455e017c0e77ac98b612004dead76b664dbfbe2d62e7cb"
      },
      "challenge": "ORRE1.eNp1Um1ugzAMvcrk31Al4aOEq1RV5QanRQpJRQB1mnagnWMXWxispbSTEst6ec_PTvIBeLkcBmp97SyUIDZ8wyACsqfa0uLgWsUWu75FE5NVrrcdtXHjBvLxwLdBoWsylT_4M4osDwKZVFxrphIpdZYoQlEUeaJSIQSh2mZaKsb4kSdaiSwRqVQ6z1MlKywEsmIsecKGfq1D7tWZGoSSh5SoCvAgOIub-tRiF1qMv786Vxt6C9wBTU8eyl3X9hS9ChqN_4t3FNC-Q8SCsXFHNLAkhGt5WemGT9zdflwjuLSY4oiOOxioMzoPkzB7qDxT_2nzKV2PsGbB_GjwwL-jT8bbTbacTsj5VpY1XVuH33GTp2wxIFhnCVYd7T9_AD2iza8.54a820bbf09c44bf"
    },
    "xd-random": {
      "profile": {
        "format": "pokemon-xd-randomizer-profile",
        "schema_version": 1,
        "engine_version": "xd-natural-encounter-moves-v17",
        "seed": "v210-migration-étoile ",
        "options": {
          "randomize_starter": true,
          "randomize_trainers": true,
          "randomize_shadows": true,
          "randomize_legendary_shadows": false,
          "randomize_tutorial_shadow": true,
          "randomize_poke_spots": true,
          "poke_spots_full_pokedex": true,
          "custom_poke_spot_shinies": true,
          "poke_spot_shiny_chance_percent": 5.0,
          "accessible_evolutions": true,
          "unique_shadow_families": true,
          "randomize_gifts": true,
          "randomize_hordel_gift": true,
          "stone_shops": true,
          "starter_species": 0,
          "starter_stage": "any",
          "starter_three_stage_families": false,
          "diverse_story_families": true,
          "balance_species": false,
          "allow_gen1": true,
          "allow_gen2": true,
          "allow_gen3": true,
          "allow_legendaries": false,
          "randomize_preserved_properties": false,
          "excluded_species": [],
          "excluded_types": [],
          "custom_shinies": true,
          "custom_shadow_shinies": true,
          "keep_shadow_lugia_after_purification": false,
          "shiny_chance_percent": 5.0,
          "trainer_theme_mode": "none",
          "trainer_force_evolved": false,
          "trainer_evolution_level": 40,
          "randomize_trainer_moves": true,
          "randomize_starter_moves": true,
          "randomize_gift_moves": true,
          "randomize_learnsets": true,
          "ensure_damaging_move": true,
          "ensure_stab_move": false,
          "no_duplicate_moves": true,
          "ban_self_destruct": true,
          "ban_ohko": true,
          "moves_mode": "chaos",
          "randomize_abilities": true,
          "abilities_family_consistent": true,
          "randomize_stats": false,
          "preserve_stat_totals": true,
          "randomize_types": false,
          "types_family_consistent": true,
          "randomize_held_items": true,
          "useful_held_items_only": true,
          "trainer_level_multiplier": 1.0,
          "progressive_levels": false,
          "early_level_multiplier": 1.0,
          "mid_level_multiplier": 1.0,
          "late_level_multiplier": 1.0,
          "capture_rate_multiplier": 1.0,
          "minimum_catch_rate": 0,
          "experience_multiplier": 1.0,
          "purification_multiplier": 1,
          "randomize_tm_moves": true,
          "tm_compatibility_mode": "random",
          "tm_ensure_offensive": true,
          "randomize_field_items": true,
          "randomize_shop_items": true,
          "shop_keep_healing": true,
          "shop_keep_capture_items": true,
          "items_similar_value": false,
          "keep_capture_items": false,
          "boss_stronger": false,
          "boss_team_variety": true,
          "boss_shadow_legendary_mode": "any",
          "boss_shadow_power_mode": "global",
          "boss_shadow_min_bst": 0
        },
        "configuration_sha256": "ad7920fbccdcda861e122822bd56a215ad70191f83f88cf3650e7cd247a2ffe5"
      },
      "challenge": "ORRE1.eNp1UGtugzAMvsrk31Al4VHgKlVVucEBpJBUCaBN0w60c-xiC4NtFLVSYlmfv4eTd8Db7TKR8501UIE48AODCMg0naHN4LWODQ6jQx2TkXY0A7m4txP5eOLHoFAd6dpffIsiy4OgTGquFJNJWaoskYSiKPJEpkIIQnnMVCkZ41eeKCmyRKSlVHmeyrLGQiArZssGe_qJDr2XLfUIFQ8tUR3gSXAW913jcAgrxl-fg-00vQTuhHokD9VpcCNFj4pC7X_rPwpo3iBiIVjbK2rYEsK3PHT6wxfu6TyfGdxGLHVG5xsCZIvWwyLM7pxXavR09T113z4nPZzcp7P1DzYqcGhq26_LpmzzGDDWEOx8zx_f3QDHyg.4ea03d90b7de1ea9"
    }
  },
  "reports": {
    "colosseum": {
      "application_version": "2.1.0",
      "engine_version": "natural-encounter-moves-v27",
      "game_id": "GC6P01",
      "revision": 0,
      "source_sha256": "1e3b4aa806ac3367cca13496f7701137e9437e7bac0101f75b9b137633a10aa9",
      "source_iso_sha256": "1e3b4aa806ac3367cca13496f7701137e9437e7bac0101f75b9b137633a10aa9",
      "seed": "v210-natural-moves",
      "options": {
        "randomize_trainers": true,
        "randomize_shadows": true,
        "randomize_legendary_shadows": false,
        "unique_shadows": true,
        "trainer_theme_mode": "none",
        "trainer_force_evolved": false,
        "trainer_evolution_level": 40,
        "custom_shinies": true,
        "seeded_shinies": true,
        "keep_shadow_lugia_after_purification": false,
        "shiny_chance_percent": 5.0,
        "starter_umbreon": true,
        "starter_espeon": true,
        "starter_umbreon_species": 374,
        "starter_espeon_species": 129,
        "starter_stage": "any",
        "starter_three_stage_families": false,
        "starter_balance_pair": false,
        "starter_distinct_families": true,
        "diverse_story_families": true,
        "starter_complementary_types": false,
        "gift_plusle": true,
        "gift_hooh": true,
        "event_celebi": true,
        "event_pikachu": true,
        "accessible_event_gifts": true,
        "postgame_shadow_lugia": true,
        "postgame_randomize_team": false,
        "postgame_randomize_lugia": false,
        "event_pikachu_purifications": 10,
        "event_celebi_purifications": 25,
        "event_pikachu_level": 30,
        "event_celebi_level": 45,
        "evolve_trade": true,
        "evolve_trade_items": true,
        "evolve_coquiperl": true,
        "evolve_day_night": true,
        "evolve_beauty": true,
        "stones_phenac": true,
        "stones_pyrite": true,
        "readable_stone_names": true,
        "randomize_trainer_moves": "natural",
        "randomize_starter_moves": "natural",
        "randomize_gift_moves": "natural",
        "randomize_learnsets": false,
        "ensure_damaging_move": true,
        "ensure_stab_move": false,
        "no_duplicate_moves": true,
        "ban_self_destruct": true,
        "ban_ohko": true,
        "moves_mode": "chaos",
        "randomize_abilities": true,
        "abilities_family_consistent": true,
        "randomize_stats": false,
        "preserve_stat_totals": true,
        "randomize_types": false,
        "types_family_consistent": true,
        "allow_gen1": true,
        "allow_gen2": true,
        "allow_gen3": true,
        "allow_legendaries": false,
        "randomize_preserved_properties": false,
        "excluded_species": [],
        "excluded_types": [],
        "balance_species": false,
        "randomize_held_items": false,
        "useful_held_items_only": true,
        "trainer_level_multiplier": 1.0,
        "progressive_levels": false,
        "early_level_multiplier": 1.0,
        "mid_level_multiplier": 1.0,
        "late_level_multiplier": 1.0,
        "experience_multiplier": 1.0,
        "purification_multiplier": 1,
        "capture_rate_multiplier": 1.0,
        "minimum_catch_rate": 0,
        "randomize_tm_moves": false,
        "tm_compatibility_mode": "original",
        "tm_ensure_offensive": true,
        "randomize_field_items": false,
        "items_similar_value": false,
        "keep_capture_items": false,
        "randomize_shop_items": false,
        "shop_keep_capture_items": true,
        "legacy_shop_scope": false,
        "shop_keep_healing": true,
        "boss_stronger": false,
        "boss_team_variety": true,
        "boss_shadow_legendary_mode": "any",
        "boss_shadow_power_mode": "global",
        "boss_shadow_min_bst": 0
      }
    },
    "xd": {
      "application_version": "2.1.0",
      "engine_version": "xd-natural-encounter-moves-v17",
      "game_id": "GXXP01",
      "revision": 0,
      "source_sha256": "1cc438ed60e542991b8f1abea4617e67880f2568aceb513602051ca6f310e8c1",
      "source_iso_sha256": "1cc438ed60e542991b8f1abea4617e67880f2568aceb513602051ca6f310e8c1",
      "seed": "v210-natural-moves",
      "options": {
        "randomize_starter": true,
        "randomize_trainers": true,
        "randomize_shadows": true,
        "randomize_legendary_shadows": false,
        "randomize_tutorial_shadow": true,
        "randomize_poke_spots": true,
        "poke_spots_full_pokedex": true,
        "custom_poke_spot_shinies": true,
        "poke_spot_shiny_chance_percent": 5.0,
        "accessible_evolutions": true,
        "unique_shadow_families": true,
        "randomize_gifts": true,
        "randomize_hordel_gift": true,
        "stone_shops": true,
        "starter_species": 374,
        "starter_stage": "any",
        "starter_three_stage_families": false,
        "diverse_story_families": true,
        "balance_species": false,
        "allow_gen1": true,
        "allow_gen2": true,
        "allow_gen3": true,
        "allow_legendaries": false,
        "randomize_preserved_properties": false,
        "excluded_species": [],
        "excluded_types": [],
        "custom_shinies": true,
        "custom_shadow_shinies": true,
        "keep_shadow_lugia_after_purification": false,
        "shiny_chance_percent": 5.0,
        "trainer_theme_mode": "none",
        "trainer_force_evolved": false,
        "trainer_evolution_level": 40,
        "randomize_trainer_moves": "natural",
        "randomize_starter_moves": "natural",
        "randomize_gift_moves": "natural",
        "randomize_learnsets": false,
        "ensure_damaging_move": true,
        "ensure_stab_move": false,
        "no_duplicate_moves": true,
        "ban_self_destruct": true,
        "ban_ohko": true,
        "moves_mode": "chaos",
        "randomize_abilities": true,
        "abilities_family_consistent": true,
        "randomize_stats": false,
        "preserve_stat_totals": true,
        "randomize_types": false,
        "types_family_consistent": true,
        "randomize_held_items": false,
        "useful_held_items_only": true,
        "trainer_level_multiplier": 1.0,
        "progressive_levels": false,
        "early_level_multiplier": 1.0,
        "mid_level_multiplier": 1.0,
        "late_level_multiplier": 1.0,
        "capture_rate_multiplier": 1.0,
        "minimum_catch_rate": 0,
        "experience_multiplier": 1.0,
        "purification_multiplier": 1,
        "randomize_tm_moves": false,
        "tm_compatibility_mode": "original",
        "tm_ensure_offensive": true,
        "randomize_field_items": false,
        "randomize_shop_items": false,
        "shop_keep_healing": true,
        "shop_keep_capture_items": true,
        "items_similar_value": false,
        "keep_capture_items": false,
        "boss_stronger": false,
        "boss_team_variety": true,
        "boss_shadow_legendary_mode": "any",
        "boss_shadow_power_mode": "global",
        "boss_shadow_min_bst": 0
      }
    }
  }
}''')


def encoded(payload):
    return json.dumps(payload, ensure_ascii=False).encode('utf-8')


def resign(payload):
    payload.pop('configuration_sha256', None)
    payload['configuration_sha256'] = hashlib.sha256(profiles._canonical(payload)).hexdigest()
    return payload


def option_values(options):
    return json.loads(json.dumps(asdict(options)))


class RealV210ProfileMigrationTests(unittest.TestCase):
    def test_real_signed_profiles_keep_every_value_and_indicate_engine_migration(self):
        for name, fixture in EXPORTED['profiles'].items():
            payload = fixture['profile']
            parser = profiles.parse_xd_profile if name.startswith('xd') else profiles.parse_profile
            with self.subTest(profile=name):
                result = parser(encoded(payload))
                self.assertEqual(option_values(result.options), payload['options'])
                self.assertEqual(result.seed, payload['seed'])
                self.assertEqual(result.source_engine_version, payload['engine_version'])
                self.assertTrue(result.engine_migration)
                self.assertIs(type(result.options.randomize_starter_moves),
                              bool if name.endswith('random') else str)
                self.assertEqual(result.options.randomize_starter_moves,
                                 True if name.endswith('random') else 'natural')
                if name.endswith('natural'):
                    self.assertTrue(result.options.randomize_preserved_properties)
                    self.assertIs(result.options.randomize_gift_moves, False)
                    self.assertEqual(result.options.shiny_chance_percent, 17.5)

    def test_real_creation_reports_keep_values_region_and_migration_in_both_games(self):
        for name, payload in EXPORTED['reports'].items():
            with self.subTest(game=name):
                report = profiles.parse_creation_report(encoded(payload), is_xd=name == 'xd')
                self.assertEqual(option_values(report.profile.options), payload['options'])
                self.assertEqual(report.profile.seed, payload['seed'])
                self.assertEqual(report.region.game_id, payload['game_id'])
                self.assertEqual(report.source_sha256, payload['source_sha256'])
                self.assertTrue(report.profile.engine_migration)

    def test_export_after_migration_uses_current_engine_without_changing_settings(self):
        for name, fixture in EXPORTED['profiles'].items():
            parser = profiles.parse_xd_profile if name.startswith('xd') else profiles.parse_profile
            old = parser(encoded(fixture['profile']))
            current = profiles.configuration_data(old.seed, old.options)
            with self.subTest(profile=name):
                self.assertNotEqual(current['engine_version'], fixture['profile']['engine_version'])
                parsed = parser(encoded(current))
                self.assertFalse(parsed.engine_migration)
                self.assertEqual(parsed.seed, old.seed)
                self.assertEqual(parsed.options, old.options)

    def test_historical_challenge_codes_still_require_the_exact_engine(self):
        for name, fixture in EXPORTED['profiles'].items():
            with self.subTest(profile=name), self.assertRaises(UserError):
                decode_challenge(fixture['challenge'])

    def test_signature_and_complete_preserved_properties_field_remain_required(self):
        for name, fixture in EXPORTED['profiles'].items():
            parser = profiles.parse_xd_profile if name.startswith('xd') else profiles.parse_profile
            changed = deepcopy(fixture['profile'])
            changed['options']['randomize_preserved_properties'] = not changed['options']['randomize_preserved_properties']
            with self.subTest(tampered=name), self.assertRaises(UserError):
                parser(encoded(changed))
            missing = deepcopy(fixture['profile'])
            del missing['options']['randomize_preserved_properties']
            resign(missing)
            with self.subTest(missing=name), self.assertRaises(UserError):
                parser(encoded(missing))

    def test_unknown_versions_and_damaged_report_identity_are_not_migrated(self):
        for name, fixture in EXPORTED['profiles'].items():
            parser = profiles.parse_xd_profile if name.startswith('xd') else profiles.parse_profile
            unknown = deepcopy(fixture['profile'])
            unknown['engine_version'] = 'future-unknown-engine'
            resign(unknown)
            with self.subTest(engine=name), self.assertRaises(UserError):
                parser(encoded(unknown))
            if not name.startswith('xd'):
                unknown = deepcopy(fixture['profile'])
                unknown['app_version'] = '999.0.0'
                resign(unknown)
                with self.subTest(app=name), self.assertRaises(UserError):
                    parser(encoded(unknown))
        for name, fixture in EXPORTED['reports'].items():
            unknown = deepcopy(fixture)
            unknown['source_iso_sha256'] = '0' * 64
            with self.subTest(report=name), self.assertRaises(UserError):
                profiles.parse_creation_report(encoded(unknown), is_xd=name == 'xd')


if __name__ == '__main__':
    unittest.main()
