"""SOURCE_ONLY values for the independently eligible C01 declaration slice.

Ordinary constructors do not establish original ownership, approval, scope
proof, or a rejection receipt. No registry, state machine, producer, consumer,
descriptor consumption, or close operation is implemented here. Native
providers and error/ownership continuity remain unimplemented and blocked.
"""

from dataclasses import dataclass
from enum import Enum, auto


class GenerationStep(Enum):
    RESERVED = auto()
    DATA_RW = auto()
    DATA_COPIED = auto()
    DATA_CLEAN_UNMOUNTED = auto()
    FORMATTER_REAPED = auto()
    DATA_RW_RELEASED = auto()
    TREE_RW = auto()
    TREE_DURABLE = auto()
    ALL_RW_RELEASED = auto()
    INODES_PROTECTED = auto()
    DEVICES_RO_VERIFIED = auto()
    ROLE_PUBLISHED = auto()
    LEASED = auto()
    CONSUMERS_DRAINED = auto()
    ROLE_UNPUBLISHED = auto()
    DM_REMOVED = auto()
    LOOPS_ABSENT = auto()
    BACKING_DELETED = auto()
    COMPLETE = auto()
    POISONED = auto()
    RESIDUE_RETAINED = auto()


@dataclass(frozen=True, slots=True)
class NativeFault:
    operation: str
    error_number: int
    object_serial: int
    descriptor: int | None


@dataclass(slots=True)
class OwnedDescriptor:
    """An ordinary descriptor value, not issued ownership or authority."""

    serial: int
    fd: int
    device: int
    inode: int
    mount_id: int
    consumed: bool = False


class BFailure(Exception):
    def __init__(
        self, primary: BaseException, secondary: tuple[NativeFault, ...]
    ) -> None:
        self.primary = primary
        self.secondary = secondary
        super().__init__(
            "original B operation failed; retained primary and native secondary facts"
        )
