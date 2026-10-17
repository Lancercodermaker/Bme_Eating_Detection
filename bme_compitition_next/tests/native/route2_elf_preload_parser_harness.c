/* SOURCE ONLY: all assertions below are UNCOMPILED / UNRUN.
 * Invented FILE bytes; no OS queries or loader. Explicit real Linux-start
 * target and the actual production translation unit, with no fake platform.
 */
#ifndef R2_TARGET_LINUX_START
#error "Select R2_TARGET_LINUX_START explicitly; never fake target macros"
#endif
#include "../../src/eating_event/route2_candidate_overlap/native/route2_mount_helper.c"
#include <assert.h>

static unsigned char elf_file[131072];
/* Static FILE-limit fixture storage; never an automatic report/stack copy. */
static unsigned char file_limit_bytes[R2_ELF_RAW_FILE_LIMIT + 1u];
static struct r2_elf_raw_report_v1 elf_report;
static void ew(unsigned int o, uint64_t v, unsigned int n)
{
    unsigned int i;
    for (i = 0; i < n; ++i) { elf_file[o + i] = (unsigned char)v; v >>= 8; }
}
static void ep(unsigned int n, uint32_t type, uint32_t flags, uint64_t off,
               uint64_t va, uint64_t fs, uint64_t ms, uint64_t align)
{
    unsigned int p = 64 + n * 56;
    ew(p, type, 4); ew(p + 4, flags, 4); ew(p + 8, off, 8);
    ew(p + 16, va, 8); ew(p + 24, va, 8); ew(p + 32, fs, 8);
    ew(p + 40, ms, 8); ew(p + 48, align, 8);
}
static void ed(unsigned int n, uint64_t tag, uint64_t value)
{ ew(512 + n * 16, tag, 8); ew(520 + n * 16, value, 8); }
static void eb(unsigned int phnum)
{
    unsigned int i;
    for (i = 0; i < sizeof(elf_file); ++i) elf_file[i] = 0;
    ew(0, UINT64_C(0x00010102464c457f), 8);
    ew(16, 3, 2); ew(18, 62, 2); ew(20, 1, 4);
    ew(24, 0x400000, 8); ew(32, 64, 8); ew(52, 64, 2);
    ew(54, 56, 2); ew(56, phnum, 2);
    ep(0, 1, 5, 0, 0x400000, sizeof(elf_file), sizeof(elf_file) + 4096, 4096);
}
static uint32_t er(size_t n)
{
    uint32_t s = route2_elf_preload_parse_raw_v1(elf_file, n, R2_ELF_RAW_ABI,
                                               &elf_report, sizeof(elf_report));
    assert(elf_report.preload_scope == R2_ELF_PRELOAD_CLOSURE_UNPROVEN);
    assert(elf_report.work_units <= R2_ELF_RAW_WORK_LIMIT);
    assert(elf_report.string_bytes_inspected <= R2_ELF_RAW_STRING_BYTES_LIMIT);
    assert(s == elf_report.raw_status);
    return s;
}
static void dynamic_base(unsigned int entries)
{
    eb(2); ep(1, 2, 6, 512, 0x400200, entries * 16, entries * 16, 8);
}
static void positive_fixtures(void)
{
    unsigned int i;
    eb(1);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_COMPLETE);
    assert(elf_report.structural_complete && elf_report.load_count == 1);
    ew(16, 2, 2); assert(er(sizeof(elf_file)) == R2_ELF_RAW_COMPLETE);
    assert(elf_report.programs[0].memory_size > elf_report.programs[0].file_size);
    assert(elf_report.remaining_unproven == R2_ELF_UNPROVEN_ALL);
    /* Adjacent LOAD ranges are legal when no metadata span crosses them. */
    eb(2); ep(0, 1, 5, 0, 0x400000, 4096, 4096, 4096);
    ep(1, 1, 4, 4096, 0x401000, 4096, 4096, 4096);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_COMPLETE);
    assert(elf_report.load_count == 2);
    /* PT_NULL has undefined non-type fields: even nonsensical ranges ignored. */
    eb(2); ep(1, 0, UINT32_MAX, UINT64_MAX, UINT64_MAX, UINT64_MAX, 0, 3);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_COMPLETE);
    assert(elf_report.programs[1].file_offset == UINT64_MAX);
    /* String references deliberately precede STRTAB / STRSZ. */
    dynamic_base(7); ed(0, 1, 1); ed(1, 1, 6); ed(2, 14, 11);
    ed(3, 29, 16); ed(4, 5, 0x400400); ed(5, 10, 32); ed(6, 0, 0);
    for (i = 0; i < 4; ++i) {
        elf_file[1025 + i] = (unsigned char)"a.so"[i];
        elf_file[1030 + i] = (unsigned char)"b.so"[i];
        elf_file[1035 + i] = (unsigned char)"c.so"[i];
    }
    elf_file[1029] = 0; elf_file[1034] = 0; elf_file[1039] = 0;
    elf_file[1040] = '/'; elf_file[1041] = 'x';
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_APPLICATION_CONDITIONS);
    assert(elf_report.structural_complete && elf_report.needed_count == 2);
    assert(elf_report.strings[0].file_offset == 1025 && elf_report.strings[1].file_offset == 1030);
    assert(elf_report.strings[2].kind == R2_ELF_STRING_SONAME);
    assert(elf_report.application_conditions & R2_ELF_CONDITION_SEARCH_PATH);
    assert(elf_report.dynamic_terminated && !elf_report.dynamic_remainder_unknown);
    /* Interpreter must precede LOAD; empty TLS is still PRESENT. */
    eb(4); ep(0, 3, 4, 768, 0x400300, 4, 4, 1);
    ep(1, 1, 5, 0, 0x400000, sizeof(elf_file), sizeof(elf_file), 4096);
    ep(2, 7, 4, 0, 0x400000, 0, 0, 1);
    ep(3, 2, 6, 512, 0x400200, 80, 80, 8);
    elf_file[768] = '/'; elf_file[769] = 'l'; elf_file[770] = 'd';
    ed(0, 12, 0x400700); ed(1, 25, 0x400700); ed(2, 27, 8);
    ed(3, 13, 0x400710); ed(4, 0, 0);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_APPLICATION_CONDITIONS);
    assert(elf_report.interpreter_present && elf_report.interpreter_length == 3);
    assert(elf_report.tls_present && elf_report.tls_filesz == 0);
    assert((elf_report.application_conditions & R2_ELF_CONDITION_INIT_FINI) == R2_ELF_CONDITION_INIT_FINI);
}
static void adversarial_fixtures(void)
{
    unsigned int i;
    eb(1); assert(er(63) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_TRUNCATED);
    eb(1); elf_file[4] = 1; assert(er(sizeof(elf_file)) == R2_ELF_RAW_UNSUPPORTED);
    assert(elf_report.reason == R2_ELF_REASON_CLASS);
    eb(1); ew(18, 3, 2); assert(er(sizeof(elf_file)) == R2_ELF_RAW_UNSUPPORTED);
    eb(1); ew(56, 65535, 2); assert(er(sizeof(elf_file)) == R2_ELF_RAW_UNSUPPORTED);
    assert(elf_report.reason == R2_ELF_REASON_EXTENDED_COUNT);
    eb(1); ew(56, 129, 2); assert(er(sizeof(elf_file)) == R2_ELF_RAW_INCOMPLETE);
    eb(1); ew(54, 64, 2); assert(er(sizeof(elf_file)) == R2_ELF_RAW_UNSUPPORTED);
    eb(1); ew(32, UINT64_MAX - 8, 8); assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    eb(1); ep(0, 1, 5, 0, UINT64_MAX - 4, 16, 16, 1);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    eb(1); ep(0, 1, 5, 0, 0x400000, 16, 8, 1);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    eb(1); ew(112, 3, 8); assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    eb(1); ew(72, 1, 8); assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    eb(2); ep(1, 1, 4, 4096, 0x3ff000, 4096, 4096, 4096);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_LOAD_ORDER);
    eb(2); ep(1, 1, 4, 4096, 0x401000, 4096, 4096, 4096);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_LOAD_OVERLAP);
    /* Dynamic metadata in virtual zero fill is not raw FILE content. */
    dynamic_base(1); ew(136, UINT64_C(0x400000) + sizeof(elf_file), 8);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_ZERO_FILL);
    dynamic_base(2); ed(0, 10, 32); ed(1, 10, 32);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_DUPLICATE_TAG);
    assert(elf_report.dynamic_count == 2 && elf_report.dynamic_remainder_unknown);
    dynamic_base(1); ed(0, 1, 1);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_DYNAMIC_TERMINATOR);
    dynamic_base(2); ed(0, 5, 0x400400); ed(1, 0, 0);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_STRING_TABLE_PAIR);
    dynamic_base(4); ed(0, 1, 0); ed(1, 5, 0x400400); ed(2, 10, 512); ed(3, 0, 0);
    for (i = 1024; i < 1536; ++i) elf_file[i] = 'a';
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_INCOMPLETE);
    assert(elf_report.reason == R2_ELF_REASON_STRING_LIMIT && elf_report.strings_count == 1);
    assert(!elf_report.strings[0].complete && elf_report.needed_remainder_unknown);
    elf_file[1024] = 0; assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_EMPTY_NAME);
    elf_file[1024] = 0x80; assert(er(sizeof(elf_file)) == R2_ELF_RAW_UNSUPPORTED);
    assert(elf_report.reason == R2_ELF_REASON_STRING_ASCII);
    /* Empty RUNPATH remains a present application condition. */
    dynamic_base(4); ed(0, 29, 0); ed(1, 5, 0x400400); ed(2, 10, 1); ed(3, 0, 0);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_APPLICATION_CONDITIONS);
    assert(elf_report.strings[0].complete && elf_report.strings[0].length == 0);
    dynamic_base(2); ed(0, UINT64_C(0x7fffffff), 1); ed(1, 0, 0);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_UNSUPPORTED);
    assert(elf_report.unknown_dynamic_count == 1 && elf_report.dynamic_count == 2);
    assert(!elf_report.structural_complete && elf_report.needed_remainder_unknown);
    dynamic_base(2); ed(0, 25, 0x400700); ed(1, 0, 0);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_ARRAY_PAIR);
    dynamic_base(3); ed(0, 25, 0x400701); ed(1, 27, 8); ed(2, 0, 0);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_ARRAY_ALIGNMENT);
    eb(2); ep(1, UINT32_C(0x6000abcd), 0, 0, 0, 0, 0, 1);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_UNSUPPORTED);
    assert(elf_report.unknown_program_count == 1);
}
static void interpreter_and_partial_fixtures(void)
{
    unsigned int i;
    /* Full 511-byte payload plus NUL is inside the inclusive string cap. */
    dynamic_base(4); ed(0, 1, 0); ed(1, 5, 0x400400); ed(2, 10, 512); ed(3, 0, 0);
    for (i = 1024; i < 1535; ++i) elf_file[i] = 'a';
    elf_file[1535] = 0;
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_COMPLETE);
    assert(elf_report.strings[0].length == 511 && elf_report.strings[0].complete);
    assert(elf_report.string_bytes_inspected == 512);
    /* A later failed name must retain the earlier complete name verbatim. */
    dynamic_base(5); ed(0, 1, 0); ed(1, 1, 510); ed(2, 5, 0x400400);
    ed(3, 10, 512); ed(4, 0, 0);
    elf_file[1024] = 'a'; elf_file[1534] = 'b'; elf_file[1535] = 'c';
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_STRING_TERMINATOR);
    assert(elf_report.strings_count == 2 && elf_report.needed_count == 2);
    assert(elf_report.strings[0].complete && elf_report.strings[0].length == 1);
    assert(elf_report.strings[0].file_offset == 1024 && elf_report.strings[1].length == 2);
    assert(!elf_report.strings[1].complete && elf_report.needed_remainder_unknown);
    eb(2); ep(0, 3, 4, 768, 0x400300, 4, 4, 1);
    ep(1, 1, 5, 0, 0x400000, sizeof(elf_file), sizeof(elf_file), 4096);
    elf_file[768] = 'x'; elf_file[769] = 'l'; elf_file[770] = 'd';
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_INTERPRETER);
    elf_file[768] = '/'; elf_file[769] = 0;
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_INTERPRETER);
    elf_file[769] = 'l'; elf_file[771] = 'x';
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_INTERPRETER);
    elf_file[771] = 0; elf_file[769] = 0x80;
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_UNSUPPORTED);
    assert(elf_report.reason == R2_ELF_REASON_STRING_ASCII);
    ew(96, 513, 8); ew(104, 513, 8);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_INCOMPLETE);
    assert(elf_report.reason == R2_ELF_REASON_STRING_LIMIT);
    eb(2); ep(1, 3, 4, 768, 0x400300, 4, 4, 1);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_INTERPRETER_ORDER);
    eb(3); ep(0, 3, 4, 768, 0x400300, 4, 4, 1);
    ep(1, 3, 4, 768, 0x400300, 4, 4, 1);
    ep(2, 1, 5, 0, 0x400000, sizeof(elf_file), sizeof(elf_file), 4096);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_DUPLICATE_PROGRAM);
    eb(1); assert(er(0) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_TRUNCATED);
}
static void additional_range_and_cap_fixtures(void)
{
    unsigned int i;
    uint32_t s;
    /* Two adjacent valid LOADs cannot jointly back a metadata span. */
    eb(3); ep(0, 1, 5, 0, 0x400000, 512, 512, 1);
    ep(1, 1, 4, 512, 0x400200, 512, 512, 1);
    ep(2, 2, 6, 496, 0x4001f0, 32, 32, 8);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_AMBIGUOUS_MAPPING);
    assert(elf_report.dynamic_count == 0 && elf_report.dynamic_remainder_unknown);
    /* One LOAD intersecting only the start is a distinct crossing failure. */
    dynamic_base(2); ep(0, 1, 5, 0, 0x400000, 1024, 1024, 1);
    ep(1, 2, 6, 1008, 0x4003f0, 32, 32, 8);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_SPAN_CROSSING);
    /* Earlier LOAD overlap rejects an ambiguous directory before parsing it. */
    eb(3); ep(1, 1, 4, 4096, 0x401000, 4096, 4096, 4096);
    ep(2, 2, 6, 512, 0x400200, 16, 16, 8);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_LOAD_OVERLAP && !elf_report.dynamic_count);
    dynamic_base(1); ew(136, 0x400208, 8); ed(0, 0, 0);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_MAPPING_MISMATCH);
    dynamic_base(3); ed(0, 5, 1024); ed(1, 10, 16); ed(2, 0, 0);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_UNMAPPED);
    dynamic_base(4); ed(0, 1, 1); ed(1, 5, 0x400400); ed(2, 10, 4); ed(3, 0, 0);
    elf_file[1025] = 'a'; elf_file[1026] = 'b'; elf_file[1027] = 'c';
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_STRING_TERMINATOR);
    assert(elf_report.strings[0].length == 3 && !elf_report.strings[0].complete);
    dynamic_base(4); ed(0, 1, 4); ed(1, 5, 0x400400); ed(2, 10, 4); ed(3, 0, 0);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_STRING_INDEX);
    dynamic_base(2); ew(152, 31, 8);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_DYNAMIC_SIZE);
    eb(3); ep(1, 2, 6, 512, 0x400200, 16, 16, 8);
    ep(2, 2, 6, 512, 0x400200, 16, 16, 8);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_DUPLICATE_PROGRAM);
    /* Presence/declared facts survive even a malformed empty TLS extent. */
    eb(2); ep(1, 7, 4, UINT64_MAX, 0, 0, 0, 1);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.tls_present && elf_report.tls_filesz == 0);
    assert(elf_report.application_conditions & R2_ELF_CONDITION_TLS);
    assert(elf_report.programs[1].file_offset == UINT64_MAX);
    eb(2); ep(1, 2, 6, sizeof(elf_file) - 8, 0x400200, 16, 16, 8);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.dynamic_present && elf_report.dynamic_size == 16);
    assert(elf_report.dynamic_offset == sizeof(elf_file) - 8);
    /* Unknown program fields are not invented into defined file ranges. */
    eb(2); ep(1, UINT32_C(0x6000abcd), 0, UINT64_MAX, UINT64_MAX, UINT64_MAX, UINT64_MAX, 3);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_UNSUPPORTED);
    assert(elf_report.reason == R2_ELF_REASON_UNKNOWN_PROGRAM);
    assert(elf_report.programs[1].file_offset == UINT64_MAX);
    dynamic_base(3); ed(0, 25, UINT64_MAX - 7); ed(1, 27, 16); ed(2, 0, 0);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_VIRTUAL_OVERFLOW);
    dynamic_base(3); ed(0, 32, 0); ed(1, 33, 0); ed(2, 0, 0);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_APPLICATION_CONDITIONS);
    assert(elf_report.application_conditions & R2_ELF_CONDITION_PREINIT_ARRAY);
    /* Every dynamic-string slot: 256 NEEDED + SONAME + RPATH + RUNPATH.
     * Interpreter is independent and never consumes one of these 259 slots.
     */
    dynamic_base(262);
    for (i = 0; i < 256; ++i) ed(i, 1, 1);
    ed(256, 14, 1); ed(257, 15, 0); ed(258, 29, 0);
    ed(259, 5, 0x401c00); ed(260, 10, 3); ed(261, 0, 0);
    elf_file[7169] = 'n';
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_APPLICATION_CONDITIONS);
    assert(elf_report.structural_complete && elf_report.needed_count == 256);
    assert(elf_report.strings_count == 259 && !elf_report.needed_remainder_unknown);
    assert(elf_report.strings[257].kind == R2_ELF_STRING_RPATH);
    assert(elf_report.strings[258].kind == R2_ELF_STRING_RUNPATH);
    assert(elf_report.strings[258].complete && elf_report.strings[258].length == 0);
    /* A familiar numeric GNU tag is only a retained raw semantic fact. */
    dynamic_base(2); ed(0, UINT64_C(0x6ffffffb), 16); ed(1, 0, 0);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_COMPLETE);
    assert(elf_report.dynamics[0].interpretation == R2_ELF_DYNAMIC_RAW_ONLY);
    assert(elf_report.remaining_unproven & R2_ELF_UNPROVEN_DYNAMIC_RAW_SEMANTICS);
    /* Declared dynamic extent exceeds the finite entry profile. */
    dynamic_base(R2_ELF_RAW_DYNAMIC_LIMIT + 1u);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_INCOMPLETE);
    assert(elf_report.reason == R2_ELF_REASON_DYNAMIC_LIMIT);
    assert(elf_report.dynamic_declared_entries == R2_ELF_RAW_DYNAMIC_LIMIT + 1u);
    assert(elf_report.dynamic_remainder_unknown && elf_report.needed_remainder_unknown);
    /* Repeated NEEDED is legal through 256; entry 257 refuses, never truncates. */
    dynamic_base(258);
    for (i = 0; i < 257; ++i) ed(i, 1, 0);
    ed(257, 0, 0);
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_INCOMPLETE);
    assert(elf_report.reason == R2_ELF_REASON_NEEDED_LIMIT);
    assert(elf_report.dynamic_count == 257 && !elf_report.dynamic_terminated);
    /* Each repeated reference scans the original 512 bytes afresh and charges
     * every byte including NUL. At 256 references the work budget refuses
     * before all records complete, independently of the larger byte cap.
     */
    dynamic_base(259);
    for (i = 0; i < 256; ++i) ed(i, 1, 0);
    ed(256, 5, 0x401c00); ed(257, 10, 512); ed(258, 0, 0);
    for (i = 7168; i < 7679; ++i) elf_file[i] = 'a';
    elf_file[7679] = 0;
    assert(er(sizeof(elf_file)) == R2_ELF_RAW_INCOMPLETE);
    assert(elf_report.reason == R2_ELF_REASON_WORK_LIMIT);
    assert(elf_report.dynamic_terminated && !elf_report.dynamic_remainder_unknown);
    assert(elf_report.needed_remainder_unknown && elf_report.needed_count <= 256);
    assert(elf_report.string_bytes_inspected > 512);
    /* Full valid readable caller FILE span, refused before header access. */
    s = route2_elf_preload_parse_raw_v1(file_limit_bytes, sizeof(file_limit_bytes),
        R2_ELF_RAW_ABI, &elf_report, sizeof(elf_report));
    assert(s == R2_ELF_RAW_INCOMPLETE && elf_report.reason == R2_ELF_REASON_FILE_LIMIT);
    assert(elf_report.preload_scope == R2_ELF_PRELOAD_CLOSURE_UNPROVEN);
    /* A Linux OSABI with ABI version zero is inside the selected profile. */
    eb(1); elf_file[7] = 3; assert(er(sizeof(elf_file)) == R2_ELF_RAW_COMPLETE);
    elf_file[8] = 1; assert(er(sizeof(elf_file)) == R2_ELF_RAW_UNSUPPORTED);
    eb(1); elf_file[5] = 2; assert(er(sizeof(elf_file)) == R2_ELF_RAW_UNSUPPORTED);
    eb(1); ew(20, 2, 4); assert(er(sizeof(elf_file)) == R2_ELF_RAW_UNSUPPORTED);
    eb(0); assert(er(sizeof(elf_file)) == R2_ELF_RAW_REJECTED);
    assert(elf_report.reason == R2_ELF_REASON_NO_LOAD);
}
static void assert_report_sentinel(void)
{
    size_t i;
    const unsigned char *p = (const unsigned char *)&elf_report;
    for (i = 0; i < sizeof(elf_report); ++i) assert(p[i] == 0xa5);
}
static void bad_argument_fixtures(void)
{
    size_t i;
    unsigned char *p = (unsigned char *)&elf_report;
    eb(1);
    for (i = 0; i < sizeof(elf_report); ++i) p[i] = 0xa5;
    assert(route2_elf_preload_parse_raw_v1(elf_file, sizeof(elf_file), 99,
           &elf_report, sizeof(elf_report)) == R2_ELF_RAW_BAD_ARGUMENT);
    assert_report_sentinel();
    assert(route2_elf_preload_parse_raw_v1(elf_file, sizeof(elf_file), R2_ELF_RAW_ABI,
           &elf_report, sizeof(elf_report) - 1) == R2_ELF_RAW_BAD_ARGUMENT);
    assert_report_sentinel();
    assert(route2_elf_preload_parse_raw_v1(p, sizeof(elf_report), R2_ELF_RAW_ABI,
           &elf_report, sizeof(elf_report)) == R2_ELF_RAW_BAD_ARGUMENT);
    assert_report_sentinel();
    assert(route2_elf_preload_parse_raw_v1(elf_file, sizeof(elf_file), R2_ELF_RAW_ABI,
           (struct r2_elf_raw_report_v1 *)(uintptr_t)((uintptr_t)p + 1u), sizeof(elf_report)) == R2_ELF_RAW_BAD_ARGUMENT);
    assert_report_sentinel();
    assert(route2_elf_preload_parse_raw_v1(NULL, 0, R2_ELF_RAW_ABI,
           &elf_report, sizeof(elf_report)) == R2_ELF_RAW_BAD_ARGUMENT);
    assert_report_sentinel();
    assert(route2_elf_preload_parse_raw_v1(elf_file, sizeof(elf_file), R2_ELF_RAW_ABI,
           NULL, sizeof(elf_report)) == R2_ELF_RAW_BAD_ARGUMENT);
    assert_report_sentinel();
    /* Deliberately invalid integer ranges are rejected without dereference. */
    assert(route2_elf_preload_parse_raw_v1(
           (const unsigned char *)(uintptr_t)(UINTPTR_MAX - 7u), 16, R2_ELF_RAW_ABI,
           &elf_report, sizeof(elf_report)) == R2_ELF_RAW_BAD_ARGUMENT);
    assert_report_sentinel();
    assert(route2_elf_preload_parse_raw_v1(elf_file, sizeof(elf_file), R2_ELF_RAW_ABI,
           (struct r2_elf_raw_report_v1 *)(uintptr_t)(UINTPTR_MAX - 7u), sizeof(elf_report)) == R2_ELF_RAW_BAD_ARGUMENT);
    assert_report_sentinel();
}
int main(void)
{
    positive_fixtures(); adversarial_fixtures(); interpreter_and_partial_fixtures();
    additional_range_and_cap_fixtures();
    bad_argument_fixtures();
    return 0;
}
