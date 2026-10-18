#ifndef ROUTE2_PE_BASE_RELOCATIONS_H
#define ROUTE2_PE_BASE_RELOCATIONS_H
/* SOURCE ONLY / UNCOMPILED / UNRUN. Independent native AMD64 C11 layout;
 * no installed ABI/export/loader promise. Original stable FILE buffer only.
 * This header depends on the existing raw PE fact definitions. The production
 * TU includes route2_windows_preload_catalog.c ONCE before this header.
 */
#if !defined(R2_TARGET_WINDOWS_SEED) || defined(R2_TARGET_LINUX_START) || defined(R2_TARGET_MOUNT_LIBRARY)
#error "Base relocation component requires only R2_TARGET_WINDOWS_SEED"
#endif
#include "route2_mount_helper.h"

#define R2_BR_ABI 1u
#define R2_BR_ALIGNMENT 8u
#define R2_BR_FILE_LIMIT 67108864u
#define R2_BR_BLOCK_LIMIT 4096u
#define R2_BR_WORD_LIMIT 32768u
#define R2_BR_WORKSPACE_BYTES 256u
#define R2_BR_REPORT_BYTES 2569456u
#define R2_BR_WORK_LIMIT UINT64_C(33554432)
/* The reused parser excludes its fixed output clear from its work counter.
 * Reserve BOTH that 209984-byte clear AND its entire 8Mi work ceiling, with
 * no refund for unused work. New fixed clears and 1024 units for bounded
 * validation/initialization/failure bookkeeping are separately prepaid.
 */
#define R2_BR_INITIAL_WORK (UINT64_C(1024) + R2_BR_REPORT_BYTES + \
    R2_BR_WORKSPACE_BYTES + R2_PE_RAW_REPORT_BYTES + R2_PE_RAW_WORK_LIMIT)
#define R2_BR_NONE UINT32_MAX

enum r2_br_status_v1 {
    R2_BR_COMPLETE = 0xC341u, R2_BR_PARTIAL, R2_BR_REJECTED,
    R2_BR_BAD_ARGUMENT, R2_BR_FILE_TOO_LARGE
};
enum r2_br_reason_v1 {
    R2_BR_REASON_NONE = 0, R2_BR_BASE_PARSE, R2_BR_BASE_APPLICATION,
    R2_BR_HEADER_BINDING, R2_BR_DIRECTORY_PAIR, R2_BR_DIRECTORY_RANGE,
    R2_BR_DIRECTORY_MAPPING, R2_BR_BLOCK_TRUNCATED, R2_BR_BLOCK_ALIGNMENT,
    R2_BR_BLOCK_SIZE, R2_BR_BLOCK_RANGE, R2_BR_PAGE_ALIGNMENT, R2_BR_PAGE_RANGE,
    R2_BR_UNSUPPORTED_TYPE, R2_BR_TARGET_OVERFLOW, R2_BR_TARGET_RANGE,
    R2_BR_TARGET_MAPPING, R2_BR_BLOCK_CAP, R2_BR_WORD_CAP, R2_BR_WORK_CAP,
    R2_BR_FILE_TRUNCATED
};
enum r2_br_directory_condition_v1 {
    R2_BR_DIRECTORY_UNKNOWN = 0, R2_BR_ABSENT, R2_BR_PRESENT,
    R2_BR_STRIPPED_ABSENT, R2_BR_STRIPPED_PRESENT
};
enum r2_br_mapping_v1 {
    R2_BR_MAP_UNKNOWN = 0, R2_BR_MAP_FILE, R2_BR_MAP_ZERO_FILL,
    R2_BR_MAP_MIXED, R2_BR_MAP_GAP, R2_BR_MAP_AMBIGUOUS,
    R2_BR_MAP_CROSSING, R2_BR_MAP_OUT_OF_IMAGE, R2_BR_MAP_OVERFLOW
};
#define R2_BR_MAP_HAS_FILE 1u
#define R2_BR_MAP_HAS_ZERO 2u
#define R2_BR_MAP_HAS_GAP 4u
#define R2_BR_MAP_HAS_AMBIGUITY 8u
#define R2_BR_MAP_HAS_OWNER_CROSSING 16u
#define R2_BR_BLOCK_OFFSET 1u
#define R2_BR_BLOCK_PAGE 2u
#define R2_BR_BLOCK_SIZE_FIELD 4u
#define R2_BR_BLOCK_LAYOUT 8u
#define R2_BR_BLOCK_DONE 16u
#define R2_BR_WORD_RAW 1u
#define R2_BR_WORD_TARGET 2u
#define R2_BR_WORD_MAPPING 4u
#define R2_BR_WORD_VALUE 8u
#define R2_BR_WORD_DONE 16u
enum r2_br_word_state_v1 {
    R2_BR_WORD_UNKNOWN = 0, R2_BR_WORD_SKIPPED, R2_BR_WORD_DIR64,
    R2_BR_WORD_UNSUPPORTED, R2_BR_WORD_INVALID
};

struct r2_br_block_v1 {
    uint32_t directory_offset, file_offset, page_rva, block_size;
    uint32_t word_declared, word_first, word_retained, word_complete;
    uint32_t valid_fields, status, reason, reserved;
    uint64_t raw_header;
    uint32_t raw_header_bytes, reserved2;
};
struct r2_br_word_v1 {
    uint32_t raw_word, type, offset12, block_index;
    uint32_t word_index, file_offset, valid_fields, state;
    uint32_t target_rva, target_extent, target_kind, target_file_offset;
    uint32_t section_characteristics, mapping_flags;
    uint64_t raw_value;
};
struct r2_br_report_v1 {
    uint32_t abi, size, status, reason;
    uint32_t preload_scope, metadata_complete, base_status, base_reason;
    uint64_t failure_offset, work_units, work_limit, base_work_reserved;
    uint32_t coff_characteristics, coff_characteristics_valid, relocs_stripped, directory_condition;
    uint32_t directory_rva, directory_size, directory_file_offset, directory_fields_valid;
    uint32_t block_count, block_complete, block_partial, blocks_unrepresented_min;
    uint32_t word_declared_known, word_count, word_complete, word_partial;
    uint32_t word_unrepresented_known, word_semantics_unknown_known, word_count_unknown, block_count_unknown;
    uint32_t absolute_count, dir64_count, unsupported_count, directory_map_kind;
    uint32_t remaining_directory_bytes, directory_bytes_consumed, base_accepted, reserved;
    /* Original subreport retained byte-for-byte after its one actual parse;
     * relocation helpers NEVER change its status, work, imports, TLS or facts.
     */
    struct r2_pe_raw_report_v1 base;
    struct r2_br_block_v1 blocks[R2_BR_BLOCK_LIMIT];
    struct r2_br_word_v1 words[R2_BR_WORD_LIMIT];
};
/* Native opaque caller workspace. Use actual type only in an including source
 * harness, or exact aligned allocated storage with no incompatible effective
 * type. No allocation or large automatic arrays occur in this component.
 */
struct r2_br_workspace_v1;

/* Exact ABI/size and eight-byte output/workspace alignment, pointer-wrap and
 * ALL pairwise FILE/output/workspace
 * overlaps checked before ANY clear/write. These failures, file-limit refusal
 * and an out-of-range work_limit preserve both output/workspace sentinels.
 * Accessible stable original FILE bytes and exclusive writable aligned caller
 * storage remain preconditions; no OS accessibility/identity probing occurs.
 * work_limit is only a local algorithmic fixture input in INITIAL_WORK..WORK_LIMIT;
 * it grants no original native time/RAM/authority budget. Reservations precede
 * scans, mutations and reads, count conservatively, and are never refunded.
 *
 * Directory 5 and actual COFF RELOCS_STRIPPED are metadata only. COMPLETE means
 * this bounded supported metadata walk; a failed or application-sensitive base
 * status can NEVER become final COMPLETE. metadata_complete separately records
 * the relocation walk. PRELOAD_CLOSURE_UNPROVEN is unconditional. No CRT/PE
 * closure, relocation application, safe-load/relocatability, provider/API-set,
 * SxS/transitive resolution, readonly/original-identity or admission claim.
 *
 * WORD records include partial/unsupported records. Declared WORD slots are
 * known only for validated retained block layouts; unknown flags remain set
 * after an early stop. Unsupported types stop before any following WORD (e.g.
 * HIGHADJ payload) can be misdecoded. ABSOLUTE ignores its low 12 bits. DIR64
 * has extent eight without an invented eight-byte target-alignment rule.
 * Overlapping targets are retained, never deduplicated or written. A raw u64
 * is read only for an entire uniquely FILE-backed span in ONE contiguous owner;
 * mixed, zero-fill, gap, crossing or ambiguous spans have no fabricated value.
 * Zero-fill/mixed are descriptive; gaps do not imply committed image memory.
 * failure_offset is a known FILE location (including entry/header fields), or
 * directory RVA when it cannot bind. Full base diagnostic is always separate.
 */
uint32_t route2_pe_base_relocations_parse_v1(const unsigned char *file, size_t file_bytes,
    uint32_t abi, uint64_t work_limit, struct r2_br_report_v1 *out, size_t out_bytes,
    struct r2_br_workspace_v1 *workspace, size_t workspace_bytes);
#endif
