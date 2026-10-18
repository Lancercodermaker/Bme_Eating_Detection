#ifndef ROUTE2_ELF_LINK_METADATA_H
#define ROUTE2_ELF_LINK_METADATA_H
#include "route2_mount_helper.h"
#if defined(R2_TARGET_LINUX_START)
/* SOURCE ONLY, independent ABI. All sizes are bytes; native alignment is 8.
 * Format: ELF64 little-endian x86-64. No installed loader ABI is assumed.
 */
#define R2_ELF_LINK_ABI 1u
#define R2_ELF_LINK_REPORT_BYTES 1168040u
#define R2_ELF_LINK_WORKSPACE_BYTES 16744u
#define R2_ELF_LINK_ALIGNMENT 8u
#define R2_ELF_LINK_SYMBOL_LIMIT 4096u
#define R2_ELF_LINK_RELOCATION_LIMIT 8192u
#define R2_ELF_LINK_HASH_LIMIT 4096u
#define R2_ELF_LINK_NAME_LIMIT 512u
#define R2_ELF_LINK_NAME_BYTES_LIMIT 1048576u
#define R2_ELF_LINK_WORK_LIMIT UINT64_C(33554432)
/* Reservation includes all clears, bounded local setup, and the ENTIRE old
 * parser ceiling. Reserved units are never refunded. Every later read, scan,
 * comparison and record mutation is preceded by a conservative reservation.
 */
#define R2_ELF_LINK_INITIAL_WORK (UINT64_C(4096)+R2_ELF_LINK_REPORT_BYTES+R2_ELF_LINK_WORKSPACE_BYTES+R2_ELF_RAW_WORK_LIMIT)
enum r2_elf_link_status_v1 {
    R2_ELF_LINK_COMPLETE=0xC331u, R2_ELF_LINK_PARTIAL=0xC332u,
    R2_ELF_LINK_REJECTED=0xC333u, R2_ELF_LINK_BAD_ARGUMENT=0xC334u,
    R2_ELF_LINK_INCOMPLETE=0xC335u, R2_ELF_LINK_BASE_STOP=0xC336u
};
enum r2_elf_link_reason_v1 {
    R2_ELF_LINK_REASON_NONE=0, R2_ELF_LINK_REASON_WORK,
    R2_ELF_LINK_REASON_DUPLICATE_TAG, R2_ELF_LINK_REASON_TAG_PAIR,
    R2_ELF_LINK_REASON_SYMENT, R2_ELF_LINK_REASON_RELENT,
    R2_ELF_LINK_REASON_RELAENT, R2_ELF_LINK_REASON_TABLE_SIZE,
    R2_ELF_LINK_REASON_MAPPING, R2_ELF_LINK_REASON_HASH_COUNT,
    R2_ELF_LINK_REASON_HASH_LIMIT, R2_ELF_LINK_REASON_HASH_INDEX,
    R2_ELF_LINK_REASON_HASH_CYCLE, R2_ELF_LINK_REASON_SYMBOL_ZERO,
    R2_ELF_LINK_REASON_NAME_INDEX, R2_ELF_LINK_REASON_NAME_ASCII,
    R2_ELF_LINK_REASON_NAME_TERMINATOR, R2_ELF_LINK_REASON_NAME_LIMIT,
    R2_ELF_LINK_REASON_NAME_BYTES, R2_ELF_LINK_REASON_SYMBOL_INDEX,
    R2_ELF_LINK_REASON_TABLE_ALIAS, R2_ELF_LINK_REASON_RELOCATION_LIMIT,
    R2_ELF_LINK_REASON_GNU_HEADER
};
#define R2_ELF_LINK_SYMBOL_UNDEFINED 1u
#define R2_ELF_LINK_SYMBOL_ABSOLUTE 2u
#define R2_ELF_LINK_SYMBOL_COMMON 4u
#define R2_ELF_LINK_SYMBOL_IFUNC 8u
#define R2_ELF_LINK_SYMBOL_TLS 16u
#define R2_ELF_LINK_UNSUPPORTED_VERSION 1u
#define R2_ELF_LINK_UNSUPPORTED_SHNDX 2u
#define R2_ELF_LINK_UNSUPPORTED_RELR 4u
#define R2_ELF_LINK_UNSUPPORTED_UNKNOWN 8u
#define R2_ELF_LINK_UNSUPPORTED_HASH_COUNT 16u
#define R2_ELF_LINK_UNSUPPORTED_ALIAS 32u
#define R2_ELF_LINK_UNVALIDATED_ALL 63u /* type/IFUNC/TLS/version/provider/section semantics */
#define R2_ELF_LINK_TABLE_REL 1u
#define R2_ELF_LINK_TABLE_RELA 2u
#define R2_ELF_LINK_TABLE_PLT 3u
#define R2_ELF_LINK_TARGET_UNKNOWN 0u
#define R2_ELF_LINK_TARGET_FILE 1u
#define R2_ELF_LINK_TARGET_ZERO_FILL 2u
#define R2_ELF_LINK_TARGET_CROSSING 3u
#define R2_ELF_LINK_TARGET_UNMAPPED 4u
#define R2_ELF_LINK_TARGET_AMBIGUOUS 5u
#define R2_ELF_LINK_SYMBOL_VALID_EXACT 1u
#define R2_ELF_LINK_SYMBOL_VALID_UNKNOWN 2u
#define R2_ELF_LINK_SYMBOL_INVALID_EXACT 3u
#define R2_ELF_LINK_SYMBOL_NOT_INSPECTED 0u
struct r2_elf_link_symbol_v1 {
    uint64_t file_offset, st_value, st_size, name_file_offset;
    uint32_t st_name, st_info, st_other, st_shndx, facts;
    uint32_t name_length, name_complete, complete, symbol_index, reserved;
};
struct r2_elf_link_relocation_v1 {
    uint64_t file_offset, r_offset, r_info, addend_bits, target_file_offset;
    uint32_t source_table, symbol_index, type, addend_known;
    uint32_t symbol_validation, target_class, target_program, complete;
    uint32_t target_extent_known, target_extent_bytes;
};
struct r2_elf_link_table_v1 {
    uint64_t address, byte_size, file_offset, declared, retained;
    uint32_t present, kind, entry_size, complete;
};
struct r2_elf_link_report_v1 {
    uint32_t abi,size,status,reason,preload_scope,metadata_complete;
    uint32_t unvalidated_semantics,unsupported_conditions;
    uint64_t file_bytes,work_units,failure_offset,failure_value;
    uint32_t failure_subject,symbol_count_exact,symbols_declared,symbols_retained;
    uint32_t symbol_lower_bound,symbol_remainder_unknown,relocations_retained,relocation_remainder_unknown;
    uint32_t names_inspected_bytes,hash_kind,hash_valid,hash_buckets,hash_chains;
    uint32_t gnu_symbol_offset,gnu_bloom_count,gnu_bloom_shift;
    uint32_t hash_buckets_retained,hash_chains_retained,gnu_bloom_retained,hash_remainder_unknown;
    uint64_t relocations_declared;
    uint32_t table_count,base_complete;
    struct r2_elf_raw_report_v1 base;
    struct r2_elf_link_table_v1 tables[3];
    struct r2_elf_link_symbol_v1 symbols[R2_ELF_LINK_SYMBOL_LIMIT];
    struct r2_elf_link_relocation_v1 relocations[R2_ELF_LINK_RELOCATION_LIMIT];
    uint32_t hash_bucket_values[R2_ELF_LINK_HASH_LIMIT];
    uint32_t hash_chain_values[R2_ELF_LINK_HASH_LIMIT];
    uint64_t gnu_bloom_values[R2_ELF_LINK_HASH_LIMIT];
    unsigned char hash_chain_present[R2_ELF_LINK_HASH_LIMIT];
};
/* Workspace has no evidence role. All fields are overwritten by the parser. */
struct r2_elf_link_tag_v1 { uint64_t value,offset; uint32_t present,reserved; };
struct r2_elf_link_workspace_v1 {
    uint32_t chain_state[R2_ELF_LINK_HASH_LIMIT];
    struct r2_elf_link_tag_v1 tags[15];
};
/* Stable accessible original FILE bytes and aligned, accessible, exclusive
 * output/workspace are caller preconditions. ABI, exact sizes, alignment,
 * integer range and ALL pairwise overlaps are checked before ANY writes.
 * BAD_ARGUMENT preserves every output/workspace byte, without reading either.
 * work_limit is a caller-selected ceiling within [INITIAL_WORK, WORK_LIMIT],
 * never evidence about the input. File sizes above 64 MiB are refused before
 * reading input. No heap, OS, loader, symbol resolver or relocation write.
 *
 * base is reparsed from original bytes and retained verbatim. Failure, unknown
 * program/tag facts and application conditions in base are never erased.
 * Only a fully validated SysV nchain establishes an exact symbol count.
 * SysV bucket/count limits are both 1..4096. symbols_declared retains its raw
 * validated nchain even if later symbol-span/zero validation fails; the exact
 * flag additionally requires matching FILE-backed symbol/string spans and
 * the all-zero reserved symbol. Without SysV, symbols_declared is 0 (UNKNOWN),
 * symbol_lower_bound describes the retained prefix and remainder stays UNKNOWN.
 * GNU hash lower bounds do not establish missing-tail absence. Symbol and
 * relocation retained counters count COMPLETE records; the next slot retains
 * the current raw failing record with complete=0. Name references are into the
 * original input; lengths exclude NUL, inspection costs include each NUL and
 * every reread, sharing the 1 MiB bound with the original parser's strings.
 * Hash retained counts cover copied raw slots; hash_chain_present identifies
 * each read slot, including GNU gaps and partial failures. Values can still
 * be invalid indices when hash_valid is zero. hash_remainder_unknown is cleared
 * only for complete SysV hash metadata or an absent hash. GNU chain count is
 * a lower bound only and its unreferenced tail remains UNKNOWN.
 * relocations_declared is the sum of successfully validated REL/RELA/PLT counts so
 * far; each table retains its own raw size even on failure. Remainder flags
 * indicate uninspected/unknown tails, even when subtraction gives their count.
 * RELR presence always keeps the relocation remainder UNKNOWN.
 * Selected GNU profile: positive bucket/bloom counts, power-of-two bloom count,
 * symbol offset 1..4096, bloom shift below 64; other headers are refused.
 *
 * r_info/type, binding, visibility, ABS/COMMON/IFUNC/TLS flags are raw facts.
 * Binding is st_info>>4, type is st_info&15, visibility is st_other&3; the
 * remaining st_other bits are retained without interpretation.
 * Explicit RELA addends are unsigned bit representations; REL addends stay
 * unknown. Target classification describes only a one-byte address membership
 * fact, never a relocation-dependent write extent or an implicit addend read.
 * target_extent_known/bytes remain zero (UNKNOWN). CROSSING is reserved for a
 * future explicit extent; a one-byte address cannot
 * straddle a boundary. PLT overlap is explicitly unsupported before iteration.
 * Version, SHNDX and RELR tags are retained as unsupported conditions in base.
 * metadata_complete describes symbol/relocation record coverage; unsupported
 * conditions still prevent the final COMPLETE status.
 * COMPLETE covers this bounded metadata profile only. PRELOAD_CLOSURE_UNPROVEN
 * and unvalidated semantics are unconditional, even for static empty input.
 * Build the new .c INSTEAD OF its included route2_mount_helper.c, never both.
 */
uint32_t route2_elf_link_metadata_parse_v1(const unsigned char *file,size_t file_size,
    uint32_t abi,struct r2_elf_link_report_v1 *out,size_t out_size,
    struct r2_elf_link_workspace_v1 *workspace,size_t workspace_size,uint64_t work_limit);
#endif
#endif
