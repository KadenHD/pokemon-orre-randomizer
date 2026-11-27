"""Run specimen palette selectors and qualify the three original executables."""
import hashlib
from pathlib import Path
import struct
import unittest

from orre_randomizer import xd_chamber_lugia as chamber
from orre_randomizer.artwork import _texture
from orre_randomizer.engine.analyze_game import FormatError, parse_fsys
from orre_randomizer.engine.rebuild_iso import decoded_member
from orre_randomizer.xd_battle_rules import TEXT1_TO_RAM
from orre_randomizer.xd_deoxys_runtime import install_xd_deoxys_forms
from tests.test_xd_shadow_shinies import ADDRESS, RETURN, WrapperMachine
from tests.test_castform_resources import archive


class ChamberLugiaTests(unittest.TestCase):
    def test_real_specimen_selects_animated_palette_and_preserves_constructor_registers(self):
        for owner in (29, 30):
            for shiny in (False, True):
                rare, record = 0x8014B884, 0x80400100
                m = WrapperMachine(chamber._variant_stub(ADDRESS, RETURN, owner=owner, rare=rare))
                m.reg[owner] = record
                m.cr = [bool(0xA3C55A69 & (1 << (31 - bit))) for bit in range(32)]
                before = m.reg.copy()
                condition_before = m.cr.copy()
                def check(state):
                    self.assertEqual(state.reg[3], record)
                    state.clobber_volatile()
                    state.cr = [not bit for bit in condition_before]
                    state.reg[3] = int(shiny)
                m.callbacks[rare] = check
                m.run()
                self.assertEqual(m.reg[0], chamber.SHINY if shiny else chamber.SOURCE)
                self.assertEqual(m.reg[1:], before[1:])
                self.assertEqual(m.lr, RETURN)
                self.assertEqual(m.cr, condition_before)
                self.assertEqual(len(m.calls), 1)

    def test_original_animation_and_transparency_survive_the_native_repaint(self):
        path = Path(__file__).resolve().parents[1] / "build/hd-purify-chamber/darklugia.ant"
        if not path.is_file():
            self.skipTest("requires privately retained original animated ANT")
        original = path.read_bytes()
        result = chamber.make_shiny_ant(original)
        self.assertEqual(result[:0x120], original[:0x120])
        self.assertEqual(len(result), len(original))
        a, b = [_texture(raw[0xA0:], (64, 192)) for raw in (original, result)]
        self.assertEqual(a[3::4], b[3::4])
        self.assertNotEqual(a, b)
        self.assertEqual(len({b[i * 16384:(i + 1) * 16384] for i in range(3)}), 3)
        changed = bytearray(original)
        changed[16] ^= 1
        with self.assertRaises(FormatError):
            chamber.make_shiny_ant(bytes(changed))

    def test_real_regional_constructors_compose_with_deoxys_and_preserve_gameplay_predicates(self):
        root = Path(__file__).resolve().parents[1]
        sprite = root / "build/hd-purify-chamber/darklugia.ant"
        paths = [(gid, root / f"build/xd-validation/{region}/main.dol") for gid, region in
                 (("GXXP01", "eu"), ("GXXE01", "us"), ("GXXJ01", "jp"))]
        if not sprite.is_file() or not all(path.is_file() for _, path in paths):
            self.skipTest("requires privately retained originals")
        raw = sprite.read_bytes()
        source = archive([(chamber.SOURCE, "darklugia", raw), (0x12343200, "unrelated", b"unchanged")],
                         chamber.GROUP, True)
        for gid, path in paths:
            original = path.read_bytes()
            for keep in (False, True):
                with self.subTest(game=gid, keep=keep):
                    deoxys, _ = install_xd_deoxys_forms(original, original, gid)
                    updates = {}
                    output, report = chamber.install_chamber_lugia(
                        original, deoxys, gid, lambda name: source, updates,
                        keep_after_purification=keep)
                    self.assertEqual(len(report["hooks"]), 6 if keep else 3)
                    allowed = {h["hook_address"] - TEXT1_TO_RAM for h in report["hooks"]}
                    allowed.update((8, 0x50, 0x98))
                    from orre_randomizer.xd_battle_rules import ARENA
                    allowed.add(ARENA[gid][1] - TEXT1_TO_RAM)
                    for at in range(0, len(original), 4):
                        if at not in allowed:
                            self.assertEqual(output[at:at + 4], deoxys[at:at + 4], hex(at))
                    rows = parse_fsys(updates[chamber.ARCHIVE])["members"]
                    self.assertEqual(len(rows), 3)
                    self.assertEqual(decoded_member(updates[chamber.ARCHIVE], rows[0]), raw)
                    self.assertEqual(decoded_member(updates[chamber.ARCHIVE], rows[1]), b"unchanged")
                    self.assertEqual(int(rows[2]["identifier_raw"], 16), chamber.SHINY)
                    self.assertEqual(decoded_member(updates[chamber.ARCHIVE], rows[2]), chamber.make_shiny_ant(raw))
                    self.assertFalse(report["hd_artwork_included"])
                    self.assertFalse(report["saved_identity_changed"])
                    changed = bytearray(deoxys)
                    changed[report["hooks"][0]["hook_address"] - TEXT1_TO_RAM] ^= 1
                    with self.assertRaises(FormatError):
                        chamber.install_chamber_lugia(original, bytes(changed), gid, lambda name: source, {},
                                                     keep_after_purification=keep)


if __name__ == "__main__":
    unittest.main()
