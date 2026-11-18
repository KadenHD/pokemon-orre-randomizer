import configparser
from pathlib import Path
import socket
import struct
import tempfile
import time
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zlib

from orre_randomizer import play_speed as speed


def request(kind, body=b""):
    packet = bytearray(struct.pack("<4sHHIII", b"DSUC", 1001, len(body) + 4, 0, 123, kind) + body)
    struct.pack_into("<I", packet, 8, zlib.crc32(packet))
    return bytes(packet)


class SpeedProtocolTests(unittest.TestCase):
    def test_loopback_protocol_crc_subscription_and_buttons(self):
        pad = speed._SpeedPad()
        client = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        client.bind(("127.0.0.1", 0))
        client.settimeout(1)
        try:
            self.assertEqual(pad.socket.getsockname()[0], "127.0.0.1")
            client.sendto(request(0x100001, struct.pack("<I4B", 4, 0, 1, 2, 3)), ("127.0.0.1", pad.port))
            pad.step(1)
            replies = [client.recv(256) for _ in range(4)]
            self.assertEqual([reply[20] for reply in replies], [0, 1, 2, 3])
            self.assertEqual([reply[21] for reply in replies], [2, 0, 0, 0])
            client.sendto(request(0x100002, b"\1\0" + bytes(6)), ("127.0.0.1", pad.port))
            pad.step(1.02, speed._INCREASE)
            data = client.recv(256)
            self.assertEqual(len(data), 100)
            self.assertEqual(data[36:40], b"\4\0\0\0")  # R3 only; no game-pad action
            checked = bytearray(data)
            expected = struct.unpack_from("<I", data, 8)[0]
            checked[8:12] = bytes(4)
            self.assertEqual(zlib.crc32(checked), expected)
            self.assertEqual(len(pad.clients), 1)
            pad.step(5)
            self.assertFalse(pad.clients)
        finally:
            client.close()
            pad.close()

    def test_rejects_truncated_corrupt_and_unsupported_requests(self):
        good = request(0x100000)
        self.assertEqual(speed._request_kind(good), 0x100000)
        for bad in (good[:-1], good + b"x", b"bad", request(0x999999),
                    good[:5] + bytes([good[5] ^ 1]) + good[6:],
                    request(0x100001, struct.pack("<I4B", 4, 0, 1, 2, 255))):
            self.assertIsNone(speed._request_kind(bad))

    def test_profile_preserves_game_pad_and_other_dsu_servers(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(speed.sys, "platform", "win32"):
            profile = Path(temporary)
            config = profile / "Config"
            config.mkdir()
            controller = config / "GCPadNew.ini"
            controller.write_text("[GCPad1]\nDevice = Real user pad\nButtons/A = `Button A`\n")
            before = controller.read_bytes()
            (config / "DSUClient.ini").write_text("[Server]\nEntries = GamePad:127.0.0.1:30000;OrreSpeed:127.0.0.1:30001;\n")
            (config / "Dolphin.ini").write_text("[Core]\nEmulationSpeed = 2\n")
            controls = speed.prepare_speed_controls(profile)
            try:
                self.assertTrue(controls.enabled)
                self.assertEqual(controller.read_bytes(), before)
                parser = configparser.ConfigParser()
                parser.read(config / "DSUClient.ini")
                self.assertEqual(parser["Server"]["Entries"], f"GamePad:127.0.0.1:30000;OrreSpeed:127.0.0.1:{controls.port};")
                parser.read(config / "Dolphin.ini")
                self.assertEqual(parser["Core"]["EmulationSpeed"], "2")
                self.assertTrue(parser.getboolean("General", "HotkeysRequireFocus"))
                self.assertTrue(parser.getboolean("Interface", "PauseOnFocusLost"))
                parser.read(config / "Hotkeys.ini")
                self.assertEqual(parser["Hotkeys"]["Device"], "DInput/0/Keyboard Mouse")
                self.assertEqual(parser["Hotkeys"]["General/Toggle Pause"], "F10")
                self.assertEqual(parser["Hotkeys"]["General/Toggle Fullscreen"], "@(Alt+RETURN)")
                self.assertEqual(parser["Hotkeys"]["Load State/Load State Slot 1"], "F1")
                self.assertEqual(parser["Hotkeys"]["Save State/Save State Slot 8"], "@(Shift+F8)")
                self.assertEqual(parser["Hotkeys"]["Emulation Speed/Increase Emulation Speed"], "`DSUClient/0/OrreSpeed:R3`")
                self.assertEqual(parser["Hotkeys"]["Emulation Speed/Decrease Emulation Speed"], "`DSUClient/0/OrreSpeed:Share`")
                self.assertEqual(parser["Hotkeys"]["Emulation Speed/Disable Emulation Speed Limit"], "")
            finally:
                controls.close()

    def test_preserves_existing_native_device_custom_keys_and_explicit_unbound_keys(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(speed.sys, "platform", "win32"):
            profile = Path(temporary)
            config = profile / "Config"
            config.mkdir()
            (config / "Hotkeys.ini").write_text("[Hotkeys]\nDevice = SDL/0/Custom keyboard\n"
                                                "General/Toggle Pause = `P`\nGeneral/Toggle Fullscreen =\n"
                                                "Save State/Save State Slot 7 = @(`Ctrl`+`X`)\n")
            controls = speed.prepare_speed_controls(profile)
            try:
                parser = configparser.ConfigParser()
                parser.read(config / "Hotkeys.ini")
                values = parser["Hotkeys"]
                self.assertEqual(values["Device"], "SDL/0/Custom keyboard")
                self.assertEqual(values["General/Toggle Pause"], "`P`")
                self.assertEqual(values["General/Toggle Fullscreen"], "")
                self.assertEqual(values["Save State/Save State Slot 7"], "@(`Ctrl`+`X`)")
                self.assertNotIn("Load State/Load State Slot 1", values)
            finally:
                controls.close()

    def test_unsupported_platform_has_no_files_or_socket(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(speed.sys, "platform", "linux"):
            controls = speed.prepare_speed_controls(Path(temporary) / "profile")
            self.assertFalse(controls.enabled)
            self.assertIsNone(controls._pad)
            self.assertFalse(list(Path(temporary).iterdir()))


class ForegroundTests(unittest.TestCase):
    def reader(self, owner, down):
        reader = speed._ForegroundKeys.__new__(speed._ForegroundKeys)
        reader.pid, reader.bindings = 1234, speed.SpeedBindings()
        calls = []

        def window_pid(window, target):
            target._obj.value = owner
            return 1

        def key_state(key):
            calls.append(key)
            return 0x8000 if key in down else 0

        reader.user = SimpleNamespace(GetForegroundWindow=lambda: 42,
                                      GetWindowThreadProcessId=window_pid, GetAsyncKeyState=key_state)
        return reader, calls

    def test_never_polls_keys_when_another_process_has_focus(self):
        reader, calls = self.reader(9999, {9, 16})
        self.assertIsNone(reader())
        self.assertEqual(calls, [])

    def test_shift_tab_has_priority_over_tab_and_defaults_are_configurable(self):
        for down, expected in ((set(), None), ({9}, "fast"), ({9, 16}, "slow"), ({16}, None)):
            reader, calls = self.reader(1234, down)
            self.assertEqual(reader(), expected)
            self.assertEqual(set(calls), {9, 16})
        reader, _ = self.reader(1234, {0x70})
        reader.bindings = speed.SpeedBindings(fast=(0x70,), slow=(0x71,))
        self.assertEqual(reader(), "fast")
        for fast, slow in (((), (9,)), ((9, 9), (16, 9)), ((True,), (9,)), ((9,), (9,)),
                           ((9, 16), (16, 9)), (([9],), (16,))):
            with self.assertRaises(ValueError):
                speed.SpeedBindings(fast=fast, slow=slow)


class RampTests(unittest.TestCase):
    def run_steps(self, ramp, target, *, start=0.0, duration=3.0):
        edges, previous = [], ramp.button
        now = start
        while now <= start + duration:
            button = ramp.step(now, target, True)
            if button != previous:
                edges.append(button)
            previous = button
            now += 0.005
        return edges, now

    def test_fixed_targets_and_release_restore_both_selected_base_speeds(self):
        for base in (10, 20):
            for held in (5, 20):
                ramp = speed._Ramp(base)
                edges, now = self.run_steps(ramp, held)
                self.assertEqual(ramp.current, held)
                self.assertEqual(len([button for button in edges if button]), abs(held - base))
                self.assertEqual(edges[1::2], [0] * (len(edges) // 2))
                edges, _ = self.run_steps(ramp, base, start=now)
                self.assertTrue(ramp.restored)
                self.assertEqual(len([button for button in edges if button]), abs(held - base))

    def test_release_cancels_unfinished_ramp_instead_of_draining_queued_pulses(self):
        ramp = speed._Ramp(10)
        edges, now = self.run_steps(ramp, 20, duration=0.3)
        self.assertLess(ramp.current, 20)
        self.assertGreater(ramp.current, 10)
        edges, _ = self.run_steps(ramp, 10, start=now)
        self.assertTrue(ramp.restored)
        self.assertNotIn(speed._INCREASE, edges)

    def test_no_ramp_without_a_subscribed_dolphin_device(self):
        ramp = speed._Ramp(10)
        for i in range(100):
            self.assertEqual(ramp.step(i / 100, 20, False), 0)
        self.assertEqual(ramp.current, 10)

    def test_focus_loss_sends_only_neutral_and_return_restores_before_new_fast_hold(self):
        ramp = speed._Ramp(10)
        holds = speed._Holds(ramp)
        now = 0.0
        while now < 0.8:
            holds.step(now, "fast", True, True)
            now += .005
        self.assertGreater(ramp.current, 10)
        self.assertLess(ramp.current, 20)
        stopped = ramp.current
        for _ in range(1200):
            self.assertEqual(holds.step(now, "fast", False, False), 0)
            self.assertEqual(ramp.current, stopped)
            now += .005
        self.assertTrue(holds.pending_restore)
        restored_seen = False
        first_fast_after_restore = False
        for _ in range(1000):
            before = ramp.current
            holds.step(now, "fast", True, True)
            if ramp.current == 10:
                restored_seen = True
            if ramp.current > before:
                self.assertTrue(restored_seen, "new acceleration bypassed queued base restoration")
                first_fast_after_restore = True
                break
            now += .005
        self.assertTrue(first_fast_after_restore)


class SessionTests(unittest.TestCase):
    def test_session_reads_no_keys_and_emits_no_speed_pulses_while_background(self):
        class RecordingPad:
            clients = {"owned": 0}
            next_send = 0

            def __init__(self):
                self.sent = []

            def step(self, now, button=0, *, send=True):
                if send:
                    self.sent.append(button)

            def close(self):
                pass

        pad = RecordingPad()
        controls = speed.SpeedControls(True, _pad=pad)
        child = SimpleNamespace(pid=1234, poll=lambda: None)
        calls = []

        def forbidden_keyboard_read():
            calls.append(1)
            return "fast"

        with patch.object(speed.sys, "platform", "win32"):
            session = speed.SpeedSession(child, 1, controls, key_reader=forbidden_keyboard_read,
                                         foreground_reader=lambda: False).start()
            time.sleep(.03)
            self.assertTrue(session.close())
        self.assertEqual(calls, [])
        self.assertTrue(pad.sent)
        self.assertEqual(set(pad.sent), {0})
        self.assertEqual(session.transitions, 0)

    def test_orderly_close_restores_base_and_releases_device(self):
        class NativePad:
            def __init__(self):
                self.clients = {"owned": 0}
                self.current, self.previous = 10, 0
                self.next_send, self.closed = 0, False

            def step(self, now, button=0, *, send=True):
                if not send:
                    return
                if button and button != self.previous:
                    self.current += 1 if button == speed._INCREASE else -1
                self.previous = button

            def close(self):
                self.closed = True

        pad = NativePad()
        controls = speed.SpeedControls(True, _pad=pad)
        child = SimpleNamespace(pid=1234, poll=lambda: None)
        with patch.object(speed.sys, "platform", "win32"):
            session = speed.SpeedSession(child, 1, controls, key_reader=lambda: "fast", foreground_reader=lambda: True).start()
            deadline = time.monotonic() + 1
            while pad.current < 12 and time.monotonic() < deadline:
                time.sleep(0.005)
            self.assertGreaterEqual(pad.current, 12)
            self.assertTrue(session.close())
        self.assertEqual(pad.current, 10)
        self.assertEqual(pad.previous, 0)
        self.assertTrue(pad.closed)
        with self.assertRaises(ValueError):
            speed.SpeedSession(child, 1, controls)

    def test_rejects_invalid_base_or_nonprocess(self):
        child = SimpleNamespace(pid=1234, poll=lambda: None)
        for value in (0, 0.5, 3, True, "2"):
            with self.assertRaises(ValueError):
                speed.SpeedSession(child, value, speed.SpeedControls(False))
        with self.assertRaises(ValueError):
            speed.SpeedSession(SimpleNamespace(pid=0), 1, speed.SpeedControls(False))


if __name__ == "__main__":
    unittest.main()
