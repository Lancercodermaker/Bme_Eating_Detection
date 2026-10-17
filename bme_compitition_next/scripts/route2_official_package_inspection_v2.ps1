# SOURCE PROPOSAL ONLY: H5 NOT OWNER APPROVED. Bind canonical H5 policy v2 only.
# No source/receipt/parameters authenticate owner identity or issue authority.
# Exactly one separately approved 120s active +60s cleanup additional attempt;
# H1 APPROVED_UNSTARTED; H3/H4 CONSUMED_FAILED_PARTIAL / NO RETRY unchanged.
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
$PolicyId = 'route2-h5-official-nongt-inspection-2026-10-16-002'
$PolicySha256 = '3645c1073f4153dd72f0c26b4f8cc6efd164b71117ec7e6c108e5b5a8d044754'
$ExceptionIds = 'ADOPT_TOOL_STARTED_POWERSHELL_ROOT_PRELOAD_CREATOR|DOTNET_ORIGINAL_PROCESS_NOT_NATIVE_PI_THREAD_JOIN|H5_MONITORED64_NOT_FORMAL4|H5_SAMPLED_RESOURCES_NOT_COMPLETE_CAUSAL_CAPS|H5_SHARED_RUNTIME_SERVICE_TAIL_UNJOINED|H5_E_NON_E_PHYSICAL_ACCOUNTING_UNPROVEN|H5_HARD_DEADLINE_SYNC_STALL_UNPROVEN|H5_TRUSTED_HOST_ONE_SHOT_NOT_SCRIPT_ANTIREPLAY|H5_ADDITIONAL_ONE180_NOT_H1_H3_H4'
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
    $e = [InvalidOperationException]::new('H5_FIXED_FAILURE')
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
    $encoded=H5-JsonBytes $Value
    if ($encoded.Length -gt 65536) {
        # The full result is unresolved, but retain inventory, all selected-read
        # ledgers and byte-identity summaries. Never emit an oversized record or
        # quietly reinterpret omitted full evidence as successful transport.
        $Value.collection_complete=$false;$Value.selected_evidence_complete=$false
        $Value.status='CHILD_TRANSPORT_LIMIT_UNRESOLVED'
        $summaries=[Collections.Generic.List[object]]::new()
        foreach($r in $Value.documents){$summaries.Add(@{ordinal=$r.ordinal;container_ordinal=$r.container_ordinal;kind=$r.kind;original_bytes=$r.original_bytes;original_sha256=$r.original_sha256;original_crc32=$r.original_crc32;original_encoding=$r.original_encoding;transport_encoding='identity-base64';payload_base64='';preview_bytes=0;full=$false;unresolved='CHILD_RECORD_TRANSPORT_UNRESOLVED'})}
        $Value.documents=@($summaries.ToArray());$Value['child_record_transport_unresolved']=$true
        $encoded=H5-JsonBytes $Value
        if ($encoded.Length -gt 65536) { Fail 'CHILD_RECORD_EXCEEDS_64KIB_WITH_SUMMARIES' }
    }
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
function H5-JsonBytes($Value) {
    return ,([Text.UTF8Encoding]::new($false,$true).GetBytes((ConvertTo-Json -InputObject $Value -Depth 14 -Compress)))
}
# Helpers accept an internal context so the SOURCE-only harness can supply
# synthetic MemoryStreams and fixture pins. Collect never accepts caller pins.
function H5-NewContext([long]$Deadline=0) {
    return @{ deadline=$Deadline; structural_charged=[long]0; structural_returned=[long]0;
        structural_limit=[long]131072; reads=[Collections.Generic.List[object]]::new();
        errors=[Collections.Generic.List[object]]::new(); errors_overflow=$false;
        documents=[Collections.Generic.List[object]]::new(); xml_total=[long]0;
        compressed_total=[long]0; uncompressed_total=[long]0; facts=$null; directory=$null }
}
function H5-Tick($C) {
    if ($C.deadline -gt 0 -and [Diagnostics.Stopwatch]::GetTimestamp() -ge $C.deadline) { Fail 'ACTIVE_DEADLINE_REACHED' }
}
function H5-Problem($C,[string]$Phase,[string]$Code,[int]$Ordinal=-1,[long]$Offset=-1,[string]$Field='', $Observed=$null,$Expected=$null,[int]$Container=-1) {
    $r=[ordered]@{phase=$Phase;code=$Code;ordinal=$Ordinal;container_ordinal=$Container;absolute_offset=$Offset;field=$Field;observed=$Observed;expected=$Expected;requested_bytes=$null;returned_bytes=$null;charged_bytes=$null;retryable=$false}
    $trial=@($C.errors.ToArray())+@($r)
    if ($C.errors.Count -lt 32 -and (H5-JsonBytes $trial).Length -le 8192) { $C.errors.Add($r) }
    else { $C.errors_overflow=$true }
}
function H5-Stop($C,[string]$Phase,[string]$Code,[int]$Ordinal=-1,[long]$Offset=-1,[string]$Field='', $Observed=$null,$Expected=$null) {
    H5-Problem $C $Phase $Code $Ordinal $Offset $Field $Observed $Expected
    Fail $Code
}
function H5-U16([byte[]]$B,[int]$P) {
    if ($P -lt 0 -or $P -gt $B.Length-2) { Fail 'U16_BOUNDS' }
    return [uint16]([int]$B[$P]+([int]$B[$P+1]*256))
}
function H5-U32([byte[]]$B,[int]$P) {
    if ($P -lt 0 -or $P -gt $B.Length-4) { Fail 'U32_BOUNDS' }
    return [uint32]([long]$B[$P]+([long]$B[$P+1]*256)+([long]$B[$P+2]*65536)+([long]$B[$P+3]*16777216))
}
function H5-Slice([byte[]]$B,[int]$P,[int]$N) {
    if ($P -lt 0 -or $N -lt 0 -or $P -gt $B.Length-$N) { Fail 'SLICE_BOUNDS' }
    $o=[byte[]]::new($N); [Array]::Copy($B,$P,$o,0,$N); return ,$o
}
function H5-Crc([byte[]]$Bytes) {
    [uint32]$crc=4294967295
    foreach($v in $Bytes) {
        $crc=$crc -bxor [uint32]$v
        for($j=0;$j -lt 8;$j++) {
            if (($crc -band 1) -ne 0) { $crc=($crc -shr 1) -bxor [uint32]3988292384 }
            else { $crc=$crc -shr 1 }
        }
    }
    return [uint32]($crc -bxor [uint32]4294967295)
}
function H5-ReadAt($C,[IO.Stream]$Stream,[long]$Offset,[int]$Count,[string]$Kind='structural',[int]$Ordinal=-1,[int]$Container=-1) {
    H5-Tick $C
    if ($Offset -lt 0 -or $Count -lt 0 -or $Offset -gt $Stream.Length-$Count) { H5-Stop $C 'read' 'READ_RANGE' $Ordinal $Offset 'count' $Count $Stream.Length }
    if ($Kind -ceq 'structural') {
        if ($C.structural_charged -gt $C.structural_limit-$Count) { H5-Stop $C 'read' 'STRUCTURAL_BUDGET' $Ordinal $Offset 'requested_bytes' $Count $C.structural_limit }
        $C.structural_charged += $Count
    } elseif ($Kind -cne 'payload') { Fail 'READ_KIND' }
    $r=[ordered]@{kind=$Kind;ordinal=$Ordinal;container_ordinal=$Container;absolute_offset=$Offset;requested_bytes=$Count;returned_bytes=0;charged_bytes=$Count;complete=$false;partial_bytes_unknown=$false}
    $C.reads.Add($r)
    $b=[byte[]]::new($Count); $done=0
    try {
        $null=$Stream.Seek($Offset,[IO.SeekOrigin]::Begin)
        while($done -lt $Count) {
            H5-Tick $C
            # A throwing Stream.Read may have touched bytes without returning a
            # count. Retain that uncertainty, never turn it into returned zero.
            $r.partial_bytes_unknown=$true
            $n=$Stream.Read($b,$done,$Count-$done)
            $r.partial_bytes_unknown=$false
            if ($n -le 0 -or $n -gt $Count-$done) { H5-Stop $C 'read' 'READ_SHORT_OR_INVALID_COUNT' $Ordinal ($Offset+$done) 'returned_count' $n ($Count-$done) }
            $done += $n; $r.returned_bytes=$done
            if ($Kind -ceq 'structural') { $C.structural_returned += $n }
        }
        $r.complete=$true
    } catch { throw }
    H5-Tick $C
    return ,$b
}
function H5-StrictUtf8([byte[]]$B,[switch]$NoBom) {
    if ($NoBom -and $B.Length -ge 3 -and $B[0] -eq 239 -and $B[1] -eq 187 -and $B[2] -eq 191) { Fail 'UTF8_BOM_FORBIDDEN' }
    return [Text.UTF8Encoding]::new($false,$true).GetString($B)
}
function H5-Extras($C,[byte[]]$B,[byte[]]$RawName,[byte[]]$RawComment,[bool]$Local,[int]$Ordinal,[long]$Base) {
    $items=[Collections.Generic.List[object]]::new(); $seen=@{}; $unicode=$null; $ok=$true; $p=0
    while($p -lt $B.Length) {
        H5-Tick $C
        if ($p -gt $B.Length-4) { H5-Problem $C 'extras' 'EXTRA_TLV_HEADER_TRUNCATED' $Ordinal ($Base+$p) 'remaining' ($B.Length-$p) 4; $ok=$false; break }
        $id=[int](H5-U16 $B $p); $len=[int](H5-U16 $B ($p+2)); $q=$p+4
        if ($len -gt $B.Length-$q) { H5-Problem $C 'extras' 'EXTRA_TLV_LENGTH' $Ordinal ($Base+$p+2) 'length' $len ($B.Length-$q); $ok=$false; break }
        $v=H5-Slice $B $q $len
        $item=[ordered]@{id=$id;length=$len;absolute_offset=($Base+$p);sha256=(Sha-Bytes $v);prefix_base64=[Convert]::ToBase64String((H5-Slice $v 0 ([Math]::Min(256,$len))));raw_complete=($len -le 256);recognized=$false;valid=$false;details=$null}
        $items.Add($item)
        if ($seen.ContainsKey($id)) { H5-Problem $C 'extras' 'EXTRA_DUPLICATE_ID' $Ordinal ($Base+$p) 'id' $id 'unique'; $ok=$false }
        $seen[$id]=$true
        try {
            switch($id) {
                10 {
                    $item.recognized=$true
                    if ($len -lt 4 -or (H5-U32 $v 0) -ne 0) { Fail 'NTFS_RESERVED' }
                    $np=4; $tags=[Collections.Generic.List[object]]::new(); $ntseen=@{}
                    while($np -lt $len) {
                        if ($np -gt $len-4) { Fail 'NTFS_TAG_HEADER' }
                        $tag=[int](H5-U16 $v $np); $tn=[int](H5-U16 $v ($np+2)); $np+=4
                        if ($tn -gt $len-$np) { Fail 'NTFS_TAG_LENGTH' }
                        if ($ntseen.ContainsKey($tag)) { Fail 'NTFS_DUPLICATE_TAG' }; $ntseen[$tag]=$true
                        $tb=H5-Slice $v $np $tn
                        $tags.Add(@{tag=$tag;length=$tn;raw_base64=[Convert]::ToBase64String($tb)})
                        if ($tag -ne 1) { Fail 'NTFS_UNKNOWN_TAG' }
                        if ($tn -ne 24) { Fail 'NTFS_TIMESTAMP_LENGTH' }
                        $np+=$tn
                    }
                    $item.details=@($tags.ToArray()); $item.valid=$true
                }
                21589 {
                    $item.recognized=$true
                    if ($len -lt 1 -or ($v[0] -band 248) -ne 0) { Fail 'UT_FLAGS' }
                    $n=1
                    if (($v[0] -band 1) -ne 0) { $n+=4 }
                    if ($Local) { if (($v[0] -band 2) -ne 0) { $n+=4 }; if (($v[0] -band 4) -ne 0) { $n+=4 } }
                    if ($len -ne $n) { Fail 'UT_LAYOUT_LENGTH' }
                    $item.details=@{flags=[int]$v[0];layout=$(if($Local){'local'}else{'central'});raw_timestamps_base64=[Convert]::ToBase64String((H5-Slice $v 1 ($len-1)))}; $item.valid=$true
                }
                {$_ -eq 28789 -or $_ -eq 25461} {
                    $item.recognized=$true
                    if ($len -lt 5 -or $v[0] -ne 1) { Fail 'UNICODE_VERSION_OR_LENGTH' }
                    $bound=$RawName; if($id -eq 25461){$bound=$RawComment}
                    if ((H5-U32 $v 1) -ne (H5-Crc $bound)) { Fail 'UNICODE_RAW_CRC' }
                    $txt=H5-StrictUtf8 (H5-Slice $v 5 ($len-5)) -NoBom
                    $item.details=@{utf8_base64=[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($txt));raw_binding_crc32=(H5-U32 $v 1)}
                    if ($id -eq 28789) { $unicode=$txt }
                    $item.valid=$true
                }
                30837 {
                    $item.recognized=$true
                    if ($len -lt 3 -or $v[0] -ne 1) { Fail 'UID_GID_VERSION_OR_LENGTH' }
                    $ul=[int]$v[1]; $gp=2+$ul
                    if ($ul -lt 1 -or $gp -ge $len) { Fail 'UID_LENGTH' }
                    $gl=[int]$v[$gp]
                    if ($gl -lt 1 -or $gp+1+$gl -ne $len) { Fail 'GID_LENGTH' }
                    $item.details=@{uid_little_endian_base64=[Convert]::ToBase64String((H5-Slice $v 2 $ul));gid_little_endian_base64=[Convert]::ToBase64String((H5-Slice $v ($gp+1) $gl))}; $item.valid=$true
                }
                default { H5-Problem $C 'extras' 'EXTRA_UNKNOWN_SEMANTICS' $Ordinal ($Base+$p) 'id' $id 'recognized path/type semantics'; $ok=$false }
            }
        } catch {
            $code='EXTRA_DECODE_FAILED'; $e=$_.Exception
            for($d=0;$d -lt 8;$d++){if($e.Data.Contains('Route2FixedCode')){$code=[string]$e.Data['Route2FixedCode']};if($null -eq $e.InnerException){break};$e=$e.InnerException}
            H5-Problem $C 'extras' $code $Ordinal ($Base+$p) 'extra_id' $id 'valid exact layout'; $ok=$false
        }
        $p=$q+$len
    }
    return @{items=@($items.ToArray());safe=$ok;unicode_path=$unicode;complete=($p -eq $B.Length)}
}
function H5-PathCheck([string]$Name,[int]$RawLength,[bool]$AllowNestedOpcMetadata=$false,[bool]$RawByteSafetyOnly=$false) {
    if ($RawLength -gt 1024 -or $RawLength -eq 0 -or ((-not $RawByteSafetyOnly) -and [Text.Encoding]::UTF8.GetByteCount($Name) -gt 1024) -or $Name.Length -eq 0 -or $Name -match '[\\:\x00-\x1f\x7f]' -or $Name.StartsWith('/')) { Fail 'PATH_UNSAFE_CHARACTER_OR_LENGTH' }
    $dir=$Name.EndsWith('/'); $s=$Name; if($dir){$s=$s.Substring(0,$s.Length-1)}
    $parts=$s.Split('/')
    if ($parts.Length -gt 16) { Fail 'PATH_COMPONENT_LIMIT' }
    foreach($part in $parts) {
        $exactOpcHidden=($AllowNestedOpcMetadata -and $Name -ceq '_rels/.rels' -and $part -ceq '.rels')
        if ($part.Length -eq 0 -or ($part.StartsWith('.') -and -not $exactOpcHidden) -or $part.EndsWith('.') -or $part.EndsWith(' ') -or $part -match '[<>"|?*]' -or $part -match '^(?i:CON|PRN|AUX|NUL|COM[1-9]|LPT[1-9])(?:\.|$)') { Fail 'PATH_UNSAFE_COMPONENT' }
        foreach($ch in $part.ToCharArray()) { if ([char]::IsControl($ch) -or [char]::GetUnicodeCategory($ch) -eq [Globalization.UnicodeCategory]::Format) { Fail 'PATH_CONTROL_OR_FORMAT' } }
    }
    return @{name=$Name;key=$s.Normalize([Text.NormalizationForm]::FormC).ToLowerInvariant();directory=$dir;parts=$parts}
}
function H5-Denied([string]$Name) {
    $lower=$Name.ToLowerInvariant(); $fold=[regex]::Replace($lower,'[^a-z0-9]+','_')
    foreach($t in @('gt','groundtruth','ground_truth','label','labels','annotation','annotations','answer','answers','target','targets','train','training','test','validation','dataset','data','sample','samples','sensor','raw','recording')) {
        if ($lower -match ('(?:^|[^a-z0-9])'+[regex]::Escape($t)+'(?:$|[^a-z0-9])') -or $fold -match ('(?:^|_)'+[regex]::Escape($t)+'(?:$|_)')) { return $true }
    }
    $zh=ConvertFrom-Json '["\u771f\u503c","\u6807\u7b7e","\u6807\u6ce8","\u7b54\u6848","\u8bad\u7ec3","\u6d4b\u8bd5","\u9a8c\u8bc1","\u6570\u636e","\u6837\u672c","\u4f20\u611f","\u539f\u59cb","\u5f55\u5236"]'
    foreach($t in $zh){if($Name.Contains($t)){return $true}}
    return $false
}
function H5-TypeSemantics($C,$R,$Path) {
    # PKWARE 4.4.2/4.4.15: the upper made-by byte determines the
    # attribute interpretation. No Unix/DOS interpretation for unknown hosts.
    # These are conservative supported combinations, not a claim that other
    # producers/attribute values are impossible or invalid ZIP metadata.
    $hostId=($R.made_by -shr 8) -band 255;$attrs=[long]$R.external_attributes
    $R.host_system=$hostId;$R.attribute_profile='UNRESOLVED';$R.interpreted_type='UNRESOLVED'
    $safe=$true;$directory=$null
    switch($hostId){
        0 {
            $R.attribute_profile='MSDOS_LOW_BYTE_VISIBLE_REGULAR_DIRECTORY_V1'
            if(($attrs -band 4294967246) -ne 0){H5-Problem $C 'semantics' 'DOS_ATTRIBUTES_UNSUPPORTED' $R.ordinal $R.central_offset 'external_attributes' $attrs 'only readonly(1),directory(16),archive(32)';$safe=$false}
            $directory=($attrs -band 16) -ne 0
        }
        3 {
            $R.attribute_profile='UNIX_ST_MODE_HIGH_WORD_WITH_DOS_LOW_BYTE_V1'
            $mode=($attrs -shr 16) -band 61440
            if($mode -notin @(16384,32768)){H5-Problem $C 'semantics' 'UNIX_FILE_TYPE_UNSUPPORTED' $R.ordinal $R.central_offset 'unix_file_type' $mode @(16384,32768);$safe=$false}else{$directory=$mode -eq 16384}
            if(($attrs -band 65486) -ne 0){H5-Problem $C 'semantics' 'UNIX_DOS_ATTRIBUTE_BITS_UNSUPPORTED' $R.ordinal $R.central_offset 'dos_attribute_word' ($attrs -band 65535) 'only readonly(1),directory(16),archive(32)';$safe=$false}
            if(($attrs -band 16) -ne 0 -and $mode -eq 32768){H5-Problem $C 'semantics' 'UNIX_DOS_DIRECTORY_CONFLICT' $R.ordinal $R.central_offset 'dos_directory' $true $false;$safe=$false}
        }
        10 {
            $R.attribute_profile='NTFS_VISIBLE_REGULAR_DIRECTORY_FLAGS_V1'
            if(($attrs -band 4294967118) -ne 0){H5-Problem $C 'semantics' 'NTFS_ATTRIBUTES_UNSUPPORTED' $R.ordinal $R.central_offset 'external_attributes' $attrs 'only readonly(1),directory(16),archive(32),normal(128)';$safe=$false}
            if(($attrs -band 128) -ne 0 -and $attrs -ne 128){H5-Problem $C 'semantics' 'NTFS_NORMAL_ATTRIBUTE_CONFLICT' $R.ordinal $R.central_offset 'external_attributes' $attrs 128;$safe=$false}
            $directory=($attrs -band 16) -ne 0
        }
        default {H5-Problem $C 'semantics' 'ENTRY_HOST_SEMANTICS_UNSUPPORTED' $R.ordinal $R.central_offset 'made_by_host' $hostId @(0,3,10);$safe=$false}
    }
    if($null -ne $directory){
        if($safe){$R.interpreted_type=$(if($directory){'directory'}else{'regular_file'})}
        if($null -ne $Path -and $Path.directory -ne $directory){H5-Problem $C 'semantics' 'ENTRY_TYPE_PATH_CONFLICT' $R.ordinal $R.central_offset 'path_is_directory' $Path.directory $directory;$safe=$false}
    }
    return $safe
}
function H5-LegacySafety($C,$R,[string[]]$UnicodeAliases,[bool]$Nested=$false) {
    # SAFETY ONLY: preserve literal ASCII bytes and replace opaque bytes with a
    # private sentinel. This is NOT a decoded raw name or CP437 path authority.
    # A valid Unicode CRC binds bytes, not the correspondence of path semantics.
    $sb=[Text.StringBuilder]::new()
    foreach($b in $R.raw_name){if($b -lt 128){$null=$sb.Append([char]$b)}else{$null=$sb.Append([char]65533)}}
    $shape=$sb.ToString();$safe=$true;$denied=H5-Denied $shape;$rawPath=$null
    if($denied){H5-Problem $C 'semantics' 'LEGACY_RAW_ASCII_DENY' $R.ordinal $R.central_offset 'raw_ascii_tokens' 'forbidden token' 'no forbidden original ASCII token';$safe=$false}
    try{$rawPath=H5-PathCheck $shape $R.raw_name.Length $Nested $true}catch{
        $code='LEGACY_RAW_PATH_INVALID';$e=$_.Exception
        for($i=0;$i -lt 8;$i++){if($e.Data.Contains('Route2FixedCode')){$code='LEGACY_RAW_'+[string]$e.Data['Route2FixedCode']};if($null -eq $e.InnerException){break};$e=$e.InnerException}
        H5-Problem $C 'semantics' $code $R.ordinal $R.central_offset 'raw_ascii_structure' 'unsafe' 'safe relative byte structure';$safe=$false
    }
    if($null -eq $rawPath){return @{safe=$false;denied=$denied}}
    foreach($alias in $UnicodeAliases){
        $aliasPath=$null
        try{$aliasPath=H5-PathCheck $alias $R.raw_name.Length $Nested}catch{$safe=$false;continue}
        if($aliasPath.parts.Length -ne $rawPath.parts.Length){H5-Problem $C 'semantics' 'LEGACY_COMPONENT_COUNT_CONFLICT' $R.ordinal $R.central_offset 'unicode_path_components' $aliasPath.parts.Length $rawPath.parts.Length;$safe=$false;continue}
        if($aliasPath.directory -ne $rawPath.directory){H5-Problem $C 'semantics' 'LEGACY_DIRECTORY_SHAPE_CONFLICT' $R.ordinal $R.central_offset 'unicode_is_directory' $aliasPath.directory $rawPath.directory;$safe=$false}
        for($i=0;$i -lt $rawPath.parts.Length;$i++){
            $rp=$rawPath.parts[$i];$ap=$aliasPath.parts[$i]
            if($rp.IndexOf([char]65533) -lt 0){
                if($rp -cne $ap){H5-Problem $C 'semantics' 'LEGACY_ASCII_COMPONENT_CONFLICT' $R.ordinal $R.central_offset 'unicode_component_utf8_base64' ([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($ap))) ([Convert]::ToBase64String([Text.Encoding]::ASCII.GetBytes($rp)));$safe=$false}
            }else{
                # Opaque runs may map only to nonASCII Unicode runs. Literal
                # ASCII runs (including extensions) must survive unchanged.
                $rs=[regex]::Replace($rp,'[^\x00-\x7f]+',[string][char]65533)
                $as=[regex]::Replace($ap,'[^\x00-\x7f]+',[string][char]65533)
                if($rs -cne $as){H5-Problem $C 'semantics' 'LEGACY_ASCII_SKELETON_CONFLICT' $R.ordinal $R.central_offset 'unicode_ascii_signature_base64' ([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($as))) ([Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($rs)));$safe=$false}
            }
        }
    }
    return @{safe=$safe;denied=$denied}
}
function H5-NameSemantics($C,$R,$X,$LX,[bool]$Nested=$false) {
    $safe=$X.safe -and $LX.safe; $aliases=[Collections.Generic.List[string]]::new(); $raw=$R.raw_name
    $ascii=$true; foreach($b in $raw){if($b -gt 127){$ascii=$false;break}}
    $base=$null
    try { if(($R.flags -band 2048) -ne 0){$base=H5-StrictUtf8 $raw -NoBom} elseif($ascii){$base=[Text.Encoding]::ASCII.GetString($raw)} }
    catch { H5-Problem $C 'semantics' 'NAME_STRICT_UTF8' $R.ordinal $R.central_offset 'raw_name' 'invalid' 'strict UTF8'; $safe=$false }
    $legacyDenied=$false
    if(($R.flags -band 2048) -eq 0 -and -not $ascii){
        $bindings=[Collections.Generic.List[string]]::new();foreach($x in @($X,$LX)){if($null -ne $x.unicode_path -and -not $bindings.Contains($x.unicode_path)){$bindings.Add($x.unicode_path)}}
        $legacy=H5-LegacySafety $C $R @($bindings.ToArray()) $Nested
        if(-not $legacy.safe){$safe=$false};$legacyDenied=$legacy.denied
    }
    if($null -ne $base){$aliases.Add($base)}
    foreach($x in @($X,$LX)){if($null -ne $x.unicode_path -and -not $aliases.Contains($x.unicode_path)){$aliases.Add($x.unicode_path)}}
    if($null -ne $X.unicode_path -and $null -ne $LX.unicode_path -and $X.unicode_path -cne $LX.unicode_path){H5-Problem $C 'semantics' 'LOCAL_CENTRAL_UNICODE_CONFLICT' $R.ordinal $R.local_offset 'unicode_path' 'different' 'same';$safe=$false}
    if($null -ne $base -and (($null -ne $X.unicode_path -and $base -cne $X.unicode_path) -or ($null -ne $LX.unicode_path -and $base -cne $LX.unicode_path))){H5-Problem $C 'semantics' 'RAW_UNICODE_ALIAS_CONFLICT' $R.ordinal $R.central_offset 'unicode_path' 'renamed' 'same path';$safe=$false}
    $authority=$base
    if($null -eq $authority){if($null -ne $X.unicode_path){$authority=$X.unicode_path}elseif($null -ne $LX.unicode_path){$authority=$LX.unicode_path}else{H5-Problem $C 'semantics' 'LEGACY_NAME_UNRESOLVED' $R.ordinal $R.central_offset 'raw_name' 'nonASCII legacy' 'valid Unicode binding';$safe=$false}}
    $denied=$legacyDenied; $path=$null
    foreach($a in $aliases){if(H5-Denied $a){$denied=$true};try{$p=H5-PathCheck $a $raw.Length $Nested;if($a -ceq $authority){$path=$p}}catch{$code='PATH_INVALID';$pe=$_.Exception;for($pd=0;$pd -lt 8;$pd++){if($pe.Data.Contains('Route2FixedCode')){$code=[string]$pe.Data['Route2FixedCode']};if($null -eq $pe.InnerException){break};$pe=$pe.InnerException};H5-Problem $C 'semantics' $code $R.ordinal $R.central_offset 'alias' 'unsafe' 'safe relative path';$safe=$false}}
    if(-not (H5-TypeSemantics $C $R $path)){$safe=$false}
    if(($R.flags -band 1) -ne 0 -or ($R.flags -band 64) -ne 0 -or ($R.flags -band 8192) -ne 0 -or ($R.flags -band 32768) -ne 0 -or ($R.flags -band 63473) -ne 0){H5-Problem $C 'semantics' 'ENTRY_FLAGS_UNSUPPORTED' $R.ordinal $R.central_offset 'flags' $R.flags 'ZIP32 unencrypted known flags';$safe=$false}
    if($R.needed -gt 63){H5-Problem $C 'semantics' 'ENTRY_VERSION_UNSUPPORTED' $R.ordinal $R.central_offset 'version_needed' $R.needed '<=63; selected0/8<=20';$safe=$false}
    $R.aliases_utf8_base64=@($aliases.ToArray()|ForEach-Object{[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($_))})
    $R.denied=$denied; $R.semantic_safe=$safe; $R.path=$path
}
function H5-Positive([string]$Name,[string]$Wrapper) {
    if(H5-Denied $Name){return $null}
    $p=$Name.Split('/');if($Wrapper.Length -gt 0 -and $p.Length -gt 1 -and $p[0] -ceq $Wrapper){$p=@($p[1..($p.Length-1)])}
    $locations=ConvertFrom-Json '["doc","docs","rules","spec","schema","evaluation","evaluator","\u6587\u6863","\u8bf4\u660e","\u89c4\u5219","\u89c4\u8303","\u8bc4\u6d4b","\u8bc4\u4ef7","\u63d0\u4ea4","\u63a5\u53e3"]'
    if($p.Length -gt 2 -or ($p.Length -eq 2 -and $locations -notcontains $p[0])){return $null}
    $file=$p[$p.Length-1];$ext=[IO.Path]::GetExtension($file).ToLowerInvariant();$stem=[IO.Path]::GetFileNameWithoutExtension($file)
    $stems=ConvertFrom-Json '["README","RULES","INSTRUCTIONS","TASK","SUBMISSION","METRIC","METRICS","SCORING","problem_statement","task_description","competition_rules","submission_guidelines","evaluation_protocol","scoring_rules","\u8d5b\u9898\u8bf4\u660e","\u4efb\u52a1\u8bf4\u660e","\u8d5b\u9898\u89c4\u5219","\u7ade\u8d5b\u89c4\u5219","\u63d0\u4ea4\u8bf4\u660e","\u8bc4\u6d4b\u8bf4\u660e","\u8bc4\u4ef7\u6307\u6807","\u8bc4\u5206\u89c4\u5219","\u8f93\u5165\u8f93\u51fa\u683c\u5f0f","\u63a5\u53e3\u8bf4\u660e","\u8d5b\u98982","\u8d5b\u98982\u8bf4\u660e","\u8d5b\u98982\u89c4\u5219"]'
    if($ext -in @('.md','.txt','.rst','.docx') -and $stems -contains $stem){if($ext -eq '.docx'){return 'docx'};return 'plain'}
    if($file.ToLowerInvariant() -in @('evaluate.py','evaluation.py','evaluator.py','metric.py','metrics.py','score.py','scoring.py','submission.py','schema.json','input_schema.json','output_schema.json','submission_schema.json')){return 'text_only_code_or_schema'}
    return $null
}
function H5-CentralLengths($C,$R) {
    $safe=$true
    if($R.raw_name.Length -gt 1024){H5-Problem $C 'semantics' 'CENTRAL_NAME_LENGTH_LIMIT' $R.ordinal $R.central_offset 'name_bytes' $R.raw_name.Length 1024;$safe=$false}
    if($R.raw_extra.Length -gt 4096){H5-Problem $C 'semantics' 'CENTRAL_EXTRA_LENGTH_LIMIT' $R.ordinal $R.central_extra_offset 'extra_bytes' $R.raw_extra.Length 4096;$safe=$false}
    return $safe
}
function H5-SelectedCounts($C,[int]$SelectedCount,[int]$DocxCount) {
    if($SelectedCount -gt 8){H5-Stop $C 'selection' 'SELECTED_MEMBER_COUNT_LIMIT' -1 -1 'selected_member_count' $SelectedCount 8}
    if($DocxCount -gt 2){H5-Stop $C 'selection' 'SELECTED_DOCX_COUNT_LIMIT' -1 -1 'selected_docx_count' $DocxCount 2}
}
function H5-SelectedMember($C,$R) {
    if($R.method -notin @(0,8)){H5-Stop $C 'selection' 'SELECTED_METHOD_UNSUPPORTED' $R.ordinal $R.payload_offset 'method' $R.method @(0,8)}
    if($R.needed -gt 20){H5-Stop $C 'selection' 'SELECTED_VERSION_NEEDED_LIMIT' $R.ordinal $R.payload_offset 'version_needed' $R.needed 20}
    if($R.compressed_size -gt 262144){H5-Stop $C 'selection' 'SELECTED_COMPRESSED_SIZE_LIMIT' $R.ordinal $R.payload_offset 'compressed_size' $R.compressed_size 262144}
    if($R.uncompressed_size -gt 262144){H5-Stop $C 'selection' 'SELECTED_UNCOMPRESSED_SIZE_LIMIT' $R.ordinal $R.payload_offset 'uncompressed_size' $R.uncompressed_size 262144}
    if($R.compressed_size -eq 0 -and $R.uncompressed_size -ne 0){H5-Stop $C 'selection' 'SELECTED_ZERO_COMPRESSED_NONEMPTY' $R.ordinal $R.payload_offset 'uncompressed_size' $R.uncompressed_size 0}
    if($R.compressed_size -gt 0 -and $R.uncompressed_size -gt $R.compressed_size*20){H5-Stop $C 'selection' 'SELECTED_EXPANSION_RATIO_LIMIT' $R.ordinal $R.payload_offset 'uncompressed_size' $R.uncompressed_size ($R.compressed_size*20)}
}
function H5-SelectedTotals($C,[long]$Compressed,[long]$Uncompressed) {
    if($Compressed -gt 1048576){H5-Stop $C 'selection' 'SELECTED_COMPRESSED_TOTAL_LIMIT' -1 -1 'compressed_total_bytes' $Compressed 1048576}
    if($Uncompressed -gt 1048576){H5-Stop $C 'selection' 'SELECTED_UNCOMPRESSED_TOTAL_LIMIT' -1 -1 'uncompressed_total_bytes' $Uncompressed 1048576}
}
function H5-Directory($C,[IO.Stream]$Stream,[long]$ExpectedLength,[int]$ExpectedCount,[string]$ExpectedCentral,[bool]$Nested=$false) {
    $d=@{declared_count=$null;parsed_count=0;central_records_complete=$false;local_bindings_complete=$false;metadata_semantics_complete=$false;central_sha256=$null;central_raw_base64=$null;central_start=$null;records=[Collections.Generic.List[object]]::new();safe=$false}
    $C.directory=$d
    # Make the partial directory reachable before the first potentially failing read.
    if(-not $Nested){$C.facts.directory=$d}
    $length=$Stream.Length
    if($ExpectedLength -ge 0 -and $length -ne $ExpectedLength){H5-Stop $C 'binding' 'INPUT_LENGTH_MISMATCH' -1 0 'length' $length $ExpectedLength}
    if($length -lt 22){H5-Stop $C 'eocd' 'EOCD_TOO_SHORT' -1 $length 'length' $length 22}
    $end=H5-ReadAt $C $Stream ($length-22) 22
    if((H5-U32 $end 0) -ne 101010256){H5-Stop $C 'eocd' 'EOCD_SIGNATURE' -1 ($length-22) 'signature' (H5-U32 $end 0) 101010256}
    if((H5-U16 $end 20) -ne 0){H5-Stop $C 'eocd' 'EOCD_COMMENT_UNSUPPORTED' -1 ($length-2) 'comment_length' (H5-U16 $end 20) 0}
    $count=[int](H5-U16 $end 10);$d.declared_count=$count
    if((H5-U16 $end 4) -ne 0 -or (H5-U16 $end 6) -ne 0 -or (H5-U16 $end 8) -ne $count){H5-Stop $C 'eocd' 'EOCD_MULTIDISK' -1 ($length-18) 'disk_fields' 'nonzero or unequal' 'single disk'}
    $maxCount=10;$maxCentral=1422;if($Nested){$maxCount=128;$maxCentral=32768}
    if($count -gt $maxCount -or $count -eq 65535 -or ($ExpectedCount -ge 0 -and $count -ne $ExpectedCount)){H5-Stop $C 'binding' 'EOCD_ENTRY_COUNT' -1 ($length-12) 'declared_count' $count $ExpectedCount}
    $cs=[long](H5-U32 $end 12);$co=[long](H5-U32 $end 16);$d.central_start=$co
    if($cs -gt $maxCentral){H5-Stop $C 'eocd' 'CENTRAL_SIZE_BUDGET' -1 ($length-10) 'central_size' $cs $maxCentral}
    if($co -gt $length-22){H5-Stop $C 'eocd' 'CENTRAL_OFFSET_RANGE' -1 ($length-6) 'central_offset' $co ($length-22)}
    if($cs -ne $length-22-$co){H5-Stop $C 'eocd' 'CENTRAL_END_MISMATCH' -1 ($length-10) 'central_size' $cs ($length-22-$co)}
    $central=H5-ReadAt $C $Stream $co ([int]$cs);$hash=Sha-Bytes $central;$d.central_sha256=$hash;$d.central_raw_base64=[Convert]::ToBase64String($central)
    if($ExpectedCentral.Length -gt 0 -and $hash -cne $ExpectedCentral){H5-Stop $C 'binding' 'CENTRAL_SHA256_MISMATCH' -1 $co 'central_sha256' $hash $ExpectedCentral}
    # Stage 1: only record boundaries and scalar/raw identities. No name/extra
    # semantics can stop safely bounded later central records from being parsed.
    $p=0
    for($i=0;$i -lt $count;$i++){
        H5-Tick $C
        if($p -gt $central.Length-46){H5-Stop $C 'central' 'CENTRAL_FIXED_HEADER_TRUNCATED' $i ($co+$p) 'remaining' ($central.Length-$p) 46}
        if((H5-U32 $central $p) -ne 33639248){H5-Stop $C 'central' 'CENTRAL_SIGNATURE' $i ($co+$p) 'signature' (H5-U32 $central $p) 33639248}
        $nl=[int](H5-U16 $central ($p+28));$xl=[int](H5-U16 $central ($p+30));$cl=[int](H5-U16 $central ($p+32));$total=46+$nl+$xl+$cl
        if($total -gt $central.Length-$p){H5-Stop $C 'central' 'CENTRAL_VARIABLE_RECORD_TRUNCATED' $i ($co+$p+28) 'record_length' $total ($central.Length-$p)}
        $r=@{ordinal=$i;central_offset=($co+$p);made_by=[int](H5-U16 $central ($p+4));needed=[int](H5-U16 $central ($p+6));flags=[int](H5-U16 $central ($p+8));method=[int](H5-U16 $central ($p+10));dos_time=[int](H5-U16 $central ($p+12));dos_date=[int](H5-U16 $central ($p+14));crc32=[uint32](H5-U32 $central ($p+16));compressed_size=[long](H5-U32 $central ($p+20));uncompressed_size=[long](H5-U32 $central ($p+24));disk=[int](H5-U16 $central ($p+34));internal_attributes=[int](H5-U16 $central ($p+36));external_attributes=[long](H5-U32 $central ($p+38));local_offset=[long](H5-U32 $central ($p+42));raw_name=(H5-Slice $central ($p+46) $nl);raw_extra=(H5-Slice $central ($p+46+$nl) $xl);raw_comment=(H5-Slice $central ($p+46+$nl+$xl) $cl);central_extra_offset=($co+$p+46+$nl);local_raw_extra=$null;local_extra_offset=$null;payload_offset=$null;range_end=$null;descriptor_bytes=$null;local_bound=$false;semantic_safe=$false;host_system=$null;attribute_profile='UNRESOLVED';interpreted_type='UNRESOLVED';aliases_utf8_base64=@();denied=$false;path=$null;selected=$false;selection_kind=$null;central_extras=$null;local_extras=$null}
        $d.records.Add($r);$d.parsed_count++;$p+=$total
    }
    if($p -ne $central.Length){H5-Stop $C 'central' 'CENTRAL_TRAILING_BYTES' -1 ($co+$p) 'remaining' ($central.Length-$p) 0}
    $d.central_records_complete=$true
    # Stage 2: exact local and payload ranges, without opening payload. A range
    # error preserves all already parsed central records and zero payload reads.
    $sorted=@($d.records.ToArray()|Sort-Object local_offset);$next=0L
    for($k=0;$k -lt $sorted.Length;$k++){
        $r=$sorted[$k];$i=$r.ordinal;$lo=$r.local_offset
        if($r.disk -ne 0 -or $r.compressed_size -eq 4294967295 -or $r.uncompressed_size -eq 4294967295 -or $lo -eq 4294967295){H5-Stop $C 'local' 'ZIP64_OR_DISK_UNSUPPORTED' $i $lo 'ZIP32 fields' 'sentinel/disk' 'ZIP32 single disk'}
        if($lo -ne $next){H5-Stop $C 'ranges' 'LOCAL_RANGE_START_GAP' $i $lo 'local_offset' $lo $next}
        if($lo -gt $co-30){H5-Stop $C 'ranges' 'LOCAL_FIXED_HEADER_RANGE' $i $lo 'local_offset' $lo ($co-30)}
        $boundary=$co;if($k+1 -lt $sorted.Length){$boundary=$sorted[$k+1].local_offset}
        if($boundary -le $lo -or $boundary -gt $co){H5-Stop $C 'ranges' 'LOCAL_NEXT_BOUNDARY' $i $lo 'next_boundary' $boundary $co}
        $lh=H5-ReadAt $C $Stream $lo 30
        if((H5-U32 $lh 0) -ne 67324752){H5-Stop $C 'local' 'LOCAL_SIGNATURE' $i $lo 'signature' (H5-U32 $lh 0) 67324752}
        foreach($f in @(@('needed',4),@('flags',6),@('method',8),@('dos_time',10),@('dos_date',12))){$actual=[int](H5-U16 $lh $f[1]);if($actual -ne $r[$f[0]]){H5-Stop $C 'local' ('LOCAL_'+$f[0].ToUpperInvariant()+'_MISMATCH') $i ($lo+$f[1]) $f[0] $actual $r[$f[0]]}}
        $nl=[int](H5-U16 $lh 26);$xl=[int](H5-U16 $lh 28)
        if($nl -ne $r.raw_name.Length){H5-Stop $C 'local' 'LOCAL_NAME_LENGTH_MISMATCH' $i ($lo+26) 'name_length' $nl $r.raw_name.Length}
        if($xl -gt 4096){H5-Stop $C 'local' 'LOCAL_EXTRA_LIMIT' $i ($lo+28) 'extra_length' $xl 4096}
        $start=$lo+30L+$nl+$xl
        if($start -gt $boundary -or $r.compressed_size -gt $boundary-$start){H5-Stop $C 'ranges' 'LOCAL_PAYLOAD_EXTENT' $i $lo 'compressed_size' $r.compressed_size ($boundary-$start)}
        $raw=H5-ReadAt $C $Stream ($lo+30) $nl
        if([Convert]::ToBase64String($raw) -cne [Convert]::ToBase64String($r.raw_name)){H5-Stop $C 'local' 'LOCAL_RAW_NAME_MISMATCH' $i ($lo+30) 'raw_name' 'different' 'central identical'}
        $r.local_extra_offset=$lo+30+$nl;$r.local_raw_extra=H5-ReadAt $C $Stream $r.local_extra_offset $xl
        $tail=$boundary-$start-$r.compressed_size
        $descriptor=($r.flags -band 8) -ne 0
        foreach($f in @(@('crc32',14),@('compressed_size',18),@('uncompressed_size',22))){$v=[long](H5-U32 $lh $f[1]);if(((-not $descriptor) -and $v -ne $r[$f[0]]) -or ($descriptor -and $v -ne 0 -and $v -ne $r[$f[0]])){H5-Stop $C 'local' ('LOCAL_'+$f[0].ToUpperInvariant()+'_MISMATCH') $i ($lo+$f[1]) $f[0] $v $r[$f[0]]}}
        if($descriptor){
            if($tail -notin @(12,16)){H5-Stop $C 'descriptor' 'DESCRIPTOR_EXACT_EXTENT' $i ($start+$r.compressed_size) 'extent' $tail '12 or 16'}
            $dd=H5-ReadAt $C $Stream ($start+$r.compressed_size) ([int]$tail);$dp=0
            if($tail -eq 16){if((H5-U32 $dd 0) -ne 134695760){H5-Stop $C 'descriptor' 'DESCRIPTOR_SIGNATURE' $i ($start+$r.compressed_size) 'signature' (H5-U32 $dd 0) 134695760};$dp=4}
            foreach($f in @(@('crc32',0),@('compressed_size',4),@('uncompressed_size',8))){$v=[long](H5-U32 $dd ($dp+$f[1]));if($v -ne $r[$f[0]]){H5-Stop $C 'descriptor' ('DESCRIPTOR_'+$f[0].ToUpperInvariant()+'_MISMATCH') $i ($start+$r.compressed_size+$dp+$f[1]) $f[0] $v $r[$f[0]]}}
        }elseif($tail -ne 0){H5-Stop $C 'ranges' 'LOCAL_UNCLAIMED_GAP' $i ($start+$r.compressed_size) 'gap' $tail 0}
        $r.payload_offset=$start;$r.range_end=$boundary;$r.descriptor_bytes=$tail;$r.local_bound=$true;$next=$boundary
    }
    if($next -ne $co){H5-Stop $C 'ranges' 'LOCAL_CENTRAL_UNCLAIMED_GAP' -1 $next 'next' $next $co}
    $d.local_bindings_complete=$true
    # Stage 3: all aliases/extras/type semantics, then duplicate hierarchy checks.
    $safe=$true;$keys=@{}
    foreach($r in $d.records){
        if(-not (H5-CentralLengths $C $r)){$safe=$false}
        $x=H5-Extras $C $r.raw_extra $r.raw_name $r.raw_comment $false $r.ordinal $r.central_extra_offset
        $lx=H5-Extras $C $r.local_raw_extra $r.raw_name ([byte[]]::new(0)) $true $r.ordinal $r.local_extra_offset
        $r.central_extras=$x.items;$r.local_extras=$lx.items
        # Exact nested OPC metadata is allowed by PathCheck without changing
        # raw names. Equal CRC-bound Unicode aliases pass the SAME semantics;
        # invalid or renamed aliases still block globally before payload.
        H5-NameSemantics $C $r $x $lx $Nested
        if(-not $r.semantic_safe){$safe=$false}
        if($null -ne $r.path){$key=$r.path.key;if($keys.ContainsKey($key)){H5-Problem $C 'semantics' 'PATH_CASE_OR_FILE_DIRECTORY_ALIAS' $r.ordinal $r.central_offset 'path_key' 'duplicate' 'unique';$safe=$false}else{$keys[$key]=$r}}
        if($null -ne $r.path -and $r.path.directory -and ($r.compressed_size -ne 0 -or $r.uncompressed_size -ne 0)){H5-Problem $C 'semantics' 'DIRECTORY_NONZERO_PAYLOAD' $r.ordinal $r.local_offset 'sizes' 'nonzero' 0;$safe=$false}
    }
    foreach($r in $d.records){if($null -eq $r.path){continue};$ps=$r.path.key.Split('/');$prefix='';for($j=0;$j -lt $ps.Length-1;$j++){$prefix+=$ps[$j];if($keys.ContainsKey($prefix) -and -not $keys[$prefix].path.directory){H5-Problem $C 'semantics' 'PATH_FILE_PARENT_CONFLICT' $r.ordinal $r.central_offset 'parent' 'file' 'directory';$safe=$false};$prefix+='/'}}
    $d.metadata_semantics_complete=$safe;$d.safe=$safe;return $d
}
function H5-Inventory($D) {
    $rows=[Collections.Generic.List[object]]::new()
    foreach($r in $D.records){$rows.Add([ordered]@{ordinal=$r.ordinal;central_offset=$r.central_offset;raw_name_base64=[Convert]::ToBase64String($r.raw_name);raw_name_sha256=(Sha-Bytes $r.raw_name);made_by=$r.made_by;host_system=$r.host_system;attribute_profile=$r.attribute_profile;interpreted_type=$r.interpreted_type;needed=$r.needed;flags=$r.flags;method=$r.method;dos_time=$r.dos_time;dos_date=$r.dos_date;crc32=$r.crc32;compressed_size=$r.compressed_size;uncompressed_size=$r.uncompressed_size;disk=$r.disk;internal_attributes=$r.internal_attributes;external_attributes=$r.external_attributes;raw_comment_base64=[Convert]::ToBase64String($r.raw_comment);local_offset=$r.local_offset;payload_offset=$r.payload_offset;range_end=$r.range_end;descriptor_bytes=$r.descriptor_bytes;local_bound=$r.local_bound;central_extras=$r.central_extras;local_extras=$r.local_extras;aliases_utf8_base64=$r.aliases_utf8_base64;semantic_safe=$r.semantic_safe;denied=$r.denied;selected=$r.selected;selection_kind=$r.selection_kind})}
    return [ordered]@{eocd_declared_count=$D.declared_count;actual_parsed_count=$D.parsed_count;central_records_complete=$D.central_records_complete;local_bindings_complete=$D.local_bindings_complete;metadata_semantics_complete=$D.metadata_semantics_complete;central_start=$D.central_start;central_sha256=$D.central_sha256;central_raw_base64=$D.central_raw_base64;records=@($rows.ToArray())}
}
function H5-Unpack($C,[byte[]]$Packed,$R,[int]$Maximum,[int]$Ratio) {
    H5-Tick $C
    if($R.method -notin @(0,8)){H5-Stop $C 'payload' 'SELECTED_METHOD_UNSUPPORTED' $R.ordinal $R.payload_offset 'method' $R.method '0/8'}
    if($R.uncompressed_size -gt $Maximum){H5-Stop $C 'payload' 'PAYLOAD_UNCOMPRESSED_SIZE_LIMIT' $R.ordinal $R.payload_offset 'uncompressed_size' $R.uncompressed_size $Maximum}
    if($R.compressed_size -gt 262144){H5-Stop $C 'payload' 'PAYLOAD_COMPRESSED_SIZE_LIMIT' $R.ordinal $R.payload_offset 'compressed_size' $R.compressed_size 262144}
    if($R.compressed_size -eq 0 -and $R.uncompressed_size -ne 0){H5-Stop $C 'payload' 'PAYLOAD_ZERO_COMPRESSED_NONEMPTY' $R.ordinal $R.payload_offset 'uncompressed_size' $R.uncompressed_size 0}
    if($R.compressed_size -gt 0 -and $R.uncompressed_size -gt $R.compressed_size*$Ratio){H5-Stop $C 'payload' 'PAYLOAD_EXPANSION_RATIO_LIMIT' $R.ordinal $R.payload_offset 'uncompressed_size' $R.uncompressed_size ($R.compressed_size*$Ratio)}
    if($R.method -eq 0){$out=$Packed}else{
        # The input stream contains exactly the selected compressed slice.
        $ms=[IO.MemoryStream]::new($Packed,$false);$df=$null;$out=[byte[]]::new([int]$R.uncompressed_size);$n=0;$fault=$null
        try{$df=[IO.Compression.DeflateStream]::new($ms,[IO.Compression.CompressionMode]::Decompress,$true);while($n -lt $out.Length){H5-Tick $C;$k=$df.Read($out,$n,$out.Length-$n);if($k -eq 0){break};$n+=$k};if($n -ne $out.Length -or $df.ReadByte() -ne -1){Fail 'DEFLATE_EXACT_LENGTH'}}catch{$fault=$_.Exception}finally{if($null -ne $df){try{$df.Dispose()}catch{H5-Problem $C 'payload' 'DEFLATE_DISPOSE_FAULT' $R.ordinal $R.payload_offset 'dispose' $_.Exception.GetType().FullName 'success';$fault=$_.Exception}};try{$ms.Dispose()}catch{$fault=$_.Exception}}
        if($null -ne $fault){H5-Stop $C 'payload' 'DEFLATE_DECODE_OR_DISPOSE_FAILED' $R.ordinal $R.payload_offset 'exception_type' $fault.GetType().FullName 'exact decompression'}
    }
    if($out.Length -ne $R.uncompressed_size){H5-Stop $C 'payload' 'PAYLOAD_LENGTH_MISMATCH' $R.ordinal $R.payload_offset 'length' $out.Length $R.uncompressed_size}
    $crc=H5-Crc $out;if($crc -ne $R.crc32){H5-Stop $C 'payload' 'PAYLOAD_CRC_MISMATCH' $R.ordinal $R.payload_offset 'crc32' $crc $R.crc32}
    return ,$out
}
function H5-Plain([byte[]]$Bytes) {
    $start=0;$encoding='UTF8';$decoder=[Text.UTF8Encoding]::new($false,$true)
    if($Bytes.Length -ge 3 -and $Bytes[0] -eq 239 -and $Bytes[1] -eq 187 -and $Bytes[2] -eq 191){$start=3;$encoding='UTF8_BOM'}
    elseif($Bytes.Length -ge 2 -and $Bytes[0] -eq 255 -and $Bytes[1] -eq 254){$start=2;$encoding='UTF16LE_BOM';$decoder=[Text.UnicodeEncoding]::new($false,$false,$true)}
    elseif($Bytes.Length -ge 2 -and $Bytes[0] -eq 254 -and $Bytes[1] -eq 255){$start=2;$encoding='UTF16BE_BOM';$decoder=[Text.UnicodeEncoding]::new($true,$false,$true)}
    $text=$decoder.GetString($Bytes,$start,$Bytes.Length-$start)
    foreach($ch in $text.ToCharArray()){if(([char]::IsControl($ch) -and $ch -notin @([char]9,[char]10,[char]13)) -or $ch -eq [char]0){Fail 'PLAIN_BINARY_CONTROL'}}
    return @{encoding=$encoding;text=$text;derived_utf8=[Text.UTF8Encoding]::new($false,$true).GetBytes($text)}
}
function H5-Preview([byte[]]$B,[bool]$Utf8,[int]$Limit=4096) {
    $n=[Math]::Min($Limit,$B.Length)
    if($Utf8 -and $n -lt $B.Length){while($n -gt 0 -and ($B[$n] -band 192) -eq 128){$n--}}
    return ,(H5-Slice $B 0 $n)
}
function H5-Transport($C,[int]$Ordinal,[int]$Container,[string]$Kind,[byte[]]$Bytes,[string]$OriginalEncoding,[bool]$Utf8=$false) {
    $r=[ordered]@{ordinal=$Ordinal;container_ordinal=$Container;kind=$Kind;original_bytes=$Bytes.Length;original_sha256=(Sha-Bytes $Bytes);original_crc32=(H5-Crc $Bytes);original_encoding=$OriginalEncoding;transport_encoding='identity-base64';full=$true;payload_base64=[Convert]::ToBase64String($Bytes);preview_bytes=$null;unresolved=$null}
    $trial=@($C.documents.ToArray())+@($r)
    if((H5-JsonBytes $trial).Length -le 32768){$C.documents.Add($r);return}
    # Fixed nonexpandable byte[] output: successful Write AND Dispose required.
    $back=[byte[]]::new(32768);$ms=[IO.MemoryStream]::new($back,$true);$ms.SetLength(0);$ms.Position=0;$gz=$null;$gzipOk=$false
    try{$gz=[IO.Compression.GZipStream]::new($ms,[IO.Compression.CompressionMode]::Compress,$true);$gz.Write($Bytes,0,$Bytes.Length);$gz.Dispose();$gz=$null;$gzipOk=$true}catch{$gzipOk=$false}finally{if($null -ne $gz){try{$gz.Dispose()}catch{$gzipOk=$false}}}
    if($gzipOk){$r.transport_encoding='gzip-base64';$r.payload_base64=[Convert]::ToBase64String($back,0,[int]$ms.Length);if((H5-JsonBytes (@($C.documents.ToArray())+@($r))).Length -le 32768){try{$ms.Dispose()}catch{$gzipOk=$false};if($gzipOk){$C.documents.Add($r);return}}}
    try{$ms.Dispose()}catch{H5-Problem $C 'transport' 'GZIP_BUFFER_DISPOSE_FAULT' $Ordinal -1 'exception_type' $_.Exception.GetType().FullName 'success' $Container}
    $r.full=$false;$r.transport_encoding='identity-base64';$r.unresolved='EVIDENCE_TRANSPORT_UNRESOLVED'
    $preview=H5-Preview $Bytes $Utf8 4096;$r.preview_bytes=$preview.Length;$r.payload_base64=[Convert]::ToBase64String($preview)
    if((H5-JsonBytes (@($C.documents.ToArray())+@($r))).Length -le 32768){$C.documents.Add($r);H5-Problem $C 'transport' 'EVIDENCE_TRANSPORT_UNRESOLVED' $Ordinal -1 'full' $false $true $Container;return}
    $r.preview_bytes=0;$r.payload_base64=''
    if((H5-JsonBytes (@($C.documents.ToArray())+@($r))).Length -le 32768){$C.documents.Add($r)}
    H5-Stop $C 'transport' 'DOCUMENT_AGGREGATE_JSON_LIMIT' $Ordinal -1 'serialized_bytes' '>32768' 32768
}
function H5-XmlBody($C,[byte[]]$Bytes) {
    $settings=[Xml.XmlReaderSettings]::new();$settings.DtdProcessing=[Xml.DtdProcessing]::Prohibit;$settings.XmlResolver=$null;$settings.ValidationType=[Xml.ValidationType]::None;$settings.MaxCharactersInDocument=524288;$settings.MaxCharactersFromEntities=0;$settings.CloseInput=$false
    $ms=[IO.MemoryStream]::new($Bytes,$false);$reader=$null;$builder=[Text.StringBuilder]::new();$nodes=0;$bodyCount=0;$bodyDepth=-1;$textDepth=-1;$rootSeen=$false;$ns=$null;$fault=$null
    $counts=[ordered]@{fields=0;math=0;drawing=0;altChunk=0;revisions=0;other_story_references=0;foreign_elements=0;no_break_hyphen=0;symbols=0;unsupported_wml_content=0;omitted_text_nodes=0}
    $namespaces=@('http://schemas.openxmlformats.org/wordprocessingml/2006/main','http://purl.oclc.org/ooxml/wordprocessingml/main')
    try{
        $reader=[Xml.XmlReader]::Create($ms,$settings)
        while($reader.Read()){
            H5-Tick $C;$nodes++
            if($nodes -gt 100000){Fail 'XML_NODE_LIMIT'}
            if($reader.Depth -gt 64){Fail 'XML_DEPTH_LIMIT'}
            if($reader.AttributeCount -gt 64){Fail 'XML_ATTRIBUTE_LIMIT'}
            if($reader.NodeType -eq [Xml.XmlNodeType]::DocumentType -or $reader.NodeType -eq [Xml.XmlNodeType]::EntityReference){Fail 'XML_DTD_ENTITY_FORBIDDEN'}
            if($reader.NodeType -eq [Xml.XmlNodeType]::Element){
                # w:t is leaf text. Any element child (including another w:t)
                # would make the scalar text scope ambiguous; reject before it
                # can reset textDepth and silently discard following text.
                if($textDepth -ge 0){Fail 'XML_TEXT_ELEMENT_CHILD_FORBIDDEN'}
                if(-not $rootSeen){if($reader.Depth -ne 0 -or $reader.LocalName -cne 'document' -or $namespaces -cnotcontains $reader.NamespaceURI){Fail 'XML_WORD_DOCUMENT_ROOT'};$rootSeen=$true;$ns=$reader.NamespaceURI}
                if($reader.NamespaceURI -ceq $ns){
                    $name=$reader.LocalName
                    if($name -ceq 'body'){if($reader.Depth -ne 1 -or $bodyCount -ne 0){Fail 'XML_WORD_BODY_AMBIGUOUS'};$bodyCount++;if(-not $reader.IsEmptyElement){$bodyDepth=$reader.Depth}}
                    if($name -in @('fldSimple','fldChar','instrText')){$counts.fields++}
                    if($name -in @('drawing','pict','object')){$counts.drawing++}
                    if($name -ceq 'altChunk'){$counts.altChunk++}
                    if($name -in @('ins','del','moveFrom','moveTo','delText','moveFromRangeStart','moveToRangeStart')){$counts.revisions++}
                    if($name -in @('footnoteReference','endnoteReference','headerReference','footerReference','commentReference','subDoc')){$counts.other_story_references++}
                    if($name -ceq 'noBreakHyphen'){$counts.no_break_hyphen++}
                    if($name -ceq 'sym'){$counts.symbols++}
                    # Fixed formatter coverage is intentionally narrow. Other
                    # same-namespace elements (including formatting/property
                    # constructs) are conservatively unresolved, never silently
                    # promoted to understood content or newly rendered output.
                    $handled=@('document','body','p','r','t','tab','br','cr','tbl','tr','tc','fldSimple','fldChar','instrText','drawing','pict','object','altChunk','ins','del','moveFrom','moveTo','delText','moveFromRangeStart','moveToRangeStart','footnoteReference','endnoteReference','headerReference','footerReference','commentReference','subDoc','noBreakHyphen','sym')
                    if($name -cnotin $handled){$counts.unsupported_wml_content++}
                    if($bodyDepth -ge 0 -and $reader.Depth -gt $bodyDepth){
                        if($name -ceq 't' -and -not $reader.IsEmptyElement){$textDepth=$reader.Depth}
                        if($name -ceq 'tab'){$null=$builder.Append([char]9)}
                        if($name -in @('br','cr')){$null=$builder.Append([char]10)}
                        if($reader.IsEmptyElement -and $name -in @('p','tc','tr')){if($name -ceq 'tc'){$null=$builder.Append([char]9)}else{$null=$builder.Append([char]10)}}
                    }
                }else{
                    if($reader.NamespaceURI -in @('http://schemas.openxmlformats.org/officeDocument/2006/math','http://purl.oclc.org/ooxml/officeDocument/math')){$counts.math++}else{$counts.foreign_elements++}
                }
            }elseif($reader.NodeType -eq [Xml.XmlNodeType]::EndElement){
                if($reader.NamespaceURI -ceq $ns){
                    if($reader.LocalName -ceq 't' -and $reader.Depth -eq $textDepth){$textDepth=-1}
                    if($bodyDepth -ge 0 -and $reader.Depth -gt $bodyDepth){if($reader.LocalName -in @('p','tr')){$null=$builder.Append([char]10)}elseif($reader.LocalName -ceq 'tc'){$null=$builder.Append([char]9)}}
                    if($reader.LocalName -ceq 'body' -and $reader.Depth -eq $bodyDepth){$bodyDepth=-1}
                }
            }elseif($reader.NodeType -in @([Xml.XmlNodeType]::Text,[Xml.XmlNodeType]::CDATA,[Xml.XmlNodeType]::Whitespace,[Xml.XmlNodeType]::SignificantWhitespace)){
                if($textDepth -ge 0 -and $bodyDepth -ge 0){$null=$builder.Append($reader.Value)}
                elseif($bodyDepth -ge 0 -and $reader.Value.Trim().Length -gt 0){$counts.omitted_text_nodes++}
            }
            if($builder.Length -gt 524288){Fail 'XML_DERIVED_CHARACTER_LIMIT'}
        }
        if(-not $rootSeen -or $bodyCount -ne 1){Fail 'XML_WORD_BODY_MISSING'}
    }catch{$fault=$_.Exception}finally{
        if($null -ne $reader){try{$reader.Dispose()}catch{$fault=$_.Exception;H5-Problem $C 'xml' 'XML_READER_DISPOSE_FAULT' -1 -1 'exception_type' $_.Exception.GetType().FullName 'success'}}
        try{$ms.Dispose()}catch{$fault=$_.Exception;H5-Problem $C 'xml' 'XML_STREAM_DISPOSE_FAULT' -1 -1 'exception_type' $_.Exception.GetType().FullName 'success'}
    }
    if($null -ne $fault){$code='XML_PARSE_OR_DISPOSE_FAILED';$e=$fault;for($i=0;$i -lt 8;$i++){if($e.Data.Contains('Route2FixedCode')){$code=[string]$e.Data['Route2FixedCode']};if($null -eq $e.InnerException){break};$e=$e.InnerException};H5-Stop $C 'xml' $code -1 -1 'exception_type' $e.GetType().FullName 'bounded safe Word XML'}
    $utf8=[Text.UTF8Encoding]::new($false,$true).GetBytes($builder.ToString());if($utf8.Length -gt 524288){H5-Stop $C 'xml' 'XML_DERIVED_UTF8_LIMIT' -1 -1 'bytes' $utf8.Length 524288}
    return @{bytes=$utf8;namespace=$ns;nodes=$nodes;unrendered_counts=$counts;formatter='docx-fixed-body-v1';scope='DOCX_FIXED_PART_BODY_ONLY';full_document_rendered=$false;unrendered_relevant_content_unresolved=(@($counts.Values|Where-Object{$_ -gt 0}).Count -gt 0)}
}
function H5-Docx($C,[byte[]]$Bytes,[int]$Container) {
    $nctx=H5-NewContext $C.deadline;$nested=$null;$stream=[IO.MemoryStream]::new($Bytes,$false);$summary=[ordered]@{container_ordinal=$Container;scope='DOCX_FIXED_PART_BODY_ONLY';whole_outer_container_encoded_bytes_read=$true;full_document_rendered=$false;nested_inventory_complete=$false;nested_declared_count=$null;nested_parsed_count=0;nested_central_sha256=$null;xml_ordinal=$null;xml_offset=$null;xml_encoding='XML_ORIGINAL_BYTES_WITH_DECLARATION_OR_BOM';derived_encoding='UTF8';formatter='docx-fixed-body-v1';unrendered_counts=$null;unrendered_relevant_content_unresolved=$true}
    try{
        $nested=H5-Directory $nctx $stream $Bytes.Length -1 '' $true
        $summary.nested_declared_count=$nested.declared_count;$summary.nested_parsed_count=$nested.parsed_count;$summary.nested_central_sha256=$nested.central_sha256;$summary.nested_inventory_complete=$nested.safe
        if(-not $nested.safe){Fail 'DOCX_NESTED_METADATA_UNRESOLVED'}
        $target=@($nested.records.ToArray()|Where-Object{$null -ne $_.path -and $_.path.name -ceq 'word/document.xml' -and -not $_.path.directory})
        if($target.Length -ne 1){Fail 'DOCX_FIXED_PART_NOT_UNIQUE'}
        $r=$target[0];$summary.xml_ordinal=$r.ordinal;$summary.xml_offset=$r.payload_offset
        if($r.method -notin @(0,8)){H5-Stop $C 'docx' 'DOCX_XML_METHOD_UNSUPPORTED' $r.ordinal $r.payload_offset 'method' $r.method @(0,8)}
        if($r.uncompressed_size -gt 524288){H5-Stop $C 'docx' 'DOCX_XML_UNCOMPRESSED_SIZE_LIMIT' $r.ordinal $r.payload_offset 'uncompressed_size' $r.uncompressed_size 524288}
        if($r.compressed_size -gt 262144){H5-Stop $C 'docx' 'DOCX_XML_COMPRESSED_SIZE_LIMIT' $r.ordinal $r.payload_offset 'compressed_size' $r.compressed_size 262144}
        if($r.compressed_size -eq 0 -and $r.uncompressed_size -ne 0){H5-Stop $C 'docx' 'DOCX_XML_ZERO_COMPRESSED_NONEMPTY' $r.ordinal $r.payload_offset 'uncompressed_size' $r.uncompressed_size 0}
        if($r.compressed_size -gt 0 -and $r.uncompressed_size -gt $r.compressed_size*100){H5-Stop $C 'docx' 'DOCX_XML_EXPANSION_RATIO_LIMIT' $r.ordinal $r.payload_offset 'uncompressed_size' $r.uncompressed_size ($r.compressed_size*100)}
        if($C.xml_total -gt 1048576-$r.uncompressed_size){H5-Stop $C 'docx' 'DOCX_XML_TOTAL_LIMIT' $r.ordinal $r.payload_offset 'xml_total_bytes' ($C.xml_total+$r.uncompressed_size) 1048576}
        $C.xml_total+=$r.uncompressed_size
        $packed=H5-ReadAt $nctx $stream $r.payload_offset ([int]$r.compressed_size) 'payload' $r.ordinal $Container
        $xml=H5-Unpack $nctx $packed $r 524288 100
        # Raw XML remains its original bytes. No implicit UTF8 relabeling.
        H5-Transport $C $r.ordinal $Container 'docx_raw_word_document_xml' $xml 'XML_ORIGINAL_BYTES' $false
        $body=H5-XmlBody $nctx $xml
        H5-Transport $C $r.ordinal $Container 'docx_derived_body' $body.bytes 'UTF8_DERIVED_BODY' $true
        $summary['word_namespace']=$body.namespace;$summary['xml_nodes']=$body.nodes;$summary.unrendered_counts=$body.unrendered_counts;$summary.unrendered_relevant_content_unresolved=$body.unrendered_relevant_content_unresolved
    }finally{
        if($null -eq $nested){$nested=$nctx.directory}
        if($null -ne $nested){$summary.nested_declared_count=$nested.declared_count;$summary.nested_parsed_count=$nested.parsed_count;$summary.nested_central_sha256=$nested.central_sha256;$summary.nested_inventory_complete=$nested.safe}
        foreach($r in $nctx.reads){$r.container_ordinal=$Container;$C.reads.Add($r)}
        foreach($e in $nctx.errors){$e.container_ordinal=$Container;if($C.errors.Count -lt 32 -and (H5-JsonBytes (@($C.errors.ToArray())+@($e))).Length -le 8192){$C.errors.Add($e)}else{$C.errors_overflow=$true}}
        if($nctx.errors_overflow){$C.errors_overflow=$true}
        $C.structural_charged+=$nctx.structural_charged;$C.structural_returned+=$nctx.structural_returned
        $C.facts.docx.Add($summary)
        try{$stream.Dispose()}catch{H5-Stop $C 'docx' 'DOCX_CONTAINER_DISPOSE_FAULT' -1 -1 'exception_type' $_.Exception.GetType().FullName 'success'}
    }
}
function H5-Inspect($C,[IO.Stream]$Stream,[long]$ExpectedLength,[int]$ExpectedCount,[string]$ExpectedCentral) {
    $facts=[ordered]@{schema='route2_h5_official_nongt_inspection_facts_v2';policy_id='route2-h5-official-nongt-inspection-2026-10-16-002';collection_complete=$false;central_records_complete=$false;local_bindings_complete=$false;metadata_semantics_complete=$false;directory_transport_complete=$false;selection_complete=$false;selected_evidence_complete=$false;archive_sha256='UNVERIFIED';status='STARTED';inventory=$null;directory=$null;documents=@();docx_container_evidence=@();docx=[Collections.Generic.List[object]]::new();errors=@();errors_overflow=$false;reads=@();structural_candidate_bytes_charged=0;structural_read_returned_bytes=0;selected_payload_reads=@();selected_payload_attempted_bytes=0;selected_payload_returned_bytes=0;formal_compatibility='UNRESOLVED';full_document_rendered=$false;stage_admission='NOT_GRANTED'}
    $C.facts=$facts
    try{
        $d=H5-Directory $C $Stream $ExpectedLength $ExpectedCount $ExpectedCentral
        if(-not $d.safe){Fail 'METADATA_SEMANTICS_UNRESOLVED'}
        # Stage 4: deny all ORIGINAL aliases already ran, before wrapper removal.
        $files=@($d.records.ToArray()|Where-Object{$null -ne $_.path -and -not $_.path.directory});$wrapper=''
        if($files.Length -gt 0){$first=$files[0].path.parts;if($first.Length -gt 1){$candidate=$first[0];$same=$true;foreach($r in $files){if($r.path.parts.Length -le 1 -or $r.path.parts[0] -cne $candidate){$same=$false}};if($same){$wrapper=$candidate}}}
        $selected=[Collections.Generic.List[object]]::new();$docxCount=0
        foreach($r in $files){
            if($r.denied){$r.selection_kind='DENIED_ORIGINAL_ALIAS';continue}
            $kind=H5-Positive $r.path.name $wrapper
            if($null -eq $kind){$r.selection_kind='INVENTORY_ONLY_NONCANDIDATE_UNRESOLVED';continue}
            $r.selected=$true;$r.selection_kind=$kind;$selected.Add($r);if($kind -ceq 'docx'){$docxCount++}
        }
        $facts.selection_complete=$true
        H5-SelectedCounts $C $selected.Count $docxCount
        # Validate EVERY selected member's eligibility before opening the first.
        foreach($r in $selected){
            H5-SelectedMember $C $r
            $C.compressed_total+=$r.compressed_size;$C.uncompressed_total+=$r.uncompressed_size
        }
        H5-SelectedTotals $C $C.compressed_total $C.uncompressed_total
        $inventory=H5-Inventory $d
        if((H5-JsonBytes $inventory).Length -gt 16384){H5-Stop $C 'transport' 'INVENTORY_JSON_LIMIT' -1 -1 'serialized_bytes' (H5-JsonBytes $inventory).Length 16384}
        $facts.inventory=$inventory;$facts.directory_transport_complete=$true
        foreach($r in $selected){
            $packed=H5-ReadAt $C $Stream $r.payload_offset ([int]$r.compressed_size) 'payload' $r.ordinal
            $bytes=H5-Unpack $C $packed $r 262144 20
            if($r.selection_kind -ceq 'docx'){
                # Container bytes include encoded nonselected parts. They are
                # acknowledged, never represented as excluded byte contact.
                $facts['docx_container_evidence']=@($facts.docx_container_evidence)+@(@{ordinal=$r.ordinal;bytes=$bytes.Length;sha256=(Sha-Bytes $bytes);crc32=(H5-Crc $bytes);whole_encoded_container_read=$true})
                H5-Docx $C $bytes $r.ordinal
            }else{
                $plain=H5-Plain $bytes
                H5-Transport $C $r.ordinal -1 'plain_original' $bytes $plain.encoding ($plain.encoding -in @('UTF8','UTF8_BOM'))
                # A decoded text view is distinct; original UTF16 bytes/hash
                # remain unchanged even though the derived view uses UTF8.
                if($plain.encoding -like 'UTF16*'){H5-Transport $C $r.ordinal -1 'plain_derived_utf8' $plain.derived_utf8 'UTF8_DERIVED_FROM_BOM_UTF16' $true}
            }
        }
        $facts.selected_evidence_complete=(@($C.documents.ToArray()|Where-Object{-not $_.full}).Count -eq 0)
        $facts.collection_complete=$facts.selected_evidence_complete -and -not $C.errors_overflow
        $facts.status=$(if($facts.collection_complete){'BOUNDED_EVIDENCE_ONLY'}else{'EVIDENCE_TRANSPORT_UNRESOLVED'})
    }catch{
        $e=$_.Exception;$code='INSPECTION_OPERATION_FAILED';for($j=0;$j -lt 8;$j++){if($e.Data.Contains('Route2FixedCode')){$code=[string]$e.Data['Route2FixedCode']};if($null -eq $e.InnerException){break};$e=$e.InnerException}
        H5-Problem $C 'inspection' $code -1 -1 'exception_type' $e.GetType().FullName 'complete bounded evidence'
        $facts['failure']=@{code=$code;error_type=$e.GetType().FullName;hresult=[int]$e.HResult};$facts.status='FAILED_PARTIAL';$facts.collection_complete=$false
    }finally{
        $d=$facts.directory
        if($null -ne $d){$facts.central_records_complete=$d.central_records_complete;$facts.local_bindings_complete=$d.local_bindings_complete;$facts.metadata_semantics_complete=$d.metadata_semantics_complete;if($null -eq $facts.inventory){$inv=H5-Inventory $d;if((H5-JsonBytes $inv).Length -le 16384){$facts.inventory=$inv;$facts.directory_transport_complete=$true}else{$facts['inventory_transport_unresolved']=$true;$facts['parsed_count_without_full_inventory']=$d.parsed_count}}}
        $facts.Remove('directory');$facts.documents=@($C.documents.ToArray());$facts.docx=@($facts.docx.ToArray());$facts.errors=@($C.errors.ToArray());$facts.errors_overflow=$C.errors_overflow;$facts.structural_candidate_bytes_charged=$C.structural_charged;$facts.structural_read_returned_bytes=$C.structural_returned
        # Per-read structural records stay internal; expose their exact aggregate
        # and uncertainty counts, avoiding hundreds of nested metadata rows from
        # crowding out the fixed evidence transport. Payload rows are never lost.
        $struct=@($C.reads.ToArray()|Where-Object{$_.kind -ceq 'structural'})
        $facts['structural_read_count']=$struct.Count
        $facts['structural_incomplete_read_count']=@($struct|Where-Object{-not $_.complete}).Count
        $facts['structural_partial_bytes_unknown_count']=@($struct|Where-Object{$_.partial_bytes_unknown}).Count
        $facts['structural_per_read_detail']='AGGREGATE_ONLY_CHARGED_RETURNED_AND_UNCERTAINTY_COUNTS'
        $facts.reads=@{scope='STRUCTURAL_AGGREGATES_AND_SEPARATE_SELECTED_PAYLOAD_ROWS';structural_requested_and_charged=$C.structural_charged;structural_returned=$C.structural_returned;structural_read_count=$struct.Count}
        $payload=@($C.reads.ToArray()|Where-Object{$_.kind -ceq 'payload'});$facts.selected_payload_reads=$payload
        foreach($r in $payload){$facts.selected_payload_attempted_bytes+=$r.requested_bytes;$facts.selected_payload_returned_bytes+=$r.returned_bytes}
    }
    return $facts
}
function Collect-Inspection {
    $c=H5-NewContext $script:ActiveStop;$stream=$null;$length=$null;$facts=$null
    try{
        Check-Active
        # ONLY archive open site: fixed literal, readonly/mutation-denying handle.
        $fixedInput=ConvertFrom-Json '"E:/e091f6df5b8f4fd1a62a5e43dda404b1_\u8d5b\u98982.zip"'
        $stream=[IO.FileStream]::new($fixedInput,[IO.FileMode]::Open,[IO.FileAccess]::Read,[IO.FileShare]::Read,1,[IO.FileOptions]::RandomAccess)
        $length=$stream.Length
        $facts=H5-Inspect $c $stream 42549 10 '0b72b03ee9129dfaf4ba175f6bc838c09ca360c9fe11ba425df7cf6a2093370a'
    }catch{
        if($null -eq $facts){$facts=[ordered]@{schema='route2_h5_official_nongt_inspection_facts_v2';collection_complete=$false;status='ARCHIVE_OPEN_OR_COLLECTION_FAILED';archive_sha256='UNVERIFIED';stage_admission='NOT_GRANTED'}}
        # A helper-finalization failure cannot erase already attempted reads.
        $facts['structural_candidate_bytes_charged']=$c.structural_charged
        $facts['structural_read_returned_bytes']=$c.structural_returned
        $facts['selected_payload_reads']=@($c.reads.ToArray()|Where-Object{$_.kind -ceq 'payload'})
        $facts['partial_facts_transport_unresolved']=$true
        $facts['open_or_collection_failure']=@{error_type=$_.Exception.GetType().FullName;hresult=[int]$_.Exception.HResult}
    }finally{
        if($null -ne $stream){try{if($stream.Length -ne $length){$facts.collection_complete=$false;$facts['length_changed_on_close']=$true}}catch{$facts.collection_complete=$false;$facts['final_length_check_failed']=$true};try{$stream.Dispose()}catch{$facts.collection_complete=$false;$facts['archive_dispose_failed']=$true}}
    }
    return $facts
}

try {
    if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT -or [IntPtr]::Size -ne 8) { Fail 'REQUIRES_64BIT_WINDOWS' }
    if ($PSVersionTable.PSVersion.Major -ne 5 -or $PSVersionTable.PSVersion.Minor -ne 1 -or $PSVersionTable.PSEdition -cne 'Desktop') { Fail 'REQUIRES_WINDOWS_POWERSHELL_5_1_DESKTOP' }
    if ($ActivationSha256 -cnotmatch '^[0-9a-f]{64}$') { Fail 'EXACT_ACTIVATION_SHA256_REQUIRED_OWNER_NOT_APPROVED' }
    if ($PolicySha256 -cnotmatch '^[0-9a-f]{64}$') { Fail 'POLICY_NOT_FROZEN' }
    $scriptPath = [IO.Path]::GetFullPath($PSCommandPath)
    $expectedScript='E:\bme_compitition\.worktrees\high-f1-event-stack-execution\bme_compitition_next\scripts\route2_official_package_inspection_v2.ps1'
    if ($scriptPath -match '["\r\n]' -or -not [string]::Equals($scriptPath,$expectedScript,[StringComparison]::OrdinalIgnoreCase)) { Fail 'FIXED_SCRIPT_PATH_REQUIRED' }
    $repoRoot = [IO.Directory]::GetParent([IO.Path]::GetDirectoryName($scriptPath)).FullName
    $receiptPath = [IO.Path]::Combine($repoRoot, 'docs\decisions\2026-09-27-route2-design-review.md')
    $pin = [IO.File]::Open($scriptPath, [IO.FileMode]::Open, [IO.FileAccess]::Read, [IO.FileShare]::Read)
    if ($pin.Length -gt 262144) { Fail 'SCRIPT_SOURCE_TOO_LARGE' }
    $sha = [Security.Cryptography.SHA256]::Create()
    try { $sourceSha = ([BitConverter]::ToString($sha.ComputeHash($pin))).Replace('-', '').ToLowerInvariant() }
    finally { $sha.Dispose() }
    $document = [Text.UTF8Encoding]::new($false, $true).GetString((Read-Bounded $receiptPath 4194304))
    $policyLines=[regex]::Matches($document,'(?m)^\{"schema":"route2_h5_official_nongt_inspection_policy_v2",[^\r\n]*\}')
    if ($policyLines.Count -ne 1 -or $policyLines[0].Value.Length -ne 16305 -or $policyLines[0].Value -cmatch '[^\x20-\x7e]' -or (Sha-Bytes ([Text.Encoding]::ASCII.GetBytes($policyLines[0].Value))) -cne $PolicySha256) { Fail 'EXACT_H5_V2_CANONICAL_POLICY_REQUIRED' }
    $begin = '<!-- ROUTE2_H5_OFFICIAL_NONGT_INSPECTION_ACTIVATION_V1_BEGIN -->'
    $end = '<!-- ROUTE2_H5_OFFICIAL_NONGT_INSPECTION_ACTIVATION_V1_END -->'
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
    $pattern = '^\{"schema":"route2_h5_official_nongt_inspection_activation_v1","policy_id":"' + [regex]::Escape($PolicyId) + '","source_sha256":"[0-9a-f]{64}","contract_sha256":"[0-9a-f]{64}","owner_message_sha256":"[0-9a-f]{64}","owner_approval_reference":"[A-Za-z0-9:/._-]{1,200}","invocation_nonce":"[0-9a-f]{32}","one_shot_state":"CONSUMED_FOR_THIS_INVOCATION","parent_pid":[1-9][0-9]{0,9},"qpc_epoch":[1-9][0-9]{0,18},"qpc_frequency":[1-9][0-9]{0,9},"active_stop_qpc":[1-9][0-9]{0,18},"cleanup_stop_qpc":[1-9][0-9]{0,18},"active_seconds":120,"cleanup_seconds":60,"total_seconds":180,"max_attempts":1,"exception_ids":"' + [regex]::Escape($ExceptionIds) + '"\}$'
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
        # complete immutable Windows module/loader closure remains unproved H5.
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
        $childCompleted = $true
        Check-Active
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
    $phase = 'APPROVED_H5_OFFICIAL_INSPECTION_ATTEMPT_CONSUMED'
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
    $phase = 'MONITORING_H5_FIXED_CHILD'
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
        # an unmonitored CPU tail inside this same original H5 attempt.
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
    $childFault = [ordered]@{schema='route2_h5_fixed_child_failure_v1';primary_fault=$primaryFault;error_type=$primaryErrorType;hresult=$primaryHResult;cleanup_faults=$cleanupFaults.ToArray();record_written=$childCompleted;collection_complete=$childCollectionComplete;active_stop_missed=$childLate}
    $childFaultBytes = [Text.UTF8Encoding]::new($false, $true).GetBytes(($childFault | ConvertTo-Json -Depth 4 -Compress))
    if ($childFaultBytes.Length -le 4096) {
        $childStderr = [Console]::OpenStandardError()
        $childStderr.Write($childFaultBytes, 0, $childFaultBytes.Length)
        $childStderr.Flush()
    } else { [Console]::Error.WriteLine('H5_FIXED_CHILD_REFUSED_OR_FAILED') }
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
    schema='route2_h5_official_nongt_inspection_result_v1';policy_id=$PolicyId;source_sha256=$sourceSha;contract_sha256=$PolicySha256
    phase=$phase;primary_fault=$primaryFault;primary_error_type=$primaryErrorType;primary_hresult=$primaryHResult;cleanup_faults=$cleanupFaults.ToArray();observed_resource_violations=$violations.ToArray()
    invocation_nonce=$InvocationNonce;original_qpc_epoch=$OriginalEpoch;qpc_frequency=$frequency;active_stop_qpc=$ActiveStop;cleanup_stop_qpc=$CleanupStop;result_qpc=(Now)
    original_child_start_attempted=$startAttempted;original_child_started=$started;original_process_joined=$joined;original_exit_dword=$exitDword;kill_requested=$killRequested;outstanding_read_tasks=$outstanding;unharvested_read_tasks=$unharvested
    stdout_read_state=(Capture-State $outState);stderr_read_state=(Capture-State $errState)
    stdout_base64=$rawOut;stderr_base64=$rawErr;stdout_capacity_bytes=65537;stderr_capacity_bytes=8193;child_record_limit_bytes=65536;parent_record_limit_bytes=131072
    process_image_path_observed=$processImage;process_image_handle_identity='UNPROVEN_SCOPED_H5_EXCEPTION'
    observed_parent_working_set_peak=$maxParentWs;observed_child_working_set_peak=$maxChildWs;observed_combined_working_set_peak=$maxCombinedWs;observed_combined_application_threads_peak=$maxThreads;resource_samples=$resourceSamples;unsampled_resources='UNKNOWN_NOT_ZERO'
    observed_parent_threads_peak=$maxParentThreads;cleanup_live_resource_samples=$cleanupLiveSamples;cleanup_parent_only_samples=$cleanupParentOnlySamples;cleanup_resource_sample_failures=$cleanupSampleFailures;last_cleanup_resource_sample_qpc=$lastCleanupSampleQpc;final_parent_resource_sample_qpc=$finalParentSampleQpc
    child_postexit_resources='UNKNOWN_NOT_ZERO_NOT_QUERIED_AFTER_ORIGINAL_PROCESS_JOIN';post_final_sample_resources='DISPOSAL_SERIALIZATION_FLUSH_KERNEL_SERVICE_PROVIDER_TAILS_UNKNOWN_NOT_ZERO'
    child_start_call_qpc=$childStartCallQpc;child_start_returned_qpc=$childStartReturnedQpc;monitor_cadence_baseline_qpc=$monitorBaselineQpc;first_complete_resource_sample_qpc=$firstResourceSampleQpc
    resource_start_interval='ORIGINAL_EPOCH_THROUGH_FIRST_COMPLETE_SAMPLE_UNOBSERVED_NOT_ZERO_NO_100MS_COVERAGE_CLAIM'
    cpu_scope='AFFINITY_PARENT_CHILD_SAME_ONE_CORE_AFTER_SET_FIRST_LOADER_UNPROVEN'
    parent_affinity_disposition='RETAINED_ONE_CORE_THROUGH_FINAL_OUTPUT'
    thread_scope='H5_MONITORED64_ONLY_ORIGINAL_FORMAL_FOUR_UNCHANGED'
    root_startup_creator_primary_thread_closure='UNPROVEN_SCOPED_H5_EXCEPTION'
    complete_ram_kernel_service_physical_all_fees='UNKNOWN_NOT_ZERO'
    runtime_service_infrastructure='NOT_JOINED_EXITED_SHARED_RUNTIME_SERVICE_TAIL_UNKNOWN_NOT_ZERO'
    hard_deadline_proof='UNPROVEN_SAMPLED_COOPERATIVE_EXCEPTION_NO_UNBILLED_DRAIN'
    receipt_provenance='TRUSTED_ROOT_ACTUAL_OWNER_MESSAGE_AND_DURABLE_CONSUMPTION_REQUIRED_NOT_AUTHENTICATED_BY_THIS_SCRIPT'
    budget_verdict='UNKNOWN_NOT_ZERO_NEVER_PASS';stage_admission='NOT_GRANTED';disk_plan_target_authority='NOT_GRANTED';h1='APPROVED_UNSTARTED';h3='CONSUMED_FAILED_PARTIAL_NO_RETRY';h4='CONSUMED_FAILED_PARTIAL_NO_RETRY';old_history='UNKNOWN_NOT_ZERO'
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
if ($encoded.Length -gt 131072) { [Console]::Error.WriteLine('H5_PARENT_RESULT_SHAPE_EXCEEDED'); exit 1 }
$stdout = [Console]::OpenStandardOutput()
if ($CleanupStop -gt 0 -and (Now) -ge $CleanupStop) { $outputLate = $true }
try {
    $stdout.Write($encoded, 0, $encoded.Length)
    $stdout.Flush()
} catch { [Console]::Error.WriteLine('H5_PARENT_OUTPUT_WRITE_OR_FLUSH_FAULT'); exit 1 }
# A printed provisional record never overrides a late flush or serialization.
if ($CleanupStop -gt 0 -and (Now) -ge $CleanupStop) { $outputLate = $true }
if ($outputLate) { [Console]::Error.WriteLine('H5_PARENT_OUTPUT_AFTER_ABSOLUTE_CLEANUP_STOP_UNKNOWN_FEES'); exit 1 }
if ($null -ne $primaryFault -or $cleanupFaults.Count -gt 0 -or -not $joined -or $exitDword -ne 0 -or $unharvested.Count -gt 0 -or $wireShapeFault) { exit 1 }
# Exit zero reports only that this fixed child returned and was joined; every
# budget/admission field above remains explicitly non-passing.
exit 0
