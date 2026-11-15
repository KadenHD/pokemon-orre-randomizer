"""Execute DNA-only Lugia displays against saved identity and native state."""
from dataclasses import replace
from pathlib import Path
import hashlib
import struct
import unittest

from orre_randomizer.engine.dna_lab import (
    _DNA_MODEL, _DNA_SHINY, _SAMPLE_SPECIES, _model_constructor, dna_shadow_lugia_samples,
)
from orre_randomizer.engine.dna_keypad import (
    DNA_KEYPAD_SPECIES, _ATLAS_DESCRIPTOR, _ATLAS_OFFSET, _ATLAS_SIGNATURE, _KEYPAD_DAT_SIZE,
    _SPINDA_KEYPAD_MARKER, _TILE_ORIGINS, _atlas_block_offset,
)
from orre_randomizer.engine.dna_keypad_runtime import _ATLAS_BYTES, _lugia_keypad_hook
from orre_randomizer.engine.dol_regions import PAL
from orre_randomizer.engine.gift_move_hooks import branch
from orre_randomizer.engine.postgame_lugia_model import _SAVED_IDENTITIES
from tests.test_shiny_rules import Machine, PID_GENERATOR, is_shiny
from tests.test_xd_shadow_shinies import ADDRESS, RETURN, WrapperMachine


POKEMON, PLAYER, DAT = 0x80602000, 0x80603000, 0x80900000
OWNER = 0xAABBCCDD
READERS = _SAVED_IDENTITIES[PAL.game_id]


def personality(shiny):
    high = 0xDEAD
    low = high ^ (OWNER >> 16) ^ (OWNER & 0xFFFF) ^ (0 if shiny else 8)
    return high << 16 | low


class AnalyzerMachine(Machine):
    native_targets = READERS

    def __init__(self, payload, *, generated=True, purified=False, shiny=True):
        super().__init__(payload, ADDRESS)
        self.generated, self.purified, self.shiny = generated, purified, shiny

    def native(self, target):
        arguments = self.reg[3:8].copy()
        self.calls.append((target, arguments))
        if target == PID_GENERATOR:
            pointer, species = arguments[:2]
            self.write(pointer, species, 2)
            self.write(pointer + 4, 0xABCD2397)
            self.write(pointer + 0x14, 0x018923C7)
            self.write(pointer + 0xD8, 0, 2)
            self.write(pointer + 0xDC, 0)
            result = 0xDECADE01
        else:
            if arguments[0] != 19:
                raise AssertionError('Reader used another sample Shadow ID')
            result = personality(self.shiny) if target == READERS[0] else (
                int(self.generated) if target == READERS[1] else int(self.purified))
        for register in (0, *range(3, 13)):
            self.reg[register] = 0xDEAD0000 + register
        self.reg[3] = result


class LugiaAnalyzerTests(unittest.TestCase):
    def test_temporary_hologram_uses_actual_shadow_id_saved_palette_and_purified_sentinel(self):
        region = replace(PAL, native_constructor=PID_GENERATOR)
        for generated in (False, True):
            for purified in (False, True):
                for shiny in (False, True):
                    with self.subTest(generated=generated, purified=purified, shiny=shiny):
                        machine = AnalyzerMachine(_model_constructor(ADDRESS, region, {}, None,
                            shadow_lugia_samples={153: 19}), generated=generated,
                            purified=purified, shiny=shiny)
                        # The stored sample hint deliberately opposes the real
                        # specimen. An existing saved PID must take priority.
                        hinted = not shiny
                        marker = 249 | 1 << 9 | _DNA_MODEL | (_DNA_SHINY if hinted else 0)
                        machine.reg[3:8] = [POKEMON, marker, 10, 0, 0]
                        machine.write(PAL.player_pointer, PLAYER)
                        machine.write(PLAYER + 0x9C, OWNER)
                        before = machine.reg.copy()
                        machine.run()
                        self.assertEqual(machine.reg[3], 0xDECADE01)
                        self.assertEqual(machine.read(POKEMON, 2), 249)
                        self.assertEqual(machine.read(POKEMON + 0xD8, 2), 19)
                        self.assertEqual(machine.read(POKEMON + 0xDC), 0xFFFFFF9C if purified else 10)
                        pid, owner = machine.read(POKEMON + 4), machine.read(POKEMON + 0x14)
                        self.assertEqual(is_shiny(pid, owner), shiny if generated else hinted)
                        if generated:
                            self.assertEqual((pid, owner), (personality(shiny), OWNER))
                        self.assertEqual(machine.reg[1:3], before[1:3])
                        self.assertEqual(machine.reg[13:], before[13:])

    def test_lugia_without_an_actual_sample_identity_remains_never_shadow(self):
        region = replace(PAL, native_constructor=PID_GENERATOR)
        for species, sample in ((249, 0), (25, 0), (25, 1 << 9)):
            machine = AnalyzerMachine(_model_constructor(ADDRESS, region, {}, None,
                shadow_lugia_samples={153: 19}))
            # No sample-index tag: a plain species constructor must not inherit
            # the shadow identity just because its species happens to be Lugia.
            machine.reg[3:8] = [POKEMON, species | _DNA_MODEL | sample, 10, 0, 0]
            machine.run()
            self.assertEqual(machine.read(POKEMON + 0xD8, 2), 0)
            self.assertEqual([target for target, _ in machine.calls], [PID_GENERATOR])


class LugiaKeypadTests(unittest.TestCase):
    def run_keypad(self, *, generated, purified, shiny, keep, marker=_SPINDA_KEYPAD_MARKER):
        parser, flush, invalidate = 0x801962D8, 0x8009E7F8, 0x800BE89C
        tiles = {153: tuple(bytes([variant + 1]) * 8192 for variant in range(4))}
        hints = {153: (249, not shiny)}
        payload = _lugia_keypad_hook(ADDRESS, parser, None, flush, invalidate, PAL,
            {153: 19}, hints, tiles, keep_after_purification=keep)
        machine = WrapperMachine(payload)
        machine.reg[3:6] = [0x80700000, DAT, _KEYPAD_DAT_SIZE]
        machine.store(DAT + 0x18, marker, 4)
        for offset, value in enumerate(_ATLAS_SIGNATURE):
            machine.store(DAT + _ATLAS_DESCRIPTOR + offset * 4, value, 4)
        machine.store(PAL.player_pointer, PLAYER, 4)
        machine.store(PLAYER + 0x9C, OWNER, 4)
        machine.store(parser + 4, branch(parser + 4, RETURN), 4)

        def getter(value):
            def call(m):
                self.assertEqual(m.reg[3], 19)
                m.clobber_volatile()
                m.reg[3] = value
            return call

        def cache_flush(m):
            self.assertEqual(m.reg[3:5], [DAT + _ATLAS_OFFSET, _ATLAS_BYTES])
            m.clobber_volatile()

        machine.callbacks = {READERS[0]: getter(personality(shiny)),
            READERS[1]: getter(int(generated)), READERS[2]: getter(int(purified)),
            flush: cache_flush, invalidate: lambda m: m.clobber_volatile()}
        before = machine.reg.copy()
        original_record = {address: machine.memory.get(address) for address in range(PLAYER, PLAYER + 0x100)}
        machine.run(max_steps=20000)
        self.assertEqual(machine.reg[3:6], before[3:6])
        self.assertEqual(machine.reg[13:], before[13:])
        self.assertEqual(machine.reg[1], before[1] - 0x20)  # replayed retail parser prologue
        self.assertEqual(original_record, {address: machine.memory.get(address) for address in original_record})
        self.assertEqual(machine.load(DAT + 0x18, 4), marker)
        return machine, tiles

    def test_keypad_uses_the_same_saved_shiny_and_purification_policy_as_the_hologram(self):
        for generated in (False, True):
            for purified in (False, True):
                for shiny in (False, True):
                    for keep in (False, True):
                        with self.subTest(generated=generated, purified=purified, shiny=shiny, keep=keep):
                            machine, tiles = self.run_keypad(generated=generated, purified=purified,
                                shiny=shiny, keep=keep)
                            rare = shiny if generated else not shiny
                            variant = int(rare) + (2 if purified and not keep else 0)
                            origin = DAT + _atlas_block_offset(*_TILE_ORIGINS[DNA_KEYPAD_SPECIES.index(153)])
                            image = b''.join(bytes(machine.memory[origin + row * 4096 + col]
                                for col in range(512)) for row in range(16))
                            self.assertEqual(image, tiles[153][variant])
                            for row in range(16):
                                self.assertNotIn(origin + row * 4096 - 1, machine.memory)
                                self.assertNotIn(origin + row * 4096 + 512, machine.memory)

    def test_unrelated_dat_has_no_identity_calls_or_texture_writes(self):
        machine, _ = self.run_keypad(generated=True, purified=True, shiny=True,
            keep=True, marker=0)
        self.assertFalse(machine.calls)


class RegionalLugiaDnaTests(unittest.TestCase):
    def test_three_native_dols_and_rel_sample_ids_compose_with_both_retention_policies(self):
        from orre_randomizer.engine.dna_lab import patch_dna_analyzer
        from orre_randomizer.engine.dna_keypad_runtime import apply_dna_keypad_runtime, _lugia_tiles
        from orre_randomizer.engine.randomize_trainers import layout
        from orre_randomizer.engine.inspect_tables import u16
        from orre_randomizer.engine.dol_regions import dol_layout
        root = Path(__file__).resolve().parents[1]
        research = root / 'build/region-compat-2026-11-02'
        sources = [('pal', root / 'game/sys/main.dol'),
                   ('usa', research / 'dol-research/usa-main.dol'),
                   ('japan', research / 'dol-research/japan-main.dol')]
        required = [path for _, path in sources] + [
            research / 'rel-research' / region / 'common.fsys-common_rel.rel' for region, _ in sources]
        if not all(path.exists() for path in required) or not (root / 'game/files/DNA_key.fsys').is_file():
            self.skipTest('requires local three-region executable/REL extracts and original keypad resources')
        read = lambda name: (root / 'game/files' / name).read_bytes()
        appearances = {old: (249 if old == 153 else old, True) for old in _SAMPLE_SPECIES}
        tiles = _lugia_tiles(read, appearances, {153: 1})
        self.assertEqual(len({hashlib.sha256(image).digest() for image in tiles[153]}), 4)
        for tag, path in sources:
            original = path.read_bytes()
            digest = hashlib.sha256(original).hexdigest()
            rel = (research / 'rel-research' / tag / 'common.fsys-common_rel.rel').read_bytes()
            current = bytearray(rel)
            table = layout(rel)[0]['shadow']
            sid = next(index for index in range(1, table['count'])
                       if u16(rel, table['offset'] + index * table['stride'] + 2) == 153)
            struct.pack_into('>H', current, table['offset'] + sid * table['stride'] + 2, 249)
            metadata = dna_shadow_lugia_samples(rel, current, appearances)
            self.assertEqual(metadata, {153: sid})
            self.assertEqual(dna_shadow_lugia_samples(rel, rel, appearances), {})
            for keep in (False, True):
                with self.subTest(region=tag, keep=keep):
                    analyzer = patch_dna_analyzer(original, original, appearances,
                        shadow_lugia_samples=metadata)
                    from orre_randomizer.engine.dna_lab import _ANALYZER
                    draw = _ANALYZER[dol_layout(original).game_id][1] - 0x1B0
                    for relative in (0xAC, 0xB0, 0xB4, 0xE0, 0xE4, 0xE8):
                        offset = draw + relative - 0x80003000
                        self.assertEqual(analyzer[offset:offset+4], original[offset:offset+4])
                    output = apply_dna_keypad_runtime(original, analyzer, read, {}, None,
                        shadow_lugia_samples=metadata, appearances=appearances,
                        keep_after_purification=keep)
                    region = dol_layout(original)
                    parser = 0x801962D8 if tag == 'pal' else 0x80191F64 if tag == 'usa' else 0x8018DB28
                    old_word = original[parser - 0x80003000:parser - 0x80003000 + 4]
                    self.assertNotEqual(output[parser - 0x80003000:parser - 0x80003000 + 4], old_word)
                    self.assertGreater(len(output), len(analyzer))
                    self.assertEqual(len(output) % 32, 0)
                    self.assertEqual(hashlib.sha256(path.read_bytes()).hexdigest(), digest)


if __name__ == '__main__':
    unittest.main()
