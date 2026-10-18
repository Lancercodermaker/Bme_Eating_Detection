/* SOURCE ONLY. Future builds select this TU INSTEAD OF the included core.
 * Format references (not claims about an installed loader):
 * https://gabi.xinuos.com/elf/08-dynamic.html
 * https://gabi.xinuos.com/elf/05-symtab.html
 * https://gabi.xinuos.com/elf/06-reloc.html
 * https://raw.githubusercontent.com/bminor/glibc/glibc-2.35/elf/elf.h
 */
/* Feature selection must precede the header's first glibc system include. */
#if defined(R2_TARGET_LINUX_START)
#ifndef _GNU_SOURCE
#define _GNU_SOURCE
#endif
#endif
#include "route2_elf_link_metadata.h"
#if defined(R2_TARGET_LINUX_START)
#include "route2_mount_helper.c"

_Static_assert(sizeof(struct r2_elf_link_symbol_v1)==72,"symbol ABI");
_Static_assert(sizeof(struct r2_elf_link_relocation_v1)==80,"relocation ABI");
_Static_assert(sizeof(struct r2_elf_link_table_v1)==56,"table ABI");
_Static_assert(sizeof(struct r2_elf_link_report_v1)==R2_ELF_LINK_REPORT_BYTES,"report ABI");
_Static_assert(sizeof(struct r2_elf_link_workspace_v1)==R2_ELF_LINK_WORKSPACE_BYTES,"workspace ABI");
_Static_assert(_Alignof(struct r2_elf_link_report_v1)==R2_ELF_LINK_ALIGNMENT,"report alignment");
_Static_assert(_Alignof(struct r2_elf_link_workspace_v1)==R2_ELF_LINK_ALIGNMENT,"workspace alignment");
_Static_assert(R2_ELF_LINK_INITIAL_WORK<R2_ELF_LINK_WORK_LIMIT,"initial reservation");

enum r2_lm_slot {
    LM_HASH,LM_SYM,LM_SYMENT,LM_STR,LM_STRSZ,LM_REL,LM_RELSZ,LM_RELENT,
    LM_RELA,LM_RELASZ,LM_RELAENT,LM_JMPREL,LM_PLTSZ,LM_PLTREL,LM_GNUHASH
};
struct r2_lm_context {
    const unsigned char *file;
    uint64_t length,limit;
    struct r2_elf_link_report_v1 *r;
    struct r2_elf_link_workspace_v1 *w;
};
static int r2_lm_fail(struct r2_lm_context *c,uint32_t status,uint32_t reason,
                      uint64_t offset,uint64_t value,uint32_t subject) {
    if(!c->r->reason) { c->r->reason=reason; c->r->failure_offset=offset;
        c->r->failure_value=value; c->r->failure_subject=subject; }
    c->r->status=status; return 0;
}
static int r2_lm_charge(struct r2_lm_context *c,uint64_t amount,uint64_t offset) {
    if(amount>c->limit-c->r->work_units)
        return r2_lm_fail(c,R2_ELF_LINK_INCOMPLETE,R2_ELF_LINK_REASON_WORK,offset,amount,0);
    c->r->work_units+=amount; return 1;
}
static int r2_lm_range(struct r2_lm_context *c,uint64_t offset,uint64_t n) {
    if(offset>c->length || n>c->length-offset)
        return r2_lm_fail(c,R2_ELF_LINK_REJECTED,R2_ELF_LINK_REASON_MAPPING,offset,n,0);
    return 1;
}
static int r2_lm_read(struct r2_lm_context *c,uint64_t offset,unsigned n,uint64_t *v) {
    unsigned i; uint64_t a=0;
    if(!r2_lm_charge(c,16u+4u*n,offset) || !r2_lm_range(c,offset,n)) return 0;
    for(i=0;i<n;++i) a|=(uint64_t)c->file[(size_t)(offset+i)]<<(8u*i);
    *v=a; return 1;
}
/* A metadata interval must have exactly one containing LOAD memory interval,
 * then fit that LOAD's FILE bytes. Empty intervals still require an anchored
 * FILE byte, preserving absent versus present-zero without accepting a bogus
 * pointer. Address arithmetic is unsigned and checked before addition.
 */
static int r2_lm_map(struct r2_lm_context *c,uint64_t address,uint64_t n,
                     uint64_t subject,uint64_t *offset) {
    uint32_t i,hits=0; uint64_t found=0,amount=n?n:1;
    if(!r2_lm_charge(c,32,subject)) return 0;
    if(amount>UINT64_MAX-address)
        return r2_lm_fail(c,R2_ELF_LINK_REJECTED,R2_ELF_LINK_REASON_MAPPING,subject,address,0);
    for(i=0;i<c->r->base.program_count;++i) {
        const struct r2_elf_raw_program_v1 *p; uint64_t delta;
        if(!r2_lm_charge(c,48,subject)) return 0;
        p=&c->r->base.programs[i]; if(p->type!=1 || address<p->virtual_address) continue;
        delta=address-p->virtual_address;
        if(delta>=p->memory_size || amount>p->memory_size-delta) continue;
        ++hits;
        if(delta>p->file_size || amount>p->file_size-delta || delta>UINT64_MAX-p->file_offset)
            return r2_lm_fail(c,R2_ELF_LINK_REJECTED,R2_ELF_LINK_REASON_MAPPING,subject,address,0);
        found=p->file_offset+delta;
    }
    if(hits!=1 || !r2_lm_range(c,found,amount))
        return r2_lm_fail(c,R2_ELF_LINK_REJECTED,R2_ELF_LINK_REASON_MAPPING,subject,address,0);
    *offset=found; return 1;
}
static int r2_lm_slot_for(uint64_t t) {
    switch(t) {
    case 4:return LM_HASH; case 6:return LM_SYM; case 11:return LM_SYMENT;
    case 5:return LM_STR; case 10:return LM_STRSZ;
    case 17:return LM_REL; case 18:return LM_RELSZ; case 19:return LM_RELENT;
    case 7:return LM_RELA; case 8:return LM_RELASZ; case 9:return LM_RELAENT;
    case 23:return LM_JMPREL; case 2:return LM_PLTSZ; case 20:return LM_PLTREL;
    case UINT64_C(0x6ffffef5):return LM_GNUHASH; default:return -1;
    }
}
static int r2_lm_tags(struct r2_lm_context *c) {
    uint32_t i;
    if(!r2_lm_charge(c,32,0)) return 0;
    for(i=0;i<c->r->base.dynamic_count;++i) {
        const struct r2_elf_raw_dynamic_v1 *d; int slot; uint64_t t;
        if(!r2_lm_charge(c,128,0)) return 0;
        d=&c->r->base.dynamics[i]; t=d->raw_tag; slot=r2_lm_slot_for(t);
        if(slot>=0) {
            struct r2_elf_link_tag_v1 *x=&c->w->tags[slot];
            if(x->present) return r2_lm_fail(c,R2_ELF_LINK_REJECTED,R2_ELF_LINK_REASON_DUPLICATE_TAG,d->file_offset,t,(uint32_t)slot);
            x->value=d->raw_value; x->offset=d->file_offset; x->present=1;
        }
        if(t==UINT64_C(0x6ffffff0) || t==UINT64_C(0x6ffffffc) ||
           t==UINT64_C(0x6ffffffd) || t==UINT64_C(0x6ffffffe) || t==UINT64_C(0x6fffffff))
            c->r->unsupported_conditions|=R2_ELF_LINK_UNSUPPORTED_VERSION;
        if(t==34) c->r->unsupported_conditions|=R2_ELF_LINK_UNSUPPORTED_SHNDX;
        if(t==35 || t==36 || t==37) c->r->unsupported_conditions|=R2_ELF_LINK_UNSUPPORTED_RELR;
        if(d->interpretation==R2_ELF_DYNAMIC_UNKNOWN) c->r->unsupported_conditions|=R2_ELF_LINK_UNSUPPORTED_UNKNOWN;
    }
    return 1;
}
static int r2_lm_sym_group(struct r2_lm_context *c) {
    struct r2_elf_link_tag_v1 *t=c->w->tags;
    if(!r2_lm_charge(c,128,0)) return 0;
    if(t[LM_SYM].present!=t[LM_SYMENT].present ||
       (t[LM_SYM].present && (!t[LM_STR].present || !t[LM_STRSZ].present)) ||
       ((t[LM_HASH].present || t[LM_GNUHASH].present) && !t[LM_SYM].present))
        return r2_lm_fail(c,R2_ELF_LINK_REJECTED,R2_ELF_LINK_REASON_TAG_PAIR,c->r->base.dynamic_offset,0,LM_SYM);
    if(t[LM_SYMENT].present && t[LM_SYMENT].value!=24)
        return r2_lm_fail(c,R2_ELF_LINK_REJECTED,R2_ELF_LINK_REASON_SYMENT,t[LM_SYMENT].offset,t[LM_SYMENT].value,LM_SYMENT);
    return 1;
}
/* SysV nchain is exact ONLY after the entire hash table and every functional
 * chain have been validated. Global color traversal is linear, not nchain^2.
 * Index zero is the sentinel; the raw chains[0] is bounded but never followed.
 */
static int r2_lm_sysv(struct r2_lm_context *c) {
    struct r2_elf_link_tag_v1 *t=&c->w->tags[LM_HASH];
    uint64_t o,a,b,x,span; uint32_t i,n,nb;
    if(!r2_lm_charge(c,128,t->offset) || !r2_lm_map(c,t->value,8,t->offset,&o) ||
       !r2_lm_read(c,o,4,&a) || !r2_lm_read(c,o+4,4,&b)) return 0;
    c->r->hash_kind=1; c->r->hash_buckets=(uint32_t)a; c->r->hash_chains=(uint32_t)b;
    if(!a || !b) return r2_lm_fail(c,R2_ELF_LINK_REJECTED,R2_ELF_LINK_REASON_HASH_COUNT,o,b,LM_HASH);
    if(a>R2_ELF_LINK_HASH_LIMIT || b>R2_ELF_LINK_SYMBOL_LIMIT)
        return r2_lm_fail(c,R2_ELF_LINK_INCOMPLETE,R2_ELF_LINK_REASON_HASH_LIMIT,o,b,LM_HASH);
    nb=(uint32_t)a; n=(uint32_t)b; span=8u+4u*(a+b);
    if(!r2_lm_map(c,t->value,span,t->offset,&o)) return 0;
    for(i=0;i<nb;++i) {
        if(!r2_lm_read(c,o+8u+4u*i,4,&x)) return 0;
        c->r->hash_bucket_values[i]=(uint32_t)x;
        ++c->r->hash_buckets_retained;
        if(x>=n) return r2_lm_fail(c,R2_ELF_LINK_REJECTED,R2_ELF_LINK_REASON_HASH_INDEX,o+8u+4u*i,x,LM_HASH);
    }
    for(i=0;i<n;++i) {
        if(!r2_lm_read(c,o+8u+4u*nb+4u*i,4,&x)) return 0;
        c->r->hash_chain_values[i]=(uint32_t)x;
        c->r->hash_chain_present[i]=1;
        ++c->r->hash_chains_retained;
        if(x>=n) return r2_lm_fail(c,R2_ELF_LINK_REJECTED,R2_ELF_LINK_REASON_HASH_INDEX,o+8u+4u*nb+4u*i,x,LM_HASH);
    }
    for(i=1;i<n;++i) {
        uint32_t j=i;
        if(!r2_lm_charge(c,24,o)) return 0;
        while(j) {
            if(!r2_lm_charge(c,32,o)) return 0;
            if(c->w->chain_state[j]) break;
            c->w->chain_state[j]=1; j=c->r->hash_chain_values[j];
        }
        if(j && c->w->chain_state[j]==1)
            return r2_lm_fail(c,R2_ELF_LINK_REJECTED,R2_ELF_LINK_REASON_HASH_CYCLE,o+8u+4u*nb+4u*j,j,LM_HASH);
        j=i;
        while(j) {
            if(!r2_lm_charge(c,32,o)) return 0;
            if(c->w->chain_state[j]!=1) break;
            c->w->chain_state[j]=2; j=c->r->hash_chain_values[j];
        }
    }
    if(!r2_lm_charge(c,32,o)) return 0;
    c->r->hash_valid=1; c->r->hash_remainder_unknown=0; c->r->symbol_lower_bound=n;
    c->r->symbols_declared=n;
    return 1;
}
/* GNU-only is a bounded lower-bound parser. It does NOT infer an exact dynsym
 * count, even after bucket chains terminate. Bloom words are raw facts.
 * The maximum chain slot examined is 4095 and each bucket traversal is charged.
 */
static int r2_lm_gnu(struct r2_lm_context *c) {
    struct r2_elf_link_tag_v1 *t=&c->w->tags[LM_GNUHASH];
    uint64_t o,a,b,d,e,x,bo,co,header_span; uint32_t i,lower;
    if(!r2_lm_charge(c,128,t->offset) || !r2_lm_map(c,t->value,16,t->offset,&o) ||
       !r2_lm_read(c,o,4,&a) || !r2_lm_read(c,o+4,4,&b) ||
       !r2_lm_read(c,o+8,4,&d) || !r2_lm_read(c,o+12,4,&e)) return 0;
    c->r->hash_kind=2; c->r->hash_buckets=(uint32_t)a;
    c->r->gnu_symbol_offset=(uint32_t)b; c->r->gnu_bloom_count=(uint32_t)d; c->r->gnu_bloom_shift=(uint32_t)e;
    if(!a || !d || !b || (d&(d-1)) || e>=64)
        return r2_lm_fail(c,R2_ELF_LINK_REJECTED,R2_ELF_LINK_REASON_GNU_HEADER,o,b,LM_GNUHASH);
    if(a>R2_ELF_LINK_HASH_LIMIT || d>R2_ELF_LINK_HASH_LIMIT || b>R2_ELF_LINK_SYMBOL_LIMIT)
        return r2_lm_fail(c,R2_ELF_LINK_INCOMPLETE,R2_ELF_LINK_REASON_HASH_LIMIT,o,b,LM_GNUHASH);
    header_span=16u+8u*d+4u*a;
    if(!r2_lm_map(c,t->value,header_span,t->offset,&o)) return 0;
    bo=o+16u+8u*d; co=bo+4u*a; lower=(uint32_t)b;
    for(i=0;i<(uint32_t)d;++i) {
        if(!r2_lm_read(c,o+16u+8u*i,8,&x)) return 0;
        c->r->gnu_bloom_values[i]=x;
        ++c->r->gnu_bloom_retained;
    }
    for(i=0;i<(uint32_t)a;++i) {
        uint32_t index;
        if(!r2_lm_read(c,bo+4u*i,4,&x)) return 0;
        c->r->hash_bucket_values[i]=(uint32_t)x; index=(uint32_t)x;
        ++c->r->hash_buckets_retained;
        if(!index) continue;
        if(index<b || index>=R2_ELF_LINK_SYMBOL_LIMIT)
            return r2_lm_fail(c,R2_ELF_LINK_REJECTED,R2_ELF_LINK_REASON_HASH_INDEX,bo+4u*i,index,LM_GNUHASH);
        for(;;++index) {
            uint64_t span,chainoff;
            if(!r2_lm_charge(c,48,co) ) return 0;
            if(index>=R2_ELF_LINK_SYMBOL_LIMIT)
                return r2_lm_fail(c,R2_ELF_LINK_INCOMPLETE,R2_ELF_LINK_REASON_HASH_LIMIT,co,index,LM_GNUHASH);
            span=header_span+4u*((uint64_t)index-b+1u);
            if(!r2_lm_map(c,t->value,span,t->offset,&chainoff) ||
               !r2_lm_read(c,chainoff+header_span+4u*((uint64_t)index-b),4,&x)) return 0;
            c->r->hash_chain_values[index-(uint32_t)b]=(uint32_t)x;
            c->r->hash_chain_present[index-(uint32_t)b]=1;
            if(!c->w->chain_state[index-(uint32_t)b]) {
                c->w->chain_state[index-(uint32_t)b]=1;
                ++c->r->hash_chains_retained;
            }
            if(index+1u>lower) lower=index+1u;
            if(index-(uint32_t)b+1u>c->r->hash_chains) c->r->hash_chains=index-(uint32_t)b+1u;
            if(x&1u) break;
        }
    }
    if(!r2_lm_charge(c,32,o)) return 0;
    c->r->hash_valid=1; c->r->symbol_lower_bound=lower;
    /* Referenced GNU chains finished; an unreferenced tail remains UNKNOWN. */
    c->r->unsupported_conditions|=R2_ELF_LINK_UNSUPPORTED_HASH_COUNT;
    return 1;
}
static int r2_lm_name(struct r2_lm_context *c,struct r2_elf_link_symbol_v1 *s,
                      uint64_t stringoff,uint64_t stringsize) {
    uint32_t j; uint64_t ch,remaining;
    if(!r2_lm_charge(c,64,s->file_offset)) return 0;
    if(s->st_name>=stringsize)
        return r2_lm_fail(c,R2_ELF_LINK_REJECTED,R2_ELF_LINK_REASON_NAME_INDEX,s->file_offset,s->st_name,s->symbol_index);
    s->name_file_offset=stringoff+s->st_name; remaining=stringsize-s->st_name;
    for(j=0;j<R2_ELF_LINK_NAME_LIMIT && j<remaining;++j) {
        if(!r2_lm_charge(c,16,s->name_file_offset+j)) return 0;
        if(c->r->names_inspected_bytes==R2_ELF_LINK_NAME_BYTES_LIMIT)
            return r2_lm_fail(c,R2_ELF_LINK_INCOMPLETE,R2_ELF_LINK_REASON_NAME_BYTES,s->name_file_offset+j,j,s->symbol_index);
        ++c->r->names_inspected_bytes;
        /* The whole string table was mapped before this scan. Sixteen units
         * prepay this read, counter/ASCII/NUL tests, stores and next loop test;
         * do not charge a second generic-read overhead for the same byte. */
        ch=c->file[(size_t)(s->name_file_offset+j)];
        if(ch>127) return r2_lm_fail(c,R2_ELF_LINK_PARTIAL,R2_ELF_LINK_REASON_NAME_ASCII,s->name_file_offset+j,ch,s->symbol_index);
        if(!ch) { s->name_length=j; s->name_complete=1; return 1; }
    }
    return r2_lm_fail(c,j==R2_ELF_LINK_NAME_LIMIT?R2_ELF_LINK_INCOMPLETE:R2_ELF_LINK_REJECTED,
        j==R2_ELF_LINK_NAME_LIMIT?R2_ELF_LINK_REASON_NAME_LIMIT:R2_ELF_LINK_REASON_NAME_TERMINATOR,
        s->name_file_offset+j,j,s->symbol_index);
}
static int r2_lm_symbols(struct r2_lm_context *c) {
    struct r2_elf_link_tag_v1 *t=c->w->tags; uint64_t o,so,x; uint32_t i,n;
    if(!r2_lm_charge(c,96,0)) return 0;
    if(!t[LM_SYM].present) { c->r->symbol_remainder_unknown=0; return 1; }
    if(!c->r->symbol_lower_bound) {
        c->r->symbol_lower_bound=1;
        c->r->unsupported_conditions|=R2_ELF_LINK_UNSUPPORTED_HASH_COUNT;
    }
    n=c->r->symbol_lower_bound;
    if(!r2_lm_map(c,t[LM_SYM].value,(uint64_t)n*24u,t[LM_SYM].offset,&o) ||
       !r2_lm_map(c,t[LM_STR].value,t[LM_STRSZ].value,t[LM_STR].offset,&so)) return 0;
    if(!t[LM_STRSZ].value)
        return r2_lm_fail(c,R2_ELF_LINK_REJECTED,R2_ELF_LINK_REASON_NAME_INDEX,t[LM_STRSZ].offset,0,0);
    for(i=0;i<n;++i) {
        struct r2_elf_link_symbol_v1 *s;
        if(!r2_lm_charge(c,192,o+24u*i)) return 0;
        s=&c->r->symbols[i]; s->symbol_index=i; s->file_offset=o+24u*i;
        if(!r2_lm_read(c,s->file_offset,4,&x)) return 0;
        s->st_name=(uint32_t)x;
        if(!r2_lm_read(c,s->file_offset+4,1,&x)) return 0;
        s->st_info=(uint32_t)x;
        if(!r2_lm_read(c,s->file_offset+5,1,&x)) return 0;
        s->st_other=(uint32_t)x;
        if(!r2_lm_read(c,s->file_offset+6,2,&x)) return 0;
        s->st_shndx=(uint32_t)x;
        if(!r2_lm_read(c,s->file_offset+8,8,&s->st_value) || !r2_lm_read(c,s->file_offset+16,8,&s->st_size)) return 0;
        if(!s->st_shndx) s->facts|=R2_ELF_LINK_SYMBOL_UNDEFINED;
        if(s->st_shndx==0xfff1u) s->facts|=R2_ELF_LINK_SYMBOL_ABSOLUTE;
        if(s->st_shndx==0xfff2u) s->facts|=R2_ELF_LINK_SYMBOL_COMMON;
        if((s->st_info&15u)==10) s->facts|=R2_ELF_LINK_SYMBOL_IFUNC;
        if((s->st_info&15u)==6) s->facts|=R2_ELF_LINK_SYMBOL_TLS;
        if(!i && (s->st_name || s->st_info || s->st_other || s->st_shndx || s->st_value || s->st_size))
            return r2_lm_fail(c,R2_ELF_LINK_REJECTED,R2_ELF_LINK_REASON_SYMBOL_ZERO,s->file_offset,0,0);
        if(!r2_lm_name(c,s,so,t[LM_STRSZ].value)) return 0;
        if(!i && s->name_length)
            return r2_lm_fail(c,R2_ELF_LINK_REJECTED,R2_ELF_LINK_REASON_SYMBOL_ZERO,s->name_file_offset,s->name_length,0);
        if(!i && c->r->hash_kind==1 && c->r->hash_valid) c->r->symbol_count_exact=1;
        s->complete=1; ++c->r->symbols_retained;
    }
    if(c->r->symbol_count_exact) c->r->symbol_remainder_unknown=0;
    return 1;
}
static int r2_lm_table_group(struct r2_lm_context *c,unsigned i,unsigned a,unsigned z,unsigned e,uint32_t entry) {
    struct r2_elf_link_tag_v1 *t=c->w->tags; struct r2_elf_link_table_v1 *p=&c->r->tables[i];
    if(!r2_lm_charge(c,128,0)) return 0;
    p->kind=i+1; p->present=t[a].present || t[z].present;
    /* RELENT/RELAENT may describe a PLT-only format without a base REL(A)
     * address/size pair. They are format facts, not phantom empty tables. */
    if(t[e].present && t[e].value!=entry)
        return r2_lm_fail(c,R2_ELF_LINK_REJECTED,entry==16?R2_ELF_LINK_REASON_RELENT:R2_ELF_LINK_REASON_RELAENT,t[e].offset,t[e].value,i+1);
    if(!p->present) { p->complete=1; return 1; }
    ++c->r->table_count; p->address=t[a].value; p->byte_size=t[z].value; p->entry_size=entry;
    if(!t[a].present || !t[z].present || !t[e].present)
        return r2_lm_fail(c,R2_ELF_LINK_REJECTED,R2_ELF_LINK_REASON_TAG_PAIR,c->r->base.dynamic_offset,i,i+1);
    if(p->byte_size%entry)
        return r2_lm_fail(c,R2_ELF_LINK_REJECTED,R2_ELF_LINK_REASON_TABLE_SIZE,t[z].offset,p->byte_size,i+1);
    p->declared=p->byte_size/entry;
    if(p->declared>UINT64_MAX-c->r->relocations_declared)
        return r2_lm_fail(c,R2_ELF_LINK_REJECTED,R2_ELF_LINK_REASON_TABLE_SIZE,t[z].offset,p->declared,i+1);
    c->r->relocations_declared+=p->declared;
    return 1;
}
static int r2_lm_tables(struct r2_lm_context *c) {
    struct r2_elf_link_tag_v1 *t=c->w->tags; struct r2_elf_link_table_v1 *p=&c->r->tables[2]; uint32_t i,j;
    if(!r2_lm_table_group(c,0,LM_REL,LM_RELSZ,LM_RELENT,16) ||
       !r2_lm_table_group(c,1,LM_RELA,LM_RELASZ,LM_RELAENT,24) || !r2_lm_charge(c,128,0)) return 0;
    p->kind=R2_ELF_LINK_TABLE_PLT; p->present=t[LM_JMPREL].present || t[LM_PLTSZ].present || t[LM_PLTREL].present;
    if(p->present) {
        ++c->r->table_count; p->address=t[LM_JMPREL].value; p->byte_size=t[LM_PLTSZ].value;
        if(!t[LM_JMPREL].present || !t[LM_PLTSZ].present || !t[LM_PLTREL].present)
            return r2_lm_fail(c,R2_ELF_LINK_REJECTED,R2_ELF_LINK_REASON_TAG_PAIR,c->r->base.dynamic_offset,2,3);
        if(t[LM_PLTREL].value!=17 && t[LM_PLTREL].value!=7)
            return r2_lm_fail(c,R2_ELF_LINK_REJECTED,R2_ELF_LINK_REASON_TABLE_SIZE,t[LM_PLTREL].offset,t[LM_PLTREL].value,3);
        p->entry_size=t[LM_PLTREL].value==17?16:24;
        if(p->byte_size%p->entry_size)
            return r2_lm_fail(c,R2_ELF_LINK_REJECTED,R2_ELF_LINK_REASON_TABLE_SIZE,t[LM_PLTSZ].offset,p->byte_size,3);
        p->declared=p->byte_size/p->entry_size;
        if(p->declared>UINT64_MAX-c->r->relocations_declared)
            return r2_lm_fail(c,R2_ELF_LINK_REJECTED,R2_ELF_LINK_REASON_TABLE_SIZE,t[LM_PLTSZ].offset,p->declared,3);
        c->r->relocations_declared+=p->declared;
    } else p->complete=1;
    if(c->r->relocations_declared>R2_ELF_LINK_RELOCATION_LIMIT)
        return r2_lm_fail(c,R2_ELF_LINK_INCOMPLETE,R2_ELF_LINK_REASON_RELOCATION_LIMIT,0,c->r->relocations_declared,0);
    if(c->r->relocations_declared && !c->r->symbol_count_exact) {
        c->r->symbol_remainder_unknown=1;
        c->r->unsupported_conditions|=R2_ELF_LINK_UNSUPPORTED_HASH_COUNT;
    }
    for(i=0;i<3;++i) {
        p=&c->r->tables[i]; if(!r2_lm_charge(c,32,0)) return 0;
        if(p->present && !r2_lm_map(c,p->address,p->byte_size,c->r->base.dynamic_offset,&p->file_offset)) return 0;
    }
    /* Reject all relocation table aliases, including REL/RELA overlap. Both
     * virtual and original FILE spans are compared; empty spans do not alias.
     */
    for(i=0;i<3;++i) for(j=i+1;j<3;++j) {
        struct r2_elf_link_table_v1 *a=&c->r->tables[i],*b=&c->r->tables[j];
        if(!r2_lm_charge(c,64,0)) return 0;
        if(!a->present || !b->present || !a->byte_size || !b->byte_size) continue;
        if((a->address<b->address+b->byte_size && b->address<a->address+a->byte_size) ||
           (a->file_offset<b->file_offset+b->byte_size && b->file_offset<a->file_offset+a->byte_size)) {
            c->r->unsupported_conditions|=R2_ELF_LINK_UNSUPPORTED_ALIAS;
            return r2_lm_fail(c,R2_ELF_LINK_PARTIAL,R2_ELF_LINK_REASON_TABLE_ALIAS,b->file_offset,b->address,j+1);
        }
    }
    return 1;
}
static int r2_lm_target(struct r2_lm_context *c,struct r2_elf_link_relocation_v1 *s) {
    uint32_t i,hits=0;
    if(!r2_lm_charge(c,32,s->file_offset)) return 0;
    s->target_class=R2_ELF_LINK_TARGET_UNMAPPED; s->target_program=UINT32_MAX;
    for(i=0;i<c->r->base.program_count;++i) {
        const struct r2_elf_raw_program_v1 *p; uint64_t d;
        if(!r2_lm_charge(c,48,s->file_offset)) return 0;
        p=&c->r->base.programs[i]; if(p->type!=1 || s->r_offset<p->virtual_address) continue;
        d=s->r_offset-p->virtual_address; if(d>=p->memory_size) continue;
        ++hits; s->target_program=i;
        if(d<p->file_size) { s->target_class=R2_ELF_LINK_TARGET_FILE; s->target_file_offset=p->file_offset+d; }
        else { s->target_class=R2_ELF_LINK_TARGET_ZERO_FILL; s->target_file_offset=0; }
    }
    if(hits>1) { s->target_class=R2_ELF_LINK_TARGET_AMBIGUOUS; s->target_program=UINT32_MAX; s->target_file_offset=0; }
    /* Extent remains explicitly UNKNOWN. No target byte is read. */
    return 1;
}
static int r2_lm_relocations(struct r2_lm_context *c) {
    uint32_t i; uint64_t j;
    if(!r2_lm_charge(c,32,0)) return 0;
    for(i=0;i<3;++i) {
        struct r2_elf_link_table_v1 *p=&c->r->tables[i];
        if(!r2_lm_charge(c,32,0)) return 0;
        if(!p->present) continue;
        for(j=0;j<p->declared;++j) {
            struct r2_elf_link_relocation_v1 *s;
            if(!r2_lm_charge(c,160,p->file_offset+j*p->entry_size)) return 0;
            s=&c->r->relocations[c->r->relocations_retained]; s->source_table=p->kind;
            s->file_offset=p->file_offset+j*p->entry_size;
            if(!r2_lm_read(c,s->file_offset,8,&s->r_offset) || !r2_lm_read(c,s->file_offset+8,8,&s->r_info)) return 0;
            s->symbol_index=(uint32_t)(s->r_info>>32); s->type=(uint32_t)s->r_info;
            if(p->entry_size==24) {
                if(!r2_lm_read(c,s->file_offset+16,8,&s->addend_bits)) return 0;
                s->addend_known=1;
            }
            s->symbol_validation=c->r->symbol_count_exact?R2_ELF_LINK_SYMBOL_VALID_EXACT:R2_ELF_LINK_SYMBOL_VALID_UNKNOWN;
            if(c->r->symbol_count_exact && s->symbol_index>=c->r->symbols_declared) {
                s->symbol_validation=R2_ELF_LINK_SYMBOL_INVALID_EXACT;
                return r2_lm_fail(c,R2_ELF_LINK_REJECTED,R2_ELF_LINK_REASON_SYMBOL_INDEX,s->file_offset+8,s->symbol_index,p->kind);
            }
            if(!r2_lm_target(c,s)) return 0;
            s->complete=1; ++p->retained; ++c->r->relocations_retained;
        }
        p->complete=1;
    }
    c->r->relocation_remainder_unknown=
        (c->r->unsupported_conditions & R2_ELF_LINK_UNSUPPORTED_RELR)?1u:0u;
    return 1;
}
uint32_t route2_elf_link_metadata_parse_v1(const unsigned char *file,size_t file_size,
    uint32_t abi,struct r2_elf_link_report_v1 *out,size_t out_size,
    struct r2_elf_link_workspace_v1 *workspace,size_t workspace_size,uint64_t work_limit) {
    uintptr_t ib=(uintptr_t)file,ob=(uintptr_t)out,wb=(uintptr_t)workspace,ie,oe,we;
    size_t i; unsigned char *p; struct r2_lm_context c; uint32_t base_status;
    /* Do not dereference/read either caller output before all validation. */
    if(!file || !out || !workspace || abi!=R2_ELF_LINK_ABI ||
       out_size!=R2_ELF_LINK_REPORT_BYTES || workspace_size!=R2_ELF_LINK_WORKSPACE_BYTES ||
       ob%R2_ELF_LINK_ALIGNMENT || wb%R2_ELF_LINK_ALIGNMENT ||
       file_size>UINTPTR_MAX-ib || out_size>UINTPTR_MAX-ob || workspace_size>UINTPTR_MAX-wb ||
       work_limit<R2_ELF_LINK_INITIAL_WORK || work_limit>R2_ELF_LINK_WORK_LIMIT)
        return R2_ELF_LINK_BAD_ARGUMENT;
    ie=ib+file_size; oe=ob+out_size; we=wb+workspace_size;
    if((file_size && ib<oe && ob<ie) || (file_size && ib<we && wb<ie) || (ob<we && wb<oe))
        return R2_ELF_LINK_BAD_ARGUMENT;
    /* INITIAL_WORK reserved locally BEFORE any initialization or core call. */
    p=(unsigned char *)out; for(i=0;i<out_size;++i) p[i]=0;
    p=(unsigned char *)workspace; for(i=0;i<workspace_size;++i) p[i]=0;
    out->abi=R2_ELF_LINK_ABI; out->size=R2_ELF_LINK_REPORT_BYTES; out->status=R2_ELF_LINK_BASE_STOP;
    out->preload_scope=R2_ELF_PRELOAD_CLOSURE_UNPROVEN; out->unvalidated_semantics=R2_ELF_LINK_UNVALIDATED_ALL;
    out->file_bytes=file_size; out->work_units=R2_ELF_LINK_INITIAL_WORK;
    out->symbol_remainder_unknown=1; out->relocation_remainder_unknown=1;
    out->hash_remainder_unknown=1;
    c.file=file; c.length=file_size; c.limit=work_limit; c.r=out; c.w=workspace;
    base_status=route2_elf_preload_parse_raw_v1(file,file_size,R2_ELF_RAW_ABI,&out->base,sizeof out->base);
    out->names_inspected_bytes=out->base.string_bytes_inspected;
    out->base_complete=(base_status==R2_ELF_RAW_COMPLETE || base_status==R2_ELF_RAW_APPLICATION_CONDITIONS);
    /* A base failure still retains its exact original facts. A fully read
     * program table and terminated dynamic prefix permit independent bounded
     * symbol/relocation metadata inspection despite unsupported base semantics.
     * Hard base rejection/incompleteness always stops this extension.
     */
    if(base_status==R2_ELF_RAW_REJECTED || base_status==R2_ELF_RAW_INCOMPLETE || base_status==R2_ELF_RAW_BAD_ARGUMENT ||
       !out->base.header_valid || out->base.program_count!=out->base.declared_phnum ||
       (out->base.dynamic_present && !out->base.dynamic_terminated)) return out->status;
    out->status=R2_ELF_LINK_REJECTED;
    if(!r2_lm_tags(&c) || !r2_lm_sym_group(&c)) return out->status;
    if(workspace->tags[LM_HASH].present) {
        if(!r2_lm_sysv(&c)) return out->status;
        /* A simultaneous GNU hash is retained raw in base, not silently
         * advertised as independently validated by the SysV traversal. */
        if(workspace->tags[LM_GNUHASH].present) out->unsupported_conditions|=R2_ELF_LINK_UNSUPPORTED_HASH_COUNT;
    } else if(workspace->tags[LM_GNUHASH].present) {
        if(!r2_lm_gnu(&c)) return out->status;
    } else out->hash_remainder_unknown=0;
    if(!r2_lm_symbols(&c) || !r2_lm_tables(&c) || !r2_lm_relocations(&c)) return out->status;
    out->metadata_complete=(!out->symbol_remainder_unknown && !out->relocation_remainder_unknown);
    out->status=(out->metadata_complete && out->base_complete && !out->unsupported_conditions)?R2_ELF_LINK_COMPLETE:R2_ELF_LINK_PARTIAL;
    return out->status;
}
#endif
