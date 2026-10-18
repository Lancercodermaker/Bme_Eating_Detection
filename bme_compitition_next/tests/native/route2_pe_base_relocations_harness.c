/* SOURCE FIRST fixture plan and assertion source: UNCOMPILED / UNRUN.
 * Written before the new production body. Includes that actual TU once;
 * future builds must not separately link its transitively included TUs.
 * Invented FILE bytes only. No OS/API/probe/loader, callback, allocation,
 * project import, GT, native budget grant, closure PASS or runtime evidence.
 * Intended branches are documented below; source assertions are not results.
 */
#if !defined(R2_TARGET_WINDOWS_SEED)
#error "Explicit Windows seed target required"
#endif
#include "../../src/eating_event/route2_candidate_overlap/native/route2_pe_base_relocations.c"

#define B_BYTES 131072u
static unsigned char b_file[B_BYTES];
static unsigned char b_oversize[R2_BR_FILE_LIMIT + 1u];
static struct r2_br_report_v1 b_report;
static struct r2_br_workspace_v1 b_workspace;
static struct r2_pe_raw_report_v1 b_raw_reference;
static unsigned char b_saved[R2_BR_REPORT_BYTES];
static unsigned char b_ws_saved[R2_BR_WORKSPACE_BYTES];
static uint32_t b_failures;
#define B_CHECK(e) do { if (!(e)) ++b_failures; } while (0)

static void b_put(uint32_t off, uint64_t v, uint32_t n)
{
    uint32_t i;
    for (i = 0; i < n; ++i) b_file[off + i] = (unsigned char)(v >> (i * 8u));
}
static uint32_t b_rva(uint32_t off) { return off + 0xE00u; }
static void b_base(void)
{
    memset(b_file, 0, sizeof(b_file));
    b_put(0, 0x5A4D, 2); b_put(0x3C, 0x80, 4);
    b_put(0x80, 0x4550, 4); b_put(0x84, 0x8664, 2);
    b_put(0x86, 1, 2); b_put(0x94, 240, 2); b_put(0x96, 0x22, 2);
    b_put(0x98, 0x20B, 2); b_put(0xA8, 0x1100, 4);
    b_put(0xB0, UINT64_C(0x140000000), 8);
    b_put(0xB8, 0x1000, 4); b_put(0xBC, 0x200, 4);
    b_put(0xD0, 0x22000, 4); b_put(0xD4, 0x200, 4);
    b_put(0x104, 16, 4);
    b_put(0x190, 0x21000, 4); b_put(0x194, 0x1000, 4);
    b_put(0x198, B_BYTES - 0x200, 4); b_put(0x19C, 0x200, 4);
    b_put(0x1AC, 0xC0000040, 4);
}
static void b_dir(uint32_t rva, uint32_t size)
{
    b_put(0x130, rva, 4); b_put(0x134, size, 4);
}
static void b_block(uint32_t off, uint32_t page, uint32_t bytes)
{
    b_put(off, page, 4); b_put(off + 4, bytes, 4);
}
static uint32_t b_parse_limit(uint64_t limit)
{
    uint32_t s = route2_pe_base_relocations_parse_v1(b_file, sizeof(b_file),
        R2_BR_ABI, limit, &b_report, sizeof(b_report),
        &b_workspace, sizeof(b_workspace));
    B_CHECK(s == b_report.status);
    B_CHECK(b_report.preload_scope == R2_PE_PRELOAD_CLOSURE_UNPROVEN);
    B_CHECK(b_report.work_units <= limit && b_report.work_units >= R2_BR_INITIAL_WORK);
    B_CHECK(b_report.block_count <= R2_BR_BLOCK_LIMIT && b_report.word_count <= R2_BR_WORD_LIMIT);
    B_CHECK(b_report.base.preload_scope == R2_PE_PRELOAD_CLOSURE_UNPROVEN);
    B_CHECK(b_report.base_status == b_report.base.raw_status);
    B_CHECK(b_report.base_reason == b_report.base.reason);
    return s;
}
static uint32_t b_parse(void) { return b_parse_limit(R2_BR_WORK_LIMIT); }

/* Absent/stripped/present are metadata conditions, never safe-load facts. */
static void b_good(void)
{
    b_base();
    B_CHECK(b_parse() == R2_BR_COMPLETE && b_report.metadata_complete);
    B_CHECK(b_report.directory_condition == R2_BR_ABSENT && !b_report.relocs_stripped);
    B_CHECK(b_report.coff_characteristics == 0x22 && b_report.coff_characteristics_valid);
    b_put(0x96, 0x23, 2);
    B_CHECK(b_parse() == R2_BR_COMPLETE && b_report.directory_condition == R2_BR_STRIPPED_ABSENT);
    /* Bytes outside NumberOfRvaAndSizes are not a declared directory. */
    b_base(); b_dir(0xFFFFFFFFu, 0xFFFFFFFFu); b_put(0x104, 5, 4);
    B_CHECK(b_parse() == R2_BR_COMPLETE && b_report.directory_condition == R2_BR_ABSENT);
    B_CHECK(!b_report.directory_fields_valid && !b_report.directory_rva && !b_report.directory_size);
    /* Block 1: DIR64 at an unaligned RVA and ABSOLUTE with nonzero low bits.
     * Block 2 is a legal final ten-byte block, with a header target. */
    b_base(); b_dir(b_rva(0x600), 22);
    b_block(0x600, 0x1000, 12); b_put(0x608, 0xA103, 2); b_put(0x60A, 0x0ABC, 2);
    b_block(0x60C, 0, 10); b_put(0x614, 0xA060, 2);
    b_put(0x303, UINT64_C(0x8877665544332211), 8);
    b_put(0x60, UINT64_C(0x0123456789ABCDEF), 8);
    B_CHECK(b_parse() == R2_BR_COMPLETE);
    B_CHECK(b_report.directory_fields_valid == 3 && b_report.directory_rva == b_rva(0x600));
    B_CHECK(b_report.block_count == 2 && b_report.block_complete == 2);
    B_CHECK(b_report.word_count == 3 && b_report.word_complete == 3);
    B_CHECK(b_report.absolute_count == 1 && b_report.dir64_count == 2);
    B_CHECK(!b_report.word_count_unknown && !b_report.block_count_unknown);
    B_CHECK(b_report.words[0].target_rva == 0x1103 && b_report.words[0].target_extent == 8);
    B_CHECK(b_report.words[0].target_file_offset == 0x303);
    B_CHECK(b_report.words[0].raw_value == UINT64_C(0x8877665544332211));
    B_CHECK(b_report.words[0].valid_fields & R2_BR_WORD_VALUE);
    B_CHECK(b_report.words[1].raw_word == 0x0ABC && b_report.words[1].state == R2_BR_WORD_SKIPPED);
    B_CHECK(!(b_report.words[1].valid_fields & R2_BR_WORD_TARGET));
    B_CHECK(b_report.words[2].target_kind == R2_BR_MAP_FILE);
    B_CHECK(b_report.words[2].target_file_offset == 0x60);
    B_CHECK(b_report.words[2].raw_value == UINT64_C(0x0123456789ABCDEF));
    B_CHECK(b_report.blocks[1].block_size == 10 && b_report.blocks[1].raw_header_bytes == 8);
    b_put(0x96, 0x23, 2);
    B_CHECK(b_parse() == R2_BR_COMPLETE && b_report.directory_condition == R2_BR_STRIPPED_PRESENT);
    /* Zero-fill and a FILE/zero-fill mixed span have no fabricated raw u64. */
    b_base(); b_dir(b_rva(0x600), 12); b_block(0x600, 0x20000, 12);
    b_put(0x608, 0xAE00, 2); b_put(0x60A, 0, 2);
    B_CHECK(b_parse() == R2_BR_COMPLETE && b_report.words[0].target_kind == R2_BR_MAP_ZERO_FILL);
    B_CHECK(!(b_report.words[0].valid_fields & R2_BR_WORD_VALUE));
    b_put(0x600, 0x20000, 4); b_put(0x608, 0xADFC, 2);
    /* Backed range ends at RVA 0x20E00: 0x20DFC straddles that edge. */
    B_CHECK(b_parse() == R2_BR_COMPLETE && b_report.words[0].target_kind == R2_BR_MAP_MIXED);
    B_CHECK(!(b_report.words[0].valid_fields & R2_BR_WORD_VALUE));
    /* Overlapping target addresses are retained; there is no deduplication. */
    b_base(); b_dir(b_rva(0x600), 12); b_block(0x600, 0x1000, 12);
    b_put(0x608, 0xA100, 2); b_put(0x60A, 0xA104, 2);
    B_CHECK(b_parse() == R2_BR_COMPLETE && b_report.dir64_count == 2);
    /* Full original application-sensitive TLS facts survive unchanged. */
    b_base(); b_dir(b_rva(0x600), 10); b_block(0x600, 0x1000, 10); b_put(0x608, 0xA100, 2);
    b_put(0x150, b_rva(0x800), 4); b_put(0x154, 40, 4);
    b_put(0x800, UINT64_C(0x140000000) + b_rva(0x900), 8);
    b_put(0x808, UINT64_C(0x140000000) + b_rva(0x908), 8);
    b_put(0x810, UINT64_C(0x140000000) + b_rva(0x930), 8);
    b_put(0x818, UINT64_C(0x140000000) + b_rva(0x940), 8);
    b_put(0x940, UINT64_C(0x140001100), 8);
    B_CHECK(route2_pe_preload_parse_raw_v1(b_file, sizeof(b_file), R2_PE_RAW_ABI,
        &b_raw_reference, sizeof(b_raw_reference)) == R2_PE_RAW_APPLICATION_TLS_PRESENT);
    B_CHECK(b_parse() == R2_BR_PARTIAL && b_report.reason == R2_BR_BASE_APPLICATION);
    B_CHECK(b_report.metadata_complete && !b_report.base_accepted);
    B_CHECK(b_report.base.tls.callback_count == 1 && b_report.base.structural_complete);
    B_CHECK(!memcmp(&b_raw_reference, &b_report.base, sizeof(b_raw_reference)));
}

/* Actual public parser rejection paths retain earlier and current raw facts. */
static void b_bad_metadata(void)
{
    uint32_t i;
    static const uint32_t sizes[] = { 0, 2, 6, 7, 9, 11, 14 };
    b_base(); b_dir(0, 8);
    B_CHECK(b_parse() == R2_BR_REJECTED && b_report.reason == R2_BR_DIRECTORY_PAIR);
    b_base(); b_dir(b_rva(0x600), 0);
    B_CHECK(b_parse() == R2_BR_REJECTED && b_report.reason == R2_BR_DIRECTORY_PAIR);
    b_base(); b_dir(0xFFFFFFFCu, 16);
    B_CHECK(b_parse() == R2_BR_REJECTED && b_report.reason == R2_BR_DIRECTORY_RANGE);
    b_base(); b_dir(0x20E00, 8);
    B_CHECK(b_parse() == R2_BR_REJECTED && b_report.reason == R2_BR_DIRECTORY_MAPPING);
    B_CHECK(b_report.directory_map_kind == R2_BR_MAP_ZERO_FILL);
    b_base(); b_dir(0x20DFC, 8);
    B_CHECK(b_parse() == R2_BR_REJECTED && b_report.directory_map_kind == R2_BR_MAP_MIXED);
    b_base(); b_dir(0x300, 8);
    B_CHECK(b_parse() == R2_BR_REJECTED && b_report.directory_map_kind == R2_BR_MAP_GAP);
    for (i = 1; i < 8; ++i) {
        b_base(); b_dir(b_rva(0x600), i); b_block(0x600, 0x1000, 12);
        B_CHECK(b_parse() == R2_BR_REJECTED && b_report.reason == R2_BR_BLOCK_TRUNCATED);
        B_CHECK(b_report.block_count == 1 && b_report.blocks[0].raw_header_bytes == i);
        B_CHECK(!!(b_report.blocks[0].valid_fields & R2_BR_BLOCK_PAGE) == (i >= 4));
    }
    for (i = 0; i < sizeof(sizes) / sizeof(sizes[0]); ++i) {
        b_base(); b_dir(b_rva(0x600), 12); b_block(0x600, 0x1000, sizes[i]);
        B_CHECK(b_parse() == R2_BR_REJECTED);
        B_CHECK(b_report.blocks[0].block_size == sizes[i] && b_report.block_partial == 1);
    }
    b_base(); b_dir(b_rva(0x602), 8); b_block(0x602, 0x1000, 8);
    B_CHECK(b_parse() == R2_BR_REJECTED && b_report.reason == R2_BR_BLOCK_ALIGNMENT);
    B_CHECK(b_report.blocks[0].raw_header_bytes == 8);
    b_base(); b_dir(b_rva(0x600), 20); b_block(0x600, 0x1000, 10);
    b_put(0x608, 0, 2); b_block(0x60A, 0x1000, 10); b_put(0x612, 0, 2);
    B_CHECK(b_parse() == R2_BR_REJECTED && b_report.reason == R2_BR_BLOCK_ALIGNMENT);
    B_CHECK(b_report.block_complete == 1 && b_report.blocks[1].page_rva == 0x1000);
    b_base(); b_dir(b_rva(0x600), 8); b_block(0x600, 0x1001, 8);
    B_CHECK(b_parse() == R2_BR_REJECTED && b_report.reason == R2_BR_PAGE_ALIGNMENT);
    b_put(0x600, 0x22000, 4);
    B_CHECK(b_parse() == R2_BR_REJECTED && b_report.reason == R2_BR_PAGE_RANGE);
    /* HIGHADJ's following WORD is deliberately not decoded as another entry. */
    b_base(); b_dir(b_rva(0x600), 16); b_block(0x600, 0x1000, 16);
    b_put(0x608, 0xA100, 2); b_put(0x60A, 0x4108, 2);
    b_put(0x60C, 0xA222, 2); b_put(0x60E, 0, 2);
    B_CHECK(b_parse() == R2_BR_PARTIAL && b_report.reason == R2_BR_UNSUPPORTED_TYPE);
    B_CHECK(b_report.word_count == 2 && b_report.word_complete == 1 && b_report.word_partial == 1);
    B_CHECK(b_report.words[1].raw_word == 0x4108 && b_report.words[1].type == 4);
    B_CHECK(b_report.words[2].valid_fields == 0 && b_report.word_unrepresented_known == 2);
    B_CHECK(b_report.word_semantics_unknown_known == 3 && b_report.word_count_unknown);
    /* Target gap, image extent and checked 32-bit extent overflow. */
    b_base(); b_dir(b_rva(0x600), 10); b_block(0x600, 0, 10); b_put(0x608, 0xA300, 2);
    B_CHECK(b_parse() == R2_BR_REJECTED && b_report.words[0].target_kind == R2_BR_MAP_GAP);
    b_base(); b_dir(b_rva(0x600), 10); b_block(0x600, 0x21000, 10); b_put(0x608, 0xAFFC, 2);
    B_CHECK(b_parse() == R2_BR_REJECTED && b_report.reason == R2_BR_TARGET_RANGE);
    B_CHECK(b_report.words[0].target_rva == 0x21FFC && b_report.words[0].raw_word == 0xAFFC);
    /* Near-4GiB image keeps the small FILE backing and large virtual extent. */
    b_base(); b_put(0xD0, 0xFFFFF000u, 4); b_put(0x190, 0xFFFFE000u, 4);
    b_dir(b_rva(0x600), 10); b_block(0x600, 0xFFFFE000u, 10); b_put(0x608, 0xAFFC, 2);
    B_CHECK(b_parse() == R2_BR_REJECTED && b_report.reason == R2_BR_TARGET_RANGE);
    /* A valid low-alignment base can place a target across header/section
     * owners. The public relocation parser records CROSSING and reads no u64. */
    b_base(); b_put(0xB8, 0x200, 4); b_put(0x194, 0x200, 4);
    b_dir(0x600, 10); b_block(0x600, 0, 10); b_put(0x608, 0xA1FC, 2);
    B_CHECK(b_parse() == R2_BR_REJECTED && b_report.reason == R2_BR_TARGET_MAPPING);
    B_CHECK(b_report.words[0].target_kind == R2_BR_MAP_CROSSING);
    B_CHECK(!(b_report.words[0].valid_fields & R2_BR_WORD_VALUE));
    /* SOURCE / UNRUN: the inherited profile permits 512-byte image alignment.
     * This public-input fixture keeps PageRVA below SizeOfImage, while its
     * DIR64 target RVA 0xFFFFFFFC plus extent eight overflows the u32 domain.
     * These assertions express the intended path; they are not run results. */
    b_base(); b_put(0xB8, 0x200, 4); b_put(0xD0, 0xFFFFFE00u, 4);
    b_put(0x194, 0x200, 4); b_dir(0x600, 10);
    b_block(0x600, 0xFFFFF000u, 10); b_put(0x608, 0xAFFC, 2);
    B_CHECK(b_parse() == R2_BR_REJECTED && b_report.reason == R2_BR_TARGET_OVERFLOW);
    B_CHECK(b_report.base.raw_status == R2_PE_RAW_COMPLETE && b_report.base.structural_complete);
    B_CHECK(b_report.base_accepted && !b_report.metadata_complete);
    B_CHECK(b_report.word_count == 1 && b_report.word_partial == 1);
    B_CHECK(b_report.words[0].raw_word == 0xAFFC && b_report.words[0].target_rva == 0xFFFFFFFCu);
    B_CHECK(b_report.words[0].target_extent == 8 && b_report.words[0].target_kind == R2_BR_MAP_OVERFLOW);
    B_CHECK((b_report.words[0].valid_fields & (R2_BR_WORD_RAW | R2_BR_WORD_TARGET | R2_BR_WORD_MAPPING)) ==
        (R2_BR_WORD_RAW | R2_BR_WORD_TARGET | R2_BR_WORD_MAPPING));
    B_CHECK(!(b_report.words[0].valid_fields & R2_BR_WORD_VALUE));
    b_base(); b_put(0, 0, 2);
    B_CHECK(b_parse() == R2_BR_REJECTED && b_report.reason == R2_BR_BASE_PARSE);
    B_CHECK(b_report.base.reason == R2_PE_REASON_DOS && !b_report.metadata_complete);
    /* A malformed import is retained by the full base report without promotion. */
    b_base(); b_put(0x110, b_rva(0x800), 4); b_put(0x114, 20, 4);
    b_put(0x80C, b_rva(0x900), 4); b_put(0x810, b_rva(0xA00), 4);
    b_file[0x900] = 'x';
    B_CHECK(b_parse() != R2_BR_COMPLETE && b_report.reason == R2_BR_BASE_PARSE);
    B_CHECK(b_report.base.descriptor_count == 1 && b_report.base.reason != 0);
}

static void b_limits(void)
{
    uint32_t i; uint64_t used;
    b_base(); b_dir(b_rva(0x600), (R2_BR_BLOCK_LIMIT + 1u) * 8u);
    for (i = 0; i <= R2_BR_BLOCK_LIMIT; ++i) b_block(0x600 + i * 8, 0x1000, 8);
    B_CHECK(b_parse() == R2_BR_PARTIAL && b_report.reason == R2_BR_BLOCK_CAP);
    B_CHECK(b_report.block_count == R2_BR_BLOCK_LIMIT && b_report.blocks_unrepresented_min == 1);
    b_base(); b_dir(b_rva(0x600), 8 + 2 * (R2_BR_WORD_LIMIT + 1u));
    b_block(0x600, 0x1000, 8 + 2 * (R2_BR_WORD_LIMIT + 1u));
    B_CHECK(b_parse() == R2_BR_PARTIAL && b_report.reason == R2_BR_WORD_CAP);
    B_CHECK(b_report.word_count == R2_BR_WORD_LIMIT && b_report.word_unrepresented_known == 1);
    b_base(); b_dir(b_rva(0x600), 12); b_block(0x600, 0x1000, 12);
    b_put(0x608, 0xA100, 2); b_put(0x60A, 0xA108, 2);
    B_CHECK(b_parse() == R2_BR_COMPLETE); used = b_report.work_units;
    B_CHECK(used > R2_BR_INITIAL_WORK);
    B_CHECK(b_parse_limit(used - 1u) == R2_BR_PARTIAL && b_report.reason == R2_BR_WORK_CAP);
    B_CHECK(b_parse_limit(R2_BR_INITIAL_WORK) == R2_BR_PARTIAL && b_report.reason == R2_BR_WORK_CAP);
}

static void b_sentinels(void)
{
    uint32_t s;
    b_base(); memset(&b_report, 0xA5, sizeof(b_report)); memset(&b_workspace, 0x5A, sizeof(b_workspace));
    memcpy(b_saved, &b_report, sizeof(b_report)); memcpy(b_ws_saved, &b_workspace, sizeof(b_workspace));
#define B_UNTOUCHED(call, expected) do { s = (call); B_CHECK(s == (expected)); \
    B_CHECK(!memcmp(b_saved, &b_report, sizeof(b_report))); \
    B_CHECK(!memcmp(b_ws_saved, &b_workspace, sizeof(b_workspace))); } while (0)
#define B_CALL(f,n,a,l,o,os,w,ws) route2_pe_base_relocations_parse_v1((f),(n),(a),(l),(o),(os),(w),(ws))
    B_UNTOUCHED(B_CALL(b_file,B_BYTES,0,R2_BR_WORK_LIMIT,&b_report,sizeof(b_report),&b_workspace,sizeof(b_workspace)), R2_BR_BAD_ARGUMENT);
    B_UNTOUCHED(B_CALL(b_file,B_BYTES,R2_BR_ABI,R2_BR_WORK_LIMIT,&b_report,sizeof(b_report)-1,&b_workspace,sizeof(b_workspace)), R2_BR_BAD_ARGUMENT);
    B_UNTOUCHED(B_CALL(b_file,B_BYTES,R2_BR_ABI,R2_BR_WORK_LIMIT,&b_report,sizeof(b_report),&b_workspace,sizeof(b_workspace)-1), R2_BR_BAD_ARGUMENT);
    B_UNTOUCHED(B_CALL(b_file,B_BYTES,R2_BR_ABI,R2_BR_INITIAL_WORK-1,&b_report,sizeof(b_report),&b_workspace,sizeof(b_workspace)), R2_BR_BAD_ARGUMENT);
    B_UNTOUCHED(B_CALL(b_file,B_BYTES,R2_BR_ABI,R2_BR_WORK_LIMIT+1,&b_report,sizeof(b_report),&b_workspace,sizeof(b_workspace)), R2_BR_BAD_ARGUMENT);
    B_UNTOUCHED(B_CALL(NULL,B_BYTES,R2_BR_ABI,R2_BR_WORK_LIMIT,&b_report,sizeof(b_report),&b_workspace,sizeof(b_workspace)), R2_BR_BAD_ARGUMENT);
    B_UNTOUCHED(B_CALL(b_file,B_BYTES,R2_BR_ABI,R2_BR_WORK_LIMIT,NULL,sizeof(b_report),&b_workspace,sizeof(b_workspace)), R2_BR_BAD_ARGUMENT);
    B_UNTOUCHED(B_CALL(b_file,B_BYTES,R2_BR_ABI,R2_BR_WORK_LIMIT,&b_report,sizeof(b_report),NULL,sizeof(b_workspace)), R2_BR_BAD_ARGUMENT);
    B_UNTOUCHED(B_CALL((const unsigned char *)(uintptr_t)(UINTPTR_MAX-3),8,R2_BR_ABI,R2_BR_WORK_LIMIT,&b_report,sizeof(b_report),&b_workspace,sizeof(b_workspace)), R2_BR_BAD_ARGUMENT);
    B_UNTOUCHED(B_CALL(b_file,B_BYTES,R2_BR_ABI,R2_BR_WORK_LIMIT,(struct r2_br_report_v1 *)(uintptr_t)(UINTPTR_MAX-7),sizeof(b_report),&b_workspace,sizeof(b_workspace)), R2_BR_BAD_ARGUMENT);
    B_UNTOUCHED(B_CALL(b_file,B_BYTES,R2_BR_ABI,R2_BR_WORK_LIMIT,&b_report,sizeof(b_report),(struct r2_br_workspace_v1 *)(uintptr_t)(UINTPTR_MAX-7),sizeof(b_workspace)), R2_BR_BAD_ARGUMENT);
    /* Native AMD64 fixture assumption: uintptr_t represents native addresses;
     * integer-to-pointer conversion uses that implementation-defined address
     * mapping (C11 6.3.2.3p5). This is no portable ISO-C or installed-ABI claim.
     * Under this assumption these actual eight-byte-aligned object addresses
     * are <= UINTPTR_MAX-7, so uintptr_t + 1 cannot wrap. Construct the invalid
     * pointers through integers, avoiding misaligned object-pointer conversion
     * under 6.3.2.3p7. No invalid pointer is dereferenced: the parser checks
     * integer ranges/alignment before writes; both sentinel checks remain. */
    B_UNTOUCHED(B_CALL(b_file,B_BYTES,R2_BR_ABI,R2_BR_WORK_LIMIT,(struct r2_br_report_v1 *)((uintptr_t)&b_report+(uintptr_t)1u),sizeof(b_report),&b_workspace,sizeof(b_workspace)), R2_BR_BAD_ARGUMENT);
    B_UNTOUCHED(B_CALL(b_file,B_BYTES,R2_BR_ABI,R2_BR_WORK_LIMIT,&b_report,sizeof(b_report),(struct r2_br_workspace_v1 *)((uintptr_t)&b_workspace+(uintptr_t)1u),sizeof(b_workspace)), R2_BR_BAD_ARGUMENT);
    B_UNTOUCHED(B_CALL((const unsigned char *)&b_report,8,R2_BR_ABI,R2_BR_WORK_LIMIT,&b_report,sizeof(b_report),&b_workspace,sizeof(b_workspace)), R2_BR_BAD_ARGUMENT);
    B_UNTOUCHED(B_CALL((const unsigned char *)&b_workspace,8,R2_BR_ABI,R2_BR_WORK_LIMIT,&b_report,sizeof(b_report),&b_workspace,sizeof(b_workspace)), R2_BR_BAD_ARGUMENT);
    B_UNTOUCHED(B_CALL(b_file,B_BYTES,R2_BR_ABI,R2_BR_WORK_LIMIT,&b_report,sizeof(b_report),(struct r2_br_workspace_v1 *)&b_report,sizeof(b_workspace)), R2_BR_BAD_ARGUMENT);
    B_UNTOUCHED(B_CALL(b_oversize,sizeof(b_oversize),R2_BR_ABI,R2_BR_WORK_LIMIT,&b_report,sizeof(b_report),&b_workspace,sizeof(b_workspace)), R2_BR_FILE_TOO_LARGE);
#undef B_CALL
#undef B_UNTOUCHED
}

/* Defensive mapping branches below call the real private mapper with synthetic
 * workspace facts. They do NOT pass a caller report to the public parser and
 * do NOT claim parser reachability: the inherited raw parser rejects overlapping
 * header/section spans before relocation parsing, so ambiguity is redundant.
 */
static void b_defensive_mapping(void)
{
    struct r2_br_word_v1 *w;
    b_base(); B_CHECK(b_parse() == R2_BR_COMPLETE);
    b_workspace.file = b_file; b_workspace.length = sizeof(b_file);
    b_workspace.out = &b_report; b_workspace.limit = R2_BR_WORK_LIMIT;
    w = &b_report.words[0]; memset(w, 0, sizeof(*w));
    w->target_rva = 0x1FC; w->target_extent = 8;
    B_CHECK(r2_br_target_v1(&b_workspace, w));
    B_CHECK(w->target_kind == R2_BR_MAP_GAP && !(w->valid_fields & R2_BR_WORD_VALUE));
    b_report.base.sections[0].rva = 0x100; w->target_rva = 0x110;
    B_CHECK(r2_br_target_v1(&b_workspace, w));
    B_CHECK(w->target_kind == R2_BR_MAP_AMBIGUOUS && !(w->valid_fields & R2_BR_WORD_VALUE));
    b_report.base.sections[0].rva = 0x200; w->target_rva = 0x1FC;
    B_CHECK(r2_br_target_v1(&b_workspace, w));
    B_CHECK(w->target_kind == R2_BR_MAP_CROSSING && !(w->valid_fields & R2_BR_WORD_VALUE));
    w->target_rva = UINT32_MAX - 3u;
    B_CHECK(r2_br_target_v1(&b_workspace, w));
    B_CHECK(w->target_kind == R2_BR_MAP_OVERFLOW && !(w->valid_fields & R2_BR_WORD_VALUE));
}

int main(void)
{
    b_good(); b_bad_metadata(); b_limits(); b_sentinels(); b_defensive_mapping();
    return b_failures ? 1 : 0;
}
