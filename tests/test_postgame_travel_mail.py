"""Execute the bike-completion wrapper through native-call boundaries."""
import unittest

from orre_randomizer.engine import postgame_mail as mail
from tests.test_xd_shadow_shinies import ADDRESS, RETURN, WrapperMachine

LINK, SEND = 0x80113828, 0x801D2080
RECEIVED, FLAG, GET, SET = 0x801D1E50, 0x801902E0, 0x801906A0, 0x8019075C
RIDE = -0x649C
PENDING, NOTIFICATION, UPDATE = 0x8057FF00, 0x80467390, 0x801171C8


class CompletedTripMailTests(unittest.TestCase):
    def run_trip(self, *, ride=1, phase=0, member=-1, flags=None, insertion=True,
                 busy=False, arrival_flags=None):
        current = dict.fromkeys(mail.REQUIRED_FLAGS, 1) if flags is None else dict(flags)
        machine = WrapperMachine(mail._completed_trip_stub(
            ADDRESS, LINK, flag_check=FLAG, state_get=GET,
            ride_displacement=RIDE, pending=PENDING))
        machine.reg[3:5] = [123, 0]
        before = machine.reg.copy()
        machine.store(machine.reg[13] + RIDE, ride, 4)
        status = {"phase": phase, "member": member, "sent": [], "activated": [], "linked": [], "queries": []}

        def get(state):
            self.assertEqual(state.reg[3], mail.INTRO_STATE_FLAG)
            state.clobber_volatile()
            state.reg[3] = status["phase"]

        def set_(state):
            self.assertEqual(state.reg[3:5], [mail.INTRO_STATE_FLAG, mail.PHASE_AVAILABLE])
            self.assertGreaterEqual(status["member"], 0)
            status["phase"] = state.reg[4]
            status["activated"].append(state.reg[4])
            state.clobber_volatile()

        def flag(state):
            status["queries"].append(state.reg[3])
            value = current.get(state.reg[3], 0)
            state.clobber_volatile()
            state.reg[3] = 0xBAD00100 | value

        def received(state):
            self.assertEqual(state.reg[3], mail.MAIL_ID)
            state.clobber_volatile()
            state.reg[3] = status["member"] & 0xFFFFFFFF

        def send(state):
            self.assertEqual(state.reg[3], mail.MAIL_ID)
            status["sent"].append(mail.MAIL_ID)
            if insertion:
                status["member"] = 3
            state.clobber_volatile()

        def link(state):
            status["linked"].append(state.reg[3:5])
            state.clobber_volatile()

        machine.callbacks = {GET: get, SET: set_, FLAG: flag, RECEIVED: received,
                             SEND: send, LINK: link}
        machine.run(max_steps=2600)
        self.assertEqual(status["linked"], [[123, 0]])
        self.assertEqual(machine.reg[1:3], before[1:3])
        self.assertEqual(machine.reg[13:], before[13:])
        self.assertEqual(machine.lr, RETURN)
        # No mail or persistent mission phase can change during the transition.
        self.assertEqual((status['sent'], status['activated'], status['phase']), ([], [], phase))
        status['queued'] = machine.load(PENDING, 4)
        status['departure_calls'] = [address for address, _ in machine.calls]
        if arrival_flags is not None:
            current = dict(arrival_flags)
        arrival = WrapperMachine(mail._arrival_mail_stub(
            ADDRESS, UPDATE, SEND, received=RECEIVED, flag_check=FLAG,
            state_get=GET, state_set=SET, pending=PENDING, notification=NOTIFICATION))
        arrival.store(PENDING, status['queued'], 4)
        arrival.store(NOTIFICATION, int(busy), 4)
        original = arrival.reg.copy()

        def update(state):
            self.assertEqual(state.reg[3:8], original[3:8])
            state.clobber_volatile()
            state.reg[3] = 0x12345678

        arrival.callbacks = machine.callbacks | {UPDATE: update}
        arrival.run(max_steps=2600)
        self.assertEqual(arrival.reg[3], 0x12345678)
        self.assertEqual(arrival.reg[1:3], original[1:3])
        self.assertEqual(arrival.reg[13:], original[13:])
        self.assertEqual(arrival.lr, RETURN)
        status['pending_after_arrival'] = arrival.load(PENDING, 4)
        return arrival, status

    def test_no_completed_motorcycle_ride_does_not_touch_mail_or_mission(self):
        machine, state = self.run_trip(ride=0)
        self.assertEqual(state['departure_calls'], [LINK])
        self.assertEqual([address for address, _ in machine.calls], [UPDATE])
        self.assertEqual((state["phase"], state["sent"], state["activated"], state["queries"]), (0, [], [], []))

    def test_first_eligible_trip_receives_mail_then_activates_and_keeps_destination(self):
        machine, state = self.run_trip()
        self.assertEqual((state["phase"], state["sent"], state["activated"]), (1, [32], [1]))
        calls = [address for address, _ in machine.calls]
        self.assertLess(calls.index(SEND), calls.index(SET))
        self.assertEqual(calls[0], UPDATE)
        self.assertEqual(state['pending_after_arrival'], 0)

    def test_original_story_and_each_capture_purification_are_still_required(self):
        ready = dict.fromkeys(mail.REQUIRED_FLAGS, 1)
        for missing in mail.REQUIRED_FLAGS:
            with self.subTest(missing=missing):
                _, state = self.run_trip(flags=ready | {missing: 0})
                self.assertEqual((state["phase"], state["sent"], state["activated"]), (0, [], []))

    def test_pending_master_ball_delays_the_mission_without_blocking_travel(self):
        ready = dict.fromkeys(mail.REQUIRED_FLAGS, 1)
        for notice, receipt, expected in ((0, 0, 1), (0, 1, 1), (1, 0, 0), (1, 1, 1)):
            with self.subTest(notice=notice, receipt=receipt):
                _, state = self.run_trip(flags=ready | {mail.MASTER_BALL_NOTICE_FLAG: notice,
                                                       mail.MASTER_BALL_RECEIPT_FLAG: receipt})
                self.assertEqual(state["phase"], expected)
                self.assertEqual(state["sent"], [32] if expected else [])

    def test_existing_mail_migrates_only_on_eligible_trip_without_sending_twice(self):
        _, state = self.run_trip(member=0)
        self.assertEqual((state["phase"], state["sent"], state["activated"]), (1, [], [1]))
        _, state = self.run_trip(member=0, ride=0)
        self.assertEqual((state["phase"], state["sent"], state["activated"]), (0, [], []))

    def test_already_started_or_introduced_mission_never_rewinds(self):
        for phase in (1, 2, 3):
            with self.subTest(phase=phase):
                _, state = self.run_trip(phase=phase)
                self.assertEqual((state["phase"], state["sent"], state["activated"], state["queries"]), (phase, [], [], []))

    def test_a_failed_native_receipt_leaves_the_mission_dormant(self):
        _, state = self.run_trip(insertion=False)
        self.assertEqual((state["phase"], state["member"], state["sent"], state["activated"]), (0, -1, [32], []))

    def test_captured_lugia_never_produces_a_stale_sos(self):
        _, state = self.run_trip(flags=dict.fromkeys(mail.REQUIRED_FLAGS, 1) | {mail.CAPTURE_FLAG: 1})
        self.assertEqual((state["phase"], state["sent"], state["activated"]), (0, [], []))

    def test_native_mail_notification_has_priority_and_keeps_trip_pending(self):
        machine, state = self.run_trip(busy=True)
        self.assertEqual((state['queued'], state['pending_after_arrival']), (1, 1))
        self.assertEqual((state['sent'], state['activated'], state['phase']), ([], [], 0))
        self.assertEqual([address for address, _ in machine.calls], [UPDATE])

    def test_pending_trip_sends_once_when_the_native_notification_finishes(self):
        machine, state = self.run_trip(busy=True)
        for expected_pending in (1, 0):
            arrival = WrapperMachine(mail._arrival_mail_stub(
                ADDRESS, UPDATE, SEND, received=RECEIVED, flag_check=FLAG,
                state_get=GET, state_set=SET, pending=PENDING, notification=NOTIFICATION))
            self.assertEqual(machine.load(PENDING, 4), expected_pending)
            arrival.store(PENDING, expected_pending, 4)
            arrival.store(NOTIFICATION, 0, 4)
            arrival.callbacks = machine.callbacks
            arrival.run(max_steps=2600)
            self.assertEqual(arrival.load(PENDING, 4), 0)
            self.assertEqual((state['sent'], state['activated'], state['phase']), ([32], [1], 1))
            machine = arrival

    def test_arrival_rechecks_prerequisites_before_consuming_the_trip(self):
        _, state = self.run_trip(arrival_flags={})
        self.assertEqual((state['queued'], state['pending_after_arrival']), (1, 0))
        self.assertEqual((state['sent'], state['activated'], state['phase']), ([], [], 0))

    def test_a_later_purification_cannot_make_an_ineligible_trip_eligible(self):
        _, state = self.run_trip(flags={}, arrival_flags=dict.fromkeys(mail.REQUIRED_FLAGS, 1))
        self.assertEqual((state['queued'], state['sent'], state['phase']), (0, [], 0))


if __name__ == "__main__":
    unittest.main()
