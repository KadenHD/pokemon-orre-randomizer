"""Native automatic-mail isolation and regional completed-trip integration."""
import struct
import unittest
from pathlib import Path
from unittest.mock import patch

from orre_randomizer.engine import postgame_mail as mail
from orre_randomizer.engine.analyze_game import FormatError, parse_rel, u32
from orre_randomizer.engine.inspect_tables import rel_symbols, u16
from orre_randomizer.engine.message_bank import message_directory
from tests.test_xd_shadow_shinies import ADDRESS, RETURN, WrapperMachine

NATIVE = 0x801D2764


class AutomaticMailGuardTests(unittest.TestCase):
    def run_hook(self, mail_id):
        machine = WrapperMachine(mail._automatic_mail_guard(ADDRESS, NATIVE))
        machine.reg[3:8] = [mail_id, 7, 19, 3, 25]
        before = machine.reg.copy()

        def native(state):
            self.assertEqual(state.reg[3:8], before[3:8])
            state.clobber_volatile()
            state.reg[3] = 73

        machine.callbacks[NATIVE] = native
        machine.run()
        self.assertEqual(machine.reg[1:3], before[1:3])
        self.assertEqual(machine.reg[13:], before[13:])
        self.assertEqual(machine.lr, RETURN)
        return machine

    def test_all_original_mail_keeps_its_native_predicate_and_arguments(self):
        for identifier in (*range(32), 33, 511):
            with self.subTest(identifier=identifier):
                machine = self.run_hook(identifier)
                self.assertEqual(machine.reg[3], 73)
                self.assertEqual([address for address, _ in machine.calls], [NATIVE])

    def test_bonus_mail_cannot_be_sent_by_automatic_or_generic_mail_paths(self):
        machine = self.run_hook(32)
        self.assertEqual(machine.reg[3], 0)
        self.assertEqual(machine.calls, [])

    def test_record_cannot_be_randomly_sent_or_mutate_story_on_read(self):
        row = mail._mail_record()
        self.assertEqual(len(row), 44)
        self.assertEqual(row[:2], b'\xff\xff')
        self.assertEqual([u16(row, p) for p in (2, 4, 6, 8)], [65535] * 4)
        self.assertEqual(struct.unpack_from('>III', row, 12), (0x3ED3, mail.SUBJECT_ID, mail.BODY_ID))
        self.assertEqual(row[24:], bytes(20))


class RegionalTravelHookTests(unittest.TestCase):
    PATHS = {
        'GC6P01': Path('game/sys/main.dol'),
        'GC6E01': Path('build/region-compat-2026-11-02/dol-research/usa-main.dol'),
        'GC6J01': Path('build/region-compat-2026-11-02/dol-research/japan-main.dol'),
    }

    def sources(self):
        if not all(path.is_file() for path in self.PATHS.values()):
            self.skipTest('Private retail executable fixtures are unavailable')
        return [(game, path.read_bytes()) for game, path in self.PATHS.items()]

    def test_three_regions_change_only_mail_guard_travel_arrival_calls_and_arena(self):
        for game, source in self.sources():
            with self.subTest(game=game):
                output, report = mail.install_mail_hook(source, source)
                region = mail.dol_layout(source)
                automatic, *_ = mail._LAYOUTS[game]
                trip, link, displacement, _ = mail._TRAVEL_LAYOUTS[game]
                arrival, update, _, _ = mail._ARRIVAL_LAYOUTS[game]
                self.assertEqual(len(report['hooks']), 3)
                self.assertEqual([h['hook_address'] for h in report['hooks']], [automatic, trip, arrival])
                self.assertEqual(report['ride_marker_displacement'], displacement)
                self.assertTrue(report['automatic_bonus_mail_disabled'])
                self.assertTrue(report['native_destination_preserved'])
                self.assertTrue(report['native_step_callbacks_preserved'])
                self.assertTrue(report['activation_requires_native_receipt'])
                self.assertTrue(report['notification_after_arrival'])
                self.assertTrue(report['native_mail_notification_priority'])
                pending = report['transient_pending_address'] - region.section_ram + u32(output, 8)
                self.assertEqual(output[pending:pending+32], bytes(32))
                self.assertNotIn('registered_on_field_init', report)
                self.assertIn('motorcycle', report['trigger'])
                self.assertEqual(u32(source, trip-mail.TEXT_TO_RAM), mail.branch(trip, link, link=True))
                self.assertEqual(u32(source, arrival-mail.TEXT_TO_RAM), mail.branch(arrival, update, link=True))
                allowed = set()
                for start in (8, 0x50, 0x98, automatic-mail.TEXT_TO_RAM,
                              trip-mail.TEXT_TO_RAM, arrival-mail.TEXT_TO_RAM,
                              region.set_arena_lo-mail.TEXT_TO_RAM):
                    allowed.update(range(start, start+4))
                changes = {i for i, (a, b) in enumerate(zip(source, output)) if a != b}
                self.assertLessEqual(changes, allowed)

    def test_modified_native_travel_or_mail_dependencies_are_rejected(self):
        for game, source in self.sources():
            automatic, native, received, flag = mail._LAYOUTS[game]
            get, set_, _ = mail._STATE_LAYOUTS[game]
            send, *_ = mail._SENDER_LAYOUTS[game]
            trip, _, _, dependencies = mail._TRAVEL_LAYOUTS[game]
            arrival, _, _, arrival_dependency = mail._ARRIVAL_LAYOUTS[game]
            for target in {automatic, native, received, flag, get, set_, send, trip,
                           arrival, arrival_dependency[0], *(address for address, _, _ in dependencies)}:
                with self.subTest(game=game, target=hex(target)):
                    damaged = bytearray(source)
                    damaged[target-mail.TEXT_TO_RAM] ^= 1
                    with self.assertRaises(FormatError):
                        mail.install_mail_hook(source, bytes(damaged))


def mail_carrier():
    """Real REL v3 structure, artificial data and four native table references."""
    source = bytearray(2312)
    struct.pack_into('>I', source, 0, 126)
    struct.pack_into('>II', source, 12, 4, 0x4C)
    struct.pack_into('>I', source, 28, 3)
    struct.pack_into('>III', source, 0x24, 2080, 2072, 8)
    struct.pack_into('>I', source, 0x48, 2080)
    struct.pack_into('>II', source, 0x4C + 8, 0x95, 196)
    struct.pack_into('>II', source, 0x4C + 24, 344, 1728)
    for i in range(32):
        source[656 + 44*i:656 + 44*(i+1)] = bytes([i]) * 44
    struct.pack_into('>II', source, 2064, 78, 32)
    struct.pack_into('>II', source, 2072, 126, 2080)
    rows = ((0, 202, 1, 0), (0, 6, 3, 0), (4, 6, 3, 1720),
            (4, 6, 3, 312), (4, 6, 3, 1724), (0, 203, 0, 0))
    for i, row in enumerate(rows):
        struct.pack_into('>HBBI', source, 2080 + i*8, *row)
    return bytes(source)


class MailTablesTests(unittest.TestCase):
    def test_append_33rd_mail_preserves_all_32_native_records_and_save_format(self):
        original = mail_carrier()
        with patch.object(mail, 'sha256', return_value=mail._MAIL_HASHES['GC6P01']):
            output, report = mail.patch_mail_rel(original, 'GC6P01')
        before = rel_symbols(original, parse_rel(original))
        after = rel_symbols(output, parse_rel(output))
        self.assertEqual(u32(output, after[3]['offset']), 33)
        self.assertEqual(u32(output, after[1]['offset']), 78)
        self.assertEqual(output[344:2072], original[344:2068] + struct.pack('>I', 33))
        new_base = after[2]['offset']
        self.assertEqual(output[new_base:new_base+32*44], original[before[2]['offset']:2064])
        self.assertEqual(output[new_base+32*44:new_base+33*44], mail._mail_record())
        self.assertTrue(report['native_mail_preserved'])

    def test_wrong_native_rel_is_rejected(self):
        with self.assertRaises(FormatError):
            mail.patch_mail_rel(mail_carrier(), 'GC6P01')

    def bank(self, language):
        header = bytearray(16)
        header[3] = 1 if language != 'JP' else 0
        struct.pack_into('>H', header, 4, 2)
        header[6:8] = language.encode('ascii') if language != 'JP' else bytes(2)
        # An odd-length control and shared offset must survive verbatim.
        return bytes(header) + struct.pack('>IIII', mail.SENDER_ID, 32, 123, 32) + b'\xff\xff\x00X\0\0\0'

    def test_all_languages_append_native_mail_text_without_touching_existing_payloads(self):
        for language, (subject, body) in mail.TEXTS.items():
            with self.subTest(language=language):
                source = self.bank(language)
                output = mail._append_texts(source, language)
                rows = message_directory(output)
                self.assertEqual(u16(output, 4), 4)
                self.assertEqual(rows[mail.SENDER_ID][1], 48)
                self.assertEqual(rows[123][1], 48)
                self.assertEqual(output[48:len(source)+16], source[32:])
                self.assertEqual(output[rows[mail.SUBJECT_ID][1]:rows[mail.BODY_ID][1]],
                                 b'\xff\xff\x07\x03' + subject.encode('utf-16-be') + bytes(2))
                expected = b'\xff\xff\x00'.join(line.encode('utf-16-be') for line in body.split('\n')) + bytes(2)
                self.assertEqual(output[rows[mail.BODY_ID][1]:], expected)
                self.assertNotIn('\u2013', subject + body)
                self.assertNotIn('\u2014', subject + body)
                # The inbox subject column is narrower than the opened mail.
                self.assertNotIn('\n', subject)
                self.assertLessEqual(len(subject), 8 if language == 'JP' else 16)
                self.assertTrue(all(len(line) <= (18 if language == 'JP' else 34) for line in body.split('\n')))
                with self.assertRaises(FormatError):
                    mail._append_texts(output, language)


if __name__ == '__main__':
    unittest.main()
