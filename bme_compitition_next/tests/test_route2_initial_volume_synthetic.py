"""Initial volume preparation tests: all syscalls use synthetic ports."""
from dataclasses import asdict
import hashlib
import hmac
import importlib
import json
import stat
from types import SimpleNamespace

import pytest

from test_route2_linux_volume_backend_synthetic import frozen, canonical, KEY, UUID
from test_route2_linux_volume_fd_cleanup_synthetic import syscalls, no_leak_or_retry
from eating_event.route2_candidate_overlap.budget import BudgetLimits
from eating_event.route2_candidate_overlap.contracts import STUDY_ID
from eating_event.route2_candidate_overlap.linux_volume_backend import LoopState

MODULE = "eating_event.route2_candidate_overlap.linux_initial_volume"
GIB = 1 << 30


@pytest.fixture
def rig():
    m = importlib.import_module(MODULE)
    admission = frozen()
    config = dict(schema="route2_external_supervisor_config_v1", study_id=STUDY_ID,
        controller_key_path="/etc/route2/synthetic.key", sealed_admission_path="/etc/route2/synthetic.seal",
        source_snapshot_root=admission.source_snapshot_root, source_manifest_path=admission.source_snapshot_manifest_path,
        source_snapshot_sha256=admission.source_snapshot_sha256,
        source_module_relative_path="src/eating_event/route2_candidate_overlap/admission_bootstrap.py",
        runtime_snapshot_root=admission.runtime_snapshot_root, runtime_manifest_path=admission.runtime_snapshot_manifest_path,
        runtime_snapshot_sha256=admission.runtime_snapshot_sha256, source_mount_path=admission.source_snapshot_root,
        runtime_mount_path=admission.runtime_snapshot_root, independent_review_id="synthetic-review",
        owner_approval_id=admission.approval_record, authorization_card_sha256="b" * 64)
    ab = dict(schema="route2_controller_sealed_admission_v1", study_id=STUDY_ID,
        independent_review_id=config["independent_review_id"], review_result="PASS",
        owner_approval_id=admission.approval_record, owner_approved=True, approval_scope="A+B",
        authorization_card_sha256="b" * 64, source_snapshot_sha256=admission.source_snapshot_sha256,
        runtime_snapshot_sha256=admission.runtime_snapshot_sha256, frozen_admission=asdict(admission))
    policy = dict(schema="route2_initial_volume_policy_v1", study_id=STUDY_ID,
        authorization_card_sha256="b" * 64, owner_approval_id=admission.approval_record,
        budget_policy_sha256=admission.budget_policy_sha256,
        study_image_path=admission.study_image_path, volume_path=admission.approved_write_volumes[0],
        guest_mount_id="5", guest_device="8:1", distro="Ubuntu-22.04",
        distro_registry_id="{11111111-2222-3333-4444-555555555555}",
        windows_vhdx_path="C:\\synthetic\\ext4.vhdx",
        windows_volume_id="\\\\?\\Volume{11111111-2222-3333-4444-555555555555}\\",
        host_python_path="/mnt/c/synthetic/python.exe", host_python_sha256="c" * 64,
        host_sampler_path="/mnt/c/synthetic/route2_host_volume_sample.py", host_sampler_sha256="d" * 64,
        full_ab_seal_sha256="e"*64,
        attempt_cap_bytes=4096, max_free_sample_age_ns=1000)

    def seal(body):
        return canonical(dict(body=body, controller_hmac_sha256=hmac.new(KEY, canonical(body), hashlib.sha256).hexdigest()))
    policy["full_ab_seal_sha256"]=hashlib.sha256(seal(ab)).hexdigest()

    class FakeOS:
        def __init__(self):
            self.trace, self.fds, self.closed = [], {}, []
            self.marker = False
            self.fail = None
            self.guest_free = self.host_free = 9 * GIB
            self.mount_id, self.device, self.loop_backing = "5", "8:1", 99
            self.now, self.mounted, self.image_length = 100, False, 0
            self.policy = policy
            self.ab = ab

        def require_linux_root(self): self.trace.append("root")
        def require_live_bootstrap(self, frozen, config_bytes, seal_bytes):
            self.trace.append("bootstrap")
            self.check("bootstrap")
        def require_host_execution_boundary(self, policy): self.check("host_boundary")
        def require_guest_sample_mount(self, policy, sample, *, parent_fd):
            if self.mount_id!=sample.guest_mount_id or self.device!=sample.guest_device:
                raise PermissionError("synthetic covering mount changed")
        def read_protected_file(self, path, *, max_bytes):
            data = {str(m.DEFAULT_SUPERVISOR_CONFIG): canonical(config), config["controller_key_path"]: KEY,
                    config["sealed_admission_path"]: seal(self.ab), m.INITIAL_POLICY_PATH: seal(self.policy)}[str(path)]
            assert len(data) <= max_bytes
            return data
        def monotonic_ns(self): self.now += 1; return self.now
        def reserve_initial_attempt(self, encoded, *, cap_bytes):
            if self.marker: raise FileExistsError("occupied")
            self.marker = True
            self.trace.append("attempt_durable")
            assert len(encoded) <= cap_bytes
            self.check("attempt")
        def sample_free(self, policy, invocation_id, *, parent_fd):
            assert self.fds[parent_fd]==(str(__import__('pathlib').PurePosixPath(admission.study_image_path).parent),"directory")
            self.trace.append("sample")
            return m.InitialFreeSample(invocation_id, self.monotonic_ns(), self.guest_free,
                self.mount_id, self.device, policy["windows_vhdx_path"], policy["windows_volume_id"], self.host_free)
        def check(self, phase):
            if self.fail == phase: raise OSError("synthetic " + phase)
        def open_existing(self, path, *, kind, writable=False):
            fd = 10 + len(self.fds); self.fds[fd] = (path, kind)
            self.trace.append(("open", path)); return fd
        def path_stat(self, path, *, kind):
            if path == admission.study_image_path and not self.image_length: raise FileNotFoundError(path)
            if path in (admission.study_root_path, admission.lock_path, admission.budget_ledger_path): raise FileNotFoundError(path)
            dev = 0x707 if self.mounted and path == admission.approved_write_volumes[0] else 2049
            return SimpleNamespace(st_dev=dev, st_ino=99 if kind=="file" else 70,
                st_rdev=0x707 if kind=="block" else 0, st_uid=0, st_nlink=1,
                st_mode={"file":stat.S_IFREG|0o600,"directory":stat.S_IFDIR|0o700,"block":stat.S_IFBLK|0o600}[kind],
                st_size=self.image_length if kind=="file" else 0)
        def fstat(self, fd): return self.path_stat(self.fds[fd][0], kind=self.fds[fd][1])
        def lock_exclusive(self, fd): self.trace.append("flock")
        def require_empty_directory(self, fd): self.check("empty")
        def create_image(self, path, *, parent_fd):
            assert parent_fd in self.fds
            self.trace.append("create_image"); self.check("create")
            self.image_length = 2 * GIB
            return self.open_existing(path, kind="file", writable=True)
        def configure_loop(self, fd):
            self.trace.append("configure_loop"); self.check("loop")
            path="/dev/loop7"; return path, self.open_existing(path, kind="block", writable=True)
        def format_ext4(self, fd, *, timeout): self.trace.append("format"); self.check("format")
        def mount_ext4(self, loop_fd, target_fd, loop_path):
            assert loop_path=="/dev/loop7"
            self.trace.append("mount"); self.check("mount"); self.mounted=True
        def mountinfo(self):
            text="5 1 8:1 / / rw - ext4 /dev/sda rw\n"
            if self.mounted: text+=f"42 5 7:7 / {admission.approved_write_volumes[0]} rw,nosuid,nodev,noexec - ext4 /dev/loop7 rw\n"
            return text
        def loop_state(self, fd): return LoopState(2049,self.loop_backing,7,0,0,0,2*GIB)
        def filesystem_uuid(self, fd): return UUID
        def filesystem_capacity(self, fd): return 2*GIB-65536
        def fsync(self, fd): self.trace.append("fsync"); self.check("fsync")
        def close(self, fd): self.closed.append(fd)

    ports=FakeOS()
    return SimpleNamespace(module=m, ports=ports, admission=admission,
        creator=m.LinuxInitialVolumeCreator(ports=ports), limits=BudgetLimits(), config=config, seal=seal)


def create(r):
    return r.creator.create_stage_a_volume("synthetic-invocation", r.limits, invocation_started_ns=90)


def test_initial_volume_component_exists():
    assert importlib.util.find_spec(MODULE) is not None


def test_success_is_sampled_after_durable_attempt_before_image(rig):
    volume, sample=create(rig)
    assert rig.ports.trace.index("attempt_durable") < rig.ports.trace.index("sample") < rig.ports.trace.index("create_image")
    assert 90 <= sample.sampled_monotonic_ns < volume.created_monotonic_ns
    assert volume.image_length_bytes==2*GIB and volume.image_inode==99
    assert volume.filesystem_device=="7:7" and volume.filesystem_uuid==UUID
    assert set(rig.ports.closed)==set(rig.ports.fds)


@pytest.mark.parametrize("layer", ["guest_free", "host_free"])
@pytest.mark.parametrize("value", [0,8*GIB-1,True])
def test_either_free_layer_denies_before_image(rig,layer,value):
    setattr(rig.ports,layer,value)
    with pytest.raises((PermissionError,RuntimeError)): create(rig)
    assert rig.ports.marker and "create_image" not in rig.ports.trace


@pytest.mark.parametrize("key,value",[("attempt_cap_bytes",None),("attempt_cap_bytes",True),
    ("attempt_cap_bytes",1),("max_free_sample_age_ns",0),("owner_approval_id","other"),
    ("authorization_card_sha256","c"*64),("study_image_path","/tmp/image"),("guest_device","bad"),
    ("windows_volume_id","C:"),("unexpected",1)])
def test_invalid_or_unapproved_policy_denied_without_marker(rig,key,value):
    rig.ports.policy[key]=value
    with pytest.raises(PermissionError): create(rig)
    assert not rig.ports.marker and "create_image" not in rig.ports.trace


@pytest.mark.parametrize("phase", ["attempt","empty","create","loop","format","mount","fsync"])
def test_any_post_reservation_failure_consumes_attempt(rig,phase):
    rig.ports.fail=phase
    with pytest.raises((OSError,PermissionError)): create(rig)
    rig.ports.fail=None
    with pytest.raises(PermissionError): create(rig)
    restarted=rig.module.LinuxInitialVolumeCreator(ports=rig.ports)
    with pytest.raises(FileExistsError): restarted.create_stage_a_volume("different",rig.limits,invocation_started_ns=90)
    assert set(rig.ports.closed)==set(rig.ports.fds)


def test_forged_approval_denied_before_reservation(rig):
    rig.ports.ab["owner_approved"]=False
    with pytest.raises(PermissionError): create(rig)
    assert not rig.ports.marker


@pytest.mark.parametrize("field,value",[("mount_id","6"),("device","8:2"),("loop_backing",100)])
def test_live_identity_drift_is_refused(rig,field,value):
    setattr(rig.ports,field,value)
    with pytest.raises(PermissionError): create(rig)
    if field=="loop_backing": assert "format" not in rig.ports.trace


def test_old_policy_cannot_follow_a_different_full_ab_seal(rig):
    rig.ports.ab["independent_review_id"]="different-review"
    rig.config["independent_review_id"]="different-review"
    with pytest.raises(PermissionError): create(rig)
    assert not rig.ports.marker


def test_default_component_never_authorizes_or_prepares_on_windows():
    m=importlib.import_module(MODULE)
    if __import__("sys").platform!="win32": pytest.skip("Windows refusal boundary")
    with pytest.raises(PermissionError): m.LinuxInitialVolumeCreator().create_stage_a_volume("s",BudgetLimits(),invocation_started_ns=1)


@pytest.mark.parametrize("failure",["allocation", "initial_sync", "parent_close"])
def test_concrete_initial_image_failure_closes_every_owned_fd_once(syscalls,monkeypatch,failure):
    m=importlib.import_module(MODULE)
    if failure=="initial_sync": syscalls.state.sync_failure=12
    if failure=="parent_close": syscalls.state.close_failures={11}
    def allocate(fd,offset,size):
        assert fd in syscalls.active and offset==0 and size==2*GIB
        if failure=="allocation": raise OSError("synthetic allocation failure")
    monkeypatch.setattr(m.os,"posix_fallocate",allocate,raising=False)
    with pytest.raises(OSError): m.LinuxInitialVolumeOSPorts().create_image("/protected/image.ext4")
    no_leak_or_retry(syscalls)


@pytest.mark.parametrize("short_write",[False,True])
def test_concrete_once_marker_is_synced_before_payload(syscalls,monkeypatch,short_write):
    m=importlib.import_module(MODULE)
    monkeypatch.setattr(m,"INITIAL_ATTEMPT_ROOT","/protected")
    if short_write: monkeypatch.setattr(m.os,"write",lambda fd,data:len(data)-1)
    if short_write:
        with pytest.raises(OSError): m.LinuxInitialVolumeOSPorts().reserve_initial_attempt(b"synthetic\n",cap_bytes=20)
    else:
        m.LinuxInitialVolumeOSPorts().reserve_initial_attempt(b"synthetic\n",cap_bytes=20)
        syncs=[entry for entry in syscalls.trace if entry[0]=="sync"]
        assert syncs==[("sync",12),("sync",11),("sync",12),("sync",11)]
        first_write=next(i for i,t in enumerate(syscalls.trace) if t[0]=="write")
        assert syscalls.trace[first_write-2:first_write]==[("sync",12),("sync",11)]
    no_leak_or_retry(syscalls)


def test_sample_stale_before_creation_consumes_marker_without_creating(rig):
    rig.ports.policy["max_free_sample_age_ns"]=1
    with pytest.raises(PermissionError): create(rig)
    assert rig.ports.marker and "create_image" not in rig.ports.trace


def test_host_sampler_script_exists_and_rejects_wrong_platform():
    import importlib.util
    from pathlib import Path
    file=Path(__file__).resolve().parents[1]/"scripts/route2_host_volume_sample.py"
    assert file.exists()
    spec=importlib.util.spec_from_file_location("route2_synthetic_host_sampler",file)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    with pytest.raises(PermissionError): module.sample_host_volume({"nonce":"x"})


def test_missing_live_claimed_bootstrap_denies_before_once_marker(rig):
    rig.ports.fail="bootstrap"
    with pytest.raises(OSError): create(rig)
    assert not rig.ports.marker and "create_image" not in rig.ports.trace


def test_initial_volume_cannot_use_total_wall_as_extra_stage_a_budget(rig):
    rig.ports.now=90+rig.limits.stage_a_wall_ns+1
    with pytest.raises(PermissionError): create(rig)
    assert not rig.ports.marker


def test_default_live_bootstrap_checker_rejects_preparation_state():
    m=importlib.import_module(MODULE)
    from eating_event.route2_candidate_overlap import admission_bootstrap as b
    assert b._ISSUED_BOOTSTRAP is None
    with pytest.raises(PermissionError): m.LinuxInitialVolumeOSPorts().require_live_bootstrap(frozen(),b"config",b"seal")


def test_missing_host_execution_identity_boundary_denies_before_attempt(rig):
    rig.ports.fail="host_boundary"
    with pytest.raises(OSError): create(rig)
    assert not rig.ports.marker
    with pytest.raises(PermissionError): rig.module.LinuxInitialVolumeOSPorts().require_host_execution_boundary(rig.ports.policy)


@pytest.fixture
def host_sampler(monkeypatch):
    import importlib.util
    from pathlib import Path
    import sys
    file=Path(__file__).resolve().parents[1]/"scripts/route2_host_volume_sample.py"
    spec=importlib.util.spec_from_file_location("route2_synthetic_host_sampler",file)
    module=importlib.util.module_from_spec(spec); spec.loader.exec_module(module)
    request=dict(distro="Ubuntu-22.04",distro_registry_id="{11111111-2222-3333-4444-555555555555}",
        windows_vhdx_path="C:\\synthetic\\ext4.vhdx",
        windows_volume_id="\\\\?\\Volume{11111111-2222-3333-4444-555555555555}\\",nonce="a"*32)
    state=SimpleNamespace(name=request["distro"],base="C:\\synthetic",volume=request["windows_volume_id"],
        reparse=False,ino=99,volume_calls=0)
    class Key:
        def __enter__(self): return self
        def __exit__(self,*args): return False
    def openkey(hive,path):
        assert path.endswith(request["distro_registry_id"])
        return Key()
    registry=SimpleNamespace(HKEY_CURRENT_USER=1,OpenKey=openkey,
        QueryValueEx=lambda key,name:(state.name if name=="DistributionName" else state.base,1))
    class WindowsPath:
        def __init__(self,path): self.path=str(path)
        def __str__(self): return self.path
        def is_absolute(self): return self.path.startswith("C:\\")
        def __truediv__(self,name): return WindowsPath(self.path+"\\"+name)
        def __eq__(self,other): return isinstance(other,WindowsPath) and self.path==other.path
        def stat(self): return SimpleNamespace(st_mode=stat.S_IFREG|0o600,st_nlink=1,st_dev=1,st_ino=state.ino)
    def no_links(path):
        if state.reparse: raise PermissionError("synthetic reparse")
    def volume(path):
        state.volume_calls+=1
        return state.volume,9*GIB,10*GIB
    monkeypatch.setitem(sys.modules,"winreg",registry)
    monkeypatch.setattr(module.sys,"platform","win32")
    monkeypatch.setattr(module,"Path",WindowsPath)
    monkeypatch.setattr(module,"_unlinked_path",no_links)
    monkeypatch.setattr(module,"_volume",volume)
    return SimpleNamespace(module=module,request=request,state=state)


def test_host_sample_binds_exact_registry_vhdx_volume_and_nonce(host_sampler):
    h=host_sampler
    result=h.module.sample_host_volume(h.request)
    assert all(result[k]==v for k,v in h.request.items())
    assert result["available_bytes"]==9*GIB and result["total_free_bytes"]==10*GIB
    assert h.state.volume_calls==1


@pytest.mark.parametrize("field,value",[("name","different"),("base","C:\\other"),
    ("volume","\\\\?\\Volume{aaaaaaaa-2222-3333-4444-555555555555}\\"),("reparse",True)])
def test_host_sample_live_mapping_drift_refused(host_sampler,field,value):
    h=host_sampler; setattr(h.state,field,value)
    with pytest.raises(PermissionError): h.module.sample_host_volume(h.request)


@pytest.mark.parametrize("field,value",[("nonce","old"),("distro_registry_id","other"),
    ("windows_vhdx_path","C:\\synthetic\\..\\ext4.vhdx"),("windows_volume_id","C:"),("extra",1)])
def test_host_bad_requests_denied_before_win32_sample(host_sampler,field,value):
    h=host_sampler; h.request[field]=value
    with pytest.raises(PermissionError): h.module.sample_host_volume(h.request)
    assert h.state.volume_calls==0


@pytest.mark.parametrize("fault",[None,"reparse","nonlocal","open","free"])
def test_concrete_win32_sampler_reads_free_by_held_handle_guid(host_sampler,monkeypatch,fault):
    h=host_sampler; calls=[]
    ctypes=h.module.ctypes
    def create(*args):
        calls.append(("create",args))
        return ctypes.c_void_p(-1).value if fault=="open" else 42
    def info(handle,kind,pointer,size):
        assert handle==42 and kind==9
        ctypes.cast(pointer,ctypes.POINTER(ctypes.c_uint32))[0]=0x400 if fault=="reparse" else 0
        return 1
    def path(handle,buffer,size,flags):
        assert handle==42 and flags==1
        buffer.value=("\\\\server\\share\\ext4.vhdx" if fault=="nonlocal" else h.request["windows_volume_id"]+"synthetic\\ext4.vhdx")
        return len(buffer.value)
    def free(volume,available,total,total_free):
        calls.append(("free",volume))
        assert volume==h.request["windows_volume_id"]
        for target,value in ((available,9*GIB),(total,20*GIB),(total_free,10*GIB)):
            ctypes.cast(target,ctypes.POINTER(ctypes.c_uint64))[0]=value
        return 0 if fault=="free" else 1
    def close(handle): calls.append(("close",handle)); return 1
    kernel=SimpleNamespace(CreateFileW=create,GetFileInformationByHandleEx=info,
        GetFinalPathNameByHandleW=path,GetDiskFreeSpaceExW=free,CloseHandle=close)
    monkeypatch.setattr(ctypes,"WinDLL",lambda *a,**k:kernel,raising=False)
    monkeypatch.setattr(ctypes,"get_last_error",lambda:5,raising=False)
    monkeypatch.setattr(ctypes,"WinError",lambda code:OSError(code,"synthetic Win32 failure"),raising=False)
    # Exercise the concrete method; fixture normally replaces this OS boundary.
    from pathlib import PureWindowsPath
    import importlib.util
    from pathlib import Path
    spec=importlib.util.spec_from_file_location("route2_concrete_win32",Path(__file__).resolve().parents[1]/"scripts/route2_host_volume_sample.py")
    real=importlib.util.module_from_spec(spec); spec.loader.exec_module(real)
    if fault:
        with pytest.raises((PermissionError,OSError)): real._volume(PureWindowsPath(h.request["windows_vhdx_path"]))
    else:
        assert real._volume(PureWindowsPath(h.request["windows_vhdx_path"]))==(h.request["windows_volume_id"],9*GIB,10*GIB)
    assert [entry for entry in calls if entry[0]=="close"]==([] if fault=="open" else [("close",42)])


def test_concrete_guest_sampler_retains_real_integer_mount_evidence_type(rig,monkeypatch):
    m=rig.module
    from eating_event.route2_candidate_overlap import wsl_controller as wsl
    mount=wsl.MountEvidence(5,1,"8:1","/","ext4","/dev/sda",2049,20*GIB,9*GIB,1)
    monkeypatch.setattr(wsl,"mount_evidence",lambda path:mount)
    data={rig.ports.policy["host_python_path"]:b"exe",rig.ports.policy["host_sampler_path"]:b"script"}
    for kind in ("host_python","host_sampler"):
        rig.ports.policy[kind+"_sha256"]=hashlib.sha256(data[rig.ports.policy[kind+"_path"]]).hexdigest()
    monkeypatch.setattr(m,"_host_file_bytes",lambda path,cap:data[path])
    def response(argv):
        request=json.loads(argv[-1])
        return canonical({**request,"available_bytes":9*GIB,"total_free_bytes":10*GIB})+b"\r\n"
    monkeypatch.setattr(m,"_bounded_host_output",response)
    ports=m.LinuxInitialVolumeOSPorts()
    info=SimpleNamespace(st_dev=2049,st_ino=99,st_rdev=0)
    monkeypatch.setattr(ports,"fstat",lambda fd:info)
    monkeypatch.setattr(ports,"path_stat",lambda *args,**kwargs:info)
    monkeypatch.setattr(ports,"monotonic_ns",lambda:100)
    monkeypatch.setattr(m.os,"fstatvfs",lambda fd:SimpleNamespace(f_bavail=9*GIB//4096,f_frsize=4096),raising=False)
    sample=ports.sample_free(rig.ports.policy,"synthetic-invocation",parent_fd=77)
    assert sample.guest_mount_id=="5" and type(sample.guest_mount_id) is str
    assert sample.sampled_monotonic_ns==100 and sample.windows_free_bytes==9*GIB


def test_covering_mount_changed_with_same_device_inode_refused_before_image(rig,monkeypatch):
    original=rig.ports.sample_free
    def changed(*args,**kwargs):
        sample=original(*args,**kwargs)
        rig.ports.mount_id="6"
        return sample
    monkeypatch.setattr(rig.ports,"sample_free",changed)
    with pytest.raises(PermissionError): create(rig)
    assert "create_image" not in rig.ports.trace


@pytest.mark.parametrize("cleanup_fault",["kill","wait"])
def test_bounded_host_pipe_always_closes_stdout_on_cleanup_error(rig,monkeypatch,cleanup_fault):
    import selectors
    m=rig.module; state=SimpleNamespace(closed=False)
    class Pipe:
        def fileno(self): return 77
        def close(self): state.closed=True
    class Process:
        stdout=Pipe()
        def poll(self): return None
        def kill(self):
            if cleanup_fault=="kill": raise OSError("synthetic kill failed")
        def wait(self,**kwargs): raise OSError("synthetic wait failed")
    class Selector:
        def __enter__(self): return self
        def __exit__(self,*args): pass
        def register(self,*args): pass
        def select(self,*args): return [(None,None)]
    monkeypatch.setattr(m.subprocess,"Popen",lambda *args,**kwargs:Process())
    monkeypatch.setattr(selectors,"DefaultSelector",Selector)
    monkeypatch.setattr(m.os,"set_blocking",lambda *args:None,raising=False)
    monkeypatch.setattr(m.os,"read",lambda fd,cap:b" "*4097)
    with pytest.raises(OSError): m._bounded_host_output(("synthetic-host",))
    assert state.closed
