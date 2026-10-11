"""Initial 2 GiB volume primitive; no study, ledger, lock or admission install.

Default calls authenticate protected full A+B and a separate sealed policy.
The policy has no implicit control-byte cap or freshness tolerance. OS ports
are the trusted controller boundary, replaceable only for synthetic tests.
The durable pre-image attempt is kept on success and failure. This primitive
does not issue EnforcementReceipt, clean up/quarantine mounted failures, or
implement the full ResourceEnforcer. No entry point invokes it in preparation.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict
import ctypes
import hashlib
import hmac
import json
import os
from pathlib import Path, PurePosixPath
import re
import subprocess
import threading
import uuid

from .admission_bootstrap import (
    DEFAULT_SUPERVISOR_CONFIG, MAX_SUPERVISOR_CONFIG_BYTES, MAX_CONTROLLER_KEY_BYTES,
    MAX_SEALED_ADMISSION_BYTES, parse_supervisor_config, _require_frozen_bindings,
)
from .external_admission import load_controller_sealed_admission
from .budget import (BudgetLimits, NestedBackingSample, _canonical, require_precreate_order,
                     require_fixed_native_budget, require_nested_backing_sample)
from .contracts import STUDY_ID
from .linux_supervisor import ImageVolumeReceipt
from .linux_volume_backend import (
    LinuxVolumeOSPorts, LoopState, _path, _identity, _device,
    _require_protected_stat, _close_temporary_fds, _LOOP_INFO,
)

GIB = 1 << 30
INITIAL_POLICY_PATH = f"/etc/route2/{STUDY_ID}-initial-volume.seal"
INITIAL_ATTEMPT_ROOT = "/var/lib/route2-controller/initial-volume-attempts"
LOOP_ALLOCATION_LOCK = "/var/lib/route2-controller/initial-loop.lock"
MAX_POLICY_BYTES = 65536
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_GUID = r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}"
_POLICY_FIELDS = frozenset({"schema", "study_id", "authorization_card_sha256", "owner_approval_id",
    "budget_policy_sha256", "study_image_path", "volume_path", "guest_mount_id", "guest_device",
    "distro", "distro_registry_id", "windows_vhdx_path", "windows_volume_id",
    "carrier_vhdx_path", "carrier_volume_id", "carrier_min_free_bytes",
    "host_python_path", "host_python_sha256", "host_sampler_path", "host_sampler_sha256",
    "attempt_cap_bytes", "max_free_sample_age_ns", "full_ab_seal_sha256"})


@dataclass(frozen=True, slots=True)
class InitialFreeSample:
    invocation_id: str
    sampled_monotonic_ns: int
    guest_free_bytes: int
    guest_mount_id: str
    guest_device: str
    windows_vhdx_path: str
    windows_volume_id: str
    windows_free_bytes: int
    nested_backing: NestedBackingSample


def _mounts(text):
    if type(text) is not str or not 0 < len(text) <= 4 << 20:
        raise PermissionError("initial mountinfo absent or oversized")
    result=[]
    decode=lambda s: re.sub(r"\\([0-7]{3})", lambda m:chr(int(m[1],8)), s)
    for line in text.splitlines():
        a, sep, b=line.partition(" - ")
        left,right=a.split(),b.split()
        if not sep or len(left)<6 or len(right)<3 or not left[0].isdecimal():
            raise PermissionError("initial mountinfo malformed")
        result.append((left,right,decode(left[4]),decode(left[3]),decode(right[1])))
    return result


class LinuxInitialVolumeOSPorts(LinuxVolumeOSPorts):
    """Linux descriptor operations. No operation runs at construction/import."""

    def require_live_bootstrap(self, frozen, config_bytes, seal_bytes):
        from . import admission_bootstrap as bootstrap, contracts
        with bootstrap._INSTALL_LOCK:
            issued = bootstrap._ISSUED_BOOTSTRAP
            if (issued is None or issued.consumed is not True
                    or issued.pid != os.getpid() or issued.thread is not threading.current_thread()
                    or contracts.FROZEN_ADMISSION is not issued.proof.frozen_admission
                    or issued.proof.frozen_admission != frozen
                    or issued.proof.config_sha256 != hashlib.sha256(config_bytes).hexdigest()
                    or issued.proof.seal_sha256 != hashlib.sha256(seal_bytes).hexdigest()):
                raise PermissionError("initial image requires the live claimed immutable-runtime bootstrap")

    def require_host_execution_boundary(self, policy):
        """A held Windows execution identity producer is still missing.

        Before/after byte hashes and a fresh nonce do not prove the bytes
        actually executed between them. The installed outer controller must
        hold/verify executable and script identities and enforce the worker's
        inability to mutate that installation. Refuse until that OS evidence
        producer exists; never substitute a supplied approval flag.
        """
        raise PermissionError("held Windows host execution identity boundary is not implemented")

    def require_guest_sample_mount(self, policy, sample, *, parent_fd):
        from .wsl_controller import mount_evidence
        path=Path(str(PurePosixPath(policy["study_image_path"]).parent))
        actual=mount_evidence(path)
        if (actual.fs_type!="ext4" or str(actual.mount_id)!=sample.guest_mount_id
                or str(actual.mount_id)!=policy["guest_mount_id"]
                or actual.major_minor!=sample.guest_device or actual.major_minor!=policy["guest_device"]
                or _device(self.fstat(parent_fd).st_dev)!=actual.major_minor):
            raise PermissionError("initial image parent covering mount changed since dual-layer sampling")

    def reserve_initial_attempt(self, encoded: bytes, *, cap_bytes: int) -> None:
        if type(encoded) is not bytes or type(cap_bytes) is not int or not 0 < len(encoded) <= cap_bytes <= MAX_POLICY_BYTES:
            raise PermissionError("initial attempt exceeds explicitly sealed control-byte cap")
        parent=self._open_directory(INITIAL_ATTEMPT_ROOT)
        owned=[parent]
        try:
            fd=os.open(STUDY_ID+".attempt",os.O_WRONLY|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=parent)
            owned.append(fd)
            os.fsync(fd)
            os.fsync(parent)
            if os.write(fd,encoded)!=len(encoded): raise OSError("short initial attempt write")
            os.fsync(fd)
            os.fsync(parent)
        finally:
            _close_temporary_fds(owned)

    def require_empty_directory(self, fd):
        if os.listdir(fd): raise PermissionError("initial mount target is occupied")

    def create_image(self, path, *, parent_fd=None):
        parent = parent_fd
        owned=[]
        if parent is None:
            parent=self._open_directory(str(PurePosixPath(_path(path)).parent))
            owned.append(parent)
        try:
            fd=os.open(PurePosixPath(path).name,os.O_RDWR|os.O_CREAT|os.O_EXCL|os.O_NOFOLLOW|os.O_CLOEXEC,0o600,dir_fd=parent)
            owned.append(fd)
            os.fsync(fd)
            os.fsync(parent)
            # Preallocate the backing file; logical length alone is not an
            # allocated-space guarantee on a sparse VHDX-backed ext4 volume.
            os.posix_fallocate(fd,0,2*GIB)
            os.fsync(fd)
            os.fsync(parent)
            if parent_fd is None:
                owned.remove(parent)
                os.close(parent)
            owned.remove(fd)
            return fd
        finally:
            _close_temporary_fds(owned)

    def configure_loop(self,image_fd):
        import fcntl
        # loop-control is a character device and intentionally uses its own
        # protected parent walk rather than the file/block-only base API.
        parent=self._open_directory("/dev")
        owned=[parent]
        try:
            control=os.open("loop-control",os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC,dir_fd=parent)
            owned.append(control)
            info=os.fstat(control)
            import stat
            if not stat.S_ISCHR(info.st_mode) or info.st_uid!=0 or info.st_mode & 0o002:
                raise PermissionError("untrusted loop-control")
            number=fcntl.ioctl(control,0x4C82,0)  # LOOP_CTL_GET_FREE
            if type(number) is not int or number<0: raise PermissionError("invalid free loop number")
            path=f"/dev/loop{number}"
            fd=self.open_existing(path,kind="block",writable=True)
            owned.append(fd)
            import struct
            config=struct.pack("=2I",image_fd,0)+_LOOP_INFO.pack(0,0,0,0,0,number,0,0,0,b"",b"",b"",0,0)+b"\0"*64
            fcntl.ioctl(fd,0x4C0A,config)  # LOOP_CONFIGURE, Linux >=5.8
            # Retain image inode association on failure; outer cleanup must
            # actually verify teardown before asserting quarantine/detach.
            result=fd
            owned.remove(fd)
            try: _close_temporary_fds(owned)
            except BaseException:
                os.close(result)
                raise
            return path,result
        finally:
            _close_temporary_fds(owned)

    def format_ext4(self,fd,*,timeout):
        if type(timeout) not in (int,float) or not 0<timeout<=60:
            raise PermissionError("initial formatting lacks bounded remaining wall")
        subprocess.run(("/usr/sbin/mkfs.ext4","-q","-b","4096","-m","0","-E",
            "lazy_itable_init=0,lazy_journal_init=0,nodiscard",f"/proc/self/fd/{fd}"),
            check=True,shell=False,pass_fds=(fd,),stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,timeout=timeout,env={"LC_ALL":"C","PATH":"/usr/sbin:/usr/bin:/sbin:/bin"})

    def mount_ext4(self,loop_fd,target_fd,loop_path):
        if not re.fullmatch(r"/dev/loop[0-9]+",loop_path):
            raise PermissionError("initial mount source differs from the fixed loop namespace")
        if _identity(self.fstat(loop_fd)) != _identity(self.path_stat(loop_path,kind="block")):
            raise PermissionError("initial loop path changed before mount")
        libc=ctypes.CDLL(None,use_errno=True)
        mount=libc.mount
        mount.argtypes=[ctypes.c_char_p,ctypes.c_char_p,ctypes.c_char_p,ctypes.c_ulong,ctypes.c_char_p]
        mount.restype=ctypes.c_int
        if mount(loop_path.encode(),f"/proc/self/fd/{target_fd}".encode(),b"ext4",2|4|8,b"")!=0:
            raise OSError(ctypes.get_errno(),"initial ext4 mount failed")

    def sample_free(self,policy,invocation_id,*,parent_fd):
        from .wsl_controller import mount_evidence
        image_parent=str(PurePosixPath(policy["study_image_path"]).parent)
        fd=parent_fd
        try:
            started=self.monotonic_ns()
            before=self.fstat(fd)
            mount=mount_evidence(Path(image_parent))
            values=os.fstatvfs(fd)
            if mount.fs_type!="ext4" or _device(before.st_dev)!=mount.major_minor:
                raise PermissionError("initial backing is not the actual held ext4 device")
            nonce=uuid.uuid4().hex
            identities=[]
            for path,key,cap in ((policy["host_python_path"],"host_python_sha256",64<<20),
                                 (policy["host_sampler_path"],"host_sampler_sha256",1<<20)):
                data=_host_file_bytes(path,cap)
                if hashlib.sha256(data).hexdigest()!=policy[key]: raise PermissionError("host sampler/code identity drift")
                identities.append(data)
            sampler=_windows_path(policy["host_sampler_path"])
            request=_canonical(dict(schema="route2_host_backing_sample_v2",
                distro=policy["distro"],distro_registry_id=policy["distro_registry_id"],
                windows_vhdx_path=policy["windows_vhdx_path"],windows_volume_id=policy["windows_volume_id"],
                carrier_vhdx_path=policy["carrier_vhdx_path"],carrier_volume_id=policy["carrier_volume_id"],
                nonce=nonce)).decode()
            response=_bounded_host_output((policy["host_python_path"],"-I","-B",sampler,request))
            sample=json.loads(response)
            expected={"schema","nonce","distro","distro_registry_id","windows_vhdx_path","windows_volume_id",
                "carrier_vhdx_path","carrier_volume_id","available_bytes","total_free_bytes",
                "carrier_available_bytes","carrier_total_free_bytes","carrier_file_identity",
                "guest_vhdx_file_identity","carrier_disk_number","physical_disk_number"}
            if (type(sample) is not dict or set(sample)!=expected
                    or any(sample[k]!=v for k,v in json.loads(request).items())
                    or _canonical(sample) != response.rstrip(b"\n")
                    or any(type(sample[k]) is not int or sample[k]<0 for k in
                           ("available_bytes","total_free_bytes","carrier_available_bytes","carrier_total_free_bytes"))):
                raise PermissionError("live host volume sample not bound to the request")
            nested=NestedBackingSample(policy["carrier_vhdx_path"],policy["carrier_volume_id"],
                min(sample["carrier_available_bytes"],sample["carrier_total_free_bytes"]),
                policy["carrier_min_free_bytes"],sample["carrier_disk_number"],sample["physical_disk_number"],
                _canonical(sample).decode("utf-8"))
            physical_free=min(sample["available_bytes"],sample["total_free_bytes"])
            require_nested_backing_sample(nested,windows_vhdx_path=policy["windows_vhdx_path"],
                windows_volume_id=policy["windows_volume_id"],windows_free_bytes=physical_free)
            for (path,cap),data in zip(((policy["host_python_path"],64<<20),(policy["host_sampler_path"],1<<20)),identities):
                if _host_file_bytes(path,cap)!=data: raise PermissionError("host sampler changed during invocation")
            # Re-sample guest after the host call. Linux clock bounds the
            # whole synchronous sample; no host/guest epoch subtraction.
            values=os.fstatvfs(fd)
            after=self.path_stat(image_parent,kind="directory")
            fresh=mount_evidence(Path(image_parent))
            if _identity(before)!=_identity(after) or (fresh.mount_id,fresh.major_minor)!=(mount.mount_id,mount.major_minor):
                raise PermissionError("guest backing identity changed during host sampling")
            return InitialFreeSample(invocation_id,started,values.f_bavail*values.f_frsize,
                str(fresh.mount_id),fresh.major_minor,policy["windows_vhdx_path"],policy["windows_volume_id"],
                physical_free,nested)
        finally:
            # This descriptor belongs to the creator and remains held through
            # the exclusive create. Sampling never closes a borrowed parent.
            pass


def _windows_path(path):
    if type(path) is not str or not re.fullmatch(r"/mnt/[a-z]/[^\s]+",path) or ".." in PurePosixPath(path).parts:
        raise PermissionError("host sampler requires a canonical local DrvFS path")
    return path[5].upper()+":\\"+path[7:].replace("/","\\")


def _bounded_host_output(argv):
    """Read at most 4097 raw bytes while enforcing a finite child wait."""
    import selectors
    import time
    process=subprocess.Popen(argv,shell=False,stdin=subprocess.DEVNULL,
        stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,
        env={"WSL_INTEROP":os.environ.get("WSL_INTEROP",""),"LC_ALL":"C"})
    result=bytearray()
    try:
        with selectors.DefaultSelector() as selector:
            os.set_blocking(process.stdout.fileno(),False)
            selector.register(process.stdout,selectors.EVENT_READ)
            deadline=time.monotonic()+30
            while True:
                remaining=deadline-time.monotonic()
                if remaining<=0: raise TimeoutError("host sampler timed out")
                if not selector.select(min(remaining,1)): continue
                block=os.read(process.stdout.fileno(),4097-len(result))
                if not block: break
                result.extend(block)
                if len(result)>4096: raise PermissionError("host sampler raw output exceeded 4096 bytes")
            process.wait(timeout=max(0.001,deadline-time.monotonic()))
            if process.returncode!=0: raise PermissionError("host sampler failed")
        return bytes(result)
    finally:
        try:
            if process.poll() is None:
                process.kill()
                process.wait(timeout=5)
        finally:
            process.stdout.close()


def _require_initial_loop(ports,loop,loop_path,image_stat):
    state=ports.loop_state(loop)
    if (type(state) is not LoopState or any(type(v) is not int for v in asdict(state).values())
            or (state.backing_device,state.backing_inode,state.number,state.offset,state.sizelimit,state.flags,state.capacity_bytes)!=
            (image_stat.st_dev,image_stat.st_ino,int(loop_path[9:]),0,0,0,2*GIB)
            or _device(ports.fstat(loop).st_rdev)!=f"7:{state.number}"):
        raise PermissionError("initial loop association, flags or capacity changed")
    return state


def _host_file_bytes(path,cap):
    _windows_path(path)
    descriptor=os.open(path,os.O_RDONLY|os.O_NOFOLLOW|os.O_CLOEXEC|os.O_NONBLOCK)
    try:
        import stat
        a=os.fstat(descriptor)
        if not stat.S_ISREG(a.st_mode) or not 0<a.st_size<=cap: raise PermissionError("host identity file invalid")
        data=os.read(descriptor,cap+1)
        b=os.fstat(descriptor)
        visible=os.stat(path,follow_symlinks=False)
        if (len(data)!=a.st_size or (a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)!=(b.st_dev,b.st_ino,b.st_size,b.st_mtime_ns)
                or (visible.st_dev,visible.st_ino,visible.st_size,visible.st_mtime_ns)!=(a.st_dev,a.st_ino,a.st_size,a.st_mtime_ns)):
            raise PermissionError("host identity file changed")
        return data
    finally: os.close(descriptor)


class LinuxInitialVolumeCreator:
    def __init__(self,*,ports=None):
        self._ports=ports if ports is not None else LinuxInitialVolumeOSPorts()
        self._lock=threading.Lock()
        self._attempted=False

    def _policy(self):
        p=self._ports
        config_raw=p.read_protected_file(DEFAULT_SUPERVISOR_CONFIG,max_bytes=MAX_SUPERVISOR_CONFIG_BYTES)
        config=parse_supervisor_config(config_raw)
        key=p.read_protected_file(config.controller_key_path,max_bytes=MAX_CONTROLLER_KEY_BYTES)
        seal=p.read_protected_file(config.sealed_admission_path,max_bytes=MAX_SEALED_ADMISSION_BYTES)
        frozen=load_controller_sealed_admission(seal,controller_key=key,
            expected_source_snapshot_sha256=config.source_snapshot_sha256,expected_runtime_snapshot_sha256=config.runtime_snapshot_sha256,
            expected_review_id=config.independent_review_id,expected_owner_approval_id=config.owner_approval_id,
            expected_authorization_card_sha256=config.authorization_card_sha256)
        _require_frozen_bindings(config,frozen)
        encoded=p.read_protected_file(INITIAL_POLICY_PATH,max_bytes=MAX_POLICY_BYTES)
        try:
            value=json.loads(encoded)
            if (type(value) is not dict or set(value)!={"body","controller_hmac_sha256"} or _canonical(value)!=encoded
                    or not hmac.compare_digest(hmac.new(key,_canonical(value["body"]),hashlib.sha256).hexdigest(),value["controller_hmac_sha256"])):
                raise ValueError("bad seal")
            policy=value["body"]
            if type(policy) is not dict or set(policy)!=_POLICY_FIELDS: raise ValueError("policy fields")
            bindings=dict(schema="route2_initial_volume_policy_v2",study_id=STUDY_ID,
                authorization_card_sha256=config.authorization_card_sha256,owner_approval_id=config.owner_approval_id,
                budget_policy_sha256=frozen.budget_policy_sha256,study_image_path=frozen.study_image_path,
                volume_path=frozen.approved_write_volumes[0],full_ab_seal_sha256=hashlib.sha256(seal).hexdigest())
            if any(policy[k]!=v for k,v in bindings.items()): raise ValueError("policy binding")
            for k in ("attempt_cap_bytes","max_free_sample_age_ns","carrier_min_free_bytes"):
                if type(policy[k]) is not int or policy[k]<=0: raise ValueError("policy integer")
            if policy["attempt_cap_bytes"]>MAX_POLICY_BYTES: raise ValueError("control cap")
            if (type(policy["guest_mount_id"]) is not str or not policy["guest_mount_id"].isdecimal()
                    or int(policy["guest_mount_id"])<=0 or not re.fullmatch(r"[0-9]+:[0-9]+",policy["guest_device"])
                    or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}",policy["distro"])
                    or not re.fullmatch(r"\{"+_GUID+r"\}",policy["distro_registry_id"])
                    or not re.fullmatch(r"\\\\\?\\Volume\{"+_GUID+r"\}\\",policy["windows_volume_id"])
                    or not re.fullmatch(r"\\\\\?\\Volume\{"+_GUID+r"\}\\",policy["carrier_volume_id"])
                    or policy["carrier_volume_id"]==policy["windows_volume_id"]
                    or not re.fullmatch(r"[A-Z]:\\[^\s]+\\ext4\.vhdx",policy["windows_vhdx_path"])):
                raise ValueError("backing identity")
            carrier=policy["carrier_vhdx_path"]
            from pathlib import PureWindowsPath
            if (type(carrier) is not str or not PureWindowsPath(carrier).is_absolute()
                    or str(PureWindowsPath(carrier))!=carrier
                    or not re.fullmatch(r"[A-Z]:",PureWindowsPath(carrier).drive)
                    or ".." in PureWindowsPath(carrier).parts or PureWindowsPath(carrier).suffix!=".vhdx"
                    or carrier==policy["windows_vhdx_path"]):
                raise ValueError("carrier backing file identity")
            for name in ("host_python","host_sampler"):
                _windows_path(policy[name+"_path"])
                if not _SHA.fullmatch(policy[name+"_sha256"]): raise ValueError("host identity digest")
        except (ValueError,TypeError,KeyError,RecursionError) as exc:
            raise PermissionError("initial volume policy is not an authenticated complete decision") from exc
        p.require_live_bootstrap(frozen,config_raw,seal)
        return frozen,policy,(config_raw,key,seal,encoded)

    def create_stage_a_volume(self,invocation_id,limits,*,invocation_started_ns):
        with self._lock:
            if self._attempted: raise PermissionError("initial volume is once-only; retry forbidden")
            p=self._ports
            p.require_linux_root()
            frozen,policy,policy_bytes=self._policy()
            p.require_host_execution_boundary(policy)
            require_fixed_native_budget(limits)
            if (limits.digest()!=frozen.budget_policy_sha256
                    or type(invocation_id) is not str or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}",invocation_id)
                    or type(invocation_started_ns) is not int or invocation_started_ns<=0):
                raise PermissionError("initial volume lacks exact invocation and approved budget")
            deadline=invocation_started_ns+min(limits.total_wall_ns,limits.stage_a_wall_ns)
            if not invocation_started_ns<=p.monotonic_ns()<deadline: raise PermissionError("invocation clock invalid/expired")
            attempt=_canonical(dict(schema="route2_initial_volume_attempt_v1",study_id=STUDY_ID,
                invocation_id=invocation_id,invocation_started_monotonic_ns=invocation_started_ns,
                policy_sha256=hashlib.sha256(policy_bytes[-1]).hexdigest(),image_path=frozen.study_image_path,
                volume_path=policy["volume_path"],image_bytes=2*GIB))+b"\n"
            if len(attempt)>policy["attempt_cap_bytes"]: raise PermissionError("initial marker cap insufficient")
            self._attempted=True
            p.reserve_initial_attempt(attempt,cap_bytes=policy["attempt_cap_bytes"])
            owned=[]
            try:
                gate=p.open_existing(LOOP_ALLOCATION_LOCK,kind="file")
                owned.append(gate); p.lock_exclusive(gate)
                target=p.open_existing(policy["volume_path"],kind="directory")
                owned.append(target); p.require_empty_directory(target)
                target_identity=_identity(p.fstat(target))
                image_parent_path=str(PurePosixPath(frozen.study_image_path).parent)
                image_parent=p.open_existing(image_parent_path,kind="directory")
                owned.append(image_parent)
                parent_identity=_identity(p.fstat(image_parent))
                for path in (frozen.study_image_path,frozen.study_root_path,frozen.budget_ledger_path,frozen.lock_path):
                    try: p.path_stat(path,kind="file" if path!=frozen.study_root_path else "directory")
                    except FileNotFoundError: pass
                    else: raise FileExistsError("initial namespace occupied")
                if any(point==policy["volume_path"] or point.startswith(policy["volume_path"]+"/")
                       or point.startswith(("/run/route2-input","/run/route2-worker")) for _,_,point,_,_ in _mounts(p.mountinfo())):
                    raise PermissionError("initial namespace already mounted")
                sample=p.sample_free(policy,invocation_id,parent_fd=image_parent)
                if type(sample) is not InitialFreeSample:
                    raise PermissionError("initial image lacks its native V2 backing sample")
                require_nested_backing_sample(sample.nested_backing,
                    windows_vhdx_path=sample.windows_vhdx_path,windows_volume_id=sample.windows_volume_id,
                    windows_free_bytes=sample.windows_free_bytes)
                if (sample.nested_backing.carrier_vhdx_path!=policy["carrier_vhdx_path"]
                        or sample.nested_backing.carrier_volume_id!=policy["carrier_volume_id"]
                        or sample.nested_backing.carrier_min_free_bytes!=policy["carrier_min_free_bytes"]
                        or sample.nested_backing.carrier_free_bytes<policy["carrier_min_free_bytes"]):
                    raise PermissionError("initial image fails the independently sealed carrier reserve")
                now=p.monotonic_ns()
                if (type(sample) is not InitialFreeSample or sample.invocation_id!=invocation_id
                    or (sample.guest_mount_id,sample.guest_device,sample.windows_vhdx_path,sample.windows_volume_id)!=
                       (policy["guest_mount_id"],policy["guest_device"],policy["windows_vhdx_path"],policy["windows_volume_id"])
                    or any(type(x) is not int for x in (sample.sampled_monotonic_ns,sample.guest_free_bytes,sample.windows_free_bytes))
                    or not invocation_started_ns<=sample.sampled_monotonic_ns<=now<deadline
                    or now-sample.sampled_monotonic_ns>policy["max_free_sample_age_ns"]
                    or min(sample.guest_free_bytes,sample.windows_free_bytes)<8*GIB):
                    raise PermissionError("fresh dual-layer 8 GiB free gate failed")
                if (self._policy()[2]!=policy_bytes
                        or _identity(p.path_stat(policy["volume_path"],kind="directory"))!=target_identity
                        or _identity(p.path_stat(image_parent_path,kind="directory"))!=parent_identity
                        or _identity(p.fstat(image_parent))!=parent_identity):
                    raise PermissionError("admission or target drift before image creation")
                p.require_guest_sample_mount(policy,sample,parent_fd=image_parent)
                now=p.monotonic_ns()
                if now>=deadline or now-sample.sampled_monotonic_ns>policy["max_free_sample_age_ns"]:
                    raise PermissionError("dual free sample expired before image creation")
                image=p.create_image(frozen.study_image_path,parent_fd=image_parent); owned.append(image)
                created=p.monotonic_ns()
                require_precreate_order(invocation_started_ns,sample.sampled_monotonic_ns,created,
                    sample.guest_free_bytes,sample.windows_free_bytes,limits.startup_free_disk_bytes)
                image_stat=p.fstat(image); _require_protected_stat(image_stat,"file")
                if (image_stat.st_size!=2*GIB or _device(image_stat.st_dev)!=sample.guest_device
                        or _identity(p.path_stat(image_parent_path,kind="directory"))!=parent_identity
                        or _identity(p.path_stat(frozen.study_image_path,kind="file"))!=_identity(image_stat)):
                    raise PermissionError("initial image escaped the sampled held parent/device or length cap")
                loop_path,loop=p.configure_loop(image); owned.append(loop)
                if not re.fullmatch(r"/dev/loop[0-9]+",loop_path): raise PermissionError("initial loop path invalid")
                _require_initial_loop(p,loop,loop_path,image_stat)
                remaining=(deadline-p.monotonic_ns())/1e9
                if remaining<=0: raise PermissionError("initial formatting wall expired")
                p.format_ext4(loop,timeout=min(60,remaining)); p.fsync(loop); p.fsync(image)
                p.mount_ext4(loop,target,loop_path)
                volume=p.open_existing(policy["volume_path"],kind="directory"); owned.append(volume)
                p.fsync(volume)
                visible=p.path_stat(frozen.study_image_path,kind="file")
                state=_require_initial_loop(p,loop,loop_path,image_stat)
                if (_identity(visible)!=_identity(image_stat) or p.fstat(image).st_size!=2*GIB
                        or visible.st_size!=2*GIB):
                    raise PermissionError("initial image or loop identity changed")
                records=_mounts(p.mountinfo())
                rows=[r for r in records if r[2]==policy["volume_path"]]
                if len(rows)!=1: raise PermissionError("initial mounted volume absent/stacked")
                left,right,_,root,source=rows[0]
                if (root!="/" or source!=loop_path or right[0]!="ext4"
                        or not {"rw","nosuid","nodev","noexec"}<=set(left[5].split(","))
                        or "ro" in right[2].split(",") or any(v.startswith("shared:") for v in left[6:])
                        or left[2]!=f"7:{state.number}" or _device(p.fstat(volume).st_dev)!=left[2]
                        or any(r[2].startswith(policy["volume_path"]+"/") for r in records)):
                    raise PermissionError("initial mounted volume flags/device/propagation changed")
                fs_uuid=p.filesystem_uuid(loop)
                if str(uuid.UUID(fs_uuid))!=fs_uuid: raise PermissionError("invalid initial filesystem UUID")
                capacity=p.filesystem_capacity(volume)
                if type(capacity) is not int or not 0<capacity<=2*GIB: raise PermissionError("initial actual filesystem cap invalid")
                if self._policy()[2]!=policy_bytes or p.monotonic_ns()>deadline: raise PermissionError("initial policy drift/wall expired")
                return ImageVolumeReceipt(invocation_id,STUDY_ID,frozen.study_root_path,frozen.budget_ledger_path,
                    frozen.lock_path,frozen.study_image_path,created,image_stat.st_dev,image_stat.st_ino,
                    loop_path,fs_uuid,left[0],left[2],capacity,2*GIB),sample
            finally:
                failure=None
                while owned:
                    descriptor=owned.pop()
                    try: p.close(descriptor)
                    except BaseException as exc: failure=failure or exc
                if failure is not None: raise failure
