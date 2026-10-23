/* C00 original process-object RAW protocol; SOURCE ONLY, UNCOMPILED_UNRUN.
 * Shared by separate WDM and native x64 C11 targets. No Windows types,
 * pointers, HANDLEs, image strings, caller samples or grants cross this ABI.
 */
#ifndef R2_BIRTH_OBSERVER_PROTOCOL_V1_DECLARED
#define R2_BIRTH_OBSERVER_PROTOCOL_V1_DECLARED
#include <stdint.h>
#include <stddef.h>
#define R2_BIRTH_ABI 1u
#define R2_BIRTH_PROCESS_CAP 64u
#define R2_BIRTH_EVENT_CAP 256u
#define R2_BIRTH_REPORT_BYTES 12544u
#define R2_BIRTH_DEVICE_TYPE 0x8000u
/* CTL_CODE(0x8000,0x800..802,METHOD_BUFFERED,READ|WRITE). */
#define R2_BIRTH_IOCTL_REGISTER 0x8000E000u
#define R2_BIRTH_IOCTL_QUERY    0x8000E004u
#define R2_BIRTH_IOCTL_REVOKE   0x8000E008u
#define R2_BIRTH_USER_NAME L"\\\\.\\Route2BirthObserverV1"
#define R2_BIRTH_KERNEL_NAME L"\\Device\\Route2BirthObserverV1"
#define R2_BIRTH_LINK_NAME L"\\DosDevices\\Route2BirthObserverV1"
#define R2_BIRTH_UNPROVEN_ALL 0xFFFFFFFFu
#define R2_BIRTH_OWNER_SEED 1u
#define R2_BIRTH_CALLBACK_BIRTH 2u
#define R2_BIRTH_EXIT_OBSERVED 4u
#define R2_BIRTH_REFERENCE_DISPOSED 8u
#define R2_BIRTH_EVENT_CREATE 1u
#define R2_BIRTH_EVENT_EXIT 2u
#define R2_BIRTH_STOP_CONTENTION 1u
#define R2_BIRTH_STOP_CAPACITY 2u
#define R2_BIRTH_STOP_OWNER_EXIT 4u
#define R2_BIRTH_STOP_REVOKE 8u
#define R2_BIRTH_STOP_REGISTRATION 16u
#define R2_BIRTH_STOP_INVARIANT 32u
struct r2_birth_header_v1 {
    uint32_t abi, size, operation, details_valid;
    uint32_t register_consumed, register_valid, register_status, registered;
    uint32_t remove_consumed, remove_valid, remove_status, removed;
    uint32_t stop_new, incomplete, stop_reasons, pending;
    uint32_t slots, events, sequence, disposed;
    uint32_t owner_exit, owner_thread_retained, device_pin, final;
    uint32_t operation_status, operation_status_valid, remaining_unproven, reserved[5];
    uint64_t owner_pid, owner_tid, owner_start_key, reserved64[13];
};
struct r2_birth_process_v1 {
    uint64_t pid, start_key, creator_pid, creator_tid, create_sequence, exit_sequence;
    uint32_t flags, creation_status, reserved[2];
};
struct r2_birth_event_v1 {
    uint64_t sequence, pid;
    uint32_t slot, kind, flags, reserved;
};
struct r2_birth_report_v1 {
    struct r2_birth_header_v1 h;
    struct r2_birth_process_v1 processes[R2_BIRTH_PROCESS_CAP];
    struct r2_birth_event_v1 events[R2_BIRTH_EVENT_CAP];
};
_Static_assert(sizeof(uint32_t)==4 && sizeof(uint64_t)==8,
    "birth protocol fixed integer widths");
_Static_assert(sizeof(struct r2_birth_header_v1)==256 &&
    offsetof(struct r2_birth_header_v1,owner_pid)==128 &&
    sizeof(struct r2_birth_process_v1)==64 &&
    sizeof(struct r2_birth_event_v1)==32 &&
    offsetof(struct r2_birth_report_v1,processes)==256 &&
    offsetof(struct r2_birth_report_v1,events)==4352 &&
    sizeof(struct r2_birth_report_v1)==R2_BIRTH_REPORT_BYTES &&
    _Alignof(struct r2_birth_report_v1)==8 && R2_BIRTH_REPORT_BYTES<=16384,
    "birth protocol native x64 layout; never packed");
/* OWNER_SEED is preexisting, never callback birth evidence. CreationStatus
 * is the value seen in this callback, not eventual process-creation success.
 * A disposal flag is not an exit observation. details_valid=0 means history
 * is unavailable (including gate contention), never an empty history claim.
 * transport success is independent of raw registration/removal NTSTATUS.
 * No process/service/HCS membership, primary-thread, billing, admission or
 * complete global capture claim; all unknown fees remain UNKNOWN_NOT_ZERO.
 */
#endif

/* Private numeric capability wire. Enabled only by the native consumer and
 * the explicitly selected kernel source; never part of the public C00 ABI. */
#if defined(R2_BIRTH_PROCESS_PRIVATE_WIRE_V1) && !defined(R2_BIRTH_PROCESS_PRIVATE_WIRE_DECLARED)
#define R2_BIRTH_PROCESS_PRIVATE_WIRE_DECLARED
#define R2_BIRTH_PROCESS_IOCTL_OFFER 0x8000E00Cu
#define R2_BIRTH_PROCESS_WIRE_ABI 1u
#define R2_BIRTH_PROCESS_EMPTY_NOW 1u
#define R2_BIRTH_PROCESS_OFFERED 2u
#define R2_BIRTH_PROCESS_STOPPED 3u
#define R2_BIRTH_PROCESS_PUBLICATION_UNKNOWN 0u
#define R2_BIRTH_PROCESS_PUBLICATION_KNOWN 1u
struct r2_birth_process_private_wire_v1 {
    uint32_t abi, size, operation, disposition;
    uint32_t ordinal, cursor, original_slot, publication;
    uint32_t stop_new, extra_device_pin, pending_temporaries, reserved0;
    uint64_t original_pid, original_start_key, owner_pid, owner_tid, owner_start_key;
    uint64_t user_handle; /* private same-client transfer only */
    uint32_t ddi_executed[7], ddi_status_valid[7], ddi_status[7];
    uint32_t reserved[5];
};
_Static_assert(sizeof(struct r2_birth_process_private_wire_v1)<=512 &&
    _Alignof(struct r2_birth_process_private_wire_v1)==8,
    "private offer wire bounded and naturally aligned");
#endif
