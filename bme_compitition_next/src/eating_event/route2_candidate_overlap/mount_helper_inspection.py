"""Bounded, nonexecuting inspection of a *candidate* mount helper artifact.

This preparation reader accepts bytes, never paths, file descriptors, native
handles, callbacks or approval objects. It neither loads a library nor reads
GT. Its result is descriptive data, not a loader identity or installation
receipt. Even a matching digest/ABI cannot establish immutable storage,
symbol resolution, transitive dependencies or pre-import launch continuity.

ELF layouts: https://refspecs.linuxfoundation.org/elf/gabi4+/contents.html
The deliberately restricted input is ELF64 little-endian x86-64 ET_DYN with
ordinary program-header numbering. Unsupported layouts refuse explicitly.
Resource bounds below are parser limits, not approved preparation budgets.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import struct


_MAX_IMAGE_BYTES = 8 * 1024 * 1024
_MAX_PROGRAM_HEADERS = 128
_MAX_DYNAMIC_ENTRIES = 4096
_MAX_NOTES = 128
_MAX_STRING_BYTES = 4096
_U64_MAX = (1 << 64) - 1
_ELF_HEADER = struct.Struct("<16sHHIQQQIHHHHHH")
_PROGRAM_HEADER = struct.Struct("<IIQQQQQQ")
_DYNAMIC_ENTRY = struct.Struct("<qQ")
_NOTE_HEADER = struct.Struct("<III")
_ABI = struct.Struct("<10I")
_ABI_VALUES = (1, 2, 35, 8, 8, 32, 0, 8, 16, 24)
_PT_LOAD = 1
_PT_DYNAMIC = 2
_PT_NOTE = 4
_DT_STRTAB = 5
_DT_STRSZ = 10
_STRING_TAGS = frozenset({1, 14, 15, 29})  # NEEDED, SONAME, RPATH, RUNPATH
# This restricted helper format does not support filtees, auditors or an
# alternate loader configuration. Refuse their string tags rather than
# publishing an incomplete dependency/search inventory. glibc 2.35 elf.h:
# https://raw.githubusercontent.com/bminor/glibc/glibc-2.35/elf/elf.h
_UNSUPPORTED_STRING_TAGS = frozenset({0x7ffffffd, 0x7fffffff,
                                    0x6ffffefa, 0x6ffffefb, 0x6ffffefc})
_INIT_TAGS = frozenset({12, 13, 25, 26, 27, 28, 32, 33})


@dataclass(frozen=True, slots=True)
class CandidateProgramHeader:
    kind: int
    flags: int
    file_offset: int
    virtual_address: int
    file_bytes: int
    memory_bytes: int
    alignment: int


@dataclass(frozen=True, slots=True)
class CandidateHelperELF:
    """An inventory only; constructors and symbol providers remain unproven."""

    schema: str
    image_sha256: str
    image_bytes: int
    os_abi: int
    program_headers: tuple[CandidateProgramHeader, ...]
    dynamic_entries: tuple[tuple[int, int], ...]
    needed: tuple[str, ...]
    soname: str | None
    rpath: str | None
    runpath: str | None
    initialization_entries: tuple[tuple[int, int], ...]
    gnu_build_id: str | None


def _deny(message: str):
    raise ValueError("candidate helper inspection: " + message)


def _range(total: int, offset: int, size: int) -> None:
    if not 0 <= offset <= total or not 0 <= size <= total - offset:
        _deny("file range lies outside the bounded image")


def _virtual_file_offset(loads, address: int, size: int) -> int:
    if not 0 <= address <= _U64_MAX or not 0 <= size <= _U64_MAX - address:
        _deny("virtual-address range overflows ELF64")
    candidates = [item.file_offset + address - item.virtual_address for item in loads
                  if item.virtual_address <= address
                  and address - item.virtual_address <= item.file_bytes
                  and size <= item.file_bytes - (address - item.virtual_address)]
    if len(candidates) != 1:
        _deny("dynamic range lacks one unambiguous file-backed PT_LOAD")
    return candidates[0]


def _single(entries, tag: int, *, required=False):
    values = [value for kind, value in entries if kind == tag]
    if len(values) > 1 or (required and len(values) != 1):
        _deny("required/unique dynamic tag is missing or duplicated")
    return values[0] if values else None


def _program_headers(encoded: bytes, offset: int, count: int):
    headers = []
    for index in range(count):
        kind, flags, file_offset, address, _, file_size, memory_size, alignment = (
            _PROGRAM_HEADER.unpack_from(encoded, offset + index * _PROGRAM_HEADER.size))
        _range(len(encoded), file_offset, file_size)
        if memory_size > _U64_MAX - address:
            _deny("program segment virtual range overflows ELF64")
        if alignment not in (0, 1) and alignment & (alignment - 1):
            _deny("program segment alignment is not a power of two")
        if kind == _PT_LOAD:
            if (file_size > memory_size or not flags & 4 or flags & ~7
                    or (alignment > 1 and address % alignment != file_offset % alignment)):
                _deny("PT_LOAD layout is outside the restricted helper format")
        headers.append(CandidateProgramHeader(kind, flags, file_offset, address,
                                             file_size, memory_size, alignment))
    loads = tuple(item for item in headers if item.kind == _PT_LOAD)
    if not loads or not any(item.flags & 1 for item in loads):
        _deny("candidate shared helper has no executable PT_LOAD")
    # Do not guess which overlapping mapping the installed loader would use.
    ordered = sorted((item for item in loads if item.memory_bytes), key=lambda item: item.virtual_address)
    if any(left.virtual_address + left.memory_bytes > right.virtual_address
           for left, right in zip(ordered, ordered[1:])):
        _deny("overlapping PT_LOAD virtual ranges require separate review")
    return tuple(headers), loads


def _dynamic(encoded: bytes, headers, loads):
    segments = [item for item in headers if item.kind == _PT_DYNAMIC]
    if len(segments) != 1:
        _deny("candidate helper requires exactly one PT_DYNAMIC")
    segment = segments[0]
    if (not segment.file_bytes or segment.file_bytes % _DYNAMIC_ENTRY.size
            or segment.file_bytes // _DYNAMIC_ENTRY.size > _MAX_DYNAMIC_ENTRIES
            or _virtual_file_offset(loads, segment.virtual_address, segment.file_bytes) != segment.file_offset):
        _deny("PT_DYNAMIC is unbounded, misaligned or differs from its load mapping")
    entries = []
    terminated = False
    for relative in range(0, segment.file_bytes, _DYNAMIC_ENTRY.size):
        tag, value = _DYNAMIC_ENTRY.unpack_from(encoded, segment.file_offset + relative)
        if terminated:
            if tag != 0 or value != 0:
                _deny("nonzero data follows the dynamic terminator")
        elif tag == 0:
            if value != 0:
                _deny("nonzero dynamic terminator is outside the restricted format")
            terminated = True
        else:
            if tag in _UNSUPPORTED_STRING_TAGS:
                _deny("FILTER/AUXILIARY/CONFIG/AUDIT/DEPAUDIT requires separate format support")
            entries.append((tag, value))
    if not terminated:
        _deny("PT_DYNAMIC lacks a bounded DT_NULL terminator")
    return tuple(entries)


def _dynamic_strings(encoded: bytes, entries, loads):
    references = tuple((tag, value) for tag, value in entries if tag in _STRING_TAGS)
    address = _single(entries, _DT_STRTAB, required=True)
    size = _single(entries, _DT_STRSZ, required=True)
    if not 0 < size <= _MAX_IMAGE_BYTES:
        _deny("dynamic string table is empty or exceeds the image bound")
    offset = _virtual_file_offset(loads, address, size)
    _range(len(encoded), offset, size)
    if encoded[offset] != 0 or encoded[offset + size - 1] != 0:
        _deny("dynamic string table lacks its first/final NUL")
    strings = []
    for tag, index in references:
        if not 0 <= index < size:
            _deny("dynamic string index escapes DT_STRSZ")
        end = encoded.find(b"\0", offset + index,
                           min(offset + size, offset + index + _MAX_STRING_BYTES + 1))
        if end < 0:
            _deny("dynamic string is unterminated or exceeds its bound")
        value = encoded[offset + index:end]
        if not value or any(byte < 0x20 or byte > 0x7e for byte in value):
            _deny("dynamic name/search path is empty or outside printable ASCII")
        strings.append((tag, value.decode("ascii")))
    needed = tuple(value for tag, value in strings if tag == 1)
    optional = []
    for tag in (14, 15, 29):
        values = [value for kind, value in strings if kind == tag]
        if len(values) > 1:
            _deny("SONAME/RPATH/RUNPATH is duplicated")
        optional.append(values[0] if values else None)
    return needed, *optional


def _build_id(encoded: bytes, headers):
    build_ids = []
    count = 0
    note_ranges = sorted((item.file_offset, item.file_offset + item.file_bytes, item.alignment)
                         for item in headers if item.kind == _PT_NOTE and item.file_bytes)
    if any(left[1] > right[0] for left, right in zip(note_ranges, note_ranges[1:])):
        _deny("overlapping PT_NOTE ranges require separate review")
    for start, end, alignment in note_ranges:
        if alignment not in (4, 8) or start % alignment:
            _deny("PT_NOTE requires a supported aligned 4/8-byte layout")
        cursor = start
        while cursor < end:
            count += 1
            if count > _MAX_NOTES or end - cursor < _NOTE_HEADER.size:
                _deny("note list is unbounded or truncated")
            name_size, descriptor_size, kind = _NOTE_HEADER.unpack_from(encoded, cursor)
            cursor += _NOTE_HEADER.size
            descriptor_start = (cursor + name_size + alignment - 1) & ~(alignment - 1)
            next_note = (descriptor_start + descriptor_size + alignment - 1) & ~(alignment - 1)
            if name_size > end - cursor or descriptor_start > end or next_note > end:
                _deny("note fields escape their PT_NOTE")
            name = encoded[cursor:cursor + name_size]
            if name == b"GNU\0" and kind == 3:
                if not 1 <= descriptor_size <= 64:
                    _deny("GNU build-id has an unsupported size")
                build_ids.append(encoded[descriptor_start:descriptor_start + descriptor_size].hex())
            cursor = next_note
    if len(build_ids) > 1:
        _deny("more than one GNU build-id was observed")
    return build_ids[0] if build_ids else None


def inspect_candidate_helper_elf(encoded: bytes) -> CandidateHelperELF:
    """Inventory program/dynamic metadata without executing any candidate code.

    This does NOT validate symbol exports, relocations, symbol versions,
    constructor code, dependency identities, mount immutability or actual
    loaded mappings. Do not use this return value as a production gate.
    """
    if type(encoded) is not bytes or not _ELF_HEADER.size <= len(encoded) <= _MAX_IMAGE_BYTES:
        _deny("input must be plain bounded ELF bytes")
    (ident, kind, machine, version, entry, offset, _, flags, header_size,
     program_size, count, _, _, _) = _ELF_HEADER.unpack_from(encoded)
    if (ident[:7] != b"\x7fELF\x02\x01\x01" or ident[7] not in (0, 3)
            or ident[8:] != b"\0" * 8 or (kind, machine, version, entry, flags) != (3, 62, 1, 0, 0)
            or header_size != _ELF_HEADER.size or program_size != _PROGRAM_HEADER.size
            or not 1 <= count <= _MAX_PROGRAM_HEADERS or offset < _ELF_HEADER.size):
        _deny("unsupported ELF header/ABI/program-header numbering")
    _range(len(encoded), offset, count * _PROGRAM_HEADER.size)
    headers, loads = _program_headers(encoded, offset, count)
    dynamic = _dynamic(encoded, headers, loads)
    needed, soname, rpath, runpath = _dynamic_strings(encoded, dynamic, loads)
    return CandidateHelperELF(
        "route2_mount_helper_elf_preparation_inventory_v1",
        hashlib.sha256(encoded).hexdigest(), len(encoded), ident[7], headers,
        dynamic, needed, soname, rpath, runpath,
        tuple(item for item in dynamic if item[0] in _INIT_TAGS),
        _build_id(encoded, headers),
    )


def inspect_candidate_mount_abi(encoded: bytes) -> tuple[int, ...]:
    """Decode the exact 40-byte C/H descriptor; origin is NOT attested.

    These values can be fabricated freely. A production loader must validate
    original native identity BEFORE calling describe_v1 and must validate the
    actual callable ABI/mappings separately. This function grants no authority.
    """
    if type(encoded) is not bytes or len(encoded) != _ABI.size:
        _deny("ABI description must be exactly 40 plain bytes")
    values = _ABI.unpack(encoded)
    if values != _ABI_VALUES:
        _deny("ABI description differs from the reviewed source baseline")
    return values
