# SOURCE PROPOSAL ONLY: H4 NOT OWNER APPROVED. Bind final v4 policy only.
# No source/receipt/parameters authenticate owner identity or issue authority.
# Exactly one separately approved 120s active +60s cleanup additional attempt;
# H1 APPROVED_UNSTARTED and H3 CONSUMED_FAILED_PARTIAL / NO RETRY unchanged.
# Trusted root must first issue the WHOLE fixed System32 PowerShell launcher
# with -NoProfile -NonInteractive -EncodedCommand and login:false. SAME root
# takes its first QPC before binding/Flush(true) consumption to original3.
# Host preentry creator/waiter/loader/physical/runtime/service tails UNPROVEN,
# all old/new fees UNKNOWN_NOT_ZERO. Process join never means all-service join.
# No complete hard deadlines, causal resources or immutable identity certified.
# API evidence: Context7 /dotnet/docs queried; primary fallback references:
# https://learn.microsoft.com/en-us/dotnet/api/system.io.memorystream.-ctor?view=netframework-4.8.1
# https://learn.microsoft.com/en-us/dotnet/api/system.io.compression.gzipstream?view=netframework-4.8.1
# https://pkware.cachefly.net/webdocs/casestudies/APPNOTE.TXT
# Synthetic harness is SOURCE ONLY / UNRUN; no execution authorized here.
[CmdletBinding()]
param(
    [string] $ActivationSha256 = '',
    [switch] $InspectionChild,
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
$PolicyId = 'route2-h4-official-nongt-inspection-2026-10-16-004'
$PolicySha256 = '695efa21fea9c51652602f898f5da1936810801696e1538139a50e249d327ec2'
$ExceptionIds = 'ADOPT_TOOL_STARTED_POWERSHELL_ROOT_PRELOAD_CREATOR|DOTNET_ORIGINAL_PROCESS_NOT_NATIVE_PI_THREAD_JOIN|H4_MONITORED64_NOT_FORMAL4|H4_SAMPLED_RESOURCES_NOT_COMPLETE_CAUSAL_CAPS|H4_SHARED_RUNTIME_SERVICE_TAIL_UNJOINED|H4_E_NON_E_PHYSICAL_ACCOUNTING_UNPROVEN|H4_HARD_DEADLINE_SYNC_STALL_UNPROVEN|H4_TRUSTED_HOST_ONE_SHOT_NOT_SCRIPT_ANTIREPLAY|H4_ADDITIONAL_ONE180_NOT_H1_OR_H3'
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
    $e = [InvalidOperationException]::new('H4_FIXED_FAILURE')
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
    $encoded=H4-JsonBytes $Value
    if ($encoded.Length -gt 65536) { Fail 'CHILD_RECORD_EXCEEDS_64KIB' }
    $stream=[Console]::OpenStandardOutput()
    $stream.Write($encoded,0,$encoded.Length); $stream.Flush()
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
    if ($Code -match 'OVER_(512MIB|1GIB|MONITORED64)|AFFINITY' -and -not $script:violations.Contains($Code)) { $script:violations.Add($Code) }
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
            if ($childWs -gt 536870912) { Add-CleanupResourceFault 'CLEANUP_CHILD_WORKING_SET_OVER_512MIB' }
            if (($ws + $childWs) -gt 1073741824) { Add-CleanupResourceFault 'CLEANUP_COMBINED_WORKING_SET_OVER_1GIB' }
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
function H4-JsonBytes($Value) {
    return ,([Text.UTF8Encoding]::new($false,$true).GetBytes((ConvertTo-Json -InputObject $Value -Depth 14 -Compress)))
}
function H4-U16([byte[]]$B,[int]$P) {
    if ($P -lt 0 -or $P -gt $B.Length-2) { Fail 'ZIP_U16_RANGE' }
    return [BitConverter]::ToUInt16($B,$P)
}
function H4-U32([byte[]]$B,[int]$P) {
    if ($P -lt 0 -or $P -gt $B.Length-4) { Fail 'ZIP_U32_RANGE' }
    return [BitConverter]::ToUInt32($B,$P)
}
function H4-ReadAt([IO.Stream]$Stream,[long]$Offset,[int]$Count,[string]$Kind='structural',[int]$Ordinal=-1) {
    Check-Active
    if ($Offset -lt 0 -or $Count -lt 0 -or $Offset -gt $Stream.Length - $Count) { Fail 'ZIP_READ_RANGE' }
    if ($Kind -ceq 'structural') {
        if ($script:H4StructuralBytes -gt 16777216-$Count) { Fail 'ZIP_STRUCTURAL_BUDGET' }
        $script:H4StructuralBytes += $Count
    } elseif ($Kind -ceq 'payload') {
        if ($Count -gt 262144 -or $Ordinal -lt 0 -or $script:H4PayloadOrdinals.Count -ge 8) { Fail 'PAYLOAD_READ_SCOPE' }
        $script:H4PayloadOrdinals.Add($Ordinal)
        $readFact=[ordered]@{ordinal=$Ordinal;offset=$Offset;requested_bytes=$Count;returned_bytes=0;completed=$false;failure_partial_bytes='UNKNOWN_IF_READ_THROWS_WITHOUT_COUNT'}
        $script:H4PayloadReads.Add($readFact)
    } else { Fail 'UNKNOWN_READ_CLASS' }
    $buffer=New-Object byte[] $Count
    [void]$Stream.Seek($Offset,[IO.SeekOrigin]::Begin)
    $used=0
    while ($used -lt $Count) {
        Check-Active
        $n=$Stream.Read($buffer,$used,[Math]::Min(4096,$Count-$used))
        if ($n -le 0) { Fail 'ZIP_SHORT_READ' }; $used += $n
        if ($Kind -ceq 'structural') { $script:H4StructuralReturnedBytes += $n }
        else { $readFact.returned_bytes=$used }
    }
    if ($Kind -ceq 'payload') { $readFact.completed=$true; $readFact.failure_partial_bytes='NOT_APPLICABLE_READ_COMPLETED' }
    return ,$buffer
}
function H4-Path([byte[]]$Raw,[int]$Flags) {
    if ($Raw.Length -lt 1 -or $Raw.Length -gt 512) { Fail 'ZIP_NAME_LENGTH' }
    if (($Flags -band 2048) -ne 0) { $name=[Text.UTF8Encoding]::new($false,$true).GetString($Raw) }
    else {
        foreach ($b in $Raw) { if ($b -gt 127) { Fail 'ZIP_LEGACY_NAME_ENCODING' } }
        $name=[Text.Encoding]::ASCII.GetString($Raw)
    }
    if ($name -match '[\\:\x00-\x1f\x7f]' -or $name.StartsWith('/')) { Fail 'ZIP_UNSAFE_PATH' }
    $isDir=$name.EndsWith('/',[StringComparison]::Ordinal)
    $trimmed=$name; if ($isDir) { $trimmed=$name.Substring(0,$name.Length-1) }
    $parts=$trimmed.Split([char]'/')
    if ($parts.Length -gt 16) { Fail 'ZIP_PATH_DEPTH' }
    foreach ($part in $parts) {
        if ($part.Length -eq 0 -or $part.StartsWith('.') -or $part.EndsWith('.') -or $part.EndsWith(' ') -or $part -match '[<>"|?*]') { Fail 'ZIP_UNSAFE_COMPONENT' }
        if ($part -match '^(?i:CON|PRN|AUX|NUL|COM[1-9\u00b9\u00b2\u00b3]|LPT[1-9\u00b9\u00b2\u00b3])(?:[ .]|$)') { Fail 'ZIP_DEVICE_NAME' }
        foreach ($c in $part.ToCharArray()) { if ([char]::IsControl($c) -or [char]::GetUnicodeCategory($c) -eq [Globalization.UnicodeCategory]::Format) { Fail 'ZIP_NAME_CONTROL' } }
    }
    return @{Name=$name;Key=$trimmed.Normalize([Text.NormalizationForm]::FormC);Parts=$parts;Directory=$isDir}
}
function H4-Denied([string[]]$Parts) {
    $deny='gt|groundtruth|ground_truth|label|labels|annotation|annotations|answer|answers|target|targets|train|training|test|validation|dataset|data|sample|samples|sensor|raw|recording'
    $zh=ConvertFrom-Json '["\u771f\u503c","\u6807\u7b7e","\u6807\u6ce8","\u7b54\u6848","\u8bad\u7ec3","\u6d4b\u8bd5","\u9a8c\u8bc1","\u6570\u636e","\u6837\u672c","\u4f20\u611f","\u539f\u59cb","\u5f55\u5236"]'
    foreach ($part in $Parts) {
        # route2-h4-safe-text-v4: fold separator runs for compound deny checks.
        # Both literal and folded forms retain token boundaries. Known GT
        # wrappers cannot disappear before positive filename classification.
        $asciiPart=$part.ToLowerInvariant()
        $foldedPart=[regex]::Replace($asciiPart,'[^a-z0-9]+','_')
        $denyPattern='(^|[^a-z0-9])('+$deny+')($|[^a-z0-9])'
        if ($asciiPart -cmatch $denyPattern -or $foldedPart -cmatch $denyPattern) { return $true }
        # Chinese denial always compares the original component, not its fold.
        foreach ($token in $zh) { if ($part.Contains([string]$token)) { return $true } }
    }
    return $false
}
function H4-Positive([string]$Name,[string]$Wrapper) {
    $parts=$Name.Split([char]'/')
    if (H4-Denied $parts) { return $false }
    if ($Wrapper.Length -gt 0) {
        if ($parts.Length -lt 2 -or $parts[0] -cne $Wrapper) { return $false }
        $parts=$parts[1..($parts.Length-1)]
    }
    if ($parts.Length -gt 2) { return $false }
    foreach ($part in $parts) { if ($part -cmatch '[^\x20-\x7e]') { return $false } }
    if ($parts.Length -eq 2 -and $parts[0].ToLowerInvariant() -cnotmatch '^(doc|docs|rules|spec|schema|evaluation|evaluator)$') { return $false }
    $base=$parts[$parts.Length-1].ToLowerInvariant()
    return ($base -cmatch '^(readme|rules|instructions|task|submission|metric|metrics|scoring)\.(md|txt|rst)$' -or
        $base -cmatch '^(evaluate|evaluation|evaluator|metric|metrics|score|scoring|submission)\.py$' -or
        $base -cmatch '^(schema|input_schema|output_schema|submission_schema)\.json$')
}
function H4-Crc([byte[]]$Bytes) {
    $table=New-Object uint32[] 256
    for ($i=0;$i -lt 256;$i++) {
        [uint64]$v=$i
        for ($j=0;$j -lt 8;$j++) { if (($v -band 1) -ne 0) { $v=($v -shr 1) -bxor [uint64]3988292384 } else { $v=$v -shr 1 } }
        $table[$i]=[uint32]$v
    }
    [uint64]$crc=4294967295
    for ($i=0;$i -lt $Bytes.Length;$i++) {
        if (($i -band 4095) -eq 0) { Check-Active }
        $crc=($crc -shr 8) -bxor [uint64]$table[($crc -bxor $Bytes[$i]) -band 255]
    }
    return [uint32]($crc -bxor [uint64]4294967295)
}
function H4-Preview([byte[]]$Bytes,[int]$Limit) {
    $n=[Math]::Min($Bytes.Length,[Math]::Max(0,$Limit)); $utf8=[Text.UTF8Encoding]::new($false,$true)
    while ($n -gt 0) {
        try { [void]$utf8.GetString($Bytes,0,$n); break } catch [Text.DecoderFallbackException] { $n-- }
    }
    $p=New-Object byte[] $n; [Array]::Copy($Bytes,0,$p,0,$n); return ,$p
}
function H4-Transport($Records,[int]$Ordinal,[byte[]]$Bytes,[uint32]$Crc,[int]$Budget=32768) {
    Check-Active
    $hash=Sha-Bytes $Bytes
    $record=[ordered]@{ordinal=$Ordinal;utf8_bytes=$Bytes.Length;sha256=$hash;zip_crc32=$Crc;full=$true;encoding='identity-base64';payload_base64=[Convert]::ToBase64String($Bytes);status='FULL_SELECTED_TEXT'}
    $trial=@($Records.ToArray())+@($record)
    if ((H4-JsonBytes $trial).Length -le $Budget) { $Records.Add($record); return }
    $remaining=$Budget-(H4-JsonBytes @($Records.ToArray())).Length-512
    $capacity=[Math]::Min(24576,[Math]::Max(0,[int][Math]::Floor($remaining*0.70)))
    $ok=$false; $used=0; $compressed=$null; $mem=$null; $gz=$null
    if ($capacity -gt 0) {
        $compressed=New-Object byte[] $capacity
        try {
            $mem=[IO.MemoryStream]::new($compressed,0,$capacity,$true,$true); $mem.SetLength(0); $mem.Position=0
            $gz=[IO.Compression.GZipStream]::new($mem,[IO.Compression.CompressionMode]::Compress,$true)
            for ($p=0;$p -lt $Bytes.Length;$p+=4096) { Check-Active; $gz.Write($Bytes,$p,[Math]::Min(4096,$Bytes.Length-$p)) }
            $gz.Dispose(); $gz=$null; $used=[int]$mem.Length
            $mem.Dispose(); $mem=$null; $ok=$true
        } catch { $ok=$false }
        finally {
            if ($null -ne $gz) { try { $gz.Dispose() } catch { $ok=$false } }
            if ($null -ne $mem) { try { $mem.Dispose() } catch { $ok=$false } }
        }
    }
    Check-Active
    if ($ok) {
        $record.encoding='gzip-base64'; $record.payload_base64=[Convert]::ToBase64String($compressed,0,$used)
        if ((H4-JsonBytes (@($Records.ToArray())+@($record))).Length -le $Budget) { $Records.Add($record); return }
    }
    $record.full=$false; $record.encoding='identity-base64'; $record.status='EVIDENCE_TRANSPORT_UNRESOLVED'
    $limit=4096
    while ($true) {
        $preview=H4-Preview $Bytes $limit; $record.payload_base64=[Convert]::ToBase64String($preview)
        if ((H4-JsonBytes (@($Records.ToArray())+@($record))).Length -le $Budget) { $Records.Add($record); return }
        if ($limit -eq 0) { Fail 'DOCUMENT_TRANSPORT_HEADER_BUDGET' }; $limit=[int][Math]::Floor($limit/2)
    }
}
function H4-Inspect([IO.Stream]$Stream) {
    $script:H4StructuralBytes=[long]0
    $script:H4StructuralReturnedBytes=[long]0
    $script:H4PayloadOrdinals=New-Object 'System.Collections.Generic.List[int]'
    $script:H4PayloadReads=New-Object 'System.Collections.Generic.List[object]'
    $facts=[ordered]@{schema='route2_h4_official_nongt_inspection_facts_v1';metadata_complete=$false;collection_complete=$false;archive_sha256='UNVERIFIED';immutable_identity='PATH_VS_HANDLE_AND_COMPLETE_IMMUTABLE_IDENTITY_UNPROVEN';central_sha256=$null;entry_count=0;categories=@{directory=0;denied=0;other=0;candidate=0};candidates=@();documents=@();payload_ordinals=@();evidence_transport_complete=$false;status='READING_STRUCTURAL_CANDIDATES';structural_semantic_proof='NOT_PROVEN_BEFORE_READ_MAX16MIB_RAW_CANDIDATES';stage_admission='NOT_GRANTED';compatibility_conclusion='NOT_ESTABLISHED'}
    $script:H4Facts=$facts
    $length=$Stream.Length; $facts['archive_length_observed']=$length
    if ($length -lt 22) { Fail 'ZIP_TOO_SHORT' }
    $end=H4-ReadAt $Stream ($length-22) 22
    if ((H4-U32 $end 0) -ne 101010256 -or (H4-U16 $end 20) -ne 0) { Fail 'ZIP_EOCD_OR_COMMENT_UNSUPPORTED' }
    $count=[int](H4-U16 $end 10); $centralSize=[long](H4-U32 $end 12); $centralOffset=[long](H4-U32 $end 16)
    if ((H4-U16 $end 4) -ne 0 -or (H4-U16 $end 6) -ne 0 -or (H4-U16 $end 8) -ne $count) { Fail 'ZIP_MULTIDISK_UNSUPPORTED' }
    if ($count -eq 65535 -or $centralSize -eq 4294967295 -or $centralOffset -eq 4294967295) { Fail 'ZIP64_UNSUPPORTED' }
    if ($centralSize -gt 8388608 -or $centralOffset+$centralSize -ne $length-22) { Fail 'ZIP_CENTRAL_RANGE_OR_LIMIT' }
    $central=H4-ReadAt $Stream $centralOffset ([int]$centralSize)
    $facts.central_sha256=Sha-Bytes $central; $facts.entry_count=$count
    # Compact finite per-entry state: offsets/ranges and normalized duplicate
    # keys, never a PowerShell record object for every sensor/sample member.
    $positions=New-Object int[] $count; $starts=New-Object long[] $count; $ends=New-Object long[] $count
    $keys=New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    $fileKeys=New-Object 'System.Collections.Generic.HashSet[string]' ([StringComparer]::OrdinalIgnoreCase)
    $common=$null; $wrapperPossible=$true; $p=0
    for ($i=0;$i -lt $count;$i++) {
        Check-Active; $positions[$i]=$p
        if ($p -gt $central.Length-46 -or (H4-U32 $central $p) -ne 33639248) { Fail 'ZIP_CENTRAL_HEADER' }
        $made=H4-U16 $central ($p+4); $needed=H4-U16 $central ($p+6); $flags=H4-U16 $central ($p+8); $method=H4-U16 $central ($p+10)
        $cs=[long](H4-U32 $central ($p+20)); $us=[long](H4-U32 $central ($p+24)); $nl=[int](H4-U16 $central ($p+28)); $xl=[int](H4-U16 $central ($p+30)); $cl=[int](H4-U16 $central ($p+32)); $local=[long](H4-U32 $central ($p+42))
        if ($needed -gt 20 -or ($made -shr 8) -notin @(0,3) -or ($flags -band 63481) -ne 0 -or $method -notin @(0,8) -or ($method -eq 0 -and ($flags -band 6) -ne 0)) { Fail 'ZIP_FLAGS_VERSION_METHOD_UNSUPPORTED' }
        if ($cs -eq 4294967295 -or $us -eq 4294967295 -or $local -eq 4294967295 -or (H4-U16 $central ($p+34)) -ne 0) { Fail 'ZIP64_OR_DISK_UNSUPPORTED' }
        # Deliberately minimal extra profile: all extra records unsupported.
        # Do not guess timestamp/Unicode/ZIP64/vendor extra interpretations.
        if ($xl -ne 0 -or $nl -lt 1 -or $nl -gt 512 -or $p+46+$nl+$xl+$cl -gt $central.Length) { Fail 'ZIP_NAME_EXTRA_OR_RECORD_RANGE' }
        $raw=New-Object byte[] $nl; [Array]::Copy($central,$p+46,$raw,0,$nl)
        $path=H4-Path $raw $flags
        if (-not $keys.Add($path.Key)) { Fail 'ZIP_DUPLICATE_NORMALIZED_OR_CASE_ALIAS' }
        $attrs=[long](H4-U32 $central ($p+38)); $mode=($attrs -shr 16) -band 61440
        if (($attrs -band 1024) -ne 0 -or $mode -notin @(0,16384,32768) -or ($mode -eq 16384 -and -not $path.Directory) -or ($mode -eq 32768 -and $path.Directory) -or (($attrs -band 16) -ne 0 -and -not $path.Directory)) { Fail 'ZIP_SPECIAL_OR_CONFLICTING_ATTRIBUTES' }
        if ($path.Directory) { if ($cs -ne 0 -or $us -ne 0) { Fail 'ZIP_DIRECTORY_PAYLOAD' }; $facts.categories.directory++ }
        else {
            [void]$fileKeys.Add($path.Key)
            if ($path.Parts.Length -lt 2) { $wrapperPossible=$false }
            elseif ($null -eq $common) { $common=$path.Parts[0] }
            elseif ($common -cne $path.Parts[0]) { $wrapperPossible=$false }
        }
        # Local headers are raw structural candidates even for denied members;
        # their compressed contents are never read here.
        $lh=H4-ReadAt $Stream $local 30
        if ((H4-U32 $lh 0) -ne 67324752 -or (H4-U16 $lh 4) -ne $needed -or (H4-U16 $lh 6) -ne $flags -or (H4-U16 $lh 8) -ne $method -or (H4-U32 $lh 14) -ne (H4-U32 $central ($p+16)) -or (H4-U32 $lh 18) -ne $cs -or (H4-U32 $lh 22) -ne $us -or (H4-U16 $lh 26) -ne $nl -or (H4-U16 $lh 28) -ne 0) { Fail 'ZIP_LOCAL_CENTRAL_BINDING' }
        $localRaw=H4-ReadAt $Stream ($local+30) $nl
        for ($j=0;$j -lt $nl;$j++) { if ($raw[$j] -ne $localRaw[$j]) { Fail 'ZIP_LOCAL_RAW_NAME_MISMATCH' } }
        $starts[$i]=$local; $ends[$i]=$local+30+$nl+$cs
        if ($ends[$i] -gt $centralOffset) { Fail 'ZIP_LOCAL_PAYLOAD_RANGE' }
        $p+=46+$nl+$xl+$cl
    }
    if ($p -ne $central.Length) { Fail 'ZIP_CENTRAL_COUNT_OR_TRAILER' }
    [Array]::Sort($starts,$ends)
    $expected=[long]0
    for ($i=0;$i -lt $count;$i++) { if ($starts[$i] -ne $expected -or $ends[$i] -lt $starts[$i]) { Fail 'ZIP_OVERLAP_ALIAS_OR_UNCLAIMED_GAP' }; $expected=$ends[$i] }
    if ($expected -ne $centralOffset) { Fail 'ZIP_UNCLAIMED_PREFIX_OR_TAIL' }
    foreach ($key in $keys) {
        Check-Active; $slash=$key.IndexOf('/')
        while ($slash -ge 0) { if ($fileKeys.Contains($key.Substring(0,$slash))) { Fail 'ZIP_FILE_DIRECTORY_ALIAS' }; $slash=$key.IndexOf('/',$slash+1) }
    }
    $wrapper=''; if ($wrapperPossible -and $null -ne $common) { $wrapper=$common }
    $candidates=New-Object 'System.Collections.Generic.List[object]'
    for ($i=0;$i -lt $count;$i++) {
        Check-Active; $p=$positions[$i]; $nl=[int](H4-U16 $central ($p+28)); $raw=New-Object byte[] $nl; [Array]::Copy($central,$p+46,$raw,0,$nl)
        $path=H4-Path $raw (H4-U16 $central ($p+8))
        if ($path.Directory) { continue }
        if (H4-Denied $path.Parts) { $facts.categories.denied++; continue }
        if (-not (H4-Positive $path.Name $wrapper)) { $facts.categories.other++; continue }
        $facts.categories.candidate++
        if ($candidates.Count -ge 32) { Fail 'CANDIDATE_COUNT_LIMIT' }
        $candidate=[ordered]@{ordinal=$i;path_utf8_base64=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($path.Name));method=[int](H4-U16 $central ($p+10));compressed_bytes=[long](H4-U32 $central ($p+20));uncompressed_bytes=[long](H4-U32 $central ($p+24));zip_crc32=[uint32](H4-U32 $central ($p+16))}
        if ((H4-JsonBytes (@($candidates.ToArray())+@($candidate))).Length -gt 16384) { Fail 'CANDIDATE_METADATA_LIMIT' }
        $candidates.Add($candidate)
    }
    $facts.candidates=@($candidates.ToArray()); $facts.metadata_complete=$true
    $facts['structural_candidate_bytes_charged']=$script:H4StructuralBytes
    $facts['structural_read_returned_bytes']=$script:H4StructuralReturnedBytes
    if ($candidates.Count -eq 0 -or $candidates.Count -gt 8) { $facts.status='METADATA_COMPLETE_DOCUMENT_SELECTION_UNRESOLVED'; $facts.collection_complete=$true; return $facts }
    [long]$sumC=0; [long]$sumU=0
    foreach ($candidate in $candidates) {
        $cs=$candidate.compressed_bytes; $us=$candidate.uncompressed_bytes
        if ($cs -gt 262144 -or $us -gt 262144 -or ($cs -eq 0 -and $us -gt 0) -or ($cs -gt 0 -and $us -gt 20*$cs) -or ($candidate.method -eq 0 -and $cs -ne $us)) { Fail 'TEXT_MEMBER_SIZE_OR_RATIO' }
        $sumC+=$cs; $sumU+=$us
    }
    if ($sumC -gt 1048576 -or $sumU -gt 1048576) { Fail 'TEXT_AGGREGATE_LIMIT' }
    $documents=New-Object 'System.Collections.Generic.List[object]'
    foreach ($candidate in $candidates) {
        Check-Active; $i=$candidate.ordinal; $p=$positions[$i]; $nl=[int](H4-U16 $central ($p+28)); $local=[long](H4-U32 $central ($p+42))
        $packed=H4-ReadAt $Stream ($local+30+$nl) ([int]$candidate.compressed_bytes) 'payload' $i
        $textBytes=$packed
        if ($candidate.method -eq 8) {
            $input=[IO.MemoryStream]::new($packed,$false); $inflate=$null
            try {
                $inflate=[IO.Compression.DeflateStream]::new($input,[IO.Compression.CompressionMode]::Decompress,$true)
                $textBytes=New-Object byte[] ([int]$candidate.uncompressed_bytes)
                $used=0
                while ($used -lt $textBytes.Length) { Check-Active; $n=$inflate.Read($textBytes,$used,[Math]::Min(4096,$textBytes.Length-$used)); if ($n -le 0) { Fail 'DEFLATE_SHORT_OUTPUT' }; $used+=$n }
                if ($inflate.ReadByte() -ne -1) { Fail 'DEFLATE_EXCESS_OUTPUT' }
            } finally { if ($null -ne $inflate) { $inflate.Dispose() }; $input.Dispose() }
        }
        if ($textBytes.Length -ne $candidate.uncompressed_bytes -or (H4-Crc $textBytes) -ne $candidate.zip_crc32) { Fail 'TEXT_LENGTH_OR_CRC' }
        $text=[Text.UTF8Encoding]::new($false,$true).GetString($textBytes)
        if ($text.Length -gt 0 -and $text[0] -eq [char]65279) { $text=$text.Substring(1) }
        if ($text -match '[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]') { Fail 'TEXT_BINARY_CONTROL' }
        for ($j=0;$j -lt $text.Length;$j++) {
            if (($j -band 4095) -eq 0) { Check-Active }
            if ([char]::IsControl($text[$j]) -and [int]$text[$j] -notin @(9,10,13)) { Fail 'TEXT_BINARY_CONTROL' }
        }
        H4-Transport $documents $i $textBytes $candidate.zip_crc32
        $facts.documents=@($documents.ToArray()); $facts.payload_ordinals=@($script:H4PayloadOrdinals.ToArray()); $facts['payload_reads']=@($script:H4PayloadReads.ToArray())
    }
    if ($Stream.Length -ne $length) { Fail 'ARCHIVE_LENGTH_CHANGED' }
    $facts.evidence_transport_complete=(@($documents.ToArray() | Where-Object { -not $_.full }).Count -eq 0)
    $facts.status='SELECTED_TEXT_EVIDENCE_COMPLETE'; if (-not $facts.evidence_transport_complete) { $facts.status='EVIDENCE_TRANSPORT_UNRESOLVED' }
    $facts.collection_complete=$true
    return $facts
}
function Collect-Inspection {
    $script:H4Facts=[ordered]@{schema='route2_h4_official_nongt_inspection_facts_v1';collection_complete=$false;metadata_complete=$false;archive_sha256='UNVERIFIED';status='ARCHIVE_NOT_OPENED'}
    $script:H4StructuralBytes=[long]0
    $script:H4StructuralReturnedBytes=[long]0
    $script:H4PayloadOrdinals=New-Object 'System.Collections.Generic.List[int]'
    $script:H4PayloadReads=New-Object 'System.Collections.Generic.List[object]'
    $stream=$null; $length=$null
    try {
        Check-Active
        # This is the ONLY archive open site. No existence query, fallback path,
        # whole-file hash, extraction, package import or execution exists.
        $fixedInput=ConvertFrom-Json '"E:/e091f6df5b8f4fd1a62a5e43dda404b1_\u8d5b\u98982.zip"'
        # Buffer size1 suppresses FileStream application read-ahead; kernel/cache
        # physical activity remains outside the proved scope of this exception.
        $stream=[IO.FileStream]::new($fixedInput,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read,1,[IO.FileOptions]::RandomAccess)
        $length=$stream.Length
        $facts=H4-Inspect $stream
        if ($stream.Length -ne $length) { Fail 'ARCHIVE_LENGTH_CHANGED' }
        $script:H4Facts=$facts
    } catch {
        $failure=$_.Exception; $code='INSPECTION_OPERATION_FAILED'
        for ($d=0;$d -lt 8;$d++) { if ($failure.Data.Contains('Route2FixedCode')) { $code=[string]$failure.Data['Route2FixedCode'] }; if ($null -eq $failure.InnerException) { break }; $failure=$failure.InnerException }
        $script:H4Facts.collection_complete=$false
        $script:H4Facts['failure']=@{code=$code;error_type=$failure.GetType().FullName;hresult=[int]$failure.HResult;qpc=(Now)}
    } finally {
        # Actual attempted read scope survives a later decoding/hash/transport
        # failure; never silently omit the last partially inspected member.
        $script:H4Facts['structural_candidate_bytes_charged']=$script:H4StructuralBytes
        $script:H4Facts['structural_read_returned_bytes']=$script:H4StructuralReturnedBytes
        $script:H4Facts['payload_ordinals']=@($script:H4PayloadOrdinals.ToArray())
        $script:H4Facts['payload_reads']=@($script:H4PayloadReads.ToArray())
        if ($null -ne $stream) {
            try { if ($stream.Length -ne $length) { $script:H4Facts.collection_complete=$false; $script:H4Facts['length_changed_on_close']=$true } }
            catch { $script:H4Facts.collection_complete=$false; $script:H4Facts['final_length_check_failed']=$true }
            try { $stream.Dispose() } catch { $script:H4Facts.collection_complete=$false; $script:H4Facts['archive_close_failed']=$true }
        }
    }
    return $script:H4Facts
}

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT -or [IntPtr]::Size -ne 8) { Fail 'REQUIRES_64BIT_WINDOWS' }
    if ($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1 -or $PSVersionTable.PSEdition -cne 'Desktop') { Fail 'REQUIRES_WINDOWS_POWERSHELL_5_1_DESKTOP' }
    if ($ActivationSha256 -cnotmatch '^[0-9a-f]{64}$') { Fail 'EXACT_ACTIVATION_SHA256_REQUIRED_OWNER_NOT_APPROVED' }
    if ($PolicySha256 -cnotmatch '^[0-9a-f]{64}$') { Fail 'POLICY_NOT_FROZEN' }
    $scriptPath = [IO.Path]::GetFullPath($PSCommandPath)
    $expectedScript='E:\bme_compitition\.worktrees\high-f1-event-stack-execution\bme_compitition_next\scripts\route2_official_package_inspection.ps1'
    if ($scriptPath -match '["\r\n]' -or -not [string]::Equals($scriptPath,$expectedScript,[StringComparison]::OrdinalIgnoreCase)) { Fail 'FIXED_SCRIPT_PATH_REQUIRED' }
    $repoRoot = [IO.Directory]::GetParent([IO.Path]::GetDirectoryName($scriptPath)).FullName
    $receiptPath = [IO.Path]::Combine($repoRoot, 'docs\decisions\2026-09-27-route2-design-review.md')
    $pin = [IO.File]::Open($scriptPath, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    if ($pin.Length -gt 262144) { Fail 'SCRIPT_SOURCE_TOO_LARGE' }
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $sourceSha = ([BitConverter]::ToString($sha.ComputeHash($pin))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
    $document = [Text.UTF8Encoding]::new($false, $true).GetString((Read-Bounded $receiptPath 4194304))
    $policyLines=[regex]::Matches($document,'(?m)^\{"schema":"route2_h4_official_nongt_inspection_policy_v4",[^\r\n]*\}')
    if ($policyLines.Count -ne 1 -or $policyLines[0].Value.Length -ne 10307 -or $policyLines[0].Value -cmatch '[^\x20-\x7e]' -or (Sha-Bytes ([Text.Encoding]::ASCII.GetBytes($policyLines[0].Value))) -cne $PolicySha256) { Fail 'EXACT_V4_CANONICAL_POLICY_REQUIRED' }
    $begin = '<!-- ROUTE2_H4_OFFICIAL_NONGT_INSPECTION_ACTIVATION_V1_BEGIN -->'
    $end = '<!-- ROUTE2_H4_OFFICIAL_NONGT_INSPECTION_ACTIVATION_V1_END -->'
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
    $pattern = '^\{"schema":"route2_h4_official_nongt_inspection_activation_v1","policy_id":"' + [regex]::Escape($PolicyId) + '","source_sha256":"[0-9a-f]{64}","contract_sha256":"[0-9a-f]{64}","owner_message_sha256":"[0-9a-f]{64}","owner_approval_reference":"[A-Za-z0-9:/._-]{1,200}","invocation_nonce":"[0-9a-f]{32}","one_shot_state":"CONSUMED_FOR_THIS_INVOCATION","parent_pid":[1-9][0-9]{0,9},"qpc_epoch":[1-9][0-9]{0,18},"qpc_frequency":[1-9][0-9]{0,9},"active_stop_qpc":[1-9][0-9]{0,18},"cleanup_stop_qpc":[1-9][0-9]{0,18},"active_seconds":120,"cleanup_seconds":60,"total_seconds":180,"max_attempts":1,"exception_ids":"' + [regex]::Escape($ExceptionIds) + '"\}$'
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
    if ($InspectionChild) {
        # Caller parameters only bind this fixed child's original receipt.
        # They never authenticate an owner or prove native parent/child lineage;
        # trusted-host serialization and original .NET Process are the scoped
        # exception, not a CLI-issued approval or independent creator proof.
        if ($OriginalEpoch -ne [long]$receipt.qpc_epoch -or $OriginalFrequency -ne $frequency -or $ActiveStop -ne [long]$receipt.active_stop_qpc -or $CleanupStop -ne [long]$receipt.cleanup_stop_qpc -or $InvocationNonce -cne $receipt.invocation_nonce) { Fail 'CHILD_ORIGINAL_BINDINGS_MISMATCH' }
        # Startup also receives this fixed value. Reapply before archive work
        # so startup normalization cannot admit inherited user/project module
        # directories. No Storage/CIM/provider query belongs to this script.
        # complete immutable Windows module/loader closure remains unproved H4.
        [Environment]::SetEnvironmentVariable('PSModulePath', $fixedModuleRoot, [EnvironmentVariableTarget]::Process)
        if ([Environment]::GetEnvironmentVariable('PSModulePath', [EnvironmentVariableTarget]::Process) -cne $fixedModuleRoot) { Fail 'FIXED_CHILD_MODULE_PATH_NOT_APPLIED' }
        if ($SharedAffinityMask -le 0 -or ($SharedAffinityMask -band ($SharedAffinityMask - 1)) -ne 0 -or ([Convert]::ToString($SharedAffinityMask, 2).Replace('0', '').Length -ne 1)) { Fail 'CHILD_REQUIRES_EXACTLY_ONE_SHARED_CORE' }
        $parent.ProcessorAffinity = [IntPtr]$SharedAffinityMask
        if ($parent.ProcessorAffinity.ToInt64() -ne $SharedAffinityMask) { Fail 'CHILD_AFFINITY_NOT_APPLIED' }
        $parent.Refresh()
        if ($parent.WorkingSet64 -gt 536870912 -or $parent.Threads.Count -gt 64) { Fail 'CHILD_INITIAL_RESOURCE_EXCESS' }
        Check-Active
        $phase = 'CHILD_FACT_COLLECTION'
        $childFacts = Collect-Inspection
        Write-ChildRecord $childFacts
        Check-Active
        $childCompleted = $true
        $childCollectionComplete = [bool]$childFacts['collection_complete']
    }
    if (-not $InspectionChild) {
    if ($OriginalEpoch -ne 0 -or $OriginalFrequency -ne 0 -or $ActiveStop -ne 0 -or $CleanupStop -ne 0 -or $InvocationNonce.Length -ne 0 -or $SharedAffinityMask -ne 0) { Fail 'PARENT_REJECTS_CHILD_ARGUMENTS' }
    if ([long]$receipt.parent_pid -ne $parent.Id) { Fail 'ACTIVATION_MUST_BIND_THIS_ALREADY_LOADED_PARENT' }
    $OriginalEpoch = [long]$receipt.qpc_epoch
    $OriginalFrequency = $frequency
    $ActiveStop = [long]$receipt.active_stop_qpc
    $CleanupStop = [long]$receipt.cleanup_stop_qpc
    $InvocationNonce = $receipt.invocation_nonce
    Check-Active
    $phase = 'APPROVED_H4_OFFICIAL_INSPECTION_ATTEMPT_CONSUMED'
    $parentAffinityOriginal = $parent.ProcessorAffinity
    $available = $parentAffinityOriginal.ToInt64()
    $coreBits = New-Object 'System.Collections.Generic.List[long]'
    for ($i = 0; $i -lt 63 -and $coreBits.Count -lt 1; $i++) {
        $bit = [long]1 -shl $i
        if (($available -band $bit) -ne 0) { $coreBits.Add($bit) }
    }
    if ($coreBits.Count -ne 1) { Fail 'ONE_AVAILABLE_SHARED_CORE_REQUIRED' }
    $SharedAffinityMask = $coreBits[0]
    $parentCoreMask = $coreBits[0]
    $parent.ProcessorAffinity = [IntPtr]$coreBits[0]
    if ($parent.ProcessorAffinity.ToInt64() -ne $coreBits[0]) { Fail 'PARENT_AFFINITY_NOT_APPLIED' }
    $parent.Refresh()
    if ($parent.WorkingSet64 -gt 536870912 -or $parent.Threads.Count -gt 64) { Fail 'PARENT_PRESTART_RESOURCE_EXCESS' }
    # Preallocate original Process and both raw-byte captures before Start. Never
    # recover/reopen a child using a PID. No shell or caller command/path exists.
    $child = [Diagnostics.Process]::new()
    $outState = New-Capture 65537
    $errState = New-Capture 8193
    $child.StartInfo.FileName = $fixedExe
    $child.StartInfo.UseShellExecute = $false
    $child.StartInfo.CreateNoWindow = $true
    $child.StartInfo.RedirectStandardOutput = $true
    $child.StartInfo.RedirectStandardError = $true
    $child.StartInfo.EnvironmentVariables['PSModulePath'] = $fixedModuleRoot
    $child.StartInfo.WorkingDirectory = $repoRoot
    $child.StartInfo.Arguments = '-NoLogo -NoProfile -NonInteractive -File "' + $scriptPath + '" -InspectionChild -ActivationSha256 ' + $ActivationSha256 + ' -OriginalEpoch ' + $OriginalEpoch.ToString([Globalization.CultureInfo]::InvariantCulture) + ' -OriginalFrequency ' + $frequency.ToString([Globalization.CultureInfo]::InvariantCulture) + ' -ActiveStop ' + $ActiveStop.ToString([Globalization.CultureInfo]::InvariantCulture) + ' -CleanupStop ' + $CleanupStop.ToString([Globalization.CultureInfo]::InvariantCulture) + ' -InvocationNonce ' + $InvocationNonce + ' -SharedAffinityMask ' + $SharedAffinityMask.ToString([Globalization.CultureInfo]::InvariantCulture)
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
    $phase = 'MONITORING_H4_FIXED_CHILD'
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
        if ($childWs -gt 536870912) { $violations.Add('CHILD_WORKING_SET_OVER_512MIB'); Fail 'OBSERVED_RESOURCE_VIOLATION' }
        if (($parentWs + $childWs) -gt 1073741824) { $violations.Add('COMBINED_WORKING_SET_OVER_1GIB'); Fail 'OBSERVED_RESOURCE_VIOLATION' }
        if ($threads -gt 64) { $violations.Add('COMBINED_APPLICATION_THREADS_OVER_MONITORED64'); Fail 'OBSERVED_RESOURCE_VIOLATION' }
        if ($child.ProcessorAffinity.ToInt64() -ne $SharedAffinityMask) { $violations.Add('CHILD_AFFINITY_DRIFT'); Fail 'OBSERVED_RESOURCE_VIOLATION' }
        # Finite 20ms polling request; scheduling/provider latency is unproved.
        [Threading.Thread]::Sleep(20)
    }
    $phase = 'CHILD_JOINED_CAPTURE_PENDING'
    }
} catch {
    # Codes only: never leak exception text or unselected package members.
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
    if (-not $InspectionChild) {
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
        # an unmonitored CPU tail inside this same original H4 attempt.
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

if ($InspectionChild) {
    $childLate = ((Now) -ge $ActiveStop)
    if ($childCompleted -and $childCollectionComplete -and $null -eq $primaryFault -and $cleanupFaults.Count -eq 0 -and -not $childLate) { exit 0 }
    $childFault = [ordered]@{schema='route2_h4_fixed_child_failure_v1';primary_fault=$primaryFault;error_type=$primaryErrorType;hresult=$primaryHResult;cleanup_faults=$cleanupFaults.ToArray();record_written=$childCompleted;collection_complete=$childCollectionComplete;active_stop_missed=$childLate}
    $childFaultBytes = [Text.UTF8Encoding]::new($false, $true).GetBytes(($childFault | ConvertTo-Json -Depth 4 -Compress))
    if ($childFaultBytes.Length -le 4096) {
        $childStderr = [Console]::OpenStandardError()
        $childStderr.Write($childFaultBytes, 0, $childFaultBytes.Length)
        $childStderr.Flush()
    } else { [Console]::Error.WriteLine('H4_FIXED_CHILD_REFUSED_OR_FAILED') }
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
    schema='route2_h4_official_nongt_inspection_result_v1';policy_id=$PolicyId;source_sha256=$sourceSha;contract_sha256=$PolicySha256
    phase=$phase;primary_fault=$primaryFault;primary_error_type=$primaryErrorType;primary_hresult=$primaryHResult;cleanup_faults=$cleanupFaults.ToArray();observed_resource_violations=$violations.ToArray()
    invocation_nonce=$InvocationNonce;original_qpc_epoch=$OriginalEpoch;qpc_frequency=$frequency;active_stop_qpc=$ActiveStop;cleanup_stop_qpc=$CleanupStop;result_qpc=(Now)
    original_child_start_attempted=$startAttempted;original_child_started=$started;original_process_joined=$joined;original_exit_dword=$exitDword;kill_requested=$killRequested;outstanding_read_tasks=$outstanding;unharvested_read_tasks=$unharvested
    stdout_read_state=(Capture-State $outState);stderr_read_state=(Capture-State $errState)
    stdout_base64=$rawOut;stderr_base64=$rawErr;stdout_capacity_bytes=65537;stderr_capacity_bytes=8193;child_record_limit_bytes=65536;parent_record_limit_bytes=131072
    process_image_path_observed=$processImage;process_image_handle_identity='UNPROVEN_SCOPED_H4_EXCEPTION'
    observed_parent_working_set_peak=$maxParentWs;observed_child_working_set_peak=$maxChildWs;observed_combined_working_set_peak=$maxCombinedWs;observed_combined_application_threads_peak=$maxThreads;resource_samples=$resourceSamples;unsampled_resources='UNKNOWN_NOT_ZERO'
    observed_parent_threads_peak=$maxParentThreads;cleanup_live_resource_samples=$cleanupLiveSamples;cleanup_parent_only_samples=$cleanupParentOnlySamples;cleanup_resource_sample_failures=$cleanupSampleFailures;last_cleanup_resource_sample_qpc=$lastCleanupSampleQpc;final_parent_resource_sample_qpc=$finalParentSampleQpc
    child_postexit_resources='UNKNOWN_NOT_ZERO_NOT_QUERIED_AFTER_ORIGINAL_PROCESS_JOIN';post_final_sample_resources='DISPOSAL_SERIALIZATION_FLUSH_KERNEL_SERVICE_PROVIDER_TAILS_UNKNOWN_NOT_ZERO'
    child_start_call_qpc=$childStartCallQpc;child_start_returned_qpc=$childStartReturnedQpc;monitor_cadence_baseline_qpc=$monitorBaselineQpc;first_complete_resource_sample_qpc=$firstResourceSampleQpc
    resource_start_interval='ORIGINAL_EPOCH_THROUGH_FIRST_COMPLETE_SAMPLE_UNOBSERVED_NOT_ZERO_NO_100MS_COVERAGE_CLAIM'
    cpu_scope='AFFINITY_PARENT_CHILD_SAME_ONE_CORE_AFTER_SET_FIRST_LOADER_UNPROVEN'
    parent_affinity_disposition='RETAINED_ONE_CORE_THROUGH_FINAL_OUTPUT'
    thread_scope='H4_MONITORED64_ONLY_ORIGINAL_FORMAL_FOUR_UNCHANGED'
    root_startup_creator_primary_thread_closure='UNPROVEN_SCOPED_H4_EXCEPTION'
    complete_ram_kernel_service_physical_all_fees='UNKNOWN_NOT_ZERO'
    runtime_service_infrastructure='NOT_JOINED_EXITED_SHARED_RUNTIME_SERVICE_TAIL_UNKNOWN_NOT_ZERO'
    hard_deadline_proof='UNPROVEN_SAMPLED_COOPERATIVE_EXCEPTION_NO_UNBILLED_DRAIN'
    receipt_provenance='TRUSTED_ROOT_ACTUAL_OWNER_MESSAGE_AND_DURABLE_CONSUMPTION_REQUIRED_NOT_AUTHENTICATED_BY_THIS_SCRIPT'
    budget_verdict='UNKNOWN_NOT_ZERO_NEVER_PASS';stage_admission='NOT_GRANTED';disk_plan_target_authority='NOT_GRANTED';h1='APPROVED_UNSTARTED';h3='CONSUMED_FAILED_PARTIAL_NO_RETRY';old_history='UNKNOWN_NOT_ZERO'
    output_time_status='PROVISIONAL_OBSERVATION_REQUIRE_PROCESS_EXIT_STATUS_POST_FLUSH_NOT_IN_RECORD'
}
$result['pre_serialization_qpc'] = Now
$encoded = [Text.UTF8Encoding]::new($false, $true).GetBytes(($result | ConvertTo-Json -Depth 6 -Compress))
$result['post_initial_serialization_qpc'] = Now
$outputLate = ($CleanupStop -gt 0 -and $result['post_initial_serialization_qpc'] -ge $CleanupStop)
$wireShapeFault = $false
$encoded = [Text.UTF8Encoding]::new($false, $true).GetBytes(($result | ConvertTo-Json -Depth 6 -Compress))
if ($encoded.Length -gt 131072) {
    # Fail closed without emitting an oversized record; keep primary/cleanup
    # faults and truthful read states even when the raw captured bytes are omitted.
    $wireShapeFault = $true
    $result['stdout_base64'] = $null
    $result['stderr_base64'] = $null
    $result['output_shape_fault'] = 'RAW_CAPTURE_OMITTED_PARENT_128KIB_WIRE_LIMIT'
    $encoded = [Text.UTF8Encoding]::new($false, $true).GetBytes(($result | ConvertTo-Json -Depth 6 -Compress))
}
if ($encoded.Length -gt 131072) { [Console]::Error.WriteLine('H4_PARENT_RESULT_SHAPE_EXCEEDED'); exit 1 }
$stdout = [Console]::OpenStandardOutput()
if ($CleanupStop -gt 0 -and (Now) -ge $CleanupStop) { $outputLate = $true }
try {
    $stdout.Write($encoded, 0, $encoded.Length)
    $stdout.Flush()
} catch { [Console]::Error.WriteLine('H4_PARENT_OUTPUT_WRITE_OR_FLUSH_FAULT'); exit 1 }
# A printed provisional record never overrides a late flush or serialization.
if ($CleanupStop -gt 0 -and (Now) -ge $CleanupStop) { $outputLate = $true }
if ($outputLate) { [Console]::Error.WriteLine('H4_PARENT_OUTPUT_AFTER_ABSOLUTE_CLEANUP_STOP_UNKNOWN_FEES'); exit 1 }
if ($null -ne $primaryFault -or $cleanupFaults.Count -gt 0 -or -not $joined -or $exitDword -ne 0 -or $unharvested.Count -gt 0 -or $wireShapeFault) { exit 1 }
# Exit zero reports only that this fixed child returned and was joined; every
# budget/admission field above remains explicitly non-passing.
exit 0
