#ifndef ROUTE2_WINDOWS_PRELOAD_CATALOG_H
#define ROUTE2_WINDOWS_PRELOAD_CATALOG_H
/* SOURCE ONLY / UNCOMPILED / UNRUN. Native AMD64 C11 ABI, no export target.
 * All caller memory must remain readable/stable and outputs/workspace writable
 * and exclusive for the call. Range checks do not prove accessibility or file
 * identity. FILE bytes only; no mapped-image, OS resolver, loader or I/O path.
 * This local finite-catalog fact ALWAYS retains PRELOAD_CLOSURE_UNPROVEN.
 * No admission, issuer, transport, ABI-callability, readonly-file, SxS/API-set,
 * full-first-load, deployment or safe-application claim follows from binding.
 */
#include <stddef.h>
#include <stdint.h>
#define R2_PC_ABI 1u
#define R2_PC_IMAGES 16u
#define R2_PC_FUNCTIONS 4096u
#define R2_PC_NAMES 4096u
#define R2_PC_EDGES 4096u
#define R2_PC_DEPTH 32u
#define R2_PC_KEY_BYTES 128u
#define R2_PC_NAME_BYTES 512u
#define R2_PC_NAME_READ_BYTES 1048576u
#define R2_PC_FILE_BYTES 67108864u
#define R2_PC_TOTAL_BYTES UINT64_C(268435456)
#define R2_PC_WORKSPACE_BYTES 7340032u
#define R2_PC_READ_WORK UINT64_C(134217728)
#define R2_PC_LOOKUP_WORK UINT64_C(33554432)
#define R2_PC_VALIDATION_WORK UINT64_C(131072)
#define R2_PC_TOTAL_WORK (R2_PC_READ_WORK + R2_PC_LOOKUP_WORK)
#define R2_PC_UNPROVEN 0xC3FFu
#define R2_PC_NONE UINT32_MAX

enum r2_pc_status_v1 {
    R2_PC_COMPLETE = 0xC311u, R2_PC_PARTIAL, R2_PC_REJECTED,
    R2_PC_BAD_ARGUMENT, R2_PC_ALIAS, R2_PC_BAD_KEY, R2_PC_DUPLICATE_KEY,
    R2_PC_FILE_LIMIT, R2_PC_TOTAL_LIMIT, R2_PC_IMAGE_LIMIT
};
enum r2_pc_reason_v1 {
    R2_PC_REASON_NONE = 0, R2_PC_BASE_PARSE, R2_PC_EXPORT_DIRECTORY,
    R2_PC_RESERVED_FLAGS, R2_PC_FUNCTION_LIMIT, R2_PC_NAME_LIMIT,
    R2_PC_ORDINAL_OVERFLOW, R2_PC_EXPORT_NAME_ORDER,
    R2_PC_EXPORT_NAME_ORDINAL, R2_PC_NONASCII, R2_PC_EXPORT_NAME,
    R2_PC_FORWARDER_NUL, R2_PC_FORWARDER_GRAMMAR, R2_PC_TARGET_RVA,
    R2_PC_READ_LIMIT, R2_PC_LOOKUP_LIMIT, R2_PC_EDGE_LIMIT,
    R2_PC_PROVIDER_MISSING, R2_PC_PROVIDER_INVALID, R2_PC_API_SET,
    R2_PC_EXPORT_MISSING, R2_PC_EXPORT_HOLE, R2_PC_FORWARDER_CYCLE,
    R2_PC_DEPTH_LIMIT, R2_PC_IMPORT_PARTIAL, R2_PC_MODULE_KEY,
    R2_PC_TARGET_ORDINAL_OVERFLOW, R2_PC_STRING_LIMIT
};
enum r2_pc_target_v1 {
    R2_PC_HOLE = 0, R2_PC_HEADER_BYTES, R2_PC_CODE_BYTES,
    R2_PC_DATA_BYTES, R2_PC_CODE_ZERO_FILL, R2_PC_DATA_ZERO_FILL,
    R2_PC_FORWARDER, R2_PC_TARGET_INVALID
};
struct r2_pc_image_v1 {
    const unsigned char *file;
    uint64_t file_bytes;
    /* Explicit pathless ASCII key. Allowed alphabet A-Z a-z 0-9 _ - .;
     * no empty components, initial/trailing dot, or consecutive dots. Last
     * optional .dll is removed case-insensitively, remaining key casefolded.
     * Embedded NUL is forbidden; key_length excludes optional final NUL.
     * Raw export DLL Name is metadata and never changes this identity key.
     */
    uint32_t key_length, reserved;
    unsigned char key[R2_PC_KEY_BYTES];
};
struct r2_pc_input_v1 {
    uint32_t abi, size, image_count, flags; /* image_count 1..16; flags zero */
    struct r2_pc_image_v1 images[R2_PC_IMAGES];
};
/* Opaque native workspace: reserve the exact descriptor size/alignment in
 * caller-owned untyped allocated storage, or use the actual type when this
 * TU is included by a SOURCE harness. Do not cast a declared byte-array
 * object to it: that would violate C effective-type rules. APIs allocate
 * nothing. Allocation/lifetime remain caller preconditions, not authority.
 */
struct r2_pc_workspace_v1;
struct r2_pc_function_v1 {
    uint32_t eat_index, ordinal, eat_offset, target_rva;
    uint32_t target_kind, target_offset, forward_offset, forward_length;
    uint32_t forward_reason, section_characteristics;
};
struct r2_pc_name_v1 { uint32_t offset, length, eat_index, table_offset; };
/* In both exports and image reports, tls_condition is boolean observed raw
 * TLS-directory presence, not callback count or a directory-validity claim.
 * base_status/base_reason retain the original callback-sensitive parser fact:
 * COMPLETE can coexist with a present TLS directory and no callbacks;
 * APPLICATION_TLS_PRESENT records its parsed nonempty callback condition.
 * Neither presence nor absence establishes safe application/preload acceptance.
 */
struct r2_pc_exports_v1 {
    uint32_t abi, size, status, reason;
    uint32_t preload_scope, structural_complete, base_status, base_reason;
    uint64_t failure_offset, work_units;
    uint32_t directory_rva, directory_size, directory_offset, flags;
    uint32_t ordinal_base, function_declared, name_declared, function_count;
    uint32_t name_count, dll_name_offset, dll_name_length, tls_condition;
    uint32_t raw_reason, reserved; /* original bounded helper export failure */
    struct r2_pc_function_v1 functions[R2_PC_FUNCTIONS];
    struct r2_pc_name_v1 names[R2_PC_NAMES];
};
/* Each retained hop is actual selected image/EAT evidence. Provider lookup
 * failure has no hop and keeps requested module/symbol refs on the edge (or
 * last hop forward string). NONE is used for absent provider/EAT, never zero.
 * Initial module/name/thunk offsets refer to importer; hop offsets refer to
 * hop.image. failure_offset refers explicitly to failure_image (NONE on
 * a bound edge). An unmappable failure can be an RVA, as its reason says.
 */
struct r2_pc_hop_v1 {
    uint32_t image, eat_index, ordinal, eat_offset;
    uint32_t target_rva, target_kind, target_offset, forward_offset;
    uint32_t forward_length, section_characteristics;
};
struct r2_pc_edge_v1 {
    uint32_t importer, descriptor, symbol, import_kind;
    uint32_t status, reason, provider, eat_index;
    uint32_t module_offset, module_length, symbol_kind, ordinal;
    uint32_t name_offset, name_length, thunk_offset, chain_count;
    uint32_t failure_image, reserved;
    uint64_t failure_offset;
    struct r2_pc_hop_v1 chain[R2_PC_DEPTH];
};
struct r2_pc_image_report_v1 {
    uint32_t base_status, base_reason, export_status, export_reason;
    uint32_t base_complete, export_complete, tls_condition, descriptor_count;
    uint32_t symbol_count, edge_first, edge_count, unrepresented_symbols;
    uint32_t export_raw_reason, import_count_unknown;
    uint64_t base_failure_offset, export_failure_offset, read_work;
};
struct r2_pc_report_v1 {
    uint32_t abi, size, status, reason;
    uint32_t preload_scope, complete_for_supplied_catalog, image_count, failed_images;
    uint32_t edge_count, bound_edges, unresolved_edges, unrepresented_symbols;
    uint32_t affected_images, first_failure_image, first_failure_edge, unknown_import_images;
    /* lookup_work includes a fixed 131072-unit reservation charged before
     * metadata validation/normalization; read_work is actual PE helper work.
     */
    uint64_t failure_offset, read_work, lookup_work, total_file_bytes;
    struct r2_pc_image_report_v1 images[R2_PC_IMAGES];
    struct r2_pc_edge_v1 edges[R2_PC_EDGES];
};
struct r2_pc_abi_v1 {
    uint32_t abi, size, pointer_bytes, alignment;
    uint32_t input_bytes, image_bytes, workspace_bytes, exports_bytes;
    uint32_t report_bytes, edge_bytes, hop_bytes, image_report_bytes;
    uint32_t images, functions, names, edges, depth, name_bytes, key_bytes, name_read_bytes;
    uint64_t file_bytes, total_bytes, read_work, lookup_work;
};
/* Exact sizeof and 8-byte alignment required, including input. Wrong ABI,
 * size, pointer wrap, overlap, keys, duplicates or file/total/image limits
 * return before ANY clearing.
 * File/file aliases also rejected; unused image slots must be all zero.
 * Input reports/status supplied by callers are never accepted as evidence.
 * parse_exports reparses original bytes, binder reparses EVERY catalog image.
 * Complete means only the supported raw subset and finite local catalog.
 * Base APPLICATION_TLS_PRESENT is retained, never promoted to safe preload.
 * Forward grammar is deliberately exactly one dot: key.symbol or key.#u32.
 * Other NUL-terminated ASCII grammars are unsupported, not malformed PE.
 * Export Characteristics must be zero (reserved-field conservative policy).
 * Export names strictly sorted unique ASCII, case sensitive; aliases allowed.
 * Names/forward strings inspect <=512 bytes INCLUDING NUL; combined
 * import/export FILE string inspection is cumulatively <=1MiB per image,
 * including every reread, both comparison operands and forwarder/module
 * parsing. Conservative pre-read key reservations are never refunded.
 * Caller catalog-key metadata uses the separate validation/lookup budget.
 * Initial raw-import exhaustion remains BASE_PARSE/base_reason NAME_BYTES_LIMIT;
 * export parsing/reread exhaustion is READ_LIMIT/raw_reason NAME_BYTES_LIMIT.
 * Binding uses STRING_LIMIT with actual source failure_image/offset. Earlier bound
 * edges and all enumerated unresolved records remain. API-/ext- keys
 * cannot bind even when such a caller key exists. No fallback or recursion.
 * Partial count fields include retained incomplete symbols/functions. An edge
 * limit explicitly reports known unrepresented symbols; base parse failures
 * can leave further unenumerated imports UNKNOWN, never an inferred zero.
 */
uint32_t route2_pc_describe_v1(struct r2_pc_abi_v1 *, size_t);
uint32_t route2_pc_parse_exports_v1(const unsigned char *, size_t, uint32_t,
    struct r2_pc_exports_v1 *, size_t, struct r2_pc_workspace_v1 *, size_t);
uint32_t route2_pc_bind_catalog_v1(const struct r2_pc_input_v1 *, size_t,
    struct r2_pc_report_v1 *, size_t, struct r2_pc_workspace_v1 *, size_t);
#endif
