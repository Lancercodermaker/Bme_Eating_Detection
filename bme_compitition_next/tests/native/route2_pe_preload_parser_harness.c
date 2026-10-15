/* C03-B1 SOURCE-ONLY assertion harness. NEVER compiled or run in this window.
 * Includes the actual production translation unit, so boundary checks below
 * exercise its real private budget helper, not a copied parser/model. This
 * also contains the preexisting Windows components; none is called here.
 * Future native execution/build requires its own authorization and accounting.
 * Fixtures are invented FILE bytes; no disk/OS/loader/provider/native probes,
 * imports, callbacks, heap allocation, project input, GT or proof issuer.
 * Assertion return only, no output record / application PASS / receipt.
 */
#if !defined(R2_TARGET_WINDOWS_SEED)
#error "Explicit Windows seed target required"
#endif
#include "../../src/eating_event/route2_candidate_overlap/native/route2_mount_helper.c"

#define P_FIXTURE_BYTES 147456u
static unsigned char p_file[P_FIXTURE_BYTES];
/* Source fixture storage only; no runtime RAM/startup grant is implied. */
static unsigned char p_oversize[R2_PE_RAW_FILE_LIMIT + 1u];
static struct r2_pe_raw_report_v1 p_report;
static unsigned char p_saved[R2_PE_RAW_REPORT_BYTES];
static uint32_t p_failures;
#define P_CHECK(e) do { if (!(e)) ++p_failures; } while (0)

static void p_put(uint32_t off, uint64_t value, uint32_t n)
{
    uint32_t i;
    for (i = 0; i < n; ++i) p_file[off + i] = (unsigned char)(value >> (i * 8));
}
static void p_text(uint32_t off, const char *s)
{
    do { p_file[off++] = (unsigned char)*s; } while (*s++);
}
static uint32_t p_rva(uint32_t off) { return off + 0xE00u; }
static void p_dir(uint32_t index, uint32_t off, uint32_t size)
{
    p_put(0x108u + index * 8u, off ? p_rva(off) : 0, 4);
    p_put(0x10Cu + index * 8u, size, 4);
}
static void p_base(uint32_t bytes)
{
    uint32_t i, raw = bytes - 0x200u;
    for (i = 0; i < P_FIXTURE_BYTES; ++i) p_file[i] = 0;
    p_put(0, 0x5A4D, 2); p_put(0x3C, 0x80, 4);
    p_put(0x80, 0x4550, 4); p_put(0x84, 0x8664, 2);
    p_put(0x86, 1, 2); p_put(0x94, 240, 2); p_put(0x96, 0x22, 2);
    p_put(0x98, 0x20B, 2); p_put(0xA8, 0x1010, 4);
    p_put(0xB0, UINT64_C(0x140000000), 8);
    p_put(0xB8, 0x1000, 4); p_put(0xBC, 0x200, 4);
    p_put(0xD0, (0x1000u + raw + 0xFFFu) & ~0xFFFu, 4);
    p_put(0xD4, 0x200, 4); p_put(0x104, 16, 4);
    p_text(0x188, ".facts");
    p_put(0x190, raw, 4); p_put(0x194, 0x1000, 4);
    p_put(0x198, raw, 4); p_put(0x19C, 0x200, 4);
    p_put(0x1AC, 0xC0000040, 4);
}
static void p_normal(void)
{
    p_dir(1, 0x300, 40);
    p_put(0x300, p_rva(0x400), 4);
    p_put(0x30C, p_rva(0x380), 4); p_put(0x310, p_rva(0x440), 4);
    p_text(0x380, "alpha.dll");
    p_put(0x400, p_rva(0x500), 8);
    p_put(0x408, UINT64_C(0x8000000000000007), 8);
    p_put(0x440, p_rva(0x500), 8);
    p_put(0x448, UINT64_C(0x8000000000000007), 8);
    p_put(0x500, 42, 2); p_text(0x502, "Symbol");
}
static void p_delay(void)
{
    p_dir(13, 0x600, 64);
    p_put(0x600, 1, 4); p_put(0x604, p_rva(0x680), 4);
    p_put(0x608, p_rva(0x6A0), 4); p_put(0x60C, p_rva(0x740), 4);
    p_put(0x610, p_rva(0x700), 4); p_put(0x614, p_rva(0x780), 4);
    p_put(0x618, p_rva(0x7C0), 4); p_text(0x680, "beta.dll");
    p_put(0x700, UINT64_C(0x8000000000000009), 8);
    p_put(0x740, UINT64_C(0x140001010), 8);
    p_put(0x780, UINT64_C(0x180001234), 8);
    p_put(0x7C0, UINT64_C(0x140001010), 8);
}
static void p_tls(uint32_t nonempty)
{
    const uint64_t base = UINT64_C(0x140000000);
    p_dir(9, 0x800, 40);
    p_put(0x800, base + p_rva(0x900), 8);
    p_put(0x808, base + p_rva(0x908), 8);
    p_put(0x810, base + p_rva(0x930), 8);
    p_put(0x818, base + p_rva(0x940), 8);
    p_put(0x820, 12, 4);
    if (nonempty) p_put(0x940, base + 0x1010, 8);
}
static uint32_t p_parse(uint32_t bytes)
{
    uint32_t result = route2_pe_preload_parse_raw_v1(p_file, bytes,
        R2_PE_RAW_ABI, &p_report, sizeof(p_report));
    P_CHECK(result == p_report.raw_status);
    P_CHECK(p_report.abi == 1 && p_report.size == R2_PE_RAW_REPORT_BYTES);
    P_CHECK(p_report.preload_scope == R2_PE_PRELOAD_CLOSURE_UNPROVEN);
    P_CHECK(p_report.work_units <= R2_PE_RAW_WORK_LIMIT);
    P_CHECK(p_report.names_inspected_bytes <= R2_PE_RAW_NAME_BYTES_LIMIT);
    P_CHECK(p_report.descriptor_count <= 128 && p_report.symbol_count <= 4096);
    P_CHECK(p_report.tls.callback_count <= 64);
    if (result == R2_PE_RAW_INCOMPLETE || result == R2_PE_RAW_REJECTED)
        P_CHECK(!p_report.structural_complete && p_report.reason != R2_PE_REASON_NONE);
    return result;
}
static void p_good_cases(void)
{
    p_base(0xA00);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_COMPLETE);
    P_CHECK(p_report.structural_complete && p_report.section_count == 1);
    P_CHECK(!p_report.descriptor_count && !p_report.symbol_count && !p_report.tls.present);
    p_normal(); p_delay();
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_COMPLETE);
    P_CHECK(p_report.normal_count == 1 && p_report.delay_count == 1 && p_report.symbol_count == 3);
    P_CHECK(p_report.descriptors[0].dll_name.file_offset == 0x380);
    P_CHECK(p_report.descriptors[0].dll_name.length == 9);
    P_CHECK(p_report.descriptors[0].valid_fields == 7 && p_report.descriptors[0].symbol_count == 2);
    P_CHECK(p_report.symbols[0].kind == R2_PE_SYMBOL_NAME && p_report.symbols[0].hint == 42);
    P_CHECK(p_report.symbols[0].name_offset == 0x502 && p_report.symbols[0].name_length == 6);
    P_CHECK(p_report.symbols[1].kind == R2_PE_SYMBOL_ORDINAL && p_report.symbols[1].ordinal == 7);
    P_CHECK(p_report.symbols[2].descriptor_index == 1 && p_report.symbols[2].ordinal == 9);
    P_CHECK(p_report.symbols[2].raw_iat == UINT64_C(0x140001010));
    P_CHECK(p_report.descriptors[1].bound_rva == p_rva(0x780));
    p_tls(0);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_COMPLETE);
    P_CHECK(p_report.tls.present && p_report.tls.fields_valid && !p_report.tls.callback_count);
    P_CHECK(p_report.tls.template_offset == 0x900 && p_report.tls.template_bytes == 8);
    P_CHECK(p_report.tls.index_offset == 0x930 && p_report.tls.callbacks_terminated);
    p_put(0x940, UINT64_C(0x140001010), 8);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_APPLICATION_TLS_PRESENT);
    P_CHECK(p_report.structural_complete && p_report.reason == R2_PE_REASON_APPLICATION_TLS_PRESENT);
    P_CHECK(p_report.tls.callback_count == 1 && p_report.callbacks[0].target_offset == 0x210);
    P_CHECK(p_report.callbacks[0].pointer_offset == 0x940);
    /* TLS index is four bytes: its last valid placement ends exactly at EOF. */
    p_put(0x810, UINT64_C(0x140000000) + p_rva(0x9FC), 8);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_APPLICATION_TLS_PRESENT);
    P_CHECK(p_report.tls.index_offset == 0x9FC);
    p_put(0x818, 0, 8);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_COMPLETE);
    P_CHECK(!p_report.tls.callbacks_va && !p_report.tls.callbacks_terminated);
    /* Empty raw template uses equal endpoints; it is not a one-byte span. */
    p_put(0x800, UINT64_C(0x140002000), 8);
    p_put(0x808, UINT64_C(0x140002000), 8);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_COMPLETE && !p_report.tls.template_bytes);
}
static void p_header_cases(void)
{
    uint32_t cut;
    p_base(0xA00);
    for (cut = 0; cut < 0x1B0; ++cut) {
        P_CHECK(p_parse(cut) == R2_PE_RAW_REJECTED);
        P_CHECK(!p_report.structural_complete);
    }
    p_file[0] = 0;
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_DOS);
    p_base(0xA00); p_put(0x80, 0, 4);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_PE_SIGNATURE);
    p_base(0xA00); p_put(0x84, 0x14C, 2);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_MACHINE);
    p_base(0xA00); p_put(0x98, 0x10B, 2);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_OPTIONAL_HEADER);
    p_base(0xA00); p_put(0x104, 17, 4);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_OPTIONAL_HEADER);
    p_base(0xA00); p_put(0x86, 97, 2);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_INCOMPLETE && p_report.reason == R2_PE_REASON_SECTION_LIMIT);
    p_base(0xA00); p_put(0x194, 0xFFFFF000, 4); p_put(0x190, 0x2000, 4);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_SECTION_RANGE);
    p_base(0xA00); p_put(0x19C, 0xFFFFFF00, 4);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_SECTION_RANGE);
    p_base(0xA00); p_put(0x19C, 0, 4);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_HEADER_OVERLAP);
    /* Two section headers fit the declared headers; overlapping FILE ranges
     * are rejected even with disjoint RVAs. Then test disjoint raw/same RVA. */
    p_base(0x1000); p_put(0x86, 2, 2); p_put(0xD0, 0x4000, 4);
    p_put(0x190, 0x400, 4); p_put(0x198, 0x400, 4);
    p_put(0x1B8, 0x400, 4); p_put(0x1BC, 0x2000, 4);
    p_put(0x1C0, 0x400, 4); p_put(0x1C4, 0x400, 4);
    P_CHECK(p_parse(0x1000) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_SECTION_OVERLAP);
    p_put(0x1C4, 0x800, 4); p_put(0x1BC, 0x1000, 4);
    P_CHECK(p_parse(0x1000) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_SECTION_OVERLAP);
    p_base(0xA00); p_put(0xBC, 0x300, 4);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_ALIGNMENT);
}
static void p_import_bad_cases(void)
{
    p_base(0xA00); p_normal(); p_put(0x300, 0, 4);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_LOOKUP_ABSENT);
    P_CHECK(p_report.descriptor_count == 1 && !p_report.symbol_count);
    p_base(0xA00); p_normal(); p_put(0x304, 1, 4);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_BOUND_UNSUPPORTED);
    p_base(0xA00); p_dir(11, 0x800, 8);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_BOUND_UNSUPPORTED);
    p_base(0xA00); p_normal(); p_put(0x114, 20, 4);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_DESCRIPTOR_TERMINATOR);
    P_CHECK(p_report.symbol_count == 2 && p_report.descriptors[0].lookup_terminated);
    p_base(0xA00); p_normal(); p_put(0x300, p_rva(0x9F8), 4);
    p_put(0x9F8, UINT64_C(0x8000000000000001), 8);
    p_put(0x440, UINT64_C(0x8000000000000001), 8);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_THUNK_TERMINATOR);
    p_base(0xA00); p_normal(); p_put(0x450, 1, 8);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_IAT_TERMINATOR);
    p_base(0xA00); p_normal(); p_put(0x408, UINT64_C(0x8000000000010007), 8);
    p_put(0x448, UINT64_C(0x8000000000010007), 8);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_ORDINAL_BITS);
    P_CHECK(p_report.symbol_count == 2 && p_report.symbols[0].kind == R2_PE_SYMBOL_NAME);
    p_base(0xA00); p_normal(); p_put(0x400, UINT64_C(0x100000001), 8);
    p_put(0x440, UINT64_C(0x100000001), 8);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_NAME_RVA_BITS);
    p_base(0xA00); p_normal(); p_put(0x190, 0x1800, 4);
    p_put(0xD0, 0x3000, 4); p_put(0x30C, 0x2000, 4);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_ZERO_FILL);
    p_base(0xA00); p_dir(1, 0x9F8, 40);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_SPAN_CROSSING);
    p_base(0xA00); p_normal(); p_put(0x30C, p_rva(0x9FE), 4);
    p_file[0x9FE] = 'a'; p_file[0x9FF] = 'b';
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_NAME_TERMINATOR);
    p_base(0xA00); p_delay(); p_put(0x600, 0, 4);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_DELAY_LEGACY_VA);
    p_put(0x600, 3, 4);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_DELAY_ATTRIBUTES);
    p_base(0xA00); p_delay(); p_put(0x610, 0, 4);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_LOOKUP_ABSENT);
    p_base(0xA00); p_delay(); p_put(0x608, p_rva(0x9FC), 4);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_SPAN_CROSSING);
    p_base(0xA00); p_delay(); p_put(0x614, p_rva(0x9F8), 4);
    p_put(0x9F8, UINT64_C(0x180001234), 8);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_BOUND_TERMINATOR);
    p_base(0xA00); p_delay(); p_put(0x174, 32, 4);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_DESCRIPTOR_TERMINATOR);
}
static void p_tls_bad_cases(void)
{
    uint32_t i;
    p_base(0xA00); p_tls(0); p_put(0x810, p_rva(0x930), 8);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_TLS_VA);
    P_CHECK(p_report.tls.fields_valid && p_report.tls.index_va == p_rva(0x930));
    p_base(0xA00); p_tls(0); p_put(0x808, UINT64_C(0x1400016FF), 8);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_TLS_TEMPLATE);
    p_base(0xA00); p_tls(0); p_put(0x800, UINT64_C(0x1400017FC), 8);
    p_put(0x808, UINT64_C(0x140001804), 8);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_SPAN_CROSSING);
    p_base(0xA00); p_tls(0); p_put(0x818, UINT64_C(0x140000000) + p_rva(0x9F8), 8);
    p_put(0x9F8, UINT64_C(0x140001010), 8);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_TLS_TERMINATOR);
    P_CHECK(p_report.tls.callback_count == 1 && !p_report.tls.callbacks_terminated);
    p_base(0xA00); p_tls(1); p_put(0x940, 0x1010, 8);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_TLS_VA);
    P_CHECK(p_report.callbacks[0].raw_va == 0x1010 && p_report.tls.callback_count == 1);
    p_base(0x2000); p_tls(0); p_put(0x818, UINT64_C(0x140000000) + p_rva(0x1000), 8);
    for (i = 0; i < 64; ++i) p_put(0x1000 + i * 8, UINT64_C(0x140001010), 8);
    P_CHECK(p_parse(0x2000) == R2_PE_RAW_APPLICATION_TLS_PRESENT);
    P_CHECK(p_report.tls.callback_count == 64 && p_report.tls.callbacks_terminated);
    p_put(0x1200, UINT64_C(0x140001010), 8);
    P_CHECK(p_parse(0x2000) == R2_PE_RAW_INCOMPLETE && p_report.reason == R2_PE_REASON_TLS_CALLBACK_LIMIT);
    P_CHECK(p_report.tls.callback_count == 64 && !p_report.tls.callbacks_terminated);
}
static void p_limit_cases(void)
{
    uint32_t i;
    p_base(0xA00); p_normal(); p_put(0x30C, p_rva(0x800), 4);
    for (i = 0; i < 511; ++i) p_file[0x800 + i] = 'n';
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_COMPLETE);
    P_CHECK(p_report.descriptors[0].dll_name.length == 511);
    p_file[0x9FF] = 'x';
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_INCOMPLETE && p_report.reason == R2_PE_REASON_NAME_LIMIT);
    /* A genuine disjoint 64MiB+1 storage fixture is refused before reads.
     * This source declaration is not runtime RAM/accounting evidence.
     */
    P_CHECK(route2_pe_preload_parse_raw_v1(p_oversize, sizeof(p_oversize),
        R2_PE_RAW_ABI, &p_report, sizeof(p_report)) == R2_PE_RAW_INCOMPLETE);
    P_CHECK(p_report.reason == R2_PE_REASON_FILE_LIMIT && !p_report.work_units);
    /* Exactly 4096 ordinal symbols plus zero is supported; the next nonzero
     * is a named incomplete result with all previous raw facts retained. */
    p_base(P_FIXTURE_BYTES); p_normal();
    p_put(0x300, p_rva(0x1000), 4); p_put(0x310, p_rva(0x10000), 4);
    for (i = 0; i < 4096; ++i) {
        p_put(0x1000 + i * 8, UINT64_C(0x8000000000000001), 8);
        p_put(0x10000 + i * 8, UINT64_C(0x8000000000000001), 8);
    }
    P_CHECK(p_parse(P_FIXTURE_BYTES) == R2_PE_RAW_COMPLETE);
    P_CHECK(p_report.symbol_count == 4096 && p_report.descriptors[0].lookup_terminated);
    p_put(0x9000, UINT64_C(0x8000000000000001), 8);
    p_put(0x18000, UINT64_C(0x8000000000000001), 8);
    P_CHECK(p_parse(P_FIXTURE_BYTES) == R2_PE_RAW_INCOMPLETE && p_report.reason == R2_PE_REASON_SYMBOL_LIMIT);
    /* Distinct thunk references may repeat the same 512-byte name; each scan
     * still consumes aggregate name work. This catches alias-based bypasses. */
    p_put(0x9000, 0, 8); p_put(0x18000, 0, 8);
    p_put(0x22000, 2, 2);
    for (i = 0; i < 511; ++i) p_file[0x22002 + i] = 's';
    for (i = 0; i < 4096; ++i) {
        p_put(0x1000 + i * 8, p_rva(0x22000), 8);
        p_put(0x10000 + i * 8, p_rva(0x22000), 8);
    }
    P_CHECK(p_parse(P_FIXTURE_BYTES) == R2_PE_RAW_INCOMPLETE && p_report.reason == R2_PE_REASON_NAME_BYTES_LIMIT);
    P_CHECK(p_report.names_inspected_bytes == R2_PE_RAW_NAME_BYTES_LIMIT && p_report.symbol_count < 4096);
    /* Shared descriptor limit: 64 normal + 64 delay is supported. */
    p_base(0x8000); p_text(0x7000, "d.dll");
    p_dir(1, 0x300, 65 * 20); p_dir(13, 0x1000, 65 * 32);
    for (i = 0; i < 64; ++i) {
        p_put(0x300 + i * 20, p_rva(0x6000), 4);
        p_put(0x30C + i * 20, p_rva(0x7000), 4);
        p_put(0x310 + i * 20, p_rva(0x6100), 4);
        p_put(0x1000 + i * 32, 1, 4);
        p_put(0x1004 + i * 32, p_rva(0x7000), 4);
        p_put(0x1008 + i * 32, p_rva(0x6200), 4);
        p_put(0x100C + i * 32, p_rva(0x6100), 4);
        p_put(0x1010 + i * 32, p_rva(0x6000), 4);
    }
    P_CHECK(p_parse(0x8000) == R2_PE_RAW_COMPLETE && p_report.descriptor_count == 128);
    p_put(0x1000 + 64 * 32, 1, 4); p_dir(13, 0x1000, 66 * 32);
    P_CHECK(p_parse(0x8000) == R2_PE_RAW_INCOMPLETE && p_report.reason == R2_PE_REASON_DESCRIPTOR_LIMIT);
    P_CHECK(p_report.descriptor_count == 128 && p_report.normal_count == 64 && p_report.delay_count == 64);
}
/* SPEC review regressions: observable fixture relationships, no mirror parser. */
static void p_review_regressions(void)
{
    uint64_t with_aux_work;
    p_base(0xA00); p_normal(); p_put(0x440, 0, 8);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED);
    P_CHECK(p_report.reason == R2_PE_REASON_IAT_TERMINATOR && p_report.failure_offset == 0x440);
    P_CHECK(!p_report.structural_complete && p_report.symbol_count == 1);
    P_CHECK(p_report.symbols[0].raw_lookup == p_rva(0x500) && !p_report.symbols[0].raw_iat);
    p_base(0xA00); p_normal(); p_put(0x448, 0, 8);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_IAT_TERMINATOR);
    P_CHECK(p_report.symbol_count == 2 && p_report.symbols[0].kind == R2_PE_SYMBOL_NAME);
    p_base(0xA00); p_normal(); p_put(0x440, UINT64_C(0x180001234), 8);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_IAT_CONTENT);
    P_CHECK(p_report.symbols[0].raw_iat == UINT64_C(0x180001234) && !p_report.structural_complete);
    /* A mismatched normal IAT cannot be legalized by bound metadata. */
    p_put(0x304, 1, 4);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_BOUND_UNSUPPORTED);
    P_CHECK(!p_report.symbol_count);
    /* Delay IAT stub VAs intentionally differ from ordinal lookup data. */
    p_base(0xA00); p_delay();
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_COMPLETE);
    P_CHECK(p_report.symbols[0].raw_iat == UINT64_C(0x140001010));
    P_CHECK(p_report.symbols[0].raw_iat != p_report.symbols[0].raw_lookup);
    p_put(0x740, 0, 8);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_IAT_TERMINATOR);
    p_base(0xA00); p_delay(); p_put(0x788, 1, 8);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_BOUND_TERMINATOR);
    P_CHECK(p_report.failure_offset == 0x788 && p_report.descriptors[0].lookup_terminated);
    p_base(0xA00); p_delay(); p_put(0x780, 0, 8);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_BOUND_TERMINATOR);
    p_base(0xA00); p_delay(); p_put(0x7C8, 1, 8);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_UNLOAD_CONTENT);
    P_CHECK(p_report.failure_offset == 0x7C8 && p_report.descriptors[0].lookup_terminated);
    p_base(0xA00); p_delay(); p_put(0x7C0, UINT64_C(0x140001020), 8);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_UNLOAD_CONTENT);
    /* UIAT is optional; BIAT is independently optional. Each present table
     * inspects its entry plus terminator: at least 32 extra charged bytes. */
    p_base(0xA00); p_delay();
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_COMPLETE);
    with_aux_work = p_report.work_units;
    p_put(0x614, 0, 4); p_put(0x618, 0, 4);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_COMPLETE);
    P_CHECK(with_aux_work >= p_report.work_units + 32);
    p_base(0xA00); p_delay(); p_put(0x608, 0, 4);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_DELAY_HANDLE);
    P_CHECK(p_report.failure_offset == 0x608 && !p_report.symbol_count);
    /* Genuine low-alignment image: backed data FILE offset equals RVA. */
    p_base(0xA00); p_normal();
    p_put(0xB8, 0x200, 4); p_put(0xBC, 0x200, 4);
    p_put(0xD0, 0xA00, 4); p_put(0xA8, 0x210, 4); p_put(0x194, 0x200, 4);
    p_put(0x110, 0x300, 4); p_put(0x300, 0x400, 4);
    p_put(0x30C, 0x380, 4); p_put(0x310, 0x440, 4);
    p_put(0x400, 0x500, 8); p_put(0x440, 0x500, 8);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_COMPLETE);
    P_CHECK(p_report.symbols[0].name_offset == 0x502 && p_report.symbols[1].ordinal == 7);
    /* Bounds and alignment still fit, but the low-alignment FILE/RVA rule fails. */
    p_put(0x19C, 0x400, 4); p_put(0x198, 0x600, 4);
    P_CHECK(p_parse(0xA00) == R2_PE_RAW_REJECTED && p_report.reason == R2_PE_REASON_ALIGNMENT);
}
static void p_argument_cases(void)
{
    uint32_t i;
    unsigned char *bytes = (unsigned char *)&p_report;
    p_base(0xA00);
    for (i = 0; i < sizeof(p_report); ++i) bytes[i] = p_saved[i] = 0xA5;
    P_CHECK(route2_pe_preload_parse_raw_v1(p_file, 0xA00, 2, &p_report, sizeof(p_report)) == R2_PE_RAW_BAD_ARGUMENT);
    P_CHECK(route2_pe_preload_parse_raw_v1(p_file, 0xA00, 1, &p_report, sizeof(p_report) - 1) == R2_PE_RAW_BAD_ARGUMENT);
    P_CHECK(route2_pe_preload_parse_raw_v1(NULL, 0, 1, &p_report, sizeof(p_report)) == R2_PE_RAW_BAD_ARGUMENT);
    P_CHECK(route2_pe_preload_parse_raw_v1(bytes, sizeof(p_report), 1, &p_report, sizeof(p_report)) == R2_PE_RAW_BAD_ARGUMENT);
    P_CHECK(route2_pe_preload_parse_raw_v1(bytes + 8, 16, 1, &p_report, sizeof(p_report)) == R2_PE_RAW_BAD_ARGUMENT);
    P_CHECK(route2_pe_preload_parse_raw_v1((const unsigned char *)(uintptr_t)(UINTPTR_MAX - 3), 8,
        1, &p_report, sizeof(p_report)) == R2_PE_RAW_BAD_ARGUMENT);
    P_CHECK(route2_pe_preload_parse_raw_v1(p_file, 0xA00, 1,
        (struct r2_pe_raw_report_v1 *)(uintptr_t)(UINTPTR_MAX - 7), sizeof(p_report)) == R2_PE_RAW_BAD_ARGUMENT);
    P_CHECK(route2_pe_preload_parse_raw_v1(p_file, 0xA00, 1,
        (struct r2_pe_raw_report_v1 *)(void *)(bytes + 1), sizeof(p_report)) == R2_PE_RAW_BAD_ARGUMENT);
    for (i = 0; i < sizeof(p_report); ++i) P_CHECK(bytes[i] == p_saved[i]);
}
static void p_work_boundary(void)
{
    struct r2_pe_context_v1 c;
    uint64_t value = UINT64_C(0xDEADBEEF);
    uint32_t off, span;
    p_base(0xA00); P_CHECK(p_parse(0xA00) == R2_PE_RAW_COMPLETE);
    c.file = p_file; c.length = 0xA00; c.r = &p_report;
    p_report.raw_status = R2_PE_RAW_REJECTED; p_report.reason = 0;
    p_report.structural_complete = 0; p_report.work_units = R2_PE_RAW_WORK_LIMIT - 1;
    P_CHECK(r2_pe_read_v1(&c, 0, 1, &value));
    P_CHECK(value == 'M' && p_report.work_units == R2_PE_RAW_WORK_LIMIT);
    P_CHECK(!r2_pe_read_v1(&c, 1, 1, &value));
    P_CHECK(value == 'M' && p_report.reason == R2_PE_REASON_WORK_LIMIT);
    P_CHECK(p_report.raw_status == R2_PE_RAW_INCOMPLETE && p_report.failure_offset == 1);
    p_report.reason = 0; p_report.work_units = R2_PE_RAW_WORK_LIMIT - 1;
    P_CHECK(!r2_pe_map_v1(&c, 0x1000, 1, &off, &span));
    P_CHECK(p_report.reason == R2_PE_REASON_WORK_LIMIT && p_report.work_units == R2_PE_RAW_WORK_LIMIT);
}
int main(void)
{
    p_good_cases(); p_header_cases(); p_import_bad_cases(); p_tls_bad_cases();
    p_limit_cases(); p_review_regressions(); p_argument_cases(); p_work_boundary();
    return p_failures ? 1 : 0;
}
