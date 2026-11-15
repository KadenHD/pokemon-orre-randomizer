"""Eagun's one gift identity and a narrowly scoped native home visibility operand."""
from dataclasses import replace
from pathlib import Path
import struct
import unittest

from orre_randomizer.engine import eagun_scene as scene, event_gifts as events
from orre_randomizer.engine.analyze_game import FormatError, parse_fsys, u32
from orre_randomizer.engine.colo_spinda import (ORDINARY_SPINDA_OT, colo_spinda_seeds,
    colo_spinda_gift_pid, colo_spinda_trainer_pid, colo_trainer_gift_owners)
from orre_randomizer.engine.dol_regions import special_targets
from orre_randomizer.engine.inspect_tables import u16
from orre_randomizer.engine.randomize_trainers import layout
from orre_randomizer.engine.rebuild_iso import decoded_member
from orre_randomizer.engine.shiny_rules import (apply_shiny_rules, seeded_status,
    _spinda_pid_call, _seeded_trainer_wrapper, _spinda_party_owner, SECTION_RAM,
    PLAYER_POINTER, PID_GENERATOR, PAL)
from orre_randomizer.engine.spinda import SPINDA
from orre_randomizer.options import Options
from tests.test_colo_spinda import Machine, SeedMachine, POKEMON, RNG_STATE, RNG_INITIAL
from tests.test_event_gifts import execute

ROOT = Path(__file__).resolve().parents[1]
ALIASES = ((scene.PARTNER_SLOT, scene.GIFT_KEY),)


class HomeVisibilityTests(unittest.TestCase):
    def test_receipt_phone_and_native_handoff_only_affect_companion_three(self):
        code = events._statement(50, events._local(1), 3, scene._ambient_visibility())+b'\x05'
        for mask in range(1 << len(events.STORY_FLAGS)):
            story = {flag: int(bool(mask & 1 << i)) for i, flag in enumerate(events.STORY_FLAGS)}
            for received in (0, 1):
                for notice, master_ball in ((0, 0), (0, 1), (1, 0), (1, 1)):
                    flags = story | {2740: received, 2531: notice, 3541: master_ball}
                    result = execute(code, 0, flags)
                    hidden = received and all(story.values()) and (not notice or master_ball)
                    self.assertEqual(result['visibility'], [[77, 3, int(not hidden)]])
                    self.assertEqual(result['flags'], flags)
                    self.assertEqual(result['gifts'], [])
                    self.assertEqual(result['messages'], [])
                    self.assertLessEqual(result['depth'], 10)

    def test_unrelated_trainer_gift_links_are_refused(self):
        self.assertEqual(colo_trainer_gift_owners(ALIASES), {2822: 0x7991})
        for aliases in (((2821, scene.GIFT_KEY),), ((2822, 'celebi-event'),), ALIASES*2):
            with self.assertRaises(ValueError):
                colo_trainer_gift_owners(aliases)


class GiftSpindaAbiTests(unittest.TestCase):
    def test_pid_generator_uses_gift_owner_only_for_linked_spinda_slot(self):
        helper = SECTION_RAM+32
        code = _spinda_pid_call(helper, 0x8474, PAL)
        wrapper = helper+len(code)
        flags, shadow_flags, seeds, shadow_seeds = 0x81600000, 0x81602000, 0x81603000, 0x81609000
        code += _seeded_trainer_wrapper(wrapper, flags, shadow_flags, spinda_pid=helper,
            spinda_tables=(seeds, shadow_seeds), trainer_gift_owners={2822: 0x7991})
        for slot, shadow, private_seed in ((2822, 0, 0x12345678), (2821, 0, 0x34567890),
                                           (2822, 21, 0x34567890), (2822, 0, 0)):
            with self.subTest(slot=slot, shadow=shadow, seed=private_seed):
                machine = SeedMachine(code, helper); machine.pc = wrapper
                machine.reg[3:8] = [POKEMON, -1 & 0xFFFFFFFF, -1 & 0xFFFFFFFF, 0, 0x12345678]
                machine.reg[30] = shadow
                machine.write(POKEMON, SPINDA, 2)
                machine.write(machine.reg[1]+0x48, slot)
                machine.write(PLAYER_POINTER, POKEMON)
                machine.write(POKEMON+0x9C, 0x2468ABCD)
                machine.write(flags+slot, 1, 1); machine.write(shadow_flags+21, 1, 1)
                machine.write(seeds+slot*4, private_seed); machine.write(shadow_seeds+21*4, private_seed)
                before = machine.reg.copy(); machine.run()
                owner = (0x2468ABCD if shadow else
                         0x12345678 if not private_seed else 0x7991 if slot == 2822 else ORDINARY_SPINDA_OT)
                self.assertEqual(machine.calls[0], (PID_GENERATOR,
                    [POKEMON, 0xFFFFFFFF, 0xFFFFFFFF, 1, owner]))
                self.assertEqual(machine.reg[1:3], before[1:3])
                self.assertEqual(machine.reg[13:], before[13:])
                if private_seed:
                    self.assertEqual(machine.read(RNG_STATE), RNG_INITIAL)

    def test_party_copy_uses_native_saved_row_and_retains_abi_and_other_owners(self):
        address, caller, native = SECTION_RAM+32, 0x801FE734, 0x80128064
        for species, shadow, slot, lr in ((SPINDA, 0, 2822, caller), (SPINDA, 0, 2821, caller),
                (SPINDA, 21, 2822, caller), (25, 0, 2822, caller), (SPINDA, 0, 2822, 0x801F0100)):
            machine = Machine(_spinda_party_owner(address, caller, native, {2822: 0x7991}), address)
            machine.reg[3:10] = [POKEMON, 1, 7, 0, 4, 0x12345678, 0x80501000]
            machine.write(POKEMON, species, 2); machine.write(POKEMON+0xD8, shadow, 2)
            machine.write(POKEMON+0xD6, slot, 2); machine.write(machine.reg[1]+0x164, lr)
            before, memory = machine.reg.copy(), machine.mem.copy()
            expected = before[3:10]
            if species == SPINDA and not shadow and lr == caller:
                expected[5] = 0x7991 if slot == 2822 else ORDINARY_SPINDA_OT
            machine.run(stop=native)
            self.assertEqual(machine.reg[3:10], expected)
            self.assertEqual(machine.reg[1:3], before[1:3]); self.assertEqual(machine.reg[13:], before[13:])
            self.assertEqual(machine.mem, memory)


class NativeEagunTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        research = ROOT/'build/region-compat-2026-11-02'
        cls.sources = []
        for tag, game, dol in (('pal','GC6P01',ROOT/'game/sys/main.dol'),
                ('usa','GC6E01',research/'dol-research/usa-main.dol'),
                ('japan','GC6J01',research/'dol-research/japan-main.dol')):
            rel = research/'rel-research'/tag/'common.fsys-common_rel.rel'
            home = (ROOT/'game/files/M3_houseC_1F.fsys' if tag == 'pal' else
                    research/'event-research/v2'/tag/'M3_houseC_1F.fsys')
            if not all(p.exists() for p in (dol,rel,home)):
                raise unittest.SkipTest('requires local extracted three-region originals; no ROM/save is modified')
            cls.sources.append((game,rel.read_bytes(),dol.read_bytes(),home.read_bytes()))

    def test_species_name_and_spinda_identity_link_preserve_native_levels_moves_and_other_slots(self):
        for game, original, dol, _ in self.sources:
            gift = next(r for r in special_targets(dol)if r['key']==scene.GIFT_KEY)
            p = layout(original)[0]['trainer_pokemon']['offset']+2822*80
            for chosen in (25, 201, SPINDA):
                current_dol = bytearray(dol); struct.pack_into('>H',current_dol,gift['base']+2,chosen)
                result, report = scene.synchronize_eagun_gift(original,original,dol,bytes(current_dol),game,enabled=True)
                self.assertEqual(u16(result,p+10),chosen)
                species = layout(original)[0]['species']
                self.assertEqual(u32(result,p+0x14),u32(original,species['offset']+chosen*species['stride']+0x18))
                self.assertEqual(result[p+3:p+10],original[p+3:p+10])
                self.assertEqual(result[p+0x18:p+80],original[p+0x18:p+80])
                self.assertEqual(report['trainer_special_aliases'],ALIASES)
                if chosen == SPINDA:
                    seeds=colo_spinda_seeds(original,result,dol,bytes(current_dol),'gift-identity',trainer_special_aliases=ALIASES)
                    self.assertEqual(seeds['trainer:2822'],seeds['special:pikachu-event'])
                    for shiny in (False,True):
                        self.assertEqual(colo_spinda_trainer_pid(original,result,seeds,2822,shiny,trainer_special_aliases=ALIASES),
                                         colo_spinda_gift_pid(seeds,'pikachu-event',shiny))
            self.assertEqual(scene.synchronize_eagun_gift(original,original,dol,dol,game), (original,None))

    def test_home_only_changes_native_actor_three_visibility_operand_in_all_regions(self):
        for game, _, _, home in self.sources:
            cms=decoded_member(home,parse_fsys(home)['members'][1])
            result,report=scene.patch_home_companion_visibility(cms,cms,game)
            self.assertEqual(result[0x38:0x3c],cms[0x38:0x3c])
            self.assertEqual(result[0x678:0x68c],cms[0x678:0x68c])
            self.assertEqual(result[0x312a:0x351f],cms[0x312a:0x351f])
            self.assertTrue(all(a==b or 0x158<=i<0x15d for i,(a,b)in enumerate(zip(cms,result))))
            for received,phone,notice,master_ball,visible in ((0,1,0,0,1),(1,0,0,0,1),
                    (1,1,1,0,1),(1,1,0,0,0),(1,1,1,1,0)):
                flags=dict.fromkeys(events.STORY_FLAGS,1)|{2740:received,3535:phone,2531:notice,3541:master_ball}
                state=execute(result,0x138,flags,stop_at=0x167)
                self.assertEqual(state['visibility'],[[77,3,visible]])
                self.assertEqual(state['flags'],flags)
            for offset in (0x152,0x678,0x38):
                bad=bytearray(cms);bad[offset]^=1
                with self.assertRaises(FormatError):scene.patch_home_companion_visibility(cms,bytes(bad),game)

    def test_seeded_trainer_flag_and_native_spinda_owner_guards_are_composed_for_all_regions(self):
        seed = next(f'eagun-{n}'for n in range(100)if
                    seeded_status(f'eagun-{n}','special:pikachu-event',37.5)!=seeded_status(f'eagun-{n}','trainer:2822',37.5))
        options=replace(Options.none(),accessible_event_gifts=True,custom_shinies=True,seeded_shinies=False,shiny_chance_percent=37.5)
        self.assertTrue(options.seeded_shinies)
        for game,_,dol,_ in self.sources:
            output,report=apply_shiny_rules(dol,dol,options,seed=seed,trainer_special_aliases=ALIASES,
                                           spinda_seeds={'trainer:2822':0x12345678,'special:pikachu-event':0x12345678})
            self.assertEqual(report['seeded_decisions']['trainer_slots']['2822'],report['seeded_decisions']['specials']['pikachu-event'])
            self.assertEqual(report['spinda_pid']['trainer_gift_owners'],{2822:0x7991})
            self.assertTrue(report['outside_whitelist_unchanged'])
            setter={'GC6P01':0x80121470,'GC6E01':0x8011D494,'GC6J01':0x8011AC68}[game]
            bad=bytearray(dol);bad[setter-0x80003000+10]^=1
            with self.assertRaises(FormatError):apply_shiny_rules(dol,bytes(bad),options,seed=seed,
                trainer_special_aliases=ALIASES,spinda_seeds={'trainer:2822':1})


if __name__=='__main__':unittest.main()
