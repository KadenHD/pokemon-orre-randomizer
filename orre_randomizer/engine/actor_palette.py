"""Apply the retail PKX color recipe to a stand-alone field model."""

import struct

from .analyze_game import FormatError, check_range, u32

_BLOCKS = {4: (4, 4, 32), 5: (4, 4, 32), 6: (4, 4, 64), 14: (8, 8, 32)}
_SWAP_CMPR_ALPHA = bytes(
    sum((1, 0, 2, 3)[value >> shift & 3] << shift for shift in (0, 2, 4, 6))
    for value in range(256)
)


def pkx_recipe(pkx, *, xd):
    # Routing is stored in four words; the multipliers follow in RGBA (XD)
    # or reversed order (Colosseum). 127 is the neutral multiplier.
    raw = pkx[0x73:0x84] if xd else pkx[-0x11:]
    route = tuple(raw[0:13:4])
    gain = tuple(raw[13:] if xd else raw[13:][::-1])
    if len(route) != 4 or len(gain) != 4 or any(channel > 3 for channel in route):
        raise FormatError("unexpected retail PKX color recipe")
    return route, gain


def tint_field_model(data, relocations, model, recipe):
    route, gain = recipe
    if route == (0, 1, 2, 3) and gain[:3] == (127, 127, 127):
        return
    images, palettes, solid = _walk_materials(data, relocations, model)
    source = bytes(data)

    def color(rgba):
        return tuple(min(255, (rgba[route[i]] * (gain[i] + 1) + 64) // 128)
                     for i in range(3))

    def convert(value, fmt):
        def unpack(bits, depth):
            return ((bits & ((1 << depth) - 1)) * 255 + (1 << (depth - 1))) // ((1 << depth) - 1)

        def pack(component, depth):
            return (component * ((1 << depth) - 1) + 127) // 255

        if fmt == 4:
            r, g, b = color((unpack(value >> 11, 5), unpack(value >> 5, 6), unpack(value, 5), 255))
            return pack(r, 5) << 11 | pack(g, 6) << 5 | pack(b, 5)
        if value & 0x8000:
            r, g, b = color((unpack(value >> 10, 5), unpack(value >> 5, 5), unpack(value, 5), 255))
            return 0x8000 | pack(r, 5) << 10 | pack(g, 5) << 5 | pack(b, 5)
        r, g, b = color((unpack(value >> 8, 4), unpack(value >> 4, 4), unpack(value, 4), unpack(value >> 12, 3)))
        return value & 0x7000 | pack(r, 4) << 8 | pack(g, 4) << 4 | pack(b, 4)

    written = set()

    def words(start, end, fmt):
        for at in range(start, end, 2):
            if at not in written:
                value, = struct.unpack_from(">H", source, at)
                struct.pack_into(">H", data, at, convert(value, fmt))
                written.add(at)

    for palette in sorted(palettes):
        start, fmt, _, count = struct.unpack_from(">IIIH", source, palette)
        check_range(source, start, 2 * count, "field Pokémon texture palette")
        if fmt in (1, 2):
            words(start, start + 2 * count, fmt + 3)
        elif fmt != 0:
            raise FormatError("unexpected field Pokémon texture palette format")
    for image in sorted(images):
        start, width, height, fmt, mipmap, _, max_lod = struct.unpack_from(">IHHIIff", source, image)
        # Intensity and indexed images retain their native samples. Indexed
        # colors are handled by the corresponding palettes above.
        if fmt in (0, 1, 2, 3, 8, 9, 10):
            continue
        if fmt not in _BLOCKS or not 0 < width <= 1024 or not 0 < height <= 1024:
            raise FormatError("unexpected field Pokémon image format")
        x, y, stride = _BLOCKS[fmt]
        if mipmap and not 0 <= max_lod <= 10:
            raise FormatError("unexpected field Pokémon mipmap range")
        size = sum(
            ((max(1, width >> i) + x - 1) // x) * ((max(1, height >> i) + y - 1) // y) * stride
            for i in range(1 + (int(max_lod) if mipmap else 0))
        )
        end = start + size
        check_range(source, start, size, "field Pokémon texture data")
        if fmt in (4, 5):
            words(start, end, fmt)
        elif fmt == 6:
            for block in range(start, end, 64):
                if block in written:
                    continue
                for at in range(block, block + 32, 2):
                    r, g, b = color((source[at + 1], source[at + 32], source[at + 33], source[at]))
                    data[at + 1] = r
                    data[at + 32:at + 34] = bytes((g, b))
                written.add(block)
        else:
            for at in range(start, end, 8):
                if at in written:
                    continue
                a, b, indices = struct.unpack_from(">HH4s", source, at)
                c, d = convert(a, 4), convert(b, 4)
                if a > b and c == d:
                    indices = bytes(4)  # the transformed opaque endpoints collapsed
                elif (a > b) != (c > d):
                    c, d = d, c
                    indices = bytes(v ^ 0x55 for v in indices) if a > b else indices.translate(_SWAP_CMPR_ALPHA)
                struct.pack_into(">HH4s", data, at, c, d, indices)
                written.add(at)
    for material in solid:
        for at in (material, material + 4):
            data[at:at + 3] = bytes(color(source[at:at + 4]))


def _walk_materials(data, relocations, model):
    """Collect textures and idle texture frames through the HSD pointer graph."""
    images, palettes, solid = set(), set(), set()
    seen = set()

    def pointer(slot):
        if slot in relocations:
            offset = u32(data, slot)
            check_range(data, offset, 4, "field color resource")
            return offset
        return None

    def visit(kind, *slots):
        stack = [offset for slot in slots if (offset := pointer(slot)) is not None]
        while stack:
            at = stack.pop()
            key = (kind, at)
            if key in seen:
                continue
            seen.add(key)
            yield at
            links = {"joints": (8, 12), "mat_joints": (0, 4)}.get(kind, (4,) if kind in ("meshes", "textures") else (0,))
            stack.extend(offset for link in links if (offset := pointer(at + link)) is not None)

    def collect(target, slot):
        if (offset := pointer(slot)) is not None:
            target.add(offset)

    for joint in visit("joints", model):
        if u32(data, joint + 4) & ((1 << 5) | (1 << 14)):  # particle and spline properties
            continue
        for mesh in visit("meshes", joint + 16):
            material = pointer(mesh + 8)
            if material is None:
                continue
            if pointer(material + 8) is None:
                collect(solid, material + 12)
            for texture in visit("textures", material + 8):
                collect(images, texture + 0x4C)
                collect(palettes, texture + 0x50)
    idle_material_table = pointer(model + 8)
    if idle_material_table is not None and u32(data, idle_material_table):
        for joint in visit("mat_joints", idle_material_table):
            for material in visit("mat_anims", joint + 8):
                for texture in visit("tex_anims", material + 8):
                    counts = struct.unpack_from(">HH", data, texture + 0x14)
                    for target, slot, count in zip((images, palettes), (texture + 12, texture + 16), counts, strict=True):
                        table = pointer(slot)
                        if table is not None:
                            check_range(data, table, count * 4, "field texture animation table")
                            for index in range(count):
                                collect(target, table + index * 4)
    return images, palettes, solid
