/* C03 bounded export parser + finite supplied-catalog binder.
 * SOURCE ONLY / UNCOMPILED / UNRUN. Build this TU INSTEAD OF both included
 * TUs; there is ONE original static owner. No .def/build/loader is changed.
 * These plain native functions are not added to the installed 17-export ABI.
 * Microsoft PE format primary contract (retrieved 2026-10-17):
 * https://learn.microsoft.com/en-us/windows/win32/debug/pe-format#the-edata-section-image-only
 * EAT name ordinals are unbiased u16 indices; export Base biases each EAT
 * index. An RVA inside the export directory denotes a forwarder string.
 * Documentation is not installed support, authority, closure or provenance.
 */
#include "route2_windows_owned_observation.c"
#include "route2_windows_preload_catalog.h"

struct r2_pc_cached_v1 {
    struct r2_pe_raw_report_v1 raw;
    struct r2_pc_exports_v1 exports;
    uint32_t key_length;
    unsigned char key[R2_PC_KEY_BYTES];
};
struct r2_pc_storage_v1 { struct r2_pc_cached_v1 images[R2_PC_IMAGES]; };
struct r2_pc_workspace_v1 {
    struct r2_pc_storage_v1 storage;
    unsigned char reserved[R2_PC_WORKSPACE_BYTES - sizeof(struct r2_pc_storage_v1)];
};
_Static_assert(sizeof(uintptr_t) == 8 && sizeof(size_t) == 8, "AMD64 native ABI");
_Static_assert(sizeof(struct r2_pc_image_v1) == 152 &&
    sizeof(struct r2_pc_input_v1) == 2448, "catalog input ABI");
_Static_assert(sizeof(struct r2_pc_function_v1) == 40 &&
    sizeof(struct r2_pc_name_v1) == 16 &&
    sizeof(struct r2_pc_exports_v1) == 229480, "export facts ABI");
_Static_assert(sizeof(struct r2_pc_hop_v1) == 40 &&
    sizeof(struct r2_pc_edge_v1) == 1360 &&
    sizeof(struct r2_pc_image_report_v1) == 80 &&
    sizeof(struct r2_pc_report_v1) == 5571936, "catalog output ABI");
_Static_assert(sizeof(struct r2_pc_abi_v1) == 112 &&
    sizeof(struct r2_pc_workspace_v1) == R2_PC_WORKSPACE_BYTES &&
    sizeof(struct r2_pc_storage_v1) <= R2_PC_WORKSPACE_BYTES &&
    _Alignof(struct r2_pc_storage_v1) <= 8, "fixed caller workspace ABI");
_Static_assert(R2_PC_IMAGES <= 32 && R2_PC_FILE_BYTES == R2_PE_RAW_FILE_LIMIT &&
    R2_PC_NAME_BYTES == R2_PE_RAW_NAME_LIMIT &&
    R2_PC_NAME_READ_BYTES == R2_PE_RAW_NAME_BYTES_LIMIT && R2_PC_EDGES == R2_PE_RAW_SYMBOL_LIMIT &&
    R2_PC_VALIDATION_WORK <= R2_PC_LOOKUP_WORK &&
    R2_PC_READ_WORK == (uint64_t)R2_PC_IMAGES * R2_PE_RAW_WORK_LIMIT,
    "finite limits must match the reused parser and metadata reservation");

/* Pointer integer checks precede all input reads/output writes. Actual valid
 * readable memory, caller stability and exclusivity remain C preconditions.
 */
static int r2_pc_range_v1(const void *p, uint64_t n, uint32_t alignment)
{
    uintptr_t a = (uintptr_t)p;
    return p && !(a % alignment) && n <= UINTPTR_MAX - a;
}
static int r2_pc_overlap_v1(const void *a, uint64_t an, const void *b, uint64_t bn)
{
    uintptr_t x = (uintptr_t)a, y = (uintptr_t)b;
    return an && bn && x < y + bn && y < x + an;
}
static unsigned char r2_pc_fold_v1(unsigned char b)
{
    return b >= 'A' && b <= 'Z' ? (unsigned char)(b + ('a' - 'A')) : b;
}
/* Key parsing is bounded by 128 input bytes, also for import/forward module
 * substrings. No locale, path parsing, extension guessing or OS query exists.
 */
static int r2_pc_key_v1(const unsigned char *p, uint32_t n,
    unsigned char *out, uint32_t *length)
{
    uint32_t i;
    if (!n || n > R2_PC_KEY_BYTES) return 0;
    for (i = 0; i < n; ++i) {
        unsigned char b = p[i];
        if (!((b >= 'A' && b <= 'Z') || (b >= 'a' && b <= 'z') ||
            (b >= '0' && b <= '9') || b == '_' || b == '-' || b == '.')) return 0;
        if (b == '.' && (!i || i + 1 == n || p[i - 1] == '.')) return 0;
    }
    if (n >= 4 && p[n - 4] == '.' && r2_pc_fold_v1(p[n - 3]) == 'd' &&
        r2_pc_fold_v1(p[n - 2]) == 'l' && r2_pc_fold_v1(p[n - 1]) == 'l') n -= 4;
    if (!n || p[n - 1] == '.') return 0;
    if (out) for (i = 0; i < n; ++i) out[i] = r2_pc_fold_v1(p[i]);
    *length = n;
    return 1;
}
static int r2_pc_apiset_v1(const unsigned char *p, uint32_t n)
{
    return n >= 4 && ((p[0] == 'a' && p[1] == 'p' && p[2] == 'i') ||
        (p[0] == 'e' && p[1] == 'x' && p[2] == 't')) && p[3] == '-';
}
static void r2_pc_export_init_v1(struct r2_pc_exports_v1 *e)
{
    memset(e, 0, sizeof(*e));
    e->abi = R2_PC_ABI; e->size = sizeof(*e); e->status = R2_PC_PARTIAL;
    e->preload_scope = R2_PC_UNPROVEN;
}
static int r2_pc_export_fail_v1(struct r2_pc_exports_v1 *e,
    uint32_t status, uint32_t reason, uint64_t off)
{
    if (!e->reason) { e->status = status; e->reason = reason; e->failure_offset = off; }
    return 0;
}
/* Cumulative per-image original FILE string-read reservation. The old raw
 * parser charged initial import strings; every wrapper scan and reread shares
 * its retained counter. Reservations precede reads and are never refunded,
 * including bounded conservative key-parser reservations and failed work.
 */
static int r2_pc_parse_string_charge_v1(struct r2_pe_context_v1 *c, uint64_t n, uint64_t off)
{
    if (c->r->names_inspected_bytes > R2_PC_NAME_READ_BYTES ||
        n > R2_PC_NAME_READ_BYTES - c->r->names_inspected_bytes)
        return r2_pe_limit_v1(c, R2_PE_REASON_NAME_BYTES_LIMIT, off);
    c->r->names_inspected_bytes += (uint32_t)n;
    return r2_pe_charge_v1(c, n, off);
}
/* Export strings use the original mapper; no section stitching/zero-fill.
 * A forwarder's allowed contiguous span is additionally clipped to the export
 * directory interval, including its NUL. Partial raw offset/length retained.
 */
static int r2_pc_string_v1(struct r2_pe_context_v1 *c,
    struct r2_pc_exports_v1 *e, uint32_t rva, uint32_t forward,
    uint32_t *offset, uint32_t *length)
{
    uint32_t off, span, i;
    *offset = 0; *length = 0;
    if (!r2_pe_map_v1(c, rva, 1, &off, &span)) return 0;
    *offset = off;
    if (forward) {
        uint64_t end = (uint64_t)e->directory_rva + e->directory_size;
        if (rva < e->directory_rva || rva >= end)
            return r2_pc_export_fail_v1(e, R2_PC_REJECTED, R2_PC_EXPORT_DIRECTORY, rva);
        if (span > end - rva) span = (uint32_t)(end - rva);
    }
    for (i = 0; i < span && i < R2_PC_NAME_BYTES; ++i) {
        unsigned char b;
        if (!r2_pc_parse_string_charge_v1(c, 1, off + i)) return 0;
        b = c->file[off + i];
        if (!b) {
            if (!i && !forward) return r2_pc_export_fail_v1(e, R2_PC_REJECTED,
                R2_PC_EXPORT_NAME, off);
            *length = i; return 1;
        }
        *length = i + 1;
        if (b > 0x7Fu) return r2_pc_export_fail_v1(e, R2_PC_REJECTED,
            R2_PC_NONASCII, off + i);
    }
    return r2_pc_export_fail_v1(e, i == R2_PC_NAME_BYTES ? R2_PC_PARTIAL : R2_PC_REJECTED,
        i == R2_PC_NAME_BYTES ? R2_PC_NAME_LIMIT :
        (forward ? R2_PC_FORWARDER_NUL : R2_PC_EXPORT_NAME), off + i);
}
static uint32_t r2_pc_forward_grammar_v1(struct r2_pe_context_v1 *c,
    uint32_t off, uint32_t n)
{
    uint32_t i, dot = R2_PC_NONE, key_length, value = 0;
    for (i = 0; i < n; ++i) {
        if (!r2_pc_parse_string_charge_v1(c, 1, off + i)) return R2_PC_READ_LIMIT;
        if (c->file[off + i] == '.') {
            if (dot != R2_PC_NONE) return R2_PC_FORWARDER_GRAMMAR;
            dot = i;
        }
    }
    if (dot == R2_PC_NONE || !dot || dot + 1 == n) return R2_PC_FORWARDER_GRAMMAR;
    if (!r2_pc_parse_string_charge_v1(c, (uint64_t)dot * 2u + 16u, off)) return R2_PC_READ_LIMIT;
    if (!r2_pc_key_v1(c->file + off, dot, NULL, &key_length)) return R2_PC_FORWARDER_GRAMMAR;
    if (c->file[off + dot + 1] != '#') return R2_PC_REASON_NONE;
    if (dot + 2 == n) return R2_PC_FORWARDER_GRAMMAR;
    for (i = dot + 2; i < n; ++i) {
        unsigned char b;
        if (!r2_pc_parse_string_charge_v1(c, 1, off + i)) return R2_PC_READ_LIMIT;
        b = c->file[off + i];
        if (b < '0' || b > '9') return R2_PC_FORWARDER_GRAMMAR;
        if (value > (UINT32_MAX - (uint32_t)(b - '0')) / 10u)
            return R2_PC_TARGET_ORDINAL_OVERFLOW;
        value = value * 10u + (uint32_t)(b - '0');
    }
    return R2_PC_REASON_NONE;
}
/* Direct targets can name code, data or virtual zero-fill. Classifications
 * describe bytes/section flags only, never an executable ABI or callable VA.
 */
static int r2_pc_direct_v1(struct r2_pe_context_v1 *c,
    struct r2_pc_exports_v1 *e, struct r2_pc_function_v1 *f)
{
    uint32_t i, matches = 0;
    if (f->target_rva >= c->r->size_of_image)
        return r2_pc_export_fail_v1(e, R2_PC_REJECTED, R2_PC_TARGET_RVA, f->eat_offset);
    if (f->target_rva < c->r->size_of_headers) {
        f->target_kind = R2_PC_HEADER_BYTES; f->target_offset = f->target_rva; ++matches;
    }
    for (i = 0; i < c->r->section_count; ++i) {
        const struct r2_pe_raw_section_v1 *s = &c->r->sections[i];
        uint32_t d, code = !!(s->characteristics & 0x20000000u);
        if (!r2_pe_charge_v1(c, 1, f->target_rva)) return 0;
        if (f->target_rva < s->rva || f->target_rva - s->rva >= s->virtual_extent) continue;
        ++matches; d = f->target_rva - s->rva;
        f->section_characteristics = s->characteristics;
        if (d < s->raw_size) {
            f->target_kind = code ? R2_PC_CODE_BYTES : R2_PC_DATA_BYTES;
            f->target_offset = s->raw_offset + d;
        } else {
            f->target_kind = code ? R2_PC_CODE_ZERO_FILL : R2_PC_DATA_ZERO_FILL;
            f->target_offset = R2_PC_NONE;
        }
    }
    if (matches != 1) return r2_pc_export_fail_v1(e, R2_PC_REJECTED,
        R2_PC_TARGET_RVA, f->eat_offset);
    return 1;
}
static int r2_pc_export_body_v1(struct r2_pe_context_v1 *c, struct r2_pc_exports_v1 *e)
{
    uint32_t off, size, eat, names, ords, name_rva, i, eat_off = 0, names_off = 0, ords_off = 0;
    uint64_t value;
    e->directory_rva = c->r->directories[0].rva;
    e->directory_size = c->r->directories[0].size;
    if (!r2_pe_dir_v1(c, 0, 40, &off, &size)) return 0;
    e->directory_offset = off;
    if (!size) return 1;
    if (!r2_pe_u32_v1(c, off, &e->flags) || !r2_pe_u32_v1(c, off + 12, &name_rva) ||
        !r2_pe_u32_v1(c, off + 16, &e->ordinal_base) ||
        !r2_pe_u32_v1(c, off + 20, &e->function_declared) ||
        !r2_pe_u32_v1(c, off + 24, &e->name_declared) ||
        !r2_pe_u32_v1(c, off + 28, &eat) || !r2_pe_u32_v1(c, off + 32, &names) ||
        !r2_pe_u32_v1(c, off + 36, &ords)) return 0;
    if (e->flags) return r2_pc_export_fail_v1(e, R2_PC_PARTIAL, R2_PC_RESERVED_FLAGS, off);
    if (e->function_declared > R2_PC_FUNCTIONS)
        return r2_pc_export_fail_v1(e, R2_PC_PARTIAL, R2_PC_FUNCTION_LIMIT, off + 20);
    if (e->name_declared > R2_PC_NAMES)
        return r2_pc_export_fail_v1(e, R2_PC_PARTIAL, R2_PC_NAME_LIMIT, off + 24);
    if (e->function_declared && e->ordinal_base > UINT32_MAX - (e->function_declared - 1u))
        return r2_pc_export_fail_v1(e, R2_PC_REJECTED, R2_PC_ORDINAL_OVERFLOW, off + 16);
    if (!name_rva) return r2_pc_export_fail_v1(e, R2_PC_REJECTED, R2_PC_EXPORT_DIRECTORY, off + 12);
    if (!r2_pc_string_v1(c, e, name_rva, 0, &e->dll_name_offset, &e->dll_name_length)) return 0;
    if (e->function_declared && !eat)
        return r2_pc_export_fail_v1(e, R2_PC_REJECTED, R2_PC_EXPORT_DIRECTORY, off + 28);
    if (e->function_declared && !r2_pe_map_v1(c, eat,
        (uint64_t)e->function_declared * 4, &eat_off, NULL)) return 0;
    if (e->name_declared && (!names || !ords))
        return r2_pc_export_fail_v1(e, R2_PC_REJECTED, R2_PC_EXPORT_DIRECTORY, off + (!names ? 32u : 36u));
    if (e->name_declared && (!r2_pe_map_v1(c, names,
        (uint64_t)e->name_declared * 4, &names_off, NULL) ||
        !r2_pe_map_v1(c, ords, (uint64_t)e->name_declared * 2, &ords_off, NULL))) return 0;
    for (i = 0; i < e->function_declared; ++i) {
        struct r2_pc_function_v1 *f = &e->functions[e->function_count++];
        uint64_t end = (uint64_t)e->directory_rva + e->directory_size;
        f->eat_index = i; f->ordinal = e->ordinal_base + i; f->eat_offset = eat_off + i * 4;
        f->target_offset = R2_PC_NONE; f->target_kind = R2_PC_TARGET_INVALID;
        if (!r2_pe_u32_v1(c, f->eat_offset, &f->target_rva)) return 0;
        if (!f->target_rva) { f->target_kind = R2_PC_HOLE; continue; }
        if (f->target_rva >= e->directory_rva && f->target_rva < end) {
            f->target_kind = R2_PC_FORWARDER;
            if (!r2_pc_string_v1(c, e, f->target_rva, 1, &f->forward_offset, &f->forward_length)) return 0;
            f->forward_reason = r2_pc_forward_grammar_v1(c, f->forward_offset, f->forward_length);
            if (f->forward_reason == R2_PC_READ_LIMIT) return 0;
        } else if (!r2_pc_direct_v1(c, e, f)) return 0;
    }
    for (i = 0; i < e->name_declared; ++i) {
        struct r2_pc_name_v1 *n = &e->names[e->name_count++];
        uint32_t rva, j, smaller = 0;
        n->table_offset = names_off + i * 4;
        if (!r2_pe_u32_v1(c, n->table_offset, &rva) ||
            !r2_pe_read_v1(c, ords_off + i * 2, 2, &value)) return 0;
        n->eat_index = (uint32_t)value;
        if (n->eat_index >= e->function_declared)
            return r2_pc_export_fail_v1(e, R2_PC_REJECTED, R2_PC_EXPORT_NAME_ORDINAL, ords_off + i * 2);
        if (!r2_pc_string_v1(c, e, rva, 0, &n->offset, &n->length)) return 0;
        if (!i) continue;
        for (j = 0; j < n->length && j < e->names[i - 1].length; ++j) {
            unsigned char a, b;
            if (!r2_pc_parse_string_charge_v1(c, 2, n->offset + j)) return 0;
            a = c->file[e->names[i - 1].offset + j]; b = c->file[n->offset + j];
            if (a < b) { smaller = 1; break; }
            if (a > b) break;
        }
        if (!smaller && j == e->names[i - 1].length && j < n->length) smaller = 1;
        if (!smaller) return r2_pc_export_fail_v1(e, R2_PC_REJECTED,
            R2_PC_EXPORT_NAME_ORDER, n->table_offset);
    }
    return 1;
}
/* The original parser is called on original caller bytes, never a caller's
 * asserted status. Its work ceiling is reserved BEFORE each parse+export pass.
 * Internal read_work counts actual charged byte/mapping work; fixed memset
 * and bounded metadata validation are separately finite, not native budgets.
 */
static void r2_pc_parse_one_v1(const unsigned char *file, size_t bytes,
    struct r2_pe_raw_report_v1 *raw, struct r2_pc_exports_v1 *e)
{
    struct r2_pe_context_v1 c;
    uint32_t base;
    r2_pc_export_init_v1(e);
    base = route2_pe_preload_parse_raw_v1(file, bytes, R2_PE_RAW_ABI, raw, sizeof(*raw));
    e->base_status = base; e->base_reason = raw->reason;
    e->tls_condition = raw->tls.present != 0;
    if (!raw->structural_complete) {
        e->status = base == R2_PE_RAW_REJECTED ? R2_PC_REJECTED : R2_PC_PARTIAL;
        e->reason = R2_PC_BASE_PARSE; e->failure_offset = raw->failure_offset;
        e->work_units = raw->work_units; return;
    }
    /* Preserve base facts on e; reset only private helper's sticky reason. */
    raw->reason = R2_PE_REASON_NONE; raw->failure_offset = 0;
    c.file = file; c.length = bytes; c.r = raw;
    if (r2_pc_export_body_v1(&c, e)) {
        e->status = R2_PC_COMPLETE; e->structural_complete = 1;
    } else if (!e->reason) {
        e->status = raw->raw_status == R2_PE_RAW_INCOMPLETE ? R2_PC_PARTIAL : R2_PC_REJECTED;
        e->reason = raw->reason == R2_PE_REASON_WORK_LIMIT ||
            raw->reason == R2_PE_REASON_NAME_BYTES_LIMIT ? R2_PC_READ_LIMIT : R2_PC_EXPORT_DIRECTORY;
        e->failure_offset = raw->failure_offset;
    }
    e->work_units = raw->work_units; e->raw_reason = raw->reason;
    /* Restore base reason/status/failure; export faults live independently. */
    raw->raw_status = base; raw->reason = e->base_reason;
    raw->failure_offset = e->base_reason == R2_PE_REASON_APPLICATION_TLS_PRESENT ? raw->tls.directory_offset : 0;
}
uint32_t route2_pc_describe_v1(struct r2_pc_abi_v1 *out, size_t size)
{
    if (size != sizeof(*out) || !r2_pc_range_v1(out, size, 8)) return R2_PC_BAD_ARGUMENT;
    memset(out, 0, sizeof(*out));
    out->abi = R2_PC_ABI; out->size = sizeof(*out); out->pointer_bytes = 8; out->alignment = 8;
    out->input_bytes = sizeof(struct r2_pc_input_v1); out->image_bytes = sizeof(struct r2_pc_image_v1);
    out->workspace_bytes = sizeof(struct r2_pc_workspace_v1); out->exports_bytes = sizeof(struct r2_pc_exports_v1);
    out->report_bytes = sizeof(struct r2_pc_report_v1); out->edge_bytes = sizeof(struct r2_pc_edge_v1);
    out->hop_bytes = sizeof(struct r2_pc_hop_v1); out->image_report_bytes = sizeof(struct r2_pc_image_report_v1);
    out->images = R2_PC_IMAGES; out->functions = R2_PC_FUNCTIONS; out->names = R2_PC_NAMES;
    out->edges = R2_PC_EDGES; out->depth = R2_PC_DEPTH; out->name_bytes = R2_PC_NAME_BYTES;
    out->key_bytes = R2_PC_KEY_BYTES; out->name_read_bytes = R2_PC_NAME_READ_BYTES;
    out->file_bytes = R2_PC_FILE_BYTES; out->total_bytes = R2_PC_TOTAL_BYTES;
    out->read_work = R2_PC_READ_WORK; out->lookup_work = R2_PC_LOOKUP_WORK;
    return R2_PC_COMPLETE;
}
uint32_t route2_pc_parse_exports_v1(const unsigned char *file, size_t bytes, uint32_t abi,
    struct r2_pc_exports_v1 *out, size_t out_size, struct r2_pc_workspace_v1 *workspace, size_t workspace_size)
{
    struct r2_pc_storage_v1 *s;
    if (abi != R2_PC_ABI || out_size != sizeof(*out) || workspace_size != sizeof(*workspace) ||
        !r2_pc_range_v1(file, bytes, 1) || !r2_pc_range_v1(out, out_size, 8) ||
        !r2_pc_range_v1(workspace, workspace_size, 8)) return R2_PC_BAD_ARGUMENT;
    if (bytes > R2_PC_FILE_BYTES) return R2_PC_FILE_LIMIT;
    if (r2_pc_overlap_v1(file, bytes, out, out_size) ||
        r2_pc_overlap_v1(file, bytes, workspace, workspace_size) ||
        r2_pc_overlap_v1(out, out_size, workspace, workspace_size)) return R2_PC_ALIAS;
    memset(workspace, 0, workspace_size);
    s = &workspace->storage;
    r2_pc_parse_one_v1(file, bytes, &s->images[0].raw, out);
    return out->status;
}

static uint32_t r2_pc_validate_v1(const struct r2_pc_input_v1 *in, size_t in_size,
    struct r2_pc_report_v1 *out, size_t out_size, struct r2_pc_workspace_v1 *ws, size_t ws_size,
    uint64_t *charged_validation)
{
    uint32_t i, j, k, ni, nj;
    uint64_t total = 0;
    *charged_validation = 0;
    if (in_size != sizeof(*in) || out_size != sizeof(*out) || ws_size != sizeof(*ws) ||
        !r2_pc_range_v1(in, in_size, 8) || !r2_pc_range_v1(out, out_size, 8) ||
        !r2_pc_range_v1(ws, ws_size, 8)) return R2_PC_BAD_ARGUMENT;
    if (r2_pc_overlap_v1(in, in_size, out, out_size) ||
        r2_pc_overlap_v1(in, in_size, ws, ws_size) ||
        r2_pc_overlap_v1(out, out_size, ws, ws_size)) return R2_PC_ALIAS;
    /* Local reservation precedes EVERY metadata read and also covers later
     * cache-key normalization. At most16 current +120 prior key scans,
     * 120*128 fold comparisons, unused slots and fixed field checks.
     * Output is untouched here; successful calls carry this into lookup_work.
     */
    *charged_validation = R2_PC_VALIDATION_WORK;
    if (in->abi != R2_PC_ABI || in->size != sizeof(*in) || in->flags) return R2_PC_BAD_ARGUMENT;
    if (!in->image_count || in->image_count > R2_PC_IMAGES) return R2_PC_IMAGE_LIMIT;
    /* Validation is finite: <=16 current +120 prior key scans (128 bytes
     * each), <=120*128 fold comparisons and <=120 range pairs, plus
     * fixed fields/unused slots, BEFORE clearing outputs.
     */
    for (i = 0; i < R2_PC_IMAGES; ++i) {
        const struct r2_pc_image_v1 *im = &in->images[i];
        if (i >= in->image_count) {
            if (im->file || im->file_bytes || im->key_length || im->reserved) return R2_PC_BAD_ARGUMENT;
            for (k = 0; k < R2_PC_KEY_BYTES; ++k) if (im->key[k]) return R2_PC_BAD_ARGUMENT;
            continue;
        }
        if (im->reserved || !r2_pc_range_v1(im->file, im->file_bytes, 1)) return R2_PC_BAD_ARGUMENT;
        if (im->file_bytes > R2_PC_FILE_BYTES) return R2_PC_FILE_LIMIT;
        if (im->file_bytes > R2_PC_TOTAL_BYTES - total) return R2_PC_TOTAL_LIMIT;
        total += im->file_bytes;
        if (r2_pc_overlap_v1(im->file, im->file_bytes, in, in_size) ||
            r2_pc_overlap_v1(im->file, im->file_bytes, out, out_size) ||
            r2_pc_overlap_v1(im->file, im->file_bytes, ws, ws_size)) return R2_PC_ALIAS;
        if (!r2_pc_key_v1(im->key, im->key_length, NULL, &ni)) return R2_PC_BAD_KEY;
        for (j = 0; j < i; ++j) {
            const struct r2_pc_image_v1 *prior = &in->images[j];
            if (r2_pc_overlap_v1(im->file, im->file_bytes, prior->file, prior->file_bytes)) return R2_PC_ALIAS;
            if (!r2_pc_key_v1(prior->key, prior->key_length, NULL, &nj)) return R2_PC_BAD_KEY;
            if (ni != nj) continue;
            for (k = 0; k < ni; ++k)
                if (r2_pc_fold_v1(im->key[k]) != r2_pc_fold_v1(prior->key[k])) break;
            if (k == ni) return R2_PC_DUPLICATE_KEY;
        }
    }
    return R2_PC_COMPLETE;
}
static void r2_pc_first_v1(struct r2_pc_report_v1 *r, uint32_t reason,
    uint32_t image, uint32_t edge, uint64_t offset)
{
    r->status = R2_PC_PARTIAL;
    if (!r->reason) {
        r->reason = reason; r->first_failure_image = image;
        r->first_failure_edge = edge; r->failure_offset = offset;
    }
}
static int r2_pc_lookup_charge_v1(struct r2_pc_report_v1 *r, uint64_t n)
{
    if (r->lookup_work > R2_PC_LOOKUP_WORK || n > R2_PC_LOOKUP_WORK - r->lookup_work) return 0;
    r->lookup_work += n; return 1;
}
/* Binding shares each actual source image's retained cumulative counter.
 * It does not overwrite base/export parsing status or accept caller reports.
 * A failed reservation records its exact source and never reads that byte.
 */
static int r2_pc_bind_string_charge_v1(struct r2_pc_storage_v1 *s,
    struct r2_pc_edge_v1 *edge, uint32_t image, uint64_t n, uint32_t offset)
{
    struct r2_pe_raw_report_v1 *raw = &s->images[image].raw;
    if (raw->names_inspected_bytes > R2_PC_NAME_READ_BYTES ||
        n > R2_PC_NAME_READ_BYTES - raw->names_inspected_bytes) {
        edge->failure_image = image; edge->failure_offset = offset; return 0;
    }
    raw->names_inspected_bytes += (uint32_t)n;
    return 1;
}
/* Only normalized caller-key metadata is compared here. Original FILE module
 * strings are separately reserved before key normalization in provider().
 */
static int r2_pc_compare_v1(struct r2_pc_report_v1 *r, const unsigned char *a,
    uint32_t an, const unsigned char *b, uint32_t bn, int *comparison)
{
    uint32_t i, n = an < bn ? an : bn;
    for (i = 0; i < n; ++i) {
        if (!r2_pc_lookup_charge_v1(r, 2)) return 0;
        if (a[i] != b[i]) { *comparison = a[i] < b[i] ? -1 : 1; return 1; }
    }
    *comparison = an == bn ? 0 : (an < bn ? -1 : 1); return 1;
}
/* BOTH FILE operands reserve each byte before either byte is read. If B
 * refuses, A's reservation is retained even though neither byte was read.
 * This conservative no-refund rule also works when both images are equal.
 */
static uint32_t r2_pc_compare_file_v1(const struct r2_pc_input_v1 *in,
    struct r2_pc_storage_v1 *s, struct r2_pc_report_v1 *r, struct r2_pc_edge_v1 *edge,
    uint32_t ai, uint32_t ao, uint32_t an, uint32_t bi, uint32_t bo, uint32_t bn, int *comparison)
{
    uint32_t i, n = an < bn ? an : bn;
    for (i = 0; i < n; ++i) {
        unsigned char a, b;
        if (!r2_pc_lookup_charge_v1(r, 2)) return R2_PC_LOOKUP_LIMIT;
        if (!r2_pc_bind_string_charge_v1(s, edge, ai, 1, ao + i) ||
            !r2_pc_bind_string_charge_v1(s, edge, bi, 1, bo + i)) return R2_PC_STRING_LIMIT;
        a = in->images[ai].file[ao + i]; b = in->images[bi].file[bo + i];
        if (a != b) { *comparison = a < b ? -1 : 1; return R2_PC_REASON_NONE; }
    }
    *comparison = an == bn ? 0 : (an < bn ? -1 : 1); return R2_PC_REASON_NONE;
}
static uint32_t r2_pc_provider_v1(const struct r2_pc_input_v1 *in,
    struct r2_pc_storage_v1 *s, struct r2_pc_report_v1 *r, struct r2_pc_edge_v1 *edge,
    uint32_t source, uint32_t offset, uint32_t n, uint32_t *provider)
{
    unsigned char key[R2_PC_KEY_BYTES];
    uint32_t i, length;
    uint64_t reservation = (uint64_t)n * 4u + 16u;
    int cmp;
    *provider = R2_PC_NONE;
    if (!r2_pc_lookup_charge_v1(r, reservation)) return R2_PC_LOOKUP_LIMIT;
    if (!r2_pc_bind_string_charge_v1(s, edge, source, reservation, offset)) return R2_PC_STRING_LIMIT;
    if (!r2_pc_key_v1(in->images[source].file + offset, n, key, &length)) return R2_PC_MODULE_KEY;
    if (r2_pc_apiset_v1(key, length)) return R2_PC_API_SET;
    for (i = 0; i < in->image_count; ++i) {
        if (!r2_pc_lookup_charge_v1(r, 1) || !r2_pc_compare_v1(r,
            key, length, s->images[i].key, s->images[i].key_length, &cmp)) return R2_PC_LOOKUP_LIMIT;
        if (!cmp) {
            *provider = i;
            if (!s->images[i].exports.structural_complete) return R2_PC_PROVIDER_INVALID;
            return R2_PC_REASON_NONE;
        }
    }
    return R2_PC_PROVIDER_MISSING;
}
static uint32_t r2_pc_find_export_v1(const struct r2_pc_input_v1 *in,
    struct r2_pc_storage_v1 *s, struct r2_pc_report_v1 *r, struct r2_pc_edge_v1 *edge, uint32_t image,
    uint32_t kind, uint32_t ordinal, uint32_t name_image, uint32_t name_offset, uint32_t n, uint32_t *index)
{
    const struct r2_pc_exports_v1 *e = &s->images[image].exports;
    uint32_t lo = 0, hi = e->name_count;
    int cmp;
    *index = R2_PC_NONE;
    if (!r2_pc_lookup_charge_v1(r, 1)) return R2_PC_LOOKUP_LIMIT;
    if (kind == R2_PE_SYMBOL_ORDINAL) {
        if (ordinal < e->ordinal_base || ordinal - e->ordinal_base >= e->function_count)
            return R2_PC_EXPORT_MISSING;
        *index = ordinal - e->ordinal_base; return R2_PC_REASON_NONE;
    }
    if (kind != R2_PE_SYMBOL_NAME || !n || n >= R2_PC_NAME_BYTES) return R2_PC_IMPORT_PARTIAL;
    while (lo < hi) {
        uint32_t mid = lo + (hi - lo) / 2, reason;
        const struct r2_pc_name_v1 *en = &e->names[mid];
        if (!r2_pc_lookup_charge_v1(r, 1)) return R2_PC_LOOKUP_LIMIT;
        reason = r2_pc_compare_file_v1(in, s, r, edge, name_image, name_offset, n,
            image, en->offset, en->length, &cmp);
        if (reason) return reason;
        if (!cmp) { *index = en->eat_index; return R2_PC_REASON_NONE; }
        if (cmp < 0) hi = mid; else lo = mid + 1;
    }
    return R2_PC_EXPORT_MISSING;
}
/* Iterative chain only. Module-import cycles have no global visited bit;
 * ONLY a repeated (image,EAT) within this ONE symbol's chain is a cycle.
 */
static void r2_pc_bind_edge_v1(const struct r2_pc_input_v1 *in,
    struct r2_pc_storage_v1 *s, struct r2_pc_report_v1 *r, struct r2_pc_edge_v1 *edge,
    const struct r2_pe_raw_descriptor_v1 *descriptor, const struct r2_pe_raw_symbol_v1 *symbol)
{
    uint32_t module_image = edge->importer, module_offset = descriptor->dll_name.file_offset;
    uint32_t name_image = edge->importer, name_offset = symbol->name_offset;
    uint32_t module_length = descriptor->dll_name.length, name_length = symbol->name_length;
    uint32_t kind = symbol->kind, ordinal = symbol->ordinal, provider, index, reason, i;
    edge->status = R2_PC_PARTIAL; edge->provider = edge->eat_index = R2_PC_NONE;
    if (!(descriptor->valid_fields & 2u) || !kind) { edge->reason = R2_PC_IMPORT_PARTIAL; return; }
    if (kind == R2_PE_SYMBOL_NAME) {
        if (!name_length || name_length >= R2_PC_NAME_BYTES) { edge->reason = R2_PC_IMPORT_PARTIAL; return; }
        for (i = 0; i < name_length; ++i) {
            if (!r2_pc_lookup_charge_v1(r, 1)) { edge->reason = R2_PC_LOOKUP_LIMIT; return; }
            if (!r2_pc_bind_string_charge_v1(s, edge, name_image, 1, name_offset + i)) {
                edge->reason = R2_PC_STRING_LIMIT; return;
            }
            if (in->images[name_image].file[name_offset + i] > 0x7Fu) {
                edge->reason = R2_PC_NONASCII; edge->failure_offset = name_offset + i; return;
            }
        }
    }
    for (;;) {
        const struct r2_pc_function_v1 *f;
        struct r2_pc_hop_v1 *hop;
        reason = r2_pc_provider_v1(in, s, r, edge, module_image, module_offset, module_length, &provider);
        edge->provider = provider; edge->eat_index = R2_PC_NONE;
        if (reason) { edge->reason = reason; return; }
        reason = r2_pc_find_export_v1(in, s, r, edge, provider, kind, ordinal,
            name_image, name_offset, name_length, &index);
        edge->eat_index = index;
        if (reason) { edge->reason = reason; return; }
        f = &s->images[provider].exports.functions[index];
        edge->failure_image = provider; edge->failure_offset = f->eat_offset;
        for (i = 0; i < edge->chain_count; ++i) {
            if (!r2_pc_lookup_charge_v1(r, 1)) { edge->reason = R2_PC_LOOKUP_LIMIT; return; }
            if (edge->chain[i].image == provider && edge->chain[i].eat_index == index) {
                edge->reason = R2_PC_FORWARDER_CYCLE; return;
            }
        }
        if (edge->chain_count == R2_PC_DEPTH) { edge->reason = R2_PC_DEPTH_LIMIT; return; }
        if (!r2_pc_lookup_charge_v1(r, 1)) { edge->reason = R2_PC_LOOKUP_LIMIT; return; }
        hop = &edge->chain[edge->chain_count++];
        hop->image = provider; hop->eat_index = index; hop->ordinal = f->ordinal; hop->eat_offset = f->eat_offset;
        hop->target_rva = f->target_rva; hop->target_kind = f->target_kind; hop->target_offset = f->target_offset;
        hop->forward_offset = f->forward_offset; hop->forward_length = f->forward_length;
        hop->section_characteristics = f->section_characteristics;
        if (f->target_kind == R2_PC_HOLE) { edge->reason = R2_PC_EXPORT_HOLE; return; }
        if (f->target_kind >= R2_PC_HEADER_BYTES && f->target_kind <= R2_PC_DATA_ZERO_FILL) {
            edge->status = R2_PC_COMPLETE; edge->reason = R2_PC_REASON_NONE;
            edge->failure_image = R2_PC_NONE; edge->failure_offset = 0; return;
        }
        if (f->target_kind != R2_PC_FORWARDER) { edge->reason = R2_PC_TARGET_RVA; return; }
        if (f->forward_reason) { edge->reason = f->forward_reason; edge->failure_offset = f->forward_offset; return; }
        module_image = provider; module_offset = f->forward_offset; module_length = 0;
        /* Track every forwarded substring by its ORIGINAL source image.
         * No pointer is silently reassigned to the next provider's budget.
         */
        for (i = 0; i < f->forward_length; ++i) {
            if (!r2_pc_lookup_charge_v1(r, 1)) { edge->reason = R2_PC_LOOKUP_LIMIT; return; }
            if (!r2_pc_bind_string_charge_v1(s, edge, module_image, 1, module_offset + i)) {
                edge->reason = R2_PC_STRING_LIMIT; return;
            }
            if (in->images[module_image].file[module_offset + i] == '.') { module_length = i; break; }
        }
        if (!module_length || module_length + 1 >= f->forward_length) {
            edge->reason = R2_PC_FORWARDER_GRAMMAR; return;
        }
        name_image = module_image; name_offset = module_offset + module_length + 1;
        name_length = f->forward_length - module_length - 1;
        kind = R2_PE_SYMBOL_NAME; ordinal = 0;
        if (!r2_pc_lookup_charge_v1(r, 1)) { edge->reason = R2_PC_LOOKUP_LIMIT; return; }
        if (!r2_pc_bind_string_charge_v1(s, edge, name_image, 1, name_offset)) {
            edge->reason = R2_PC_STRING_LIMIT; return;
        }
        if (in->images[name_image].file[name_offset] == '#') {
            kind = R2_PE_SYMBOL_ORDINAL;
            for (i = 1; i < name_length; ++i) {
                unsigned char b;
                if (!r2_pc_lookup_charge_v1(r, 1)) { edge->reason = R2_PC_LOOKUP_LIMIT; return; }
                if (!r2_pc_bind_string_charge_v1(s, edge, name_image, 1, name_offset + i)) {
                    edge->reason = R2_PC_STRING_LIMIT; return;
                }
                b = in->images[name_image].file[name_offset + i];
                if (b < '0' || b > '9') { edge->reason = R2_PC_FORWARDER_GRAMMAR; return; }
                if (ordinal > (UINT32_MAX - (uint32_t)(b - '0')) / 10u) {
                    edge->reason = R2_PC_TARGET_ORDINAL_OVERFLOW; return;
                }
                ordinal = ordinal * 10u + (uint32_t)(b - '0');
            }
        }
    }
}
uint32_t route2_pc_bind_catalog_v1(const struct r2_pc_input_v1 *in, size_t in_size,
    struct r2_pc_report_v1 *out, size_t out_size, struct r2_pc_workspace_v1 *workspace, size_t workspace_size)
{
    struct r2_pc_storage_v1 *s;
    uint32_t result, i, j, affected = 0;
    uint64_t validation_work;
    result = r2_pc_validate_v1(in, in_size, out, out_size, workspace, workspace_size, &validation_work);
    if (result != R2_PC_COMPLETE) return result;
    memset(workspace, 0, workspace_size); memset(out, 0, out_size);
    s = &workspace->storage;
    out->abi = R2_PC_ABI; out->size = sizeof(*out); out->status = R2_PC_COMPLETE;
    out->preload_scope = R2_PC_UNPROVEN; out->image_count = in->image_count;
    out->lookup_work = validation_work;
    out->first_failure_image = out->first_failure_edge = R2_PC_NONE;
    for (i = 0; i < in->image_count; ++i) {
        struct r2_pc_cached_v1 *im = &s->images[i];
        struct r2_pc_image_report_v1 *ir = &out->images[i];
        out->total_file_bytes += in->images[i].file_bytes;
        r2_pc_key_v1(in->images[i].key, in->images[i].key_length, im->key, &im->key_length);
        /* Reserve the full old per-image ceiling BEFORE work. A refund below
         * records actual charged reads, retaining aggregate boundedness.
         */
        if (R2_PE_RAW_WORK_LIMIT > R2_PC_READ_WORK - out->read_work) {
            ++out->failed_images; affected |= 1u << i;
            ir->export_status = R2_PC_PARTIAL; ir->export_reason = R2_PC_READ_LIMIT;
            ir->import_count_unknown = 1; ++out->unknown_import_images;
            r2_pc_first_v1(out, R2_PC_READ_LIMIT, i, R2_PC_NONE, 0); continue;
        }
        out->read_work += R2_PE_RAW_WORK_LIMIT;
        r2_pc_parse_one_v1(in->images[i].file, (size_t)in->images[i].file_bytes, &im->raw, &im->exports);
        out->read_work -= R2_PE_RAW_WORK_LIMIT - im->exports.work_units;
        ir->base_status = im->exports.base_status; ir->base_reason = im->exports.base_reason;
        ir->base_complete = im->raw.structural_complete; ir->base_failure_offset = im->raw.failure_offset;
        ir->export_status = im->exports.status; ir->export_reason = im->exports.reason;
        ir->export_raw_reason = im->exports.raw_reason;
        ir->import_count_unknown = !ir->base_complete;
        if (ir->import_count_unknown) ++out->unknown_import_images;
        ir->export_complete = im->exports.structural_complete; ir->export_failure_offset = im->exports.failure_offset;
        ir->tls_condition = im->exports.tls_condition; ir->descriptor_count = im->raw.descriptor_count;
        ir->symbol_count = im->raw.symbol_count; ir->read_work = im->exports.work_units;
        if (!ir->base_complete || !ir->export_complete) {
            ++out->failed_images; affected |= 1u << i;
            r2_pc_first_v1(out, im->exports.reason, i, R2_PC_NONE, im->exports.failure_offset);
        }
    }
    /* Every actually enumerated symbol gets a record or explicit exhaustion.
     * Incomplete raw parsers retain UNKNOWN further imports; no zero claim.
     */
    for (i = 0; i < in->image_count; ++i) {
        const struct r2_pe_raw_report_v1 *raw = &s->images[i].raw;
        struct r2_pc_image_report_v1 *ir = &out->images[i];
        ir->edge_first = out->edge_count;
        for (j = 0; j < raw->symbol_count; ++j) {
            const struct r2_pe_raw_symbol_v1 *sym = &raw->symbols[j];
            const struct r2_pe_raw_descriptor_v1 *d;
            struct r2_pc_edge_v1 *edge;
            uint32_t ei;
            if (out->edge_count == R2_PC_EDGES) {
                ir->unrepresented_symbols = raw->symbol_count - j;
                out->unrepresented_symbols += ir->unrepresented_symbols;
                affected |= 1u << i;
                r2_pc_first_v1(out, R2_PC_EDGE_LIMIT, i, R2_PC_NONE, sym->thunk_offset); break;
            }
            ei = out->edge_count++; ++ir->edge_count; edge = &out->edges[ei];
            edge->importer = i; edge->descriptor = sym->descriptor_index; edge->symbol = j;
            edge->symbol_kind = sym->kind; edge->ordinal = sym->ordinal;
            edge->name_offset = sym->name_offset; edge->name_length = sym->name_length;
            edge->thunk_offset = sym->thunk_offset; edge->provider = edge->eat_index = R2_PC_NONE;
            edge->failure_image = i; edge->failure_offset = sym->thunk_offset;
            if (sym->descriptor_index >= raw->descriptor_count) {
                edge->status = R2_PC_PARTIAL; edge->reason = R2_PC_IMPORT_PARTIAL;
            } else {
                d = &raw->descriptors[sym->descriptor_index];
                edge->import_kind = d->kind; edge->module_offset = d->dll_name.file_offset;
                edge->module_length = d->dll_name.length;
                r2_pc_bind_edge_v1(in, s, out, edge, d, sym);
            }
            if (edge->status == R2_PC_COMPLETE) ++out->bound_edges;
            else {
                ++out->unresolved_edges; affected |= 1u << i;
                if (edge->reason == R2_PC_STRING_LIMIT && edge->failure_image < in->image_count)
                    affected |= 1u << edge->failure_image;
                r2_pc_first_v1(out, edge->reason, edge->failure_image, ei, edge->failure_offset);
            }
        }
    }
    for (i = 0; i < in->image_count; ++i) if (affected & (1u << i)) ++out->affected_images;
    if (out->status == R2_PC_COMPLETE) out->complete_for_supplied_catalog = 1;
    return out->status;
}
