/* SOURCE FIXTURES FIRST. UNCOMPILED / UNRUN. Invented bytes only.
 * This translation unit includes the new production TU exactly once. Future
 * harness builds must not also compile that TU or route2_mount_helper.c.
 * No claim about installed ABI, loader behavior, or executable viability.
 */
#if !defined(R2_TARGET_LINUX_START)
#error "Select R2_TARGET_LINUX_START explicitly"
#endif
#include "../../src/eating_event/route2_candidate_overlap/native/route2_elf_link_metadata.c"

#define FX_BYTES 1048576u
#define FX_VA UINT64_C(0x400000)
static unsigned char fx[FX_BYTES];
/* Separate BSS fixture keeps the oversize-file case within the accessible
 * input precondition. Its bytes are never read by the bounded parser. */
static unsigned char oversize_file[R2_ELF_RAW_FILE_LIMIT+1u];
static struct r2_elf_link_report_v1 report;
static struct r2_elf_link_workspace_v1 workspace;
static unsigned int failures;
static void expect(int v) { if (!v) ++failures; }
static void w16(size_t o, uint16_t v) { fx[o]=(unsigned char)v; fx[o+1]=(unsigned char)(v>>8); }
static void w32(size_t o, uint32_t v) { unsigned i; for(i=0;i<4;++i) fx[o+i]=(unsigned char)(v>>(8*i)); }
static void w64(size_t o, uint64_t v) { unsigned i; for(i=0;i<8;++i) fx[o+i]=(unsigned char)(v>>(8*i)); }
static void clear_fx(void) { size_t i; for(i=0;i<FX_BYTES;++i) fx[i]=0; }
static void tag(unsigned i, uint64_t t, uint64_t v) { w64(0x200u+16u*i,t); w64(0x208u+16u*i,v); }
static void program(unsigned i,uint32_t type,uint64_t off,uint64_t va,uint64_t fs,uint64_t ms) {
    size_t o=64u+56u*i; w32(o,type); w32(o+4,6); w64(o+8,off); w64(o+16,va);
    w64(o+32,fs); w64(o+40,ms); w64(o+48,1);
}
static void base_fixture(int dynamic) {
    clear_fx(); fx[0]=0x7f; fx[1]='E'; fx[2]='L'; fx[3]='F'; fx[4]=2; fx[5]=1; fx[6]=1;
    w16(16,3); w16(18,62); w32(20,1); w64(32,64); w16(52,64); w16(54,56);
    w16(56,(uint16_t)(dynamic?2:1)); program(0,1,0,FX_VA,FX_BYTES,FX_BYTES+4096u);
    if(dynamic) program(1,2,0x200,FX_VA+0x200,16u*24u,16u*24u);
}
static void symbol(unsigned i,uint32_t name,unsigned char info,uint16_t section,uint64_t value) {
    size_t o=0x1000u+24u*i; w32(o,name); fx[o+4]=info; w16(o+6,section); w64(o+8,value); w64(o+16,i?8:0);
}
static void dynamic_fixture(void) {
    base_fixture(1);
    tag(0,4,FX_VA+0x800); tag(1,6,FX_VA+0x1000); tag(2,11,24);
    tag(3,5,FX_VA+0x1800); tag(4,10,16);
    tag(5,17,FX_VA+0x2000); tag(6,18,16); tag(7,19,16);
    tag(8,7,FX_VA+0x2100); tag(9,8,24); tag(10,9,24);
    tag(11,23,FX_VA+0x2200); tag(12,2,24); tag(13,20,7); tag(14,0,0);
    w32(0x800,1); w32(0x804,3); w32(0x808,1); w32(0x80c,0); w32(0x810,2); w32(0x814,0);
    symbol(0,0,0,0,0); symbol(1,1,0x12,0,0); symbol(2,5,0x11,1,FX_VA+0x3000);
    fx[0x1801]='e'; fx[0x1802]='x'; fx[0x1803]='t';
    fx[0x1805]='d'; fx[0x1806]='e'; fx[0x1807]='f';
    w64(0x2000,FX_VA+0x3000); w64(0x2008,(UINT64_C(1)<<32)|1u);
    w64(0x2100,FX_VA+FX_BYTES); w64(0x2108,(UINT64_C(2)<<32)|8u); w64(0x2110,UINT64_MAX);
    w64(0x2200,FX_VA+0x3010); w64(0x2208,(UINT64_C(1)<<32)|7u); w64(0x2210,5);
}
static uint32_t parse_limit(uint64_t budget) {
    return route2_elf_link_metadata_parse_v1(fx,FX_BYTES,R2_ELF_LINK_ABI,&report,sizeof report,
                                            &workspace,sizeof workspace,budget);
}
static uint32_t parse(void) { return parse_limit(R2_ELF_LINK_WORK_LIMIT); }
static void plt_only_fixture(int rela) {
    unsigned i; dynamic_fixture(); for(i=0x200;i<0x380;++i) fx[i]=0;
    tag(0,4,FX_VA+0x800); tag(1,6,FX_VA+0x1000); tag(2,11,24);
    tag(3,5,FX_VA+0x1800); tag(4,10,16); tag(5,rela?9:19,rela?24:16);
    tag(6,23,FX_VA+0x2200); tag(7,2,rela?24:16); tag(8,20,rela?7:17); tag(9,0,0);
}
static void fixtures_positive(void) {
    base_fixture(0); expect(parse()==R2_ELF_LINK_COMPLETE); expect(report.symbols_retained==0);
    expect(report.base.raw_status==R2_ELF_RAW_COMPLETE); expect(report.preload_scope==R2_ELF_PRELOAD_CLOSURE_UNPROVEN);
    dynamic_fixture(); expect(parse()==R2_ELF_LINK_COMPLETE);
    expect(report.symbol_count_exact==1 && report.symbols_declared==3 && report.symbols_retained==3);
    expect(report.symbols[1].name_complete && report.symbols[1].name_length==3);
    expect(report.symbols[1].facts & R2_ELF_LINK_SYMBOL_UNDEFINED);
    expect(report.relocations_retained==3 && report.relocations[0].addend_known==0);
    expect(report.relocations[1].addend_bits==UINT64_MAX);
    expect(!report.relocations[1].target_extent_known && !report.relocations[1].target_extent_bytes);
    expect(report.relocations[1].target_class==R2_ELF_LINK_TARGET_ZERO_FILL);
    expect(report.relocations[2].source_table==R2_ELF_LINK_TABLE_PLT);
    dynamic_fixture(); tag(6,18,0); tag(9,8,0); tag(12,2,0); expect(parse()==R2_ELF_LINK_COMPLETE);
    expect(report.tables[0].present && report.tables[0].declared==0 && report.relocations_retained==0);
    plt_only_fixture(0); expect(parse()==R2_ELF_LINK_COMPLETE);
    expect(report.table_count==1 && report.relocations_retained==1 && !report.tables[0].present);
    expect(!report.relocations[0].addend_known);
    plt_only_fixture(1); expect(parse()==R2_ELF_LINK_COMPLETE);
    expect(report.table_count==1 && report.relocations_retained==1 && !report.tables[1].present);
    expect(report.relocations[0].addend_known);
    dynamic_fixture(); tag(0,0x6ffffef5u,FX_VA+0x800);
    w32(0x800,1); w32(0x804,1); w32(0x808,1); w32(0x80c,5);
    w64(0x810,0); w32(0x818,1); w32(0x81c,0x100); w32(0x820,0x101);
    expect(parse()==R2_ELF_LINK_PARTIAL); expect(!report.symbol_count_exact && report.symbol_remainder_unknown);
    expect(report.symbol_lower_bound==3 && report.symbols_retained==3);
    expect(report.hash_remainder_unknown && report.hash_valid);
    dynamic_fixture(); tag(0,30,0); expect(parse()==R2_ELF_LINK_PARTIAL);
    expect(!report.symbol_count_exact && report.symbols_retained==1 && report.symbol_remainder_unknown);
    expect(report.relocations[0].symbol_validation==R2_ELF_LINK_SYMBOL_VALID_UNKNOWN);
}
static void fixtures_malformed(void) {
    dynamic_fixture(); tag(2,11,16); parse(); expect(report.reason==R2_ELF_LINK_REASON_SYMENT);
    dynamic_fixture(); tag(7,19,24); parse(); expect(report.reason==R2_ELF_LINK_REASON_RELENT);
    dynamic_fixture(); tag(10,9,16); parse(); expect(report.reason==R2_ELF_LINK_REASON_RELAENT);
    dynamic_fixture(); tag(6,30,0); parse(); expect(report.reason==R2_ELF_LINK_REASON_TAG_PAIR);
    dynamic_fixture(); tag(7,17,FX_VA+0x2000); parse();
    expect(report.reason==R2_ELF_LINK_REASON_DUPLICATE_TAG || report.base.reason==R2_ELF_REASON_DUPLICATE_TAG);
    dynamic_fixture(); tag(6,18,17); parse(); expect(report.reason==R2_ELF_LINK_REASON_TABLE_SIZE);
    expect(report.tables[0].address==FX_VA+0x2000 && report.tables[0].byte_size==17 && !report.tables[0].complete);
    dynamic_fixture(); tag(9,8,25); parse(); expect(report.reason==R2_ELF_LINK_REASON_TABLE_SIZE);
    dynamic_fixture(); tag(12,2,25); parse(); expect(report.reason==R2_ELF_LINK_REASON_TABLE_SIZE);
    dynamic_fixture(); tag(5,17,UINT64_MAX-7u); parse(); expect(report.reason==R2_ELF_LINK_REASON_MAPPING);
    dynamic_fixture(); tag(5,17,FX_VA+FX_BYTES); parse(); expect(report.reason==R2_ELF_LINK_REASON_MAPPING);
    dynamic_fixture(); tag(5,17,FX_VA+FX_BYTES-8u); parse(); expect(report.reason==R2_ELF_LINK_REASON_MAPPING);
    dynamic_fixture(); tag(5,17,FX_VA+FX_BYTES+8192u); parse(); expect(report.reason==R2_ELF_LINK_REASON_MAPPING);
    dynamic_fixture(); w16(56,3); program(2,1,0x100,FX_VA+0x100,0x100,0x100);
    expect(parse()==R2_ELF_LINK_BASE_STOP); expect(report.base.reason==R2_ELF_REASON_LOAD_OVERLAP);
    expect(report.preload_scope==R2_ELF_PRELOAD_CLOSURE_UNPROVEN);
    dynamic_fixture(); w32(0x808,3); parse(); expect(report.reason==R2_ELF_LINK_REASON_HASH_INDEX);
    dynamic_fixture(); w32(0x810,3); parse(); expect(report.reason==R2_ELF_LINK_REASON_HASH_INDEX);
    expect(report.hash_chain_present[1] && report.hash_chain_values[1]==3 && !report.hash_valid);
    dynamic_fixture(); w32(0x814,1); parse(); expect(report.reason==R2_ELF_LINK_REASON_HASH_CYCLE);
    dynamic_fixture(); w32(0x804,0); parse(); expect(report.reason==R2_ELF_LINK_REASON_HASH_COUNT);
    dynamic_fixture(); w32(0x804,4097); parse(); expect(report.reason==R2_ELF_LINK_REASON_HASH_LIMIT);
    dynamic_fixture(); w32(0x1000,1); parse(); expect(report.reason==R2_ELF_LINK_REASON_SYMBOL_ZERO);
    dynamic_fixture(); fx[0x1800]='x'; parse(); expect(report.reason==R2_ELF_LINK_REASON_SYMBOL_ZERO);
    expect(!report.symbol_count_exact && report.symbols[0].st_name==0);
    dynamic_fixture(); w32(0x1018,16); parse(); expect(report.reason==R2_ELF_LINK_REASON_NAME_INDEX);
    expect(report.symbols_retained==1 && report.symbols[1].st_name==16 && !report.symbols[1].complete);
    dynamic_fixture(); fx[0x1801]=0x80; parse(); expect(report.reason==R2_ELF_LINK_REASON_NAME_ASCII);
    dynamic_fixture(); tag(4,10,4); fx[0x1803]='x'; parse(); expect(report.reason==R2_ELF_LINK_REASON_NAME_TERMINATOR);
    dynamic_fixture(); tag(4,10,1024); {unsigned i; for(i=1;i<513;++i) fx[0x1800+i]='x';}
    parse(); expect(report.reason==R2_ELF_LINK_REASON_NAME_LIMIT);
    dynamic_fixture(); w64(0x2108,(UINT64_C(3)<<32)|8u); parse(); expect(report.reason==R2_ELF_LINK_REASON_SYMBOL_INDEX);
    expect(report.relocations_retained==1 && report.relocations[1].symbol_index==3 && !report.relocations[1].complete);
    expect(report.relocations[1].symbol_validation==R2_ELF_LINK_SYMBOL_INVALID_EXACT);
    dynamic_fixture(); tag(11,23,FX_VA+0x2100); parse(); expect(report.reason==R2_ELF_LINK_REASON_TABLE_ALIAS);
    expect(report.relocations_retained==0); /* group validation precedes iteration */
    dynamic_fixture(); tag(14,0x6ffffff0u,FX_VA+0x2500); tag(15,0,0); fx[0x1034]=0x1a;
    expect(parse()==R2_ELF_LINK_PARTIAL); expect(report.unsupported_conditions & R2_ELF_LINK_UNSUPPORTED_VERSION);
    expect(report.symbols[2].facts & R2_ELF_LINK_SYMBOL_IFUNC);
    dynamic_fixture(); tag(14,0x12345678u,42); tag(15,0,0); parse(); expect(report.base.unknown_dynamic_count==1);
    expect(report.base.raw_status==R2_ELF_RAW_UNSUPPORTED && report.symbols_retained==3);
    dynamic_fixture(); w64(0x2000,UINT64_MAX); parse(); expect(report.relocations[0].target_class==R2_ELF_LINK_TARGET_UNMAPPED);
    dynamic_fixture(); w64(0x2000,FX_VA+FX_BYTES-1u); parse();
    expect(report.relocations[0].target_class==R2_ELF_LINK_TARGET_FILE); /* point classification, never inferred width */
    dynamic_fixture(); w16(0x101e,0xfff1); fx[0x101d]=3; parse();
    expect(report.symbols[1].facts & R2_ELF_LINK_SYMBOL_ABSOLUTE); expect(report.symbols[1].st_other==3);
    dynamic_fixture(); w16(0x101e,0xfff2); fx[0x101c]=0x16; parse();
    expect((report.symbols[1].facts & (R2_ELF_LINK_SYMBOL_COMMON|R2_ELF_LINK_SYMBOL_TLS))==(R2_ELF_LINK_SYMBOL_COMMON|R2_ELF_LINK_SYMBOL_TLS));
    dynamic_fixture(); tag(13,20,16); parse(); expect(report.reason==R2_ELF_LINK_REASON_TABLE_SIZE);
    dynamic_fixture(); tag(12,30,0); parse(); expect(report.reason==R2_ELF_LINK_REASON_TAG_PAIR);
    dynamic_fixture(); tag(0,0x6ffffef5u,FX_VA+0x800); w32(0x808,3); parse();
    expect(report.reason==R2_ELF_LINK_REASON_GNU_HEADER); /* bloom count 3 */
}
static void fixtures_limits_and_arguments(void) {
    unsigned char *p=(unsigned char *)&report,*w=(unsigned char *)&workspace; size_t i; uint32_t s;
    dynamic_fixture(); for(i=0;i<sizeof report;++i) p[i]=0xa5;
    for(i=0;i<sizeof workspace;++i) w[i]=0x5a;
    s=route2_elf_link_metadata_parse_v1(fx,FX_BYTES,99,&report,sizeof report,&workspace,sizeof workspace,R2_ELF_LINK_WORK_LIMIT);
    expect(s==R2_ELF_LINK_BAD_ARGUMENT); for(i=0;i<sizeof report;++i) expect(p[i]==0xa5);
    expect(route2_elf_link_metadata_parse_v1(fx,FX_BYTES,1,&report,sizeof report-1,&workspace,sizeof workspace,R2_ELF_LINK_WORK_LIMIT)==R2_ELF_LINK_BAD_ARGUMENT);
    expect(route2_elf_link_metadata_parse_v1(fx,FX_BYTES,1,&report,sizeof report,NULL,sizeof workspace,R2_ELF_LINK_WORK_LIMIT)==R2_ELF_LINK_BAD_ARGUMENT);
    expect(route2_elf_link_metadata_parse_v1(fx,FX_BYTES,1,NULL,sizeof report,&workspace,sizeof workspace,R2_ELF_LINK_WORK_LIMIT)==R2_ELF_LINK_BAD_ARGUMENT);
    expect(route2_elf_link_metadata_parse_v1(fx,FX_BYTES,1,(struct r2_elf_link_report_v1 *)(p+1),sizeof report,&workspace,sizeof workspace,R2_ELF_LINK_WORK_LIMIT)==R2_ELF_LINK_BAD_ARGUMENT);
    expect(route2_elf_link_metadata_parse_v1(fx,FX_BYTES,1,&report,sizeof report,(struct r2_elf_link_workspace_v1 *)&report,sizeof workspace,R2_ELF_LINK_WORK_LIMIT)==R2_ELF_LINK_BAD_ARGUMENT);
    expect(route2_elf_link_metadata_parse_v1(fx,FX_BYTES,1,&report,sizeof report,(struct r2_elf_link_workspace_v1 *)(w+1),sizeof workspace,R2_ELF_LINK_WORK_LIMIT)==R2_ELF_LINK_BAD_ARGUMENT);
    expect(route2_elf_link_metadata_parse_v1((const unsigned char *)&workspace,16,1,&report,sizeof report,&workspace,sizeof workspace,R2_ELF_LINK_WORK_LIMIT)==R2_ELF_LINK_BAD_ARGUMENT);
    expect(route2_elf_link_metadata_parse_v1(fx,FX_BYTES,1,(struct r2_elf_link_report_v1 *)(uintptr_t)(UINTPTR_MAX-7u),sizeof report,&workspace,sizeof workspace,R2_ELF_LINK_WORK_LIMIT)==R2_ELF_LINK_BAD_ARGUMENT);
    expect(route2_elf_link_metadata_parse_v1(fx,FX_BYTES,1,&report,sizeof report,(struct r2_elf_link_workspace_v1 *)(uintptr_t)(UINTPTR_MAX-7u),sizeof workspace,R2_ELF_LINK_WORK_LIMIT)==R2_ELF_LINK_BAD_ARGUMENT);
    expect(route2_elf_link_metadata_parse_v1((const unsigned char *)(uintptr_t)(UINTPTR_MAX-7u),16,1,&report,sizeof report,&workspace,sizeof workspace,R2_ELF_LINK_WORK_LIMIT)==R2_ELF_LINK_BAD_ARGUMENT);
    expect(route2_elf_link_metadata_parse_v1((const unsigned char *)&report,16,1,&report,sizeof report,&workspace,sizeof workspace,R2_ELF_LINK_WORK_LIMIT)==R2_ELF_LINK_BAD_ARGUMENT);
    expect(route2_elf_link_metadata_parse_v1(fx,FX_BYTES,1,&report,sizeof report,&workspace,sizeof workspace,1)==R2_ELF_LINK_BAD_ARGUMENT);
    for(i=0;i<sizeof report;++i) expect(p[i]==0xa5);
    for(i=0;i<sizeof workspace;++i) expect(w[i]==0x5a);
    base_fixture(0); s=route2_elf_link_metadata_parse_v1(oversize_file,sizeof oversize_file,1,&report,sizeof report,&workspace,sizeof workspace,R2_ELF_LINK_WORK_LIMIT);
    expect(s==R2_ELF_LINK_BASE_STOP && report.base.reason==R2_ELF_REASON_FILE_LIMIT);
    dynamic_fixture(); s=parse_limit(R2_ELF_LINK_INITIAL_WORK); expect(s==R2_ELF_LINK_INCOMPLETE && report.reason==R2_ELF_LINK_REASON_WORK);
    dynamic_fixture(); tag(6,18,UINT64_C(8193)*16u); parse(); expect(report.reason==R2_ELF_LINK_REASON_RELOCATION_LIMIT);
    /* No fixture uses a real executable, OS mapping, loader, or OS helper.
     * Target crossing is deliberately not tested: no target width is inferred.
     */
}
static void fixtures_full_record_and_name_caps(void) {
    unsigned i; uint32_t s;
    dynamic_fixture(); tag(1,6,FX_VA+0x10000); tag(3,5,FX_VA+0x30000); tag(4,10,1024);
    w32(0x800,1); w32(0x804,4096); w32(0x808,0);
    for(i=0;i<4096;++i) { size_t o=0x10000u+24u*i; w32(0x80cu+4u*i,0);
        w64(o,0); w64(o+8,0); w64(o+16,0); }
    s=parse(); expect(s==R2_ELF_LINK_COMPLETE && report.symbols_retained==4096 && report.symbol_count_exact);
    for(i=1;i<4096;++i) w32(0x10000u+24u*i,1);
    for(i=1;i<512;++i) fx[0x30000u+i]='a';
    fx[0x30200]=0;
    s=parse(); expect(s==R2_ELF_LINK_INCOMPLETE && report.reason==R2_ELF_LINK_REASON_NAME_BYTES);
    expect(report.names_inspected_bytes==R2_ELF_LINK_NAME_BYTES_LIMIT);
    expect(report.symbols_retained>0 && report.symbol_remainder_unknown);
    dynamic_fixture(); tag(5,17,FX_VA+0x40000); tag(6,18,UINT64_C(8192)*16u); tag(9,8,0); tag(12,2,0);
    for(i=0;i<8192;++i) { w64(0x40000u+16u*i,FX_VA+0x60000); w64(0x40008u+16u*i,0); }
    s=parse(); expect(s==R2_ELF_LINK_COMPLETE && report.relocations_retained==8192 && !report.relocation_remainder_unknown);
    dynamic_fixture(); w32(0x800,4097); parse(); expect(report.reason==R2_ELF_LINK_REASON_HASH_LIMIT);
    dynamic_fixture(); tag(14,34,FX_VA+0x2500); tag(15,35,8); tag(16,36,FX_VA+0x2600); tag(17,37,8); tag(18,0,0);
    parse(); expect(report.unsupported_conditions & R2_ELF_LINK_UNSUPPORTED_SHNDX);
    expect(report.unsupported_conditions & R2_ELF_LINK_UNSUPPORTED_RELR);
    expect(report.relocation_remainder_unknown && !report.metadata_complete);
    /* Long repeated GNU bucket chains reach the real fixed work ceiling while
     * every raw count remains within its independent finite array limit. */
    dynamic_fixture(); tag(0,0x6ffffef5u,FX_VA+0x800);
    w32(0x800,4096); w32(0x804,1); w32(0x808,1); w32(0x80c,5); w64(0x810,0);
    for(i=0;i<4096;++i) w32(0x818u+4u*i,1);
    for(i=0;i<4095;++i) w32(0x4818u+4u*i,i==4094?0x101:0x100);
    s=parse(); expect(s==R2_ELF_LINK_INCOMPLETE && report.reason==R2_ELF_LINK_REASON_WORK);
    expect(report.work_units<=R2_ELF_LINK_WORK_LIMIT && report.hash_remainder_unknown);
}
int main(void) { fixtures_positive(); fixtures_malformed(); fixtures_limits_and_arguments(); fixtures_full_record_and_name_caps(); return failures?1:0; }
