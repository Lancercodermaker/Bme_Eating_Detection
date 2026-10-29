# SOURCE ONLY. Qualified Windows C00 gauges. Loading defines functions only.
# Entry calls these continuations inside ORIGINAL ordinary ledger steps (48 calls,
# never Observer). Each transition performs at most three fixed native APIs; all
# ledger QPC/operation/allocator calls remain charged. A complete cycle, including
# all caller scheduling gaps, has the SAME 100 ms ceiling. No runtime gate claim.
# Required independent target producer (currently absent):
# Get-R2OriginalTargetDiskBinding -Context; Assert-R2OriginalTargetDiskBinding
# -Context -Binding; Get-R2OriginalTargetValidationFields -Context -Validation.
# Only its original private issued VolumeGUID/held-owner
# reference can name LiteralCounterInstanceName. An E: spelling is not evidence.
# Current documentation: Context7 resolve Windows SDK + query WindowsAppSDK had
# no PDH result; primary contracts: learn.microsoft.com/windows/win32/api/pdh/
# nf-pdh-pdhgetrawcounterarrayw, ns-pdh-pdh_raw_counter; NVIDIA NVML latest
# group__nvmlDeviceQueries (used already includes reserved).

function Initialize-R2GaugeOwner {
    if (Get-Module -Name Route2OriginalGauges) { return }
    $owner=New-Module -Name Route2OriginalGauges -ScriptBlock {
        $script:state=$null
        $script:issuer=[object]::new()
        $script:samples=[Runtime.CompilerServices.ConditionalWeakTable[object,object]]::new()
        $script:serial=0L
        $script:thread=[Threading.Thread]::CurrentThread.ManagedThreadId

        function New-R2GaugeMap([hashtable]$Fields) {
            $d=[Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
            foreach($k in $Fields.Keys){$d.Add([string]$k,$Fields[$k])};return ,$d
        }
        function New-R2GaugeView($Data) {return ,([Collections.ObjectModel.ReadOnlyDictionary[string,object]]::new($Data))}
        function Stop-R2Gauge($Context,[string]$Code,$Fact=$null) {
            $status=$null;$serial=[uint64]0
            if($null -ne $Fact){$status=$Fact.RawStatus;$serial=$Fact.IssuerSerial}
            Stop-R2Guard $Context 'External' $Code $status $serial
            throw $Code
        }
        function Get-R2GaugeState($Context,[bool]$Create=$false) {
            Assert-R2ContextReference $Context
            if([Threading.Thread]::CurrentThread.ManagedThreadId -ne $script:thread){throw 'R2_GAUGE_OWNER_THREAD'}
            if($null -eq $script:state){
                if(-not $Create){throw 'R2_GAUGE_NOT_INITIALIZED'}
                $slot=Get-R2CurrentSlot $Context;Assert-R2PlanSlot $Context $slot
                $identity=Reserve-R2ComponentIdentity $Context $slot 'Gauge'
                $script:state=[pscustomobject]@{
                    Context=$Context;Plan=$Context.PlanReference;Identity=$identity;Init=0;InitBegin=$null;Ready=$false;Closed=$false
                    Small=$null;Raw=$null;Buffers=[Collections.Generic.List[object]]::new(2);Slices=@{}
                    NvmlAttempted=$false;NvmlLive=$false;NvmlClosed=$false;NvmlInitFact=$null
                    Query=$null;Physical=$null;Logical=$null;Acquisitions=[Collections.Generic.List[object]]::new()
                    InfoIndex=0;InfoNeeded=0;DeviceCount=$null;Devices=[Collections.Generic.List[object]]::new();DeviceIndex=0
                    UUIDs=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal);UUIDByIndex=[Collections.Generic.List[string]]::new()
                    N=$null;CpuPrevious=$null;CpuPreviousQpcBegin=$null;CpuPreviousQpcEnd=$null;CpuFirstFact=$null;FirstObserved=$false
                    FirstGroupQpc=$null;FirstProcessorCountQpc=$null;FirstRamQpc=$null
                    FirstNvmlMemoryQpcs=[Collections.Generic.Dictionary[uint32,long]]::new();FirstNvmlPassQpc=$null
                    FirstPhysicalRawQpc=$null;FirstLogicalRawQpc=$null
                    PhysicalBase=$null;LogicalBase=$null;PhysicalLast=$null;LogicalLast=$null;BaselineQpc=$null
                    TimeZone=$null;TimeZoneId=$null;UtcLast=$null;LocalLast=$null;OffsetLow=$null;OffsetHigh=$null
                    Cycle=0;CycleBegin=$null;CycleCadenceAnchor=$null;CycleCpu=$null;CpuReady=$false;Ram=0L;Vram=[bigint]0;CycleN=$null
                    CycleUUIDs=$null;CyclePhysical=$null;CycleLogical=$null;RawNeeded=0;RawCount=0;RawKind=0
                    ClockBegin=0L;ClockEnd=0L;ClockUtc=0L;ClockLocal=0L;CycleZone=$null;CycleZoneId=$null
                    Binding=$null;Validation=$null;BoundInstance=$null;ValidationPending=$false;ValidationSequence=0L;CurrentSample=$null;CloseIndex=0;ReleaseIndex=0;CloseFaults=0;CloseUnknown=$false
                }
            }
            $r=$script:state
            if(-not [object]::ReferenceEquals($r.Context,$Context) -or -not [object]::ReferenceEquals($r.Plan,$Context.PlanReference)){throw 'R2_GAUGE_CONTEXT_SUBSTITUTION'}
            Assert-R2PlanSlot $Context $r.Identity.OriginalSlotReference
            return $r
        }
        function Assert-R2GaugeLive($Context,$r) {
            if($r.Closed -or $Context.StopState -eq [R2Fact]::TRUE){throw 'R2_GAUGE_STOP_LATCHED'}
        }
        function Test-R2GaugeElapsed($Context,[long]$Begin,[long]$End) {
            if($Begin -lt $Context.Q0 -or $End -lt $Begin -or ([bigint]$End-$Begin)*10 -gt $Context.Frequency){Stop-R2Gauge $Context 'R2_GAUGE_100MS'}
        }
        function Get-R2GaugeNow($Context) {return [long](Get-R2LedgerTimestamp $Context)}
        function Assert-R2GaugeZero($Context,$Fact) {
            Assert-R2NativeFact $Context $Fact
            if($Fact.RawStatus -ne 0){Stop-R2Gauge $Context 'R2_GAUGE_NATIVE_STATUS' $Fact}
        }
        function Assert-R2GaugeBool($Context,$Fact) {
            Assert-R2NativeFact $Context $Fact
            if($Fact.RawStatus -eq 0){Stop-R2Gauge $Context 'R2_GAUGE_NATIVE_BOOL' $Fact}
        }
        function Get-R2GaugeFirstCompletion($Context,$Fact) {
            Assert-R2NativeFact $Context $Fact
            if(-not ($Fact.QpcBegin -is [long]) -or -not ($Fact.QpcEnd -is [long]) -or $Fact.QpcBegin -lt $Context.Q0 -or $Fact.QpcEnd -lt $Fact.QpcBegin){Stop-R2Gauge $Context 'R2_FIRST_RESOURCE_NATIVE_CLOCK' $Fact}
            # Original q0 is never replaced by InitBegin/CycleBegin, peer
            # startup, or the later first valid CPU delta. No additional QPC.
            Test-R2GaugeElapsed $Context $Context.Q0 $Fact.QpcEnd
            return [long]$Fact.QpcEnd
        }
        function Read-R2GaugeBytes($Context,$b,[uint32]$Offset,[uint32]$Count) {
            if($b.ContainsKey('BufferOwnerReference')){
                if([bigint]$Offset+$Count -gt $b.Capacity){Stop-R2Gauge $Context 'R2_GAUGE_SLICE_RANGE'}
                return ,(Read-R2NativeBuffer $Context $b.BufferOwnerReference ([uint32]([bigint]$b.Offset+$Offset)) $Count)
            }
            return ,(Read-R2NativeBuffer $Context $b $Offset $Count)
        }
        function Write-R2GaugeBytes($Context,$b,[byte[]]$Bytes) {
            if($b.ContainsKey('BufferOwnerReference')){
                if($Bytes.Length -gt $b.Capacity){Stop-R2Gauge $Context 'R2_GAUGE_SLICE_RANGE'}
                Write-R2NativeBuffer $Context $b.BufferOwnerReference $b.Offset $Bytes
            }else{Write-R2NativeBuffer $Context $b 0 $Bytes}
        }
        function Get-R2GaugeU32($Context,$b,[int]$o=0) {return [BitConverter]::ToUInt32([byte[]](Read-R2GaugeBytes $Context $b $o 4),0)}
        function Get-R2GaugeI64($Context,$b,[int]$o=0) {return [BitConverter]::ToInt64([byte[]](Read-R2GaugeBytes $Context $b $o 8),0)}
        function Get-R2GaugeU64($Context,$b,[int]$o=0) {return [BitConverter]::ToUInt64([byte[]](Read-R2GaugeBytes $Context $b $o 8),0)}
        function Set-R2GaugeU32($Context,$b,[uint32]$n) {Write-R2GaugeBytes $Context $b ([BitConverter]::GetBytes($n))}
        function Add-R2GaugeBuffer($Context,$r,[uint32]$Size) {
            $slot=Get-R2CurrentSlot $Context
            # This synchronous factory attempt can append exactly one original
            # registry record. Do not scan/adopt another component's buffers.
            $registry=$Context.Registry;$next=$registry.Count;$b=$null
            try {
                $b=New-R2NativeBuffer $Context $slot $Size 8
                $r.Buffers.Add($b);return ,$b
            }catch{
                $allocationFailure=$_
                try {
                    if(-not [object]::ReferenceEquals($Context.Registry,$registry) -or $registry.Count -lt $next -or $registry.Count -gt $next+1){throw 'R2_GAUGE_BUFFER_RECOVERY_REGISTRY'}
                    if($registry.Count -eq $next+1){
                        $candidate=$registry[$next]
                        if($null -eq $candidate -or -not [object]::ReferenceEquals($candidate.ContextReference,$Context) -or -not [object]::ReferenceEquals($candidate.PlanReference,$r.Plan) -or -not [object]::ReferenceEquals($candidate.OriginalSlotReference,$slot) -or $candidate.Capacity -ne $Size -or $candidate.Alignment -ne 8 -or $candidate.Ownership -ne [R2HandleOwnership]::OWNED -or $candidate.State -notin @([R2HandleState]::RESERVED,[R2HandleState]::LIVE)){throw 'R2_GAUGE_BUFFER_RECOVERY_BINDING'}
                        if($null -ne $b -and -not [object]::ReferenceEquals($b,$candidate)){throw 'R2_GAUGE_BUFFER_RECOVERY_RETURN_REFERENCE'}
                        # Bank the exact original reference BEFORE another
                        # fallible validation; this fixed bank has two slots.
                        $alreadyHeld=$false
                        foreach($held in $r.Buffers){if([object]::ReferenceEquals($held,$candidate)){$alreadyHeld=$true;break}}
                        if(-not $alreadyHeld){$r.Buffers.Add($candidate)}
                        if($candidate.State -eq [R2HandleState]::LIVE){
                            # Resolves THIS exact issuer-registered Buffer and
                            # its actual LIVE pointer even after global STOP.
                            $pointer=Get-R2NativeBufferPointer $Context $candidate
                            if($pointer -eq [IntPtr]::Zero){throw 'R2_GAUGE_BUFFER_RECOVERY_POINTER'}
                        }else{
                            # A reserved record alone cannot prove that a failed
                            # allocation acquired no unmanaged storage.
                            $r.CloseUnknown=$true;$r.CloseFaults++
                        }
                    }elseif($null -ne $b){throw 'R2_GAUGE_BUFFER_RECOVERY_RECORD_MISSING'}
                }catch{
                    # Recovery failure is sticky, independently of the original
                    # allocation STOP. Untouched cleanup resources stay banked.
                    $r.CloseUnknown=$true;$r.CloseFaults++
                    Stop-R2Guard $Context 'External' 'R2_GAUGE_BUFFER_RECOVERY_UNKNOWN' $null 0
                }
                Stop-R2Guard $Context 'External' 'R2_GAUGE_BUFFER_ALLOCATION_FAILED' $null 0
                throw $allocationFailure
            }
        }
        function Initialize-R2GaugeBuffers($Context,$r) {
            # One fixed 64 KiB PDH allocation per observing context: four
            # observers together have the SAME combined 256 KiB allowance.
            # Reuse across info/physical/logical; oversize means STOP, no resize.
            # The small control arena is disjoint from the PDH native output.
            $r.Small=Add-R2GaugeBuffer $Context $r 1024
            $r.Raw=Add-R2GaugeBuffer $Context $r 65536
            $ranges=@{Idle=@(0,8);Kernel=@(8,8);User=@(16,8);Memory=@(24,64);Count=@(88,4);Pointer=@(96,8);UUID=@(104,96);NvMemory=@(200,40);Size=@(240,4);Items=@(244,4);Collect=@(248,8);Utc=@(256,8);UtcSystem=@(264,16);LocalSystem=@(280,16);Local=@(296,8);Zone=@(304,172)}
            foreach($name in $ranges.Keys){$range=$ranges[$name];$r.Slices[$name]=Get-R2NativeBufferSlice $Context $r.Small $range[0] $range[1]}
        }
        function Read-R2GaugeCpu($Context,$r) {
            $f=Invoke-R2NativeCall $Context ([R2ApiId]::GetSystemTimes) @($r.Slices.Idle,$r.Slices.Kernel,$r.Slices.User)
            Assert-R2GaugeBool $Context $f
            # Retain bounded private scalars from the actual issuer fact, not a
            # new clock origin or one permanent NativeFact per polling frame.
            $begin=$f.QpcBegin;$end=$f.QpcEnd
            if(-not ($begin -is [long]) -or -not ($end -is [long]) -or $begin -lt $Context.Q0 -or $end -lt $begin){Stop-R2Gauge $Context 'R2_CPU_NATIVE_CLOCK_INVALID' $f}
            Test-R2GaugeElapsed $Context $begin $end
            $v=@((Get-R2GaugeI64 $Context $r.Slices.Idle),(Get-R2GaugeI64 $Context $r.Slices.Kernel),(Get-R2GaugeI64 $Context $r.Slices.User))
            foreach($n in $v){if($n -lt 0){Stop-R2Gauge $Context 'R2_CPU_NEGATIVE' $f}}
            if([bigint]$v[0] -gt [bigint]$v[1]+$v[2]){Stop-R2Gauge $Context 'R2_CPU_IDLE_INVALID' $f}
            $r.CpuReady=$false
            if($null -ne $r.CpuPrevious){
                if($null -eq $r.CpuPreviousQpcBegin -or $null -eq $r.CpuPreviousQpcEnd -or $r.CpuPreviousQpcBegin -lt $Context.Q0 -or $r.CpuPreviousQpcEnd -lt $r.CpuPreviousQpcBegin -or $r.CpuPreviousQpcEnd -gt $begin){Stop-R2Gauge $Context 'R2_CPU_NATIVE_CLOCK_REGRESSION' $f}
                # Conservative span includes BOTH actual collection brackets
                # and their scheduling gap. A long idle gap cannot dilute CPU.
                Test-R2GaugeElapsed $Context $r.CpuPreviousQpcBegin $end
                $di=[bigint]$v[0]-$r.CpuPrevious[0];$dk=[bigint]$v[1]-$r.CpuPrevious[1];$du=[bigint]$v[2]-$r.CpuPrevious[2]
                $total=$dk+$du
                if($di -lt 0 -or $dk -lt 0 -or $du -lt 0 -or $total -le 0 -or $total -gt [long]::MaxValue -or $di -gt $total){Stop-R2Gauge $Context 'R2_CPU_DELTA_INVALID' $f}
                if(10*($total-$di) -ge 9*$total){Stop-R2Gauge $Context 'R2_CPU_90_PERCENT' $f}
                $r.CpuReady=$true
            }else{
                Retain-R2NativeFact $Context $f;$r.CpuFirstFact=$f
            }
            # Bounded private decoded history, never a caller supplied scalar.
            $r.CpuPrevious=$v;$r.CpuPreviousQpcBegin=$begin;$r.CpuPreviousQpcEnd=$end;$r.CycleCpu=$v
            if(-not $r.FirstObserved){Test-R2GaugeElapsed $Context $Context.Q0 $f.QpcEnd;$r.FirstObserved=$true}
        }
        function Read-R2GaugeTopology($Context,$r) {
            $g=Invoke-R2NativeCall $Context ([R2ApiId]::GetActiveProcessorGroupCount) @()
            if($g.RawStatus -ne 1){Stop-R2Gauge $Context 'R2_GAUGE_SINGLE_GROUP' $g}
            if($null -eq $r.FirstGroupQpc){$r.FirstGroupQpc=Get-R2GaugeFirstCompletion $Context $g}
            $n=Invoke-R2NativeCall $Context ([R2ApiId]::GetActiveProcessorCount) @([uint16]0)
            if($n.RawStatus -lt 1 -or $n.RawStatus -gt 64 -or ($null -ne $r.N -and $r.N -ne $n.RawStatus)){Stop-R2Gauge $Context 'R2_GAUGE_TOPOLOGY_CHANGED' $n}
            if($null -eq $r.FirstProcessorCountQpc){$r.FirstProcessorCountQpc=Get-R2GaugeFirstCompletion $Context $n}
            if($null -eq $r.N){Retain-R2NativeFact $Context $g;Retain-R2NativeFact $Context $n;$r.N=[uint32]$n.RawStatus}
            $r.CycleN=[uint32]$n.RawStatus
        }
        function Read-R2GaugeRam($Context,$r) {
            Set-R2GaugeU32 $Context $r.Slices.Memory 64
            $f=Invoke-R2NativeCall $Context ([R2ApiId]::GlobalMemoryStatusEx) @($r.Slices.Memory)
            Assert-R2GaugeBool $Context $f
            $total=Get-R2GaugeU64 $Context $r.Slices.Memory 8;$avail=Get-R2GaugeU64 $Context $r.Slices.Memory 16
            if($total -eq 0 -or $avail -gt $total){Stop-R2Gauge $Context 'R2_RAM_INVALID' $f}
            $used=[bigint]$total-$avail
            if($used -gt 17179869184){Stop-R2Gauge $Context 'R2_RAM_16_GIB' $f}
            if($null -eq $r.FirstRamQpc){$r.FirstRamQpc=Get-R2GaugeFirstCompletion $Context $f}
            $r.Ram=[long]$used
        }
        function Read-R2GaugeDeviceCount($Context,$r) {
            $f=Invoke-R2NativeCall $Context ([R2ApiId]::nvmlDeviceGetCount_v2) @($r.Slices.Count)
            Assert-R2GaugeZero $Context $f;$n=Get-R2GaugeU32 $Context $r.Slices.Count
            if($n -lt 1 -or $n -gt 64 -or ($null -ne $r.DeviceCount -and $r.DeviceCount -ne $n)){Stop-R2Gauge $Context 'R2_NVML_DEVICE_COUNT' $f}
            if($null -eq $r.DeviceCount){Retain-R2NativeFact $Context $f;$r.DeviceCount=$n}
        }
        function Read-R2GaugeUUID($Context,$r,$Device,[bool]$Essential=$false) {
            $f=Invoke-R2NativeCall $Context ([R2ApiId]::nvmlDeviceGetUUID) @($Device,$r.Slices.UUID,[uint32]96)
            Assert-R2GaugeZero $Context $f
            $bytes=[byte[]](Read-R2GaugeBytes $Context $r.Slices.UUID 0 96);$end=-1
            for($i=0;$i -lt 96;$i++){if($bytes[$i] -eq 0){$end=$i;break};if($bytes[$i] -lt 33 -or $bytes[$i] -gt 126){Stop-R2Gauge $Context 'R2_NVML_UUID_BYTES' $f}}
            if($end -le 0){Stop-R2Gauge $Context 'R2_NVML_UUID_UNTERMINATED' $f}
            if($Essential){Retain-R2NativeFact $Context $f}
            return [Text.Encoding]::ASCII.GetString($bytes,0,$end)
        }
        function Read-R2GaugeVram($Context,$r,$Device) {
            Set-R2GaugeU32 $Context $r.Slices.NvMemory ([uint32]33554472)
            $f=Invoke-R2NativeCall $Context ([R2ApiId]::nvmlDeviceGetMemoryInfo_v2) @($Device,$r.Slices.NvMemory)
            Assert-R2GaugeZero $Context $f
            $version=Get-R2GaugeU32 $Context $r.Slices.NvMemory
            $total=Get-R2GaugeU64 $Context $r.Slices.NvMemory 8;$reserved=Get-R2GaugeU64 $Context $r.Slices.NvMemory 16
            $free=Get-R2GaugeU64 $Context $r.Slices.NvMemory 24;$used=Get-R2GaugeU64 $Context $r.Slices.NvMemory 32
            if($version -ne 33554472 -or $total -eq 0 -or $used -gt $total -or $free -gt $total -or $reserved -gt $used -or [bigint]$used+$free -gt $total){Stop-R2Gauge $Context 'R2_NVML_MEMORY_INVALID' $f}
            $sum=$r.Vram+[bigint]$used
            if($sum -gt 8589934592){Stop-R2Gauge $Context 'R2_VRAM_8_GIB' $f}
            if($r.DeviceIndex -lt 0 -or $r.DeviceIndex -ge $r.DeviceCount -or -not [object]::ReferenceEquals($Device,$r.Devices[$r.DeviceIndex])){Stop-R2Gauge $Context 'R2_FIRST_NVML_DEVICE_BINDING' $f}
            $index=[uint32]$r.DeviceIndex
            if(-not $r.FirstNvmlMemoryQpcs.ContainsKey($index)){
                $completed=Get-R2GaugeFirstCompletion $Context $f
                $r.FirstNvmlMemoryQpcs.Add($index,$completed)
                # All physical devices must finish their ORIGINAL first pass
                # by q0+100ms. One early device never certifies the others.
                if($r.FirstNvmlMemoryQpcs.Count -eq $r.DeviceCount -and $null -eq $r.FirstNvmlPassQpc){$r.FirstNvmlPassQpc=$completed}
            }
            $r.Vram=$sum
        }
        function Get-R2GaugeCounter($r,[int]$Index){if($Index -eq 0){return ,$r.Physical};return ,$r.Logical}
        function Initialize-R2Gauges($Context) {
            $r=Get-R2GaugeState $Context $true;Assert-R2GaugeLive $Context $r
            if($r.Ready){return 'READY'}
            $now=Get-R2GaugeNow $Context
            if($null -eq $r.InitBegin){$r.InitBegin=$now}else{Test-R2GaugeElapsed $Context $r.InitBegin $now}
            switch($r.Init){
                0 {Initialize-R2GaugeBuffers $Context $r;$r.Init=1}
                1 {Read-R2GaugeCpu $Context $r;$r.Init=2}
                2 {Read-R2GaugeTopology $Context $r;$r.Init=3}
                3 {
                    if($r.NvmlAttempted){Stop-R2Gauge $Context 'R2_NVML_INIT_REATTEMPT'}
                    $r.NvmlAttempted=$true
                    $f=Invoke-R2NativeCall $Context ([R2ApiId]::nvmlInit_v2) @()
                    # Record ownership immediately after actual success, before
                    # retaining or any further operation that can fail.
                    if($f.RawStatus -eq 0){$r.NvmlLive=$true;$r.NvmlInitFact=$f}
                    Assert-R2GaugeZero $Context $f;Retain-R2NativeFact $Context $f;$r.Init=4
                }
                4 {Read-R2GaugeDeviceCount $Context $r;$r.Init=5}
                5 {
                    if($r.DeviceIndex -ge $r.DeviceCount){$r.Init=7;break}
                    $reservation=Reserve-R2NativeOpaqueReference $Context ([R2ApiId]::nvmlDeviceGetHandleByIndex_v2)
                    $r.Acquisitions.Add($reservation)
                    $f=Invoke-R2NativeCall $Context ([R2ApiId]::nvmlDeviceGetHandleByIndex_v2) @([uint32]$r.DeviceIndex,$r.Slices.Pointer)
                    Assert-R2GaugeZero $Context $f;$r.Devices.Add((New-R2NativeOpaqueReference $Context $f));$r.Init=6
                }
                6 {
                    $uuid=Read-R2GaugeUUID $Context $r $r.Devices[$r.DeviceIndex] $true
                    if(-not $r.UUIDs.Add($uuid)){Stop-R2Gauge $Context 'R2_NVML_DUPLICATE_UUID'}
                    $r.UUIDByIndex.Add($uuid);$r.DeviceIndex++;$r.Init=5
                }
                7 {
                    $r.Query=Reserve-R2NativeOpaqueReference $Context ([R2ApiId]::PdhOpenQueryW);$r.Acquisitions.Add($r.Query)
                    $f=Invoke-R2NativeCall $Context ([R2ApiId]::PdhOpenQueryW) @($null,[uint64]0,$r.Slices.Pointer)
                    Assert-R2GaugeZero $Context $f;$r.Query=New-R2NativeOpaqueReference $Context $f;$r.Init=8
                }
                8 {
                    $r.Physical=Reserve-R2NativeOpaqueReference $Context ([R2ApiId]::PdhAddEnglishCounterW);$r.Acquisitions.Add($r.Physical)
                    $f=Invoke-R2NativeCall $Context ([R2ApiId]::PdhAddEnglishCounterW) @($r.Query,'\PhysicalDisk(*)\Disk Write Bytes/sec',[uint64]0,$r.Slices.Pointer)
                    Assert-R2GaugeZero $Context $f;$r.Physical=New-R2NativeOpaqueReference $Context $f;$r.Init=9
                }
                9 {
                    $r.Logical=Reserve-R2NativeOpaqueReference $Context ([R2ApiId]::PdhAddEnglishCounterW);$r.Acquisitions.Add($r.Logical)
                    $f=Invoke-R2NativeCall $Context ([R2ApiId]::PdhAddEnglishCounterW) @($r.Query,'\LogicalDisk(*)\Disk Write Bytes/sec',[uint64]0,$r.Slices.Pointer)
                    Assert-R2GaugeZero $Context $f;$r.Logical=New-R2NativeOpaqueReference $Context $f;$r.Init=10
                }
                10 {
                    Set-R2GaugeU32 $Context $r.Slices.Size 0
                    $counter=Get-R2GaugeCounter $r $r.InfoIndex
                    $f=Invoke-R2NativeCall $Context ([R2ApiId]::PdhGetCounterInfoW) @($counter,[int]0,$r.Slices.Size,[IntPtr]::Zero)
                    if($f.StatusBits -ne [uint32]2147485650){Stop-R2Gauge $Context 'R2_PDH_INFO_SIZE_STATUS' $f}
                    $r.InfoNeeded=Get-R2GaugeU32 $Context $r.Slices.Size
                    if($r.InfoNeeded -lt 8 -or $r.InfoNeeded -gt 65536){Stop-R2Gauge $Context 'R2_PDH_INFO_SIZE' $f};$r.Init=11
                }
                11 {
                    Set-R2GaugeU32 $Context $r.Slices.Size ([uint32]65536)
                    $counter=Get-R2GaugeCounter $r $r.InfoIndex
                    $f=Invoke-R2NativeCall $Context ([R2ApiId]::PdhGetCounterInfoW) @($counter,[int]0,$r.Slices.Size,$r.Raw)
                    Assert-R2GaugeZero $Context $f
                    $length=Get-R2GaugeU32 $Context $r.Slices.Size;$declared=Get-R2GaugeU32 $Context $r.Raw
                    if($length -lt 8 -or $length -gt 65536 -or $declared -lt 8 -or $declared -gt $length -or (Get-R2GaugeU32 $Context $r.Raw 4) -ne 272696576){Stop-R2Gauge $Context 'R2_PDH_COUNTER_TYPE' $f}
                    # Large info remains transient; the verified fixed type and
                    # original opaque counter references are private authority.
                    $r.InfoIndex++;if($r.InfoIndex -lt 2){$r.Init=10}else{$r.Init=12}
                }
                12 {$r.Ready=$true;$r.Cycle=0;return 'READY'}
                default {Stop-R2Gauge $Context 'R2_GAUGE_INIT_STATE'}
            }
            Test-R2GaugeElapsed $Context $r.InitBegin (Get-R2GaugeNow $Context)
            return 'PENDING'
        }

        function Read-R2GaugeRawSize($Context,$r) {
            Set-R2GaugeU32 $Context $r.Slices.Size 0
            Set-R2GaugeU32 $Context $r.Slices.Items 0
            $counter=Get-R2GaugeCounter $r $r.RawKind
            $f=Invoke-R2NativeCall $Context ([R2ApiId]::PdhGetRawCounterArrayW) @($counter,$r.Slices.Size,$r.Slices.Items,[IntPtr]::Zero)
            if($f.StatusBits -ne [uint32]2147485650){Stop-R2Gauge $Context 'R2_PDH_ARRAY_SIZE_STATUS' $f}
            $r.RawNeeded=Get-R2GaugeU32 $Context $r.Slices.Size
            if($r.RawNeeded -lt 48 -or $r.RawNeeded -gt 65536){Stop-R2Gauge $Context 'R2_PDH_ARRAY_SIZE' $f}
        }
        function Read-R2GaugeWideName($Context,$r,[long]$Pointer,[uint32]$Length) {
            $base=(Get-R2NativeBufferPointer $Context $r.Raw).ToInt64()
            $offset=[bigint]$Pointer-$base
            # No pointer dereference until its complete WCHAR is inside the
            # actual returned data extent. Names cannot alias the item array.
            if($offset -lt [bigint]$r.RawCount*48 -or $offset -gt [bigint]$Length-2 -or $offset%2 -ne 0){Stop-R2Gauge $Context 'R2_PDH_NAME_POINTER'}
            $chars=[Collections.Generic.List[char]]::new(256)
            for($i=0;$i -lt 256;$i++){
                $at=$offset+2*$i
                if($at+2 -gt $Length){Stop-R2Gauge $Context 'R2_PDH_NAME_BOUNDARY'}
                $v=[BitConverter]::ToUInt16([byte[]](Read-R2NativeBuffer $Context $r.Raw ([uint32]$at) 2),0)
                if($v -eq 0){
                    if($chars.Count -eq 0){Stop-R2Gauge $Context 'R2_PDH_EMPTY_NAME'}
                    return [string]::new($chars.ToArray())
                }
                if($v -lt 32 -or ($v -ge 55296 -and $v -le 57343)){Stop-R2Gauge $Context 'R2_PDH_NAME_ENCODING'}
                $chars.Add([char]$v)
            }
            Stop-R2Gauge $Context 'R2_PDH_NAME_UNTERMINATED'
        }
        function Read-R2GaugeRawData($Context,$r) {
            # One fixed-capacity data attempt after the exact size-only call.
            # A growth/MORE_DATA result is a fault; never resize or retry.
            Set-R2GaugeU32 $Context $r.Slices.Size ([uint32]65536)
            Set-R2GaugeU32 $Context $r.Slices.Items 0
            $counter=Get-R2GaugeCounter $r $r.RawKind
            $f=Invoke-R2NativeCall $Context ([R2ApiId]::PdhGetRawCounterArrayW) @($counter,$r.Slices.Size,$r.Slices.Items,$r.Raw)
            Assert-R2GaugeZero $Context $f
            $length=Get-R2GaugeU32 $Context $r.Slices.Size;$count=Get-R2GaugeU32 $Context $r.Slices.Items
            if($length -lt 48 -or $length -gt 65536 -or $count -lt 1 -or $count -gt 65 -or [bigint]$count*48 -gt $length){Stop-R2Gauge $Context 'R2_PDH_ARRAY_EXTENT' $f}
            if(-not $f.Outputs.ContainsKey('3') -or $f.Outputs['3'].Count -ne $length -or $f.Outputs['3'].LeaseSerial -ne $f.IssuerSerial){Stop-R2Gauge $Context 'R2_PDH_OUTPUT_LEASE' $f}
            $r.RawCount=$count
            $names=[Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
            $data=[Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
            for($i=0;$i -lt $count;$i++){
                $at=$i*48
                $pointer=Get-R2GaugeI64 $Context $r.Raw $at
                $name=Read-R2GaugeWideName $Context $r $pointer $length
                if(-not $names.Add($name)){Stop-R2Gauge $Context 'R2_PDH_DUPLICATE_INSTANCE' $f}
                $status=Get-R2GaugeU32 $Context $r.Raw ($at+8)
                if($status -ne 0 -and $status -ne 1){Stop-R2Gauge $Context 'R2_PDH_ITEM_STATUS' $f}
                $low=Get-R2GaugeU32 $Context $r.Raw ($at+12);$high=Get-R2GaugeU32 $Context $r.Raw ($at+16)
                $timestamp=[bigint]$high*4294967296+$low
                $value=Get-R2GaugeI64 $Context $r.Raw ($at+24)
                if($value -lt 0 -or $timestamp -le 0 -or $timestamp -gt [long]::MaxValue){Stop-R2Gauge $Context 'R2_PDH_ITEM_VALUE' $f}
                if($name -ceq '_Total'){continue}
                if($name.Equals('_Total',[StringComparison]::OrdinalIgnoreCase)){Stop-R2Gauge $Context 'R2_PDH_TOTAL_ALIAS' $f}
                if($data.Count -ge 64){Stop-R2Gauge $Context 'R2_PDH_INSTANCE_LIMIT' $f}
                # These bounded scalars originate only in the checked actual
                # native buffer. No full frame byte array or NativeFact survives.
                $data.Add($name,[pscustomobject]@{Bytes=[long]$value;Time=[long]$timestamp})
            }
            if($data.Count -eq 0){Stop-R2Gauge $Context 'R2_PDH_NO_INSTANCES' $f}
            if($r.RawKind -eq 0 -and $null -eq $r.FirstPhysicalRawQpc){$r.FirstPhysicalRawQpc=Get-R2GaugeFirstCompletion $Context $f}
            if($r.RawKind -eq 1 -and $null -eq $r.FirstLogicalRawQpc){$r.FirstLogicalRawQpc=Get-R2GaugeFirstCompletion $Context $f}
            if($r.RawKind -eq 0){$r.CyclePhysical=$data}else{$r.CycleLogical=$data}
        }
        function Read-R2GaugeZone($Context,$r) {
            $f=Invoke-R2NativeCall $Context ([R2ApiId]::GetTimeZoneInformation) @($r.Slices.Zone)
            if($f.RawStatus -lt 0 -or $f.RawStatus -gt 2){Stop-R2Gauge $Context 'R2_GAUGE_TIMEZONE' $f}
            $bytes=[byte[]](Read-R2GaugeBytes $Context $r.Slices.Zone 0 172)
            if($null -ne $r.TimeZone){
                if($r.TimeZoneId -ne $f.RawStatus){Stop-R2Gauge $Context 'R2_TIMEZONE_CHANGED' $f}
                for($i=0;$i -lt 172;$i++){if($bytes[$i] -ne $r.TimeZone[$i]){Stop-R2Gauge $Context 'R2_TIMEZONE_CHANGED' $f}}
            }
            $r.CycleZone=$bytes;$r.CycleZoneId=$f.RawStatus
        }
        function Read-R2GaugePreciseUtc($Context,$r) {
            $f=Invoke-R2NativeCall $Context ([R2ApiId]::GetSystemTimePreciseAsFileTime) @($r.Slices.Utc)
            Assert-R2NativeFact $Context $f
            $utc=Get-R2GaugeI64 $Context $r.Slices.Utc
            if($utc -le 0 -or ($null -ne $r.UtcLast -and $utc -lt $r.UtcLast)){Stop-R2Gauge $Context 'R2_UTC_REGRESSION' $f}
            $r.ClockUtc=$utc;$r.ClockBegin=[long]$f.QpcBegin;$r.ClockEnd=[long]$f.QpcEnd
        }
        function Complete-R2GaugeClock($Context,$r) {
            $local=Get-R2GaugeI64 $Context $r.Slices.Local
            # SYSTEMTIME truncates sub-millisecond precision; timezone conversion
            # changes an integral-minute offset, so restore the actual precise
            # UTC remainder before deriving the LOCAL FILETIME offset interval.
            $localValue=[bigint]$local+($r.ClockUtc%10000)
            if($local -le 0 -or $localValue -gt [long]::MaxValue -or ($null -ne $r.LocalLast -and $localValue -lt $r.LocalLast)){Stop-R2Gauge $Context 'R2_LOCAL_TIME_REGRESSION'}
            $r.ClockLocal=[long]$localValue
            $frequency=[bigint]$Context.Frequency
            $low=$localValue*$frequency-[bigint]$r.ClockEnd*10000000
            $high=$localValue*$frequency-[bigint]$r.ClockBegin*10000000
            if($low -gt $high){Stop-R2Gauge $Context 'R2_CLOCK_OFFSET_INVALID'}
            if($null -ne $r.OffsetLow){
                if($r.OffsetLow -gt $low){$low=$r.OffsetLow}
                if($r.OffsetHigh -lt $high){$high=$r.OffsetHigh}
            }
            if($low -gt $high){Stop-R2Gauge $Context 'R2_CLOCK_DISCONTINUITY'}
            # Rational numerator in 100 ns * frequency; no rounding or doubles.
            $r.OffsetLow=$low;$r.OffsetHigh=$high
            $r.UtcLast=$r.ClockUtc;$r.LocalLast=$r.ClockLocal
            if($null -eq $r.TimeZone){$r.TimeZone=$r.CycleZone;$r.TimeZoneId=$r.CycleZoneId}
        }
        function Assert-R2GaugeRows($Context,$r,$Current,$Previous,$Baseline,[long]$Now) {
            if($null -ne $Previous -and $Current.Count -ne $Previous.Count){Stop-R2Gauge $Context 'R2_PDH_INSTANCE_SET_CHANGED'}
            foreach($pair in $Current.GetEnumerator()){
                $name=$pair.Key;$row=$pair.Value
                if($null -ne $Previous){
                    if(-not $Previous.ContainsKey($name)){Stop-R2Gauge $Context 'R2_PDH_INSTANCE_SET_CHANGED'}
                    if($row.Time -le $Previous[$name].Time){Stop-R2Gauge $Context 'R2_PDH_RAW_TIME_NOT_ADVANCING'}
                    if($row.Bytes -lt $Previous[$name].Bytes){Stop-R2Gauge $Context 'R2_PDH_COUNTER_RESET'}
                }
                if($null -ne $Baseline -and (-not $Baseline.ContainsKey($name) -or $row.Bytes -lt $Baseline[$name].Bytes)){Stop-R2Gauge $Context 'R2_PDH_BASELINE_RESET'}
                $ageLow=[bigint]$Now*10000000+$r.OffsetLow-[bigint]$row.Time*$Context.Frequency
                $ageHigh=[bigint]$Now*10000000+$r.OffsetHigh-[bigint]$row.Time*$Context.Frequency
                if($ageLow -lt 0 -or $ageHigh -gt [bigint]1000000*$Context.Frequency){Stop-R2Gauge $Context 'R2_PDH_RAW_FRAME_STALE'}
            }
        }
        function Get-R2GaugeExposure($Context,$Current,$Baseline,[string]$ExcludedName='') {
            $sum=[bigint]0
            foreach($pair in $Current.GetEnumerator()){
                if($ExcludedName.Length -gt 0 -and $pair.Key -ceq $ExcludedName){continue}
                if(-not $Baseline.ContainsKey($pair.Key)){Stop-R2Gauge $Context 'R2_DISK_BASELINE_MISSING'}
                $delta=[bigint]$pair.Value.Bytes-$Baseline[$pair.Key].Bytes
                if($delta -lt 0){Stop-R2Gauge $Context 'R2_DISK_NEGATIVE_DELTA'};$sum+=$delta
                if($sum -gt [long]::MaxValue){Stop-R2Gauge $Context 'R2_DISK_SUM_OVERFLOW'}
            };return [long]$sum
        }
        function Get-R2GaugeTargetBinding($Context,$r) {
            # Exact fixed producer names. Neither a callback nor a caller boolean
            # can grant acceptance. Its issuer assertion owns all field evidence.
            $r.ValidationPending=$false
            if($null -eq (Get-Command Get-R2OriginalTargetDiskBinding -CommandType Function -ErrorAction SilentlyContinue) -or $null -eq (Get-Command Assert-R2OriginalTargetDiskBinding -CommandType Function -ErrorAction SilentlyContinue) -or $null -eq (Get-Command Get-R2OriginalTargetValidationFields -CommandType Function -ErrorAction SilentlyContinue)){return $null}
            $binding=Get-R2OriginalTargetDiskBinding -Context $Context
            if($null -eq $binding){return $null}
            if($binding -is [string]){
                if($binding -ceq 'NOT_READY' -or $binding -ceq 'PENDING'){return $null}
                Stop-R2Gauge $Context 'R2_TARGET_DISK_BINDING_RESULT'
            }
            $validation=Assert-R2OriginalTargetDiskBinding -Context $Context -Binding $binding
            if($validation -is [string]){
                if($validation -ceq 'NOT_READY'){return $null}
                if($validation -ceq 'PENDING'){$r.ValidationPending=$true;return $null}
                Stop-R2Gauge $Context 'R2_TARGET_DISK_VALIDATION_RESULT'
            }
            if($null -eq $validation){Stop-R2Gauge $Context 'R2_TARGET_DISK_VALIDATION_MISSING'}
            # The target owner verifies original private issuer/reference/latest
            # sequence. Returned fields are never accepted from a caller sample.
            $fields=Get-R2OriginalTargetValidationFields -Context $Context -Validation $validation
            $now=Get-R2GaugeNow $Context;Test-R2GaugeElapsed $Context $r.CycleBegin $now
            if(-not [object]::ReferenceEquals($fields.ContextReference,$Context) -or -not [object]::ReferenceEquals($fields.BindingReference,$binding) -or $fields.QpcBegin -lt $r.CycleBegin -or $fields.QpcEnd -lt $fields.QpcBegin -or $fields.QpcEnd -gt $now -or $fields.Sequence -le $r.ValidationSequence){Stop-R2Gauge $Context 'R2_TARGET_DISK_VALIDATION_STALE'}
            Test-R2GaugeElapsed $Context $fields.QpcBegin $now
            if(-not ($fields.LiteralCounterInstanceName -is [string]) -or [string]::IsNullOrEmpty($fields.LiteralCounterInstanceName) -or [string]::IsNullOrEmpty($fields.VolumeGuid)){Stop-R2Gauge $Context 'R2_TARGET_DISK_BINDING_INSTANCE'}
            if($null -ne $r.Binding -and -not [object]::ReferenceEquals($r.Binding,$binding)){Stop-R2Gauge $Context 'R2_TARGET_DISK_BINDING_REPLACED'}
            if($null -ne $r.BoundInstance -and $r.BoundInstance -cne $fields.LiteralCounterInstanceName){Stop-R2Gauge $Context 'R2_TARGET_DISK_INSTANCE_CHANGED'}
            $r.Binding=$binding;$r.Validation=$validation;$r.BoundInstance=$fields.LiteralCounterInstanceName;$r.ValidationSequence=$fields.Sequence
            return ,$binding
        }
        function New-R2GaugeSample($Context,$r,[string]$Status,[string]$Reason,[long]$Now,[long]$Physical,[Nullable[long]]$NonE) {
            if($script:serial -eq [long]::MaxValue){Stop-R2Gauge $Context 'R2_GAUGE_SAMPLE_SERIAL'};$script:serial++
            # Only one current sample is authoritative. CWT permits old client
            # views to be collected without retaining every polling frame.
            $d=New-R2GaugeMap @{IssuerIdentity=$script:issuer;IssuerSerial=$script:serial;ContextReference=$Context;PlanReference=$r.Plan;OriginalSlotReference=(Get-R2CurrentSlot $Context);Status=$Status;Reason=$Reason;ObservedQpc=$Now;ProcessorCount=$r.N;RamUsedBytes=$r.Ram;VramUsedBytes=[long]$r.Vram;PhysicalWriteExposure=$Physical;NonEWriteExposure=$NonE;UnderlyingProviderFreshness='UNKNOWN_NOT_ZERO';TargetBindingReference=$r.Binding}
            $view=New-R2GaugeView $d
            $entry=[pscustomobject]@{View=$view;Data=$d;Consumed=$false;CycleBegin=$r.CycleBegin;Physical=$r.CyclePhysical;Logical=$r.CycleLogical;Binding=$r.Binding;Validation=$r.Validation;ValidationSequence=$r.ValidationSequence}
            $script:samples.Add($view,$entry);$r.CurrentSample=$view
            return ,$view
        }
        function Complete-R2GaugeCycle($Context,$r) {
            $now=Get-R2GaugeNow $Context;Test-R2GaugeElapsed $Context $r.CycleBegin $now
            Assert-R2GaugeRows $Context $r $r.CyclePhysical $r.PhysicalLast $r.PhysicalBase $now
            Assert-R2GaugeRows $Context $r $r.CycleLogical $r.LogicalLast $r.LogicalBase $now
            if($null -eq $r.PhysicalBase){
                # b0 is the SAME invocation's first valid frame, never reset on
                # missing target binding, deletion or later target publication.
                if($null -eq $r.FirstPhysicalRawQpc -or $null -eq $r.FirstLogicalRawQpc){Stop-R2Gauge $Context 'R2_FIRST_PDH_NATIVE_OBSERVATIONS_MISSING'}
                Test-R2GaugeElapsed $Context $Context.Q0 $now
                $r.PhysicalBase=$r.CyclePhysical;$r.LogicalBase=$r.CycleLogical;$r.BaselineQpc=$now
            }
            # These are write-once actual producer observations. Later READY
            # can await another fresh CPU delta or target validation without
            # moving any first-resource origin or imposing a new READY clock.
            if(-not $r.FirstObserved -or $null -eq $r.FirstGroupQpc -or $null -eq $r.FirstProcessorCountQpc -or $null -eq $r.FirstRamQpc -or $null -eq $r.FirstNvmlPassQpc -or $r.FirstNvmlMemoryQpcs.Count -ne $r.DeviceCount){Stop-R2Gauge $Context 'R2_FIRST_RESOURCE_OBSERVATIONS_INCOMPLETE'}
            $physical=Get-R2GaugeExposure $Context $r.CyclePhysical $r.PhysicalBase
            if($physical -gt 32212254720){Stop-R2Gauge $Context 'R2_PHYSICAL_WRITE_30_GIB_VIOLATION'}
            if($physical -ge 25769803776){Stop-R2Gauge $Context 'R2_PHYSICAL_WRITE_24_GIB_STOP'}
            $binding=Get-R2GaugeTargetBinding $Context $r;$nonE=$null
            if($r.ValidationPending){return 'PENDING'}
            $status='NOT_READY';$reason='TARGET_DISK_BINDING_UNAVAILABLE'
            if($null -ne $binding){
                $instance=$r.BoundInstance
                # Exact literal from the actual held-owner/VolumeGUID binding,
                # never special treatment of any caller-provided E: spelling.
                $exact=$false;foreach($name in $r.CycleLogical.Keys){if($name -ceq $instance){$exact=$true;break}}
                if(-not $exact){Stop-R2Gauge $Context 'R2_BOUND_LOGICAL_INSTANCE_MISSING'}
                $nonE=Get-R2GaugeExposure $Context $r.CycleLogical $r.LogicalBase $instance
                if($nonE -gt 536870912){Stop-R2Gauge $Context 'R2_NON_E_WRITE_512_MIB_VIOLATION'}
                if($nonE -ge 402653184){Stop-R2Gauge $Context 'R2_NON_E_WRITE_384_MIB_STOP'}
                if($r.CpuReady){$status='READY';$reason='ACTUAL_FRAME_VERIFIED'}else{$reason='CPU_FIRST_DELTA_PENDING'}
            }
            # Target validation, row processing and exposure arithmetic also
            # belong to this original cycle, not an earlier sampled endpoint.
            $now=Get-R2GaugeNow $Context;Test-R2GaugeElapsed $Context $r.CycleBegin $now
            Assert-R2GaugeRows $Context $r $r.CyclePhysical $null $r.PhysicalBase $now
            Assert-R2GaugeRows $Context $r $r.CycleLogical $null $r.LogicalBase $now
            $r.PhysicalLast=$r.CyclePhysical;$r.LogicalLast=$r.CycleLogical
            $sample=New-R2GaugeSample $Context $r $status $reason $now $physical $nonE
            $r.Cycle=0
            return ,$sample
        }
        function Read-R2GaugeFrame($Context) {
            $r=Get-R2GaugeState $Context;Assert-R2GaugeLive $Context $r
            if(-not $r.Ready){throw 'R2_GAUGE_INITIALIZATION_PENDING'}
            $now=Get-R2GaugeNow $Context
            if($r.Cycle -eq 0){
                # This anchor survives Complete-R2GaugeCycle's Cycle=0 reset.
                # Check the prior cycle's actual start BEFORE granting a new
                # origin, so individually short cycles cannot hide long gaps.
                if($null -ne $r.CycleCadenceAnchor){Test-R2GaugeElapsed $Context $r.CycleCadenceAnchor $now}
                if($null -ne $r.CurrentSample){
                    $old=$null
                    if($script:samples.TryGetValue($r.CurrentSample,[ref]$old)){$old.Consumed=$true;[void]$script:samples.Remove($r.CurrentSample)}
                    $r.CurrentSample=$null
                }
                $r.CycleCadenceAnchor=$now;$r.CycleBegin=$now;$r.Vram=[bigint]0;$r.DeviceIndex=0
                $r.CycleUUIDs=[Collections.Generic.HashSet[string]]::new([StringComparer]::Ordinal)
                $r.CyclePhysical=$null;$r.CycleLogical=$null;$r.Cycle=1
            }else{Test-R2GaugeElapsed $Context $r.CycleBegin $now}
            switch($r.Cycle){
                1 {Read-R2GaugeCpu $Context $r;$r.Cycle=2}
                2 {Read-R2GaugeTopology $Context $r;$r.Cycle=3}
                3 {Read-R2GaugeRam $Context $r;$r.Cycle=4}
                4 {Read-R2GaugeDeviceCount $Context $r;$r.Cycle=5}
                5 {
                    if($r.DeviceIndex -ge $r.DeviceCount){
                        if($r.CycleUUIDs.Count -ne $r.UUIDs.Count -or -not $r.CycleUUIDs.SetEquals($r.UUIDs)){Stop-R2Gauge $Context 'R2_NVML_UUID_SET_CHANGED'}
                        $r.Cycle=7;break
                    }
                    $uuid=Read-R2GaugeUUID $Context $r $r.Devices[$r.DeviceIndex]
                    if(-not $r.CycleUUIDs.Add($uuid) -or $uuid -cne $r.UUIDByIndex[$r.DeviceIndex]){Stop-R2Gauge $Context 'R2_NVML_UUID_SET_CHANGED'}
                    $r.Cycle=6
                }
                6 {Read-R2GaugeVram $Context $r $r.Devices[$r.DeviceIndex];$r.DeviceIndex++;$r.Cycle=5}
                7 {
                    $f=Invoke-R2NativeCall $Context ([R2ApiId]::PdhCollectQueryDataWithTime) @($r.Query,$r.Slices.Collect)
                    Assert-R2GaugeZero $Context $f
                    # The collect timestamp is deliberately NOT raw freshness.
                    $r.RawKind=0;$r.Cycle=8
                }
                8 {Read-R2GaugeRawSize $Context $r;$r.Cycle=9}
                9 {Read-R2GaugeRawData $Context $r;$r.RawKind=1;$r.Cycle=10}
                10 {Read-R2GaugeRawSize $Context $r;$r.Cycle=11}
                11 {Read-R2GaugeRawData $Context $r;$r.Cycle=12}
                12 {Read-R2GaugeZone $Context $r;$r.Cycle=13}
                13 {Read-R2GaugePreciseUtc $Context $r;$r.Cycle=14}
                14 {
                    # Original precise value still resides in the held control
                    # buffer. The current private scalar is not caller input.
                    $f=Invoke-R2NativeCall $Context ([R2ApiId]::FileTimeToSystemTime) @($r.Slices.Utc,$r.Slices.UtcSystem)
                    Assert-R2GaugeBool $Context $f;$r.Cycle=15
                }
                15 {
                    $f=Invoke-R2NativeCall $Context ([R2ApiId]::SystemTimeToTzSpecificLocalTime) @($r.Slices.Zone,$r.Slices.UtcSystem,$r.Slices.LocalSystem)
                    Assert-R2GaugeBool $Context $f;$r.Cycle=16
                }
                16 {
                    $f=Invoke-R2NativeCall $Context ([R2ApiId]::SystemTimeToFileTime) @($r.Slices.LocalSystem,$r.Slices.Local)
                    Assert-R2GaugeBool $Context $f;Complete-R2GaugeClock $Context $r;$r.Cycle=17
                }
                17 {
                    # Re-read actual timezone after conversion. Any mid-cycle
                    # structure or ID change prevents issuing a sample.
                    $previous=$r.CycleZone;$previousId=$r.CycleZoneId
                    Read-R2GaugeZone $Context $r
                    if($previousId -ne $r.CycleZoneId){Stop-R2Gauge $Context 'R2_TIMEZONE_CHANGED_DURING_CYCLE'}
                    for($i=0;$i -lt 172;$i++){if($previous[$i] -ne $r.CycleZone[$i]){Stop-R2Gauge $Context 'R2_TIMEZONE_CHANGED_DURING_CYCLE'}}
                    $r.Cycle=18
                }
                18 {return ,(Complete-R2GaugeCycle $Context $r)}
                default {Stop-R2Gauge $Context 'R2_GAUGE_READ_STATE'}
            }
            Test-R2GaugeElapsed $Context $r.CycleBegin (Get-R2GaugeNow $Context)
            return 'PENDING'
        }
        function Assert-R2GaugeFrame($Context,$Sample) {
            $r=Get-R2GaugeState $Context;Assert-R2GaugeLive $Context $r
            $entry=$null
            if($null -eq $Sample -or -not $script:samples.TryGetValue($Sample,[ref]$entry) -or -not [object]::ReferenceEquals($entry.View,$Sample) -or -not [object]::ReferenceEquals($r.CurrentSample,$Sample)){Stop-R2Gauge $Context 'R2_GAUGE_UNISSUED_SAMPLE'}
            if($entry.Consumed){Stop-R2Gauge $Context 'R2_GAUGE_SAMPLE_ALREADY_CONSUMED'}
            # Once consumed even when a later assertion fails. Reusing decoded
            # views cannot authorize a second operation or a later guard step.
            $entry.Consumed=$true
            if(-not [object]::ReferenceEquals($entry.Data.ContextReference,$Context) -or -not [object]::ReferenceEquals($entry.Data.PlanReference,$Context.PlanReference) -or -not [object]::ReferenceEquals($entry.Data.IssuerIdentity,$script:issuer)){Stop-R2Gauge $Context 'R2_GAUGE_SAMPLE_BINDING'}
            Assert-R2PlanSlot $Context $entry.Data.OriginalSlotReference
            $now=Get-R2GaugeNow $Context
            Test-R2GaugeElapsed $Context $entry.CycleBegin $now
            Test-R2GaugeElapsed $Context $entry.Data.ObservedQpc $now
            Assert-R2GaugeRows $Context $r $entry.Physical $null $r.PhysicalBase $now
            Assert-R2GaugeRows $Context $r $entry.Logical $null $r.LogicalBase $now
            if($entry.Data.Status -cne 'READY') {throw ('R2_GAUGE_NOT_READY_'+$entry.Data.Reason)}
            $fields=Get-R2OriginalTargetValidationFields -Context $Context -Validation $entry.Validation
            $now=Get-R2GaugeNow $Context
            if(-not [object]::ReferenceEquals($fields.ContextReference,$Context) -or -not [object]::ReferenceEquals($fields.BindingReference,$entry.Binding) -or $fields.Sequence -ne $entry.ValidationSequence -or $fields.QpcBegin -lt $entry.CycleBegin -or $fields.QpcEnd -lt $fields.QpcBegin -or $fields.QpcEnd -gt $now){Stop-R2Gauge $Context 'R2_GAUGE_TARGET_BINDING_STALE'}
            Test-R2GaugeElapsed $Context $entry.CycleBegin $now
            Assert-R2GaugeRows $Context $r $entry.Physical $null $r.PhysicalBase $now
            Assert-R2GaugeRows $Context $r $entry.Logical $null $r.LogicalBase $now
            return 'VERIFIED'
        }
        function Close-R2GaugesStep($Context) {
            $r=Get-R2GaugeState $Context
            if($r.Closed){return 'CLOSED'}
            # The caller MUST have entered its original cleanup ledger step;
            # Begin locks the original deadline and never grants fresh seconds.
            [void](Begin-R2LedgerCleanup $Context 'External')
            # Recover original ledger ownership even if Init succeeded natively
            # but its post-call QPC/step gate threw before returning to us.
            $actualInit=Get-R2NvmlInitializationFact $Context
            if($null -ne $actualInit){$r.NvmlLive=$true;$r.NvmlInitFact=$actualInit}
            if($null -ne $r.CurrentSample){[void]$script:samples.Remove($r.CurrentSample);$r.CurrentSample=$null}
            if($r.CloseIndex -lt $r.Acquisitions.Count){
                # Reverse acquisition order: counters, query, borrowed devices.
                $index=$r.Acquisitions.Count-1-$r.CloseIndex;$r.CloseIndex++
                $reference=$r.Acquisitions[$index]
                if($reference.State -eq [R2HandleState]::LIVE -and $reference.Ownership -eq [R2HandleOwnership]::OWNED){
                    try {
                        $closed=Consume-R2NativeOpaqueReference $Context $reference
                        if($closed.RawStatus -ne 0){$r.CloseFaults++}
                    }
                    catch {
                        $r.CloseFaults++
                        Stop-R2Guard $Context 'External' 'R2_GAUGE_OPAQUE_CLEANUP_FAILED' $null $reference.IssuerSerial
                        # Keep independent untouched acquisitions reachable; the
                        # next continuation closes them under the SAME deadline.
                    }
                }
                return 'PENDING'
            }
            if($r.NvmlLive -and -not $r.NvmlClosed){
                $r.NvmlClosed=$true # Consume before native invocation, no retry.
                try {
                    $f=Invoke-R2NativeCall $Context ([R2ApiId]::nvmlShutdown) @()
                    if($f.RawStatus -ne 0){$r.CloseFaults++;Stop-R2Guard $Context 'External' 'R2_NVML_SHUTDOWN_FAILED' $f.RawStatus $f.IssuerSerial}
                }catch{$r.CloseFaults++;Stop-R2Guard $Context 'External' 'R2_NVML_SHUTDOWN_EXCEPTION' $null 0}
                return 'PENDING'
            }
            if($r.ReleaseIndex -lt $r.Buffers.Count){
                $b=$r.Buffers[$r.Buffers.Count-1-$r.ReleaseIndex];$r.ReleaseIndex++
                if($b.State -eq [R2HandleState]::LIVE){
                    try {Release-R2NativeBuffer $Context $b}
                    catch {$r.CloseFaults++;Stop-R2Guard $Context 'External' 'R2_GAUGE_BUFFER_CLEANUP_FAILED' $null $b.IssuerSerial}
                }
                return 'PENDING'
            }
            foreach($buffer in $r.Buffers){
                if($buffer.State -ne [R2HandleState]::CONSUMED){$r.CloseUnknown=$true}
            }
            # An unsuccessful once-close leaves residue UNKNOWN. It cannot be
            # retried or labelled CLOSED merely because every attempt was made.
            if($r.CloseUnknown -or $r.CloseFaults -gt 0){return 'PENDING'}
            $r.Closed=$true
            return 'CLOSED'
        }
        Export-ModuleMember -Function Initialize-R2Gauges,Read-R2GaugeFrame,Assert-R2GaugeFrame,Close-R2GaugesStep
    }
    Import-Module $owner -Global -ErrorAction Stop
}

# These wrappers do no native work while the file is loaded. The private module
# is created only on the first explicitly called component operation after q0.
function Initialize-R2Gauges {
    [CmdletBinding()]param([Parameter(Mandatory)][object]$Context)
    Initialize-R2GaugeOwner
    Initialize-R2Gauges -Context $Context
}
function Read-R2GaugeFrame {
    [CmdletBinding()]param([Parameter(Mandatory)][object]$Context)
    Initialize-R2GaugeOwner
    Read-R2GaugeFrame -Context $Context
}
function Assert-R2GaugeFrame {
    [CmdletBinding()]param([Parameter(Mandatory)][object]$Context,[Parameter(Mandatory)][object]$Sample)
    Initialize-R2GaugeOwner
    Assert-R2GaugeFrame -Context $Context -Sample $Sample
}
function Close-R2GaugesStep {
    [CmdletBinding()]param([Parameter(Mandatory)][object]$Context)
    Initialize-R2GaugeOwner
    Close-R2GaugesStep -Context $Context
}
