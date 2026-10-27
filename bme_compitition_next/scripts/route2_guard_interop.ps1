# SOURCE ONLY. C00 qualified Windows contract, 2026-10-26, including both repairs.
# Definitions have no native/emit initializer. Load only after the original root q0.
# Native binding, emitted ABI assertions and runtime timing gates belong inside H1.

# R2ApiId and R2LayoutId are emitted with UInt32 backing INSIDE New-R2Interop.
# Windows PowerShell 5.1 enum syntax cannot select an underlying UInt32 type.
# Their fixed names/values are exactly the numbered API rows and layout row order.

function New-R2Interop {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][object]$Plan)
    Assert-R2StaticPlan -Plan $Plan
    # Private module scope prevents the shared dot-source scope from exposing the
    # mutable issuer/registry/backing dictionaries. A second factory cannot reset it.
    if ($null -ne (Get-Module -Name Route2OriginalInteropIssuer)) {throw [InvalidOperationException]::new('R2_INTEROP_FACTORY_ALREADY_ISSUED')}
    $issuerModule=New-Module -Name Route2OriginalInteropIssuer -ScriptBlock {

function Get-R2FixedApiSpecifications {
    # Literal reviewed allowlist. P = pointer/HANDLE, S = UTF-16 input string.
    # A pointer's direction None denotes a handle or opaque native context value.
    # Scalar-output pointers are bounded native buffers, never unregistered addresses.
    $rows = @'
1|QueryPerformanceCounter|kernel32|i32|BOOL|1|P:Out
2|QueryPerformanceFrequency|kernel32|i32|BOOL|1|P:Out
3|GetSystemTimePreciseAsFileTime|kernel32|void|VOID|0|P:Out
4|FileTimeToSystemTime|kernel32|i32|BOOL|1|P:In,P:Out
5|SystemTimeToTzSpecificLocalTime|kernel32|i32|BOOL|1|P:In,P:In,P:Out
6|SystemTimeToFileTime|kernel32|i32|BOOL|1|P:In,P:Out
7|GetTimeZoneInformation|kernel32|u32|DWORD|1|P:Out
8|GlobalMemoryStatusEx|kernel32|i32|BOOL|1|P:InOut
9|GetSystemTimes|kernel32|i32|BOOL|1|P:Out,P:Out,P:Out
10|GetActiveProcessorGroupCount|kernel32|u16|DWORD|1|
11|GetActiveProcessorCount|kernel32|u32|DWORD|1|u16:None
12|CreateJobObjectW|kernel32|ptr|HANDLE_NULL|1|P:In,S:In
13|SetInformationJobObject|kernel32|i32|BOOL|1|P:None,i32:None,P:In,u32:None
14|QueryInformationJobObject|kernel32|i32|BOOL|1|P:None,i32:None,P:Out,u32:None,P:Out
15|AssignProcessToJobObject|kernel32|i32|BOOL|1|P:None,P:None
16|IsProcessInJob|kernel32|i32|BOOL|1|P:None,P:None,P:Out
17|TerminateJobObject|kernel32|i32|BOOL|1|P:None,u32:None
18|InitializeProcThreadAttributeList|kernel32|i32|BOOL|1|P:InOut,u32:None,u32:None,P:InOut
19|UpdateProcThreadAttribute|kernel32|i32|BOOL|1|P:InOut,u32:None,u64:None,P:In,u64:None,P:Out,P:Out
20|DeleteProcThreadAttributeList|kernel32|void|VOID|0|P:InOut
21|CreateProcessW|kernel32|i32|BOOL|1|S:In,P:InOut,P:In,P:In,i32:None,u32:None,P:In,S:In,P:In,P:Out
22|ResumeThread|kernel32|u32|DWORD|1|P:None
23|DuplicateHandle|kernel32|i32|BOOL|1|P:None,P:None,P:None,P:Out,u32:None,i32:None,u32:None
24|GetProcessTimes|kernel32|i32|BOOL|1|P:None,P:Out,P:Out,P:Out,P:Out
25|GetProcessId|kernel32|u32|DWORD|1|P:None
26|GetThreadId|kernel32|u32|DWORD|1|P:None
27|GetProcessIdOfThread|kernel32|u32|DWORD|1|P:None
28|WaitForSingleObject|kernel32|u32|DWORD|1|P:None,u32:None
29|GetExitCodeProcess|kernel32|i32|BOOL|1|P:None,P:Out
30|TerminateProcess|kernel32|i32|BOOL|1|P:None,u32:None
31|CloseHandle|kernel32|i32|BOOL|1|P:None
32|CreateToolhelp32Snapshot|kernel32|ptr|HANDLE_INVALID|1|u32:None,u32:None
33|Thread32First|kernel32|i32|BOOL|1|P:None,P:InOut
34|Thread32Next|kernel32|i32|BOOL|1|P:None,P:InOut
35|K32GetProcessMemoryInfo|kernel32|i32|BOOL|1|P:None,P:InOut,u32:None
36|GetCurrentProcess|kernel32|ptr|BORROWED_PSEUDO|0|
37|GetThreadTimes|kernel32|i32|BOOL|1|P:None,P:Out,P:Out,P:Out,P:Out
38|OpenProcessToken|advapi32|i32|BOOL|1|P:None,u32:None,P:Out
39|GetTokenInformation|advapi32|i32|BOOL|1|P:None,i32:None,P:Out,u32:None,P:Out
40|ConvertSidToStringSidW|advapi32|i32|BOOL|1|P:In,P:Out
41|ConvertStringSecurityDescriptorToSecurityDescriptorW|advapi32|i32|BOOL|1|S:In,u32:None,P:Out,P:Out
42|LocalFree|kernel32|ptr|LOCALFREE|1|P:None
43|CreateNamedPipeW|kernel32|ptr|HANDLE_INVALID|1|S:In,u32:None,u32:None,u32:None,u32:None,u32:None,u32:None,P:In
44|ConnectNamedPipe|kernel32|i32|BOOL|1|P:None,P:InOut
45|GetNamedPipeClientProcessId|kernel32|i32|BOOL|1|P:None,P:Out
46|ReadFile|kernel32|i32|BOOL|1|P:None,P:Out,u32:None,P:Out,P:InOut
47|WriteFile|kernel32|i32|BOOL|1|P:None,P:In,u32:None,P:Out,P:InOut
48|GetOverlappedResult|kernel32|i32|BOOL|1|P:None,P:InOut,P:Out,i32:None
49|CancelIoEx|kernel32|i32|BOOL|1|P:None,P:InOut
50|DisconnectNamedPipe|kernel32|i32|BOOL|1|P:None
51|CreateEventW|kernel32|ptr|HANDLE_NULL|1|P:In,i32:None,i32:None,S:In
52|SetEvent|kernel32|i32|BOOL|1|P:None
53|BCryptGenRandom|bcrypt|i32|NTSTATUS|0|P:None,P:Out,u32:None,u32:None
54|nvmlInit_v2|nvml|i32|NVML|0|
55|nvmlDeviceGetCount_v2|nvml|i32|NVML|0|P:Out
56|nvmlDeviceGetHandleByIndex_v2|nvml|i32|NVML|0|u32:None,P:Out
57|nvmlDeviceGetUUID|nvml|i32|NVML|0|P:None,P:Out,u32:None
58|nvmlDeviceGetMemoryInfo_v2|nvml|i32|NVML|0|P:None,P:InOut
59|nvmlShutdown|nvml|i32|NVML|0|
60|PdhOpenQueryW|pdh|i32|PDH|0|S:In,u64:None,P:Out
61|PdhAddEnglishCounterW|pdh|i32|PDH|0|P:None,S:In,u64:None,P:Out
62|PdhCollectQueryDataWithTime|pdh|i32|PDH|0|P:None,P:Out
63|PdhGetRawCounterArrayW|pdh|i32|PDH|0|P:None,P:InOut,P:Out,P:Out
64|PdhGetCounterInfoW|pdh|i32|PDH|0|P:None,i32:None,P:InOut,P:Out
65|PdhRemoveCounter|pdh|i32|PDH|0|P:None
66|PdhCloseQuery|pdh|i32|PDH|0|P:None
67|CreatePipe|kernel32|i32|BOOL|1|P:Out,P:Out,P:In,u32:None
68|Process32FirstW|kernel32|i32|BOOL|1|P:None,P:InOut
69|Process32NextW|kernel32|i32|BOOL|1|P:None,P:InOut
70|GetNamedPipeServerProcessId|kernel32|i32|BOOL|1|P:None,P:Out
71|CreateFileW|kernel32|ptr|HANDLE_INVALID|1|S:In,u32:None,u32:None,P:In,u32:None,u32:None,P:None
72|GetFileInformationByHandleEx|kernel32|i32|BOOL|1|P:None,i32:None,P:Out,u32:None
73|GetFinalPathNameByHandleW|kernel32|u32|DWORD|1|P:None,P:Out,u32:None,u32:None
74|FlushFileBuffers|kernel32|i32|BOOL|1|P:None
'@
    $nullable = @{
        12=@(0,1); 14=@(4); 18=@(0); 19=@(5,6); 21=@(2,3)
        39=@(2); 43=@(); 46=@(3,4); 47=@(4); 51=@(3); 53=@(0)
        60=@(0); 63=@(3); 64=@(3); 67=@(2); 71=@(3,6)
    }
    $sentinels = @{7=[uint32]::MaxValue;10=[uint32]0;11=[uint32]0;22=[uint32]::MaxValue;25=[uint32]0;26=[uint32]0;27=[uint32]0;28=[uint32]::MaxValue;73=[uint32]0}
    foreach ($row in ($rows -split '\r?\n')) {
        $p=$row.Split('|'); $paramKinds=New-Object 'System.Collections.Generic.List[string]'
        $directions=New-Object 'System.Collections.Generic.List[string]'
        $types=New-Object 'System.Collections.Generic.List[System.Type]'
        if ($p[6].Length -gt 0) {
            foreach ($token in $p[6].Split(',')) {
                $t=$token.Split(':'); $type=Get-R2FixedScalarType $t[0]
                $kind=switch ($t[0]) { 'P' {'Pointer'} 'S' {'String'} 'u32' {'UInt32'} 'i32' {'Int32'} 'u16' {'UInt16'} 'u64' {'UInt64'} default {throw 'R2_INTEROP_FIXED_PARAMETER'} }
                $paramKinds.Add($kind); $directions.Add($t[1]); $types.Add($type)
            }
        }
        $id=[uint32]::Parse($p[0],[Globalization.CultureInfo]::InvariantCulture)
        $nulls=[int[]]@(); if ($nullable.ContainsKey([int]$id)) {$nulls=[int[]]$nullable[[int]$id]}
        $sentinel=$null; if ($sentinels.ContainsKey([int]$id)) {$sentinel=$sentinels[[int]$id]}
        [pscustomobject]@{
            ApiId=$id; Name=$p[1]; DllKey=$p[2]; ReturnType=(Get-R2FixedScalarType $p[3])
            ParameterTypes=$types.ToArray(); ParamKinds=$paramKinds.ToArray(); BufferDirections=$directions.ToArray()
            ReturnConvention=$p[4]; SetLastError=($p[5] -ceq '1'); ErrorSentinel=$sentinel
            NullableParameters=$nulls
            CallingConvention=$(if ($p[2] -ceq 'nvml') {[Runtime.InteropServices.CallingConvention]::Cdecl} else {[Runtime.InteropServices.CallingConvention]::Winapi})
        }
    }
}

function Get-R2FixedScalarType {
    param([Parameter(Mandatory=$true)][string]$Code)
    switch -CaseSensitive ($Code) {
        'void' {return [void]} 'ptr' {return [IntPtr]} 'P' {return [IntPtr]}
        'S' {return [string]} 'i32' {return [int32]} 'u32' {return [uint32]}
        'u16' {return [uint16]} 'u64' {return [uint64]} 'i64' {return [int64]}
        'u8' {return [byte]} default {throw 'R2_INTEROP_UNKNOWN_FIXED_SCALAR'}
    }
}

function Get-R2FixedBufferContract {
    param([Parameter(Mandatory=$true)][uint32]$ApiId)
    # Fixed byte minima for every dereferenced pointer. A nullable sizing pointer
    # is exempt ONLY when NULL; non-NULL buffers must meet the same minima.
    $rows=@'
1|0:8:LARGE_INTEGER
2|0:8:LARGE_INTEGER
3|0:8:FILETIME
4|0:8:FILETIME,1:16:SYSTEMTIME
5|0:172:TIME_ZONE_INFORMATION,1:16:SYSTEMTIME,2:16:SYSTEMTIME
6|0:16:SYSTEMTIME,1:8:FILETIME
7|0:172:TIME_ZONE_INFORMATION
8|0:64:MEMORYSTATUSEX
9|0:8:FILETIME,1:8:FILETIME,2:8:FILETIME
12|0:24:SECURITY_ATTRIBUTES
13|2:8:JOB_CLASS_BUFFER
14|2:8:JOB_CLASS_BUFFER,4:4:DWORD
16|2:4:BOOL
18|0:1:ATTRIBUTE_LIST,3:8:SIZE_T
19|0:1:ATTRIBUTE_LIST,3:8:HANDLE_ARRAY,5:1:PREVIOUS_VALUE,6:8:SIZE_T
20|0:1:ATTRIBUTE_LIST
21|1:2:MUTABLE_UTF16,2:24:SECURITY_ATTRIBUTES,3:24:SECURITY_ATTRIBUTES,6:4:UTF16_ENVIRONMENT,8:112:STARTUPINFOEXW,9:24:PROCESS_INFORMATION
23|3:8:HANDLE
24|1:8:FILETIME,2:8:FILETIME,3:8:FILETIME,4:8:FILETIME
29|1:4:DWORD
33|1:28:THREADENTRY32
34|1:28:THREADENTRY32
35|1:80:PROCESS_MEMORY_COUNTERS_EX
37|1:8:FILETIME,2:8:FILETIME,3:8:FILETIME,4:8:FILETIME
38|2:8:HANDLE
39|2:16:TOKEN_USER,4:4:DWORD
40|0:8:SID_HEADER,1:8:LOCAL_ALLOCATION_POINTER
41|2:8:LOCAL_ALLOCATION_POINTER,3:4:DWORD
43|7:24:SECURITY_ATTRIBUTES
44|1:32:OVERLAPPED
45|1:4:DWORD
46|1:1:BYTES,3:4:DWORD,4:32:OVERLAPPED
47|1:1:BYTES,3:4:DWORD,4:32:OVERLAPPED
48|1:32:OVERLAPPED,2:4:DWORD
49|1:32:OVERLAPPED
51|0:24:SECURITY_ATTRIBUTES
53|1:32:NONCE32
55|0:4:DWORD
56|1:8:NVML_DEVICE_POINTER
57|1:96:NVML_UUID96
58|1:40:nvmlMemory_v2_t
60|2:8:PDH_QUERY_POINTER
61|3:8:PDH_COUNTER_POINTER
62|1:8:LARGE_INTEGER
63|1:4:DWORD,2:4:DWORD,3:48:PDH_RAW_COUNTER_ITEM_W
64|2:4:DWORD,3:8:PDH_COUNTER_INFO_W_PREFIX
67|0:8:HANDLE,1:8:HANDLE,2:24:SECURITY_ATTRIBUTES
68|1:568:PROCESSENTRY32W
69|1:568:PROCESSENTRY32W
70|1:4:DWORD
71|3:24:SECURITY_ATTRIBUTES
72|2:8:FILE_INFO_CLASS_BUFFER
73|1:2:MUTABLE_UTF16
'@
    $sizes=@{}; $layouts=@{}; $dynamic=@{}; $classLayouts=@{}
    foreach ($row in ($rows -split '\r?\n')) {
        $pair=$row.Split('|'); if ([uint32]$pair[0] -ne $ApiId) {continue}
        foreach ($entry in $pair[1].Split(',')) {$p=$entry.Split(':');$sizes[$p[0]]=[uint32]$p[1];$layouts[$p[0]]=$p[2]}
    }
    # Capacity is checked BEFORE invoking against the original numeric count;
    # multiplication is checked and counts never authorize a new allocation.
    $dynamicRows=@{13='2:3:1';14='2:3:1';19='3:4:1';35='1:2:1';39='2:3:1';46='1:2:1';47='1:2:1';53='1:2:1';57='1:2:1';72='2:3:1';73='1:2:2'}
    if ($dynamicRows.ContainsKey([int]$ApiId)) {
        $parts=$dynamicRows[[int]$ApiId].Split(':')
        $dynamic[$parts[0]]=New-R2InteropReadOnlyMap @{LengthParameter=[int]$parts[1];UnitBytes=[uint32]$parts[2]}
    }
    # The only admitted class-dependent fixed layouts; no arbitrary native class.
    if ($ApiId -eq 13) {$classLayouts=@{'9'='JOBOBJECT_EXTENDED_LIMIT_INFORMATION';'15'='JOBOBJECT_CPU_RATE_CONTROL_INFORMATION'}}
    if ($ApiId -eq 14) {$classLayouts=@{'1'='JOBOBJECT_BASIC_ACCOUNTING_INFORMATION';'3'='JOBOBJECT_BASIC_PROCESS_ID_LIST';'9'='JOBOBJECT_EXTENDED_LIMIT_INFORMATION';'15'='JOBOBJECT_CPU_RATE_CONTROL_INFORMATION'}}
    if ($ApiId -eq 72) {$classLayouts=@{'1'='FILE_STANDARD_INFO';'9'='FILE_ATTRIBUTE_TAG_INFO';'18'='FILE_ID_INFO'}}
    return ,(New-R2InteropReadOnlyMap @{
        MinimumSizes=(New-R2InteropReadOnlyMap $sizes);BufferLayouts=(New-R2InteropReadOnlyMap $layouts)
        DynamicBufferLengths=(New-R2InteropReadOnlyMap $dynamic);InformationClassLayouts=(New-R2InteropReadOnlyMap $classLayouts)
        InformationClassParameter=$(if ($classLayouts.Count -gt 0) {[int]1} else {$null})
        InformationClassBufferParameter=$(if ($classLayouts.Count -gt 0) {[int]2} else {$null})
        # PDH_COUNTER_INFO_W's inspected fixed prefix is dwLength:DWORD@0,
        # dwType:DWORD@4; the remaining returned bytes are opaque bounded storage.
        PdhCounterInfoPrefix=$(if ($ApiId -eq 64) {New-R2InteropReadOnlyMap @{Size=[uint32]8;dwLength=[uint32]0;dwType=[uint32]4}} else {$null})
    })
}

function Get-R2FixedLayoutSpecifications {
    # Each entry: fixed enum ID | size | alignment | field:type:offset.
    # Bounded inline arrays are represented by their fixed bytes in explicit types.
    $rows=@'
FILETIME|8|4|dwLowDateTime:u32:0,dwHighDateTime:u32:4
LARGE_INTEGER|8|8|QuadPart:i64:0
MEMORYSTATUSEX|64|8|dwLength:u32:0,dwMemoryLoad:u32:4,ullTotalPhys:u64:8,ullAvailPhys:u64:16,ullTotalPageFile:u64:24,ullAvailPageFile:u64:32,ullTotalVirtual:u64:40,ullAvailVirtual:u64:48,ullAvailExtendedVirtual:u64:56
PROCESS_INFORMATION|24|8|hProcess:ptr:0,hThread:ptr:8,dwProcessId:u32:16,dwThreadId:u32:20
STARTUPINFOEXW|112|8|cb:u32:0,lpReserved:ptr:8,lpDesktop:ptr:16,lpTitle:ptr:24,dwX:u32:32,dwY:u32:36,dwXSize:u32:40,dwYSize:u32:44,dwXCountChars:u32:48,dwYCountChars:u32:52,dwFillAttribute:u32:56,dwFlags:u32:60,wShowWindow:u16:64,cbReserved2:u16:66,lpReserved2:ptr:72,hStdInput:ptr:80,hStdOutput:ptr:88,hStdError:ptr:96,lpAttributeList:ptr:104
SECURITY_ATTRIBUTES|24|8|nLength:u32:0,lpSecurityDescriptor:ptr:8,bInheritHandle:i32:16
JOBOBJECT_BASIC_LIMIT_INFORMATION|64|8|PerProcessUserTimeLimit:i64:0,PerJobUserTimeLimit:i64:8,LimitFlags:u32:16,MinimumWorkingSetSize:u64:24,MaximumWorkingSetSize:u64:32,ActiveProcessLimit:u32:40,Affinity:u64:48,PriorityClass:u32:56,SchedulingClass:u32:60
IO_COUNTERS|48|8|ReadOperationCount:u64:0,WriteOperationCount:u64:8,OtherOperationCount:u64:16,ReadTransferCount:u64:24,WriteTransferCount:u64:32,OtherTransferCount:u64:40
JOBOBJECT_EXTENDED_LIMIT_INFORMATION|144|8|PerProcessUserTimeLimit:i64:0,PerJobUserTimeLimit:i64:8,LimitFlags:u32:16,MinimumWorkingSetSize:u64:24,MaximumWorkingSetSize:u64:32,ActiveProcessLimit:u32:40,Affinity:u64:48,PriorityClass:u32:56,SchedulingClass:u32:60,ReadOperationCount:u64:64,WriteOperationCount:u64:72,OtherOperationCount:u64:80,ReadTransferCount:u64:88,WriteTransferCount:u64:96,OtherTransferCount:u64:104,ProcessMemoryLimit:u64:112,JobMemoryLimit:u64:120,PeakProcessMemoryUsed:u64:128,PeakJobMemoryUsed:u64:136
JOBOBJECT_CPU_RATE_CONTROL_INFORMATION|8|4|ControlFlags:u32:0,CpuRate:u32:4
PDH_RAW_COUNTER|40|8|CStatus:u32:0,TimeStampLow:u32:4,TimeStampHigh:u32:8,FirstValue:i64:16,SecondValue:i64:24,MultiCount:u32:32
PDH_RAW_COUNTER_ITEM_W|48|8|szName:ptr:0,CStatus:u32:8,TimeStampLow:u32:12,TimeStampHigh:u32:16,FirstValue:i64:24,SecondValue:i64:32,MultiCount:u32:40
nvmlMemory_v2_t|40|8|version:u32:0,total:u64:8,reserved:u64:16,free:u64:24,used:u64:32
SYSTEMTIME|16|2|wYear:u16:0,wMonth:u16:2,wDayOfWeek:u16:4,wDay:u16:6,wHour:u16:8,wMinute:u16:10,wSecond:u16:12,wMilliseconds:u16:14
TIME_ZONE_INFORMATION|172|4|Bias:i32:0,StandardName:bytes64:4,StandardDate:bytes16:68,StandardBias:i32:84,DaylightName:bytes64:88,DaylightDate:bytes16:152,DaylightBias:i32:168
THREADENTRY32|28|4|dwSize:u32:0,cntUsage:u32:4,th32ThreadID:u32:8,th32OwnerProcessID:u32:12,tpBasePri:i32:16,tpDeltaPri:i32:20,dwFlags:u32:24
PROCESS_MEMORY_COUNTERS_EX|80|8|cb:u32:0,PageFaultCount:u32:4,PeakWorkingSetSize:u64:8,WorkingSetSize:u64:16,QuotaPeakPagedPoolUsage:u64:24,QuotaPagedPoolUsage:u64:32,QuotaPeakNonPagedPoolUsage:u64:40,QuotaNonPagedPoolUsage:u64:48,PagefileUsage:u64:56,PeakPagefileUsage:u64:64,PrivateUsage:u64:72
TOKEN_USER|16|8|Sid:ptr:0,Attributes:u32:8
SID_AND_ATTRIBUTES|16|8|Sid:ptr:0,Attributes:u32:8
SECURITY_DESCRIPTOR_RELATIVE|20|4|Revision:u8:0,Sbz1:u8:1,Control:u16:2,Owner:u32:4,Group:u32:8,Sacl:u32:12,Dacl:u32:16
ACL|8|2|AclRevision:u8:0,Sbz1:u8:1,AclSize:u16:2,AceCount:u16:4,Sbz2:u16:6
ACCESS_ALLOWED_ACE_HEADER|8|4|AceType:u8:0,AceFlags:u8:1,AceSize:u16:2,Mask:u32:4
JOBOBJECT_BASIC_ACCOUNTING_INFORMATION|48|8|TotalUserTime:i64:0,TotalKernelTime:i64:8,ThisPeriodTotalUserTime:i64:16,ThisPeriodTotalKernelTime:i64:24,TotalPageFaultCount:u32:32,TotalProcesses:u32:36,ActiveProcesses:u32:40,TotalTerminatedProcesses:u32:44
JOBOBJECT_BASIC_PROCESS_ID_LIST|40|8|NumberOfAssignedProcesses:u32:0,NumberOfProcessIdsInList:u32:4,ProcessId0:u64:8,ProcessId1:u64:16,ProcessId2:u64:24,ProcessId3:u64:32
OVERLAPPED|32|8|Internal:u64:0,InternalHigh:u64:8,Offset:u32:16,OffsetHigh:u32:20,Pointer:ptr:16,hEvent:ptr:24
PROCESSENTRY32W|568|8|dwSize:u32:0,cntUsage:u32:4,th32ProcessID:u32:8,th32DefaultHeapID:u64:16,th32ModuleID:u32:24,cntThreads:u32:28,th32ParentProcessID:u32:32,pcPriClassBase:i32:36,dwFlags:u32:40,szExeFile:bytes520:44
FILE_ID_INFO|24|8|VolumeSerialNumber:u64:0,FileId:bytes16:8
FILE_STANDARD_INFO|24|8|AllocationSize:i64:0,EndOfFile:i64:8,NumberOfLinks:u32:16,DeletePending:u8:20,Directory:u8:21
FILE_ATTRIBUTE_TAG_INFO|8|4|FileAttributes:u32:0,ReparseTag:u32:4
SID_HEADER|8|4|Revision:u8:0,SubAuthorityCount:u8:1,IdentifierAuthority:bytes6:2
'@
    $layoutId=[uint32]0
    foreach ($row in ($rows -split '\r?\n')) {
        $layoutId++
        $parts=$row.Split('|'); $fields=New-Object 'System.Collections.Generic.List[object]'
        foreach ($entry in $parts[3].Split(',')) {
            $f=$entry.Split(':'); $width=0; $type=$null
            if ($f[1] -cmatch '^bytes([0-9]+)$') {$width=[int]$Matches[1]; $type=[byte]}
            else {$type=Get-R2FixedScalarType $f[1]; $width=switch ($f[1]) {'u8' {1} 'u16' {2} 'i32' {4} 'u32' {4} default {8}}}
            $fields.Add([pscustomobject]@{Name=$f[0];Type=$type;Offset=[uint32]$f[2];Width=[uint32]$width;InlineBytes=($f[1] -clike 'bytes*')})
        }
        [pscustomobject]@{Id=$layoutId;Name=$parts[0];Size=[uint32]$parts[1];Alignment=[uint32]$parts[2];Fields=$fields.ToArray()}
    }
}

function New-R2InteropReadOnlyMap {
    param([Parameter(Mandatory=$true)][System.Collections.IDictionary]$Values)
    # Copy before wrapping; callers never retain this mutable backing dictionary.
    $copy=New-Object 'System.Collections.Generic.Dictionary[string,object]' ([StringComparer]::Ordinal)
    foreach ($key in $Values.Keys) {$copy.Add([string]$key,$Values[$key])}
    return ,(New-Object 'System.Collections.ObjectModel.ReadOnlyDictionary[string,object]' (,$copy))
}

function New-R2InteropReadOnlyList {
    param([AllowEmptyCollection()][object[]]$Values)
    $copy=New-Object 'System.Collections.Generic.List[object]'
    foreach ($item in $Values) {$copy.Add($item)}
    return ,$copy.AsReadOnly()
}

function New-R2InteropReadOnlyEnumMap {
    param([Parameter(Mandatory=$true)][System.Collections.IDictionary]$Values,[Parameter(Mandatory=$true)][type]$EnumType)
    if (-not $EnumType.IsEnum -or [Enum]::GetUnderlyingType($EnumType) -ne [uint32]) {throw 'R2_INTEROP_ENUM_MAP_TYPE'}
    $copy=New-Object 'System.Collections.Generic.Dictionary[object,object]'
    foreach ($key in $Values.Keys) {
        if ($key.GetType() -ne $EnumType -or -not [Enum]::IsDefined($EnumType,$key)) {throw 'R2_INTEROP_ENUM_MAP_KEY'}
        $copy.Add($key,$Values[$key])
    }
    return ,(New-Object 'System.Collections.ObjectModel.ReadOnlyDictionary[object,object]' (,$copy))
}

function Get-R2InteropPinnedLibraries {
    param([Parameter(Mandatory=$true)][object]$Plan)
    # Assert-R2StaticPlan owns full source/runtime/recursive closure validation.
    # This component additionally rejects search paths, substituted filenames and
    # incomplete pin records. It performs no pre-H1 disk probe or hash assertion.
    Assert-R2StaticPlan -Plan $Plan
    $system32=$Plan.WindowsSystem32Literal
    if ($system32 -isnot [string] -or $system32 -cnotmatch '^[A-Za-z]:\\Windows\\System32$') {throw 'R2_INTEROP_SYSTEM32_PIN_MISSING'}
    if ($null -eq $Plan.RuntimePins -or $Plan.RuntimePins -is [System.Collections.IDictionary]) {throw 'R2_INTEROP_RUNTIME_PINS_MISSING'}
    $paths=@{}
    foreach ($key in @('kernel32','advapi32','pdh','bcrypt','nvml')) {
        $matches=@($Plan.RuntimePins | Where-Object {$_.Id -ceq $key})
        if ($matches.Count -ne 1) {throw 'R2_INTEROP_DLL_PIN_MISSING_OR_DUPLICATE'}
        $pin=$matches[0]; $expected=$system32+'\'+$key+'.dll'
        if ($pin.AbsolutePath -isnot [string] -or -not [string]::Equals($pin.AbsolutePath,$expected,[StringComparison]::OrdinalIgnoreCase)) {throw 'R2_INTEROP_DLL_PIN_PATH'}
        if ($pin.Sha256 -isnot [string] -or $pin.Sha256 -cnotmatch '^[a-f0-9]{64}$' -or $pin.Sha256 -ceq ('0'*64)) {throw 'R2_INTEROP_DLL_PIN_HASH'}
        if ($null -eq $pin.DependencyClosure -or $pin.DependencyClosure.Count -lt 1) {throw 'R2_INTEROP_DLL_CLOSURE_MISSING'}
        $paths[$key]=$pin.AbsolutePath
    }
    return ,(New-R2InteropReadOnlyMap $paths)
}

function New-R2InteropState {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][object]$Plan)
    Assert-R2StaticPlan -Plan $Plan
    if ([IntPtr]::Size -ne 8 -or [Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {throw 'R2_INTEROP_NATIVE_X64_REQUIRED'}
    if ($PSVersionTable.PSEdition -cne 'Desktop' -or $PSVersionTable.PSVersion.Major -ne 5) {throw 'R2_INTEROP_PINNED_FRAMEWORK_REQUIRED'}
    $pins=Get-R2InteropPinnedLibraries -Plan $Plan
    # Lazy private issuance state. No reset after construction or binding failure.
    if (-not (Get-Variable -Scope Script -Name R2InteropPrivateRegistry -ErrorAction SilentlyContinue)) {
        $script:R2InteropPrivateRegistry=New-Object 'System.Collections.Generic.List[object]'
        $script:R2InteropPrivateSerial=[uint64]0
        $script:R2InteropPrivateIssuer=New-Object object
    }
    if ($script:R2InteropPrivateSerial -eq [uint64]::MaxValue -or $script:R2InteropPrivateRegistry.Count -ge 1) {throw 'R2_INTEROP_CONSTRUCTION_ALREADY_ISSUED'}
    $script:R2InteropPrivateSerial++
    $serial=$script:R2InteropPrivateSerial
    $state=[pscustomobject]@{View=$null;Issuer=$script:R2InteropPrivateIssuer;Serial=$serial;Plan=$Plan;NativeType=$null;ApiEnum=$null;LayoutEnum=$null;Layouts=$null;ApiTable=$null;Descriptors=$null;Pins=$pins;BoundContext=$null;BootstrapQuarantine=$null;BindingAttempted=$false;LayoutVerified=$false;Ready=$false;Faulted=$false;IntegrityStopRequested=$false;Backing=$null}
    $script:R2InteropPrivateRegistry.Add($state)
    try {
        # A pre-existing name cannot become the issuer's fixed enum by name alone.
        if ($null -ne ([System.Management.Automation.PSTypeName]'R2ApiId').Type -or $null -ne ([System.Management.Automation.PSTypeName]'R2LayoutId').Type) {throw 'R2_INTEROP_ENUM_NAME_ALREADY_LOADED'}
        $assemblyName=New-Object Reflection.AssemblyName ('Route2.FixedInterop.'+$serial)
        $assembly=[AppDomain]::CurrentDomain.DefineDynamicAssembly($assemblyName,[Reflection.Emit.AssemblyBuilderAccess]::Run)
        $module=$assembly.DefineDynamicModule('Route2FixedNative')
        $apiSpecs=@(Get-R2FixedApiSpecifications); $layoutSpecs=@(Get-R2FixedLayoutSpecifications)
        $apiEnumBuilder=$module.DefineEnum('R2ApiId',[Reflection.TypeAttributes]::Public,[uint32])
        foreach ($spec in $apiSpecs) {$null=$apiEnumBuilder.DefineLiteral($spec.Name,[uint32]$spec.ApiId)}
        $state.ApiEnum=$apiEnumBuilder.CreateType()
        $layoutEnumBuilder=$module.DefineEnum('R2LayoutId',[Reflection.TypeAttributes]::Public,[uint32])
        foreach ($spec in $layoutSpecs) {$null=$layoutEnumBuilder.DefineLiteral($spec.Name,[uint32]$spec.Id)}
        $state.LayoutEnum=$layoutEnumBuilder.CreateType()
        $layoutMap=@{}
        foreach ($spec in $layoutSpecs) {
            $attributes=[Reflection.TypeAttributes]::Public -bor [Reflection.TypeAttributes]::Sealed -bor [Reflection.TypeAttributes]::ExplicitLayout -bor [Reflection.TypeAttributes]::AnsiClass -bor [Reflection.TypeAttributes]::BeforeFieldInit
            $builder=$module.DefineType(('Route2.Native.'+$spec.Name),$attributes,[ValueType],[Reflection.Emit.PackingSize]::Size8,[int]$spec.Size)
            $fieldMap=@{}
            foreach ($field in $spec.Fields) {
                if ([uint64]$field.Offset+[uint64]$field.Width -gt [uint64]$spec.Size) {throw 'R2_INTEROP_FIXED_FIELD_BOUND'}
                if ($field.InlineBytes) {
                    for ($i=0; $i -lt $field.Width; $i++) {
                        $fb=$builder.DefineField(($field.Name+'_'+$i),[byte],[Reflection.FieldAttributes]::Public)
                        $fb.SetOffset([int]$field.Offset+$i)
                    }
                } else {
                    $fb=$builder.DefineField($field.Name,$field.Type,[Reflection.FieldAttributes]::Public)
                    $fb.SetOffset([int]$field.Offset)
                }
                $fieldMap[$field.Name]=New-R2InteropReadOnlyMap @{Type=$field.Type;Offset=$field.Offset;Width=$field.Width;InlineBytes=$field.InlineBytes}
            }
            $layoutType=$builder.CreateType()
            $layoutKey=[Enum]::ToObject($state.LayoutEnum,$spec.Id)
            $layoutMap[$layoutKey]=New-R2InteropReadOnlyMap @{Id=$layoutKey;Name=$spec.Name;Size=$spec.Size;Alignment=$spec.Alignment;Fields=(New-R2InteropReadOnlyMap $fieldMap);NativeType=$layoutType}
        }
        $nativeBuilder=$module.DefineType('Route2.Native.FixedApi',[Reflection.TypeAttributes]::Public -bor [Reflection.TypeAttributes]::Sealed -bor [Reflection.TypeAttributes]::Abstract)
        $ctor=[Runtime.InteropServices.DllImportAttribute].GetConstructor([type[]]@([string]))
        $attributeFields=[Reflection.FieldInfo[]]@(
            [Runtime.InteropServices.DllImportAttribute].GetField('EntryPoint'),
            [Runtime.InteropServices.DllImportAttribute].GetField('ExactSpelling'),
            [Runtime.InteropServices.DllImportAttribute].GetField('SetLastError'),
            [Runtime.InteropServices.DllImportAttribute].GetField('CallingConvention'),
            [Runtime.InteropServices.DllImportAttribute].GetField('CharSet'),
            [Runtime.InteropServices.DllImportAttribute].GetField('PreserveSig'))
        $specs=$apiSpecs
        if ($specs.Count -ne 74 -or $layoutMap.Count -ne 30) {throw 'R2_INTEROP_FIXED_TABLE_CARDINALITY'}
        foreach ($spec in $specs) {
            $dll=[string]$pins[$spec.DllKey]
            $method=$nativeBuilder.DefinePInvokeMethod($spec.Name,$dll,$spec.Name,([Reflection.MethodAttributes]::Public -bor [Reflection.MethodAttributes]::Static -bor [Reflection.MethodAttributes]::PinvokeImpl),[Reflection.CallingConventions]::Standard,$spec.ReturnType,[type[]]$spec.ParameterTypes,$spec.CallingConvention,[Runtime.InteropServices.CharSet]::Unicode)
            $attributeValues=[object[]]@($spec.Name,$true,$spec.SetLastError,$spec.CallingConvention,[Runtime.InteropServices.CharSet]::Unicode,$true)
            $attribute=New-Object Reflection.Emit.CustomAttributeBuilder -ArgumentList @($ctor,[object[]]@($dll),$attributeFields,$attributeValues)
            $method.SetCustomAttribute($attribute)
            $method.SetImplementationFlags([Reflection.MethodImplAttributes]::PreserveSig)
            for ($i=0; $i -lt $spec.ParameterTypes.Count; $i++) {
                $pa=[Reflection.ParameterAttributes]::None
                if ($spec.BufferDirections[$i] -cin @('In','InOut')) {$pa=$pa -bor [Reflection.ParameterAttributes]::In}
                if ($spec.BufferDirections[$i] -cin @('Out','InOut')) {$pa=$pa -bor [Reflection.ParameterAttributes]::Out}
                $null=$method.DefineParameter($i+1,$pa,('p'+$i))
            }
        }
        $nativeType=$nativeBuilder.CreateType(); $apiMap=@{}; $descriptorMap=@{}
        foreach ($spec in $specs) {
            $method=$nativeType.GetMethod($spec.Name,[Reflection.BindingFlags]'Public,Static')
            $bufferContract=Get-R2FixedBufferContract -ApiId $spec.ApiId
            $apiKey=[Enum]::ToObject($state.ApiEnum,$spec.ApiId)
            $apiMap[$apiKey]=$method
            $descriptorMap[$apiKey]=New-R2InteropReadOnlyMap @{
                ApiId=$apiKey;Name=$spec.Name;DllKey=$spec.DllKey;AbsoluteDll=$pins[$spec.DllKey]
                ReturnType=$spec.ReturnType;ParameterTypes=(New-R2InteropReadOnlyList $spec.ParameterTypes)
                ParamKinds=(New-R2InteropReadOnlyList $spec.ParamKinds);BufferDirections=(New-R2InteropReadOnlyList $spec.BufferDirections)
                ReturnConvention=$spec.ReturnConvention;SetLastError=$spec.SetLastError;CallingConvention=$spec.CallingConvention
                NullableParameters=(New-R2InteropReadOnlyList $spec.NullableParameters);ErrorSentinel=$spec.ErrorSentinel
                OutputSizes=$bufferContract.MinimumSizes;BufferMinimumSizes=$bufferContract.MinimumSizes
                BufferLayouts=$bufferContract.BufferLayouts;DynamicBufferLengths=$bufferContract.DynamicBufferLengths
                InformationClassLayouts=$bufferContract.InformationClassLayouts;InformationClassParameter=$bufferContract.InformationClassParameter
                InformationClassBufferParameter=$bufferContract.InformationClassBufferParameter;PdhCounterInfoPrefix=$bufferContract.PdhCounterInfoPrefix
            }
        }
        $state.NativeType=$nativeType; $state.Layouts=New-R2InteropReadOnlyEnumMap $layoutMap $state.LayoutEnum
        $state.ApiTable=New-R2InteropReadOnlyEnumMap $apiMap $state.ApiEnum; $state.Descriptors=New-R2InteropReadOnlyEnumMap $descriptorMap $state.ApiEnum
        $backing=New-Object 'System.Collections.Generic.Dictionary[string,object]' ([StringComparer]::Ordinal)
        $backing.Add('NativeType',$nativeType); $backing.Add('Layouts',$state.Layouts); $backing.Add('ApiTable',$state.ApiTable)
        $backing.Add('PlanReference',$Plan); $backing.Add('IssuerSerial',$serial); $backing.Add('BoundContextReference',$null)
        $view=New-Object 'System.Collections.ObjectModel.ReadOnlyDictionary[string,object]' (,$backing)
        $state.Backing=$backing; $state.View=$view; $state.Ready=$true
        Assert-R2InteropConstruction -Interop $view
        return ,$view
    } catch {
        $state.Faulted=$true
        throw [InvalidOperationException]::new('R2_INTEROP_CONSTRUCTION_FAILED',$_.Exception)
    }
}

function Assert-R2InteropConstruction {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][object]$Interop)
    try {Assert-R2InteropConstructionCore -Interop $Interop}
    catch {
        Set-R2InteropIntegrityFailure -Interop $Interop -Context $null
        throw [InvalidOperationException]::new('R2_INTEROP_INTEGRITY_FAILED',$_.Exception)
    }
}

function Set-R2InteropIntegrityFailure {
    param([AllowNull()][object]$Interop,[AllowNull()][object]$Context)
    if (-not (Get-Variable -Scope Script -Name R2InteropPrivateRegistry -ErrorAction SilentlyContinue)) {return}
    # A rejected lookalike may fail before its Interop is read. Only the sole
    # original private issuer's already-bound state supplies fallback authority;
    # no property/getter on either rejected caller object is inspected here.
    $originalBoundState=$null
    if ($script:R2InteropPrivateRegistry.Count -eq 1) {
        $original=$script:R2InteropPrivateRegistry[0]
        if ([object]::ReferenceEquals($original.Issuer,$script:R2InteropPrivateIssuer) -and $null -ne $original.BoundContext) {$originalBoundState=$original}
    }
    foreach ($state in $script:R2InteropPrivateRegistry) {
        $knownView=($null -ne $Interop -and [object]::ReferenceEquals($state.View,$Interop))
        $knownContext=($null -ne $Context -and [object]::ReferenceEquals($state.BoundContext,$Context))
        if (-not $knownView -and -not $knownContext -and -not [object]::ReferenceEquals($state,$originalBoundState)) {continue}
        $state.Faulted=$true; $state.LayoutVerified=$false
        if ($null -ne $state.BoundContext -and -not $state.IntegrityStopRequested) {
            $state.IntegrityStopRequested=$true
            # Pure managed first-fault latch. UNKNOWN native status stays null;
            # this path neither obtains a native method nor attempts cleanup.
            Stop-R2Guard -Context $state.BoundContext -Domain 'External' -Code 'R2_INTEROP_INTEGRITY_FAILED' -NativeStatus $null -Serial $state.Serial
        }
        return
    }
}

function Assert-R2InteropConstructionCore {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][object]$Interop)
    $state=$null
    if (-not (Get-Variable -Scope Script -Name R2InteropPrivateRegistry -ErrorAction SilentlyContinue)) {throw 'R2_INTEROP_UNISSUED'}
    foreach ($candidate in $script:R2InteropPrivateRegistry) {if ([object]::ReferenceEquals($candidate.View,$Interop)) {$state=$candidate; break}}
    if ($null -eq $state -or -not $state.Ready -or $state.Faulted -or -not [object]::ReferenceEquals($state.Issuer,$script:R2InteropPrivateIssuer)) {throw 'R2_INTEROP_ISSUER_IDENTITY'}
    if (-not [object]::ReferenceEquals($Interop.NativeType,$state.NativeType) -or -not [object]::ReferenceEquals($Interop.Layouts,$state.Layouts) -or -not [object]::ReferenceEquals($Interop.ApiTable,$state.ApiTable) -or -not [object]::ReferenceEquals($Interop.PlanReference,$state.Plan) -or $Interop.IssuerSerial -ne $state.Serial -or -not [object]::ReferenceEquals($Interop.BoundContextReference,$state.BoundContext)) {throw 'R2_INTEROP_VIEW_TAMPER'}
    Assert-R2StaticPlan -Plan $state.Plan
    $fixed=@(Get-R2FixedApiSpecifications)
    if ([Enum]::GetUnderlyingType($state.ApiEnum) -ne [uint32] -or [Enum]::GetNames($state.ApiEnum).Count -ne 74 -or [Enum]::GetUnderlyingType($state.LayoutEnum) -ne [uint32] -or [Enum]::GetNames($state.LayoutEnum).Count -ne 30) {throw 'R2_INTEROP_ENUM_TAMPER'}
    if ($state.ApiTable.Count -ne 74 -or $state.Descriptors.Count -ne 74 -or $state.NativeType.GetMethods([Reflection.BindingFlags]'Public,Static,DeclaredOnly').Count -ne 74) {throw 'R2_INTEROP_API_TABLE_TAMPER'}
    foreach ($spec in $fixed) {
        if ([Enum]::GetName($state.ApiEnum,$spec.ApiId) -cne $spec.Name) {throw 'R2_INTEROP_API_ENUM_TAMPER'}
        $key=[Enum]::ToObject($state.ApiEnum,$spec.ApiId); $method=$state.ApiTable[$key]; $descriptor=$state.Descriptors[$key]
        if ($null -eq $method -or $method.Name -cne $spec.Name -or -not [object]::ReferenceEquals($method.DeclaringType,$state.NativeType) -or -not [object]::ReferenceEquals($method.ReturnType,$spec.ReturnType) -or -not $method.IsStatic -or -not $method.IsPublic) {throw 'R2_INTEROP_METHOD_IDENTITY'}
        if (($method.Attributes -band [Reflection.MethodAttributes]::PinvokeImpl) -eq 0 -or ($method.GetMethodImplementationFlags() -band [Reflection.MethodImplAttributes]::PreserveSig) -eq 0) {throw 'R2_INTEROP_METHOD_FLAGS'}
        $parameters=$method.GetParameters()
        if ($parameters.Count -ne $spec.ParameterTypes.Count) {throw 'R2_INTEROP_PARAMETER_COUNT'}
        for ($i=0; $i -lt $parameters.Count; $i++) {
            if (-not [object]::ReferenceEquals($parameters[$i].ParameterType,$spec.ParameterTypes[$i])) {throw 'R2_INTEROP_PARAMETER_TYPE'}
            if ($descriptor.ParamKinds[$i] -cne $spec.ParamKinds[$i] -or $descriptor.BufferDirections[$i] -cne $spec.BufferDirections[$i] -or $descriptor.ParameterTypes[$i] -ne $spec.ParameterTypes[$i]) {throw 'R2_INTEROP_PARAMETER_DESCRIPTOR'}
        }
        $attrs=$method.GetCustomAttributes([Runtime.InteropServices.DllImportAttribute],$false)
        if ($attrs.Count -ne 1) {throw 'R2_INTEROP_DLL_ATTRIBUTE'}
        $a=$attrs[0]
        if ($a.Value -cne $state.Pins[$spec.DllKey] -or $a.EntryPoint -cne $spec.Name -or -not $a.ExactSpelling -or $a.SetLastError -ne $spec.SetLastError -or -not $a.PreserveSig -or $a.CallingConvention -ne $spec.CallingConvention -or $a.CharSet -ne [Runtime.InteropServices.CharSet]::Unicode) {throw 'R2_INTEROP_DLL_METADATA_TAMPER'}
        if ($descriptor.ApiId.GetType() -ne $state.ApiEnum -or $descriptor.ApiId -ne $spec.ApiId -or $descriptor.Name -cne $spec.Name -or $descriptor.ReturnConvention -cne $spec.ReturnConvention -or $descriptor.SetLastError -ne $spec.SetLastError -or $descriptor.ParameterTypes.Count -ne $parameters.Count -or $descriptor.ParamKinds.Count -ne $parameters.Count -or $descriptor.BufferDirections.Count -ne $parameters.Count -or $descriptor.DllKey -cne $spec.DllKey -or $descriptor.AbsoluteDll -cne $state.Pins[$spec.DllKey] -or $descriptor.ReturnType -ne $spec.ReturnType -or $descriptor.CallingConvention -ne $spec.CallingConvention -or $descriptor.ErrorSentinel -ne $spec.ErrorSentinel) {throw 'R2_INTEROP_DESCRIPTOR_TAMPER'}
        if ($descriptor.NullableParameters.Count -ne $spec.NullableParameters.Count) {throw 'R2_INTEROP_NULLABILITY_TAMPER'}
        for ($i=0;$i -lt $spec.NullableParameters.Count;$i++) {if ($descriptor.NullableParameters[$i] -ne $spec.NullableParameters[$i]) {throw 'R2_INTEROP_NULLABILITY_TAMPER'}}
        $bufferContract=Get-R2FixedBufferContract -ApiId $spec.ApiId
        if (-not [object]::ReferenceEquals($descriptor.OutputSizes,$descriptor.BufferMinimumSizes) -or $descriptor.BufferMinimumSizes.Count -ne $bufferContract.MinimumSizes.Count -or $descriptor.BufferLayouts.Count -ne $bufferContract.BufferLayouts.Count -or $descriptor.DynamicBufferLengths.Count -ne $bufferContract.DynamicBufferLengths.Count -or $descriptor.InformationClassLayouts.Count -ne $bufferContract.InformationClassLayouts.Count) {throw 'R2_INTEROP_BUFFER_CONTRACT_TAMPER'}
        foreach ($index in $bufferContract.MinimumSizes.Keys) {if ($descriptor.BufferMinimumSizes[$index] -ne $bufferContract.MinimumSizes[$index] -or $descriptor.BufferLayouts[$index] -cne $bufferContract.BufferLayouts[$index]) {throw 'R2_INTEROP_BUFFER_MINIMUM_TAMPER'}}
        foreach ($index in $bufferContract.DynamicBufferLengths.Keys) {if ($descriptor.DynamicBufferLengths[$index].LengthParameter -ne $bufferContract.DynamicBufferLengths[$index].LengthParameter -or $descriptor.DynamicBufferLengths[$index].UnitBytes -ne $bufferContract.DynamicBufferLengths[$index].UnitBytes) {throw 'R2_INTEROP_DYNAMIC_BUFFER_TAMPER'}}
        foreach ($class in $bufferContract.InformationClassLayouts.Keys) {if ($descriptor.InformationClassLayouts[$class] -cne $bufferContract.InformationClassLayouts[$class]) {throw 'R2_INTEROP_CLASS_BUFFER_TAMPER'}}
        if ($descriptor.InformationClassParameter -ne $bufferContract.InformationClassParameter -or $descriptor.InformationClassBufferParameter -ne $bufferContract.InformationClassBufferParameter) {throw 'R2_INTEROP_CLASS_PARAMETER_TAMPER'}
        if ($spec.ApiId -eq 64 -and ($descriptor.PdhCounterInfoPrefix.Size -ne 8 -or $descriptor.PdhCounterInfoPrefix.dwLength -ne 0 -or $descriptor.PdhCounterInfoPrefix.dwType -ne 4)) {throw 'R2_INTEROP_PDH_PREFIX_TAMPER'}
    }
    $layouts=@(Get-R2FixedLayoutSpecifications)
    if ($state.Layouts.Count -ne $layouts.Count) {throw 'R2_INTEROP_LAYOUT_TABLE_TAMPER'}
    foreach ($spec in $layouts) {
        if ([Enum]::GetName($state.LayoutEnum,$spec.Id) -cne $spec.Name) {throw 'R2_INTEROP_LAYOUT_ENUM_TAMPER'}
        $layout=$state.Layouts[[Enum]::ToObject($state.LayoutEnum,$spec.Id)]
        if ($null -eq $layout -or $layout.Id.GetType() -ne $state.LayoutEnum -or [uint32]$layout.Id -ne $spec.Id -or $layout.Name -cne $spec.Name -or $layout.Size -ne $spec.Size -or $layout.Alignment -ne $spec.Alignment -or $layout.Fields.Count -ne $spec.Fields.Count -or -not $layout.NativeType.IsExplicitLayout -or -not $layout.NativeType.IsValueType -or $layout.NativeType.StructLayoutAttribute.Size -ne $spec.Size -or -not [object]::ReferenceEquals($layout.NativeType.Assembly,$state.NativeType.Assembly) -or $layout.NativeType.FullName -cne ('Route2.Native.'+$spec.Name)) {throw 'R2_INTEROP_LAYOUT_DESCRIPTOR_TAMPER'}
        foreach ($field in $spec.Fields) {
            $actual=$layout.Fields[$field.Name]
            if ($null -eq $actual -or $actual.Type -ne $field.Type -or $actual.Offset -ne $field.Offset -or $actual.Width -ne $field.Width -or $actual.InlineBytes -ne $field.InlineBytes) {throw 'R2_INTEROP_LAYOUT_FIELD_TAMPER'}
            $names=@($field.Name); if ($field.InlineBytes) {$names=@();for ($j=0;$j -lt $field.Width;$j++) {$names+=($field.Name+'_'+$j)}}
            for ($j=0;$j -lt $names.Count;$j++) {
                $fi=$layout.NativeType.GetField($names[$j]); if ($null -eq $fi -or $fi.FieldType -ne $field.Type) {throw 'R2_INTEROP_LAYOUT_EMITTED_FIELD'}
                $offsets=$fi.GetCustomAttributes([Runtime.InteropServices.FieldOffsetAttribute],$false)
                $expected=[int]$field.Offset; if ($field.InlineBytes) {$expected+=$j}
                if ($offsets.Count -ne 1 -or $offsets[0].Value -ne $expected) {throw 'R2_INTEROP_LAYOUT_EMITTED_OFFSET'}
            }
        }
    }
}

function Get-R2InteropPlanReference {
    param([Parameter(Mandatory=$true)][object]$Interop)
    Assert-R2InteropConstruction -Interop $Interop
    return ,$Interop.PlanReference
}

function Bind-R2InteropInternal {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][object]$Context,[Parameter(Mandatory=$true)][object]$Interop)
    try {
    Assert-R2ContextReference -Context $Context
    Assert-R2InteropConstruction -Interop $Interop
    $state=$null
    foreach ($candidate in $script:R2InteropPrivateRegistry) {if ([object]::ReferenceEquals($candidate.View,$Interop)) {$state=$candidate;break}}
    if ($state.BindingAttempted -or $null -ne $state.BoundContext -or $null -ne $Context.Interop -or -not [object]::ReferenceEquals($Context.PlanReference,$state.Plan)) {throw 'R2_INTEROP_REBIND_OR_PLAN'}
    if ($null -ne $state.BootstrapQuarantine) {Assert-R2BootstrapPromotion -Context $Context -Quarantine $state.BootstrapQuarantine}
    # Attempt is consumed before mutation. A failed ledger attachment cannot rebind.
    $state.BindingAttempted=$true
    $state.BoundContext=$Context; $state.Backing['BoundContextReference']=$Context
    } catch {
        Set-R2InteropIntegrityFailure -Interop $Interop -Context $Context
        throw [InvalidOperationException]::new('R2_INTEROP_BIND_FAILED',$_.Exception)
    }
}

function Assert-R2NativeLayout {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][object]$Interop)
    try {
    Assert-R2InteropConstruction -Interop $Interop
    if ($null -eq $Interop.BoundContextReference) {throw 'R2_INTEROP_LAYOUT_BEFORE_BIND'}
    Assert-R2ContextReference -Context $Interop.BoundContextReference
    if (-not [object]::ReferenceEquals($Interop.BoundContextReference.Interop,$Interop)) {throw 'R2_INTEROP_LAYOUT_CONTEXT'}
    if ([IntPtr]::Size -ne 8) {throw 'R2_INTEROP_POINTER_WIDTH'}
    $originalState=$null
    foreach ($state in $script:R2InteropPrivateRegistry) {if ([object]::ReferenceEquals($state.View,$Interop)) {$originalState=$state;break}}
    foreach ($spec in @(Get-R2FixedLayoutSpecifications)) {
        $type=$originalState.Layouts[[Enum]::ToObject($originalState.LayoutEnum,$spec.Id)].NativeType
        if ([Runtime.InteropServices.Marshal]::SizeOf($type) -ne $spec.Size) {throw 'R2_INTEROP_NATIVE_LAYOUT_SIZE'}
        foreach ($field in $spec.Fields) {
            if ($field.InlineBytes) {
                for ($i=0; $i -lt $field.Width; $i++) {
                    if ([Runtime.InteropServices.Marshal]::OffsetOf($type,($field.Name+'_'+$i)).ToInt64() -ne ([int64]$field.Offset+$i)) {throw 'R2_INTEROP_NATIVE_INLINE_OFFSET'}
                }
            } elseif ([Runtime.InteropServices.Marshal]::OffsetOf($type,$field.Name).ToInt64() -ne $field.Offset) {throw 'R2_INTEROP_NATIVE_FIELD_OFFSET'}
        }
    }
    foreach ($state in $script:R2InteropPrivateRegistry) {if ([object]::ReferenceEquals($state.View,$Interop)) {$state.LayoutVerified=$true;break}}
    } catch {
        Set-R2InteropIntegrityFailure -Interop $Interop -Context $null
        throw [InvalidOperationException]::new('R2_INTEROP_NATIVE_LAYOUT_FAILED',$_.Exception)
    }
}

function Get-R2NativeApi {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][object]$Context,[Parameter(Mandatory=$true)][uint32]$ApiId)
    try {
    Assert-R2ContextReference -Context $Context
    $interop=$Context.Interop
    if ($null -eq $interop) {throw 'R2_INTEROP_CALL_BEFORE_BIND'}
    Assert-R2InteropConstruction -Interop $interop
    if (-not [object]::ReferenceEquals($interop.BoundContextReference,$Context)) {throw 'R2_INTEROP_CONTEXT_MISMATCH'}
    foreach ($state in $script:R2InteropPrivateRegistry) {
        if ([object]::ReferenceEquals($state.View,$interop)) {
            if (-not [Enum]::IsDefined($state.ApiEnum,$ApiId)) {throw 'R2_INTEROP_UNKNOWN_API'}
            if (-not $state.LayoutVerified) {throw 'R2_INTEROP_API_BEFORE_ABI_ASSERTION'}
            return ,$interop.ApiTable[[Enum]::ToObject($state.ApiEnum,$ApiId)]
        }
    }
    throw 'R2_INTEROP_UNISSUED_API'
    } catch {
        Set-R2InteropIntegrityFailure -Interop $null -Context $Context
        throw [InvalidOperationException]::new('R2_INTEROP_API_FAILED',$_.Exception)
    }
}

function Get-R2NativeDescriptor {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][object]$Context,[Parameter(Mandatory=$true)][uint32]$ApiId)
    try {
    $null=Get-R2NativeApi -Context $Context -ApiId $ApiId
    foreach ($state in $script:R2InteropPrivateRegistry) {
        if ([object]::ReferenceEquals($state.View,$Context.Interop)) {return ,$state.Descriptors[[Enum]::ToObject($state.ApiEnum,$ApiId)]}
    }
    throw 'R2_INTEROP_DESCRIPTOR_UNISSUED'
    } catch {
        Set-R2InteropIntegrityFailure -Interop $null -Context $Context
        throw [InvalidOperationException]::new('R2_INTEROP_DESCRIPTOR_FAILED',$_.Exception)
    }
}

function Get-R2ApiIdByName {
    param([Parameter(Mandatory=$true)][object]$Interop,[Parameter(Mandatory=$true)][string]$Name)
    try {
    Assert-R2InteropConstruction -Interop $Interop
    $matches=@(Get-R2FixedApiSpecifications | Where-Object {$_.Name -ceq $Name})
    if ($matches.Count -ne 1) {throw 'R2_INTEROP_UNKNOWN_FIXED_API_NAME'}
    foreach ($state in $script:R2InteropPrivateRegistry) {if ([object]::ReferenceEquals($state.View,$Interop)) {return [Enum]::ToObject($state.ApiEnum,$matches[0].ApiId)}}
    throw 'R2_INTEROP_NAME_LOOKUP_UNISSUED'
    } catch {
        Set-R2InteropIntegrityFailure -Interop $Interop -Context $null
        throw [InvalidOperationException]::new('R2_INTEROP_API_NAME_FAILED',$_.Exception)
    }
}

function Get-R2LayoutIdByName {
    param([Parameter(Mandatory=$true)][object]$Interop,[Parameter(Mandatory=$true)][string]$Name)
    try {
    Assert-R2InteropConstruction -Interop $Interop
    $matches=@(Get-R2FixedLayoutSpecifications | Where-Object {$_.Name -ceq $Name})
    if ($matches.Count -ne 1) {throw 'R2_INTEROP_UNKNOWN_FIXED_LAYOUT_NAME'}
    foreach ($state in $script:R2InteropPrivateRegistry) {if ([object]::ReferenceEquals($state.View,$Interop)) {return [Enum]::ToObject($state.LayoutEnum,$matches[0].Id)}}
    throw 'R2_INTEROP_LAYOUT_LOOKUP_UNISSUED'
    } catch {
        Set-R2InteropIntegrityFailure -Interop $Interop -Context $null
        throw [InvalidOperationException]::new('R2_INTEROP_LAYOUT_NAME_FAILED',$_.Exception)
    }
}

function Get-R2NativeLayoutDescriptor {
    param([Parameter(Mandatory=$true)][object]$Interop,[Parameter(Mandatory=$true)][string]$Name)
    $id=Get-R2LayoutIdByName -Interop $Interop -Name $Name
    return ,$Interop.Layouts[$id]
}

function Get-R2BootstrapNativeApi {
    [CmdletBinding()]
    param([Parameter(Mandatory=$true)][object]$Quarantine,[Parameter(Mandatory=$true)][object]$Interop,[Parameter(Mandatory=$true)][uint32]$ApiId)
    try {
    Assert-R2BootstrapQuarantineReference -Quarantine $Quarantine
    Assert-R2InteropConstruction -Interop $Interop
    # Only original-handle bootstrap reading, self/parent/root identity, current
    # SID and the single actual named client are admitted before local authority.
    # Event/completion/cancellation are restricted by ledger to the SAME pending
    # read, manual-reset TRUE, initial FALSE, name NULL, non-inheritable event.
    # CreateFileW is additionally constrained to that exact pipe by ledger's
    # quarantine invoker; this table does not authorize file/target acquisition.
    $allowed=[uint32[]]@(24,25,28,31,32,36,38,39,40,41,42,46,48,49,51,68,69,70,71)
    if ($ApiId -notin $allowed) {throw 'R2_INTEROP_BOOTSTRAP_API_FORBIDDEN'}
    foreach ($state in $script:R2InteropPrivateRegistry) {
        if (-not [object]::ReferenceEquals($state.View,$Interop)) {continue}
        if ($null -ne $state.BoundContext -or $state.BindingAttempted -or -not [object]::ReferenceEquals($Quarantine.PlanReference,$state.Plan)) {throw 'R2_INTEROP_BOOTSTRAP_PLAN_OR_BOUND'}
        if ($null -eq $state.BootstrapQuarantine) {$state.BootstrapQuarantine=$Quarantine}
        elseif (-not [object]::ReferenceEquals($state.BootstrapQuarantine,$Quarantine)) {throw 'R2_INTEROP_BOOTSTRAP_REPLACED'}
        # ABI assertions are required before any native call, including bootstrap.
        # This is an in-H1 managed Marshal check, not a native/self probe or epoch.
        if (-not $state.LayoutVerified) {
            foreach ($spec in @(Get-R2FixedLayoutSpecifications)) {
                $layout=$state.Layouts[[Enum]::ToObject($state.LayoutEnum,$spec.Id)]
                if ([Runtime.InteropServices.Marshal]::SizeOf($layout.NativeType) -ne $spec.Size) {throw 'R2_INTEROP_BOOTSTRAP_ABI_SIZE'}
                foreach ($field in $spec.Fields) {
                    $fieldName=$field.Name;if ($field.InlineBytes) {$fieldName+='_0'}
                    if ([Runtime.InteropServices.Marshal]::OffsetOf($layout.NativeType,$fieldName).ToInt64() -ne $field.Offset) {throw 'R2_INTEROP_BOOTSTRAP_ABI_OFFSET'}
                }
            }
            $state.LayoutVerified=$true
        }
        return ,$state.ApiTable[[Enum]::ToObject($state.ApiEnum,$ApiId)]
    }
    throw 'R2_INTEROP_BOOTSTRAP_UNISSUED'
    } catch {
        Set-R2InteropIntegrityFailure -Interop $Interop -Context $null
        throw [InvalidOperationException]::new('R2_INTEROP_BOOTSTRAP_API_FAILED',$_.Exception)
    }
}

function Get-R2BootstrapNativeDescriptor {
    param([Parameter(Mandatory=$true)][object]$Quarantine,[Parameter(Mandatory=$true)][object]$Interop,[Parameter(Mandatory=$true)][uint32]$ApiId)
    $null=Get-R2BootstrapNativeApi -Quarantine $Quarantine -Interop $Interop -ApiId $ApiId
    foreach ($state in $script:R2InteropPrivateRegistry) {if ([object]::ReferenceEquals($state.View,$Interop)) {return ,$state.Descriptors[[Enum]::ToObject($state.ApiEnum,$ApiId)]}}
    throw 'R2_INTEROP_BOOTSTRAP_DESCRIPTOR_UNISSUED'
}

    Export-ModuleMember -Function Assert-R2InteropConstruction,Get-R2InteropPlanReference,Bind-R2InteropInternal,Assert-R2NativeLayout,Get-R2NativeApi,Get-R2NativeDescriptor,Get-R2ApiIdByName,Get-R2LayoutIdByName,Get-R2NativeLayoutDescriptor,Get-R2BootstrapNativeApi,Get-R2BootstrapNativeDescriptor
    }
    Import-Module -ModuleInfo $issuerModule -Global -ErrorAction Stop
    return ,(& $issuerModule {param([object]$OriginalPlan) New-R2InteropState -Plan $OriginalPlan} $Plan)
}
