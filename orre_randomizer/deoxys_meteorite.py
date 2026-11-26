"""Reusable native Bag item for changing a saved Deoxys form outside battle.

The item occupies an ordinary item slot, never a finite story/key-item slot.
It is granted only when the native inventory allocator reports room. Messages
use private native banks; no existing dialogue, quest flag or name is replaced.
"""
from __future__ import annotations

import hashlib
import struct
from collections.abc import Mapping

from .castform_portraits import _reservation
from .deoxys import DEOXYS, FORM_ORDER, form_label
from .deoxys_identity import FORM_TAG, FORM_MASK, form_offset
from .engine.analyze_game import FormatError, parse_dol, parse_rel, u32
from .engine.dol_regions import dol_layout
from .engine.gift_move_hooks import _arena_guard, branch
from .engine.shiny_rules import _Code

VERSION = "deoxys-reusable-meteorite-native-v1"
ITEM_ID = 277
MESSAGE_KEYS = ("name", "description", "no_effect", "changed", *FORM_ORDER)
MESSAGE_IDS = {key: 0xF0200 + i for i, key in enumerate(MESSAGE_KEYS)}
LANGUAGES = ("ja", "en", "de", "fr", "it", "es")
_LANG_TAGS = {"ja": b"JP", "en": b"UK", "de": b"GE", "fr": b"FR", "it": b"IT", "es": b"SP"}
_HP_FIELDS = {"colosseum": (0x8A, 0x8C), "xd": (4, 0x90)}
_XD_UNUSED_CALLBACKS = {"GXXP01": 0x800A71F8, "GXXE01": 0x800A60E0, "GXXJ01": 0x800A2578}
_COLO_ITEM_MAPS = {"GC6P01": 0x803B52A0, "GC6E01": 0x803681E8, "GC6J01": 0x80354928}
_TEXT = {
    "en": ("METEORITE", "Changes DEOXYS's\nform.",
           "The METEORITE can only be used on DEOXYS.", "DEOXYS changed form!"),
    "fr": ("MÉTÉORITE", "Change la forme\nde DEOXYS.",
           "La MÉTÉORITE ne peut être utilisée que sur DEOXYS.", "DEOXYS a changé de forme !"),
    "de": ("METEORIT", "Ändert die Form\nvon DEOXYS.",
           "Der METEORIT kann nur bei DEOXYS verwendet werden.", "DEOXYS hat seine Form geändert!"),
    "es": ("METEORITO", "Cambia la forma\nde DEOXYS.",
           "El METEORITO solo se puede usar en DEOXYS.", "¡DEOXYS ha cambiado de forma!"),
    "it": ("METEORITE", "Cambia la forma\ndi DEOXYS.",
           "Il METEORITE può essere usato solo su DEOXYS.", "DEOXYS ha cambiato forma!"),
    "ja": ("いんせき", "デオキシスの\nフォルムを かえる。",
           "いんせきは デオキシスにしか つかえません。", "デオキシスの フォルムが かわった！"),
}
METEORITE_TEXT = {
    language: dict(zip(MESSAGE_KEYS, (*_TEXT[language], *(form_label(form, language).upper() for form in FORM_ORDER)), strict=True))
    for language in LANGUAGES
}

# Qualifications inserted below from exact retail inputs.
# Exact original retail DOL qualifications, generated from the private native audit.
_QUALIFIED = {
    'GC6P01': ('a788176a45eb88dbd227246a7205ab9856bc79f3cca7e4a0f5376cf466664df5', {
        'party_open': (0x80015748, 0x78, '44dc370e32be951418b270e399cb956a517b0ec7812a84cce26a8717bbb9aa17'),
        'party_get': (0x800156A4, 0x80, '0ccd3ff5f22d08f6357307b226f6cb7fe24e8077efe138ab2992c7619a2ff8ca'),
        'party_close': (0x80015724, 0x24, '856b01ee1cc2b6c5bef3ee9475f64d41c5bd1891cf916c7400f81df45fc0e8cd'),
        'choice': (0x8001EE74, 0xAC, '8052991c7087b920996c2e07f1a1ac4ae04fd2c4342963d4ea9250ab54c3a0ce'),
        'have': (0x8012DCF4, 0x9C, '5af372a4a1b4af5afe61718f0b699ff6996d63b40bedb989386310d383d5add8'),
        'can_add': (0x8012DA80, 0x90, '6d4e964e30e55608ca8607ad82b163b7b5d5d503a180732189a4c34ce1fb30bb'),
        'add': (0x8012DC40, 0xB4, '6fa0adf897b7dcbf01c60ccf09571b08637dfce35079790a2d74e8b98fe20d0c'),
        'bag': (0x80019FF4, 0x4C8, 'bca70cb8527c87c8c08aadf215359e49564a82bfbe57d89db6ce7d57bba25064'),
        'actions': (0x80019244, 0x1D4, '532c95aec6ea057856d467215a9286e8aa79c21ef5e3866d73704c2b959f2b00'),
        'use': (0x8001550C, 0x17C, 'a0ed1c6083eb184f59e6f203bb547da72f6d451f24847a3a282f07bf3461da04'),
        'message': (0x8010A268, 0x25C, '5aca1ae21116415c769085a9e0f94847d2d5db71fe71b91b1d3652cfbd2ec951'),
        'recalculate': (0x801295E0, 0x40, '0014c05959b797350775450a2235f8d8ac38dc64460a864d75c3efb231a63e9b'),
        'bank_open': (0x800FF728, 0x64, '0db84c3d1c94ae5f51eeafd70fddfccbbe5b9359b16656a6765e7471331d150f'),
        'bank_close': (0x800FF59C, 0x74, '7c7006c4d3540a01fa1aa295ff892a92bd142190bf82dec9a504e3334ca40b8a'),
        'language': (0x800056D0, 0x14, 'b59d4052a3e698f911a1c07bfed233e1dea219330c3c05bbfd7eef913ac0c91b'),
        'message_close': (0x80109F28, 0xE0, '2f4cd6281a2c66dc0e33f12f18650f51ec7095af855bafb8c459597b0616ba06'),
    }),
    'GC6E01': ('7e6c00a3bd632126d5466cbab856c63ac3c52a5da20b60dba7e756538152c9f4', {
        'party_open': (0x800141BC, 0x78, 'aaac4792ff255f90faab3068ee585fb0c65b4e4e095c7efeebd4be56eedc7dcd'),
        'party_get': (0x80014118, 0x80, '03dcc81504b5bdb4874701345d4cd42ff7f50ed3f1258a7959844d699fe627cc'),
        'party_close': (0x80014198, 0x24, '892aee5761b518f7237a8b11c4f8a513f0ae7bbb410762192eeeea7fb93cbbfb'),
        'choice': (0x8001D8E8, 0xAC, 'c685f09f0ecb91ac1e77dd9a161f1c0bfc37780803e4df4e0b45b0d86f01cd69'),
        'have': (0x80129B2C, 0x9C, 'de7dd7857b69c2a5c74a28cda7b902cd9b317881ab2e52841f8b72bb62091832'),
        'can_add': (0x801298B8, 0x90, 'ed4d736bc34276ca370c040850319bcebcb32748e33cd4ab3bb24630d7a9ab4d'),
        'add': (0x80129A78, 0xB4, 'd085cf0bc5ae8608c976599508170548685ed49042b7e27d2c10f03369e16cc5'),
        'bag': (0x80018A68, 0x4C8, '13fc54df810906282d15aa25085c61723ae0c643b72b4dd448e30d932d2b4ebc'),
        'actions': (0x80017CB8, 0x1D4, '6fa6eca45b236acdd4f2f41cc165986c4310b675478568caad6044fb1691e222'),
        'use': (0x80013F80, 0x17C, '478d31e77feda75bcf34f5cf07afb509256b5599a27c6b5c658bb662ca4db4d5'),
        'message': (0x80106D3C, 0x25C, '21795f08d4194fcec52665dd3490cef98600970871b6731869e19aa88f1a76a8'),
        'recalculate': (0x8012546C, 0x40, '0014c05959b797350775450a2235f8d8ac38dc64460a864d75c3efb231a63e9b'),
        'bank_open': (0x800FC244, 0x64, '0db84c3d1c94ae5f51eeafd70fddfccbbe5b9359b16656a6765e7471331d150f'),
        'bank_close': (0x800FC1D0, 0x74, '7c7006c4d3540a01fa1aa295ff892a92bd142190bf82dec9a504e3334ca40b8a'),
        'message_close': (0x801069FC, 0xE0, '5ff5d6cc4b431da302380cc813dd5e9d7f5f4fd1b1c5f7c2de8e273ee1fb19d3'),
    }),
    'GC6J01': ('64cedd009afb5b944310bd626bed4890de200fa978fea72b58f2c80c2b2ebaf2', {
        'party_open': (0x80014368, 0x78, '2e434a6a5232c5fc15402aeb4c20ec6f8aaa791272e49f828d31116ef7ab4fd1'),
        'party_get': (0x800142C4, 0x80, '918000f09284a3bdc59ff372fc2a03400a92abdf36af05381f9570468913fbe2'),
        'party_close': (0x80014344, 0x24, '3054c4c3b95c9ace335c1528f6177b4fd0952ff729b5c966c4d830fd71c7dccc'),
        'choice': (0x8001DA0C, 0xAC, '775d58b6dcc1f7a24143413ba6f8cc0db775aba99a904d2730d0d61e43f5fd2a'),
        'have': (0x80127268, 0x9C, '23b5d1c51a83ed4e296bfc4616b6254f5c8adc2d0887cf3bf1d2f2420159439f'),
        'can_add': (0x80126FF4, 0x90, '4a21086dc9e4dc8686e30bc490ac3fd50788b6477ef0f62b631bc48b560ab1a2'),
        'add': (0x801271B4, 0xB4, '2b0e863b5e1dd259a35eb3fac49c4c22d2bd769a7949c16383e5993b15368653'),
        'bag': (0x80018C04, 0x4C8, '14120d79e8135e802c1bbc50a989753dd0ebb986d031a874837ce43aaba9e625'),
        'actions': (0x80017E54, 0x1D4, '5e723f70191c8b1eac8d7f9d9e243cba7d357b060881d957f1b64762cd3186c0'),
        'use': (0x8001412C, 0x17C, '6785e544660fbd59510dffd3d264dd37c6f4d15613a277a61f8e40dd6c9fa48d'),
        'message': (0x80104744, 0x25C, '2b96a5e6e91d66fb3f512b04de4d3b0243e364530f36f63d299ebd465f4c01b4'),
        'recalculate': (0x80122C0C, 0x40, '0014c05959b797350775450a2235f8d8ac38dc64460a864d75c3efb231a63e9b'),
        'bank_open': (0x800F9BCC, 0x64, '46d54a9da6725cdde6a32510c6b8167ee6fe049180bf419dc12b2554db43dc55'),
        'bank_close': (0x800F9B58, 0x74, 'a7c2b6a80830f46f421578b5412e8f2c4cd9bbe586deb59b56607b33eae9d29c'),
        'message_close': (0x80104404, 0xE0, '1b4c348e632ab8aaa1a504f1fe44d63a1e686ea6d956741c26eba1f1156c5db3'),
    }),
    'GXXP01': ('a90eae103e6e8471e41c92df1f894f98c2f98d1f9f3a0aca84964492135f5cfd', {
        'party_open': (0x80023EC4, 0x98, '356bdafed853757728ebd7c4b9e2fef4d3ec7f1c3096be1e6cab21df24b1e3e2'),
        'party_get': (0x80023E00, 0x98, '16e9e8721256c4c35cd55cc9597e8dd393d20e7400ed7f7a0bd66d97e5405689'),
        'party_close': (0x80023E98, 0x2C, '192f9d1add4d490d207f80f3d6b81bbaebbbfe49f1ba2368bba9366ec2077a48'),
        'choice': (0x80065060, 0xB0, '3ca6171979d00154838b9719a7d6bc9ba4f4d1acf1e951357304e6f3a1df24c4'),
        'have': (0x8014E43C, 0x78, 'dac515a19463c7486a893751b6cf55e685ee15f82243d8f34f4b31e2970c6b70'),
        'can_add': (0x8014E2B4, 0x6C, 'cc055cf1af5f737e14a823be8481a260f921977a103b6c28365ba83626b77328'),
        'add': (0x8014E3AC, 0x90, 'a777f668e1bf494eee247baec095fdfd65d5c5514a87aed84bd71b6ee53ed6be'),
        'bag': (0x80023ACC, 0x1E4, '8d027d2ad080294c29403a7844a0109009b7ced515e75a4f5441fa53b333a9d6'),
        'actions': (0x80021EE4, 0x14C, '2635e13ddeccae73b3db7784d807a421237a2343d8cd93eea914dbb863721d95'),
        'use': (0x80023140, 0xD0, '6eba34794215a5e631d4c01deabe1cf9b0baf4ff4b3c1eabf38d6f7a53bd6b0a'),
        'item_getter': (0x801603E4, 0x50, '11c683fc415a1692128bdaa4d0975dfdc292ab185f9a96914712f6001642df90'),
        'message': (0x80118BAC, 0x2C, '70e5a48efe74143be9f06d972b4bb883171f6717b86429fec8b4a8d37107fcaa'),
        'recalculate': (0x80143598, 0x40, '94a5b76a13bf7dcc212e25085bc032c5e27cccdb0826dc56663d10e0e4a7b7a4'),
        'bank_open': (0x8010A380, 0x60, '303b4c18f9719018febb58f0b8d1b8c17de9a2b58a0e44d489e93b90b1da7348'),
        'bank_close': (0x8010A30C, 0x74, '25c77a17501b108a5032b886018c549c6c51ac44ed12f51c1755f10388e22512'),
        'language': (0x8005C260, 0x14, 'fdb0a853310af87f0b9ee9aa90bdbf37d1c0cb128865e2f0b8d7c50fe853c0c6'),
        'message_close': (0x80118AEC, 0x94, 'c61310d0b453be97581329c5f3cca79eb3ac76124043d4d2798b83a468618364'),
    }),
    'GXXE01': ('c8659341c252d1b088753d508769344eb6f092b5da5cc7cc0ce1560b32478c15', {
        'party_open': (0x8002420C, 0x98, '22fcbeb82db1d20c7141f2c214b952f5accb7cedd7e0d986714a0515e8bebd8a'),
        'party_get': (0x80024148, 0x98, '56706c7dbbc11e7b2240e02035478ddeb341f6940178f1c8e1b746f10cf66237'),
        'party_close': (0x800241E0, 0x2C, '7cf7a14c8d5c0d371cfe53cd64553276db9ebb2246691594e82377ef1017858f'),
        'choice': (0x80064BA0, 0xB0, 'fb83caabc54b2f94a7168aee6b7f1fe4e46d3eeadb3e8083e9643803c311821e'),
        'have': (0x8014CB78, 0x78, '9cc55532c5644d15a7e46999950ab9cbeb9cb3ac7206c09a6d8712281922cae2'),
        'can_add': (0x8014C9F0, 0x6C, 'b4da27dac6abefb0994a432e18449e4b33e91d47ed43adaa1bac71d2ae19cb58'),
        'add': (0x8014CAE8, 0x90, 'c7f7abd553ecd534940b198d85207bba20241dc5bf87c4d56f53b14594c05dab'),
        'bag': (0x80023E14, 0x1E4, '5f8ce41c596c53115d8c85808c951e95fbc037d27cdb61838024959a3f60e99d'),
        'actions': (0x80022234, 0x14C, 'da5cd03b2790f910e2cf0a7009dcea4205a9addac99ad832c26602022228e85a'),
        'use': (0x80023490, 0xD0, '009df987662d2a022f8d50213a68ba30a68523c106e6c2827556fdcd6fce2c43'),
        'item_getter': (0x8015EB34, 0x50, '11c683fc415a1692128bdaa4d0975dfdc292ab185f9a96914712f6001642df90'),
        'message': (0x80117468, 0x2C, '70e5a48efe74143be9f06d972b4bb883171f6717b86429fec8b4a8d37107fcaa'),
        'recalculate': (0x80141CD4, 0x40, '94a5b76a13bf7dcc212e25085bc032c5e27cccdb0826dc56663d10e0e4a7b7a4'),
        'bank_open': (0x80108D20, 0x60, '303b4c18f9719018febb58f0b8d1b8c17de9a2b58a0e44d489e93b90b1da7348'),
        'bank_close': (0x80108CAC, 0x74, '25c77a17501b108a5032b886018c549c6c51ac44ed12f51c1755f10388e22512'),
        'language': (0x8005C070, 0x14, 'b72cd1c3d075acfcff6fcc4e9ab8507c8cecea9f134a5112dd213128afeb883a'),
        'message_close': (0x801173A8, 0x94, '32bac097d060ad5e629b529f8203eb76c5c227a26c6f421a7847185abc6bfeb5'),
    }),
    'GXXJ01': ('14c129cc0f79682574f635290b09e37fa2a652ac5aa5565281bd583c31c5d702', {
        'party_open': (0x80023D6C, 0x98, '358f4e2fd0ca3c096ef348d63f39404c0938ed84d54be4ead2d390621c569f3a'),
        'party_get': (0x80023CA8, 0x98, 'df222bccdaa74025b05498b50afd42a1d610d973bd5a6d1d382fa4266b02546a'),
        'party_close': (0x80023D40, 0x2C, '2b0245e615d2d057d8b0059b24f5b0a34d5f07d7d937a03e9975bdf8b83c3183'),
        'choice': (0x80063018, 0xB0, 'd808ab5c2aab87df43273675d0106885428677bb1159a2b725024c270ef1f4e4'),
        'have': (0x80147EC0, 0x78, '8abf3db71f614a2ed75e7f20d19c5b2c283066eb695f1dafd035cb5491ee22e3'),
        'can_add': (0x80147D38, 0x6C, '324b9300540181ab3b780807eb453f41c54e37967df2950f5c7d7cb85a8123db'),
        'add': (0x80147E30, 0x90, '52fe0c90c7f874fed7458fad2981dd57dc3f2f042ae1ff061ab89bcb05301bf1'),
        'bag': (0x80023974, 0x1E4, '78fdb614dcb4370ad67b7e0eb8ce8bd6b06f505e80f5cdf9a35ea2ab1dd0b589'),
        'actions': (0x80021DBC, 0x14C, 'aad7e48faee15298a06f5cc0a66593c5b2c92ada8b9894dedb6a8316051cc861'),
        'use': (0x80023018, 0xD0, 'b0445bcf2d7055403b56b841bce5527bf17cd2e76b1646ebff2949618126d3ac'),
        'item_getter': (0x8015A1A0, 0x50, '253341cb442c557b58033e41e3eac5e043972227898704397014f8a7e32358c3'),
        'message': (0x80112B04, 0x2C, '70e5a48efe74143be9f06d972b4bb883171f6717b86429fec8b4a8d37107fcaa'),
        'recalculate': (0x8013D0E0, 0x40, '2cf226de6867874fb8765f660930cc001f100139d0f3b3b867c4abc51128e54b'),
        'bank_open': (0x801047C8, 0x60, '26dffa76ab77b98643e6b8f1b4fed228c8a89c3aec7d2f90419e96412385f6ee'),
        'bank_close': (0x80104754, 0x74, 'd2583d0eb2d837d91084575e8815a32533dff788f309e368514a7f01f4e7cad8'),
        'language': (0x8005A7E8, 0x14, 'b2ff8d1099e49dd7cc648645504314bc6286481cf6261fe5c8bd0dd0b8beacbb'),
        'message_close': (0x80112A44, 0x94, '02ab71c8664f3e5d94334f9b9a9288deb6d0f2f57a857af849c0427acfac9322'),
    }),
}



def _read(data, address, length):
    section = next((s for s in parse_dol(data)["sections"]
                    if s["ram_address"] <= address and address + length <= s["ram_address"] + s["size"]), None)
    if section is None:
        raise FormatError("Meteorite native address is outside executable sections")
    position = section["offset"] + address - section["ram_address"]
    return data[position:position + length]


def _offset(data, address):
    section = next(s for s in parse_dol(data)["sections"]
                   if s["ram_address"] <= address < s["ram_address"] + s["size"])
    return section["offset"] + address - section["ram_address"]


def _load(code, register, value):
    code.emit(0x3C000000 | register << 21 | value >> 16,
              0x60000000 | register << 21 | register << 16 | value & 0xFFFF)


def _messages(ids):
    if (not isinstance(ids, Mapping) or set(ids) != set(MESSAGE_KEYS)
            or any(type(v) is not int or not 0 < v < 0x100000 for v in ids.values())
            or len(set(ids.values())) != len(ids)):
        raise FormatError("Eight distinct Meteorite native message IDs are required")
    return dict(ids)


def _bank(language, ids):
    """Native GSmsgOpen bank: group0, native font/tag, sorted index directory."""
    order = sorted(MESSAGE_KEYS, key=ids.__getitem__)
    output = bytearray(struct.pack(">HBBH2sII", 0, 0, 0 if language == "ja" else 1,
                                   len(order), _LANG_TAGS[language], 0, 0))
    output.extend(bytes(8 * len(order)))
    for index, key in enumerate(order):
        struct.pack_into(">II", output, 16 + 8 * index, ids[key], len(output))
        # A native GSmsg line break is a three-byte control, not UTF-16 LF.
        lines = METEORITE_TEXT[language][key].split("\n")
        output.extend(b"\xff\xff\x00".join(line.encode("utf-16-be") for line in lines) + b"\0\0")
    output.extend(bytes(-len(output) % 32))
    return bytes(output)


def _bank_refresh(address, functions, banks, game_id):
    c = _Code(address)
    c.emit(0x9421FFF0, 0x7C0802A6, 0x90010014)
    # Closing a missing bank is a native no-op. Only our six pointers are used.
    for pointer in banks.values():
        _load(c, 3, pointer)
        c.call(functions["bank_close"])
    if "language" in functions:
        c.call(functions["language"])
    else:
        c.emit(0x38600000 | (1 if game_id == "GC6J01" else 2))
    for native_language, language in enumerate(LANGUAGES, 1):
        c.emit(0x28030000 | native_language)
        c.conditional(0x41820000, language)
    c.jump("en")
    for language in LANGUAGES:
        c.label(language)
        _load(c, 3, banks[language])
        c.jump("register")
    c.label("register")
    c.call(functions["bank_open"])
    c.emit(0x80010014, 0x7C0803A6, 0x38210010, 0x4E800020)
    return c.finish()


def _grant(address, functions):
    c = _Code(address)
    # Native inventory APIs accept Hero0 as the current player. XD's ordinary
    # field Bag deliberately uses that implicit-player convention.
    c.emit(0x9421FFE0, 0x7C0802A6, 0x90010024, 0x93E1001C, 0x7C7F1B78)
    c.emit(0x38800000 | ITEM_ID)
    c.call(functions["have"])
    c.emit(0x28030000)
    c.conditional(0x40820000, "done")
    c.emit(0x7FE3FB78, 0x38800000 | ITEM_ID)
    c.call(functions["can_add"])
    c.emit(0x2C030000)
    # Native CheckAdd returns remaining quantity, not a slot index: 0 is full.
    c.conditional(0x40810000, "done")
    c.emit(0x7FE3FB78, 0x38800000 | ITEM_ID, 0x38A00001, 0x38C0FFFF)
    c.call(functions["add"])
    c.label("done")
    c.emit(0x83E1001C, 0x80010024, 0x7C0803A6, 0x38210020, 0x4E800020)
    return c.finish()


def _bag_open(address, continuation, displaced, *, functions, refresh, grant, game_id, mode_load, hero_load):
    c = _Code(address)
    c.emit(mode_load, 0x2C000000)
    c.conditional(0x40820000, "native")
    c.emit(0x9421FFF0, 0x7C0802A6, 0x90010014)
    c.call(refresh)
    c.emit(hero_load)
    c.call(grant)
    c.emit(0x80010014, 0x7C0803A6, 0x38210010)
    c.label("native")
    c.emit(displaced, branch(address + len(c.words) * 4 + 4, continuation))
    return c.finish()


def _action_filter(address, continuation, displaced, use, *, xd_context=None, item_table_load=None):
    """Keep only Use/Cancel for this item; leave native actions for all others."""
    c = _Code(address)
    if xd_context is None:
        c.emit(0x281C0000 | ITEM_ID)
    else:
        _load(c, 9, xd_context)
        c.emit(0x80090004, 0x2C000000)
        c.conditional(0x40820000, "native")
        # XD retains the resolved raw item row in r31, and the list end in r27.
        # The qualified retail getter supplies its dynamic common REL table.
        c.emit((item_table_load & ~(31 << 21)) | (9 << 21),
               0x39290000 | (ITEM_ID * 40), 0x7C1F4840)
    c.conditional(0x40820000, "native")
    c.emit(0x1C03000C, 0x7D60E850 if xd_context is None else 0x7D60D850,
           0x7D6C5B78, 0x7C6A1B78, 0x38600000)
    _load(c, 9, use)
    c.label("loop")
    c.emit(0x280A0000)
    c.conditional(0x41820000, "native")
    c.emit(0x800B0004, 0x28000000)
    c.conditional(0x41820000, "keep")
    c.emit(0x7C004840)
    c.conditional(0x40820000, "next")
    c.label("keep")
    for offset in (0, 4, 8):
        c.emit(0x800B0000 | offset, 0x900C0000 | offset)
    c.emit(0x398C000C, 0x38630001)
    c.label("next")
    c.emit(0x396B000C, 0x394AFFFF)
    c.jump("loop")
    c.label("native")
    c.emit(displaced, branch(address + len(c.words) * 4 + 4, continuation))
    return c.finish()


def _field_callback(address, functions, ids, choices, game_id):
    family = "colosseum" if game_id.startswith("GC6") else "xd"
    current_hp, maximum_hp = _HP_FIELDS[family]
    tag_offset = form_offset(game_id)
    c = _Code(address)
    c.emit(0x9421FFC0, 0x7C0802A6, 0x90010044, 0xBF61002C,
           0x7C9F2378, 0x38000000, 0x901F0000, 0x3B600001, 0x38800001)
    c.call(functions["party_open"])
    c.emit(0x7C7E1B78, 0x2C1E0000)
    c.conditional(0x41800000, "close")
    c.emit(0x38810010, 0x38A10014)
    c.call(functions["party_get"])
    c.emit(0x83A10010, 0x281D0000)
    c.conditional(0x41820000, "no_effect")
    c.emit(0xA01D0000, 0x28000000 | DEOXYS)
    c.conditional(0x40820000, "no_effect")
    c.emit(0xA01D0000 | tag_offset, 0x28000000)
    c.conditional(0x41820000, "choose")
    c.emit(0x70000000 | FORM_MASK, 0x28000000 | FORM_TAG)
    c.conditional(0x40820000, "no_effect")
    c.label("choose")
    c.emit(0x38600001)
    _load(c, 4, choices)
    c.emit(0x38A00004, 0x38C00070, 0x38E00070, 0x39000000)
    c.call(functions["choice"])
    c.emit(0x28030003)
    c.conditional(0x41810000, "close")
    c.emit(0x60600000 | FORM_TAG, 0xB01D0000 | tag_offset,
           0xA39D0000 | current_hp, 0x7FA3EB78)
    c.call(functions["recalculate"])
    c.emit(0xA01D0000 | maximum_hp, 0x7C1C0040)
    c.conditional(0x40810000, "restore_hp")
    c.emit(0x7C1C0378)
    c.label("restore_hp")
    c.emit(0xB39D0000 | current_hp, 0x3B600000)
    _load(c, 4, ids["changed"])
    c.jump("message")
    c.label("no_effect")
    _load(c, 4, ids["no_effect"])
    c.label("message")
    c.emit(0x38600002, 0x38A00001, 0x38C00000)
    c.call(functions["message"])
    c.emit(0x38600001)
    c.call(functions["message_close"])
    c.label("close")
    c.emit(0x7FC3F378)
    c.call(functions["party_close"])
    c.emit(0x7F63DB78, 0xBB61002C, 0x80010044, 0x7C0803A6, 0x38210040, 0x4E800020)
    return c.finish()


def _callback_relocation(data, first, game_id):
    """Qualify the one existing native module0 callback fixup of item277."""
    rel = parse_rel(data)
    sections = {s["index"]: s for s in rel["sections"]}
    found = []
    for imported in rel["imports"]:
        position, target_section, target_offset = imported["relocations_offset"], None, 0
        for _ in range(len(data) // 8 + 1):
            if position + 8 > len(data):
                raise FormatError("Meteorite REL relocation stream is truncated")
            entry = position
            delta, kind, section, addend = struct.unpack_from(">HBBI", data, position)
            position += 8
            if kind == 203:
                break
            if kind == 202:
                target_section, target_offset = section, 0
                continue
            target_offset += delta
            if kind in (0, 201):
                continue
            native = sections.get(target_section)
            if native is None or native["bss"]:
                continue
            offset = native["offset"] + target_offset
            if offset < first + 40 and first < offset + 4:
                if (offset != first + 28 or kind != 1 or imported["module_id"] != 0
                        or section != 4 or addend != _XD_UNUSED_CALLBACKS[game_id]):
                    raise FormatError("Unexpected Meteorite placeholder REL relocation")
                found.append(entry)
        else:
            raise FormatError("Meteorite REL relocation stream has no terminator")
    if len(found) != 1:
        raise FormatError("Meteorite requires its single native module0 callback relocation")
    return found[0]


def _item_conversion(original, current, game_id):
    """Route a previously unmapped external item ID to its unused raw row.

    Native item getters always consult this u16 conversion array. Filling a raw
    item row alone leaves ID277 mapped to empty row0 and therefore unusable.
    """
    if game_id.startswith('GC6'):
        first, count = _offset(original, _COLO_ITEM_MAPS[game_id]), 548
    else:
        from .engine.inspect_tables import rel_symbols
        symbols = rel_symbols(original, parse_rel(original))
        first, count = symbols[68]['offset'], u32(original, symbols[69]['offset'])
        if count != 594 or first + count * 2 != symbols[70]['offset']:
            raise FormatError('Unexpected XD native item ID conversion array')
    size = count * 2
    if first + size > len(original) or first + size > len(current):
        raise FormatError('Meteorite item conversion array is truncated')
    for data in (original, current):
        values = struct.unpack_from('>' + str(count) + 'H', data, first)
        if values[ITEM_ID] != 0 or ITEM_ID in values:
            raise FormatError('Meteorite item identity or raw row is already mapped')
    return first + ITEM_ID * 2


def install_meteorite(original_dol: bytes, current_dol: bytes, game_id: str, *,
                      message_ids=None, original_rel=None, current_rel=None):
    """Return (DOL, REL-or-None, report) after native Deoxys form/stat hooks.

    The callback needs the saved-form runtime installed first. It never invokes
    the evolution or purification machinery. Existing foreign reserved values
    are refused, and only this item's action list and Bag entry are changed.
    """
    qualification = _QUALIFIED.get(game_id)
    if (qualification is None or type(original_dol) is not bytes or type(current_dol) is not bytes
            or hashlib.sha256(original_dol).hexdigest() != qualification[0]):
        raise FormatError("Unknown original executable for the Deoxys Meteorite")
    functions = {}
    for name, (address, length, expected) in qualification[1].items():
        if hashlib.sha256(_read(original_dol, address, length)).hexdigest() != expected:
            raise FormatError("Meteorite native function failed qualification")
        # Form runtime patches native stat calculation internals, not this wrapper.
        if _read(current_dol, address, length) != _read(original_dol, address, length):
            raise FormatError(f"Meteorite native {name} function has already changed")
        functions[name] = address
    ids = _messages(MESSAGE_IDS if message_ids is None else message_ids)
    family = "colosseum" if game_id.startswith("GC6") else "xd"
    if family == "colosseum":
        table = dol_layout(original_dol).item_table_offset
        item_source, item_current = original_dol, current_dol
    else:
        from .xd_item_rules import _table_offsets
        if type(original_rel) is not bytes or type(current_rel) is not bytes or len(current_rel) < len(original_rel):
            raise FormatError("The XD Meteorite requires original and current common REL bytes")
        _, table = _table_offsets(original_rel)
        item_source, item_current = original_rel, current_rel
    item_position = table + ITEM_ID * 40
    conversion = _item_conversion(item_source, item_current, game_id)
    row = item_source[item_position:item_position + 40]
    if (len(row) != 40 or row[:3] != b"\x05\x01\0" or any(row[3:28])
            or any(row[32:]) or item_current[item_position:item_position + 40] != row):
        raise FormatError("Meteorite item277 is not an unused native placeholder")
    if family == "xd":
        if any(row[28:32]):
            raise FormatError("XD Meteorite field callback is not empty")
        _callback_relocation(original_rel, item_position, game_id)
        relocation = _callback_relocation(current_rel, item_position, game_id)
    offset, ram, setter, store, code = _reservation(original_dol, current_dol, game_id)
    banks = {}
    for language in LANGUAGES:
        banks[language] = ram + len(code)
        code.extend(_bank(language, ids))
    choices = ram + len(code)
    code.extend(struct.pack(">4I", *(ids[form] for form in FORM_ORDER)) + bytes(16))
    refresh = ram + len(code)
    code.extend(_bank_refresh(refresh, functions, banks, game_id))
    grant = ram + len(code)
    code.extend(_grant(grant, functions))
    callback = ram + len(code)
    code.extend(_field_callback(callback, functions, ids, choices, game_id))
    bag = functions["bag"]
    if family == "colosseum":
        hook = bag + 0x10
        target_body = _read(original_dol, functions["party_get"], 0x50)
        mode_load = u32(target_body, 0x24)
        hero_load = u32(target_body, 0x48)
        if mode_load & 0xFFFF0000 != 0x800D0000 or hero_load & 0xFFFF0000 != 0x806D0000:
            raise FormatError("Unexpected Colosseum Bag context globals")
    else:
        hook = bag + 0x34
        # The native loop already loaded its persistent Bag context in r31.
        if _read(original_dol, bag + 0x30, 8) != bytes.fromhex("3be382e4801f0004"):
            # Regional context low halves differ; verify the register/opcode pair.
            words = struct.unpack(">2I", _read(original_dol, bag + 0x30, 8))
            if words[0] & 0xFFFF0000 != 0x3BE30000 or words[1] != 0x801F0004:
                raise FormatError("Unexpected XD Bag context register")
        mode_load, hero_load = 0x801F0004, 0x807F000C
    displaced = u32(_read(original_dol, hook, 4), 0)
    open_stub = ram + len(code)
    code.extend(_bag_open(open_stub, hook + 4, displaced, functions=functions,
                          refresh=refresh, grant=grant, game_id=game_id,
                          mode_load=mode_load, hero_load=hero_load))
    hooks = [(hook, open_stub)]
    action_hook = functions["actions"] + (0x1C0 if family == "colosseum" else 0x138)
    displaced = u32(_read(original_dol, action_hook, 4), 0)
    if displaced != 0xBB210014:
        raise FormatError("Unexpected native Bag action return")
    action_options = {}
    if family == "xd":
        hi = u32(_read(original_dol, functions["actions"] + 0x40, 4), 0)
        lo = u32(_read(original_dol, functions["actions"] + 0x48, 4), 0)
        item_table_load = u32(_read(original_dol, functions["item_getter"] + 0x44, 4), 0)
        if (hi & 0xFFFF0000 != 0x3C800000 or lo & 0xFFFF0000 != 0x38840000
                or item_table_load & 0xFFFF0000 != 0x806D0000):
            raise FormatError("Unexpected XD Bag action context/table")
        context = ((hi & 0xFFFF) << 16) + ((lo & 0xFFFF) - (0x10000 if lo & 0x8000 else 0))
        action_options = dict(xd_context=context, item_table_load=item_table_load)
    target = ram + len(code)
    code.extend(_action_filter(target, action_hook + 4, displaced, functions["use"], **action_options))
    hooks.append((action_hook, target))
    code.extend(bytes(-len(code) % 32))
    if ram + len(code) >= 0x81700000:
        raise FormatError("Meteorite code exceeds the reserved memory limit")
    code[:32] = _arena_guard(ram + len(code), store)
    output = bytearray(current_dol[:offset])
    output.extend(bytes(offset - len(output)))
    output.extend(code)
    for site, target in hooks:
        struct.pack_into(">I", output, _offset(original_dol, site), branch(site, target))
    text_base = 0x800030A0 if family == "xd" else 0x80003000
    for position, value in ((8, offset), (0x50, ram), (0x98, len(code)),
                             (setter - text_base, branch(setter, ram))):
        struct.pack_into(">I", output, position, value)
    new_row = bytearray(40)
    new_row[:3] = bytes((2, 1, 1))
    struct.pack_into(">II", new_row, 16, ids["name"], ids["description"])
    struct.pack_into(">I", new_row, 28, callback)
    if family == "colosseum":
        output[item_position:item_position + 40] = new_row
        struct.pack_into('>H', output, conversion, ITEM_ID)
        rel_output = None
    else:
        rel_output = bytearray(current_rel)
        # REL absolute function pointers are supplied by module0 ADDR32 addends.
        # Keep the source row's pointer convention and redirect only that addend.
        struct.pack_into(">I", new_row, 28, 0)
        rel_output[item_position:item_position + 40] = new_row
        struct.pack_into('>H', rel_output, conversion, ITEM_ID)
        struct.pack_into(">I", rel_output, relocation + 4, callback)
        rel_output = bytes(rel_output)
    return bytes(output), rel_output, {
        "version": VERSION, "game_id": game_id, "item_id": ITEM_ID,
        "item_row": item_position, "pocket": "ordinary items", "important": True,
        "item_conversion_offset": conversion, "item_conversion_row": ITEM_ID,
        "field_callback": callback, "bank_addresses": banks, "message_ids": ids,
        "hooks": [{"address": site, "target": target} for site, target in hooks],
        "availability": "field Bag open; native have/free-slot checks; retry when full",
        "reusable": True, "usable_on_shadow_deoxys": True,
        "form_source": "reserved Para1Amari u16 tag",
        "hp_policy": "min(previous current HP, recalculated maximum HP); fainted stays fainted",
        "story_flags_written": [], "native_key_slots_used": 0,
        "pid_ot_nature_iv_ev_moves_held_item_shadow_identity_preserved": True,
    }
