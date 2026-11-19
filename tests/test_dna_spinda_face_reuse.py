"""Execute native face hooks across recycled allocations; no ROM or Dolphin."""
import unittest

from orre_randomizer.engine import dna_spinda_face_hd as bridge
from tests.test_dna_spinda_face_hd import machine


class RecycledFaceAllocationTests(unittest.TestCase):
    def test_recycled_pixels_select_new_pid_across_ring_and_serial_wrap(self):
        for game_id in bridge.PATCHABLE_GAME_IDS:
            for initial_serial in (0, 6, 0xFFFFFFFE):
                with self.subTest(game_id=game_id, initial_serial=initial_serial):
                    cpu, factory, control, buffers, profile = machine("factory", game_id)
                    setup = factory + 0x2000
                    cpu.load_code(setup, bridge._setup_stub(setup, control, buffers, profile))
                    texture, pixels = 0x80900000, 0x80902000
                    tobj, descriptor = 0x80904000, 0x80905000
                    analyzer, sequence = 0x80800000, 0x80810000
                    cpu.write(texture, 0x00800080)
                    cpu.write(texture + 0x28, pixels)
                    cpu.write(tobj + 0x58, descriptor)
                    for offset, value in ((0, pixels), (4, 0x00800080), (8, 4)):
                        cpu.write(descriptor + offset, value)
                    cpu.write(profile["analyzer"], analyzer)
                    cpu.write(analyzer + 12, 308, 2)
                    cpu.write(analyzer + 0x168, sequence)
                    cpu.write(control + bridge.FIELDS["enabled"], 1)
                    cpu.write(control + bridge.FIELDS["heartbeat"], 100)
                    cpu.write(control + bridge.FIELDS["factory_serial"], initial_serial)
                    # This different live allocation never occupies either
                    # publication slot in the three wrap scenarios below.
                    unrelated = control + 128 + 3 * 16
                    unrelated_record = (0x12345678, pixels + 0x8000, 0xAABBCCDD,
                                        texture + 0x8000)
                    for offset, value in enumerate(unrelated_record):
                        cpu.write(unrelated + offset * 4, value)

                    def native_factory(m):
                        m.reg[3] = texture
                        m.reg[1] += 0x50
                        m.pc = m.lr

                    def native_setup(m):
                        m.reg[1] += 0x80
                        m.pc = m.lr

                    cpu.external[profile["factory"] + 4] = native_factory
                    cpu.external[profile["setup"] + 4] = native_setup
                    preserved_registers = cpu.reg[14:].copy()
                    expected_serial = initial_serial
                    previous_request = 0
                    for pid in (0xBC029B0D, 0xBC039B16):
                        cpu.pc, cpu.lr, cpu.reg[5] = factory, 0x81300000, pid
                        cpu.run(0x81300000)
                        expected_serial = (expected_serial + 1) & 0xFFFFFFFF or 1
                        self.assertEqual(cpu.read(control + bridge.FIELDS["factory_serial"]),
                                         expected_serial)
                        live = []
                        for index in range(bridge.REGISTRY_COUNT):
                            at = control + 128 + index * 16
                            epoch = cpu.read(at)
                            if epoch and cpu.read(at + 4) == pixels:
                                live.append((epoch, cpu.read(at + 8), cpu.read(at + 12)))
                        self.assertEqual(live, [(expected_serial, pid, texture)])
                        cpu.pc, cpu.lr, cpu.reg[3] = setup, 0x81300000, tobj
                        cpu.run(0x81300000)
                        self.assertEqual(cpu.read(control + bridge.FIELDS["request_pid"]), pid)
                        self.assertEqual(cpu.read(control + bridge.FIELDS["request_epoch"]),
                                         expected_serial)
                        self.assertEqual(cpu.read(control + bridge.FIELDS["request_pixels"]), pixels)
                        request = cpu.read(control + bridge.FIELDS["request_serial"])
                        self.assertNotEqual(request, previous_request)
                        previous_request = request
                        self.assertEqual(cpu.reg[14:], preserved_registers)
                        self.assertEqual(cpu.read(tobj + 0x58), descriptor)
                        self.assertEqual(tuple(cpu.read(unrelated + offset * 4)
                                               for offset in range(4)), unrelated_record)


if __name__ == "__main__":
    unittest.main()
