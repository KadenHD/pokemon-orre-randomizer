"""External, precomposed HD Spinda face for an owned Dolphin child.

The companion writes complete opaque RGB565 images, not independently filtered
layers. Original material/UV/expression and colour-swap state remain native.
No production launcher integration is enabled by importing this module.
"""
from __future__ import annotations

from array import array
from collections import OrderedDict
import ctypes as C
import hashlib
import json
from pathlib import Path
import struct
import subprocess
import sys
import threading
import time

from PIL import Image

from .engine import dna_spinda_face_hd as bridge
from .engine.spinda_diagram import spot_rows

ASSET_SCHEMA = 1
DONOR = "tex1_128x128_a1443261174f684e_4.png"
PAINT_CROP = (128, 80, 176, 144)
ELLIPSE = (14.5, 16., 12.5, 14.)


class FaceContractLost(RuntimeError):
    """A boot/state no longer owns the reserved arena; no more writes allowed."""


def _words(raw):
    result = array("H")
    result.frombytes(raw)
    if sys.byteorder == "little":
        result.byteswap()
    return result


def _big_endian(words):
    result = array("H", words)
    if sys.byteorder == "little":
        result.byteswap()
    return result.tobytes()


def _rgb565(rgb):
    r, g, b = rgb
    return ((r * 31 + 127) // 255) << 11 | ((g * 63 + 127) // 255) << 5 | ((b * 31 + 127) // 255)


def author_paint(donor: Image.Image):
    """Author one 128² stamp from real x4 paint and an analytic boundary.

    The geometry uses the same native coordinates as the existing HD keypad
    diagram. Neither the native 32² stamp nor the native 128² face is resized.
    """
    if donor.size != (512, 512):
        raise ValueError("Spinda face paint requires the verified x4 material")
    donor = donor.convert("RGBA")
    skin = donor.getpixel((0, 0))[:3]
    paint = donor.crop(PAINT_CROP).resize((128, 128), Image.Resampling.LANCZOS)
    result = array("H")
    cx, cy, rx, ry = ELLIPSE
    for y in range(128):
        for x in range(128):
            covered = sum((((x + (sx + .5) / 4) / 4 - cx) / rx) ** 2
                          + (((y + (sy + .5) / 4) / 4 - cy) / ry) ** 2 <= 1
                          for sy in range(4) for sx in range(4))
            color = paint.getpixel((x, y))[:3]
            result.append(_rgb565(tuple((a * (16 - covered) + b * covered + 8) // 16
                                        for a, b in zip(skin, color))))
    return _rgb565(skin), _big_endian(result)


def compose_face(pid: int, background: int, stamp: bytes, *, tiled=True) -> bytes:
    """Compose all four spots before GX filtering, retaining native row carry.

    RGB565 comparison occurs in the normal palette. Native material colour swap
    handles shiny afterwards; the companion must not tint a second time.
    """
    if (type(pid) is not int or not 0 <= pid <= 0xFFFFFFFF
            or type(background) is not int or not 0 <= background <= 65535
            or not isinstance(stamp, bytes) or len(stamp) != 128 * 128 * 2):
        raise ValueError("Invalid Spinda face identity or paint template")
    source = _words(stamp)
    result = array("H", [background]) * (512 * 512)
    for index in range(4):
        for row, start, count in spot_rows(index, (pid >> (index * 8)) & 255):
            for dy in range(4):
                source_at = (row * 4 + dy) * 128
                for col in range(count):
                    native = start + col
                    destination = (native // 128 * 4 + dy) * 512 + native % 128 * 4
                    at = source_at + col * 4
                    for dx in range(4):
                        result[destination + dx] = max(result[destination + dx], source[at + dx])
    if not tiled:
        return _big_endian(result)
    tiled_words = array("H")
    for y in range(0, 512, 4):
        for x in range(0, 512, 4):
            for dy in range(4):
                at = (y + dy) * 512 + x
                tiled_words.extend(result[at:at + 4])
    return _big_endian(tiled_words)


def _capture_references(source_iso):
    from .artwork import _disc_files
    from .engine.analyze_game import parse_fsys
    from .engine.rebuild_iso import decoded_member
    from .play_rom import read_executable
    from .engine.dol_regions import dol_layout
    region = dol_layout(read_executable(source_iso))
    profile = bridge.bridge_profile(region.game_id)
    archive = _disc_files(source_iso, {"pkx_patcheel.fsys"})["pkx_patcheel.fsys"]
    resources = {row["name"]: decoded_member(archive, row) for row in parse_fsys(archive)["members"]}
    return {"native-face.bin": resources["face"], "native-stamp.bin": resources["buti_a"]}, profile


def _write_assets(destination, manifest_name, manifest, files):
    destination = Path(destination)
    if destination.exists() or destination.is_symlink() or destination.parent.is_symlink():
        raise FileExistsError("Spinda face cache must be a new directory")
    manifest = dict(manifest, files={name: {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": len(raw)}
                                     for name, raw in files.items()})
    destination.mkdir(parents=False, exist_ok=False)
    for name, raw in files.items():
        (destination / name).write_bytes(raw)
    (destination / manifest_name).write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def capture_native_face_assets(source_iso: Path, destination: Path) -> dict:
    """Capture only native guides at creation; an HD pack is not required."""
    references, profile = _capture_references(source_iso)
    return _write_assets(destination, "native-face-assets.json", {
        "schema": ASSET_SCHEMA, "contract": bridge.CONTRACT, "game_id": profile["game_id"], "revision": 0,
        "source_dol_sha256": profile["source_dol_sha256"], "hd_materials_included": False,
    }, references)


def _prepare_paint(references, pack_root, destination, profile):
    from .hd_images import load_texture, resolve_texture
    pack_root = Path(pack_root)
    texture_root = pack_root / "Textures" if (pack_root / "Textures").is_dir() else pack_root
    if texture_root.is_symlink():
        raise ValueError("Spinda HD texture root must not be a symlink")
    donor = load_texture(resolve_texture(texture_root, DONOR), expected_native_size=(128, 128))
    q = donor.image
    image = Image.frombytes("RGBA", (q.width(), q.height()), bytes(q.constBits())[:q.sizeInBytes()],
                            "raw", "RGBA", q.bytesPerLine())
    background, paint = author_paint(image)
    files = {"paint.rgb565": paint, **references}
    manifest = {"schema": ASSET_SCHEMA, "contract": bridge.CONTRACT, "background_rgb565": background,
                "game_id": profile["game_id"], "revision": 0,
                "source_dol_sha256": profile["source_dol_sha256"],
                "donor": {"logical_file": DONOR, **donor.metadata}, "paint_crop": list(PAINT_CROP),
                "ellipse_native_coordinates": list(ELLIPSE), "native_bitmap_resampled": False,
                "color_policy": "normal-palette-before-unchanged-native-material-color-swap"}
    return _write_assets(destination, "face-assets.json", manifest, files)


def prepare_face_assets_from_references(native_directory: Path, pack_root: Path, destination: Path) -> dict:
    """Enable HD later from the folder's native guides, without a source ROM."""
    native_directory = Path(native_directory)
    manifest = json.loads((native_directory / "native-face-assets.json").read_text(encoding="utf-8"))
    profile = bridge.bridge_profile(manifest.get("game_id"), manifest.get("revision"))
    if (manifest.get("schema") != ASSET_SCHEMA or manifest.get("contract") != bridge.CONTRACT
            or manifest.get("source_dol_sha256") != profile["source_dol_sha256"]):
        raise ValueError("Native Spinda face reference contract differs")
    references = {}
    for name, length in (("native-face.bin", 32896), ("native-stamp.bin", 2176)):
        path = native_directory / name
        raw = path.read_bytes()
        if (path.is_symlink() or len(raw) != length or manifest.get("files", {}).get(name)
                != {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": length}):
            raise ValueError("Native Spinda face reference digest differs")
        references[name] = raw
    return _prepare_paint(references, pack_root, destination, profile)


def prepare_face_assets(source_iso: Path, pack_root: Path, destination: Path) -> dict:
    """Convenience preparation from a verified disc; production can use guides."""
    references, profile = _capture_references(source_iso)
    return _prepare_paint(references, pack_root, destination, profile)


class FaceAssets:
    """Verified immutable paint, with a bounded eight-face host cache (4 MiB)."""
    def __init__(self, directory):
        from .engine.spinda_art import _FACE_ORDER, _SPOT_ORDER, _linear_rgb565
        directory = Path(directory)
        self.manifest = json.loads((directory / "face-assets.json").read_text(encoding="utf-8"))
        profile = bridge.bridge_profile(self.manifest.get("game_id", "GC6P01"), self.manifest.get("revision", 0))
        self.source_game_id = profile["game_id"]
        if (self.manifest.get("schema") != ASSET_SCHEMA or self.manifest.get("contract") != bridge.CONTRACT
                or self.manifest.get("source_dol_sha256") != profile["source_dol_sha256"]):
            raise ValueError("Spinda face asset schema/source differs")
        self.payloads = {}
        for name, length in (("paint.rgb565", 32768), ("native-face.bin", 32896), ("native-stamp.bin", 2176)):
            path = directory / name
            raw = path.read_bytes()
            expected = self.manifest.get("files", {}).get(name, {})
            if path.is_symlink() or len(raw) != length or expected != {"sha256": hashlib.sha256(raw).hexdigest(), "bytes": length}:
                raise ValueError("Spinda face asset digest differs: " + name)
            self.payloads[name] = raw
        _linear_rgb565(self.payloads["native-face.bin"], 128, _FACE_ORDER)
        _linear_rgb565(self.payloads["native-stamp.bin"], 32, _SPOT_ORDER)
        self.cache = OrderedDict()

    def render(self, pid):
        if pid not in self.cache:
            self.cache[pid] = compose_face(pid, self.manifest["background_rgb565"], self.payloads["paint.rgb565"])
            while len(self.cache) > 8:
                self.cache.popitem(last=False)
        self.cache.move_to_end(pid)
        return self.cache[pid]

    def validate_native(self, pid, pixels):
        from .engine.spinda_art import spinda_face_texture
        if pixels != spinda_face_texture(self.payloads["native-face.bin"], self.payloads["native-stamp.bin"], pid):
            raise ValueError("Displayed native Spinda face does not match its registered PID")


def validate_metadata(metadata):
    p = bridge.bridge_profile(metadata.get("game_id"), metadata.get("revision"))
    if any(metadata.get(k) != value for k, value in p.items()):
        raise ValueError("Spinda face bridge fixed profile differs")
    control, end = metadata.get("control"), metadata.get("reserved_end")
    count = 1 if p["game_id"] == "GC6J01" else 2
    if count == 1 and metadata.get("pixel_banks_in_executable") is not False:
        raise ValueError("Japanese Spinda face requires the qualified compact reservation")
    if (type(control) is not int or type(end) is not int or control % 32
            or not p["base"] + 32 <= control < end < 0x81700000
            or metadata.get("contract") != bridge.CONTRACT or metadata.get("bridge_abi") != bridge.ABI
            or metadata.get("buffers") != [control + 512 + i * bridge.BUFFER_BYTES for i in range(count)]
            or end != control + 512 + bridge.BUFFER_BYTES * count
            or metadata.get("control_bytes") != 512 or metadata.get("buffer_bytes") != bridge.BUFFER_BYTES):
        raise ValueError("Spinda face bridge arena differs")
    if metadata.get("pixel_banks_in_executable") is False:
        if (p["game_id"] != "GC6J01" or metadata.get("pixel_banks_begin") != control + 512
                or metadata.get("section_bytes") != control + 512 - p["base"]):
            raise ValueError("Spinda face unloaded bank reservation differs")
    hooks = metadata.get("hooks", [])
    if [row.get("kind") for row in hooks] != ["factory", "setup"]:
        raise ValueError("Spinda face hook list differs")
    occupied = []
    for hook in hooks:
        address, length = hook.get("stub_address"), hook.get("stub_size")
        if (hook.get("address") != p[hook["kind"]] or type(address) is not int or type(length) is not int
                or address % 32 or length <= 0 or length % 32
                or not p["base"] + 32 <= address < address + length <= control
                or any(max(a, address) < min(b, address + length) for a, b in occupied)):
            raise ValueError("Spinda face stub is outside its arena")
        occupied.append((address, address + length))


class OwnedFaceMemory:
    """Map only the live Popen child; restrict writes to host fields/two banks."""
    def __init__(self, process, metadata):
        validate_metadata(metadata)
        if sys.platform != "win32" or not isinstance(process, subprocess.Popen) or process.poll() is not None:
            raise ValueError("Spinda HD requires the live owned Windows Dolphin child")
        self.process, self.metadata = process, metadata
        self.kernel = C.WinDLL("kernel32", use_last_error=True)
        k = self.kernel
        from ctypes import wintypes as W
        k.GetProcessTimes.argtypes = [W.HANDLE, *([C.POINTER(W.FILETIME)] * 4)]
        k.GetProcessTimes.restype = W.BOOL
        times = [W.FILETIME() for _ in range(4)]
        if not k.GetProcessTimes(int(process._handle), *(C.byref(item) for item in times)):
            raise C.WinError(C.get_last_error())
        self.creation_time = times[0].dwLowDateTime | times[0].dwHighDateTime << 32
        k.OpenFileMappingW.argtypes = [C.c_uint32, C.c_int, C.c_wchar_p]
        k.OpenFileMappingW.restype = C.c_void_p
        k.MapViewOfFile.argtypes = [C.c_void_p, C.c_uint32, C.c_uint32, C.c_uint32, C.c_size_t]
        k.MapViewOfFile.restype = C.c_void_p
        k.UnmapViewOfFile.argtypes = [C.c_void_p]
        k.CloseHandle.argtypes = [C.c_void_p]
        self.pointer = self.handle = None
        self.handle = k.OpenFileMappingW(6, False, f"dolphin-emu.{process.pid}")
        if not self.handle:
            raise OSError("Owned Dolphin MEM1 is not ready")
        self.pointer = k.MapViewOfFile(self.handle, 6, 0, 0, 0x1800000)
        if not self.pointer:
            self.close()
            raise OSError("Cannot map owned Dolphin MEM1")
        try:
            self.verify_contract(full=True)
        except FaceContractLost as error:
            self.close()
            raise OSError(str(error)) from error
        except BaseException:
            self.close()
            raise

    def verify_contract(self, *, full=False):
        """Revalidate after boot/load/reset, before every host mutation.

        A mapping handle can remain readable after the guest restores another
        state. Its existence does not prove that this arena is still reserved.
        """
        from .engine.gift_move_hooks import branch
        m = self.metadata
        if m.get("pixel_banks_in_executable") is False:
            from .engine.gift_move_hooks import _arena_guard
            if (self.word(m["arena_setter"]) != branch(m["arena_setter"], m["base"])
                    or self.read(m["base"], 32) != _arena_guard(m["reserved_end"], m["arena_store"])):
                raise FaceContractLost("Spinda face allocator guard ownership was lost")
            # Verified JP startup sets r13=0x8046bf00; native OSSetArenaLo's
            # stw r3,-0x7ea0(r13) owns this word. Check the effective allocator
            # boundary, as well as the wrapper/descriptor ownership below.
            arena_low = self.word(0x80464060)
            if not m["reserved_end"] <= arena_low < 0x81800000:
                raise FaceContractLost("Spinda face pixel-bank reservation was lost: " + hex(arena_low))
        if self.read(0x80000000, 8) != m["game_id"].encode("ascii") + b"\0\0" or self.read(m["control"], 8) != struct.pack(">II", bridge.MAGIC, bridge.ABI):
            raise FaceContractLost("Spinda face game/mailbox ownership was lost")
        for hook in m["hooks"]:
            if self.word(hook["address"]) != branch(hook["address"], hook["stub_address"]):
                raise FaceContractLost("Spinda face native hook ownership was lost")
            if full:
                if hook["kind"] == "factory":
                    expected = bridge._factory_stub(hook["stub_address"], m["control"], m,
                        guard_reuse=m.get("registry_reuse_guard", False))
                else:
                    expected = bridge._setup_stub(hook["stub_address"], m["control"], m["buffers"], m)
                if self.read(hook["stub_address"], len(expected)) != expected:
                    raise FaceContractLost("Spinda face native wrapper bytes differ")
        for bank, address in enumerate(m["buffers"]):
            expected = struct.pack(">IHHIIff", address, 512, 512, 4, 0, 0., 0.)
            if self.read(m["control"] + bridge.DESCRIPTOR_OFFSET + bank * 32, 24) != expected:
                raise FaceContractLost("Spinda face immutable descriptor ownership was lost")

    def read(self, address, size):
        if (type(address) is not int or type(size) is not int or size < 0
                or not 0x80000000 <= address <= address + size <= 0x81800000):
            raise ValueError("Spinda face read is outside MEM1")
        if not self.pointer or self.process.poll() is not None:
            raise OSError("Owned Dolphin has exited")
        return C.string_at(self.pointer + address - 0x80000000, size)

    def word(self, address):
        return int.from_bytes(self.read(address, 4), "big")

    def snapshot(self):
        self.verify_contract()
        control = self.metadata["control"]
        # Native publishes request_serial last and ack_serial only after its
        # active-bank switch/fence. Reject a copy spanning either publication.
        for _ in range(8):
            before = self.word(control + 28), self.word(control + 76)
            raw = self.read(control, 96)
            after = self.word(control + 28), self.word(control + 76)
            if before == after == (struct.unpack_from(">I", raw, 28)[0], struct.unpack_from(">I", raw, 76)[0]):
                return {name: struct.unpack_from(">I", raw, at)[0] for name, at in bridge.FIELDS.items()}
        raise FaceContractLost("Spinda face native publication did not stabilize")

    def put(self, name, value):
        offset = bridge.FIELDS[name]
        if offset not in bridge.HOST_FIELDS or type(value) is not int or not 0 <= value <= 0xFFFFFFFF:
            raise ValueError("Spinda face write is outside host-owned fields")
        self.verify_contract()
        self._copy(self.metadata["control"] + offset, struct.pack(">I", value))

    def bank(self, index, pixels):
        if (type(index) is not int or not 0 <= index < len(self.metadata["buffers"])
                or len(pixels) != bridge.BUFFER_BYTES):
            raise ValueError("Spinda face write is outside the exact inactive bank")
        self.verify_contract(full=True)
        # Keep the transfer bounded between ownership checks. A valid restored
        # state can also change which bank is active, so check that each time.
        for offset in range(0, len(pixels), 4096):
            state = self.snapshot()
            if state["active_bank"] == index or state["ready_serial"] != state["ack_serial"]:
                raise FaceContractLost("Spinda face bank ownership changed during transfer")
            self._copy(self.metadata["buffers"][index] + offset, pixels[offset:offset + 4096])
        self.verify_contract(full=True)

    def _copy(self, address, pixels):
        self.verify_contract()
        if not self.pointer or self.process.poll() is not None:
            raise OSError("Owned Dolphin has exited")
        C.memmove(self.pointer + address - 0x80000000, pixels, len(pixels))

    def close(self):
        if self.pointer:
            self.kernel.UnmapViewOfFile(self.pointer)
            self.pointer = None
        if self.handle:
            self.kernel.CloseHandle(self.handle)
            self.handle = None


class SpindaFaceSession:
    """A separate HD session; music may be off. Missing companion means native."""
    def __init__(self, process, assets_dir, metadata, *, memory_factory=OwnedFaceMemory, assets_factory=FaceAssets,
                 on_error=None, allow_unvalidated=False):
        validate_metadata(metadata)
        if not allow_unvalidated and not bridge.face_runtime_validated(metadata["game_id"], metadata["revision"]):
            raise ValueError("Spinda HD face is not runtime-qualified for this game revision")
        self.process, self.metadata = process, dict(metadata)
        self.assets_dir, self.memory_factory, self.assets_factory = Path(assets_dir), memory_factory, assets_factory
        self.on_error, self.error, self.active = on_error, None, False
        self.stopped = threading.Event()
        self.thread = None
        self.stats = {"published": 0, "native_checks": 0, "stale_requests": 0}

    def start(self):
        if self.thread is not None:
            raise RuntimeError("Spinda face session already started")
        self.thread = threading.Thread(target=self._run, name="Spinda HD face", daemon=True)
        self.thread.start()
        return self

    def stop(self):
        self.stopped.set()
        if self.thread is not None and self.thread is not threading.current_thread():
            self.thread.join(timeout=3)

    def _withdraw(self, memory):
        """Wait for a native acknowledgement before reusing either bank.

        An uncommitted serial is a withdrawal token, not a texture packet.
        The existing native fallback acknowledges it after its GPU fence.
        A fresh token also excludes a stale acknowledgement already present
        in a restored state or an enabled callback still in flight.
        """
        token = previous_vi = None
        while not self.stopped.is_set() and self.process.poll() is None:
            memory.verify_contract()
            state = memory.snapshot()
            vi = memory.word(self.metadata["vi"])
            rewound = previous_vi is not None and vi < previous_vi and not (
                previous_vi > 0xFFFF0000 and vi < 0x10000)
            previous_vi = vi
            if (token is None or rewound or state["enabled"] != 0
                    or state["ready_commit"] != 0 or state["ready_serial"] != token):
                memory.put("enabled", 0)
                memory.put("ready_commit", 0)
                forbidden = {0, state["ready_serial"], state["ack_serial"], state["request_serial"]}
                token = (state["ready_serial"] + 1) & 0xFFFFFFFF
                while token in forbidden:
                    token = (token + 1) & 0xFFFFFFFF
                memory.put("ready_serial", token)
            elif state["ack_serial"] == token and state["active_bank"] == bridge.NONE:
                return True
            memory.put("heartbeat", vi)
            self.stopped.wait(.01)
        return False

    def _run(self):
        memory = None
        try:
            assets = self.assets_factory(self.assets_dir)
            if getattr(assets, "source_game_id", self.metadata["game_id"]) != self.metadata["game_id"]:
                raise ValueError("Spinda face assets belong to another game region")
            deadline = time.monotonic() + 30
            while not self.stopped.is_set() and self.process.poll() is None:
                try:
                    memory = self.memory_factory(self.process, self.metadata)
                    break
                except OSError:
                    if time.monotonic() >= deadline:
                        raise
                    self.stopped.wait(.05)
            if memory is None:
                return
            last = previous_vi = None
            self.active = True
            if not self._withdraw(memory):
                return
            while not self.stopped.is_set() and self.process.poll() is None:
                memory.verify_contract()
                state = memory.snapshot()
                vi = memory.word(self.metadata["vi"])
                if previous_vi is not None and vi < previous_vi and not (previous_vi > 0xFFFF0000 and vi < 0x10000):
                    last = None
                    if not self._withdraw(memory):
                        return
                    state = memory.snapshot()
                    vi = memory.word(self.metadata["vi"])
                previous_vi = vi
                memory.put("heartbeat", vi)
                memory.put("enabled", 1)
                serial = state["request_serial"]
                identity = (serial, state["request_epoch"], state["request_pixels"], state["request_pid"])
                if serial and identity != last and state["ready_serial"] == state["ack_serial"]:
                    native = memory.read(state["request_pixels"], 128 * 128 * 2)
                    assets.validate_native(state["request_pid"], native)
                    self.stats["native_checks"] += 1
                    pixels = assets.render(state["request_pid"])
                    memory.verify_contract(full=True)
                    current = memory.snapshot()
                    if tuple(current[name] for name in ("request_serial", "request_epoch", "request_pixels", "request_pid")) != identity:
                        self.stats["stale_requests"] += 1
                        continue
                    single = len(self.metadata["buffers"]) == 1
                    if single and current["active_bank"] == 0:
                        if not self._withdraw(memory):
                            return
                        current = memory.snapshot()
                        if tuple(current[name] for name in ("request_serial", "request_epoch", "request_pixels", "request_pid")) != identity:
                            self.stats["stale_requests"] += 1
                            continue
                    bank = 0 if single else (1 if current["active_bank"] == 0 else 0)
                    memory.put("ready_commit", 0)
                    memory.bank(bank, pixels)
                    memory.verify_contract(full=True)
                    for name, value in (("ready_bank", bank), ("ready_epoch", identity[1]), ("ready_pixels", identity[2]),
                                        ("ready_pid", identity[3]), ("ready_serial", serial)):
                        memory.put(name, value)
                    memory.put("heartbeat", memory.word(self.metadata["vi"]))
                    memory.put("ready_commit", identity[1])
                    if single:
                        memory.put("enabled", 1)
                    last = identity
                    self.stats["published"] += 1
                self.stopped.wait(.01)
        except Exception as error:
            self.error = str(error)
            if self.on_error is not None:
                self.on_error(self.error)
        finally:
            self.active = False
            if memory is not None:
                try:
                    memory.verify_contract()
                    memory.put("enabled", 0)
                except (OSError, ValueError, FaceContractLost):
                    pass
                memory.close()
