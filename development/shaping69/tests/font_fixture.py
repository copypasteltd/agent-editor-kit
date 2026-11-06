"""Author-owned MIT TrueType fixture with a deliberately unequal ffi caret map.

The font contains actual outlines, GSUB ligature substitution and GDEF data.
It is a numerical oracle, not evidence for natural typographic quality.
No third-party font generation package or installed font is used.
"""
import struct


def u16(*values):
    return struct.pack('>' + 'H' * len(values), *values)


def checksum(raw):
    raw += b'\0' * (-len(raw) % 4)
    return sum(struct.unpack('>' + 'I' * (len(raw) // 4), raw)) & 0xFFFFFFFF


def post_names(raw):
    """Read independent author names from the pinned font's post v2 table.

    Standard names are labelled by index; the Arabic assertions below use
    actual custom names. No shaping output is used to construct this oracle.
    """
    count = struct.unpack_from('>H', raw, 4)[0]
    records = [struct.unpack_from('>4sIII', raw, 12 + index * 16) for index in range(count)]
    offset, length = next((row[2], row[3]) for row in records if row[0] == b'post')
    table = raw[offset:offset + length]
    assert struct.unpack_from('>I', table)[0] == 0x20000
    glyph_count = struct.unpack_from('>H', table, 32)[0]
    indices = struct.unpack_from('>' + str(glyph_count) + 'H', table, 34)
    position = 34 + glyph_count * 2
    custom = []
    for _ in range(max(indices) - 257):
        size = table[position]
        position += 1
        assert position + size <= len(table)
        custom.append(table[position:position + size].decode('ascii'))
        position += size
    return {glyph: custom[index - 258] if index >= 258 else 'standard:' + str(index)
            for glyph, index in enumerate(indices)}


def font_bytes(*, carets=True):
    glyphs, locations = [], [0]
    for index in range(8):
        width = 1000 if index == 4 else 400
        raw = b'' if index == 1 else (struct.pack('>hhhhh', 1, 0, 0, width, 700) + u16(3, 0)
              + b'\x01' * 4 + struct.pack('>hhhhhhhh', 0, width, 0, -width, 0, 0, 700, 0))
        raw += b'\0' * (-len(raw) % 4)
        glyphs.append(raw)
        locations.append(locations[-1] + len(raw))
    head = bytearray(54)
    struct.pack_into('>IIIIHH', head, 0, 0x10000, 0x10000, 0, 0x5F0F3CF5, 0, 1000)
    struct.pack_into('>hhhhHHhhh', head, 36, 0, 0, 1000, 700, 0, 8, 2, 1, 0)
    hhea = bytearray(36)
    struct.pack_into('>IhhhH', hhea, 0, 0x10000, 800, -200, 100, 1000)
    struct.pack_into('>h', hhea, 18, 1)
    struct.pack_into('>H', hhea, 34, 8)
    maxp = struct.pack('>IH' + 'H' * 13, 0x10000, 8, 4, 1, 0, 0, 2, 0, 0, 0, 0, 0, 0, 0, 0)
    mapping = [(32, 1), (65, 5), (97, 7), (102, 2), (105, 3), (0x301, 6), (0xFFFF, 0)]
    count = len(mapping)
    cmap4 = (u16(4, 16 + 8 * count, 0, count * 2, 8, 2, count * 2 - 8)
             + u16(*(cp for cp, _ in mapping)) + u16(0) + u16(*(cp for cp, _ in mapping))
             + u16(*((gid - cp) & 0xFFFF for cp, gid in mapping)) + u16(*([0] * count)))
    cmap = u16(0, 1, 3, 1) + struct.pack('>I', 12) + cmap4
    script = u16(1) + b'DFLT' + u16(8) + u16(4, 0, 0, 0xFFFF, 1, 0)
    feature = u16(1) + b'liga' + u16(8, 0, 1, 0)
    ligature = u16(1, 8, 1, 14) + u16(1, 1, 2) + u16(1, 4, 4, 3, 2, 3)
    lookup = u16(1, 4, 4, 0, 1, 8) + ligature
    gsub = struct.pack('>IHHH', 0x10000, 10, 10 + len(script), 10 + len(script) + len(feature)) + script + feature + lookup
    classes = u16(1, 2, 3, 1, 1, 2)
    caret_list = u16(6, 1, 12) + u16(1, 1, 4) + u16(2, 6, 10, 1, 200, 1, 800)
    gdef = struct.pack('>IHHHH', 0x10000, 12, 0, 24 if carets else 0, 0) + classes + (caret_list if carets else b'')
    names = {0: 'Copyright 2026 Agent editor kit contributors. MIT License.', 1: 'AEK Geometry Fixture',
             2: 'Regular', 4: 'AEK Geometry Fixture Regular', 6: 'AEKGeometryFixture-Regular', 13: 'MIT License'}
    records, strings = [], b''
    for name, value in names.items():
        encoded = value.encode('utf-16-be')
        records.append(u16(3, 1, 0x409, name, len(encoded), len(strings)))
        strings += encoded
    name = u16(0, len(records), 6 + len(records) * 12) + b''.join(records) + strings
    os2 = bytearray(78)
    struct.pack_into('>HhHHH', os2, 0, 0, 400, 400, 5, 0)
    struct.pack_into('>hhhHH', os2, 68, 800, -200, 100, 800, 200)
    tables = {'head': bytes(head), 'hhea': bytes(hhea), 'maxp': maxp, 'cmap': cmap, 'glyf': b''.join(glyphs),
              'loca': struct.pack('>' + 'I' * len(locations), *locations), 'hmtx': b''.join(u16(1000 if i == 4 else 400, 0) for i in range(8)),
              'name': name, 'post': struct.pack('>I', 0x30000) + b'\0' * 28, 'OS/2': bytes(os2), 'GSUB': gsub, 'GDEF': gdef}
    count = len(tables)
    power = 2 ** (count.bit_length() - 1)
    header = struct.pack('>IHHHH', 0x10000, count, power * 16, power.bit_length() - 1, count * 16 - power * 16)
    records, payload, offset, head_at = [], b'', 12 + 16 * count, 0
    for tag, raw in sorted(tables.items()):
        if tag == 'head':
            head_at = offset
        records.append(tag.encode('ascii') + struct.pack('>III', checksum(raw), offset, len(raw)))
        padded = raw + b'\0' * (-len(raw) % 4)
        payload += padded
        offset += len(padded)
    result = bytearray(header + b''.join(records) + payload)
    struct.pack_into('>I', result, head_at + 8, (0xB1B0AFBA - checksum(bytes(result))) & 0xFFFFFFFF)
    return bytes(result)
