/* Separate kernel TU, NEVER included in the existing native Windows TU graph.
 * SOURCE ONLY / UNCOMPILED_UNRUN. WDM C11 x64, Windows 10 1703+, matching
 * SDK/WDK/MSVC, ntifs.h (includes ntddk.h), wdmsec.h, NtosKrnl.lib/Wdmsec.lib,
 * kernel DriverEntry/subsystem and FORCE_INTEGRITY plus normal driver signing.
 * No installation, signing bypass, loader or runtime permission is provided.
 * Docs: PsSetCreateProcessNotifyRoutineEx (PASSIVE/removal drains callbacks),
 * IoGetRequestorProcess/IoThreadToProcess, PsGetProcessStartKey,
 * WdmlibIoCreateDeviceSecure, KeWaitForSingleObject, Unload Routine Environment.
 * KMUTEX preserves PASSIVE_LEVEL; ordinary FAST_MUTEX would raise APC_LEVEL.
 * No timeout/cancel claim: lifecycle mutex and callback removal may stall.
 */
#if !defined(R2_TARGET_WINDOWS_BIRTH_DRIVER) || !defined(_WIN64) || !defined(_M_AMD64)
#error "explicit separate WDM x64 birth driver target required"
#endif
#include <ntifs.h>
#include <wdmsec.h>
#include "route2_birth_observer_protocol.h"
#ifndef R2_BIRTH_OBSERVER_DRIVER_V1_BODY
#define R2_BIRTH_OBSERVER_DRIVER_V1_BODY
static const GUID r2_birth_class_v1 =
    {0xbdbaab38,0x6a0d,0x4d78,{0xac,0x11,0x73,0x13,0x2a,0xa9,0x0c,0x39}};
struct r2_birth_driver_v1 {
    KMUTEX lifecycle;
    volatile LONG gate, reasons;
    PDEVICE_OBJECT device;
    PFILE_OBJECT file; /* borrowed until CLOSE, deliberately no self-ref cycle */
    PETHREAD owner_thread;
    PEPROCESS objects[R2_BIRTH_PROCESS_CAP]; /* slot0 owns sole owner process ref */
    ULONG ready, consumed, active, pin, remove_consumed, disposed, cleaned;
    NTSTATUS registration_status, removal_status;
    ULONG registration_valid, removal_valid;
    struct r2_birth_report_v1 report;
};
static struct r2_birth_driver_v1 r2_bd;
_Static_assert(sizeof(void *)==8 && sizeof(LONG)==4 &&
    sizeof(r2_bd)+sizeof(r2_birth_class_v1)+sizeof(R2_BIRTH_KERNEL_NAME)+
    sizeof(R2_BIRTH_LINK_NAME)+sizeof(L"D:P(A;;GA;;;SY)(A;;GA;;;BA)")<=32768,
    "all fixed driver state including report bounded; opaque object/code fees excluded");
_Static_assert(R2_BIRTH_IOCTL_REGISTER==CTL_CODE(0x8000,0x800,METHOD_BUFFERED,FILE_READ_DATA|FILE_WRITE_DATA) &&
    R2_BIRTH_IOCTL_QUERY==CTL_CODE(0x8000,0x801,METHOD_BUFFERED,FILE_READ_DATA|FILE_WRITE_DATA) &&
    R2_BIRTH_IOCTL_REVOKE==CTL_CODE(0x8000,0x802,METHOD_BUFFERED,FILE_READ_DATA|FILE_WRITE_DATA),
    "kernel/native exact IOCTL mapping");
static VOID r2_bd_stop(ULONG reason)
{
    InterlockedOr(&r2_bd.reasons,(LONG)reason);
    /* One atomic word publishes STOP and completeness reason together. */
}
static VOID r2_bd_event(ULONG slot, ULONG kind)
{
    struct r2_birth_header_v1 *h=&r2_bd.report.h;
    struct r2_birth_event_v1 *e=&r2_bd.report.events[h->events++];
    e->sequence=++h->sequence; e->pid=r2_bd.report.processes[slot].pid;
    e->slot=slot; e->kind=kind;
    if (kind==R2_BIRTH_EVENT_CREATE)
        r2_bd.report.processes[slot].create_sequence=e->sequence;
    else r2_bd.report.processes[slot].exit_sequence=e->sequence;
}
static VOID r2_bd_notify(PEPROCESS process,HANDLE pid,PPS_CREATE_NOTIFY_INFO info)
{
    ULONG i,slot; struct r2_birth_header_v1 *h=&r2_bd.report.h;
    struct r2_birth_process_v1 *p;
    /* No global counter increments after STOP, thus no unbounded/saturating
     * counter arithmetic. Invocation count/opaque callback cost is UNKNOWN. */
    if (InterlockedCompareExchange(&r2_bd.reasons,0,0)) return;
    if (InterlockedCompareExchange(&r2_bd.gate,1,0)) {
        r2_bd_stop(R2_BIRTH_STOP_CONTENTION); return;
    }
    if (InterlockedCompareExchange(&r2_bd.reasons,0,0)) goto done;
    /* This gate/STOP check reserves this one in-flight callback. A racing
     * STOP cannot cancel that reservation; every later callback declines. */
    if (h->events>=R2_BIRTH_EVENT_CAP || h->sequence==UINT32_MAX) {
        r2_bd_stop(R2_BIRTH_STOP_CAPACITY); goto done;
    }
    if (info) {
        if (info->Size<sizeof(*info) || h->slots>=R2_BIRTH_PROCESS_CAP) {
            r2_bd_stop(R2_BIRTH_STOP_CAPACITY); goto done;
        }
        slot=h->slots; p=&r2_bd.report.processes[slot];
        ObReferenceObject(process); r2_bd.objects[slot]=process;
        p->pid=(uint64_t)(ULONG_PTR)pid;
        p->start_key=PsGetProcessStartKey(process);
        p->creator_pid=(uint64_t)(ULONG_PTR)info->CreatingThreadId.UniqueProcess;
        p->creator_tid=(uint64_t)(ULONG_PTR)info->CreatingThreadId.UniqueThread;
        p->creation_status=(uint32_t)info->CreationStatus;
        p->flags=R2_BIRTH_CALLBACK_BIRTH; ++h->slots;
        r2_bd_event(slot,R2_BIRTH_EVENT_CREATE);
        /* Never modify CreationStatus: never veto unrelated system births. */
    } else {
        /* Single <=64 object comparisons includes owner seed. No PID reopen. */
        for (i=0;i<h->slots;++i) {
            if (r2_bd.objects[i]!=process) continue;
            p=&r2_bd.report.processes[i];
            if (p->flags&R2_BIRTH_EXIT_OBSERVED) {
                r2_bd_stop(R2_BIRTH_STOP_INVARIANT); break;
            }
            p->flags|=R2_BIRTH_EXIT_OBSERVED;
            r2_bd_event(i,R2_BIRTH_EVENT_EXIT);
            if (!i) { h->owner_exit=1; r2_bd_stop(R2_BIRTH_STOP_OWNER_EXIT); }
            break;
        }
    }
done:
    InterlockedExchange(&r2_bd.gate,0);
}
static BOOLEAN r2_bd_actor(PIRP irp)
{
    PETHREAD thread=irp->Tail.Overlay.Thread;
    PEPROCESS process;
    if (irp->RequestorMode!=UserMode || !thread || thread!=PsGetCurrentThread())
        return FALSE;
    process=IoGetRequestorProcess(irp);
    return process && process==IoThreadToProcess(thread) && process==PsGetCurrentProcess();
}
static BOOLEAN r2_bd_owner(PIRP irp,PFILE_OBJECT file)
{
    return r2_bd_actor(irp) && file==r2_bd.file && !r2_bd.cleaned &&
        r2_bd.owner_thread==irp->Tail.Overlay.Thread &&
        r2_bd.objects[0]==PsGetCurrentProcess();
}
static VOID r2_bd_dispose(VOID)
{
    ULONG i;
    /* Caller holds lifecycle mutex. Callback has never registered, or known
     * successful removal has returned after draining ALL callbacks. */
    if (r2_bd.disposed) return;
    for (i=0;i<r2_bd.report.h.slots;++i) {
        if (r2_bd.objects[i]) {
            ObDereferenceObject(r2_bd.objects[i]); r2_bd.objects[i]=NULL;
            r2_bd.report.processes[i].flags|=R2_BIRTH_REFERENCE_DISPOSED;
        }
    }
    if (r2_bd.owner_thread) {
        ObDereferenceObject(r2_bd.owner_thread); r2_bd.owner_thread=NULL;
    }
    r2_bd.disposed=1;
    if (r2_bd.pin) {
        r2_bd.pin=0; ObDereferenceObject(r2_bd.device);
    }
}
static VOID r2_bd_revoke(VOID)
{
    r2_bd_stop(R2_BIRTH_STOP_REVOKE);
    if (!r2_bd.active || r2_bd.remove_consumed) return;
    r2_bd.remove_consumed=1;
    /* Never called by callback; publication gate is NOT held here.
     * In-flight or failed removal retains pin, objects and all liabilities.
     * CLEANUP/CLOSE cannot retry this lifetime consumption. */
    r2_bd.removal_status=PsSetCreateProcessNotifyRoutineEx(r2_bd_notify,TRUE);
    r2_bd.removal_valid=1;
    if (NT_SUCCESS(r2_bd.removal_status)) {
        r2_bd.active=0; r2_bd_dispose();
    }
}
static VOID r2_bd_register(PIRP irp)
{
    struct r2_birth_process_v1 *p=&r2_bd.report.processes[0];
    r2_bd.consumed=1;
    ObReferenceObject(r2_bd.device); r2_bd.pin=1;
    r2_bd.objects[0]=PsGetCurrentProcess(); ObReferenceObject(r2_bd.objects[0]);
    r2_bd.owner_thread=irp->Tail.Overlay.Thread; ObReferenceObject(r2_bd.owner_thread);
    p->pid=(uint64_t)(ULONG_PTR)PsGetProcessId(r2_bd.objects[0]);
    p->start_key=PsGetProcessStartKey(r2_bd.objects[0]); p->flags=R2_BIRTH_OWNER_SEED;
    r2_bd.report.h.slots=1;
    r2_bd.report.h.owner_pid=p->pid;
    r2_bd.report.h.owner_tid=(uint64_t)(ULONG_PTR)PsGetThreadId(r2_bd.owner_thread);
    r2_bd.report.h.owner_start_key=p->start_key;
    /* All callback-visible state and its device pin precede registration.
     * A callback may execute BEFORE the following registration call returns. */
    r2_bd.registration_status=PsSetCreateProcessNotifyRoutineEx(r2_bd_notify,FALSE);
    r2_bd.registration_valid=1;
    if (NT_SUCCESS(r2_bd.registration_status)) r2_bd.active=1;
    else {
        r2_bd_stop(R2_BIRTH_STOP_REGISTRATION);
        r2_bd_dispose(); /* known never registered; no callback can be active */
    }
}
static VOID r2_bd_snapshot(struct r2_birth_report_v1 *out,ULONG operation,NTSTATUS opstatus)
{
    BOOLEAN gate=(InterlockedCompareExchange(&r2_bd.gate,1,0)==0);
    struct r2_birth_header_v1 *h;
    RtlZeroMemory(out,sizeof(*out));
    if (gate) RtlCopyMemory(out,&r2_bd.report,sizeof(*out));
    else r2_bd_stop(R2_BIRTH_STOP_CONTENTION);
    h=&out->h; h->abi=R2_BIRTH_ABI; h->size=sizeof(*out); h->operation=operation;
    h->details_valid=gate ? 1u : 0u;
    h->register_consumed=r2_bd.consumed;
    h->register_valid=r2_bd.registration_valid;
    h->register_status=r2_bd.registration_valid ? (uint32_t)r2_bd.registration_status : 0;
    h->registered=r2_bd.registration_valid && NT_SUCCESS(r2_bd.registration_status);
    h->remove_consumed=r2_bd.remove_consumed; h->remove_valid=r2_bd.removal_valid;
    h->remove_status=r2_bd.removal_valid ? (uint32_t)r2_bd.removal_status : 0;
    h->removed=r2_bd.removal_valid && NT_SUCCESS(r2_bd.removal_status);
    h->stop_reasons=(uint32_t)InterlockedCompareExchange(&r2_bd.reasons,0,0);
    h->stop_new=h->stop_reasons!=0;
    h->incomplete=(h->stop_reasons&(R2_BIRTH_STOP_CONTENTION|R2_BIRTH_STOP_CAPACITY|
        R2_BIRTH_STOP_REGISTRATION|R2_BIRTH_STOP_INVARIANT))!=0;
    h->pending=r2_bd.active || r2_bd.pin || r2_bd.owner_thread!=NULL;
    h->disposed=r2_bd.disposed; h->owner_thread_retained=r2_bd.owner_thread!=NULL;
    h->device_pin=r2_bd.pin;
    h->final=gate && h->removed && h->disposed && !h->pending;
    h->operation_status=(uint32_t)(gate ? opstatus : STATUS_DEVICE_BUSY);
    h->operation_status_valid=1; h->remaining_unproven=R2_BIRTH_UNPROVEN_ALL;
    if (gate) InterlockedExchange(&r2_bd.gate,0);
}
static NTSTATUS r2_bd_complete(PIRP irp,NTSTATUS status,ULONG_PTR bytes)
{
    irp->IoStatus.Status=status; irp->IoStatus.Information=bytes;
    IoCompleteRequest(irp,IO_NO_INCREMENT); return status;
}
static NTSTATUS r2_bd_dispatch(PDEVICE_OBJECT device,PIRP irp)
{
    PIO_STACK_LOCATION sp=IoGetCurrentIrpStackLocation(irp);
    NTSTATUS status=STATUS_INVALID_DEVICE_REQUEST,opstatus=STATUS_SUCCESS;
    ULONG_PTR bytes=0; ULONG code;
    UNREFERENCED_PARAMETER(device);
    if (KeGetCurrentIrql()!=PASSIVE_LEVEL)
        return r2_bd_complete(irp,STATUS_INVALID_DEVICE_STATE,0);
    status=KeWaitForSingleObject(&r2_bd.lifecycle,Executive,KernelMode,FALSE,NULL);
    if (status!=STATUS_SUCCESS) return r2_bd_complete(irp,status,0);
    status=STATUS_INVALID_DEVICE_REQUEST;
    if (!r2_bd.ready) { status=STATUS_DEVICE_NOT_READY; goto done; }
    switch (sp->MajorFunction) {
    case IRP_MJ_CREATE:
        if (!sp->FileObject || sp->FileObject->FileName.Length ||
            sp->FileObject->RelatedFileObject || !r2_bd_actor(irp)) {
            status=STATUS_ACCESS_DENIED; break;
        }
        if (r2_bd.file || r2_bd.consumed) { status=STATUS_DEVICE_BUSY; break; }
        r2_bd.file=sp->FileObject; status=STATUS_SUCCESS; break;
    case IRP_MJ_CLEANUP:
    case IRP_MJ_CLOSE:
        /* Deliberately no owner/RequestorMode check: cleanup may be on a
         * different actor after owner death. Original FileObject still binds. */
        if (sp->FileObject==r2_bd.file && r2_bd.file) {
            r2_bd.cleaned=1; r2_bd_revoke();
            if (sp->MajorFunction==IRP_MJ_CLOSE) r2_bd.file=NULL;
        }
        status=STATUS_SUCCESS; break;
    case IRP_MJ_DEVICE_CONTROL:
        code=sp->Parameters.DeviceIoControl.IoControlCode;
        if ((code!=R2_BIRTH_IOCTL_REGISTER && code!=R2_BIRTH_IOCTL_QUERY &&
             code!=R2_BIRTH_IOCTL_REVOKE) ||
            sp->Parameters.DeviceIoControl.InputBufferLength!=0 ||
            sp->Parameters.DeviceIoControl.OutputBufferLength!=sizeof(struct r2_birth_report_v1) ||
            !irp->AssociatedIrp.SystemBuffer) {
            status=STATUS_INVALID_PARAMETER; break;
        }
        if (code==R2_BIRTH_IOCTL_REGISTER) {
            if (!r2_bd_actor(irp) || sp->FileObject!=r2_bd.file || r2_bd.cleaned) {
                status=STATUS_ACCESS_DENIED; break;
            }
            if (r2_bd.consumed) { status=STATUS_INVALID_DEVICE_STATE; break; }
            r2_bd_register(irp);
            opstatus=r2_bd.registration_status;
        } else {
            if (!r2_bd_owner(irp,sp->FileObject)) { status=STATUS_ACCESS_DENIED; break; }
            if (code==R2_BIRTH_IOCTL_REVOKE) {
                r2_bd_revoke();
                opstatus=r2_bd.removal_valid ? r2_bd.removal_status : STATUS_INVALID_DEVICE_STATE;
            }
        }
        r2_bd_snapshot((struct r2_birth_report_v1 *)irp->AssociatedIrp.SystemBuffer,code,opstatus);
        status=STATUS_SUCCESS; bytes=sizeof(struct r2_birth_report_v1); break;
    default: break;
    }
done:
    KeReleaseMutex(&r2_bd.lifecycle,FALSE);
    return r2_bd_complete(irp,status,bytes);
}
static VOID r2_bd_unload(PDRIVER_OBJECT driver)
{
    UNICODE_STRING link=RTL_CONSTANT_STRING(R2_BIRTH_LINK_NAME);
    UNREFERENCED_PARAMETER(driver);
    /* I/O manager cannot enter normal unload while any device reference,
     * file or IRP remains. Pin release happens only after callback drain and
     * object disposal. Unload-pending may suppress new IRPs before that point:
     * this can retain the pin forever, never a false cleanup/exit PASS. */
    NT_ASSERT(!r2_bd.active && !r2_bd.pin && !r2_bd.owner_thread && !r2_bd.file);
    r2_bd.ready=0; IoDeleteSymbolicLink(&link); IoDeleteDevice(r2_bd.device);
}
DRIVER_INITIALIZE DriverEntry;
NTSTATUS DriverEntry(PDRIVER_OBJECT driver,PUNICODE_STRING registry)
{
    UNICODE_STRING name=RTL_CONSTANT_STRING(R2_BIRTH_KERNEL_NAME);
    UNICODE_STRING link=RTL_CONSTANT_STRING(R2_BIRTH_LINK_NAME);
    UNICODE_STRING sddl=RTL_CONSTANT_STRING(L"D:P(A;;GA;;;SY)(A;;GA;;;BA)");
    NTSTATUS status; ULONG i;
    UNREFERENCED_PARAMETER(registry);
    KeInitializeMutex(&r2_bd.lifecycle,0);
    for (i=0;i<=IRP_MJ_MAXIMUM_FUNCTION;++i) driver->MajorFunction[i]=r2_bd_dispatch;
    driver->DriverUnload=r2_bd_unload;
    status=IoCreateDeviceSecure(driver,0,&name,R2_BIRTH_DEVICE_TYPE,
        FILE_DEVICE_SECURE_OPEN,TRUE,&sddl,&r2_birth_class_v1,&r2_bd.device);
    if (!NT_SUCCESS(status)) return status;
    status=IoCreateSymbolicLink(&link,&name);
    if (!NT_SUCCESS(status)) {
        IoDeleteDevice(r2_bd.device); r2_bd.device=NULL; return status;
    }
    r2_bd.device->Flags|=DO_BUFFERED_IO;
    r2_bd.ready=1;
    r2_bd.device->Flags&=~DO_DEVICE_INITIALIZING;
    /* No fallible initialization after readiness; no callback in DriverEntry.
     * Failed DriverEntry would free code without calling DriverUnload. */
    return STATUS_SUCCESS;
}
#endif