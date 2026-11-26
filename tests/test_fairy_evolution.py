"""Instruction/ABI proofs, separate from actual Dolphin evolution validation."""
from pathlib import Path
import hashlib
import struct
import unittest
from unittest.mock import patch

from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.fairy_data import learning_records
from orre_randomizer.fairy_evolution import (
    EVOLUTION_EVENTS, QUEUE_CAPACITY, _LAYOUTS, _queue_stub,
    install_evolution_learning, qualify_evolution_learning,
)
from orre_randomizer.fairy_gameplay import NATIVE_MOVE_MAP
from tests.test_deoxys_meteorite import ItemMachine, MASK

ROOT = Path(__file__).resolve().parents[1]
BASE, CONTINUE, CHECKER, POKEMON, QUEUE = 0x81500020, 0x80100004, 0x80100200, 0x80600000, 0x80610000


class EvolutionMachine(ItemMachine):
    def __init__(self, species, owner=27, *, pending=(), known=(), count=None):
        super().__init__(_queue_stub(BASE, CONTINUE, CHECKER, owner), BASE)
        self.native_targets = {CHECKER}
        self.known = tuple(known)
        self.reg[owner], self.reg[30], self.reg[31] = POKEMON, QUEUE, len(pending) if count is None else count
        self.write(POKEMON, species, 2)
        self.write(QUEUE - 2, 0xBEEF, 2)
        for i in range(QUEUE_CAPACITY):
            self.write(QUEUE + i * 2, pending[i] if i < len(pending) else 0xDEAD, 2)
        self.write(QUEUE + QUEUE_CAPACITY * 2, 0xCAFE, 2)

    def native(self, target):
        record, move = self.reg[3:5]
        self.calls.append((target, record, move))
        assert record == POKEMON
        result = self.known.index(move) if move in self.known else -1
        for i in (0, *range(3, 13)):
            self.reg[i] = 0xDEAD0000 | i
        self.reg[3] = result & MASK


class EvolutionQueueContract(unittest.TestCase):
    def execute(self, species, owner=27, **kwargs):
        machine = EvolutionMachine(species, owner, **kwargs)
        before, link, memory = machine.reg.copy(), machine.lr, dict(machine.mem)
        machine.run(stop=CONTINUE)
        self.assertEqual(machine.reg[1], before[1])
        self.assertEqual(machine.lr, link)
        self.assertEqual(machine.reg[14:31], before[14:31])
        self.assertEqual(machine.reg[3], machine.reg[31])
        self.assertEqual(machine.read(POKEMON, 2), species)
        self.assertEqual(machine.read(QUEUE - 2, 2), 0xBEEF)
        self.assertEqual(machine.read(QUEUE + QUEUE_CAPACITY * 2, 2), 0xCAFE)
        # Only the private stack and a single appended halfword can change.
        changed = {address for address, value in machine.mem.items() if memory.get(address) != value}
        permitted = set(range(before[1] - 32, before[1] + 8))
        if machine.reg[31] > before[31]:
            permitted.update(range(QUEUE + before[31] * 2, QUEUE + before[31] * 2 + 2))
        self.assertLessEqual(changed, permitted)
        return machine

    def test_events_are_only_the_two_sourced_level_zero_records(self):
        expected = []
        for native, national in ((176, 176), (394, 282)):
            expected.extend((native, NATIVE_MOVE_MAP[row['move']]) for row in learning_records(national)
                            if row['method'] == 1 and row['level'] == 0)
        self.assertEqual(tuple(expected), EVOLUTION_EVENTS)

    def test_every_evolved_species_and_native_register_allocation(self):
        events = dict(EVOLUTION_EVENTS)
        for owner in (27, 29):
            for species in range(415):
                with self.subTest(species=species, owner=owner):
                    machine = self.execute(species, owner, pending=(1, 2, 3))
                    event = events.get(species)
                    self.assertEqual(machine.reg[31], 3 + (event is not None))
                    self.assertEqual(len(machine.calls), int(event is not None))
                    if event is not None:
                        self.assertEqual(machine.read(QUEUE + 6, 2), event)
                        self.assertEqual(machine.calls, [(CHECKER, POKEMON, event)])

    def test_existing_moves_and_pending_duplicates_are_never_offered_twice(self):
        for owner in (27, 29):
            for species, move in EVOLUTION_EVENTS:
                for slot in range(4):
                    known = [1, 2, 3, 4]
                    known[slot] = move
                    machine = self.execute(species, owner, pending=(1, 2), known=known)
                    self.assertEqual(machine.reg[31], 2)
                for slot in range(19):
                    pending = list(range(1, 20)); pending[slot] = move
                    machine = self.execute(species, owner, pending=pending)
                    self.assertEqual(machine.reg[31], 19)
                    self.assertEqual(machine.calls, [])

    def test_queue_capacity_zero_through_twenty_and_malformed_counts(self):
        for owner in (27, 29):
            for species, move in EVOLUTION_EVENTS:
                for count in range(21):
                    machine = self.execute(species, owner, pending=tuple(range(1, count + 1)))
                    self.assertEqual(machine.reg[31], min(20, count + 1))
                    self.assertEqual(len(machine.calls), int(count < 20))
                    if count < 20:
                        self.assertEqual(machine.read(QUEUE + count * 2, 2), move)
                for count in (21, 0xFFFFFFFF):
                    machine = self.execute(species, owner, count=count)
                    self.assertEqual(machine.reg[31], count)
                    self.assertEqual(machine.calls, [])

    def test_invalid_region_or_register_is_rejected(self):
        for game in ('GC6P01', 'GXXJ01', 'other'):
            with self.assertRaises(FormatError):
                qualify_evolution_learning(b'foreign original', game)
        for owner in (3, 26, 28, 30):
            with self.assertRaises(ValueError):
                _queue_stub(BASE, CONTINUE, CHECKER, owner)


PATHS = {
    'GC6P01': 'game/sys/main.dol',
    'GC6E01': 'build/hd-completion/hud/GC6E01.dol',
    'GC6J01': 'build/hd-completion/hud/GC6J01.dol',
    'GXXP01': 'build/xd-validation/eu/main.dol',
    'GXXE01': 'build/xd-validation/us/main.dol',
    'GXXJ01': 'build/xd-validation/jp/main.dol',
}


@unittest.skipUnless(all((ROOT / path).is_file() for path in PATHS.values()), 'requires local original DOLs')
class EvolutionRetailPreflight(unittest.TestCase):
    def test_six_originals_install_exactly_one_success_return_hook_and_preserve_sources(self):
        from orre_randomizer.deoxys_meteorite import _offset, _read
        for game, path in PATHS.items():
            with self.subTest(game=game):
                original = (ROOT / path).read_bytes()
                digest = hashlib.sha256(original).hexdigest()
                layout = qualify_evolution_learning(original, game)
                with patch('orre_randomizer.fairy_tms.read_installed_content',
                           return_value={'moves': {378: bytes(56), 380: bytes(56)}}):
                    patched, report = install_evolution_learning(original, original, game,
                        additional_tms_report={'game_id': game})
                self.assertEqual(hashlib.sha256((ROOT / path).read_bytes()).hexdigest(), digest)
                self.assertEqual(report['queue_capacity'], 20)
                self.assertEqual(report['pokemon_register'], 29 if game == 'GXXJ01' else 27)
                for key in ('level_zero_terminators_preserved', 'native_learning_dialogue',
                            'native_evolution_cancel_and_commit_preserved', 'no_direct_pokemon_writes'):
                    self.assertTrue(report[key])
                site = _offset(original, layout['hook_address'])
                self.assertNotEqual(patched[site:site + 4], original[site:site + 4])
                # The entire prepare function differs only at its successful
                # return; error exits still bypass the injected event queue.
                begin, size = layout['producer_address'], layout['producer_size']
                before, after = _read(original, begin, size), bytearray(_read(patched, begin, size))
                relative = layout['hook_address'] - begin
                after[relative:relative + 4] = before[relative:relative + 4]
                self.assertEqual(after, before)
                with patch('orre_randomizer.fairy_tms.read_installed_content',
                           return_value={'moves': {378: bytes(56), 380: bytes(56)}}):
                    with self.assertRaisesRegex(FormatError, 'already been modified'):
                        install_evolution_learning(original, patched, game,
                            additional_tms_report={'game_id': game})
                    foreign = bytearray(original)
                    known_position = _offset(original, layout['known_move_checker'])
                    foreign[known_position] ^= 1
                    with self.assertRaisesRegex(FormatError, 'known-move checker'):
                        install_evolution_learning(original, bytes(foreign), game,
                            additional_tms_report={'game_id': game})
                with self.assertRaisesRegex(FormatError, 'matching installed move report'):
                    install_evolution_learning(original, original, game, additional_tms_report={})
                with patch('orre_randomizer.fairy_tms.read_installed_content', return_value={'moves': {}}):
                    with self.assertRaisesRegex(FormatError, 'not installed'):
                        install_evolution_learning(original, original, game,
                            additional_tms_report={'game_id': game})


if __name__ == '__main__':
    unittest.main()
