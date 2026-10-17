/* SOURCE ONLY: all assertions UNCOMPILED and UNRUN.
 * Fixture/assertion plan written before production implementation:
 * - named and ordinal normal/delay imports bind through actual production TU;
 * - aliases and holes; direct code, data and virtual zero-fill retain facts;
 * - named/ordinal forwarders, three-image chains, module/forwarder cycles;
 * - missing/API-set/duplicate keys, invalid unused image, malformed exports;
 * - sorted unique names, ordinal arithmetic, directory-contained NUL, RVA/span;
 * - file/count/depth/work limits and partial record/failure preservation;
 * - native ABI, exact sizes, alignment, wrap and aliases reject before writes.
 * No compiler, runtime, OS/probe, filesystem fixture, GT or helper invocation.
 */
#if !defined(R2_TARGET_WINDOWS_SEED)
#error "Explicit Windows seed target required"
#endif
#include "../../src/eating_event/route2_candidate_overlap/native/route2_windows_preload_catalog.c"

#define C_BYTES 8192u
static unsigned char c_files[4][C_BYTES];
static struct r2_pc_input_v1 c_input;
static struct r2_pc_workspace_v1 c_workspace;
static struct r2_pc_report_v1 c_report;
static struct r2_pc_exports_v1 c_exports;
static uint32_t c_failures;
#define C_CHECK(e) do { if (!(e)) ++c_failures; } while (0)

/* Functions and assertions follow the plan above. No execution claimed. */
static void c_put(uint32_t im, uint32_t off, uint64_t value, uint32_t n)
{
    uint32_t i;
    for (i = 0; i < n; ++i) c_files[im][off + i] = (unsigned char)(value >> (i * 8));
}
static void c_text(uint32_t im, uint32_t off, const char *text)
{
    do { c_files[im][off++] = (unsigned char)*text; } while (*text++);
}
static uint32_t c_rva(uint32_t off) { return off + 0xE00u; }
static void c_directory(uint32_t im, uint32_t index, uint32_t off, uint32_t bytes)
{
    c_put(im, 0x108 + index * 8, off ? c_rva(off) : 0, 4);
    c_put(im, 0x10C + index * 8, bytes, 4);
}
static void c_key(uint32_t im, const char *key)
{
    uint32_t n = 0;
    memset(c_input.images[im].key, 0, R2_PC_KEY_BYTES);
    while (key[n]) { c_input.images[im].key[n] = (unsigned char)key[n]; ++n; }
    c_input.images[im].key_length = n;
}
static void c_base(uint32_t im)
{
    memset(c_files[im], 0, C_BYTES);
    c_put(im, 0, 0x5A4D, 2); c_put(im, 0x3C, 0x80, 4);
    c_put(im, 0x80, 0x4550, 4); c_put(im, 0x84, 0x8664, 2);
    c_put(im, 0x86, 1, 2); c_put(im, 0x94, 240, 2); c_put(im, 0x96, 0x22, 2);
    c_put(im, 0x98, 0x20B, 2); c_put(im, 0xA8, 0x2600, 4);
    c_put(im, 0xB0, UINT64_C(0x140000000), 8);
    c_put(im, 0xB8, 0x1000, 4); c_put(im, 0xBC, 0x200, 4);
    c_put(im, 0xD0, 0x4000, 4); c_put(im, 0xD4, 0x200, 4); c_put(im, 0x104, 16, 4);
    c_text(im, 0x188, ".invent");
    c_put(im, 0x190, 0x3000, 4); c_put(im, 0x194, 0x1000, 4);
    c_put(im, 0x198, C_BYTES - 0x200, 4); c_put(im, 0x19C, 0x200, 4);
    c_put(im, 0x1AC, 0x60000020, 4);
}
static void c_prepare(uint32_t count)
{
    uint32_t i;
    static const char *keys[4] = { "root.dll", "alpha.dll", "beta.dll", "gamma.dll" };
    memset(&c_input, 0, sizeof(c_input));
    c_input.abi = R2_PC_ABI; c_input.size = sizeof(c_input); c_input.image_count = count;
    for (i = 0; i < 4; ++i) c_base(i);
    for (i = 0; i < count; ++i) {
        c_input.images[i].file = c_files[i]; c_input.images[i].file_bytes = C_BYTES; c_key(i, keys[i]);
    }
}
static void c_name(uint32_t im, uint32_t index, const char *name, uint32_t eat_index)
{
    c_put(im, 0x1300 + index * 4, c_rva(0x1600 + index * 16), 4);
    c_put(im, 0x1500 + index * 2, eat_index, 2);
    c_text(im, 0x1600 + index * 16, name);
}
static void c_exports_fixture(uint32_t im, uint32_t base, uint32_t functions, uint32_t names)
{
    uint32_t i;
    c_directory(im, 0, 0x600, 0xA00);
    c_put(im, 0x60C, c_rva(0x700), 4); c_text(im, 0x700, "untrusted-metadata.dll");
    c_put(im, 0x610, base, 4); c_put(im, 0x614, functions, 4); c_put(im, 0x618, names, 4);
    c_put(im, 0x61C, c_rva(0x1100), 4); c_put(im, 0x620, c_rva(0x1300), 4);
    c_put(im, 0x624, c_rva(0x1500), 4);
    for (i = 0; i < functions && i < 64; ++i) c_put(im, 0x1100 + i * 4, c_rva(0x1800 + i), 4);
    if (names) c_name(im, 0, "Entry", 0);
}
static void c_forward(uint32_t im, uint32_t index, const char *target)
{
    c_put(im, 0x1100 + index * 4, c_rva(0x900 + index * 32), 4);
    c_text(im, 0x900 + index * 32, target);
}
static void c_normal(uint32_t im, const char *module, const char *name, uint32_t ordinal, uint32_t both)
{
    uint64_t first = name ? c_rva(0x3E0) : (UINT64_C(0x8000000000000000) | ordinal);
    c_directory(im, 1, 0x300, 40);
    c_put(im, 0x300, c_rva(0x3A0), 4); c_put(im, 0x30C, c_rva(0x360), 4);
    c_put(im, 0x310, c_rva(0x3C0), 4); c_text(im, 0x360, module);
    c_put(im, 0x3A0, first, 8); c_put(im, 0x3C0, first, 8);
    if (name) c_text(im, 0x3E2, name);
    if (both) {
        c_put(im, 0x3A8, UINT64_C(0x8000000000000000) | ordinal, 8);
        c_put(im, 0x3C8, UINT64_C(0x8000000000000000) | ordinal, 8);
    }
}
static void c_delay(uint32_t im, const char *module, uint32_t ordinal)
{
    c_directory(im, 13, 0x400, 64);
    c_put(im, 0x400, 1, 4); c_put(im, 0x404, c_rva(0x460), 4);
    c_put(im, 0x408, c_rva(0x480), 4); c_put(im, 0x40C, c_rva(0x4C0), 4);
    c_put(im, 0x410, c_rva(0x4A0), 4); c_text(im, 0x460, module);
    c_put(im, 0x4A0, UINT64_C(0x8000000000000000) | ordinal, 8);
    c_put(im, 0x4C0, UINT64_C(0x140002600), 8);
}
static uint32_t c_bind(void)
{
    uint32_t result = route2_pc_bind_catalog_v1(&c_input, sizeof(c_input), &c_report,
        sizeof(c_report), &c_workspace, sizeof(c_workspace));
    C_CHECK(result == c_report.status);
    C_CHECK(c_report.abi == R2_PC_ABI && c_report.size == sizeof(c_report));
    C_CHECK(c_report.preload_scope == R2_PC_UNPROVEN);
    C_CHECK(c_report.edge_count <= R2_PC_EDGES && c_report.bound_edges + c_report.unresolved_edges == c_report.edge_count);
    C_CHECK(c_report.read_work <= R2_PC_READ_WORK && c_report.lookup_work <= R2_PC_LOOKUP_WORK);
    C_CHECK((result == R2_PC_COMPLETE) == (c_report.complete_for_supplied_catalog == 1));
    return result;
}
static uint32_t c_parse(uint32_t im)
{
    uint32_t result = route2_pc_parse_exports_v1(c_files[im], C_BYTES, R2_PC_ABI,
        &c_exports, sizeof(c_exports), &c_workspace, sizeof(c_workspace));
    C_CHECK(result == c_exports.status && c_exports.preload_scope == R2_PC_UNPROVEN);
    C_CHECK(c_exports.function_count <= R2_PC_FUNCTIONS && c_exports.name_count <= R2_PC_NAMES);
    C_CHECK(c_exports.work_units <= R2_PE_RAW_WORK_LIMIT);
    return result;
}
static void c_good_cases(void)
{
    c_prepare(2); c_normal(0, "ALPHA.DLL", "Entry", 8, 1); c_delay(0, "alpha", 7);
    c_exports_fixture(1, 7, 2, 1);
    C_CHECK(c_bind() == R2_PC_COMPLETE && c_report.edge_count == 3 && c_report.bound_edges == 3);
    C_CHECK(c_report.edges[0].chain[0].image == 1 && c_report.edges[0].chain[0].ordinal == 7);
    C_CHECK(c_report.edges[1].chain[0].eat_index == 1 && c_report.edges[1].ordinal == 8);
    C_CHECK(c_report.edges[2].import_kind == R2_PE_IMPORT_DELAY && c_report.edges[2].chain[0].ordinal == 7);
    C_CHECK(c_report.edges[0].chain[0].target_kind == R2_PC_CODE_BYTES);
    C_CHECK(c_report.edges[0].chain[0].target_offset == 0x1800);
    c_put(0, 0x4A0, c_rva(0x4E0), 8); c_text(0, 0x4E2, "Entry");
    C_CHECK(c_bind() == R2_PC_COMPLETE && c_report.edges[2].symbol_kind == R2_PE_SYMBOL_NAME);
    C_CHECK(c_report.edges[2].name_offset == 0x4E2 && c_report.edges[2].import_kind == R2_PE_IMPORT_DELAY);
    c_put(1, 0x1AC, 0xC0000040, 4);
    C_CHECK(c_bind() == R2_PC_COMPLETE && c_report.edges[0].chain[0].target_kind == R2_PC_DATA_BYTES);
    c_put(1, 0x1100, 0x3000, 4);
    C_CHECK(c_bind() == R2_PC_COMPLETE && c_report.edges[0].chain[0].target_kind == R2_PC_DATA_ZERO_FILL);
    C_CHECK(c_report.edges[0].chain[0].target_offset == R2_PC_NONE);
    c_put(1, 0x1AC, 0x60000020, 4);
    C_CHECK(c_bind() == R2_PC_COMPLETE && c_report.edges[0].chain[0].target_kind == R2_PC_CODE_ZERO_FILL);
    c_put(1, 0x1100, 0x100, 4);
    C_CHECK(c_bind() == R2_PC_COMPLETE && c_report.edges[0].chain[0].target_kind == R2_PC_HEADER_BYTES);
    /* Two distinct sorted names may alias one EAT entry. */
    c_exports_fixture(1, 7, 2, 2); c_name(1, 0, "Alias", 0); c_name(1, 1, "Entry", 0);
    C_CHECK(c_bind() == R2_PC_COMPLETE && c_report.edges[0].chain[0].eat_index == 0);
    c_put(1, 0x1100, 0, 4);
    C_CHECK(c_bind() == R2_PC_PARTIAL && c_report.bound_edges == 1 && c_report.unresolved_edges == 2);
    C_CHECK(c_report.edges[0].reason == R2_PC_EXPORT_HOLE && c_report.edges[0].chain_count == 1);
    c_prepare(2); c_normal(0, "alpha", NULL, 0, 0); c_exports_fixture(1, 0, 1, 0);
    C_CHECK(c_bind() == R2_PC_COMPLETE && c_report.edges[0].chain[0].ordinal == 0);
    /* SOURCE-only SPEC P2 regression assertions, written before the repair:
     * absent TLS and a present valid TLS directory with an eight-byte template
     * and AddressOfCallbacks==0 must remain distinct through BOTH APIs.
     * All assertions remain UNCOMPILED and UNRUN.
     */
    c_prepare(2); c_normal(0, "alpha", "Entry", 0, 0); c_exports_fixture(1, 1, 1, 1);
    C_CHECK(c_parse(0) == R2_PC_COMPLETE && c_exports.tls_condition == 0);
    C_CHECK(c_exports.base_status == R2_PE_RAW_COMPLETE && c_exports.base_reason == R2_PE_REASON_NONE);
    C_CHECK(c_exports.preload_scope == R2_PC_UNPROVEN);
    C_CHECK(c_bind() == R2_PC_COMPLETE && c_report.images[0].tls_condition == 0);
    C_CHECK(c_report.images[0].base_status == R2_PE_RAW_COMPLETE && c_report.images[0].base_reason == R2_PE_REASON_NONE);
    C_CHECK(c_report.preload_scope == R2_PC_UNPROVEN);
    c_directory(0, 9, 0x500, 40);
    c_put(0, 0x500, UINT64_C(0x140000000) + c_rva(0x540), 8);
    c_put(0, 0x508, UINT64_C(0x140000000) + c_rva(0x548), 8);
    c_put(0, 0x510, UINT64_C(0x140000000) + c_rva(0x560), 8);
    c_put(0, 0x518, 0, 8);
    c_put(0, 0x540, UINT64_C(0x0807060504030201), 8);
    C_CHECK(c_parse(0) == R2_PC_COMPLETE && c_exports.tls_condition == 1);
    C_CHECK(c_exports.base_status == R2_PE_RAW_COMPLETE && c_exports.base_reason == R2_PE_REASON_NONE);
    C_CHECK(c_workspace.storage.images[0].raw.tls.present == 1 && c_workspace.storage.images[0].raw.tls.fields_valid == 1);
    C_CHECK(c_workspace.storage.images[0].raw.tls.template_bytes == 8 && c_workspace.storage.images[0].raw.tls.callback_count == 0);
    C_CHECK(c_exports.preload_scope == R2_PC_UNPROVEN);
    C_CHECK(c_bind() == R2_PC_COMPLETE && c_report.images[0].tls_condition == 1);
    C_CHECK(c_report.images[0].base_status == R2_PE_RAW_COMPLETE && c_report.images[0].base_reason == R2_PE_REASON_NONE);
    C_CHECK(c_report.preload_scope == R2_PC_UNPROVEN);
    /* TLS structural facts are retained while local binding can complete. */
    c_prepare(2); c_normal(0, "alpha", "Entry", 0, 0); c_exports_fixture(1, 1, 1, 1);
    c_directory(0, 9, 0x500, 40);
    c_put(0, 0x510, UINT64_C(0x140000000) + c_rva(0x560), 8);
    c_put(0, 0x518, UINT64_C(0x140000000) + c_rva(0x580), 8);
    c_put(0, 0x580, UINT64_C(0x140000000) + c_rva(0x1800), 8);
    C_CHECK(c_bind() == R2_PC_COMPLETE && c_report.images[0].tls_condition == 1);
    C_CHECK(c_report.images[0].base_status == R2_PE_RAW_APPLICATION_TLS_PRESENT);
    C_CHECK(c_report.preload_scope == R2_PC_UNPROVEN);
}
static void c_forward_cases(void)
{
    c_prepare(4); c_normal(0, "alpha", "Entry", 0, 0);
    c_exports_fixture(1, 1, 1, 1); c_forward(1, 0, "beta.Entry");
    c_exports_fixture(2, 7, 1, 1); c_forward(2, 0, "gamma.#9");
    c_exports_fixture(3, 9, 1, 1);
    C_CHECK(c_bind() == R2_PC_COMPLETE && c_report.edges[0].chain_count == 3);
    C_CHECK(c_report.edges[0].chain[1].image == 2 && c_report.edges[0].chain[2].ordinal == 9);
    C_CHECK(c_report.edges[0].chain[0].forward_offset == 0x900);
    c_forward(2, 0, "alpha.Entry");
    C_CHECK(c_bind() == R2_PC_PARTIAL && c_report.edges[0].reason == R2_PC_FORWARDER_CYCLE);
    C_CHECK(c_report.edges[0].chain_count == 2 && c_report.edges[0].provider == 1);
    C_CHECK(c_report.edges[0].failure_image == 1 && c_report.first_failure_image == 1);
    c_forward(2, 0, "gamma.#4294967296");
    C_CHECK(c_bind() == R2_PC_PARTIAL && c_report.edges[0].reason == R2_PC_TARGET_ORDINAL_OVERFLOW);
    c_forward(2, 0, "gamma.dll.Entry");
    C_CHECK(c_bind() == R2_PC_PARTIAL && c_report.edges[0].reason == R2_PC_FORWARDER_GRAMMAR);
    C_CHECK(c_report.failed_images == 0); /* unsupported grammar is an edge fact */
    c_forward(2, 0, "gamma.Entry"); c_name(3, 0, "entry", 0);
    C_CHECK(c_bind() == R2_PC_PARTIAL && c_report.edges[0].reason == R2_PC_EXPORT_MISSING);
    /* A biased ordinal can use the complete u32 range in a forwarder. */
    c_prepare(3); c_normal(0, "alpha", "Entry", 0, 0);
    c_exports_fixture(1, 1, 1, 1); c_forward(1, 0, "beta.#4294967295");
    c_exports_fixture(2, UINT32_MAX, 1, 1);
    C_CHECK(c_bind() == R2_PC_COMPLETE && c_report.edges[0].chain[1].ordinal == UINT32_MAX);
    /* Imports between modules can cycle without any forwarder cycle. */
    c_prepare(2); c_normal(0, "alpha", "Entry", 0, 0); c_normal(1, "root", "Entry", 0, 0);
    c_exports_fixture(0, 1, 1, 1); c_exports_fixture(1, 1, 1, 1);
    C_CHECK(c_bind() == R2_PC_COMPLETE && c_report.edge_count == 2 && c_report.bound_edges == 2);
}
static void c_catalog_cases(void)
{
    uint32_t result;
    c_prepare(2); c_normal(0, "alpha", "Entry", 0, 0);
    C_CHECK(c_bind() == R2_PC_PARTIAL && c_report.edges[0].reason == R2_PC_EXPORT_MISSING);
    C_CHECK(c_report.failed_images == 0 && c_report.images[1].export_complete);
    c_prepare(2); c_normal(0, "absent", "Entry", 0, 0); c_exports_fixture(1, 1, 1, 1);
    C_CHECK(c_bind() == R2_PC_PARTIAL && c_report.edges[0].reason == R2_PC_PROVIDER_MISSING);
    C_CHECK(c_report.edges[0].provider == R2_PC_NONE && c_report.first_failure_edge == 0);
    c_prepare(2); c_normal(0, "alpha", "Entry", 0, 0); c_exports_fixture(1, 1, 1, 1);
    c_files[0][0x3E2] = 0x80;
    C_CHECK(c_bind() == R2_PC_PARTIAL && c_report.edges[0].reason == R2_PC_NONASCII);
    C_CHECK(c_report.edges[0].failure_offset == 0x3E2);
    c_normal(0, "api-ms-win-invented", "Entry", 0, 0); c_key(1, "api-ms-win-invented.dll");
    C_CHECK(c_bind() == R2_PC_PARTIAL && c_report.edges[0].reason == R2_PC_API_SET);
    c_normal(0, "ext-invented", "Entry", 0, 0); c_key(1, "ext-invented.dll");
    C_CHECK(c_bind() == R2_PC_PARTIAL && c_report.edges[0].reason == R2_PC_API_SET);
    c_prepare(3); c_normal(0, "alpha", "Entry", 0, 0); c_exports_fixture(1, 1, 1, 1);
    c_files[2][0] = 0;
    C_CHECK(c_bind() == R2_PC_PARTIAL && c_report.bound_edges == 1 && c_report.failed_images == 1);
    C_CHECK(!c_report.images[2].base_complete && c_report.images[2].base_reason == R2_PE_REASON_DOS);
    c_files[1][0] = 0;
    C_CHECK(c_bind() == R2_PC_PARTIAL && c_report.edges[0].reason == R2_PC_PROVIDER_INVALID);
    c_prepare(2); c_key(1, "ROOT");
    memset(&c_report, 0xA5, sizeof(c_report)); memset(&c_workspace, 0x5A, sizeof(c_workspace));
    result = route2_pc_bind_catalog_v1(&c_input, sizeof(c_input), &c_report,
        sizeof(c_report), &c_workspace, sizeof(c_workspace));
    C_CHECK(result == R2_PC_DUPLICATE_KEY && c_report.abi == 0xA5A5A5A5u);
    C_CHECK(((unsigned char *)&c_workspace)[0] == 0x5A);
    c_key(1, "bad/path.dll");
    C_CHECK(route2_pc_bind_catalog_v1(&c_input, sizeof(c_input), &c_report,
        sizeof(c_report), &c_workspace, sizeof(c_workspace)) == R2_PC_BAD_KEY);
    C_CHECK(c_report.abi == 0xA5A5A5A5u);
}
static void c_export_bad_cases(void)
{
    uint32_t i;
    c_prepare(1);
    C_CHECK(c_parse(0) == R2_PC_COMPLETE && !c_exports.function_count && c_exports.structural_complete);
    c_exports_fixture(0, 7, 2, 2); c_name(0, 0, "Entry", 0); c_name(0, 1, "Alias", 1);
    C_CHECK(c_parse(0) == R2_PC_REJECTED && c_exports.reason == R2_PC_EXPORT_NAME_ORDER);
    C_CHECK(c_exports.function_count == 2 && c_exports.name_count == 2 && c_exports.failure_offset == 0x1304);
    c_name(0, 1, "Entry", 1);
    C_CHECK(c_parse(0) == R2_PC_REJECTED && c_exports.reason == R2_PC_EXPORT_NAME_ORDER);
    c_name(0, 1, "Extra", 2);
    C_CHECK(c_parse(0) == R2_PC_REJECTED && c_exports.reason == R2_PC_EXPORT_NAME_ORDINAL);
    c_exports_fixture(0, UINT32_MAX, 2, 0);
    C_CHECK(c_parse(0) == R2_PC_REJECTED && c_exports.reason == R2_PC_ORDINAL_OVERFLOW);
    c_exports_fixture(0, 1, R2_PC_FUNCTIONS + 1, 0);
    C_CHECK(c_parse(0) == R2_PC_PARTIAL && c_exports.reason == R2_PC_FUNCTION_LIMIT);
    c_exports_fixture(0, 1, 1, R2_PC_NAMES + 1);
    C_CHECK(c_parse(0) == R2_PC_PARTIAL && c_exports.reason == R2_PC_NAME_LIMIT);
    c_exports_fixture(0, 1, 1, 1); c_put(0, 0x600, 1, 4);
    C_CHECK(c_parse(0) == R2_PC_PARTIAL && c_exports.reason == R2_PC_RESERVED_FLAGS);
    c_put(0, 0x600, 0, 4); c_files[0][0x1600] = 0x80;
    C_CHECK(c_parse(0) == R2_PC_REJECTED && c_exports.reason == R2_PC_NONASCII);
    c_exports_fixture(0, 1, 1, 1); c_name(0, 0, "Entry", 0);
    c_put(0, 0x1100, c_rva(0xFFE), 4); c_text(0, 0xFFE, "a");
    C_CHECK(c_parse(0) == R2_PC_COMPLETE && c_exports.functions[0].forward_length == 1);
    C_CHECK(c_exports.functions[0].forward_reason == R2_PC_FORWARDER_GRAMMAR);
    c_files[0][0xFFE] = 0;
    C_CHECK(c_parse(0) == R2_PC_COMPLETE && c_exports.functions[0].forward_reason == R2_PC_FORWARDER_GRAMMAR);
    c_files[0][0xFFE] = 'a'; c_files[0][0xFFF] = 'b';
    C_CHECK(c_parse(0) == R2_PC_REJECTED && c_exports.reason == R2_PC_FORWARDER_NUL);
    C_CHECK(c_exports.functions[0].forward_offset == 0xFFE && c_exports.functions[0].forward_length == 2);
    /* A NUL just OUTSIDE the directory does not terminate a forwarder. */
    c_files[0][0x1000] = 0;
    C_CHECK(c_parse(0) == R2_PC_REJECTED && c_exports.reason == R2_PC_FORWARDER_NUL);
    c_exports_fixture(0, 1, 1, 1); c_put(0, 0x1100, 0x4000, 4);
    C_CHECK(c_parse(0) == R2_PC_REJECTED && c_exports.reason == R2_PC_TARGET_RVA);
    c_exports_fixture(0, 1, 1, 1); c_put(0, 0x1300, 0x3000, 4);
    C_CHECK(c_parse(0) == R2_PC_REJECTED && c_exports.reason == R2_PC_EXPORT_DIRECTORY);
    C_CHECK(c_exports.raw_reason == R2_PE_REASON_ZERO_FILL && c_exports.failure_offset == 0x3000);
    c_exports_fixture(0, 1, 1, 1); c_put(0, 0x1300, c_rva(0x1FFF), 4); c_files[0][0x1FFF] = 'X';
    C_CHECK(c_parse(0) == R2_PC_REJECTED && c_exports.reason == R2_PC_EXPORT_NAME);
    c_exports_fixture(0, 1, 1, 1); c_put(0, 0x1300, c_rva(0x1800), 4);
    for (i = 0; i < 512; ++i) c_files[0][0x1800 + i] = 'X';
    C_CHECK(c_parse(0) == R2_PC_PARTIAL && c_exports.reason == R2_PC_NAME_LIMIT);
    c_prepare(1); c_exports_fixture(0, 1, 1, 1); c_put(0, 0x61C, c_rva(0x1FFE), 4);
    C_CHECK(c_parse(0) == R2_PC_REJECTED && c_exports.raw_reason == R2_PE_REASON_SPAN_CROSSING);
    C_CHECK(c_exports.failure_offset == c_rva(0x1FFE));
    c_prepare(1); c_directory(0, 0, 0, 40);
    C_CHECK(c_parse(0) == R2_PC_REJECTED && c_exports.reason == R2_PC_EXPORT_DIRECTORY);
    c_prepare(1); c_put(0, 0x108, 0xFFFFFFF0u, 4); c_put(0, 0x10C, 64, 4);
    C_CHECK(c_parse(0) == R2_PC_REJECTED && c_exports.reason == R2_PC_EXPORT_DIRECTORY);
}
static unsigned char c_large[2][131072u];
static struct r2_pc_edge_v1 c_work_edge;
static struct r2_pc_abi_v1 c_abi;
static void c_large_put(uint32_t im, uint32_t off, uint64_t value, uint32_t n)
{
    uint32_t i;
    for (i = 0; i < n; ++i) c_large[im][off + i] = (unsigned char)(value >> (i * 8));
}
static void c_limits_cases(void)
{
    uint32_t i, j;
    char name[4] = { 'N', '0', '0', 0 };
    char target[10] = { 'a', 'l', 'p', 'h', 'a', '.', 'N', '0', '0', 0 };
    c_prepare(2); c_normal(0, "alpha", "N00", 0, 0); c_exports_fixture(1, 1, 33, 33);
    for (i = 0; i < 33; ++i) {
        name[1] = (char)('0' + i / 10); name[2] = (char)('0' + i % 10);
        c_name(1, i, name, i);
        if (i < 32) {
            target[7] = (char)('0' + (i + 1) / 10); target[8] = (char)('0' + (i + 1) % 10);
            c_forward(1, i, target);
        }
    }
    C_CHECK(c_bind() == R2_PC_PARTIAL && c_report.edges[0].reason == R2_PC_DEPTH_LIMIT);
    C_CHECK(c_report.edges[0].chain_count == R2_PC_DEPTH && c_report.edges[0].eat_index == 32);
    c_put(1, 0x1100 + 31 * 4, c_rva(0x1800), 4);
    C_CHECK(c_bind() == R2_PC_COMPLETE && c_report.edges[0].chain_count == 32);
    c_forward(1, 31, "alpha.N00");
    C_CHECK(c_bind() == R2_PC_PARTIAL && c_report.edges[0].reason == R2_PC_FORWARDER_CYCLE);
    C_CHECK(c_report.edges[0].chain_count == 32);
    /* Real production lookup helper at an exact exhausted boundary. The
     * workspace below was populated by the actual public reparse, not a
     * caller-supplied fake status accepted by a production entry point.
     */
    c_prepare(2); c_normal(0, "alpha", "Entry", 0, 0); c_exports_fixture(1, 1, 1, 1);
    C_CHECK(c_bind() == R2_PC_COMPLETE);
    memset(&c_work_edge, 0, sizeof(c_work_edge));
    c_work_edge.importer = 0; c_report.lookup_work = R2_PC_LOOKUP_WORK;
    r2_pc_bind_edge_v1(&c_input, &c_workspace.storage, &c_report, &c_work_edge,
        &c_workspace.storage.images[0].raw.descriptors[0], &c_workspace.storage.images[0].raw.symbols[0]);
    C_CHECK(c_work_edge.reason == R2_PC_LOOKUP_LIMIT && !c_work_edge.chain_count);
    C_CHECK(c_report.lookup_work == R2_PC_LOOKUP_WORK);
    c_report.lookup_work = R2_PC_LOOKUP_WORK - 1;
    C_CHECK(r2_pc_lookup_charge_v1(&c_report, 1) && c_report.lookup_work == R2_PC_LOOKUP_WORK);
    C_CHECK(!r2_pc_lookup_charge_v1(&c_report, 1) && c_report.lookup_work == R2_PC_LOOKUP_WORK);
    {
        struct r2_pe_context_v1 context;
        uint32_t offset, length;
        context.file = c_files[1]; context.length = C_BYTES; context.r = &c_workspace.storage.images[1].raw;
        context.r->work_units = R2_PE_RAW_WORK_LIMIT; context.r->reason = R2_PE_REASON_NONE;
        C_CHECK(!r2_pc_string_v1(&context, &c_exports, c_rva(0x1600), 0, &offset, &length));
        C_CHECK(context.r->reason == R2_PE_REASON_WORK_LIMIT && context.r->work_units == R2_PE_RAW_WORK_LIMIT);
        context.r->work_units = 0; context.r->reason = R2_PE_REASON_NONE;
        context.r->names_inspected_bytes = R2_PE_RAW_NAME_BYTES_LIMIT;
        C_CHECK(!r2_pc_string_v1(&context, &c_exports, c_rva(0x1600), 0, &offset, &length));
        C_CHECK(context.r->reason == R2_PE_REASON_NAME_BYTES_LIMIT);
        C_CHECK(context.r->names_inspected_bytes == R2_PE_RAW_NAME_BYTES_LIMIT);
    }
    /* Two actual FILE fixtures each have 4096 imports; the global 4096
     * output limit cannot silently discard the second image's imports.
     */
    c_prepare(2); c_normal(0, "alpha", NULL, 1, 0); c_normal(1, "root", NULL, 1, 0);
    c_exports_fixture(0, 1, 1, 1); c_exports_fixture(1, 1, 1, 1);
    for (i = 0; i < 2; ++i) {
        memset(c_large[i], 0, sizeof(c_large[i])); memcpy(c_large[i], c_files[i], C_BYTES);
        c_large_put(i, 0x190, 0x20000, 4); c_large_put(i, 0x198, 0x1FE00, 4);
        c_large_put(i, 0xD0, 0x21000, 4);
        c_large_put(i, 0x300, c_rva(0x2000), 4); c_large_put(i, 0x310, c_rva(0xC000), 4);
        for (j = 0; j < 4096; ++j) {
            c_large_put(i, 0x2000 + j * 8, UINT64_C(0x8000000000000001), 8);
            c_large_put(i, 0xC000 + j * 8, UINT64_C(0x8000000000000001), 8);
        }
        c_input.images[i].file = c_large[i]; c_input.images[i].file_bytes = sizeof(c_large[i]);
    }
    C_CHECK(c_bind() == R2_PC_PARTIAL && c_report.reason == R2_PC_EDGE_LIMIT);
    C_CHECK(c_report.edge_count == 4096 && c_report.bound_edges == 4096);
    C_CHECK(c_report.unrepresented_symbols == 4096 && c_report.images[1].unrepresented_symbols == 4096);
    C_CHECK(c_report.images[0].symbol_count == 4096 && c_report.images[1].symbol_count == 4096);
    C_CHECK(c_report.first_failure_image == 1 && c_report.first_failure_edge == R2_PC_NONE);
    /* 4097th actual thunk is retained as explicit original parser exhaustion;
     * its unknowable further count is not turned into a success-shaped zero.
     */
    c_input.image_count = 1; memset(&c_input.images[1], 0, sizeof(c_input.images[1]));
    c_large_put(0, 0x2000 + 4096 * 8, UINT64_C(0x8000000000000001), 8);
    c_large_put(0, 0xC000 + 4096 * 8, UINT64_C(0x8000000000000001), 8);
    C_CHECK(c_bind() == R2_PC_PARTIAL && c_report.images[0].base_reason == R2_PE_REASON_SYMBOL_LIMIT);
    C_CHECK(c_report.images[0].symbol_count == 4096 && !c_report.images[0].base_complete);
    C_CHECK(c_report.images[0].import_count_unknown && c_report.unknown_import_images == 1);
}
/* QUALITY P2 cumulative-string regression assertions FIRST, before repair.
 * All bytes below are invented. These assertions remain UNCOMPILED/UNRUN.
 * Separate bounded static storage permits the real common-prefix aliases and
 * repeated named-import counterexamples without project files or I/O.
 */
static unsigned char c_string_file[1048576u];
static void c_string_put(uint32_t off, uint64_t value, uint32_t n)
{
    uint32_t i;
    for (i = 0; i < n; ++i) c_string_file[off + i] = (unsigned char)(value >> (i * 8));
}
static void c_string_base(void)
{
    memset(c_string_file, 0, sizeof(c_string_file));
    memcpy(c_string_file, c_files[0], C_BYTES);
    c_string_put(0x190, 0x100000, 4); c_string_put(0x198, 0xFFE00, 4);
    c_string_put(0xD0, 0x101000, 4);
}
static void c_string_budget_cases(void)
{
    uint32_t i, j, result;
    int comparison = 77;
    struct r2_pe_context_v1 context;
    uint32_t offset, length;
    /* 2048 distinct, sorted aliases: 250 'A' + four decimal digits + NUL.
     * Initial scans alone fit; pairwise ordering rereads push over 1MiB.
     */
    c_prepare(1); c_exports_fixture(0, 1, 1, 2048); c_string_base();
    c_string_put(0x620, c_rva(0x2000), 4); c_string_put(0x624, c_rva(0x4000), 4);
    for (i = 0; i < 2048; ++i) {
        uint32_t at = 0x6000 + i * 256;
        c_string_put(0x2000 + i * 4, c_rva(at), 4); c_string_put(0x4000 + i * 2, 0, 2);
        for (j = 0; j < 250; ++j) c_string_file[at + j] = 'A';
        c_string_file[at + 250] = (unsigned char)('0' + i / 1000);
        c_string_file[at + 251] = (unsigned char)('0' + (i / 100) % 10);
        c_string_file[at + 252] = (unsigned char)('0' + (i / 10) % 10);
        c_string_file[at + 253] = (unsigned char)('0' + i % 10);
    }
    result = route2_pc_parse_exports_v1(c_string_file, sizeof(c_string_file), R2_PC_ABI,
        &c_exports, sizeof(c_exports), &c_workspace, sizeof(c_workspace));
    C_CHECK(result == R2_PC_PARTIAL && c_exports.reason == R2_PC_READ_LIMIT);
    C_CHECK(c_exports.raw_reason == R2_PE_REASON_NAME_BYTES_LIMIT && !c_exports.structural_complete);
    C_CHECK(c_exports.function_count == 1 && c_exports.name_count > 1 && c_exports.name_count < 2048);
    C_CHECK(c_workspace.storage.images[0].raw.names_inspected_bytes <= R2_PC_NAME_READ_BYTES);
    C_CHECK(c_exports.work_units < R2_PE_RAW_WORK_LIMIT && c_exports.preload_scope == R2_PC_UNPROVEN);
    /* Repeated long imports: old initial-name scans fit, later ASCII/provider
     * key/name comparisons must exhaust the IMPORTER's cumulative budget.
     */
    c_prepare(2); c_normal(0, "alpha", "Entry", 0, 0); c_exports_fixture(1, 1, 1, 1); c_string_base();
    c_string_put(0x300, c_rva(0x2000), 4); c_string_put(0x310, c_rva(0x7000), 4);
    for (j = 0; j < 254; ++j) { c_string_file[0xC002 + j] = 'A'; c_files[1][0x1600 + j] = 'A'; }
    c_files[1][0x1600 + 254] = 0;
    for (i = 0; i < 2048; ++i) {
        c_string_put(0x2000 + i * 8, c_rva(0xC000), 8);
        c_string_put(0x7000 + i * 8, c_rva(0xC000), 8);
    }
    c_input.images[0].file = c_string_file; c_input.images[0].file_bytes = sizeof(c_string_file);
    C_CHECK(c_bind() == R2_PC_PARTIAL && c_report.reason == R2_PC_STRING_LIMIT);
    C_CHECK(c_report.edge_count == 2048 && c_report.bound_edges > 0 && c_report.unresolved_edges > 0);
    C_CHECK(c_report.bound_edges + c_report.unresolved_edges == 2048 && !c_report.unrepresented_symbols);
    C_CHECK(c_report.first_failure_image == 0 && c_report.failed_images == 0 && !c_report.unknown_import_images);
    C_CHECK(c_report.edges[c_report.first_failure_edge].reason == R2_PC_STRING_LIMIT);
    C_CHECK(c_report.edges[c_report.first_failure_edge].failure_image == 0);
    C_CHECK(c_workspace.storage.images[0].raw.names_inspected_bytes <= R2_PC_NAME_READ_BYTES);
    C_CHECK(c_workspace.storage.images[1].raw.names_inspected_bytes < R2_PC_NAME_READ_BYTES);
    C_CHECK(c_report.preload_scope == R2_PC_UNPROVEN);
    /* Exact final byte is reserved; the next byte is refused before a read.
     * Helpers operate on workspace populated by the actual public parser.
     */
    c_prepare(2); c_normal(0, "alpha", "Entry", 0, 0); c_exports_fixture(1, 1, 1, 1);
    C_CHECK(c_bind() == R2_PC_COMPLETE);
    memset(&c_work_edge, 0, sizeof(c_work_edge));
    c_workspace.storage.images[0].raw.names_inspected_bytes = R2_PC_NAME_READ_BYTES - 1;
    C_CHECK(r2_pc_bind_string_charge_v1(&c_workspace.storage, &c_work_edge, 0, 1, 0x3E2));
    C_CHECK(c_workspace.storage.images[0].raw.names_inspected_bytes == R2_PC_NAME_READ_BYTES);
    C_CHECK(!r2_pc_bind_string_charge_v1(&c_workspace.storage, &c_work_edge, 0, 1, 0x3E3));
    C_CHECK(c_work_edge.failure_image == 0 && c_work_edge.failure_offset == 0x3E3);
    context.file = c_files[1]; context.length = C_BYTES; context.r = &c_workspace.storage.images[1].raw;
    context.r->reason = R2_PE_REASON_NONE; context.r->names_inspected_bytes = R2_PC_NAME_READ_BYTES - 1;
    C_CHECK(!r2_pc_string_v1(&context, &c_exports, c_rva(0x1600), 0, &offset, &length));
    C_CHECK(length == 1 && context.r->reason == R2_PE_REASON_NAME_BYTES_LIMIT);
    C_CHECK(context.r->names_inspected_bytes == R2_PC_NAME_READ_BYTES && context.r->failure_offset == 0x1601);
    /* BOTH original FILE operands are attributed separately. Reservations
     * are conservative and never refunded if the second operand refuses.
     */
    c_workspace.storage.images[0].raw.names_inspected_bytes = R2_PC_NAME_READ_BYTES;
    c_workspace.storage.images[1].raw.names_inspected_bytes = 0;
    C_CHECK(r2_pc_compare_file_v1(&c_input, &c_workspace.storage, &c_report, &c_work_edge,
        0, 0x3E2, 5, 1, 0x1600, 5, &comparison) == R2_PC_STRING_LIMIT);
    C_CHECK(c_work_edge.failure_image == 0 && c_work_edge.failure_offset == 0x3E2 && comparison == 77);
    c_workspace.storage.images[0].raw.names_inspected_bytes = 0;
    c_workspace.storage.images[1].raw.names_inspected_bytes = R2_PC_NAME_READ_BYTES;
    C_CHECK(r2_pc_compare_file_v1(&c_input, &c_workspace.storage, &c_report, &c_work_edge,
        0, 0x3E2, 5, 1, 0x1600, 5, &comparison) == R2_PC_STRING_LIMIT);
    C_CHECK(c_work_edge.failure_image == 1 && c_work_edge.failure_offset == 0x1600);
    C_CHECK(c_workspace.storage.images[0].raw.names_inspected_bytes == 1);
    c_workspace.storage.images[0].raw.names_inspected_bytes = R2_PC_NAME_READ_BYTES - 1;
    C_CHECK(r2_pc_compare_file_v1(&c_input, &c_workspace.storage, &c_report, &c_work_edge,
        0, 0x3E2, 5, 0, 0x3E2, 5, &comparison) == R2_PC_STRING_LIMIT);
    C_CHECK(c_work_edge.failure_image == 0 && c_work_edge.failure_offset == 0x3E2);
    C_CHECK(c_workspace.storage.images[0].raw.names_inspected_bytes == R2_PC_NAME_READ_BYTES);
    /* Forwarded-name operand belongs to the FORWARDING image, not importer
     * or selected target. 5 export-name bytes + 5 split bytes + '#' check1
     * + conservative beta-key reservation32 consume the available43 bytes.
     */
    c_prepare(3); c_normal(0, "alpha", "Entry", 0, 0);
    c_exports_fixture(1, 1, 1, 1); c_forward(1, 0, "beta.Entry"); c_exports_fixture(2, 1, 1, 1);
    C_CHECK(c_bind() == R2_PC_COMPLETE);
    c_workspace.storage.images[0].raw.names_inspected_bytes = 0;
    c_workspace.storage.images[1].raw.names_inspected_bytes = R2_PC_NAME_READ_BYTES - 43;
    c_workspace.storage.images[2].raw.names_inspected_bytes = 0;
    memset(&c_work_edge, 0, sizeof(c_work_edge)); c_work_edge.importer = 0;
    r2_pc_bind_edge_v1(&c_input, &c_workspace.storage, &c_report, &c_work_edge,
        &c_workspace.storage.images[0].raw.descriptors[0], &c_workspace.storage.images[0].raw.symbols[0]);
    C_CHECK(c_work_edge.reason == R2_PC_STRING_LIMIT && c_work_edge.chain_count == 1);
    C_CHECK(c_work_edge.failure_image == 1 && c_work_edge.failure_offset == 0x905);
    C_CHECK(c_workspace.storage.images[1].raw.names_inspected_bytes == R2_PC_NAME_READ_BYTES);
    /* Grammar rereads, conservative FILE key parsing, and ordinal digits
     * also reject their next byte/reservation before touching FILE bytes.
     */
    context.file = c_files[1]; context.length = C_BYTES; context.r = &c_workspace.storage.images[1].raw;
    context.r->reason = R2_PE_REASON_NONE; context.r->names_inspected_bytes = R2_PC_NAME_READ_BYTES - 1;
    C_CHECK(r2_pc_forward_grammar_v1(&context, 0x900, 10) == R2_PC_READ_LIMIT);
    C_CHECK(context.r->reason == R2_PE_REASON_NAME_BYTES_LIMIT && context.r->failure_offset == 0x901);
    context.r->reason = R2_PE_REASON_NONE; context.r->names_inspected_bytes = R2_PC_NAME_READ_BYTES - 10;
    C_CHECK(r2_pc_forward_grammar_v1(&context, 0x900, 10) == R2_PC_READ_LIMIT);
    C_CHECK(context.r->reason == R2_PE_REASON_NAME_BYTES_LIMIT && context.r->failure_offset == 0x900);
    c_forward(1, 0, "beta.#9");
    context.r->reason = R2_PE_REASON_NONE; context.r->names_inspected_bytes = R2_PC_NAME_READ_BYTES - 31;
    C_CHECK(r2_pc_forward_grammar_v1(&context, 0x900, 7) == R2_PC_READ_LIMIT);
    C_CHECK(context.r->reason == R2_PE_REASON_NAME_BYTES_LIMIT && context.r->failure_offset == 0x906);
}
static void c_sentinels(void)
{
    memset(&c_report, 0xA5, sizeof(c_report)); memset(&c_workspace, 0x5A, sizeof(c_workspace));
    memset(&c_exports, 0x3C, sizeof(c_exports));
}
static void c_unchanged(void)
{
    uint32_t i;
    const unsigned char *report = (const unsigned char *)&c_report;
    const unsigned char *ws = (const unsigned char *)&c_workspace;
    const unsigned char *exports = (const unsigned char *)&c_exports;
    for (i = 0; i < sizeof(c_report); ++i) C_CHECK(report[i] == 0xA5);
    for (i = 0; i < sizeof(c_workspace); ++i) C_CHECK(ws[i] == 0x5A);
    for (i = 0; i < sizeof(c_exports); ++i) C_CHECK(exports[i] == 0x3C);
}
static void c_argument_cases(void)
{
    uint32_t result;
    c_prepare(1); c_sentinels();
    C_CHECK(route2_pc_describe_v1(&c_abi, sizeof(c_abi)) == R2_PC_COMPLETE);
    C_CHECK(c_abi.abi == R2_PC_ABI && c_abi.report_bytes == sizeof(c_report));
    C_CHECK(c_abi.workspace_bytes == sizeof(c_workspace) && c_abi.exports_bytes == sizeof(c_exports));
    C_CHECK(c_abi.alignment == 8 && c_abi.depth == 32 && c_abi.read_work == R2_PC_READ_WORK);
    C_CHECK(c_abi.name_read_bytes == R2_PE_RAW_NAME_BYTES_LIMIT);
    C_CHECK(route2_pc_bind_catalog_v1(&c_input, sizeof(c_input) - 1, &c_report,
        sizeof(c_report), &c_workspace, sizeof(c_workspace)) == R2_PC_BAD_ARGUMENT);
    c_unchanged();
    c_input.abi = 2;
    C_CHECK(route2_pc_bind_catalog_v1(&c_input, sizeof(c_input), &c_report,
        sizeof(c_report), &c_workspace, sizeof(c_workspace)) == R2_PC_BAD_ARGUMENT);
    c_input.abi = R2_PC_ABI; c_unchanged();
    C_CHECK(route2_pc_bind_catalog_v1(&c_input, sizeof(c_input), &c_report,
        sizeof(c_report) - 1, &c_workspace, sizeof(c_workspace)) == R2_PC_BAD_ARGUMENT);
    C_CHECK(route2_pc_bind_catalog_v1(&c_input, sizeof(c_input), &c_report,
        sizeof(c_report), &c_workspace, sizeof(c_workspace) - 1) == R2_PC_BAD_ARGUMENT);
    c_unchanged();
    C_CHECK(route2_pc_bind_catalog_v1(&c_input, sizeof(c_input),
        (struct r2_pc_report_v1 *)((unsigned char *)&c_report + 1), sizeof(c_report),
        &c_workspace, sizeof(c_workspace)) == R2_PC_BAD_ARGUMENT);
    C_CHECK(route2_pc_bind_catalog_v1((const struct r2_pc_input_v1 *)((const unsigned char *)&c_input + 1),
        sizeof(c_input), &c_report, sizeof(c_report), &c_workspace, sizeof(c_workspace)) == R2_PC_BAD_ARGUMENT);
    c_unchanged();
    C_CHECK(route2_pc_parse_exports_v1(c_files[0], C_BYTES, 2, &c_exports, sizeof(c_exports),
        &c_workspace, sizeof(c_workspace)) == R2_PC_BAD_ARGUMENT);
    C_CHECK(route2_pc_parse_exports_v1(c_files[0], C_BYTES, R2_PC_ABI, &c_exports, sizeof(c_exports),
        (struct r2_pc_workspace_v1 *)((unsigned char *)&c_workspace + 1), sizeof(c_workspace)) == R2_PC_BAD_ARGUMENT);
    c_unchanged();
    C_CHECK(route2_pc_parse_exports_v1((const unsigned char *)(uintptr_t)(UINTPTR_MAX - 7u), 16,
        R2_PC_ABI, &c_exports, sizeof(c_exports), &c_workspace, sizeof(c_workspace)) == R2_PC_BAD_ARGUMENT);
    c_input.images[0].file = (const unsigned char *)(uintptr_t)(UINTPTR_MAX - 7u);
    c_input.images[0].file_bytes = 16;
    C_CHECK(route2_pc_bind_catalog_v1(&c_input, sizeof(c_input), &c_report,
        sizeof(c_report), &c_workspace, sizeof(c_workspace)) == R2_PC_BAD_ARGUMENT);
    c_unchanged();
    c_prepare(1); c_input.images[0].file = (const unsigned char *)&c_report;
    C_CHECK(route2_pc_bind_catalog_v1(&c_input, sizeof(c_input), &c_report,
        sizeof(c_report), &c_workspace, sizeof(c_workspace)) == R2_PC_ALIAS);
    c_input.images[0].file = (const unsigned char *)&c_workspace;
    C_CHECK(route2_pc_bind_catalog_v1(&c_input, sizeof(c_input), &c_report,
        sizeof(c_report), &c_workspace, sizeof(c_workspace)) == R2_PC_ALIAS);
    c_input.images[0].file = (const unsigned char *)&c_input; c_input.images[0].file_bytes = sizeof(c_input);
    C_CHECK(route2_pc_bind_catalog_v1(&c_input, sizeof(c_input), &c_report,
        sizeof(c_report), &c_workspace, sizeof(c_workspace)) == R2_PC_ALIAS);
    c_unchanged();
    C_CHECK(route2_pc_parse_exports_v1((const unsigned char *)&c_exports, sizeof(c_exports),
        R2_PC_ABI, &c_exports, sizeof(c_exports), &c_workspace, sizeof(c_workspace)) == R2_PC_ALIAS);
    C_CHECK(route2_pc_parse_exports_v1(c_files[0], C_BYTES, R2_PC_ABI,
        (struct r2_pc_exports_v1 *)&c_workspace, sizeof(c_exports), &c_workspace, sizeof(c_workspace)) == R2_PC_ALIAS);
    c_unchanged();
    c_prepare(1);
    C_CHECK(route2_pc_bind_catalog_v1(&c_input, sizeof(c_input),
        (struct r2_pc_report_v1 *)&c_workspace, sizeof(c_report),
        &c_workspace, sizeof(c_workspace)) == R2_PC_ALIAS);
    C_CHECK(route2_pc_bind_catalog_v1((const struct r2_pc_input_v1 *)&c_workspace, sizeof(c_input),
        &c_report, sizeof(c_report), &c_workspace, sizeof(c_workspace)) == R2_PC_ALIAS);
    c_unchanged();
    c_prepare(2); c_input.images[1].file = c_input.images[0].file;
    C_CHECK(route2_pc_bind_catalog_v1(&c_input, sizeof(c_input), &c_report,
        sizeof(c_report), &c_workspace, sizeof(c_workspace)) == R2_PC_ALIAS);
    c_unchanged();
    c_prepare(1); c_input.images[0].file_bytes = R2_PC_FILE_BYTES + 1u;
    C_CHECK(route2_pc_bind_catalog_v1(&c_input, sizeof(c_input), &c_report,
        sizeof(c_report), &c_workspace, sizeof(c_workspace)) == R2_PC_FILE_LIMIT);
    c_unchanged();
    c_prepare(1); c_input.image_count = R2_PC_IMAGES + 1;
    C_CHECK(route2_pc_bind_catalog_v1(&c_input, sizeof(c_input), &c_report,
        sizeof(c_report), &c_workspace, sizeof(c_workspace)) == R2_PC_IMAGE_LIMIT);
    c_unchanged();
    c_prepare(1); c_input.flags = 1;
    C_CHECK(route2_pc_bind_catalog_v1(&c_input, sizeof(c_input), &c_report,
        sizeof(c_report), &c_workspace, sizeof(c_workspace)) == R2_PC_BAD_ARGUMENT);
    c_input.flags = 0; c_input.images[15].reserved = 1;
    result = route2_pc_bind_catalog_v1(&c_input, sizeof(c_input), &c_report,
        sizeof(c_report), &c_workspace, sizeof(c_workspace));
    C_CHECK(result == R2_PC_BAD_ARGUMENT); c_unchanged();
}
int main(void)
{
    c_good_cases(); c_forward_cases(); c_catalog_cases(); c_export_bad_cases();
    c_limits_cases(); c_string_budget_cases(); c_argument_cases();
    return c_failures ? 1 : 0;
}
