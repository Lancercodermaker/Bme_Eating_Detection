/* Included once inside the paired WDM driver, after its private helpers.
 * SOURCE ONLY / UNCOMPILED_UNRUN. No separate translation unit. */
#if !defined(R2_BIRTH_PROCESS_DRIVER_INTERNAL_INCLUDE_V1) || \
    !defined(R2_ENABLE_WIN_BIRTH_PROCESS_RAW_V1) || \
    !defined(R2_ENABLE_WIN_BIRTH_OBSERVER_RAW_V1) || \
    !defined(R2_BIRTH_PROCESS_PRIVATE_WIRE_V1)
#error "private process bridge requires the paired original-object driver"
#endif
#ifndef R2_BIRTH_PROCESS_DRIVER_V1_BODY
#define R2_BIRTH_PROCESS_DRIVER_V1_BODY
struct r2_birth_process_driver_v1 {
    ULONG cursor, issued, stop, extra_pin, pending_temporaries;
    HANDLE pending[3]; /* diagnostic identities only; never retried */
};
static struct r2_birth_process_driver_v1 r2_bp={1};
_Static_assert(sizeof(r2_bd)+sizeof(r2_bp)+sizeof(r2_birth_class_v1)+
    sizeof(R2_BIRTH_KERNEL_NAME)+sizeof(R2_BIRTH_LINK_NAME)+
    sizeof(L"D:P(A;;GA;;;SY)(A;;GA;;;BA)")<=32768,
    "all paired fixed kernel state remains within 32 KiB");
_Static_assert(R2_BIRTH_PROCESS_IOCTL_OFFER==
    CTL_CODE(0x8000,0x803,METHOD_BUFFERED,FILE_READ_DATA|FILE_WRITE_DATA),
    "private IOCTL exact mapping");
static VOID r2_bp_fail(VOID) { r2_bp.stop=1; }
static VOID r2_bp_status(struct r2_birth_process_private_wire_v1 *w,
    ULONG i,NTSTATUS s)
{
    w->ddi_executed[i]=1; w->ddi_status_valid[i]=1;
    w->ddi_status[i]=(uint32_t)s;
}
static VOID r2_bp_close(struct r2_birth_process_private_wire_v1 *w,
    ULONG index,HANDLE *source,ULONG pending_index)
{
    HANDLE value=*source; NTSTATUS status;
    if (!value) return;
    *source=NULL; /* consume before the sole ZwClose, including its failure */
    status=ZwClose(value); r2_bp_status(w,index,status);
    if (!NT_SUCCESS(status)) {
        r2_bp.pending[pending_index]=value;
        ++r2_bp.pending_temporaries; r2_bp_fail();
    }
}
static VOID r2_bp_uncertain_open(HANDLE *source,ULONG pending_index)
{
    if (!*source) return;
    r2_bp.pending[pending_index]=*source;
    *source=NULL; /* failed DDI output is not a proven closable handle */
    ++r2_bp.pending_temporaries; r2_bp_fail();
}
static NTSTATUS r2_bp_offer(PIRP irp,struct r2_birth_process_private_wire_v1 *w)
{
    struct r2_birth_process_private_wire_v1 out={0};
    const struct r2_birth_process_v1 *entry;
    PEPROCESS original=NULL;
    HANDLE original_kernel=NULL,system_kernel=NULL,client_kernel=NULL,user=NULL;
    NTSTATUS status; ULONG slot=0;
    UNREFERENCED_PARAMETER(irp); /* caller was checked by r2_bd_owner */
    out.abi=R2_BIRTH_PROCESS_WIRE_ABI;
    out.size=sizeof(out); out.operation=R2_BIRTH_PROCESS_IOCTL_OFFER;
    out.owner_pid=r2_bd.report.h.owner_pid;
    out.owner_tid=r2_bd.report.h.owner_tid;
    out.owner_start_key=r2_bd.report.h.owner_start_key;
    out.cursor=r2_bp.cursor;
    out.ordinal=r2_bp.issued;
    if (r2_bp.stop || r2_bp.extra_pin || !r2_bd.active ||
        !r2_bd.registration_valid || !NT_SUCCESS(r2_bd.registration_status) ||
        r2_bd.cleaned || r2_bd.disposed || !r2_bd.objects[0] ||
        InterlockedCompareExchange(&r2_bd.reasons,0,0)) {
        r2_bp_fail(); goto stopped;
    }
    /* Single publication-gate attempt. The lifecycle mutex already held by
     * dispatch prevents removal/disposal throughout this whole offer. */
    if (InterlockedCompareExchange(&r2_bd.gate,1,0)) {
        r2_bd_stop(R2_BIRTH_STOP_CONTENTION); r2_bp_fail(); goto stopped;
    }
    if (InterlockedCompareExchange(&r2_bd.reasons,0,0) ||
        r2_bp.cursor>63 || r2_bd.report.h.slots>R2_BIRTH_PROCESS_CAP) {
        InterlockedExchange(&r2_bd.gate,0); r2_bp_fail(); goto stopped;
    }
    if (r2_bp.cursor>=r2_bd.report.h.slots) {
        InterlockedExchange(&r2_bd.gate,0);
        out.disposition=R2_BIRTH_PROCESS_EMPTY_NOW; goto publish;
    }
    slot=r2_bp.cursor++;
    entry=&r2_bd.report.processes[slot]; original=r2_bd.objects[slot];
    out.cursor=r2_bp.cursor; out.ordinal=++r2_bp.issued;
    out.original_slot=slot; out.original_pid=entry->pid;
    out.original_start_key=entry->start_key;
    if (!original || !entry->pid ||
        !(entry->flags&R2_BIRTH_CALLBACK_BIRTH) ||
        entry->flags&R2_BIRTH_REFERENCE_DISPOSED ||
        (uint64_t)(ULONG_PTR)PsGetProcessId(original)!=entry->pid ||
        PsGetProcessStartKey(original)!=entry->start_key) {
        InterlockedExchange(&r2_bd.gate,0); r2_bp_fail(); goto stopped;
    }
    InterlockedExchange(&r2_bd.gate,0);
    /* Private pin covers all possibly outstanding kernel temporaries. */
    ObReferenceObject(r2_bd.device); r2_bp.extra_pin=1;
    status=ObOpenObjectByPointer(original,
        OBJ_KERNEL_HANDLE|OBJ_FORCE_ACCESS_CHECK,NULL,
        PROCESS_QUERY_LIMITED_INFORMATION|SYNCHRONIZE,
        *PsProcessType,KernelMode,&original_kernel);
    r2_bp_status(&out,0,status);
    if (!NT_SUCCESS(status)) {
        r2_bp_uncertain_open(&original_kernel,0); r2_bp_fail(); goto close_all;
    }
    if (!original_kernel) { r2_bp_fail(); goto close_all; }
    status=ObOpenObjectByPointer(PsInitialSystemProcess,OBJ_KERNEL_HANDLE,
        NULL,PROCESS_DUP_HANDLE,*PsProcessType,KernelMode,&system_kernel);
    r2_bp_status(&out,1,status);
    if (!NT_SUCCESS(status)) {
        r2_bp_uncertain_open(&system_kernel,1); r2_bp_fail(); goto close_all;
    }
    if (!system_kernel) { r2_bp_fail(); goto close_all; }
    status=ObOpenObjectByPointer(r2_bd.objects[0],OBJ_KERNEL_HANDLE,
        NULL,PROCESS_DUP_HANDLE,*PsProcessType,KernelMode,&client_kernel);
    r2_bp_status(&out,2,status);
    if (!NT_SUCCESS(status)) {
        r2_bp_uncertain_open(&client_kernel,2); r2_bp_fail(); goto close_all;
    }
    if (!client_kernel) { r2_bp_fail(); goto close_all; }
    status=ZwDuplicateObject(system_kernel,original_kernel,client_kernel,
        &user,0,0,DUPLICATE_SAME_ACCESS);
    r2_bp_status(&out,3,status);
    if (NT_SUCCESS(status) && user) {
        out.publication=R2_BIRTH_PROCESS_PUBLICATION_KNOWN;
        out.user_handle=(uint64_t)(ULONG_PTR)user;
        out.disposition=R2_BIRTH_PROCESS_OFFERED;
    } else r2_bp_fail();
    /* A failed duplicate can have ambiguous delivery. Never use a numeric
     * user handle for remote close; the client or its actual rundown owns it. */
close_all:
    r2_bp_close(&out,4,&client_kernel,2);
    r2_bp_close(&out,5,&system_kernel,1);
    r2_bp_close(&out,6,&original_kernel,0);
    if (!r2_bp.pending_temporaries) {
        r2_bp.extra_pin=0; ObDereferenceObject(r2_bd.device);
    }
    if (r2_bp.stop && !out.disposition) out.disposition=R2_BIRTH_PROCESS_STOPPED;
publish:
    /* A callback may have latched base STOP while this issued offer was in
     * flight. Preserve its known user publication and stop future offers. */
    if (InterlockedCompareExchange(&r2_bd.reasons,0,0)) r2_bp_fail();
    out.stop_new=r2_bp.stop;
    out.extra_device_pin=r2_bp.extra_pin;
    out.pending_temporaries=r2_bp.pending_temporaries;
    RtlCopyMemory(w,&out,sizeof(out)); return STATUS_SUCCESS;
stopped:
    out.disposition=R2_BIRTH_PROCESS_STOPPED; goto publish;
}
#endif
