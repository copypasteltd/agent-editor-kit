// Agent editor kit text candidate: Unicode bidi, OpenType shaping and raster ABI.
// MIT for this wrapper. Upstream engines retain their individual licenses.
// All source text indices are UTF-32 scalar offsets; geometry is signed 26.6.
#include <SheenBidi/SheenBidi.h>
#include <hb.h>
#include <hb-ot.h>
#include <hb-ft.h>
#include <ft2build.h>
#include FT_FREETYPE_H
#include FT_MULTIPLE_MASTERS_H
#include <algorithm>
#include <cmath>
#include <cstdint>
#include <cstring>
#include <new>
#include <vector>

#define AEK_API extern "C" __declspec(dllexport)
static const uint32_t MAX_TEXT = 16384;
static const uint32_t MAX_GLYPHS = 65536;
static const FT_Int32 LOAD_FLAGS = FT_LOAD_NO_HINTING | FT_LOAD_NO_AUTOHINT | FT_LOAD_NO_BITMAP;

struct AekRun { uint32_t start, length, level, tag; };
struct AekGlyph {
    uint32_t id, cluster, flags;
    int32_t x_advance, y_advance, x_offset, y_offset;
    int32_t x_bearing, y_bearing, width, height;
};
struct AekFeature { uint32_t tag, value; };
struct AekAxis { uint32_t tag; float value; };
struct AekFont {
    std::vector<uint8_t> bytes;
    FT_Library library = nullptr;
    FT_Face face = nullptr;
    hb_font_t *font = nullptr;
    ~AekFont() {
        if (font) hb_font_destroy(font);
        if (face) FT_Done_Face(face);
        if (library) FT_Done_FreeType(library);
    }
};

static bool valid_text(const uint32_t *text, uint32_t length) {
    if (length > MAX_TEXT || (length && !text)) return false;
    for (uint32_t i = 0; i < length; ++i)
        if (!SBCodepointIsValid(text[i])) return false;
    return true;
}
static bool removed_x9(SBBidiType type) {
    return type == SBBidiTypeBN || type == SBBidiTypeLRE || type == SBBidiTypeRLE ||
        type == SBBidiTypeLRO || type == SBBidiTypeRLO || type == SBBidiTypePDF;
}

AEK_API uint32_t aek_text_abi() { return 1; }
AEK_API const char *aek_sheen_version() { return SBVersionGetString(); }
AEK_API const char *aek_harfbuzz_version() { return hb_version_string(); }
AEK_API void aek_freetype_version(int32_t *major, int32_t *minor, int32_t *patch) {
    if (major) *major = FREETYPE_MAJOR;
    if (minor) *minor = FREETYPE_MINOR;
    if (patch) *patch = FREETYPE_PATCH;
}

// One paragraph, and one explicit line range inside it. Returned levels include
// L1 resets from SBLine. X9 characters have level255 and are omitted from order.
AEK_API int32_t aek_bidi(const uint32_t *text, uint32_t length, uint32_t base,
    uint32_t line_start, uint32_t line_length, uint8_t *levels, uint32_t *order,
    uint32_t *order_count, AekRun *runs, uint32_t capacity, uint32_t *run_count,
    uint32_t *resolved_base) {
    if (!valid_text(text, length) || !length || !levels || !order || !order_count ||
        !runs || !run_count || !resolved_base || capacity < length ||
        line_start > length || !line_length || line_length > length - line_start ||
        (base != 0 && base != 1 && base != 254 && base != 253)) return 1;
    SBCodepointSequence sequence = { SBStringEncodingUTF32, text, length };
    SBAlgorithmRef algorithm = SBAlgorithmCreate(&sequence);
    if (!algorithm) return 2;
    SBParagraphRef paragraph = SBAlgorithmCreateParagraph(algorithm, 0, length, (SBLevel)base);
    if (!paragraph) { SBAlgorithmRelease(algorithm); return 3; }
    if (SBParagraphGetLength(paragraph) != length) {
        SBParagraphRelease(paragraph); SBAlgorithmRelease(algorithm); return 4;
    }
    SBLineRef line = SBParagraphCreateLine(paragraph, line_start, line_length);
    if (!line) { SBParagraphRelease(paragraph); SBAlgorithmRelease(algorithm); return 5; }
    const SBBidiType *types = SBAlgorithmGetBidiTypesPtr(algorithm);
    const SBRun *source_runs = SBLineGetRunsPtr(line);
    SBUInteger count = SBLineGetRunCount(line);
    const SBLevel *paragraph_levels = SBParagraphGetLevelsPtr(paragraph);
    std::memcpy(levels, paragraph_levels, length);
    *order_count = 0;
    *run_count = (uint32_t)count;
    *resolved_base = SBParagraphGetBaseLevel(paragraph);
    int32_t status = count <= capacity ? 0 : 6;
    if (!status) {
        for (uint32_t i = 0; i < count; ++i) {
            const SBRun &run = source_runs[i];
            if (run.offset > length || run.length > length - run.offset) { status = 7; break; }
            runs[i] = { (uint32_t)run.offset, (uint32_t)run.length, run.level, 0 };
            for (uint32_t j = 0; j < run.length; ++j) {
                uint32_t index = (uint32_t)run.offset + ((run.level & 1) ? (uint32_t)run.length - j - 1 : j);
                levels[index] = removed_x9(types[index]) ? 255 : run.level;
                if (!removed_x9(types[index])) order[(*order_count)++] = index;
            }
        }
    }
    SBLineRelease(line);
    SBParagraphRelease(paragraph);
    SBAlgorithmRelease(algorithm);
    return status;
}

AEK_API int32_t aek_scripts(const uint32_t *text, uint32_t length, AekRun *runs,
    uint32_t capacity, uint32_t *run_count) {
    if (!valid_text(text, length) || !runs || capacity < length || !run_count) return 1;
    *run_count = 0;
    if (!length) return 0;
    SBCodepointSequence sequence = { SBStringEncodingUTF32, text, length };
    SBScriptLocatorRef locator = SBScriptLocatorCreate();
    if (!locator) return 2;
    SBScriptLocatorLoadCodepoints(locator, &sequence);
    int32_t status = 0;
    while (SBScriptLocatorMoveNext(locator)) {
        const SBScriptAgent *agent = SBScriptLocatorGetAgent(locator);
        if (*run_count >= capacity || agent->offset > length || agent->length > length - agent->offset) { status = 3; break; }
        runs[(*run_count)++] = { (uint32_t)agent->offset, (uint32_t)agent->length, 0,
                                SBScriptGetUnicodeTag(agent->script) };
    }
    SBScriptLocatorRelease(locator);
    return status;
}

AEK_API AekFont *aek_font_create(const uint8_t *bytes, uint32_t length,
    uint32_t index, uint32_t pixels, const AekAxis *axes, uint32_t axis_count, int32_t *error) {
    if (!error) return nullptr;
    *error = 1;
    if (!bytes || length < 12 || length > 64 * 1024 * 1024 || index > 1024 ||
        pixels < 4 || pixels > 512 || axis_count > 32 || (axis_count && !axes)) return nullptr;
    AekFont *result = nullptr;
    try {
        result = new AekFont();
        result->bytes.assign(bytes, bytes + length);
        if (FT_Init_FreeType(&result->library) ||
            FT_New_Memory_Face(result->library, result->bytes.data(), length, index, &result->face)) {
            *error = 2; delete result; return nullptr;
        }
        if (!FT_IS_SCALABLE(result->face) || FT_HAS_COLOR(result->face) ||
            FT_Select_Charmap(result->face, FT_ENCODING_UNICODE)) {
            *error = 3; delete result; return nullptr;
        }
        if (axis_count) {
            FT_MM_Var *variation = nullptr;
            if (FT_Get_MM_Var(result->face, &variation) || !variation) {
                *error = 4; delete result; return nullptr;
            }
            std::vector<FT_Fixed> coordinates(variation->num_axis);
            for (uint32_t i = 0; i < variation->num_axis; ++i) coordinates[i] = variation->axis[i].def;
            bool okay = true;
            for (uint32_t i = 0; i < axis_count && okay; ++i) {
                bool found = false;
                for (uint32_t j = 0; j < variation->num_axis; ++j) {
                    if (axes[i].tag == variation->axis[j].tag) {
                        double value = (double)axes[i].value * 65536.0;
                        if (!std::isfinite(value) || value < variation->axis[j].minimum || value > variation->axis[j].maximum) okay = false;
                        else coordinates[j] = (FT_Fixed)std::llround(value);
                        found = true; break;
                    }
                }
                okay = okay && found;
            }
            if (okay) okay = FT_Set_Var_Design_Coordinates(result->face, variation->num_axis, coordinates.data()) == 0;
            FT_Done_MM_Var(result->library, variation);
            if (!okay) { *error = 5; delete result; return nullptr; }
        }
        if (FT_Set_Char_Size(result->face, 0, pixels * 64, 72, 72)) {
            *error = 6; delete result; return nullptr;
        }
        result->font = hb_ft_font_create_referenced(result->face);
        if (!result->font || result->font == hb_font_get_empty()) {
            *error = 7; delete result; return nullptr;
        }
        hb_ft_font_set_load_flags(result->font, LOAD_FLAGS);
        hb_font_set_scale(result->font, pixels * 64, pixels * 64);
        hb_font_set_ppem(result->font, pixels, pixels);
        *error = 0;
        return result;
    } catch (...) { delete result; *error = 8; return nullptr; }
}

AEK_API void aek_font_destroy(AekFont *font) { delete font; }
AEK_API uint32_t aek_font_nominal(AekFont *font, uint32_t codepoint) {
    if (!font || !SBCodepointIsValid(codepoint)) return 0;
    hb_codepoint_t glyph = 0;
    return hb_font_get_nominal_glyph(font->font, codepoint, &glyph) ? glyph : 0;
}
AEK_API int32_t aek_font_metrics(AekFont *font, int32_t *metrics) {
    if (!font || !metrics) return 1;
    metrics[0] = (int32_t)font->face->size->metrics.ascender;
    metrics[1] = (int32_t)font->face->size->metrics.descender;
    metrics[2] = (int32_t)font->face->size->metrics.height;
    metrics[3] = (int32_t)font->face->units_per_EM;
    return 0;
}

AEK_API int32_t aek_shape(AekFont *font, const uint32_t *text, uint32_t length,
    uint32_t start, uint32_t count, uint32_t rtl, uint32_t script, const char *language,
    const AekFeature *features, uint32_t feature_count, AekGlyph *glyphs,
    uint32_t capacity, uint32_t *glyph_count) {
    if (!font || !valid_text(text, length) || start > length || count > length - start ||
        !glyphs || !glyph_count || capacity > MAX_GLYPHS || feature_count > 64 || (feature_count && !features)) return 1;
    hb_buffer_t *buffer = hb_buffer_create();
    if (!buffer) return 2;
    int32_t status = 0;
    try {
        hb_buffer_add_codepoints(buffer, text, length, start, count);
        hb_buffer_set_direction(buffer, rtl ? HB_DIRECTION_RTL : HB_DIRECTION_LTR);
        hb_buffer_set_script(buffer, hb_script_from_iso15924_tag(script));
        hb_buffer_set_language(buffer, hb_language_from_string(language ? language : "und", -1));
        hb_buffer_set_cluster_level(buffer, HB_BUFFER_CLUSTER_LEVEL_MONOTONE_GRAPHEMES);
        hb_buffer_set_flags(buffer, (hb_buffer_flags_t)(HB_BUFFER_FLAG_REMOVE_DEFAULT_IGNORABLES | HB_BUFFER_FLAG_PRODUCE_UNSAFE_TO_CONCAT));
        std::vector<hb_feature_t> values(feature_count);
        for (uint32_t i = 0; i < feature_count; ++i)
            values[i] = { features[i].tag, features[i].value, HB_FEATURE_GLOBAL_START, HB_FEATURE_GLOBAL_END };
        hb_shape(font->font, buffer, values.data(), feature_count);
        unsigned int n = 0;
        hb_glyph_info_t *infos = hb_buffer_get_glyph_infos(buffer, &n);
        hb_glyph_position_t *positions = hb_buffer_get_glyph_positions(buffer, nullptr);
        *glyph_count = n;
        if (!hb_buffer_allocation_successful(buffer) || n > capacity) status = 3;
        else for (uint32_t i = 0; i < n; ++i) {
            hb_glyph_extents_t extents = { 0, 0, 0, 0 };
            hb_font_get_glyph_extents(font->font, infos[i].codepoint, &extents);
            glyphs[i] = { infos[i].codepoint, infos[i].cluster, (uint32_t)hb_glyph_info_get_glyph_flags(&infos[i]),
                positions[i].x_advance, positions[i].y_advance, positions[i].x_offset, positions[i].y_offset,
                extents.x_bearing, extents.y_bearing, extents.width, extents.height };
        }
    } catch (...) { status = 4; }
    hb_buffer_destroy(buffer);
    return status;
}

AEK_API int32_t aek_carets(AekFont *font, uint32_t glyph, uint32_t rtl,
    int32_t *positions, uint32_t capacity, uint32_t *count) {
    if (!font || !positions || !count || capacity > 256) return 1;
    unsigned int available = capacity;
    unsigned int total = hb_ot_layout_get_ligature_carets(font->font,
        rtl ? HB_DIRECTION_RTL : HB_DIRECTION_LTR, glyph, 0, &available, positions);
    *count = total;
    return total > capacity ? 2 : 0;
}

// Glyph origin subpixel phases are 0..63 in a canvas whose y axis points down.
AEK_API int32_t aek_bitmap(AekFont *font, uint32_t glyph, uint32_t phase_x,
    uint32_t phase_y, uint8_t *pixels, uint32_t capacity, int32_t *metrics) {
    if (!font || !metrics || phase_x > 63 || phase_y > 63 || glyph >= (uint32_t)font->face->num_glyphs) return 1;
    FT_Vector delta = { (FT_Pos)phase_x, -(FT_Pos)phase_y };
    FT_Set_Transform(font->face, nullptr, &delta);
    FT_Error error = FT_Load_Glyph(font->face, glyph, LOAD_FLAGS);
    if (!error) error = FT_Render_Glyph(font->face->glyph, FT_RENDER_MODE_NORMAL);
    FT_Set_Transform(font->face, nullptr, nullptr);
    if (error) return 2;
    FT_GlyphSlot slot = font->face->glyph;
    FT_Bitmap &bitmap = slot->bitmap;
    if (bitmap.width > 4096 || bitmap.rows > 4096 || (uint64_t)bitmap.width * bitmap.rows > 4 * 1024 * 1024) return 3;
    metrics[0] = (int32_t)bitmap.width; metrics[1] = (int32_t)bitmap.rows;
    metrics[2] = slot->bitmap_left; metrics[3] = slot->bitmap_top;
    if (!pixels && !capacity) return 0;
    if (!pixels || capacity < bitmap.width * bitmap.rows || bitmap.pixel_mode != FT_PIXEL_MODE_GRAY) return 4;
    for (uint32_t y = 0; y < bitmap.rows; ++y) {
        const uint8_t *source = bitmap.pitch >= 0 ? bitmap.buffer + y * bitmap.pitch :
            bitmap.buffer + (bitmap.rows - 1 - y) * (-(int64_t)bitmap.pitch);
        std::memcpy(pixels + y * bitmap.width, source, bitmap.width);
    }
    return 0;
}
