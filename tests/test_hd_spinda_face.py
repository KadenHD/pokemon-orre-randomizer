"""Pre-filter composition, external provenance and bank ownership regressions."""
from array import array
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import random
import struct
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from PIL import Image

from orre_randomizer import hd_spinda_face as h
from orre_randomizer.engine import dna_spinda_face_hd as b
from orre_randomizer.engine.spinda_art import _FACE_ORDER, _SPOT_ORDER, spinda_face_texture
from tests.test_spinda_diagram import retail
from tests.test_dna_spinda_face_hd import fixture, machine, set_request


def assets(directory):
    face = retail(128, [0xE698] * 16384, _FACE_ORDER)
    stamp32 = [0xFACC if (x * 13 + y * 7) % 17 < 9 else 0xD500 for y in range(32) for x in range(32)]
    stamp = retail(32, stamp32, _SPOT_ORDER)
    paint = h._big_endian([stamp32[y // 4 * 32 + x // 4] for y in range(128) for x in range(128)])
    payloads = {"native-face.bin": face, "native-stamp.bin": stamp, "paint.rgb565": paint}
    manifest = {"schema": 1, "contract": b.CONTRACT, "source_dol_sha256": b.bridge_profile()["source_dol_sha256"],
                "background_rgb565": 0xE698,
                "files": {name: {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)} for name, raw in payloads.items()}}
    for name, raw in payloads.items():
        (directory / name).write_bytes(raw)
    (directory / "face-assets.json").write_text(json.dumps(manifest))
    return face, stamp, paint


def metadata(game_id="GC6P01"):
    original, profile = fixture(game_id)
    with patch.dict(b._PROFILES[game_id], profile):
        _, result = b.patch_spinda_face_bridge(original, original, game_id)
    # A synthetic source still validates against its own pinned test profile.
    return profile, result


class FaceCompositionTests(unittest.TestCase):
    def test_native_capture_needs_no_pack_and_hd_can_be_prepared_later_from_standard_pack_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            guides = root / "synthetic"
            guides.mkdir()
            face, stamp, _ = assets(guides)
            native = root / "Native"
            with patch.object(h, "_capture_references", return_value=({"native-face.bin": face, "native-stamp.bin": stamp}, b.bridge_profile())):
                captured = h.capture_native_face_assets(root / "source-not-opened.iso", native)
            self.assertFalse(captured["hd_materials_included"])
            pack = root / "pack"
            (pack / "Textures").mkdir(parents=True)
            Image.new("RGBA", (512, 512), (230, 90, 100, 255)).save(pack / "Textures" / h.DONOR)
            (pack / "installed.json").write_text('{}')
            with patch.object(h, "_capture_references", side_effect=AssertionError("Source ROM must not be reopened")):
                prepared = h.prepare_face_assets_from_references(native, pack, root / "HD")
            self.assertEqual(prepared["donor"]["source_scale"], 4)
            self.assertEqual((root / "HD/native-face.bin").read_bytes(), face)
            (native / "native-stamp.bin").write_bytes(bytes(2176))
            with self.assertRaises(ValueError):
                h.prepare_face_assets_from_references(native, pack, root / "invalid")
            self.assertFalse((root / "invalid").exists())

    def test_precomposition_matches_native_overlap_and_row_carry_for_boundary_pids(self):
        with tempfile.TemporaryDirectory() as tmp:
            face, stamp, paint = assets(Path(tmp))
            rng = random.Random(20261118)
            for pid in (0, 0xFFFFFFFF, 0x000000FF, 0xFF00FF00, 0x00FF00FF, 0x12345678,
                        *(rng.getrandbits(32) for _ in range(6))):
                native_tiled = h._words(spinda_face_texture(face, stamp, pid))
                native = [0] * 16384
                for index, pixel in enumerate(_FACE_ORDER):
                    native[pixel] = native_tiled[index]
                hd = h._words(h.compose_face(pid, 0xE698, paint, tiled=False))
                for y in range(512):
                    self.assertEqual(hd[y * 512:(y + 1) * 512], array("H", [native[y // 4 * 128 + x // 4] for x in range(512)]))

    def test_single_precomposed_image_removes_the_filtering_counterexample(self):
        # Two overlapping source signals. Native composes BEFORE interpolation.
        first, second = [100, 0], [0, 100]
        composed = [max(a, b) for a, b in zip(first, second)]
        bilinear = lambda values: (values[0] + values[1]) / 2
        self.assertEqual(bilinear(composed), 100)
        self.assertEqual(max(bilinear(first), bilinear(second)), 50)
        self.assertEqual(len(h.compose_face(0, 0xE698, bytes(32768))), b.BUFFER_BYTES)

    def test_paint_uses_donor_details_and_vector_boundary_without_native_bitmap_input(self):
        image = Image.new("RGBA", (512, 512), (230, 210, 195, 255))
        pixels = image.load()
        for y in range(80, 144):
            for x in range(128, 176):
                pixels[x, y] = (247, 30 + (x % 11) * 5, 40 + (y % 13) * 3, 255)
        background, raw = h.author_paint(image)
        words = h._words(raw)
        self.assertEqual(background, h._rgb565((230, 210, 195)))
        self.assertEqual(len(words), 128 * 128)
        self.assertGreater(len(set(words)), 30)
        self.assertEqual(words[0], background)
        self.assertNotEqual(words[64 * 128 + 64], background)
        # RGB565 donor colours are composed in the normal palette. Shiny is a
        # native material operation, so this API intentionally has no tint arg.
        with self.assertRaises(TypeError):
            h.compose_face(0, background, raw, shiny=True)

    def test_external_cache_verifies_every_payload_and_stays_bounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            face, stamp, paint = assets(directory)
            loaded = h.FaceAssets(directory)
            native = spinda_face_texture(face, stamp, 7)
            loaded.validate_native(7, native)
            with self.assertRaises(ValueError):
                loaded.validate_native(8, native)
            with patch.object(h, "compose_face", side_effect=lambda pid, *a: bytes([pid]) * b.BUFFER_BYTES):
                for pid in range(11):
                    loaded.render(pid)
                self.assertEqual(list(loaded.cache), list(range(3, 11)))
                self.assertEqual(sum(map(len, loaded.cache.values())), 4 * 1024 * 1024)
            (directory / "paint.rgb565").write_bytes(bytes(32768))
            with self.assertRaises(ValueError):
                h.FaceAssets(directory)


class BankOwnershipTests(unittest.TestCase):
    def test_unqualified_profiles_require_an_explicit_private_qa_opt_in(self):
        for game in b.PATCHABLE_GAME_IDS:
            original, profile = fixture(game)
            with patch.dict(b._PROFILES[game], profile), patch.object(b, "VALIDATED_GAME_IDS", frozenset()):
                _, info = b.patch_spinda_face_bridge(original, original, game)
                # A saved manifest cannot promote an unqualified profile.
                info['production_validated'] = True
                with self.assertRaisesRegex(ValueError, "not runtime-qualified"):
                    h.SpindaFaceSession(None, Path("unused"), info)
                session = h.SpindaFaceSession(None, Path("unused"), info, allow_unvalidated=True)
                self.assertIsNone(session.thread)

    def test_runtime_qualification_is_per_region_without_private_qa_override(self):
        for game in b.PATCHABLE_GAME_IDS:
            original, profile = fixture(game)
            with patch.dict(b._PROFILES[game], profile), patch.object(b, 'VALIDATED_GAME_IDS', frozenset({'GC6E01'})):
                _, info = b.patch_spinda_face_bridge(original, original, game)
                if game == 'GC6E01':
                    session = h.SpindaFaceSession(None, Path('unused'), info)
                    self.assertIsNone(session.thread)
                else:
                    with self.assertRaisesRegex(ValueError, 'not runtime-qualified'):
                        h.SpindaFaceSession(None, Path('unused'), info)

    def test_snapshot_retries_if_native_acknowledges_a_bank_switch_during_copy(self):
        memory = object.__new__(h.OwnedFaceMemory)
        memory.metadata = {"control": 0x80500000}
        memory.verify_contract = lambda **kwargs: None
        state = bytearray(96)
        struct.pack_into(">I", state, 20, 0)
        switched = False
        def read(address, count):
            nonlocal switched
            offset = address - memory.metadata["control"]
            result = bytes(state[offset:offset + count])
            if count == 96 and not switched:
                struct.pack_into(">I", state, 20, 1)
                struct.pack_into(">I", state, 76, 7)
                switched = True
            return result
        memory.read = read
        actual = memory.snapshot()
        self.assertEqual(actual["active_bank"], 1)
        self.assertEqual(actual["ack_serial"], 7)

    def test_live_mapping_revalidates_game_hooks_descriptors_and_complete_wrappers(self):
        profile, info = metadata()
        memory = object.__new__(h.OwnedFaceMemory)
        memory.metadata = info
        contents = {0x80000000: b"GC6P01\0\0", info["control"]: struct.pack(">II", b.MAGIC, b.ABI)}
        from orre_randomizer.engine.gift_move_hooks import branch
        for hook in info["hooks"]:
            contents[hook["address"]] = struct.pack(">I", branch(hook["address"], hook["stub_address"]))
            contents[hook["stub_address"]] = (b._factory_stub(hook["stub_address"], info["control"], info)
                if hook["kind"] == "factory" else b._setup_stub(hook["stub_address"], info["control"], info["buffers"], info))
        for index, address in enumerate(info["buffers"]):
            contents[info["control"] + 256 + index * 32] = struct.pack(">IHHIIff", address, 512, 512, 4, 0, 0., 0.)
        memory.read = lambda address, size: contents[address][:size]
        memory.verify_contract(full=True)
        for address in tuple(contents):
            original = contents[address]
            contents[address] = bytes([original[0] ^ 1]) + original[1:]
            with self.assertRaises(h.FaceContractLost):
                memory.verify_contract(full=True)
            contents[address] = original

    def test_metadata_rejects_shifted_profile_overlapping_stubs_and_bank_escape(self):
        profile, info = metadata()
        with patch.dict(b._PROFILE, profile):
            h.validate_metadata(info)
            for mutate in (lambda x: x["buffers"].__setitem__(0, x["buffers"][0] + 32),
                           lambda x: x.__setitem__("factory", x["factory"] + 4),
                           lambda x: x["hooks"][1].__setitem__("stub_address", x["hooks"][0]["stub_address"])):
                damaged = deepcopy(info)
                mutate(damaged)
                with self.assertRaises(ValueError):
                    h.validate_metadata(damaged)

    def test_japanese_bank_requires_the_compact_layout_and_live_allocator_reservation(self):
        profile, info = metadata("GC6J01")
        with patch.dict(b._PROFILES["GC6J01"], profile):
            h.validate_metadata(info)
            damaged = dict(info, pixel_banks_in_executable=True)
            with self.assertRaisesRegex(ValueError, "compact reservation"):
                h.validate_metadata(damaged)
        memory = object.__new__(h.OwnedFaceMemory)
        memory.metadata = info
        contents = {0x80000000: b"GC6J01\0\0", 0x80464060: struct.pack(">I", info["reserved_end"]),
                    info["control"]: struct.pack(">II", b.MAGIC, b.ABI)}
        from orre_randomizer.engine.gift_move_hooks import branch, _arena_guard
        contents[info["base"]] = _arena_guard(info["reserved_end"], info["arena_store"])
        contents[info["arena_setter"]] = struct.pack(">I", branch(info["arena_setter"], info["base"]))
        for hook in info["hooks"]:
            contents[hook["address"]] = struct.pack(">I", branch(hook["address"], hook["stub_address"]))
        contents[info["control"] + 256] = struct.pack(">IHHIIff", info["buffers"][0], 512, 512, 4, 0, 0., 0.)
        memory.read = lambda address, size: contents[address][:size]
        memory.verify_contract()
        for value in (info["reserved_end"] - 32, 0x81800000, 0x10):
            contents[0x80464060] = struct.pack(">I", value)
            with self.assertRaisesRegex(h.FaceContractLost, "reservation was lost"):
                memory.verify_contract()
        contents[0x80464060] = struct.pack(">I", info["reserved_end"])
        for address in (info["base"], info["arena_setter"]):
            original = contents[address]
            contents[address] = b'\xff' + original[1:]
            with self.assertRaisesRegex(h.FaceContractLost, "guard ownership"):
                memory.verify_contract()
            contents[address] = original
        memory.snapshot = lambda: {"active_bank": b.NONE, "ready_serial": 1, "ack_serial": 1}
        memory._copy = lambda *a: self.fail("An absent second bank must never be written")
        with self.assertRaises(ValueError):
            memory.bank(1, bytes(b.BUFFER_BYTES))

    def test_older_european_folder_keeps_its_original_wrapper_contract(self):
        original, profile = fixture()
        factory = b._factory_stub
        with patch.dict(b._PROFILE, profile), patch.object(b, "_factory_stub",
                side_effect=lambda at, control, p: factory(at, control, p, guard_reuse=False)):
            _, info = b.patch_spinda_face_bridge(original, original)
        info.pop("registry_reuse_guard")
        memory = object.__new__(h.OwnedFaceMemory)
        memory.metadata = info
        contents = {0x80000000: b"GC6P01\0\0", info["control"]: struct.pack(">II", b.MAGIC, b.ABI)}
        from orre_randomizer.engine.gift_move_hooks import branch
        for hook in info["hooks"]:
            contents[hook["address"]] = struct.pack(">I", branch(hook["address"], hook["stub_address"]))
            contents[hook["stub_address"]] = (factory(hook["stub_address"], info["control"], info, guard_reuse=False)
                if hook["kind"] == "factory" else b._setup_stub(hook["stub_address"], info["control"], info["buffers"], info))
        for index, address in enumerate(info["buffers"]):
            contents[info["control"] + 256 + index * 32] = struct.pack(">IHHIIff", address, 512, 512, 4, 0, 0., 0.)
        memory.read = lambda address, size: contents[address][:size]
        memory.verify_contract(full=True)

    def test_mapping_writes_reject_active_or_unacknowledged_bank_and_native_fields(self):
        memory = object.__new__(h.OwnedFaceMemory)
        profile, memory.metadata = metadata()
        copied = []
        memory._copy = lambda address, raw: copied.append((address, len(raw)))
        memory.verify_contract = lambda **kwargs: None
        memory.snapshot = lambda: {"active_bank": 0, "ready_serial": 3, "ack_serial": 3}
        memory.bank(1, bytes(b.BUFFER_BYTES))
        with self.assertRaises(h.FaceContractLost):
            memory.bank(0, bytes(b.BUFFER_BYTES))
        memory.snapshot = lambda: {"active_bank": b.NONE, "ready_serial": 4, "ack_serial": 3}
        with self.assertRaises(h.FaceContractLost):
            memory.bank(1, bytes(b.BUFFER_BYTES))
        for name in ("active_bank", "request_pid", "magic", "factory_serial"):
            with self.assertRaises(ValueError):
                memory.put(name, 0)
        self.assertEqual(len(copied), 128)
        self.assertEqual(copied[0], (memory.metadata["buffers"][1], 4096))
        self.assertEqual(sum(size for _, size in copied), b.BUFFER_BYTES)

    def test_owned_session_publishes_complete_bank_then_commit_and_restores_lease_on_stop(self):
        profile, info = metadata()
        closed = threading.Event()
        class Process:
            def poll(self):
                return None
        class Memory:
            def __init__(self, *args):
                self.state = {name: 0 for name in b.FIELDS}
                self.state.update(active_bank=b.NONE, request_serial=1, request_epoch=7,
                                  request_pixels=0x80902000, request_pid=0x12345678,
                                  ready_serial=1, ack_serial=1, ready_commit=7)
                self.log = []
            def word(self, at): return 100
            def verify_contract(self, **kwargs): pass
            def snapshot(self):
                if not self.state['enabled'] and not self.state['ready_commit']:
                    self.state.update(ack_serial=self.state['ready_serial'], active_bank=b.NONE)
                return dict(self.state)
            def read(self, *args): return b"native"
            def put(self, name, value):
                self.log.append((name, value))
                self.state[name] = value
            def bank(self, index, pixels):
                assert self.state["ready_commit"] == 0
                self.log.append(("bank", index, len(pixels)))
            def close(self): closed.set()
        memory = Memory()
        class Assets:
            def __init__(self, *args): pass
            def validate_native(self, pid, raw): assert raw == b"native"
            def render(self, pid): return bytes(b.BUFFER_BYTES)
        with patch.dict(b._PROFILE, profile):
            session = h.SpindaFaceSession(Process(), Path("unused"), info, memory_factory=lambda *a: memory, assets_factory=Assets, allow_unvalidated=True)
            self.assertIs(session.start(), session)
            deadline = time.monotonic() + 2
            while session.stats["published"] < 1 and session.error is None and time.monotonic() < deadline:
                time.sleep(.01)
            session.stop()
        self.assertIsNone(session.error)
        self.assertTrue(closed.is_set())
        self.assertEqual(session.stats["published"], 1)
        names = [row[0] for row in memory.log]
        self.assertEqual(memory.log[0], ("enabled", 0))
        self.assertLess(memory.log.index(("ready_commit", 0)), memory.log.index(("enabled", 1)))
        bank_at = names.index("bank")
        commit_at = next(i for i, row in enumerate(memory.log) if row == ("ready_commit", 7))
        self.assertLess(bank_at, commit_at)
        self.assertEqual(memory.log[-1], ("enabled", 0))

    def test_lost_contract_after_tour_during_render_or_bank_permits_no_later_write(self):
        profile, info = metadata()
        for phase in ("tour", "render", "bank"):
            class Process:
                def poll(self): return None
            class Memory:
                def __init__(self):
                    self.state = {name: 0 for name in b.FIELDS}
                    self.state.update(active_bank=b.NONE, request_serial=1, request_epoch=7,
                                      request_pixels=0x80902000, request_pid=0x12345678)
                    self.valid, self.closed, self.log, self.loss_at = True, False, [], None
                def lose(self):
                    self.valid = False
                    self.loss_at = len(self.log)
                def verify_contract(self, **kwargs):
                    if not self.valid: raise h.FaceContractLost("test old state restored")
                def word(self, address): return 100
                def snapshot(self):
                    if not self.state['enabled'] and not self.state['ready_commit']:
                        self.state.update(ack_serial=self.state['ready_serial'], active_bank=b.NONE)
                    return dict(self.state)
                def read(self, *args): return b"native"
                def put(self, name, value):
                    self.log.append((name, value))
                    self.state[name] = value
                    if phase == "tour" and name == "ready_commit" and value:
                        self.lose()
                def bank(self, bank, pixels):
                    self.log.append(("bank", bank))
                    if phase == "bank": self.lose()
                def close(self): self.closed = True
            memory = Memory()
            class Assets:
                def __init__(self, *args): pass
                def validate_native(self, *args): pass
                def render(self, pid):
                    if phase == "render": memory.lose()
                    return bytes(b.BUFFER_BYTES)
            with patch.dict(b._PROFILE, profile):
                session = h.SpindaFaceSession(Process(), Path("unused"), info,
                    memory_factory=lambda *a: memory, assets_factory=Assets, allow_unvalidated=True).start()
                session.thread.join(2)
                session.stop()
            self.assertIn("old state restored", session.error, phase)
            self.assertTrue(memory.closed, phase)
            self.assertEqual(len(memory.log), memory.loss_at, phase)
            self.assertNotEqual(memory.log[-1], ("enabled", 0), phase)

    def test_bank_revalidates_between_chunks_and_stops_when_arena_or_active_bank_changes(self):
        for lose_signature in (True, False):
            memory = object.__new__(h.OwnedFaceMemory)
            _, memory.metadata = metadata()
            written = []
            def verify(**kwargs):
                if lose_signature and written:
                    raise h.FaceContractLost("arena lost")
            memory.verify_contract = verify
            def snapshot():
                verify()
                return {"active_bank": 1 if written else b.NONE, "ready_serial": 0, "ack_serial": 0}
            memory.snapshot = snapshot
            memory._copy = lambda address, raw: written.append((address, len(raw)))
            with self.assertRaises(h.FaceContractLost):
                memory.bank(1, bytes(b.BUFFER_BYTES))
            self.assertEqual(written, [(memory.metadata["buffers"][1], 4096)])

    def test_valid_rewind_republishes_even_when_native_pid_and_epoch_are_reused(self):
        profile, info = metadata()
        class Process:
            def poll(self): return None
        class Memory:
            def __init__(self):
                self.state = {name: 0 for name in b.FIELDS}
                self.state.update(active_bank=b.NONE, request_serial=1, request_epoch=7,
                                  request_pixels=0x80902000, request_pid=0x12345678)
                self.vi, self.publications = 100, 0
                self.requires_withdrawal = False
            def verify_contract(self, **kwargs): pass
            def word(self, address): return self.vi
            def snapshot(self):
                if not self.state['enabled'] and not self.state['ready_commit']:
                    self.state.update(ack_serial=self.state['ready_serial'], active_bank=b.NONE)
                return dict(self.state)
            def read(self, *args): return b"native"
            def put(self, name, value):
                if name == "ready_commit" and value == 0:
                    assert self.state["enabled"] == 0 or not self.requires_withdrawal
                    self.requires_withdrawal = False
                if name == "enabled" and value == 1:
                    assert not self.requires_withdrawal
                self.state[name] = value
                if name == "ready_commit" and value:
                    self.publications += 1
                    self.state["ack_serial"] = self.state["ready_serial"]
                    if self.publications == 1:
                        self.vi = 50
                        self.state["active_bank"] = b.NONE
                        self.requires_withdrawal = True
            def bank(self, *args): pass
            def close(self): pass
        memory = Memory()
        class Assets:
            def __init__(self, *args): pass
            def validate_native(self, *args): pass
            def render(self, pid): return bytes(b.BUFFER_BYTES)
        with patch.dict(b._PROFILE, profile):
            session = h.SpindaFaceSession(Process(), Path("unused"), info,
                memory_factory=lambda *a: memory, assets_factory=Assets, allow_unvalidated=True).start()
            deadline = time.monotonic() + 2
            while session.stats["published"] < 2 and session.error is None and time.monotonic() < deadline:
                time.sleep(.01)
            session.stop()
        self.assertIsNone(session.error)
        self.assertEqual(session.stats["published"], 2)

    def test_real_native_stub_acknowledges_withdrawal_before_startup_or_rewind_reuses_a_bank(self):
        cases = (("GC6P01", False, False, False), ("GC6P01", True, False, False),
                 ("GC6P01", True, True, False), ("GC6P01", True, False, True),
                 ("GC6J01", False, False, False), ("GC6J01", True, False, False),
                 ("GC6J01", True, True, False), ("GC6J01", True, False, True))
        for game_id, active, rewind, next_pid in cases:
            with self.subTest(game_id=game_id, active=active, rewind=rewind, next_pid=next_pid):
                profile, info = metadata(game_id)
                cpu, origin, control, buffers, native = machine(game_id=game_id, bank_count=len(info['buffers']))
                tobj, desc, pixels = set_request(cpu, control, profile=native)
                for name, value in {'request_serial': 1, 'request_epoch': 1,
                        'request_counter': 1,
                        'request_pixels': pixels, 'request_pid': 0x12345678,
                        'ready_bank': 1 if active else 0, 'ready_epoch': 1,
                        'ready_pixels': pixels, 'ready_pid': 0x12345678,
                        'ready_serial': 1, 'ack_serial': 0, 'ready_commit': 1,
                        'active_bank': 0 if active else b.NONE}.items():
                    cpu.write(control + b.FIELDS[name], value)
                class Process:
                    def poll(self): return None
                class Memory:
                    def __init__(self):
                        self.vi, self.disabled_polls, self.commits = 100, 0, 0
                        self.log, self.closed = [], False
                    def verify_contract(self, **kwargs): pass
                    def word(self, address): return self.vi
                    def read(self, *args): return b'native'
                    def draw(self):
                        cpu.reg[3], cpu.pc, cpu.lr = tobj, origin, 0x81300000
                        cpu.run(0x81300000)
                    def snapshot(self):
                        if not cpu.read(control + b.FIELDS['enabled']):
                            self.disabled_polls += 1
                            if self.disabled_polls % 2 == 0:
                                self.draw()
                                self.log.append(('native_disabled_ack', cpu.read(control + b.FIELDS['ack_serial'])))
                        return {name: cpu.read(control + at) for name, at in b.FIELDS.items()}
                    def put(self, name, value):
                        # No native draw between enabled0/commit0/token writes:
                        # this is the interleaving that previously deadlocked.
                        if name == 'enabled' and value == 1:
                            assert cpu.read(control + b.FIELDS['active_bank']) == b.NONE or self.commits, 'unreleased bank on enable'
                            assert (cpu.read(control + b.FIELDS['ack_serial']) == cpu.read(control + b.FIELDS['ready_serial'])
                                    or (self.commits and cpu.read(control + b.FIELDS['ready_commit']))), 'unacknowledged enable'
                        self.log.append((name, value))
                        cpu.write(control + b.FIELDS[name], value)
                        if name == 'enabled' and value == 1 and self.commits:
                            self.draw()
                        if name == 'ready_commit' and value:
                            self.commits += 1
                            self.draw()
                            if rewind and self.commits == 1:
                                self.vi = 50
                                cpu.write(native['vi'], 50)
                                # Restore an in-flight publication with the
                                # same identity, after bank switch/before ack.
                                cpu.write(control + b.FIELDS['ack_serial'], 0)
                            if next_pid and self.commits == 1:
                                set_request(cpu, control, epoch=2, pid=0x87654321, profile=native)
                    def bank(self, index, raw):
                        assert cpu.read(control + b.FIELDS['active_bank']) != index, 'active bank write'
                        assert cpu.read(control + b.FIELDS['ack_serial']) == cpu.read(control + b.FIELDS['ready_serial']), 'unacknowledged bank write'
                        assert cpu.read(control + b.FIELDS['ready_commit']) == 0, 'committed bank write'
                        self.log.append(('bank', index))
                    def close(self): self.closed = True
                memory = Memory()
                class Assets:
                    def __init__(self, *args): pass
                    def validate_native(self, *args): pass
                    def render(self, pid): return bytes(b.BUFFER_BYTES)
                with patch.dict(b._PROFILES[game_id], profile):
                    session = h.SpindaFaceSession(Process(), Path('unused'), info,
                        memory_factory=lambda *a: memory, assets_factory=Assets, allow_unvalidated=True).start()
                    deadline = time.monotonic() + 2
                    wanted = 2 if rewind or next_pid else 1
                    while session.stats['published'] < wanted and session.error is None and time.monotonic() < deadline:
                        time.sleep(.005)
                    session.stop()
                self.assertIsNone(session.error)
                self.assertEqual(session.stats['published'], wanted)
                self.assertTrue(memory.closed)
                first_enable = memory.log.index(('enabled', 1))
                self.assertTrue(any(name == 'native_disabled_ack' for name, value in memory.log[:first_enable]))
                self.assertEqual(cpu.read(control + b.FIELDS['ack_serial']), 2 if next_pid else 1)
                self.assertEqual(cpu.read(control + b.FIELDS['active_bank']),
                                 1 if next_pid and len(buffers) == 2 else 0)
                if next_pid:
                    self.assertEqual(cpu.read(control + b.FIELDS['active_epoch']), 2)
                    self.assertEqual(cpu.read(control + b.FIELDS['ready_pid']), 0x87654321)
                if active:
                    self.assertTrue(any(call[0] == native['draw_done'] for call in cpu.calls))

    def test_stop_while_native_cannot_acknowledge_never_enables_or_writes_a_bank(self):
        profile, info = metadata()
        class Process:
            def poll(self): return None
        class Memory:
            def __init__(self):
                self.state = {name: 0 for name in b.FIELDS}
                self.state.update(enabled=1, active_bank=0, request_serial=1,
                                  ready_serial=1, ack_serial=0, ready_commit=1)
                self.log, self.closed = [], False
            def verify_contract(self, **kwargs): pass
            def snapshot(self): return dict(self.state)
            def word(self, address): return 100
            def put(self, name, value):
                self.log.append((name, value))
                self.state[name] = value
            def bank(self, *args): raise AssertionError('Native did not release the bank')
            def close(self): self.closed = True
        class Assets:
            def __init__(self, *args): pass
            def render(self, pid): raise AssertionError('Native did not acknowledge')
        memory = Memory()
        with patch.dict(b._PROFILE, profile):
            session = h.SpindaFaceSession(Process(), Path('unused'), info,
                memory_factory=lambda *a: memory, assets_factory=Assets, allow_unvalidated=True).start()
            deadline = time.monotonic() + 1
            while not memory.log and time.monotonic() < deadline:
                time.sleep(.001)
            session.stop()
        self.assertIsNone(session.error)
        self.assertTrue(memory.closed)
        self.assertNotIn(('enabled', 1), memory.log)
        self.assertEqual(session.stats['published'], 0)


if __name__ == "__main__":
    unittest.main()
