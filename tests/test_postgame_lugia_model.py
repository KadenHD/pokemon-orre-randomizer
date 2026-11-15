"""Execute specimen-specific Lugia displays while preserving native identities."""
import hashlib
import json
from pathlib import Path
import struct
import unittest

from orre_randomizer.engine.analyze_game import FormatError, u32
from orre_randomizer.engine.postgame_lugia_model import (
    ASSET, MODEL_MARKER, NATIVE_LUGIA_MARKER, RESOURCE_ID, SHINY_RESOURCE_ID, _battle_identity_selector,
    _identity_selector, _resource_selector, convert_xd_model,
)
from tests.test_shiny_rules import Machine

ADDRESS, LOADER, POKEMON = 0x80500020, 0x801DE190, 0x80600000


class BonusLugiaModelTests(unittest.TestCase):
    def test_target_views_use_the_saved_identity_when_transient_shadow_fields_are_missing(self):
        from orre_randomizer.engine.gift_move_hooks import branch
        from tests.test_xd_shadow_shinies import ADDRESS as STUB, RETURN, WrapperMachine
        saved, generated, purified = 0x80100100, 0x80100200, 0x80100300
        for requested, saved_value, exists, done, model, expected in (
                (0xCF9DE894, 0xCF9DE894, True, False, 249, True),
                (0, 0, True, False, 249, True),
                (0, 0, False, False, 249, False),
                (0xCF9DE894, 0xCF9DE894, True, True, 249, False),
                (0x12345678, 0xCF9DE894, True, False, 249, False),
                (0xCF9DE894, 0xCF9DE894, True, False, 0x19D, False)):
            with self.subTest(requested=requested, exists=exists, done=done, model=model):
                machine = WrapperMachine(_resource_selector(STUB, LOADER, 0x800D84B0, 0x16E,
                                                            (saved, generated, purified)))
                machine.reg[3], machine.reg[26:30] = model, [model, requested, 1, 0]
                machine.reg[13] = 0x80480000
                machine.store(machine.reg[13] - 0x7B50, 417, 4)
                for exit_at in (LOADER + 0x2C, LOADER + 0x14C):
                    machine.store(exit_at, branch(exit_at, RETURN), 4)
                before, memory = machine.reg.copy(), machine.memory.copy()

                def getter(value):
                    def callback(m):
                        self.assertEqual(m.reg[3], 96)
                        m.clobber_volatile()
                        m.reg[3] = value
                    return callback

                machine.callbacks.update({saved: getter(saved_value), generated: getter(int(exists)),
                                          purified: getter(int(done))})
                machine.run()
                self.assertEqual(machine.reg[27:29], before[27:29])
                self.assertEqual(machine.reg[13:26], before[13:26])
                self.assertEqual(machine.memory, memory)
                if expected:
                    self.assertEqual(machine.reg[29:32], [1, SHINY_RESOURCE_ID, 0x16E])
                else:
                    self.assertEqual(machine.reg[3], model)
                    self.assertEqual(machine.reg[29:32], before[29:32])
                if model != 249:
                    self.assertFalse(machine.calls)

    def test_reduced_views_search_only_configured_lugia_slots_and_follow_purification_policy(self):
        from orre_randomizer.engine.gift_move_hooks import branch
        from tests.test_xd_shadow_shinies import ADDRESS as STUB, RETURN, WrapperMachine
        readers = (0x80100100, 0x80100200, 0x80100300)
        candidates = (17, 44, 96)
        pid = 0xA234BCDE
        for keep in (False, True):
          for done in (False, True):
            for target in (17, 44, 96, 0):
                with self.subTest(keep=keep, purified=done, target=target):
                    machine = WrapperMachine(_resource_selector(STUB, LOADER, 0x800D84B0,
                        0x16E, readers, keep_after_purification=keep, shadow_ids=candidates))
                    machine.reg[3], machine.reg[26:30] = 249, [249, pid, 1, 0]
                    machine.reg[13] = 0x80480000
                    machine.store(machine.reg[13]-0x7B50, 417, 4)
                    for at in (LOADER+0x2C, LOADER+0x14C):
                        machine.store(at, branch(at, RETURN), 4)
                    memory, before = machine.memory.copy(), machine.reg.copy()

                    def reader(kind):
                        def callback(m):
                            sid=m.reg[3]
                            self.assertIn(sid, candidates)
                            result = (pid if sid == target else 0x12340000+sid) if kind == 0 else 1 if kind == 1 else int(done)
                            m.clobber_volatile()
                            m.reg[3]=result
                        return callback

                    machine.callbacks.update({address:reader(i)for i,address in enumerate(readers)})
                    machine.run(max_steps=500)
                    dark=target in candidates and (keep or not done)
                    self.assertEqual(machine.reg[29:32], [1, SHINY_RESOURCE_ID, 0x16E] if dark else before[29:32])
                    self.assertEqual(machine.reg[13:26], before[13:26])
                    self.assertEqual(machine.reg[27:29], before[27:29])
                    self.assertEqual(machine.memory, memory)
                    if keep:
                        self.assertNotIn(readers[2], [at for at,_ in machine.calls])

    def test_explicit_ordinary_lugia_bypasses_shadow_pid_lookup_even_when_pid_collides(self):
        from orre_randomizer.engine.gift_move_hooks import branch
        from tests.test_xd_shadow_shinies import ADDRESS as STUB, RETURN, WrapperMachine
        for keep in (False, True):
            machine=WrapperMachine(_resource_selector(STUB, LOADER, 0x800D84B0, 0x16E,
                (0x80100100,0x80100200,0x80100300), keep_after_purification=keep,
                shadow_ids=(1,17,96)))
            machine.reg[3]=machine.reg[26]=NATIVE_LUGIA_MARKER
            machine.reg[27:30]=[0xCF9DE894,1,0]
            machine.reg[13]=0x80480000
            machine.store(machine.reg[13]-0x7B50,417,4)
            machine.store(LOADER+0x2C,branch(LOADER+0x2C,RETURN),4)
            machine.run()
            self.assertFalse(machine.calls)
            self.assertEqual((machine.reg[3],machine.reg[26]),(249,249))
            self.assertEqual(machine.reg[27:30],[0xCF9DE894,1,0])

    def test_display_policy_rejects_non_native_shadow_identifiers(self):
        from orre_randomizer.engine.postgame_lugia_model import install_postgame_lugia_model
        for ids in ((0,),(-1,),(97,),(True,),('44',),(44,'96')):
            with self.subTest(ids=ids),self.assertRaises(FormatError):
                install_postgame_lugia_model(None,None,None,{},shadow_ids=ids)
        with self.assertRaises(FormatError):
            install_postgame_lugia_model(None,None,None,{},keep_after_purification=1)

    def test_every_valid_shadow_lugia_uses_its_own_shiny_status_and_purification_policy(self):
        for species, shadow, gauge in (
                    (249, 96, 200), (249, 96, 0), (249, 96, -100),
                    (249, 1, 5000), (249, 44, 0), (249, 44, -100),
                    (249, 0, 0), (249, 0, -100), (249, 97, 0),
                    (249, 65535, 5000), (250, 96, 0)):
            for keep in (False, True):
                for shiny in (False, True):
                    with self.subTest(species=species, shadow=shadow, gauge=gauge, shiny=shiny, keep=keep):
                        machine = Machine(_identity_selector(ADDRESS, LOADER, keep_after_purification=keep), ADDRESS)
                        pointer = POKEMON
                        machine.reg[31] = POKEMON
                        machine.reg[3:6] = [249, 0x12345678, int(shiny)]
                        machine.write(pointer, species, 2)
                        machine.write(pointer + 0xD8, shadow, 2)
                        machine.write(pointer + 0xDC, gauge)
                        before = machine.reg.copy()
                        memory = machine.mem.copy()
                        machine.run(stop=LOADER)
                        dark = species == 249 and 1 <= shadow <= 96 and (keep or gauge != -100)
                        expected = MODEL_MARKER if dark else NATIVE_LUGIA_MARKER if species == 249 else 249
                        self.assertEqual(machine.reg[3], expected)
                        self.assertEqual(machine.reg[4:6], before[4:6])
                        self.assertEqual(machine.reg[13:], before[13:])
                        self.assertEqual(machine.mem, memory)

    def test_battle_uses_full_native_record_instead_of_incomplete_stack_bios(self):
        from tests.test_xd_shadow_shinies import ADDRESS as STUB, RETURN, WrapperMachine
        getter, battle, context = 0x80100010, 0x80610000, 0x80611000
        for species, shadow, gauge, keep in ((249, 96, 5000, False), (249, 96, -100, False),
                (249, 1, 5000, False), (249, 44, -100, True), (249, 44, -100, False),
                (249, 0, -100, True), (249, 0, 0, True), (249, 97, 0, True),
                (250, 96, 5000, False)):
            machine = WrapperMachine(_battle_identity_selector(STUB, RETURN, getter,
                                                             keep_after_purification=keep))
            machine.reg[3:6] = [249, 0x12345678, 1]
            machine.reg[30] = battle
            machine.store(POKEMON, species, 2)
            machine.store(POKEMON + 0xD8, shadow, 2)
            machine.store(POKEMON + 0xDC, gauge, 4)
            # The real battle's stack BIOS has species/PID but no Shadow ID.
            machine.store(machine.reg[1] + 0x10 + 0xD8, 0, 2)
            before = machine.reg.copy()

            def native_getter(m):
                pointer, zero, field, unused = m.reg[3:7]
                self.assertEqual((zero, unused), (0, 0))
                self.assertIn((pointer, field), ((battle, 0xD6), (context, 0xCC)))
                value = context if field == 0xD6 else POKEMON
                m.clobber_volatile()
                m.reg[3] = value

            machine.callbacks[getter] = native_getter
            machine.run()
            dark = species == 249 and 1 <= shadow <= 96 and (keep or gauge != -100)
            expected = MODEL_MARKER if dark else NATIVE_LUGIA_MARKER if species == 249 else 249
            self.assertEqual(machine.reg[3], expected)
            self.assertEqual(machine.reg[4:6], before[4:6])
            self.assertEqual(machine.reg[13:], before[13:])
            self.assertEqual(machine.reg[1:3], before[1:3])
            self.assertEqual(machine.load(POKEMON + 0xD8, 2), shadow)
            self.assertEqual(machine.load(POKEMON + 0xDC, 4), gauge & 0xFFFFFFFF)
        machine = WrapperMachine(_battle_identity_selector(STUB, RETURN, getter))
        machine.reg[3:6] = [0x19D, 0x12345678, 1]  # the native Substitute model
        machine.reg[30] = battle
        machine.run()
        self.assertEqual(machine.reg[3], 0x19D)
        self.assertFalse(machine.calls)
        for out_pointer, context_pointer, pokemon_pointer in ((0, context, POKEMON),
                                                               (battle, 0, POKEMON), (battle, context, 0)):
            machine = WrapperMachine(_battle_identity_selector(STUB, RETURN, getter))
            machine.reg[3:6] = [249, 0x12345678, 1]
            machine.reg[30] = out_pointer

            def missing_record(m):
                value = context_pointer if m.reg[5] == 0xD6 else pokemon_pointer
                m.clobber_volatile()
                m.reg[3] = value

            machine.callbacks[getter] = missing_record
            machine.run()
            self.assertEqual(machine.reg[3:6], [249, 0x12345678, 1])

    def test_null_menu_pokemon_keeps_native_model(self):
        machine = Machine(_identity_selector(ADDRESS, LOADER), ADDRESS)
        machine.reg[31], machine.reg[3] = 0, 249
        machine.run(stop=LOADER)
        self.assertEqual(machine.reg[3], 249)

    def test_asynchronous_requests_keep_explicit_ordinary_and_dark_markers_without_mutating_the_pokemon(self):
        for gauge in (5000, 0, -100):
            machine = Machine(_identity_selector(ADDRESS, LOADER, return_marker=True), ADDRESS)
            machine.reg[31] = POKEMON
            machine.reg[3:7] = [0, 249, 0x66, 0]
            machine.write(POKEMON, 249, 2)
            machine.write(POKEMON + 0xD8, 96, 2)
            machine.write(POKEMON + 0xDC, gauge)
            before = machine.mem.copy()
            machine.run(stop=machine.lr)
            self.assertEqual(machine.reg[3], NATIVE_LUGIA_MARKER if gauge == -100 else MODEL_MARKER)
            self.assertEqual(machine.reg[4:7], [249, 0x66, 0])
            self.assertEqual(machine.mem, before)

    def test_purification_display_uses_final_colors_before_the_cached_clone_is_updated(self):
        # Retail loads this model before its ceremony sets the native purified
        # flag. Waiting for the copied gauge/flag would leave its cached dark
        # model alive through the post-purification messages.
        for shadow in (0, 19, 96):
            for gauge in (0, -100):
                for native_purified in (False, True):
                    for keep in (False, True):
                        for shiny in (False, True):
                            with self.subTest(shadow=shadow, gauge=gauge,
                                    purified=native_purified, keep=keep, shiny=shiny):
                                machine = Machine(_identity_selector(ADDRESS, LOADER,
                                    return_marker=True, keep_after_purification=keep,
                                    force_ordinary=not keep), ADDRESS)
                                machine.reg[31] = POKEMON
                                machine.reg[3:7] = [0, 249, 0x66, 0]
                                machine.write(POKEMON, 249, 2)
                                owner = 0x018923C7
                                pid = 0xABCD0000 | (0xABCD ^ (owner >> 16) ^ (owner & 0xFFFF)
                                                    ^ (2 if shiny else 24))
                                machine.write(POKEMON + 4, pid)
                                machine.write(POKEMON + 0x14, 0x018923C7)
                                machine.write(POKEMON + 0xD8, shadow, 2)
                                machine.write(POKEMON + 0xDC, gauge)
                                machine.write(0x80690000, int(native_purified))
                                before, memory = machine.reg.copy(), machine.mem.copy()
                                machine.run(stop=machine.lr)
                                self.assertEqual(machine.reg[3], MODEL_MARKER if keep and shadow
                                                 else NATIVE_LUGIA_MARKER)
                                self.assertEqual(machine.reg[4:11], before[4:11])
                                self.assertEqual(machine.reg[12:], before[12:])
                                self.assertEqual(machine.mem, memory)
                                self.assertFalse(machine.calls)

    def test_marker_selects_dedicated_dark_resource_and_native_calls_keep_the_bounds_check(self):
        for marker in (249, MODEL_MARKER, NATIVE_LUGIA_MARKER, 0x19D):
            for shiny in (False, True):
                machine = Machine(_resource_selector(ADDRESS, LOADER, 0x800D84B0, 0x16E), ADDRESS)
                machine.reg[3], machine.reg[26] = marker, marker
                machine.reg[28] = int(shiny)
                machine.reg[13] = 0x80480000
                machine.write(machine.reg[13] - 0x7B50, 417)
                machine.run(stop=LOADER + (0x14C if marker == MODEL_MARKER else 0x2C))
                if marker == MODEL_MARKER:
                    self.assertEqual(machine.reg[30:32], [SHINY_RESOURCE_ID if shiny else RESOURCE_ID, 0x16E])
                    self.assertEqual(machine.reg[26], 249)
                    self.assertEqual(machine.reg[29], 1)
                else:
                    self.assertEqual(machine.reg[0], 417)
                    self.assertEqual(machine.reg[26], 249 if marker == NATIVE_LUGIA_MARKER else marker)
                self.assertEqual(machine.reg[28], int(shiny))

    def test_conversion_preserves_xd_dat_but_adapts_timing_and_track_kinds(self):
        source = bytearray(0xE60 + 0x80)
        struct.pack_into(">I", source, 0, 0x71)
        struct.pack_into(">I", source, 0x20, 0xFFFFFFFF)
        struct.pack_into(">I", source, 0x10, 17)
        for index in range(17):
            row = 0x84 + index * 0xD0
            struct.pack_into(">IIIff", source, row, 2, 1, 16 if index == 0 else 0, 0.0, 118 / 60)
            kind = 0 if 11 <= index <= 15 else 2 if index in (0, 16) else 1
            struct.pack_into(">II", source, row + 0x8C, kind, index % 9)
            struct.pack_into(">I", source, row + 0x50, 0x12345678)
        source[0xE60:] = bytes((i * 31) & 255 for i in range(0x80))
        struct.pack_into(">I", source, 0xE60, 0x71)
        template = bytearray(0x40 + 17 * 0xD0)
        struct.pack_into(">I", template, 8, 17)
        struct.pack_into(">I", template, 0x10, 5)
        converted = convert_xd_model(bytes(source), bytes(template))
        self.assertEqual(converted[0x40:0xC0], source[0xE60:])
        for index in range(17):
            row = 0xC0 + index * 0xD0
            self.assertEqual(u32(converted, row + 0x10), 118)
            self.assertEqual(u32(converted, row + 0x8C), int(11 <= index <= 15))
            self.assertEqual(u32(converted, row + 0x90), index % 9)
            self.assertEqual(u32(converted, row + 8), 0)
            self.assertEqual(u32(converted, row + 0x50), 0x12345678)
        self.assertEqual(u32(converted, 0), 0x71)
        self.assertEqual(len(converted) % 32, 0)
        with self.assertRaises(FormatError):
            convert_xd_model(bytes(source[:-32]), bytes(template))
        struct.pack_into(">f", source, 0x94, float("nan"))
        with self.assertRaises(FormatError):
            convert_xd_model(bytes(source), bytes(template))

    def test_bundled_model_has_verified_provenance_and_a_valid_native_container(self):
        pack = Path(__file__).resolve().parents[1] / "orre_randomizer/assets/game"
        if not (pack / ASSET).is_file():
            self.skipTest("optional game resource pack is not present")
        manifest = json.loads((pack / "models/manifest.json").read_text("utf-8"))
        model = (pack / ASSET).read_bytes()
        self.assertEqual(len(model), manifest["converted_bytes"])
        self.assertEqual(hashlib.sha256(model).hexdigest(), manifest["converted_sha256"])
        self.assertEqual(manifest["source"]["game_id"], "GXXP01")
        self.assertEqual(u32(model, 8), 17)
        self.assertEqual(u32(model, 0x40), u32(model, 0))
        metadata = 0x40 + ((u32(model, 0) + 31) & ~31)
        self.assertEqual(u32(model, metadata + 0x10), 118)
        self.assertEqual(u32(model, metadata + 16 * 0xD0 + 0x8C), 0)
        self.assertEqual(u32(model, metadata + 16 * 0xD0 + 0x90), 8)
        for index in range(17):
            row = metadata + index * 0xD0
            self.assertLessEqual(max(u32(model, row + 0x0C + n * 4)
                                     for n in range(u32(model, row))), 3600 * 60)


class RegionalLugiaHookTests(unittest.TestCase):
    def test_retail_windows_accept_generic_and_retained_displays_without_unrelated_dol_changes(self):
        from orre_randomizer.engine.dol_regions import dol_layout
        from orre_randomizer.engine.gift_move_hooks import TEXT_TO_RAM
        from orre_randomizer.engine.postgame_lugia_model import _LAYOUTS, _install_hooks
        root=Path(__file__).resolve().parents[1]
        research=root/'build/region-compat-2026-11-02/dol-research'
        paths=(root/'game/sys/main.dol',research/'usa-main.dol',research/'japan-main.dol')
        available=[p for p in paths if p.is_file()]
        if len(available)!=3:
            self.skipTest('requires three local original Colosseum executable extracts')
        for path in available:
            original=path.read_bytes()
            before=hashlib.sha256(original).hexdigest()
            region=dol_layout(original)
            group=u32(original,_LAYOUTS[region.game_id][3]+249*12)
            for keep in (False,True):
                with self.subTest(region=region.game_id,keep=keep):
                    output,hooks=_install_hooks(original,original,group,
                        keep_after_purification=keep,shadow_ids=(1,17,44,96))
                    self.assertEqual(len(hooks),18)
                    self.assertEqual(len({h['address']for h in hooks}),18)
                    allowed={8,0x50,0x98,region.set_arena_lo-TEXT_TO_RAM}
                    allowed.update(h['address']-TEXT_TO_RAM for h in hooks)
                    changed={i for i,(a,b)in enumerate(zip(original,output))if a!=b}
                    self.assertTrue(changed)
                    self.assertTrue(all(any(start<=i<start+4 for start in allowed)for i in changed))
                    self.assertGreater(len(output),len(original))
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(),before)


if __name__ == "__main__":
    unittest.main()
