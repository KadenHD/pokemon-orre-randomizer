"""Region headers cannot bypass the exact, full-image allowlist."""
import unittest

from orre_randomizer.engine.analyze_game import FormatError
from orre_randomizer.engine.regions import REGIONS, region_for_boot, validate_disc_hash


def boot(game_id, revision=0):
    data = bytearray(0x440)
    data[:6] = game_id.encode('ascii')
    data[7] = revision
    data[0x1C:0x20] = bytes.fromhex('c2339f3d')
    return bytes(data)


class RegionTests(unittest.TestCase):
    def test_exact_retail_header_and_full_hash_must_agree(self):
        for region in REGIONS:
            with self.subTest(game_id=region.game_id):
                header = boot(region.game_id)
                self.assertEqual(region_for_boot(header), region)
                self.assertEqual(validate_disc_hash(header, region.iso_sha256), region)
                for digest in ('0' * 64, next(r.iso_sha256 for r in REGIONS if r != region)):
                    with self.assertRaises(FormatError):
                        validate_disc_hash(header, digest)

    def test_unknown_revisions_discs_truncation_and_magic_are_rejected(self):
        cases = [boot('GC6P01', 1), boot('GC6E01', 1), boot('GC6J01', 1),
                 boot('GXXP01'), boot('GC6P01')[:0x43F]]
        invalid = bytearray(boot('GC6P01'))
        invalid[6] = 1
        cases.append(bytes(invalid))
        invalid[6] = 0
        invalid[0x1C] ^= 1
        cases.append(bytes(invalid))
        for header in cases:
            with self.assertRaises(FormatError):
                region_for_boot(header)
