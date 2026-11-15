"""Native Colosseum staging for the optional Relic Stone battle.

CMS commands are qualified against the three original regional dispatch tables.
The caller supplies story/capture predicates and owns actor/model installation.
The scene latch is room-local CMS storage. A separate mission flag retains
introduction progress across native wipeouts.
"""
from __future__ import annotations

import math
import struct

from . import event_gifts as events
from .postgame_scene_state import INTRO_STATE_FLAG, PHASE_AVAILABLE, PHASE_INTRODUCED

BOSS_ACTOR = 4
LUGIA_ACTOR = 5
HERO_ACTOR = 100
PARTNER_ACTOR = 101
SCENE_GLOBAL = 2
ARRIVAL_GLOBAL = 3

# Aim the wide shot at the meeting, rather than the foreground steps. Keep the
# commander, both heroes and Lugia inside the frame. Euler values are radians;
# actor headings below are degrees.
ENTRANCE_CAMERA = ((0.0, 65.0, 135.0), (-0.503, 0.0, 0.0))
SHRINE_CAMERA = ((10.0, 36.0, 64.0), (-0.50, 0.402, 0.0))
POST_BATTLE_CAMERA = ((10.0, 36.0, 64.0), (-0.50, 0.18, 0.0))
# Keep the original unobstructed camera position, aimed at the remaining
# group's centre (7.3, 10, 24.1) for an over-the-shoulder conversation.
AFTERMATH_CAMERA = ((10.0, 36.0, 64.0), (-0.576475203, 0.067566167, 0.0))
RELIC_CAMERA = ((12.0, 35.0, 55.0), (-0.475, 0.647, 0.0))
# Eagun stands to the east of the stone. The commander's close-up puts him
# outside the frame, so his lines need their own unobstructed camera.
EAGUN_CAMERA = ((32.0, 34.0, 48.0), (-0.481634655, 0.608689308, 0.0))
HERO_APPROACH = (10.0, 0.0, 28.06)
PARTNER_APPROACH = (2.9, 0.0, 29.37)
# The original CCD is flat, including the visually descending steps. Its narrow
# passage bends away from the old left-hand segment near z72. First pass west
# of the lectern, then stay in the passage's centre until beyond the camera.
DEPARTURE_PATH = ((-14.0, 0.0, 34.0), (0.0, 0.0, 45.0),
                  (0.0, 0.0, 75.0), (0.0, 0.0, 105.0), (0.0, 0.0, 125.0))
_LUGIA_EAGUN_LINES = frozenset(("arrival_warning", "arrival_stand"))


def floating(value: float) -> bytes:
    """A float literal, distinct from the native-call argument type byte."""
    if not math.isfinite(value):
        raise ValueError("scene float must be finite")
    return b"\x08\x03" + struct.pack(">f", value)


def global_get(index: int = SCENE_GLOBAL) -> bytes:
    if index < 0:
        raise ValueError("negative scene global index")
    return events._push(index) + b"\x10\x02\x00\x01"


def global_set(value: int, index: int = SCENE_GLOBAL) -> bytes:
    if index < 0:
        raise ValueError("negative scene global index")
    # setVar pops its source before its destination index and returns the value.
    return events._push(index) + events._push(value) + b"\x1f\x82\x02" + events._POP


def pause(frames: int) -> bytes:
    """Wait engine frame ticks, as original shrine/home CMS sequences do."""
    if not isinstance(frames, int) or frames < 0:
        raise ValueError("pause requires nonnegative integer frame ticks")
    return events._push(frames) + b"\x24\x00\x00\x00\x01\x03\x81\x00\x00"


def camera(position: tuple[float, float, float], rotation: tuple[float, float, float]) -> bytes:
    return (events._statement(36, 3)
            + events._statement(40, *(floating(v) for v in position))
            + events._statement(41, *(floating(v) for v in rotation)))


def move(group: int | bytes, actor: int, position: tuple[float, float, float], *, speed: float = 1.0) -> bytes:
    # 61 resets speed to 1.0. 69 must follow it. 61 also enables native
    # model-specific idle/walk/run animation selection and automatic turning.
    return (events._statement(61, group, actor, 1, *(floating(v) for v in position))
            + events._statement(69, group, actor, floating(speed)))


def place(group: int | bytes, actor: int, position: tuple[float, float, float]) -> bytes:
    """Set a native field position before the post-battle shot is rendered."""
    return events._statement(59, group, actor, *(floating(v) for v in position))


def wait_for_movement(group: int | bytes, actor: int) -> bytes:
    return events._statement(62, group, actor, 1)


def turn(group: int | bytes, actor: int, degrees: float) -> bytes:
    return events._statement(68, group, actor, floating(degrees)) + wait_for_movement(group, actor)


def face_character(group: int | bytes, actor: int, target_group: int | bytes, target_actor: int) -> bytes:
    """Turn toward the target's actual field position, including its native yaw."""
    return (events._statement(165, group, actor, target_group, target_actor, floating(1.0))
            + wait_for_movement(group, actor))


def visibility(actor: int, visible: bool) -> bytes:
    return events._statement(50, events._local(1), actor, int(visible))


def refresh_guard(base: int, refresh: bytes, *, resume: int,
                  arrival_ready: bytes | None = None, captured: bytes | None = None,
                  battle_id: int | None = None) -> bytes:
    """Refresh after the native yield and optionally stage the first idle visit.

    Actor initialization runs before the map fade can finish. The arrival must
    instead run here, once the original idle thread has yielded to rendering.
    Mark this first visit even when ineligible so purification in this room does
    not suddenly move the player into an arrival scene.
    """
    if arrival_ready is not None and captured is None:
        raise ValueError("arrival refresh requires a capture predicate")
    code = events._Assembler(base)
    code.emit(global_get() + b"\x11\x82")
    code.jump("resume", when_false=True)
    code.emit(refresh)
    if arrival_ready is not None:
        code.emit(global_get(ARRIVAL_GLOBAL) + b"\x11\x82")
        code.jump("resume", when_false=True)
        code.emit(global_set(1, ARRIVAL_GLOBAL))
        # Native wipeout reconstructs room globals. Only this mission's own
        # introduction state survives; another battle's result is irrelevant.
        code.emit(events._call(82, INTRO_STATE_FLAG) + events._push(PHASE_AVAILABLE) + b"\x1d\x82\x82")
        code.jump("resume", when_false=True)
        start = base + len(code.code)
        code.emit(arrival(start, ready=arrival_ready, captured=captured,
                          entry_pop=False, resume=resume, battle_id=battle_id))
    code.mark("resume")
    code.emit(b"\x06" + struct.pack(">I", resume))
    return code.finish()


def talk(key: str) -> bytes:
    # Import lazily so installation code can build CMS without import cycles.
    from .postgame_scene_text import ACTOR_IDS, CAPTURE_AFTER_EXIT_KEYS, MESSAGE_IDS, SPEAKERS
    speaker = SPEAKERS[key]
    group = 0 if speaker in ("hero", "partner") else events._local(1)
    actor = ACTOR_IDS[speaker]
    facing = (face_character(events._local(1), LUGIA_ACTOR, events._local(1), 1)
              if key in _LUGIA_EAGUN_LINES else b"")
    if speaker == "eagun":
        facing += face_character(group, actor, 0, HERO_ACTOR)
    elif speaker == "boss":
        facing += face_character(events._local(1), 1, group, actor)
    # The final exchange has already moved both heroes beside Eagun. Retain
    # its group shot: the arrival camera cuts them off at the right edge.
    shot = (AFTERMATH_CAMERA if key in CAPTURE_AFTER_EXIT_KEYS else
            EAGUN_CAMERA if speaker == "eagun" else
            RELIC_CAMERA if speaker == "boss" else SHRINE_CAMERA)
    return (camera(*shot) + pause(20) + facing + events._statement(54, group, actor, MESSAGE_IDS[key])
            + events._statement(55, group, actor))


def _guard(code: events._Assembler, ready: bytes, captured: bytes) -> None:
    code.emit(ready)
    code.jump("return", when_false=True)
    code.emit(captured + b"\x11\x82")
    code.jump("return", when_false=True)


def _finish(code: events._Assembler) -> None:
    code.emit(global_set(0))
    code.emit(events._statement(179, floating(0.3), 1))
    code.emit(events._statement(33))


def arrival(base: int, *, ready: bytes, captured: bytes,
            entry_pop: bool = True, resume: int | None = None,
            battle_id: int | None = None) -> bytes:
    """Stage arrival after rendering starts, then resume the native idle loop.

    ``entry_pop`` supports relocation of a native POP/RETURN tail, but shrine
    integration uses the post-yield refresh with ``entry_pop=False`` because
    native actor initialization still holds the map fade black.
    """
    from .postgame_scene_text import ARRIVAL_KEYS
    code = events._Assembler(base)
    if entry_pop:
        code.emit(events._POP)
    _guard(code, ready, captured)
    code.emit(events._statement(32) + global_set(1))
    code.emit(visibility(BOSS_ACTOR, True) + visibility(LUGIA_ACTOR, True))
    if not entry_pop:
        code.emit(pause(60))
    code.emit(camera(*ENTRANCE_CAMERA) + pause(30))
    code.emit(move(0, HERO_ACTOR, HERO_APPROACH))
    code.emit(move(0, PARTNER_ACTOR, PARTNER_APPROACH))
    code.emit(wait_for_movement(0, HERO_ACTOR) + wait_for_movement(0, PARTNER_ACTOR))
    code.emit(turn(0, HERO_ACTOR, 240.0) + turn(0, PARTNER_ACTOR, 230.0))
    code.emit(turn(events._local(1), BOSS_ACTOR, 60.0) + pause(30))
    for index, key in enumerate(ARRIVAL_KEYS):
        if index == 1:
            code.emit(camera(*SHRINE_CAMERA) + pause(30))
        elif key == "arrival_lugia":
            code.emit(camera(*RELIC_CAMERA) + pause(60))
        elif key == "arrival_challenge":
            code.emit(camera(*SHRINE_CAMERA) + pause(30))
        code.emit(talk(key))
    # Arm only after the eligible introduction has actually finished, before
    # battle152 can replace the room and its local allocation on a wipeout.
    code.emit(events._statement(80, INTRO_STATE_FLAG, PHASE_INTRODUCED))
    if battle_id is None:
        _finish(code)
    else:
        # Continue the first confrontation directly into its native battle.
        # Retrying later still uses the commander's ordinary interaction.
        code.emit(events._statement(179, floating(0.3), 1))
        code.emit(interaction(base + len(code.code), ready=ready, captured=captured,
                              battle_id=battle_id, challenge=False, resume=resume))
    code.mark("return")
    code.emit(b"\x05" if resume is None else b"\x06" + struct.pack(">I", resume))
    return code.finish()


def interaction(base: int, *, ready: bytes, captured: bytes, battle_id: int,
                challenge: bool = True, resume: int | None = None) -> bytes:
    """Keep the encounter repeatable until capture, then stage a visible exit."""
    from .postgame_scene_text import (CAPTURE_AFTER_EXIT_KEYS, CAPTURE_BEFORE_EXIT_KEYS,
                                      LOSS_KEYS, RETRY_KEYS)
    code = events._Assembler(base)
    _guard(code, ready, captured)
    code.emit(events._statement(32) + global_set(1))
    if challenge:
        code.emit(talk("arrival_challenge"))
    code.emit(events._statement(152, battle_id, 1, 0))
    # Reassert before any post-battle dialogue or movement yields. Room-reload
    # ordering is additionally checked in Dolphin by the installation caller.
    code.emit(global_set(1) + global_set(1, ARRIVAL_GLOBAL))
    code.emit(captured)
    code.jump("not_captured", when_false=True)
    code.emit(visibility(BOSS_ACTOR, True) + visibility(LUGIA_ACTOR, False))
    # A retry can start from any side of Nascour. Re-stage both heroes during
    # the battle-to-field transition, before the first camera wait yields.
    # Their arbitrary interaction positions must not obstruct his exit path.
    code.emit(place(0, HERO_ACTOR, HERO_APPROACH) + place(0, PARTNER_ACTOR, PARTNER_APPROACH))
    code.emit(camera(*POST_BATTLE_CAMERA) + pause(30))
    code.emit(turn(0, HERO_ACTOR, 240.0) + turn(0, PARTNER_ACTOR, 230.0))
    for key in CAPTURE_BEFORE_EXIT_KEYS:
        code.emit(talk(key))
    code.emit(camera(*ENTRANCE_CAMERA) + pause(30))
    for point in DEPARTURE_PATH:
        code.emit(move(events._local(1), BOSS_ACTOR, point))
        code.emit(wait_for_movement(events._local(1), BOSS_ACTOR))
    # Keep the actor alive after the last off-screen step. Its cape and shadow
    # must leave the picture before the resource is hidden and the shot changes.
    code.emit(pause(15))
    code.emit(visibility(BOSS_ACTOR, False) + pause(30))
    code.emit(camera(*AFTERMATH_CAMERA))
    code.emit(face_character(events._local(1), 1, 0, HERO_ACTOR))
    code.emit(face_character(0, HERO_ACTOR, events._local(1), 1))
    code.emit(face_character(0, PARTNER_ACTOR, events._local(1), 1))
    for key in CAPTURE_AFTER_EXIT_KEYS:
        code.emit(talk(key))
    code.jump("end")
    code.mark("not_captured")
    code.emit(visibility(BOSS_ACTOR, True) + visibility(LUGIA_ACTOR, True))
    code.emit(events._call(103) + events._push(2) + b"\x1d\x82\x82")
    code.jump("lost", when_false=True)
    for key in RETRY_KEYS:
        code.emit(talk(key))
    code.jump("end")
    code.mark("lost")
    for key in LOSS_KEYS:
        code.emit(talk(key))
    code.mark("end")
    _finish(code)
    code.mark("return")
    code.emit(b"\x05" if resume is None else b"\x06" + struct.pack(">I", resume))
    return code.finish()
