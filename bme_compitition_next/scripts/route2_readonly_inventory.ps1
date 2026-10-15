# SOURCE PROPOSAL ONLY. H3 is OWNER_NOT_APPROVED until the owner approves the
# exact source and policy hashes and trusted root consumes its sole invocation.
# H3 is an ADDITIONAL 120s active + 60s cleanup allowance, never Stage admission,
# H1 start, disk-plan authority, a scientific run, or a historical-budget reset.
# H1 remains APPROVED_UNSTARTED; old unmeasured history is UNKNOWN_NOT_ZERO.
#
# Activation is a bounded, exact block in the ORIGINAL design-review document.
# A trusted root must verify the ACTUAL owner message, durably record consumption
# in all original three documents, Flush(true), then invoke this file IN THE SAME
# already-loaded PowerShell process whose QPC epoch preceded those writes.
# Missing approval refuses. This script issues no approval and cannot establish
# owner identity or durable anti-replay from strings. An interrupted launch is
# consumed: no retry. Never manufacture the block to demonstrate execution.
#
# Scoped H3 exceptions (no Stage-criterion waiver): already-loaded trusted parent
# startup/creator history and first-loader identity; no raw creator/primary-thread
# closure; MONITORED64 application threads instead of original formal limit four;
# incomplete RAM/kernel/service/physical accounting and ALL metadata/log/cache/
# registry/pagefile charges; sampled, cooperative deadline enforcement. Provider
# infrastructure may survive child join: NOT_JOINED_EXITED, UNKNOWN_NOT_ZERO.
# Source-path lock/hash is not a native executable-image HANDLE identity proof.
#
# API evidence (Context7 resolution used; exact .NET API had no relevant hit):
# https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.process.waitforexit
# https://learn.microsoft.com/en-us/dotnet/api/system.diagnostics.process.kill
# https://learn.microsoft.com/en-us/dotnet/api/system.io.stream.readasync
# https://learn.microsoft.com/en-us/powershell/module/storage/get-disk
# https://learn.microsoft.com/en-us/powershell/module/storage/get-partition
# https://learn.microsoft.com/en-us/powershell/module/storage/get-volume
# Kill is asynchronous; WaitForExit(1) joins only this original Process, not services.
[CmdletBinding()]
param(
    [string] $ActivationSha256 = '',
    [switch] $InventoryChild,
    [long] $OriginalEpoch = 0,
    [long] $OriginalFrequency = 0,
    [long] $ActiveStop = 0,
    [long] $CleanupStop = 0,
    [string] $InvocationNonce = '',
    [long] $SharedAffinityMask = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
$WarningPreference = 'SilentlyContinue'
$InformationPreference = 'SilentlyContinue'
$entryQpc = [Diagnostics.Stopwatch]::GetTimestamp()
$frequency = [Diagnostics.Stopwatch]::Frequency
$PolicyId = 'route2-h3-readonly-inventory-2026-10-15-001'
$PolicySha256 = 'b255b40a7a4f83acee88019a32f811a87e27521bd174d2b1bb76ed10dd233dab'
$ExceptionIds = 'ADOPT_TOOL_STARTED_POWERSHELL_ROOT_PRELOAD_CREATOR|DOTNET_ORIGINAL_PROCESS_NOT_NATIVE_PI_THREAD_JOIN|H3_MONITORED64_NOT_FORMAL4|H3_SAMPLED_RESOURCES_NOT_COMPLETE_CAUSAL_CAPS|H3_SHARED_PROVIDER_SERVICE_TAIL_UNJOINED|H3_E_NON_E_PHYSICAL_ACCOUNTING_UNPROVEN|H3_HARD_DEADLINE_SYNC_STALL_UNPROVEN|H3_TRUSTED_HOST_ONE_SHOT_NOT_SCRIPT_ANTIREPLAY|H3_ADDITIONAL_ONE180_NOT_H1_EPOCH'
$pin = $null
$parent = $null
$child = $null
$started = $false
$startAttempted = $false
$joined = $false
$primaryFault = $null
$cleanupFaults = New-Object 'System.Collections.Generic.List[string]'
$violations = New-Object 'System.Collections.Generic.List[string]'
$receipt = $null
$outState = $null
$errState = $null
$exitDword = $null
$killRequested = $false
$phase = 'REFUSED_BEFORE_ACTIVATION'
$sourceSha = $null
$maxParentWs = $null
$maxChildWs = $null
$maxCombinedWs = $null
$maxThreads = $null
$resourceSamples = 0
$lastSampleQpc = 0
$childStartCallQpc = $null
$childStartReturnedQpc = $null
$monitorBaselineQpc = $null
$firstResourceSampleQpc = $null
$parentAffinityOriginal = $null
$processImage = $null
$primaryErrorType = $null
$primaryHResult = $null
$childCompleted = $false
$childCollectionComplete = $false
$parentCoreMask = $null
$maxParentThreads = $null
$cleanupLiveSamples = 0
$cleanupParentOnlySamples = 0
$cleanupSampleFailures = 0
$lastCleanupSampleQpc = $null
$finalParentSampleQpc = $null

function Fail([string] $Code) {
    $e = [InvalidOperationException]::new('H3_FIXED_FAILURE')
    $e.Data['Route2FixedCode'] = $Code
    throw $e
}
function Now { [Diagnostics.Stopwatch]::GetTimestamp() }
function Check-Active {
    if ((Now) -ge $script:ActiveStop) { Fail 'ACTIVE_DEADLINE_REACHED' }
}
function Sha-Bytes([byte[]] $Bytes) {
    $sha = [Security.Cryptography.SHA256]::Create()
    try { return ([BitConverter]::ToString($sha.ComputeHash($Bytes))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
}
function Read-Bounded([string] $Path, [int] $Limit) {
    $s = [IO.File]::Open($Path, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    try {
        if ($s.Length -gt $Limit) { Fail 'SOURCE_OR_RECEIPT_TOO_LARGE' }
        $b = New-Object byte[] ([int]$s.Length)
        $n = 0
        while ($n -lt $b.Length) {
            $k = $s.Read($b, $n, $b.Length - $n)
            if ($k -eq 0) { Fail 'SHORT_FILE_READ' }
            $n += $k
        }
        if ($s.ReadByte() -ne -1) { Fail 'FILE_GREW_DURING_READ' }
        return ,$b
    } finally { $s.Dispose() }
}
function Text-Field($Value, [int] $Limit = 512) {
    if ($null -eq $Value) { return $null }
    $v = [string]$Value
    if ($v.Length -gt $Limit -or $v -match '[\x00-\x08\x0b\x0c\x0e-\x1f]') { Fail 'FACT_FIELD_SHAPE' }
    return $v
}
function Write-ChildRecord($Value) {
    $encoded = [Text.UTF8Encoding]::new($false, $true).GetBytes(($Value | ConvertTo-Json -Depth 12 -Compress))
    # Retain the earliest bounded facts if a later group exceeds the wire shape.
    # Capture allocations remain 64KiB/8KiB; the child's wire record is <=32KiB
    # so base64 plus parent metadata can fit the parent's total 64KiB stdout.
    $omitted = New-Object 'System.Collections.Generic.List[string]'
    foreach ($group in @('wslconfig','lxss','volume','partition','disk','computer_system','admin_membership','os_build')) {
        if ($encoded.Length -le 32768) { break }
        if ($Value.Contains($group)) {
            $Value.Remove($group)
            $omitted.Add($group)
            $Value['collection_complete'] = $false
            $Value['output_shape_fault'] = 'PARTIAL_FACTS_32KIB_WIRE_LIMIT'
            $Value['output_omitted_groups'] = $omitted.ToArray()
            $encoded = [Text.UTF8Encoding]::new($false, $true).GetBytes(($Value | ConvertTo-Json -Depth 12 -Compress))
        }
    }
    if ($encoded.Length -gt 32768) { Fail 'CHILD_FACT_HEADER_EXCEEDS_32KIB' }
    $stream = [Console]::OpenStandardOutput()
    $stream.Write($encoded, 0, $encoded.Length)
    $stream.Flush()
}
function New-Capture([int] $Capacity) {
    return @{ Buffer = (New-Object byte[] $Capacity); Used = 0; Task = $null; Eof = $false; Capacity = $Capacity; Requested = 0 }
}
function Capture-State($State) {
    if ($null -eq $State) { return 'NOT_ALLOCATED' }
    if ($State.Eof) { return 'EOF_OBSERVED_NO_OUTSTANDING_TASK' }
    if ($null -eq $State.Task) { return 'NO_TASK_NO_EOF_PROOF' }
    if (-not $State.Task.IsCompleted) { return 'PENDING_UNHARVESTED' }
    if ($State.Task.IsCanceled) { return 'CANCELED_UNHARVESTED' }
    if ($State.Task.IsFaulted) { return 'FAULTED_UNHARVESTED' }
    return 'COMPLETED_UNHARVESTED'
}
function Pump-Capture($State, [IO.Stream] $Stream) {
    if ($null -ne $State.Task -and $State.Task.IsCompleted) {
        # Result is inspected only after completion; never a blocking Result call.
        $n = $State.Task.GetAwaiter().GetResult()
        if ($n -lt 0 -or $n -gt $State.Requested) { Fail 'READ_TASK_INVALID_COUNT' }
        $State.Used += $n
        $State.Task = $null
        if ($n -eq 0) { $State.Eof = $true }
        elseif ($State.Used -ge $State.Capacity) { Fail 'CAPTURE_LIMIT_REACHED' }
    }
    if (-not $State.Eof -and $null -eq $State.Task) {
        $State.Requested = [Math]::Min(4096, $State.Capacity - $State.Used)
        if ($State.Requested -le 0) { Fail 'CAPTURE_LIMIT_REACHED' }
        $State.Task = $Stream.ReadAsync($State.Buffer, $State.Used, $State.Requested)
    }
}
function Add-CleanupResourceFault([string] $Code) {
    # Finite fixed codes, recorded once even if a cleanup loop samples repeatedly.
    if (-not $script:cleanupFaults.Contains($Code)) { $script:cleanupFaults.Add($Code) }
    if ($Code -match 'OVER_(512MIB|4GIB|MONITORED64)|AFFINITY' -and -not $script:violations.Contains($Code)) { $script:violations.Add($Code) }
}
function Sample-CleanupResources([switch] $ParentOnly, [switch] $Final) {
    # Called AFTER the available original kill/join operation in each iteration.
    # Observation failures record failure and return; they never escape this
    # function or prevent the next available original-object join attempt.
    $sampleStart = Now
    if ($sampleStart -ge $script:CleanupStop) {
        Add-CleanupResourceFault 'CLEANUP_RESOURCE_SAMPLE_MISSING_ABSOLUTE_DEADLINE'
        return
    }
    if ($script:lastSampleQpc -le 0) {
        Add-CleanupResourceFault 'CLEANUP_RESOURCE_PRIOR_CADENCE_UNOBSERVED'
    } elseif (($sampleStart - $script:lastSampleQpc) -gt ([decimal]$script:frequency / 10)) {
        Add-CleanupResourceFault 'CLEANUP_RESOURCE_SAMPLE_STALE_OVER_100MS'
    }
    try {
        $script:parent.Refresh()
        $ws = $script:parent.WorkingSet64
        $threadCount = $script:parent.Threads.Count
        $affinity = $script:parent.ProcessorAffinity.ToInt64()
        $script:maxParentWs = [Math]::Max([long]$script:maxParentWs, $ws)
        $script:maxParentThreads = [Math]::Max([int]$script:maxParentThreads, $threadCount)
        if ($ws -gt 536870912) { Add-CleanupResourceFault 'CLEANUP_PARENT_WORKING_SET_OVER_512MIB' }
        if ($threadCount -gt 64) { Add-CleanupResourceFault 'CLEANUP_PARENT_THREADS_OVER_MONITORED64' }
        if ($null -eq $script:parentCoreMask -or $affinity -ne $script:parentCoreMask) { Add-CleanupResourceFault 'CLEANUP_PARENT_AFFINITY_UNCONFIGURED_OR_DRIFT' }
    } catch {
        $script:cleanupSampleFailures++
        Add-CleanupResourceFault 'CLEANUP_PARENT_RESOURCE_SAMPLE_FAILED'
        return
    }
    if ((Now) -ge $script:CleanupStop) {
        Add-CleanupResourceFault 'CLEANUP_RESOURCE_SAMPLE_FINISHED_AFTER_ABSOLUTE_DEADLINE'
        return
    }
    if ($ParentOnly) {
        # A joined child's RSS/threads are never queried and are never zeroed.
        $script:cleanupParentOnlySamples++
    } else {
        try {
            $script:child.Refresh()
            $childWs = $script:child.WorkingSet64
            $childThreads = $script:child.Threads.Count
            $childAffinity = $script:child.ProcessorAffinity.ToInt64()
            $script:maxChildWs = [Math]::Max([long]$script:maxChildWs, $childWs)
            $script:maxCombinedWs = [Math]::Max([long]$script:maxCombinedWs, $ws + $childWs)
            $script:maxThreads = [Math]::Max([int]$script:maxThreads, $threadCount + $childThreads)
            $script:cleanupLiveSamples++
            if ($childWs -gt 4294967296 -or ($ws + $childWs) -gt 4294967296) { Add-CleanupResourceFault 'CLEANUP_CHILD_OR_COMBINED_WORKING_SET_OVER_4GIB' }
            if (($threadCount + $childThreads) -gt 64) { Add-CleanupResourceFault 'CLEANUP_COMBINED_THREADS_OVER_MONITORED64' }
            if ($childAffinity -ne $script:SharedAffinityMask) { Add-CleanupResourceFault 'CLEANUP_CHILD_AFFINITY_DRIFT' }
        } catch {
            $script:cleanupSampleFailures++
            Add-CleanupResourceFault 'CLEANUP_LIVE_CHILD_RESOURCE_SAMPLE_FAILED'
            return
        }
    }
    $sampleEnd = Now
    $script:lastCleanupSampleQpc = $sampleEnd
    if ($Final) { $script:finalParentSampleQpc = $sampleEnd }
    if (($sampleEnd - $sampleStart) -gt ([decimal]$script:frequency / 10) -or ($script:lastSampleQpc -gt 0 -and ($sampleEnd - $script:lastSampleQpc) -gt ([decimal]$script:frequency / 10))) {
        Add-CleanupResourceFault 'CLEANUP_RESOURCE_SAMPLE_STALE_OVER_100MS'
    }
    if ($sampleEnd -ge $script:CleanupStop) { Add-CleanupResourceFault 'CLEANUP_RESOURCE_SAMPLE_FINISHED_AFTER_ABSOLUTE_DEADLINE' }
    $script:lastSampleQpc = $sampleEnd
}
function Collect-Facts {
    $facts = [ordered]@{
        schema = 'route2_h3_readonly_inventory_facts_v1'
        nonce = $InvocationNonce
        qpc_epoch = $OriginalEpoch
        qpc_frequency = $OriginalFrequency
        active_stop_qpc = $ActiveStop
        cleanup_stop_qpc = $CleanupStop
        source_sha256 = $script:sourceSha
        raw_fact_authority = 'OBSERVATIONS_ONLY_NO_DISK_PLAN_TARGET_OR_ADMISSION_AUTHORITY'
        identity_coherence = 'PATH_VS_HANDLE_AND_CROSS_FACT_COHERENCE_UNPROVEN'
        vram = 'UNKNOWN_NOT_ZERO_NO_GPU_PAYLOAD_WMI_ADAPTERRAM_NOT_EXACT_VRAM'
        provider_infrastructure = 'NOT_JOINED_EXITED_UNKNOWN_NOT_ZERO'
        collection_complete = $false
    }
    $factStage = 'os_build'
    try {
    $pre = Now
    Check-Active
    $osKey = [Microsoft.Win32.Registry]::LocalMachine.OpenSubKey('SOFTWARE\Microsoft\Windows NT\CurrentVersion', $false)
    if ($null -eq $osKey) { Fail 'FIXED_OS_BUILD_KEY_UNAVAILABLE' }
    try {
        $buildNumber = Text-Field ($osKey.GetValue('CurrentBuildNumber', $null))
        $ubr = $osKey.GetValue('UBR', $null)
        $productName = Text-Field ($osKey.GetValue('ProductName', $null))
        $displayVersion = Text-Field ($osKey.GetValue('DisplayVersion', $null))
        $facts.os_build = @{qpc_pre=$pre;qpc_post=(Now);current_build_number=$buildNumber;ubr=$ubr;product_name=$productName;display_version=$displayVersion;api_support='OBSERVATION_ONLY_UNPROVEN'}
    } finally { $osKey.Dispose() }
    $factStage = 'admin_membership'
    $pre = Now
    Check-Active
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    try {
        $principal = [Security.Principal.WindowsPrincipal]::new($identity)
        $adminMembership = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
        $facts.admin_membership = @{qpc_pre=$pre;qpc_post=(Now);current_token_builtin_administrators=$adminMembership;privilege_rights_proof='UNPROVEN_MEMBERSHIP_ONLY'}
    } finally { $identity.Dispose() }
    $factStage = 'computer_system'
    $pre = Now
    Check-Active
    $systems = @(CimCmdlets\Get-CimInstance -ClassName Win32_ComputerSystem -Property TotalPhysicalMemory,NumberOfLogicalProcessors -OperationTimeoutSec 10 -ErrorAction Stop | Select-Object -First 2)
    if ($systems.Count -ne 1) { Fail 'COMPUTER_SYSTEM_COUNT_NOT_1' }
    $ramReported = $systems[0].TotalPhysicalMemory
    $cpusReported = $systems[0].NumberOfLogicalProcessors
    $facts.computer_system = @{qpc_pre=$pre;qpc_post=(Now);total_physical_memory_reported=$ramReported;logical_processors_reported=$cpusReported;complete_budget_ram='UNKNOWN_NOT_ZERO'}
    $factStage = 'disk'
    $pre = Now
    Check-Active
    $disks = New-Object 'System.Collections.Generic.List[object]'
    Storage\Get-Disk -ThrottleLimit 1 -ErrorAction Stop | ForEach-Object {
        Check-Active
        if ($disks.Count -ge 8) { Fail 'DISK_COUNT_EXCEEDS_8' }
        $disks.Add([ordered]@{number=$_.Number;unique_id=(Text-Field $_.UniqueId);serial_number=(Text-Field $_.SerialNumber);size=$_.Size;logical_sector_size=$_.LogicalSectorSize;physical_sector_size=$_.PhysicalSectorSize;partition_style=(Text-Field $_.PartitionStyle);bus_type=(Text-Field $_.BusType);is_boot=$_.IsBoot;is_system=$_.IsSystem;is_read_only=$_.IsReadOnly;is_offline=$_.IsOffline})
    }
    $facts.disk = @{qpc_pre=$pre;qpc_post=(Now);items=$disks.ToArray();returned_limit=8;provider_internal_allocation='UNKNOWN_NOT_ZERO'}
    $factStage = 'partition'
    $pre = Now
    Check-Active
    $parts = New-Object 'System.Collections.Generic.List[object]'
    Storage\Get-Partition -ThrottleLimit 1 -ErrorAction Stop | ForEach-Object {
        Check-Active
        if ($parts.Count -ge 128) { Fail 'PARTITION_COUNT_EXCEEDS_128' }
        $accessPaths = @($_.AccessPaths)
        if ($accessPaths.Count -gt 8) { Fail 'PARTITION_ACCESS_PATH_COUNT_EXCEEDS_8' }
        $safePaths = @($accessPaths | ForEach-Object { Text-Field $_ 1024 })
        $parts.Add([ordered]@{disk_number=$_.DiskNumber;partition_number=$_.PartitionNumber;offset=$_.Offset;size=$_.Size;gpt_type=(Text-Field $_.GptType);access_paths=$safePaths;drive_letter=(Text-Field $_.DriveLetter);type=(Text-Field $_.Type);is_boot=$_.IsBoot;is_system=$_.IsSystem})
    }
    $facts.partition = @{qpc_pre=$pre;qpc_post=(Now);items=$parts.ToArray();returned_limit=128;provider_internal_allocation='UNKNOWN_NOT_ZERO'}
    $factStage = 'volume'
    $pre = Now
    Check-Active
    $volumes = New-Object 'System.Collections.Generic.List[object]'
    Storage\Get-Volume -ThrottleLimit 1 -ErrorAction Stop | ForEach-Object {
        Check-Active
        if ($volumes.Count -ge 64) { Fail 'VOLUME_COUNT_EXCEEDS_64' }
        $volumes.Add([ordered]@{unique_id=(Text-Field $_.UniqueId);drive_letter=(Text-Field $_.DriveLetter);file_system=(Text-Field $_.FileSystem);file_system_type_raw=$_.FileSystemType;size=$_.Size;size_remaining=$_.SizeRemaining;health_status=(Text-Field $_.HealthStatus)})
    }
    $facts.volume = @{qpc_pre=$pre;qpc_post=(Now);items=$volumes.ToArray();returned_limit=64;provider_internal_allocation='UNKNOWN_NOT_ZERO'}
    $factStage = 'lxss'
    $pre = Now
    Check-Active
    $lxss = [Microsoft.Win32.Registry]::CurrentUser.OpenSubKey('Software\Microsoft\Windows\CurrentVersion\Lxss', $false)
    $distros = New-Object 'System.Collections.Generic.List[object]'
    try {
        if ($null -ne $lxss) {
            if ($lxss.SubKeyCount -gt 32) { Fail 'LXSS_COUNT_EXCEEDS_32' }
            $names = @($lxss.GetSubKeyNames())
            if ($names.Count -gt 32) { Fail 'LXSS_COUNT_CHANGED_OVER_32' }
            foreach ($name in $names) {
                Check-Active
                if ($name -notmatch '^\{[0-9a-fA-F-]{36}\}$') { Fail 'LXSS_KEY_SHAPE' }
                $key = $lxss.OpenSubKey($name, $false)
                if ($null -eq $key) { Fail 'LXSS_KEY_DISAPPEARED' }
                try {
                    $base = Text-Field ($key.GetValue('BasePath', $null, [Microsoft.Win32.RegistryValueOptions]::DoNotExpandEnvironmentNames)) 1024
                    $vhd = @{status='UNKNOWN_NOT_ZERO';path_vs_handle='METADATA_PATH_ONLY_NO_PAYLOAD_HANDLE'}
                    if ($null -ne $base) {
                        $localBase = $base
                        if ($localBase.StartsWith('\\?\')) { $localBase = $localBase.Substring(4) }
                        if ($localBase -notmatch '^[a-zA-Z]:\\' -or $localBase.Contains('..') -or $localBase.Substring(2).Contains(':')) { Fail 'LXSS_BASE_NOT_LOCAL_DOS_PATH' }
                        $vhdPath = [IO.Path]::Combine($localBase, 'ext4.vhdx')
                        $vhdPre = Now
                        $info = [IO.FileInfo]::new($vhdPath)
                        $info.Refresh()
                        if ($info.Exists) {
                            $vhdLength = $info.Length
                            $vhdLastWrite = $info.LastWriteTimeUtc.ToString('o')
                            $vhdAttributes = Text-Field $info.Attributes
                            $vhd = @{status='METADATA_OBSERVED';qpc_pre=$vhdPre;qpc_post=(Now);length=$vhdLength;last_write_utc=$vhdLastWrite;attributes=$vhdAttributes;path_vs_handle='METADATA_PATH_ONLY_NO_PAYLOAD_HANDLE';allocation_and_coherence='UNPROVEN'}
                        } else { $vhd = @{status='ABSENT_OR_INACCESSIBLE_NOT_PROOF_OF_ZERO';qpc_pre=$vhdPre;qpc_post=(Now);path_vs_handle='METADATA_PATH_ONLY_NO_PAYLOAD_HANDLE'} }
                    }
                    $distros.Add(@{name=(Text-Field ($key.GetValue('DistributionName', $null)));version=$key.GetValue('Version', $null);base_path=$base;default_uid=$key.GetValue('DefaultUid', $null);ext4_vhdx=$vhd})
                } finally { $key.Dispose() }
            }
        }
    } finally { if ($null -ne $lxss) { $lxss.Dispose() } }
    $facts.lxss = @{qpc_pre=$pre;qpc_post=(Now);items=$distros.ToArray();returned_limit=32;wsl_start='NEVER_REQUESTED';registry_fees='UNKNOWN_NOT_ZERO'}
    $factStage = 'wslconfig'
    $pre = Now
    Check-Active
    $configPath = [IO.Path]::Combine([Environment]::GetFolderPath([Environment+SpecialFolder]::UserProfile), '.wslconfig')
    $configInfo = [IO.FileInfo]::new($configPath)
    $configInfo.Refresh()
    $settings = [ordered]@{}
    $configStatus = 'ABSENT_OR_INACCESSIBLE_NOT_PROOF_OF_ZERO'
    if ($configInfo.Exists) {
        $bytes = Read-Bounded $configPath 65536
        $text = [Text.UTF8Encoding]::new($false, $true).GetString($bytes)
        if ($text.Length -gt 0 -and $text[0] -eq [char]0xfeff) { $text = $text.Substring(1) }
        $section = ''
        foreach ($line in ($text -split '\r?\n')) {
            Check-Active
            if ($line -match '^\s*\[([^\]]+)\]\s*(?:[#;].*)?$') { $section = $Matches[1].ToLowerInvariant(); continue }
            if ($section -eq 'wsl2' -and $line -match '^\s*(memory|swap|processors|guiApplications)\s*=\s*([^#;]*?)(?:\s*[#;].*)?$') {
                $keyName = $Matches[1].ToLowerInvariant()
                if ($settings.Contains($keyName)) { Fail 'DUPLICATE_SELECTED_WSLCONFIG_KEY' }
                $settings[$keyName] = Text-Field ($Matches[2].Trim()) 128
            }
        }
        $configStatus = 'SELECTED_KEYS_ONLY_READ'
    }
    $facts.wslconfig = @{qpc_pre=$pre;qpc_post=(Now);status=$configStatus;max_bytes=65536;settings=$settings;path_vs_handle='PATH_AND_READ_HANDLE_COHERENCE_UNPROVEN';all_other_content='NOT_EMITTED'}
    Check-Active
    $facts['collection_complete'] = $true
    } catch {
        $failure = $_.Exception
        $code = $null
        for ($depth = 0; $depth -lt 8; $depth++) {
            if ($failure.Data.Contains('Route2FixedCode')) { $code = Text-Field $failure.Data['Route2FixedCode'] 128 }
            if ($null -eq $failure.InnerException) { break }
            $failure = $failure.InnerException
        }
        $facts['query_failure'] = @{stage=$factStage;failure_code=$code;error_type=(Text-Field $failure.GetType().FullName 256);hresult=[int]$failure.HResult;qpc=(Now);subsequent_facts='NOT_COLLECTED_UNKNOWN_NOT_ZERO'}
    }
    return $facts
}

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT -or [IntPtr]::Size -ne 8) { Fail 'REQUIRES_64BIT_WINDOWS' }
    if ($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1 -or $PSVersionTable.PSEdition -cne 'Desktop') { Fail 'REQUIRES_WINDOWS_POWERSHELL_5_1_DESKTOP' }
    if ($ActivationSha256 -cnotmatch '^[0-9a-f]{64}$') { Fail 'EXACT_ACTIVATION_SHA256_REQUIRED_OWNER_NOT_APPROVED' }
    if ($PolicySha256 -cnotmatch '^[0-9a-f]{64}$') { Fail 'POLICY_NOT_FROZEN' }
    $scriptPath = [IO.Path]::GetFullPath($PSCommandPath)
    if ($scriptPath -match '["\r\n]' -or -not $scriptPath.EndsWith('\scripts\route2_readonly_inventory.ps1', [StringComparison]::OrdinalIgnoreCase)) { Fail 'FIXED_SCRIPT_PATH_REQUIRED' }
    $repoRoot = [IO.Directory]::GetParent([IO.Path]::GetDirectoryName($scriptPath)).FullName
    $receiptPath = [IO.Path]::Combine($repoRoot, 'docs\decisions\2026-09-27-route2-design-review.md')
    $pin = [IO.File]::Open($scriptPath, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    if ($pin.Length -gt 262144) { Fail 'SCRIPT_SOURCE_TOO_LARGE' }
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $sourceSha = ([BitConverter]::ToString($sha.ComputeHash($pin))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
    $document = [Text.UTF8Encoding]::new($false, $true).GetString((Read-Bounded $receiptPath 4194304))
    $begin = '<!-- ROUTE2_H3_READONLY_INVENTORY_ACTIVATION_V1_BEGIN -->'
    $end = '<!-- ROUTE2_H3_READONLY_INVENTORY_ACTIVATION_V1_END -->'
    if (($document.Split([string[]]@($begin), [StringSplitOptions]::None).Length -ne 2) -or ($document.Split([string[]]@($end), [StringSplitOptions]::None).Length -ne 2)) { Fail 'MISSING_OR_DUPLICATE_OWNER_ACTIVATION_BLOCK' }
    $a = $document.IndexOf($begin, [StringComparison]::Ordinal) + $begin.Length
    $z = $document.IndexOf($end, [StringComparison]::Ordinal)
    if ($z -le $a -or ($z - $a) -gt 16388) { Fail 'ACTIVATION_BLOCK_SHAPE' }
    # EXACT bytes are the ASCII JSON between the delimiters, with a single LF on
    # each side. CRLF, padding, alternate key order, unknown keys or dupes refuse.
    $block = $document.Substring($a, $z - $a)
    if (-not $block.StartsWith("`n") -or -not $block.EndsWith("`n") -or $block.Contains("`r")) { Fail 'ACTIVATION_REQUIRES_EXACT_LF_DELIMITED_JSON' }
    $json = $block.Substring(1, $block.Length - 2)
    if ($json.Length -gt 16384 -or $json -cmatch '[^\x20-\x7e]' -or (Sha-Bytes ([Text.Encoding]::ASCII.GetBytes($json))) -cne $ActivationSha256) { Fail 'ACTIVATION_BYTE_BINDING_MISMATCH' }
    $pattern = '^\{"schema":"route2_h3_readonly_inventory_activation_v1","policy_id":"' + [regex]::Escape($PolicyId) + '","source_sha256":"[0-9a-f]{64}","contract_sha256":"[0-9a-f]{64}","owner_message_sha256":"[0-9a-f]{64}","owner_approval_reference":"[A-Za-z0-9:/._-]{1,200}","invocation_nonce":"[0-9a-f]{32}","one_shot_state":"CONSUMED_FOR_THIS_INVOCATION","parent_pid":[1-9][0-9]{0,9},"qpc_epoch":[1-9][0-9]{0,18},"qpc_frequency":[1-9][0-9]{0,9},"active_stop_qpc":[1-9][0-9]{0,18},"cleanup_stop_qpc":[1-9][0-9]{0,18},"active_seconds":120,"cleanup_seconds":60,"total_seconds":180,"max_attempts":1,"exception_ids":"' + [regex]::Escape($ExceptionIds) + '"\}$'
    if ($json -cnotmatch $pattern) { Fail 'ACTIVATION_NONCANONICAL_OR_SCOPE_MISMATCH' }
    $receipt = $json | ConvertFrom-Json
    if ($receipt.source_sha256 -cne $sourceSha -or $receipt.contract_sha256 -cne $PolicySha256) { Fail 'SOURCE_OR_POLICY_HASH_MISMATCH' }
    if ([long]$receipt.qpc_frequency -ne $frequency -or [decimal]$receipt.active_stop_qpc -ne ([decimal]$receipt.qpc_epoch + [decimal]$frequency * 120) -or [decimal]$receipt.cleanup_stop_qpc -ne ([decimal]$receipt.qpc_epoch + [decimal]$frequency * 180)) { Fail 'ORIGINAL_QPC_DEADLINE_BINDING_INVALID' }
    if ([long]$receipt.qpc_epoch -gt $entryQpc -or $entryQpc -ge [long]$receipt.active_stop_qpc) { Fail 'ORIGINAL_EPOCH_NOT_LIVE_AT_ENTRY' }
    $parent = [Diagnostics.Process]::GetCurrentProcess()
    $fixedExe = [IO.Path]::Combine([Environment]::SystemDirectory, 'WindowsPowerShell\v1.0\powershell.exe')
    $fixedModuleRoot = [IO.Path]::Combine([Environment]::SystemDirectory, 'WindowsPowerShell\v1.0\Modules')
    $processImage = Text-Field $parent.MainModule.FileName 1024
    if (-not [string]::Equals($processImage, $fixedExe, [StringComparison]::OrdinalIgnoreCase)) { Fail 'CURRENT_PROCESS_NOT_FIXED_SYSTEM32_WINDOWS_POWERSHELL' }
    if ($InventoryChild) {
        if ($OriginalEpoch -ne [long]$receipt.qpc_epoch -or $OriginalFrequency -ne $frequency -or $ActiveStop -ne [long]$receipt.active_stop_qpc -or $CleanupStop -ne [long]$receipt.cleanup_stop_qpc -or $InvocationNonce -cne $receipt.invocation_nonce) { Fail 'CHILD_ORIGINAL_BINDINGS_MISMATCH' }
        # Startup also receives this fixed value. Reapply in this child before
        # any Storage/CimCmdlets lookup so PowerShell startup path normalization
        # cannot admit inherited user/project module directories. Process only;
        # complete immutable Windows module/loader closure remains unproved H3.
        [Environment]::SetEnvironmentVariable('PSModulePath', $fixedModuleRoot, [EnvironmentVariableTarget]::Process)
        if ([Environment]::GetEnvironmentVariable('PSModulePath', [EnvironmentVariableTarget]::Process) -cne $fixedModuleRoot) { Fail 'FIXED_CHILD_MODULE_PATH_NOT_APPLIED' }
        if ($SharedAffinityMask -le 0 -or ($SharedAffinityMask -band ($SharedAffinityMask - 1)) -eq 0 -or ([Convert]::ToString($SharedAffinityMask, 2).Replace('0', '').Length -ne 2)) { Fail 'CHILD_REQUIRES_EXACTLY_TWO_SHARED_CORES' }
        $parent.ProcessorAffinity = [IntPtr]$SharedAffinityMask
        if ($parent.ProcessorAffinity.ToInt64() -ne $SharedAffinityMask) { Fail 'CHILD_AFFINITY_NOT_APPLIED' }
        $parent.Refresh()
        if ($parent.WorkingSet64 -gt 4294967296 -or $parent.Threads.Count -gt 64) { Fail 'CHILD_INITIAL_RESOURCE_EXCESS' }
        Check-Active
        $phase = 'CHILD_FACT_COLLECTION'
        $childFacts = Collect-Facts
        Write-ChildRecord $childFacts
        Check-Active
        $childCompleted = $true
        $childCollectionComplete = [bool]$childFacts['collection_complete']
    }
    if (-not $InventoryChild) {
    if ($OriginalEpoch -ne 0 -or $OriginalFrequency -ne 0 -or $ActiveStop -ne 0 -or $CleanupStop -ne 0 -or $InvocationNonce.Length -ne 0 -or $SharedAffinityMask -ne 0) { Fail 'PARENT_REJECTS_CHILD_ARGUMENTS' }
    if ([long]$receipt.parent_pid -ne $parent.Id) { Fail 'ACTIVATION_MUST_BIND_THIS_ALREADY_LOADED_PARENT' }
    $OriginalEpoch = [long]$receipt.qpc_epoch
    $OriginalFrequency = $frequency
    $ActiveStop = [long]$receipt.active_stop_qpc
    $CleanupStop = [long]$receipt.cleanup_stop_qpc
    $InvocationNonce = $receipt.invocation_nonce
    Check-Active
    $phase = 'APPROVED_H3_INVENTORY_ATTEMPT_CONSUMED'
    $parentAffinityOriginal = $parent.ProcessorAffinity
    $available = $parentAffinityOriginal.ToInt64()
    $coreBits = New-Object 'System.Collections.Generic.List[long]'
    for ($i = 0; $i -lt 63 -and $coreBits.Count -lt 2; $i++) {
        $bit = [long]1 -shl $i
        if (($available -band $bit) -ne 0) { $coreBits.Add($bit) }
    }
    if ($coreBits.Count -ne 2) { Fail 'TWO_AVAILABLE_SHARED_CORES_REQUIRED' }
    $SharedAffinityMask = $coreBits[0] -bor $coreBits[1]
    $parentCoreMask = $coreBits[0]
    $parent.ProcessorAffinity = [IntPtr]$coreBits[0]
    if ($parent.ProcessorAffinity.ToInt64() -ne $coreBits[0]) { Fail 'PARENT_AFFINITY_NOT_APPLIED' }
    $parent.Refresh()
    if ($parent.WorkingSet64 -gt 536870912 -or $parent.Threads.Count -gt 64) { Fail 'PARENT_PRESTART_RESOURCE_EXCESS' }
    # Preallocate original Process and both raw-byte captures before Start. Never
    # recover/reopen a child using a PID. No shell or caller command/path exists.
    $child = [Diagnostics.Process]::new()
    $outState = New-Capture 65536
    $errState = New-Capture 8192
    $child.StartInfo.FileName = $fixedExe
    $child.StartInfo.UseShellExecute = $false
    $child.StartInfo.CreateNoWindow = $true
    $child.StartInfo.RedirectStandardOutput = $true
    $child.StartInfo.RedirectStandardError = $true
    $child.StartInfo.EnvironmentVariables['PSModulePath'] = $fixedModuleRoot
    $child.StartInfo.WorkingDirectory = $repoRoot
    $child.StartInfo.Arguments = '-NoLogo -NoProfile -NonInteractive -File "' + $scriptPath + '" -InventoryChild -ActivationSha256 ' + $ActivationSha256 + ' -OriginalEpoch ' + $OriginalEpoch.ToString([Globalization.CultureInfo]::InvariantCulture) + ' -OriginalFrequency ' + $frequency.ToString([Globalization.CultureInfo]::InvariantCulture) + ' -ActiveStop ' + $ActiveStop.ToString([Globalization.CultureInfo]::InvariantCulture) + ' -CleanupStop ' + $CleanupStop.ToString([Globalization.CultureInfo]::InvariantCulture) + ' -InvocationNonce ' + $InvocationNonce + ' -SharedAffinityMask ' + $SharedAffinityMask.ToString([Globalization.CultureInfo]::InvariantCulture)
    Check-Active
    $startAttempted = $true
    $childStartCallQpc = Now
    if (-not $child.Start()) { Fail 'CHILD_START_RETURNED_FALSE' }
    $started = $true
    $childStartReturnedQpc = Now
    $child.ProcessorAffinity = [IntPtr]$SharedAffinityMask
    if ($child.ProcessorAffinity.ToInt64() -ne $SharedAffinityMask) { Fail 'CHILD_AFFINITY_NOT_APPLIED' }
    $monitorBaselineQpc = Now
    $lastSampleQpc = $monitorBaselineQpc
    $phase = 'MONITORING_H3_FIXED_CHILD'
    while ($true) {
        Check-Active
        Pump-Capture $outState $child.StandardOutput.BaseStream
        Pump-Capture $errState $child.StandardError.BaseStream
        $parent.Refresh()
        $parentWs = $parent.WorkingSet64
        $parentThreads = $parent.Threads.Count
        $maxParentWs = [Math]::Max([long]$maxParentWs, $parentWs)
        $maxParentThreads = [Math]::Max([int]$maxParentThreads, $parentThreads)
        if ($parentWs -gt 536870912) { $violations.Add('PARENT_WORKING_SET_OVER_512MIB'); Fail 'OBSERVED_RESOURCE_VIOLATION' }
        if ($parentThreads -gt 64) { $violations.Add('PARENT_THREADS_OVER_MONITORED64'); Fail 'OBSERVED_RESOURCE_VIOLATION' }
        if ($parent.ProcessorAffinity.ToInt64() -ne $coreBits[0]) { $violations.Add('PARENT_AFFINITY_DRIFT'); Fail 'OBSERVED_RESOURCE_VIOLATION' }
        $sampleQpc = Now
        if (($sampleQpc - $lastSampleQpc) -gt ([decimal]$frequency / 10)) { $violations.Add('RESOURCE_SAMPLE_STALE_OVER_100MS'); Fail 'OBSERVED_RESOURCE_VIOLATION' }
        if ($child.WaitForExit(1)) {
            $joined = $true
            if ($resourceSamples -eq 0) { $violations.Add('NO_LIVE_CHILD_RESOURCE_SAMPLE'); Fail 'MISSING_CHILD_RESOURCE_SAMPLE' }
            break
        }
        $child.Refresh()
        $childWs = $child.WorkingSet64
        $threads = $parentThreads + $child.Threads.Count
        $maxChildWs = [Math]::Max([long]$maxChildWs, $childWs)
        $maxCombinedWs = [Math]::Max([long]$maxCombinedWs, $parentWs + $childWs)
        $maxThreads = [Math]::Max([int]$maxThreads, $threads)
        $resourceSamples++
        $sampleQpc = Now
        if ($null -eq $firstResourceSampleQpc) { $firstResourceSampleQpc = $sampleQpc }
        if (($sampleQpc - $lastSampleQpc) -gt ([decimal]$frequency / 10)) { $violations.Add('RESOURCE_SAMPLE_STALE_OVER_100MS'); Fail 'OBSERVED_RESOURCE_VIOLATION' }
        $lastSampleQpc = $sampleQpc
        if ($childWs -gt 4294967296 -or ($parentWs + $childWs) -gt 4294967296) { $violations.Add('CHILD_OR_COMBINED_WORKING_SET_OVER_4GIB'); Fail 'OBSERVED_RESOURCE_VIOLATION' }
        if ($threads -gt 64) { $violations.Add('COMBINED_APPLICATION_THREADS_OVER_MONITORED64'); Fail 'OBSERVED_RESOURCE_VIOLATION' }
        if ($child.ProcessorAffinity.ToInt64() -ne $SharedAffinityMask) { $violations.Add('CHILD_AFFINITY_DRIFT'); Fail 'OBSERVED_RESOURCE_VIOLATION' }
        # Finite 20ms polling request; scheduling/provider latency is unproved.
        [Threading.Thread]::Sleep(20)
    }
    $phase = 'CHILD_JOINED_CAPTURE_PENDING'
    }
} catch {
    # Codes only: avoid leaking provider exception text or unselected config data.
    $failure = $_.Exception
    for ($depth = 0; $depth -lt 8; $depth++) {
        if ($failure.Data.Contains('Route2FixedCode')) { $primaryFault = Text-Field $failure.Data['Route2FixedCode'] 128 }
        if ($null -eq $failure.InnerException) { break }
        $failure = $failure.InnerException
    }
    $primaryErrorType = Text-Field $failure.GetType().FullName 256
    $primaryHResult = [int]$failure.HResult
    if ($null -eq $primaryFault) { $primaryFault = 'PARENT_OPERATION_FAILED' }
} finally {
    if (-not $InventoryChild) {
        if ($startAttempted) {
            # A stalled/throwing Start can leave launch identity uncertain. Keep
            # the original object and request termination even if the clock has
            # already expired; report that tail, never call it unbilled cleanup.
            if (-not $joined) {
                $killRequested = $true
                if ((Now) -ge $CleanupStop) { $cleanupFaults.Add('TERMINATION_REQUEST_AFTER_ABSOLUTE_CLEANUP_STOP_UNKNOWN_FEES') }
                try { $child.Kill() } catch { $cleanupFaults.Add('ORIGINAL_PROCESS_KILL_FAULT') }
            }
            $captureEnabled = $started
            $joinUnavailable = $false
            # One original absolute cleanup stop. No per-call timeout epoch reset.
            while ((Now) -lt $CleanupStop) {
                if (-not $joined) {
                    try { $joined = $child.WaitForExit(1) }
                    catch { $cleanupFaults.Add('ORIGINAL_PROCESS_JOIN_FAULT'); $joinUnavailable = $true }
                }
                if ($captureEnabled) {
                    try {
                        Pump-Capture $outState $child.StandardOutput.BaseStream
                        Pump-Capture $errState $child.StandardError.BaseStream
                    } catch {
                        $cleanupFaults.Add('BOUNDED_CAPTURE_CLEANUP_FAULT')
                        $captureEnabled = $false
                    }
                }
                # Join was attempted first. A child may exit during a live
                # sample; that failed observation is recorded, then join resumes.
                Sample-CleanupResources -ParentOnly:$joined
                # Capture failure never abandons an available original join.
                if ($joinUnavailable -or ($joined -and (-not $captureEnabled -or ($outState.Eof -and $errState.Eof)))) { break }
                [Threading.Thread]::Sleep(20)
            }
            if ($joined) {
                try { $exitDword = [BitConverter]::ToUInt32([BitConverter]::GetBytes([int]$child.ExitCode), 0) }
                catch { $cleanupFaults.Add('EXIT_DWORD_UNAVAILABLE') }
                if ($null -ne $exitDword -and $exitDword -ne 0 -and $null -eq $primaryFault) { $primaryFault = 'FIXED_CHILD_NONZERO_EXIT_DWORD' }
            } else { $cleanupFaults.Add('ORIGINAL_CHILD_NOT_JOINED_UNKNOWN_NOT_ZERO') }
            if ($started -and (-not $outState.Eof -or -not $errState.Eof)) { $cleanupFaults.Add('CAPTURE_EOF_NOT_OBSERVED_FOR_BOTH_STREAMS') }
        }
        # Keep the adopted root on its selected single core through serialization
        # and final output. Restoring its wider original mask here would create
        # an unmonitored CPU tail inside this same original H3 attempt.
        if ($null -ne $parent -and $OriginalEpoch -gt 0) {
            # Last bounded parent-only observation before either Process object
            # is disposed. Serialization/flush and provider tails stay unknown.
            Sample-CleanupResources -ParentOnly -Final
        }
    }
    # Closing outstanding pipe reads may abort them; never claim completion or
    # service drain merely because Dispose was called or the child was joined.
    if ($null -ne $child) { try { $child.Dispose() } catch { $cleanupFaults.Add('ORIGINAL_PROCESS_DISPOSE_FAULT') } }
    if ($null -ne $pin) { try { $pin.Dispose() } catch { $cleanupFaults.Add('SCRIPT_PIN_CLOSE_FAULT') } }
    if ($null -ne $parent) { try { $parent.Dispose() } catch { $cleanupFaults.Add('PARENT_METADATA_HANDLE_CLOSE_FAULT') } }
}

if ($InventoryChild) {
    $childLate = ((Now) -ge $ActiveStop)
    if ($childCompleted -and $childCollectionComplete -and $null -eq $primaryFault -and $cleanupFaults.Count -eq 0 -and -not $childLate) { exit 0 }
    $childFault = [ordered]@{schema='route2_h3_fixed_child_failure_v1';primary_fault=$primaryFault;error_type=$primaryErrorType;hresult=$primaryHResult;cleanup_faults=$cleanupFaults.ToArray();record_written=$childCompleted;collection_complete=$childCollectionComplete;active_stop_missed=$childLate}
    $childFaultBytes = [Text.UTF8Encoding]::new($false, $true).GetBytes(($childFault | ConvertTo-Json -Depth 4 -Compress))
    if ($childFaultBytes.Length -le 4096) {
        $childStderr = [Console]::OpenStandardError()
        $childStderr.Write($childFaultBytes, 0, $childFaultBytes.Length)
        $childStderr.Flush()
    } else { [Console]::Error.WriteLine('H3_FIXED_CHILD_REFUSED_OR_FAILED') }
    exit 1
}
$outstanding = @()
if ($null -ne $outState -and $null -ne $outState.Task -and -not $outState.Task.IsCompleted) { $outstanding += 'stdout' }
if ($null -ne $errState -and $null -ne $errState.Task -and -not $errState.Task.IsCompleted) { $outstanding += 'stderr' }
$unharvested = @()
if ($null -ne $outState -and $null -ne $outState.Task) { $unharvested += 'stdout' }
if ($null -ne $errState -and $null -ne $errState.Task) { $unharvested += 'stderr' }
$rawOut = $null
$rawErr = $null
if ($null -ne $outState) { $rawOut = [Convert]::ToBase64String($outState.Buffer, 0, $outState.Used) }
if ($null -ne $errState) { $rawErr = [Convert]::ToBase64String($errState.Buffer, 0, $errState.Used) }
$result = [ordered]@{
    schema='route2_h3_readonly_inventory_result_v1';policy_id=$PolicyId;source_sha256=$sourceSha;contract_sha256=$PolicySha256
    phase=$phase;primary_fault=$primaryFault;primary_error_type=$primaryErrorType;primary_hresult=$primaryHResult;cleanup_faults=$cleanupFaults.ToArray();observed_resource_violations=$violations.ToArray()
    invocation_nonce=$InvocationNonce;original_qpc_epoch=$OriginalEpoch;qpc_frequency=$frequency;active_stop_qpc=$ActiveStop;cleanup_stop_qpc=$CleanupStop;result_qpc=(Now)
    original_child_start_attempted=$startAttempted;original_child_started=$started;original_process_joined=$joined;original_exit_dword=$exitDword;kill_requested=$killRequested;outstanding_read_tasks=$outstanding;unharvested_read_tasks=$unharvested
    stdout_read_state=(Capture-State $outState);stderr_read_state=(Capture-State $errState)
    stdout_base64=$rawOut;stderr_base64=$rawErr;stdout_capacity_bytes=65536;stderr_capacity_bytes=8192;child_record_limit_bytes=32768;parent_record_limit_bytes=65536
    process_image_path_observed=$processImage;process_image_handle_identity='UNPROVEN_SCOPED_H3_EXCEPTION'
    observed_parent_working_set_peak=$maxParentWs;observed_child_working_set_peak=$maxChildWs;observed_combined_working_set_peak=$maxCombinedWs;observed_combined_application_threads_peak=$maxThreads;resource_samples=$resourceSamples;unsampled_resources='UNKNOWN_NOT_ZERO'
    observed_parent_threads_peak=$maxParentThreads;cleanup_live_resource_samples=$cleanupLiveSamples;cleanup_parent_only_samples=$cleanupParentOnlySamples;cleanup_resource_sample_failures=$cleanupSampleFailures;last_cleanup_resource_sample_qpc=$lastCleanupSampleQpc;final_parent_resource_sample_qpc=$finalParentSampleQpc
    child_postexit_resources='UNKNOWN_NOT_ZERO_NOT_QUERIED_AFTER_ORIGINAL_PROCESS_JOIN';post_final_sample_resources='DISPOSAL_SERIALIZATION_FLUSH_KERNEL_SERVICE_PROVIDER_TAILS_UNKNOWN_NOT_ZERO'
    child_start_call_qpc=$childStartCallQpc;child_start_returned_qpc=$childStartReturnedQpc;monitor_cadence_baseline_qpc=$monitorBaselineQpc;first_complete_resource_sample_qpc=$firstResourceSampleQpc
    resource_start_interval='ORIGINAL_EPOCH_THROUGH_FIRST_COMPLETE_SAMPLE_UNOBSERVED_NOT_ZERO_NO_100MS_COVERAGE_CLAIM'
    cpu_scope='AFFINITY_PARENT_ONE_CHILD_TWO_SHARED_CORES_AGGREGATE_200PCT_AFTER_SET_FIRST_LOADER_UNPROVEN'
    parent_affinity_disposition='RETAINED_ONE_CORE_THROUGH_FINAL_OUTPUT'
    thread_scope='H3_MONITORED64_ONLY_ORIGINAL_FORMAL_FOUR_UNCHANGED'
    root_startup_creator_primary_thread_closure='UNPROVEN_SCOPED_H3_EXCEPTION'
    complete_ram_kernel_service_physical_all_fees='UNKNOWN_NOT_ZERO'
    provider_infrastructure='NOT_JOINED_EXITED_PENDING_PROVIDER_UNKNOWN_NOT_ZERO'
    hard_deadline_proof='UNPROVEN_SAMPLED_COOPERATIVE_EXCEPTION_NO_UNBILLED_DRAIN'
    receipt_provenance='TRUSTED_ROOT_ACTUAL_OWNER_MESSAGE_AND_DURABLE_CONSUMPTION_REQUIRED_NOT_AUTHENTICATED_BY_THIS_SCRIPT'
    budget_verdict='UNKNOWN_NOT_ZERO_NEVER_PASS';stage_admission='NOT_GRANTED';disk_plan_target_authority='NOT_GRANTED';h1='APPROVED_UNSTARTED';old_history='UNKNOWN_NOT_ZERO'
    output_time_status='PROVISIONAL_OBSERVATION_REQUIRE_PROCESS_EXIT_STATUS_POST_FLUSH_NOT_IN_RECORD'
}
$result['pre_serialization_qpc'] = Now
$encoded = [Text.UTF8Encoding]::new($false, $true).GetBytes(($result | ConvertTo-Json -Depth 6 -Compress))
$result['post_initial_serialization_qpc'] = Now
$outputLate = ($CleanupStop -gt 0 -and $result['post_initial_serialization_qpc'] -ge $CleanupStop)
$wireShapeFault = $false
$encoded = [Text.UTF8Encoding]::new($false, $true).GetBytes(($result | ConvertTo-Json -Depth 6 -Compress))
if ($encoded.Length -gt 65536) {
    # Fail closed without emitting an oversized record; keep primary/cleanup
    # faults and truthful read states even when the raw captured bytes are omitted.
    $wireShapeFault = $true
    $result['stdout_base64'] = $null
    $result['stderr_base64'] = $null
    $result['output_shape_fault'] = 'RAW_CAPTURE_OMITTED_PARENT_64KIB_WIRE_LIMIT'
    $encoded = [Text.UTF8Encoding]::new($false, $true).GetBytes(($result | ConvertTo-Json -Depth 6 -Compress))
}
if ($encoded.Length -gt 65536) { [Console]::Error.WriteLine('H3_PARENT_RESULT_SHAPE_EXCEEDED'); exit 1 }
$stdout = [Console]::OpenStandardOutput()
if ($CleanupStop -gt 0 -and (Now) -ge $CleanupStop) { $outputLate = $true }
try {
    $stdout.Write($encoded, 0, $encoded.Length)
    $stdout.Flush()
} catch { [Console]::Error.WriteLine('H3_PARENT_OUTPUT_WRITE_OR_FLUSH_FAULT'); exit 1 }
# A printed provisional record never overrides a late flush or serialization.
if ($CleanupStop -gt 0 -and (Now) -ge $CleanupStop) { $outputLate = $true }
if ($outputLate) { [Console]::Error.WriteLine('H3_PARENT_OUTPUT_AFTER_ABSOLUTE_CLEANUP_STOP_UNKNOWN_FEES'); exit 1 }
if ($null -ne $primaryFault -or $cleanupFaults.Count -gt 0 -or -not $joined -or $exitDword -ne 0 -or $unharvested.Count -gt 0 -or $wireShapeFault) { exit 1 }
# Exit zero reports only that this fixed child returned and was joined; every
# budget/admission field above remains explicitly non-passing.
exit 0
