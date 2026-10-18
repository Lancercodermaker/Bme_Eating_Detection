/* C03 bounded original-FILE AMD64 PE32+ base relocation metadata.
 * SOURCE ONLY / UNCOMPILED / UNRUN. Build this TU INSTEAD OF the included
 * catalog/owned/core TUs: ONE textual inclusion chain, one original owner.
 * Existing .def, 17 exports, 40-byte ABI, build and loader remain separate.
 * All original native fees remain UNKNOWN_NOT_ZERO; source units grant none.
 * Format: https://learn.microsoft.com/en-us/windows/win32/debug/pe-format#the-reloc-section-image-only
 * Context7 lookup had no matching relocation passage; the primary reference
 * specifies 4KiB pages, 32-bit block starts, WORD type/offset, ABSOLUTE=0 and
 * DIR64=10. Public format documentation grants no installed/runtime support.
 */
#if !defined(R2_TARGET_WINDOWS_SEED) || defined(R2_TARGET_LINUX_START) || defined(R2_TARGET_MOUNT_LIBRARY)
#error "Base relocation component requires only the explicit Windows seed target"
#endif
#include "route2_windows_preload_catalog.c"
#include "route2_pe_base_relocations.h"

struct r2_br_workspace_v1 {
    const unsigned char *file;
    struct r2_br_report_v1 *out;
    uint64_t length, limit;
    uint32_t matches[8], kinds[8], offsets[8], owners[8], characteristics[8];
    uint32_t current_block;
    unsigned char reserved[60];
};
/* Intended native C11 layout assertions: SOURCE ONLY, never compiled here. */
_Static_assert(sizeof(uintptr_t) == 8 && sizeof(size_t) == 8, "native AMD64 only");
_Static_assert(sizeof(struct r2_br_block_v1) == 64 && _Alignof(struct r2_br_block_v1) == 8,
    "relocation block layout");
_Static_assert(sizeof(struct r2_br_word_v1) == 64 && _Alignof(struct r2_br_word_v1) == 8,
    "relocation WORD fact layout");
_Static_assert(sizeof(struct r2_br_workspace_v1) == R2_BR_WORKSPACE_BYTES &&
    _Alignof(struct r2_br_workspace_v1) == R2_BR_ALIGNMENT, "caller workspace layout");
_Static_assert(sizeof(struct r2_br_report_v1) == R2_BR_REPORT_BYTES &&
    _Alignof(struct r2_br_report_v1) == R2_BR_ALIGNMENT &&
    offsetof(struct r2_br_report_v1, base) == 176 &&
    offsetof(struct r2_br_report_v1, blocks) == 210160 &&
    offsetof(struct r2_br_report_v1, words) == 472304, "independent report layout");
_Static_assert(R2_BR_FILE_LIMIT == R2_PE_RAW_FILE_LIMIT &&
    R2_PE_RAW_REPORT_BYTES == 209984 && R2_PE_RAW_WORK_LIMIT == 8388608 &&
    R2_BR_INITIAL_WORK == UINT64_C(11169328) && R2_BR_INITIAL_WORK < R2_BR_WORK_LIMIT,
    "prepaid original raw clear and entire work ceiling plus new storage");

static int r2_br_range_v1(const void *p, uint64_t n, uint32_t alignment)
{
    uintptr_t a = (uintptr_t)p;
    return p && !(a % alignment) && n <= UINTPTR_MAX - a;
}
static int r2_br_overlap_v1(const void *a, uint64_t an, const void *b, uint64_t bn)
{
    uintptr_t x = (uintptr_t)a, y = (uintptr_t)b;
    return an && bn && x < y + bn && y < x + an;
}
/* Initial reservation prepays bounded first-failure bookkeeping, including
 * the current block status, so an exhausted charge never needs a refund or
 * an unaccounted file read to preserve the diagnostic.
 */
static int r2_br_fail_v1(struct r2_br_workspace_v1 *c, uint32_t status,
    uint32_t reason, uint64_t off)
{
    struct r2_br_report_v1 *r = c->out;
    if (!r->reason) {
        r->status = status; r->reason = reason; r->failure_offset = off;
        r->word_semantics_unknown_known = r->word_unrepresented_known;
        if (r->word_partial) ++r->word_semantics_unknown_known;
        if (c->current_block < r->block_count) {
            r->blocks[c->current_block].status = status;
            r->blocks[c->current_block].reason = reason;
        }
    }
    return 0;
}
static int r2_br_charge_v1(struct r2_br_workspace_v1 *c, uint64_t n, uint64_t off)
{
    if (c->out->work_units > c->limit || n > c->limit - c->out->work_units)
        return r2_br_fail_v1(c, R2_BR_PARTIAL, R2_BR_WORK_CAP, off);
    c->out->work_units += n;
    return 1;
}
/* Reservations include byte inspection, decoding/comparison, result mutation
 * and bounded local bookkeeping. Work units are conservative algorithmic
 * units, never a wall-time, RAM, operating-system or authority measurement.
 */
static int r2_br_read_v1(struct r2_br_workspace_v1 *c, uint64_t off,
    uint32_t n, uint64_t *v)
{
    uint32_t i; uint64_t x = 0;
    if (!r2_br_charge_v1(c, (uint64_t)n * 4u + 32u, off)) return 0;
    if (n > 8 || off > c->length || n > c->length - off)
        return r2_br_fail_v1(c, R2_BR_REJECTED, R2_BR_FILE_TRUNCATED, off);
    for (i = 0; i < n; ++i) x |= (uint64_t)c->file[(size_t)(off + i)] << (8u * i);
    *v = x;
    return 1;
}

/* Directory bytes must bind to one contiguous original FILE owner. The
 * existing base report is read-only here, including on a mapping failure.
 */
static int r2_br_directory_map_v1(struct r2_br_workspace_v1 *c,
    uint32_t rva, uint32_t n, uint32_t *kind, uint32_t *offset)
{
    const struct r2_pe_raw_report_v1 *b = &c->out->base;
    uint32_t i, matches = 0, selected = R2_BR_MAP_GAP, off = R2_BR_NONE;
    uint64_t end = (uint64_t)rva + n;
    if (!r2_br_charge_v1(c, 128u + (uint64_t)b->section_count * 32u, rva)) return 0;
    *offset = R2_BR_NONE;
    if (end > UINT32_MAX) { *kind = R2_BR_MAP_OVERFLOW; return 1; }
    if (!n || rva >= b->size_of_image || end > b->size_of_image) {
        *kind = R2_BR_MAP_OUT_OF_IMAGE; return 1;
    }
    if (rva < b->size_of_headers) {
        ++matches; off = rva;
        selected = n <= b->size_of_headers - rva ? R2_BR_MAP_FILE : R2_BR_MAP_CROSSING;
    }
    for (i = 0; i < b->section_count; ++i) {
        const struct r2_pe_raw_section_v1 *s = &b->sections[i];
        uint32_t d;
        if (rva < s->rva || (uint64_t)rva - s->rva >= s->virtual_extent) continue;
        ++matches; d = rva - s->rva;
        if (n > s->virtual_extent - d) selected = R2_BR_MAP_CROSSING;
        else if (d >= s->raw_size) selected = R2_BR_MAP_ZERO_FILL;
        else if (n > s->raw_size - d) selected = R2_BR_MAP_MIXED;
        else { selected = R2_BR_MAP_FILE; off = s->raw_offset + d; }
    }
    if (matches > 1) selected = R2_BR_MAP_AMBIGUOUS;
    if (selected == R2_BR_MAP_FILE && (off > c->length || n > c->length - off))
        return r2_br_fail_v1(c, R2_BR_REJECTED, R2_BR_FILE_TRUNCATED, off);
    *kind = selected;
    if (selected == R2_BR_MAP_FILE) *offset = off;
    return 1;
}

/* Classify all EIGHT target bytes against EVERY header/section candidate.
 * No mandatory target alignment, commitment inference, stitching or writes.
 * For the inherited valid profile ambiguity cannot occur, but defensive facts
 * remain explicit and never turn into a FILE read or a fabricated u64.
 * Return 1 means classification produced, including invalid map kinds; only
 * a finite-work/read failure returns 0. The public caller rejects bad kinds.
 */
static int r2_br_target_v1(struct r2_br_workspace_v1 *c, struct r2_br_word_v1 *w)
{
    const struct r2_pe_raw_report_v1 *b = &c->out->base;
    uint32_t j, i, flags = 0, first_owner = R2_BR_NONE, crossing = 0;
    uint32_t all_file = 1, all_zero = 1;
    uint64_t end = (uint64_t)w->target_rva + 8u, value;
    if (!r2_br_charge_v1(c, 512u + UINT64_C(256) * (b->section_count + 1u), w->file_offset)) return 0;
    w->valid_fields &= ~(R2_BR_WORD_MAPPING | R2_BR_WORD_VALUE);
    w->raw_value = 0; w->target_file_offset = R2_BR_NONE;
    w->section_characteristics = 0; w->mapping_flags = 0;
    if (end > UINT32_MAX) { w->target_kind = R2_BR_MAP_OVERFLOW; w->valid_fields |= R2_BR_WORD_MAPPING; return 1; }
    if (w->target_rva >= b->size_of_image || end > b->size_of_image) {
        w->target_kind = R2_BR_MAP_OUT_OF_IMAGE; w->valid_fields |= R2_BR_WORD_MAPPING; return 1;
    }
    for (j = 0; j < 8; ++j) {
        uint32_t at = w->target_rva + j;
        c->matches[j] = 0; c->kinds[j] = R2_BR_MAP_GAP;
        c->offsets[j] = R2_BR_NONE; c->owners[j] = R2_BR_NONE; c->characteristics[j] = 0;
        if (at < b->size_of_headers) {
            ++c->matches[j]; c->kinds[j] = R2_BR_MAP_FILE;
            c->offsets[j] = at; c->owners[j] = 0;
        }
        for (i = 0; i < b->section_count; ++i) {
            const struct r2_pe_raw_section_v1 *s = &b->sections[i];
            uint32_t d;
            if (at < s->rva || (uint64_t)at - s->rva >= s->virtual_extent) continue;
            ++c->matches[j]; d = at - s->rva;
            c->owners[j] = i + 1; c->characteristics[j] = s->characteristics;
            if (d < s->raw_size) { c->kinds[j] = R2_BR_MAP_FILE; c->offsets[j] = s->raw_offset + d; }
            else { c->kinds[j] = R2_BR_MAP_ZERO_FILL; c->offsets[j] = R2_BR_NONE; }
        }
        if (!c->matches[j]) flags |= R2_BR_MAP_HAS_GAP;
        else if (c->matches[j] > 1) flags |= R2_BR_MAP_HAS_AMBIGUITY;
        if (c->kinds[j] == R2_BR_MAP_FILE) flags |= R2_BR_MAP_HAS_FILE;
        if (c->kinds[j] == R2_BR_MAP_ZERO_FILL) flags |= R2_BR_MAP_HAS_ZERO;
        all_file &= c->matches[j] == 1 && c->kinds[j] == R2_BR_MAP_FILE;
        all_zero &= c->matches[j] == 1 && c->kinds[j] == R2_BR_MAP_ZERO_FILL;
        if (!j) first_owner = c->owners[j];
        else if (c->owners[j] != first_owner) crossing = 1;
    }
    if (crossing) flags |= R2_BR_MAP_HAS_OWNER_CROSSING;
    w->mapping_flags = flags; w->valid_fields |= R2_BR_WORD_MAPPING;
    if (flags & R2_BR_MAP_HAS_AMBIGUITY) w->target_kind = R2_BR_MAP_AMBIGUOUS;
    else if (flags & R2_BR_MAP_HAS_GAP) w->target_kind = R2_BR_MAP_GAP;
    else if (crossing) w->target_kind = R2_BR_MAP_CROSSING;
    else if (all_file) w->target_kind = R2_BR_MAP_FILE;
    else if (all_zero) w->target_kind = R2_BR_MAP_ZERO_FILL;
    else w->target_kind = R2_BR_MAP_MIXED;
    if (!crossing && !(flags & (R2_BR_MAP_HAS_GAP | R2_BR_MAP_HAS_AMBIGUITY)))
        w->section_characteristics = c->characteristics[0];
    if (w->target_kind != R2_BR_MAP_FILE) return 1;
    for (j = 1; j < 8; ++j) {
        if (c->offsets[j] != (uint64_t)c->offsets[0] + j) {
            w->target_kind = R2_BR_MAP_CROSSING; w->mapping_flags |= R2_BR_MAP_HAS_OWNER_CROSSING;
            return 1;
        }
    }
    w->target_file_offset = c->offsets[0];
    if (!r2_br_read_v1(c, w->target_file_offset, 8, &value)) return 0;
    w->raw_value = value; w->valid_fields |= R2_BR_WORD_VALUE;
    return 1;
}

static int r2_br_headers_v1(struct r2_br_workspace_v1 *c)
{
    struct r2_br_report_v1 *r = c->out;
    uint64_t pe, value;
    if (!r2_br_charge_v1(c, 128, 0)) return 0;
    if (!r2_br_read_v1(c, 0x3C, 4, &pe) || !r2_br_read_v1(c, pe + 22, 2, &value)) return 0;
    r->coff_characteristics = (uint32_t)value; r->coff_characteristics_valid = 1;
    r->relocs_stripped = !!(r->coff_characteristics & 1u);
    if (r->base.optional_directory_count > 5) {
        uint64_t at = pe + 24u + 112u + 5u * 8u;
        if (!r2_br_read_v1(c, at, 4, &value)) return 0;
        r->directory_rva = (uint32_t)value; r->directory_fields_valid = 1;
        if (!r2_br_read_v1(c, at + 4, 4, &value)) return 0;
        r->directory_size = (uint32_t)value; r->directory_fields_valid = 3;
        if (r->directory_rva != r->base.directories[5].rva ||
            r->directory_size != r->base.directories[5].size)
            return r2_br_fail_v1(c, R2_BR_REJECTED, R2_BR_HEADER_BINDING, at);
    }
    r->directory_condition = r->directory_rva || r->directory_size ?
        (r->relocs_stripped ? R2_BR_STRIPPED_PRESENT : R2_BR_PRESENT) :
        (r->relocs_stripped ? R2_BR_STRIPPED_ABSENT : R2_BR_ABSENT);
    return 1;
}

static int r2_br_walk_v1(struct r2_br_workspace_v1 *c)
{
    struct r2_br_report_v1 *r = c->out;
    uint32_t cursor = 0, directory_off, kind;
    if (!r2_br_headers_v1(c)) return 0;
    if (!r2_br_charge_v1(c, 128, r->directory_rva)) return 0;
    if (!r->directory_rva && !r->directory_size) {
        r->word_count_unknown = 0; r->block_count_unknown = 0; return 1;
    }
    r->remaining_directory_bytes = r->directory_size;
    if (!r->directory_rva || !r->directory_size)
        return r2_br_fail_v1(c, R2_BR_REJECTED, R2_BR_DIRECTORY_PAIR, r->directory_rva);
    if (!r2_br_directory_map_v1(c, r->directory_rva, r->directory_size, &kind, &directory_off)) return 0;
    r->directory_map_kind = kind;
    if (kind == R2_BR_MAP_OVERFLOW || kind == R2_BR_MAP_OUT_OF_IMAGE)
        return r2_br_fail_v1(c, R2_BR_REJECTED, R2_BR_DIRECTORY_RANGE, r->directory_rva);
    if (kind != R2_BR_MAP_FILE)
        return r2_br_fail_v1(c, R2_BR_REJECTED, R2_BR_DIRECTORY_MAPPING, r->directory_rva);
    r->directory_file_offset = directory_off;
    while (cursor < r->directory_size) {
        struct r2_br_block_v1 *block;
        uint32_t remaining = r->directory_size - cursor, j, off = directory_off + cursor;
        uint64_t value;
        if (!r2_br_charge_v1(c, 256, off)) return 0;
        if (r->block_count == R2_BR_BLOCK_LIMIT) {
            c->current_block = R2_BR_NONE; r->blocks_unrepresented_min = 1;
            return r2_br_fail_v1(c, R2_BR_PARTIAL, R2_BR_BLOCK_CAP, off);
        }
        c->current_block = r->block_count;
        block = &r->blocks[r->block_count++]; ++r->block_partial;
        block->directory_offset = cursor; block->file_offset = off;
        block->word_first = r->word_count; block->valid_fields = R2_BR_BLOCK_OFFSET;
        block->status = R2_BR_PARTIAL;
        if (!r2_br_read_v1(c, off, remaining < 8 ? remaining : 8, &value)) return 0;
        block->raw_header = value; block->raw_header_bytes = remaining < 8 ? remaining : 8;
        if (remaining >= 4) { block->page_rva = (uint32_t)value; block->valid_fields |= R2_BR_BLOCK_PAGE; }
        if (remaining < 8) return r2_br_fail_v1(c, R2_BR_REJECTED, R2_BR_BLOCK_TRUNCATED, off);
        block->block_size = (uint32_t)(value >> 32); block->valid_fields |= R2_BR_BLOCK_SIZE_FIELD;
        /* Check RVA and FILE block start independently; each following block
         * must satisfy its own alignment. A final size-ten block is allowed. */
        if (((uint64_t)r->directory_rva + cursor) % 4u || off % 4u)
            return r2_br_fail_v1(c, R2_BR_REJECTED, R2_BR_BLOCK_ALIGNMENT, off);
        if (block->block_size < 8 || block->block_size % 2u)
            return r2_br_fail_v1(c, R2_BR_REJECTED, R2_BR_BLOCK_SIZE, off + 4u);
        if (block->block_size > remaining)
            return r2_br_fail_v1(c, R2_BR_REJECTED, R2_BR_BLOCK_RANGE, off + 4u);
        if (block->page_rva % 4096u)
            return r2_br_fail_v1(c, R2_BR_REJECTED, R2_BR_PAGE_ALIGNMENT, off);
        if (block->page_rva >= r->base.size_of_image)
            return r2_br_fail_v1(c, R2_BR_REJECTED, R2_BR_PAGE_RANGE, off);
        block->word_declared = (block->block_size - 8u) / 2u;
        block->valid_fields |= R2_BR_BLOCK_LAYOUT;
        r->word_declared_known += block->word_declared;
        r->word_unrepresented_known += block->word_declared;
        for (j = 0; j < block->word_declared; ++j) {
            struct r2_br_word_v1 *w;
            uint32_t word_off = off + 8u + j * 2u;
            uint64_t target;
            if (!r2_br_charge_v1(c, 128, word_off)) return 0;
            if (r->word_count == R2_BR_WORD_LIMIT)
                return r2_br_fail_v1(c, R2_BR_PARTIAL, R2_BR_WORD_CAP, word_off);
            w = &r->words[r->word_count++]; ++r->word_partial;
            ++block->word_retained; --r->word_unrepresented_known;
            w->block_index = c->current_block; w->word_index = j;
            w->file_offset = word_off; w->target_file_offset = R2_BR_NONE;
            if (!r2_br_read_v1(c, word_off, 2, &value)) return 0;
            w->raw_word = (uint32_t)value; w->type = w->raw_word >> 12;
            w->offset12 = w->raw_word & 0xFFFu; w->valid_fields = R2_BR_WORD_RAW;
            if (!w->type) {
                w->state = R2_BR_WORD_SKIPPED; ++r->absolute_count;
            } else if (w->type == 10) {
                w->state = R2_BR_WORD_DIR64; ++r->dir64_count; w->target_extent = 8;
                target = (uint64_t)block->page_rva + w->offset12;
                if (target > UINT32_MAX) {
                    w->state = R2_BR_WORD_INVALID; w->target_kind = R2_BR_MAP_OVERFLOW;
                    w->valid_fields |= R2_BR_WORD_MAPPING;
                    return r2_br_fail_v1(c, R2_BR_REJECTED, R2_BR_TARGET_OVERFLOW, word_off);
                }
                w->target_rva = (uint32_t)target; w->valid_fields |= R2_BR_WORD_TARGET;
                if (!r2_br_target_v1(c, w)) return 0;
                if (w->target_kind == R2_BR_MAP_OVERFLOW || w->target_kind == R2_BR_MAP_OUT_OF_IMAGE) {
                    w->state = R2_BR_WORD_INVALID;
                    return r2_br_fail_v1(c, R2_BR_REJECTED,
                        w->target_kind == R2_BR_MAP_OVERFLOW ? R2_BR_TARGET_OVERFLOW : R2_BR_TARGET_RANGE, word_off);
                }
                if (w->target_kind != R2_BR_MAP_FILE && w->target_kind != R2_BR_MAP_ZERO_FILL &&
                    w->target_kind != R2_BR_MAP_MIXED) {
                    w->state = R2_BR_WORD_INVALID;
                    return r2_br_fail_v1(c, R2_BR_REJECTED, R2_BR_TARGET_MAPPING, word_off);
                }
            } else {
                w->state = R2_BR_WORD_UNSUPPORTED; ++r->unsupported_count;
                /* Do not consume/decode the next WORD: HIGHADJ may own it. */
                return r2_br_fail_v1(c, R2_BR_PARTIAL, R2_BR_UNSUPPORTED_TYPE, word_off);
            }
            w->valid_fields |= R2_BR_WORD_DONE; ++r->word_complete; --r->word_partial;
            ++block->word_complete;
        }
        if (!r2_br_charge_v1(c, 64, off)) return 0;
        block->valid_fields |= R2_BR_BLOCK_DONE; block->status = R2_BR_COMPLETE;
        ++r->block_complete; --r->block_partial;
        cursor += block->block_size;
        r->directory_bytes_consumed = cursor; r->remaining_directory_bytes = r->directory_size - cursor;
        c->current_block = R2_BR_NONE;
    }
    if (!r2_br_charge_v1(c, 32, directory_off + cursor)) return 0;
    r->word_count_unknown = 0; r->block_count_unknown = 0;
    return 1;
}

uint32_t route2_pe_base_relocations_parse_v1(const unsigned char *file, size_t file_size,
    uint32_t abi, uint64_t work_limit, struct r2_br_report_v1 *out, size_t out_size,
    struct r2_br_workspace_v1 *workspace, size_t workspace_size)
{
    unsigned char *clear; size_t i; uint32_t status;
    /* Local prepayment precedes even the bounded argument comparisons. Bad
     * arguments publish no ledger and touch no caller storage. One fixed-clear
     * unit covers one initialized byte and its loop bookkeeping; later scans
     * reserve additional conservative comparison/mutation units explicitly. */
    uint64_t reserved_work = R2_BR_INITIAL_WORK;
    /* No input FILE read, output/workspace clear or caller report evidence
     * before exact native argument/range/alias validation. Initial reservation
     * covers these finite integer checks and fixed initialization if accepted.
     */
    if (abi != R2_BR_ABI || out_size != R2_BR_REPORT_BYTES ||
        workspace_size != R2_BR_WORKSPACE_BYTES ||
        work_limit < R2_BR_INITIAL_WORK || work_limit > R2_BR_WORK_LIMIT ||
        !r2_br_range_v1(file, file_size, 1) ||
        !r2_br_range_v1(out, out_size, _Alignof(struct r2_br_report_v1)) ||
        !r2_br_range_v1(workspace, workspace_size, _Alignof(struct r2_br_workspace_v1)))
        return R2_BR_BAD_ARGUMENT;
    if (r2_br_overlap_v1(file, file_size, out, out_size) ||
        r2_br_overlap_v1(file, file_size, workspace, workspace_size) ||
        r2_br_overlap_v1(out, out_size, workspace, workspace_size)) return R2_BR_BAD_ARGUMENT;
    if (file_size > R2_BR_FILE_LIMIT) return R2_BR_FILE_TOO_LARGE;
    /* The local prepayment is validated BEFORE either fixed clear; publish
     * that consumed reservation in the cleared report afterwards. No refund. */
    clear = (unsigned char *)out;
    for (i = 0; i < out_size; ++i) clear[i] = 0;
    clear = (unsigned char *)workspace;
    for (i = 0; i < workspace_size; ++i) clear[i] = 0;
    out->abi = R2_BR_ABI; out->size = R2_BR_REPORT_BYTES; out->status = R2_BR_PARTIAL;
    out->preload_scope = R2_PE_PRELOAD_CLOSURE_UNPROVEN;
    out->work_units = reserved_work; out->work_limit = work_limit;
    out->base_work_reserved = R2_PE_RAW_WORK_LIMIT;
    out->directory_file_offset = R2_BR_NONE;
    out->word_count_unknown = 1; out->block_count_unknown = 1;
    workspace->file = file; workspace->out = out;
    workspace->length = file_size; workspace->limit = work_limit; workspace->current_block = R2_BR_NONE;
    /* ALWAYS reparse original FILE bytes. Never accept a supplied status or
     * report as base evidence. Its full work ceiling and fixed clear were
     * reserved separately; its returned facts are not subsequently mutated.
     */
    status = route2_pe_preload_parse_raw_v1(file, file_size, R2_PE_RAW_ABI,
        &out->base, sizeof(out->base));
    out->base_status = status; out->base_reason = out->base.reason;
    if (status != R2_PE_RAW_COMPLETE && status != R2_PE_RAW_APPLICATION_TLS_PRESENT) {
        r2_br_fail_v1(workspace, status == R2_PE_RAW_REJECTED ? R2_BR_REJECTED : R2_BR_PARTIAL,
            R2_BR_BASE_PARSE, out->base.failure_offset);
        return out->status;
    }
    out->base_accepted = status == R2_PE_RAW_COMPLETE;
    if (!r2_br_walk_v1(workspace)) return out->status;
    /* Final bookkeeping is prepaid by INITIAL_WORK, including the failure
     * path for application-sensitive TLS. Metadata completion cannot promote
     * the underlying application/base condition to final local COMPLETE.
     */
    out->metadata_complete = 1;
    if (status == R2_PE_RAW_APPLICATION_TLS_PRESENT) {
        r2_br_fail_v1(workspace, R2_BR_PARTIAL, R2_BR_BASE_APPLICATION, out->base.failure_offset);
        return out->status;
    }
    out->status = R2_BR_COMPLETE;
    return out->status;
}
