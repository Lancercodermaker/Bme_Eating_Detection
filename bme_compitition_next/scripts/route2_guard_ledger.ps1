# SOURCE ONLY. Load after route2_guard_interop.ps1 definitions. No native work is
# performed by loading this file. New-R2Ledger is called only after original q0.
# The module created there keeps the issuance tables out of exported record views.
# Windows PowerShell 5.1 lacks UInt32 enum syntax. These exact fixed enums are
# defined in memory inside New-R2Ledger, after q0; file loading emits nothing.

function Initialize-R2LedgerEnums {
    $enumTables=[ordered]@{
        R2Fact=@('UNKNOWN','TRUE','FALSE')
        R2HandleOwnership=@('UNKNOWN','OWNED','BORROWED')
        R2HandleState=@('UNKNOWN','RESERVED','LIVE','CONSUMED')
        R2ChildState=@('RESERVED','BORN_SUSPENDED','BIRTH_CONFIRMED','RESUME_REQUESTED','RUNNING_OBSERVED','TERMINATE_REQUESTED','EXIT_OBSERVED','JOINED','FAULTED')
        R2PipeState=@('RESERVED','CREATED','CONNECT_PENDING','CONNECTED_VERIFIED','EOF_OBSERVED','DISCONNECT_REQUESTED','CLOSED','FAULTED')
        R2PeerState=@('RESERVED','BOOTSTRAP_PENDING','CONNECTED_VERIFIED','READY_OBSERVED','STOP_LATCHED','EXITING_OBSERVED','JOINED','FAULTED')
        R2IoState=@('RESERVED','ISSUED','PENDING','CANCEL_REQUESTED','COMPLETED','RELEASED','FAULTED')
        R2IoOperation=@('CONNECT','READ','WRITE')
        R2Role=@('ROOT','CONTROLLER','WATCHDOG','TRANSPORT','PREP')
        R2HandleKind=@('PROCESS','THREAD','JOB','PIPE','EVENT','TOKEN','LOCAL_ALLOCATION','FILE','SNAPSHOT')
    }
    $existing='R2Fact' -as [type]
    if($null -ne $existing){
        foreach($enumName in $enumTables.Keys){
            $type=$enumName -as [type]
            if($null -eq $type -or -not $type.IsEnum -or [Enum]::GetUnderlyingType($type) -ne [uint32] -or $type.Assembly.GetName().Name -cne 'Route2OriginalLedgerEnums'){throw 'R2_ENUM_SUBSTITUTION'}
            $names=[Enum]::GetNames($type)
            if($names.Count -ne $enumTables[$enumName].Count){throw 'R2_ENUM_SUBSTITUTION'}
            for($i=0;$i -lt $names.Count;$i++){if($names[$i] -cne $enumTables[$enumName][$i] -or [uint32][Enum]::Parse($type,$names[$i]) -ne $i){throw 'R2_ENUM_SUBSTITUTION'}}
        }
        return
    }
    $assemblyName=[Reflection.AssemblyName]::new('Route2OriginalLedgerEnums')
    $assembly=[AppDomain]::CurrentDomain.DefineDynamicAssembly($assemblyName,[Reflection.Emit.AssemblyBuilderAccess]::Run)
    $enumModule=$assembly.DefineDynamicModule('Route2OriginalLedgerEnums')
    foreach($enumName in $enumTables.Keys){
        if($null -ne ($enumName -as [type])){throw 'R2_ENUM_ALREADY_DEFINED'}
        $builder=$enumModule.DefineEnum($enumName,[Reflection.TypeAttributes]::Public,[uint32])
        $value=[uint32]0
        foreach($member in $enumTables[$enumName]){[void]$builder.DefineLiteral($member,$value);$value++}
        [void]$builder.CreateType()
    }
}

function New-R2Ledger {
    [CmdletBinding()]
    param([Parameter(Mandatory)][long]$Q0,[Parameter(Mandatory)][long]$Frequency,[Parameter(Mandatory)][object]$Plan)
    if (Get-Module -Name Route2OriginalLedger) { throw 'R2_LEDGER_REISSUE' }
    Assert-R2StaticPlan -Plan $Plan
    Initialize-R2LedgerEnums
    $privateModule = New-Module -Name Route2OriginalLedger -ScriptBlock {
        $script:root = $null
        $script:issuer = [object]::new()
        $script:serial = [uint64]0
        $script:objects = [System.Collections.Generic.List[object]]::new()
        $script:objectIndex = [Runtime.CompilerServices.ConditionalWeakTable[object,object]]::new()
        $script:retiredFacts=[Runtime.CompilerServices.ConditionalWeakTable[object,object]]::new()
        $script:activeFacts=[Collections.Generic.List[object]]::new(48)
        $script:essentialFacts=[Collections.Generic.List[object]]::new(4096)
        $script:activeFactBytes=0L;$script:essentialFactBytes=0L
        $script:thread = [Threading.Thread]::CurrentThread.ManagedThreadId

        function New-R2View([System.Collections.Generic.Dictionary[string,object]]$Data) {
            return ,([System.Collections.ObjectModel.ReadOnlyDictionary[string,object]]::new($Data))
        }
        function New-R2Map([hashtable]$Fields) {
            $d = [System.Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
            foreach ($key in $Fields.Keys) { $d.Add([string]$key,$Fields[$key]) }
            return ,$d
        }
        function Get-R2Registered([object]$Reference,[string]$Type) {
            if ([Threading.Thread]::CurrentThread.ManagedThreadId -ne $script:thread) { throw 'R2_OWNER_THREAD' }
            $entry=$null
            if($null -eq $Reference -or -not $script:objectIndex.TryGetValue($Reference,[ref]$entry) -or -not [object]::ReferenceEquals($entry.View,$Reference)){throw 'R2_UNISSUED_REFERENCE'}
            if ($Type -and $entry.Type -cne $Type) { throw 'R2_RECORD_KIND' }
            if (-not [object]::ReferenceEquals($entry.Data.IssuerIdentity,$script:issuer)) { throw 'R2_ISSUER' }
            return $entry
        }
        function New-R2Record([string]$Type,[object]$Context,[object]$Slot,[hashtable]$Fields) {
            if ($script:serial -eq [uint64]::MaxValue) { throw 'R2_SERIAL_EXHAUSTED' }
            $script:serial++
            $d = New-R2Map $Fields
            $d['IssuerIdentity']=$script:issuer; $d['IssuerSerial']=$script:serial
            $d['ContextReference']=$Context; $d['PlanReference']=$script:root.Data.PlanReference
            $d['OriginalSlotReference']=$Slot
            $v = New-R2View $d
            $e = [pscustomobject]@{ Type=$Type; View=$v; Data=$d; Private=(New-R2Map @{}) }
            if($Type -ceq 'NativeFact'){
                if($script:activeFacts.Count -ge 48){throw 'R2_ACTIVE_FACT_LIMIT'}
                $e.Private['Retired']=$false;$e.Private['Retained']=$false;$e.Private['StorageCharge']=256L
                Assert-R2FactStorage 256
                $script:activeFactBytes+=256;$script:activeFacts.Add($e)
            }elseif($Type -ceq 'BufferSlice' -or ($Type -ceq 'ComponentIdentity' -and $Fields.Kind -ceq 'PendingIo')){
                # Borrowed slices and process-owned logical-I/O issuance tokens
                # carry no independent resource. Their original reference remains
                # authenticated by the weak identity table while held by an owner.
            }else{$script:objects.Add($e)}
            $script:objectIndex.Add($v,$e)
            return $e
        }
        function Assert-R2FactStorage([long]$Additional){
            $limit=if($script:root.Private.ContainsKey('PeerRole')){174762L}else{524288L}
            if($Additional -lt 0 -or [bigint]$script:root.Private.BytesReserved+$script:activeFactBytes+$script:essentialFactBytes+$Additional -gt $limit){Stop-R2Guard $script:root.View 'External' 'R2_FACT_STORAGE_LIMIT' $null 0;throw 'R2_FACT_STORAGE_LIMIT'}
            # These are explicit storage reservations. Actual CLR object/header,
            # allocator and provider fees still require the independent RAM gauge.
        }
        function Retire-R2NativeFact([object]$Context,[object]$Fact){
            Assert-R2ContextReference $Context
            $retiredSerial=$null
            if($null -ne $Fact -and $script:retiredFacts.TryGetValue($Fact,[ref]$retiredSerial)){return}
            $entry=Get-R2Registered $Fact 'NativeFact'
            if($entry.Private.Retained){return} # Permanent original evidence.
            $entry.Private.Retired=$true
            $script:retiredFacts.Add($entry.View,[object]$entry.Data.IssuerSerial)
            [void]$script:objectIndex.Remove($entry.View)
            [void]$script:activeFacts.Remove($entry)
            $script:activeFactBytes-=[long]$entry.Private.StorageCharge
            $entry.Private.Clear() # Views contain descriptors/scalars, no payload.
        }
        function Retire-R2BufferFacts([object]$Buffer){
            $bufferEntry=Get-R2Registered $Buffer ''
            if($bufferEntry.Type -ceq 'BufferSlice'){$Buffer=$bufferEntry.Data.BufferOwnerReference}
            for($n=$script:activeFacts.Count-1;$n -ge 0;$n--){
                $fact=$script:activeFacts[$n]
                if(-not $fact.Private.ContainsKey('OutputLeases')){continue}
                foreach($lease in $fact.Private.OutputLeases.Values){
                    if([object]::ReferenceEquals($lease.Owner,$Buffer)){Retire-R2NativeFact $script:root.View $fact.View;break}
                }
            }
        }
        function Retain-R2NativeFact([object]$Context,[object]$Fact){
            Assert-R2NativeFact $Context $Fact
            $entry=Get-R2Registered $Fact 'NativeFact'
            if($entry.Private.Retained){return}
            if($script:essentialFacts.Count -ge 4096){Throw-R2Fault 'R2_ESSENTIAL_FACT_LIMIT'}
            $bytes=0L
            if($entry.Private.ContainsKey('OutputLeases')){foreach($lease in $entry.Private.OutputLeases.Values){if($lease.Valid -and $null -eq $lease.Data){$bytes+=$lease.Length}}}
            if($bytes -gt 4096){Throw-R2Fault 'R2_TRANSIENT_PAYLOAD_NOT_ESSENTIAL'}
            Assert-R2FactStorage $bytes
            # Reserve storage BEFORE allocation/copy, including a partial failure.
            $script:activeFactBytes+=$bytes;$entry.Private.StorageCharge+=$bytes
            if($entry.Private.ContainsKey('OutputLeases')){
                foreach($lease in $entry.Private.OutputLeases.Values){
                    if(-not $lease.Valid){continue}
                    if($null -eq $lease.Data){$lease.Data=[byte[]]::new([int]$lease.Length)}
                    if($null -eq $lease.ReadOnlyData){$lease.ReadOnlyData=[Array]::AsReadOnly($lease.Data)}
                    if($null -ne $lease.Owner){[Runtime.InteropServices.Marshal]::Copy($lease.Address,$lease.Data,0,$lease.Data.Length);$lease.Owner=$null;$lease.Address=[IntPtr]::Zero}
                }
            }
            $entry.Private.Retained=$true
            [void]$script:activeFacts.Remove($entry)
            $script:activeFactBytes-=[long]$entry.Private.StorageCharge
            $script:essentialFactBytes+=[long]$entry.Private.StorageCharge
            $script:essentialFacts.Add($entry)
        }
        function Get-R2FactLease([object]$Fact,[int]$Index,[int]$Offset,[int]$Count){
            $entry=Get-R2Registered $Fact 'NativeFact'
            $key=[string]$Index
            if(-not $entry.Private.ContainsKey('OutputLeases') -or -not $entry.Private.OutputLeases.ContainsKey($key)){throw 'R2_FACT_PAYLOAD_UNAVAILABLE'}
            $lease=$entry.Private.OutputLeases[$key]
            if(-not $lease.Valid -or $Offset -lt 0 -or $Count -lt 0 -or [bigint]$Offset+$Count -gt $lease.Length){throw 'R2_FACT_PAYLOAD_RANGE'}
            return $lease
        }
        function Read-R2FactInt64([object]$Fact,[int]$Index,[int]$Offset=0){
            $lease=Get-R2FactLease $Fact $Index $Offset 8
            if($null -ne $lease.Data -and $null -eq $lease.Owner){return [BitConverter]::ToInt64($lease.Data,$Offset)}
            return [Runtime.InteropServices.Marshal]::ReadInt64($lease.Address,$Offset)
        }
        function Read-R2FactUInt32([object]$Fact,[int]$Index,[int]$Offset=0){
            $lease=Get-R2FactLease $Fact $Index $Offset 4
            if($null -ne $lease.Data -and $null -eq $lease.Owner){return [BitConverter]::ToUInt32($lease.Data,$Offset)}
            return [uint32]([long][Runtime.InteropServices.Marshal]::ReadInt32($lease.Address,$Offset) -band 4294967295L)
        }
        function Assert-R2ContextReference([object]$Context) {
            $e=Get-R2Registered $Context 'Context'
            if (-not [object]::ReferenceEquals($e,$script:root)) { throw 'R2_CONTEXT_SUBSTITUTION' }
            if (-not [object]::ReferenceEquals($e.Data.PlanReference,$script:root.Private.Plan)) { throw 'R2_PLAN_SUBSTITUTION' }
        }
        function Assert-R2PlanSlot([object]$Context,[object]$Slot) {
            Assert-R2ContextReference $Context
            foreach($original in $script:root.Private.Slots) {
                if ([object]::ReferenceEquals($original,$Slot)) { return }
            }
            throw 'R2_SLOT_SUBSTITUTION'
        }
        function Get-R2CurrentSlot([object]$Context) {
            Assert-R2ContextReference $Context
            if ($null -eq $script:root.Private.Step) { throw 'R2_NO_ACTIVE_STEP' }
            return ,$script:root.Private.Step.Slot
        }
        function New-R2LedgerState([long]$Q0,[long]$Frequency,[object]$Plan) {
            if ($null -ne $script:root) { throw 'R2_LEDGER_REISSUE' }
            if ($Q0 -le 0 -or $Frequency -le 0 -or $Frequency -ne [Diagnostics.Stopwatch]::Frequency) { throw 'R2_CLOCK_INPUT' }
            if ([IntPtr]::Size -ne 8) { throw 'R2_X64_REQUIRED' }
            $external=[bigint]$Q0+6000*[bigint]$Frequency
            if ($external -gt [long]::MaxValue) { throw 'R2_DEADLINE_OVERFLOW' }
            $slots=@($Plan.Slots)
            if ($slots.Count -eq 0 -or $slots.Count -gt 64) { throw 'R2_SLOT_COUNT' }
            $seen=[Collections.Generic.HashSet[uint32]]::new()
            foreach($slot in $slots) {
                if (-not ($slot.Id -is [uint32]) -or -not $seen.Add($slot.Id)) { throw 'R2_SLOT_ID' }
            }
            $work=New-R2Map @{Births=[long]0;Handles=[long]0;Faults=[long]0;Observations=[long]0;Calls=[long]1;BufferBytes=[long]0;DiskInstances=[long]0}
            $cleanup=New-R2Map @{Births=[long]0;Handles=[long]0;Faults=[long]0;Observations=[long]0;Calls=[long]0;BufferBytes=[long]0;DiskInstances=[long]0}
            $origins=New-R2Map @{Prep=$null;Study=$null;External=$null}
            $jobs=New-R2Map @{External=$null;Prep=$null}
            $registry=[Collections.Generic.List[object]]::new()
            $peers=[Collections.Generic.List[object]]::new()
            $faults=[Collections.Generic.List[object]]::new(64)
            $d=New-R2Map @{Q0=$Q0;Frequency=$Frequency;PrepDeadline=[long]([bigint]$Q0+1800*[bigint]$Frequency);ExternalDeadline=[long]$external;StudyDeadline=$null;StopState=[R2Fact]::FALSE;PrimaryFault=$null;CleanupOrigins=(New-R2View $origins);Counters=(New-R2View (New-R2Map @{Work=(New-R2View $work);Cleanup=(New-R2View $cleanup)}));Registry=$registry.AsReadOnly();Jobs=(New-R2View $jobs);Peers=$peers.AsReadOnly();GaugeState=$null;TargetOwner=$null;PlanReference=$Plan;Interop=$null;CleanupFaults=$faults.AsReadOnly();IssuerIdentity=$script:issuer;IssuerSerial=[uint64]1;ContextReference=$null;OriginalSlotReference=$null;DeadlineOwnerReference=$null}
            $script:serial=[uint64]1
            $v=New-R2View $d; $d['ContextReference']=$v;$d['DeadlineOwnerReference']=$v
            # Fixed disjoint root and three-peer portions, never four million per peer.
            $limits=New-R2Map @{Work=@{Births=224L;Handles=480L;Faults=20L;Observations=135000L;Calls=1800000L};Cleanup=@{Births=32L;Handles=160L;Faults=20L;Observations=15000L;Calls=200000L}}
            $p=New-R2Map @{Plan=$Plan;Slots=$slots;Work=$work;Cleanup=$cleanup;Origins=$origins;OriginLocked=@{Prep=$false;Study=$false;External=$false};Jobs=$jobs;Registry=$registry;Peers=$peers;Faults=$faults;Limits=$limits;Step=$null;Bound=$false;BindAttempted=$false;ClockReady=$false;ClockBuffer=[IntPtr]::Zero;LastQpc=$Q0;Nonce=$null;NonceAttempted=$false;BytesReserved=0L;DisksReserved=0L;Allotments=@{};StudyStarted=$false;OriginalStudyFact=$null;FaultOverflow=$false}
            $script:root=[pscustomobject]@{Type='Context';View=$v;Data=$d;Private=$p}
            $pool=[object[]]::new(64)
            for($i=0;$i -lt 64;$i++){
                $faultData=New-R2Map @{Domain=$null;Code=$null;NativeStatus=$null;Serial=$null;Qpc=$null;NativeFactReference=$null}
                $pool[$i]=[pscustomobject]@{Data=$faultData;View=(New-R2View $faultData)}
            }
            $p['FaultPool']=$pool
            $p['NvmlInitAttempted']=$false;$p['NvmlInitFact']=$null
            $p['NvmlShutdownAttempted']=$false;$p['NvmlShutdownFact']=$null
            $script:objects.Add($script:root)
            $script:objectIndex.Add($v,$script:root)
            return ,$v
        }
        function Stop-R2Guard([object]$Context,[string]$Domain,[string]$Code,[Nullable[long]]$NativeStatus=$null,[uint64]$Serial=0) {
            Assert-R2ContextReference $Context
            if ($Domain -cnotin @('Prep','Study','External')) { throw 'R2_DOMAIN' }
            if ([string]::IsNullOrEmpty($Code) -or $Code.Length -gt 128) { throw 'R2_FAULT_CODE' }
            $r=$script:root
            # Latch first, before any fault allocation, reporting or cleanup.
            $first=($r.Data.StopState -eq [R2Fact]::FALSE)
            $r.Data['StopState']=[R2Fact]::TRUE
            if($first){
                # Lock BEFORE sampling. An unavailable original failure clock stays
                # UNKNOWN; cleanup cannot acquire a later fresh sixty seconds.
                $affected=@('Prep','External')
                if($null -ne $r.Data.StudyDeadline){$affected+= 'Study'}
                $newOrigins=[Collections.Generic.List[string]]::new()
                foreach($originalDomain in $affected){if(-not $r.Private.OriginLocked[$originalDomain]){$r.Private.OriginLocked[$originalDomain]=$true;$newOrigins.Add($originalDomain)}}
            }
            $partition=if($null -ne $r.Private.Step -and $r.Private.Step.Cleanup){'Cleanup'}else{'Work'}
            $counter=$r.Private[$partition]
            if ($counter.Faults -ge $r.Private.Limits[$partition].Faults) {
                $r.Private.FaultOverflow=$true
                return
            }
            $index=[int]$counter.Faults+$(if($partition -ceq 'Cleanup'){32}else{0})
            $counter['Faults']=[long]$counter.Faults+1
            $fault=$r.Private.FaultPool[$index]
            $fault.Data['Domain']=$Domain;$fault.Data['Code']=$Code;$fault.Data['NativeStatus']=$NativeStatus;$fault.Data['Serial']=$Serial
            foreach($issued in $script:activeFacts){if($issued.Data.IssuerSerial -eq $Serial){$fault.Data['NativeFactReference']=$issued.View;break}}
            if($null -eq $fault.Data.NativeFactReference){foreach($issued in $script:essentialFacts){if($issued.Data.IssuerSerial -eq $Serial){$fault.Data['NativeFactReference']=$issued.View;break}}}
            if($first){$r.Data['PrimaryFault']=$fault.View}else{$r.Private.Faults.Add($fault.View)}
            # The primary is already retained even if clock logging cannot run.
            try{$fault.Data['Qpc']=Read-R2LedgerTimestamp -ForFault $true}catch{}
            if($first){foreach($originalDomain in $newOrigins){$r.Private.Origins[$originalDomain]=$fault.Data.Qpc}}
        }
        function Throw-R2Fault([string]$Code,[Nullable[long]]$Status=$null,[uint64]$Serial=0) {
            $domain=if($null -ne $script:root.Private.Step){$script:root.Private.Step.Domain}else{'External'}
            Stop-R2Guard $script:root.View $domain $Code $Status $Serial
            throw $Code
        }
        function Get-R2DomainDeadline([string]$Domain) {
            switch -CaseSensitive($Domain) {
                'Prep' { return [long]$script:root.Data.PrepDeadline }
                'External' { return [long]$script:root.Data.ExternalDeadline }
                'Study' { if($null -eq $script:root.Data.StudyDeadline){Throw-R2Fault 'R2_STUDY_NOT_STARTED'}; return [long]$script:root.Data.StudyDeadline }
                default { Throw-R2Fault 'R2_DOMAIN' }
            }
        }
        function Get-R2Deadline([object]$Context,[string]$Domain,[bool]$Cleanup) {
            Assert-R2ContextReference $Context
            $d=[Math]::Min((Get-R2DomainDeadline $Domain),[long]$script:root.Data.ExternalDeadline)
            if($null -ne $script:root.Private.Step -and $script:root.Private.Step.Domain -ceq $Domain){$d=[Math]::Min($d,[long]$script:root.Private.Step.LocalDeadline)}
            if($Cleanup){
                $c0=$script:root.Private.Origins[$Domain]
                if($null -eq $c0){Throw-R2Fault 'R2_CLEANUP_NOT_BEGUN'}
                $end=[bigint]$c0+60*[bigint]$script:root.Data.Frequency
                $d=[long][bigint]::Min([bigint]$d,$end)
            }
            return $d
        }
        function Begin-R2LedgerCleanup([object]$Context,[string]$Domain) {
            Assert-R2ContextReference $Context
            [void](Get-R2DomainDeadline $Domain)
            if(-not $script:root.Private.OriginLocked[$Domain]){
                $script:root.Private.OriginLocked[$Domain]=$true
                $script:root.Private.Origins[$Domain]=(Read-R2LedgerTimestamp -CleanupClock $true)
            }
            return (Get-R2Deadline $Context $Domain $true)
        }
        function Add-R2Budget([string]$Name,[long]$Count=1) {
            if($Count -lt 0){Throw-R2Fault 'R2_NEGATIVE_BUDGET'}
            $s=$script:root.Private.Step
            if($null -eq $s){Throw-R2Fault 'R2_NO_ACTIVE_STEP'}
            $partition=if($s.Cleanup){'Cleanup'}else{'Work'}
            $counter=$script:root.Private[$partition]
            if(-not $counter.ContainsKey($Name) -or -not $script:root.Private.Limits[$partition].ContainsKey($Name)){Throw-R2Fault 'R2_BUDGET_NAME'}
            $next=[bigint]$counter[$Name]+$Count
            if($next -gt $script:root.Private.Limits[$partition][$Name]){Throw-R2Fault 'R2_GLOBAL_BUDGET_EXHAUSTED'}
            $slotField=switch($Name){'Births'{'MaxBirths'}'Handles'{'MaxHandles'}'Calls'{'MaxCalls'}default{$null}}
            if($slotField){
                $slotKey=[string]$s.Slot.Id
                $usage=$script:root.Private.SlotUsage[$slotKey]
                $slotNext=[bigint]$usage[$Name]+$Count
                if($slotNext -gt [long]$s.Slot[$slotField]){Throw-R2Fault 'R2_SLOT_BUDGET_EXHAUSTED'}
                $usage[$Name]=[long]$slotNext
            }
            if($Name -ceq 'Calls'){
                if([bigint]$s.Calls+$Count -gt $s.CallLimit){Throw-R2Fault 'R2_STEP_CALL_LIMIT'}
                $s.Calls=[long]$s.Calls+$Count
            }
            $counter[$Name]=[long]$next
        }
        function Read-R2LedgerTimestamp([bool]$ForFault=$false,[bool]$CleanupClock=$false) {
            # Stopwatch.GetTimestamp is itself a native QPC call on the pinned
            # Framework. Charge it BEFORE calling; no separate clock allowance.
            $step=$script:root.Private.Step
            if($null -eq $step){
                # Faults outside an operation retain UNKNOWN time. They cannot
                # escape slot/step accounting or start a later cleanup window.
                if($ForFault){return $null}
                Stop-R2Guard $script:root.View 'External' 'R2_CLOCK_REQUIRES_ACTIVE_STEP' $null 0
                throw 'R2_CLOCK_REQUIRES_ACTIVE_STEP'
            }
            $partition=if(($null -ne $step -and $step.Cleanup) -or ($null -eq $step -and $CleanupClock)){'Cleanup'}else{'Work'}
            $counter=$script:root.Private[$partition]
            $allowed=($counter.Calls -lt $script:root.Private.Limits[$partition].Calls)
            $usage=$null
            if($null -ne $step){
                $usage=$script:root.Private.SlotUsage[[string]$step.Slot.Id]
                $allowed=$allowed -and $step.Calls -lt $step.CallLimit -and $usage.Calls -lt [long]$step.Slot.MaxCalls
            }
            if(-not $allowed){
                if($ForFault){return $null}
                Stop-R2Guard $script:root.View 'External' 'R2_CLOCK_CALL_BUDGET' $null 0
                throw 'R2_CLOCK_CALL_BUDGET'
            }
            $counter['Calls']=[long]$counter.Calls+1
            if($null -ne $step){$step.Calls++;$usage.Calls++}
            return [Diagnostics.Stopwatch]::GetTimestamp()
        }
        function Get-R2LedgerTimestamp([object]$Context) {
            Assert-R2ContextReference $Context
            if(-not $script:root.Private.ClockReady){Throw-R2Fault 'R2_NATIVE_CLOCK_NOT_READY'}
            return (Read-R2LedgerTimestamp)
        }
        function Enter-R2LedgerStep([object]$Context,[uint32]$SlotId,[uint32]$Operation=0,[bool]$Cleanup=$false,[bool]$Observer=$false) {
            Assert-R2ContextReference $Context
            if($null -ne $script:root.Private.Step){Throw-R2Fault 'R2_NESTED_STEP'}
            $slot=$null
            foreach($candidate in $script:root.Private.Slots){if($candidate.Id -eq $SlotId){$slot=$candidate;break}}
            if($null -eq $slot){Throw-R2Fault 'R2_UNKNOWN_SLOT'}
            if($slot.ProducerName -ceq 'RESERVED_NONEXECUTABLE'){Throw-R2Fault 'R2_RESERVED_SLOT'}
            $domain=switch -CaseSensitive([string]$slot.Phase){'Prep'{'Prep'}'PREP'{'Prep'}'Study'{'Study'}'STUDY'{'Study'}'External'{'External'}'EXTERNAL'{'External'}default{Throw-R2Fault 'R2_SLOT_PHASE'}}
            if(-not $Cleanup -and $script:root.Data.StopState -eq [R2Fact]::TRUE){throw 'R2_STOP_LATCHED'}
            if(-not $script:root.Private.ContainsKey('SlotUsage')){$script:root.Private['SlotUsage']=@{}}
            $key=[string]$SlotId
            if(-not $script:root.Private.SlotUsage.ContainsKey($key)){$script:root.Private.SlotUsage[$key]=@{Births=0L;Handles=0L;Calls=0L;Bytes=0L;FirstStartedQpc=$null}}
            $duration=[long]$slot.MaxDurationTicks
            if($duration -le 0){Throw-R2Fault 'R2_SLOT_DURATION'}
            # Install the actual slot/step BEFORE its first charged QPC, including
            # the first cleanup-origin sample. No uncounted entry-clock allowance.
            $script:root.Private.Step=[pscustomobject]@{Slot=$slot;Operation=$Operation;Domain=$domain;Cleanup=$Cleanup;Observer=$Observer;Calls=0L;CallLimit=$(if($Observer){12L}else{48L});StartedQpc=$null;LocalDeadline=[long]::MaxValue}
            $now=(Read-R2LedgerTimestamp -CleanupClock $Cleanup)
            $script:root.Private.Step.StartedQpc=$now
            if($Cleanup){[void](Begin-R2LedgerCleanup $Context $domain)}
            $slotUsage=$script:root.Private.SlotUsage[$key]
            if($null -eq $slotUsage.FirstStartedQpc){$slotUsage.FirstStartedQpc=$now}
            $local=[bigint]$slotUsage.FirstStartedQpc+$duration
            if($local -gt [long]::MaxValue){Throw-R2Fault 'R2_LOCAL_DEADLINE_OVERFLOW'}
            $script:root.Private.Step.LocalDeadline=[long]$local
            Assert-R2Operation $Context $SlotId $Operation
        }
        function Assert-R2Operation([object]$Context,[uint32]$SlotId,[uint32]$Operation) {
            Assert-R2ContextReference $Context
            $s=$script:root.Private.Step
            if($null -eq $s -or $s.Slot.Id -ne $SlotId -or $s.Operation -ne $Operation){Throw-R2Fault 'R2_OPERATION_BINDING'}
            Assert-R2PlanSlot $Context $s.Slot
            if(-not $s.Cleanup -and $script:root.Data.StopState -eq [R2Fact]::TRUE){throw 'R2_STOP_LATCHED'}
            $now=(Read-R2LedgerTimestamp)
            $d=Get-R2Deadline $Context $s.Domain $s.Cleanup
            if(-not $s.Cleanup){
                $domainWork=[Math]::Min((Get-R2DomainDeadline $s.Domain),[long]$script:root.Data.ExternalDeadline)-[long](60*[bigint]$script:root.Data.Frequency)
                $d=[Math]::Min($d,$domainWork)
            }
            if($now -lt $script:root.Data.Q0 -or $now -ge $d){Throw-R2Fault 'R2_DEADLINE'}
            if(([bigint]$now-$s.StartedQpc)*10 -gt $script:root.Data.Frequency){Throw-R2Fault 'R2_STEP_100MS'}
        }
        function Exit-R2LedgerStep([object]$Context) {
            Assert-R2ContextReference $Context
            $s=$script:root.Private.Step
            if($null -eq $s){Throw-R2Fault 'R2_NO_ACTIVE_STEP'}
            try { Assert-R2Operation $Context $s.Slot.Id $s.Operation }
            finally {
                for($n=$script:activeFacts.Count-1;$n -ge 0;$n--){Retire-R2NativeFact $Context $script:activeFacts[$n].View}
                $script:root.Private.Step=$null
            }
        }
        function Add-R2BirthAttempt([object]$Context) { Assert-R2ContextReference $Context; if($script:root.Data.StopState -eq [R2Fact]::TRUE){throw 'R2_STOP_NO_BIRTH'}; Add-R2Budget 'Births' }
        function Add-R2ObservationAttempt([object]$Context) { Assert-R2ContextReference $Context; Add-R2Budget 'Observations' }
        function Reserve-R2DiskInstances([object]$Context,[uint32]$Count) {
            Assert-R2ContextReference $Context
            $step=$script:root.Private.Step
            if($null -eq $step){Throw-R2Fault 'R2_NO_ACTIVE_STEP'}
            Assert-R2Operation $Context $step.Slot.Id $step.Operation
            if([bigint]$script:root.Private.DisksReserved+$Count -gt 32){Throw-R2Fault 'R2_DISK_INSTANCE_LIMIT'}
            $script:root.Private.DisksReserved+=$Count
            $counter=if($step.Cleanup){$script:root.Private.Cleanup}else{$script:root.Private.Work}
            $counter['DiskInstances']=[long]$counter.DiskInstances+$Count
        }
        function Bind-R2Interop([object]$Context,[object]$Interop) {
            Assert-R2ContextReference $Context
            if($script:root.Private.BindAttempted){Throw-R2Fault 'R2_INTEROP_REBIND'}
            $script:root.Private.BindAttempted=$true
            try{
                Assert-R2InteropConstruction $Interop
                $plan=Get-R2InteropPlanReference $Interop
                if(-not [object]::ReferenceEquals($plan,$script:root.Data.PlanReference)){Throw-R2Fault 'R2_INTEROP_PLAN'}
                Bind-R2InteropInternal $Context $Interop
                $script:root.Data['Interop']=$Interop
                $script:root.Private.Bound=$true
            }catch{Stop-R2Guard $Context 'External' 'R2_INTEROP_BIND_FAILED' $null 0;throw}
        }
        function Assert-R2Bound([object]$Context) {
            Assert-R2ContextReference $Context
            if(-not $script:root.Private.Bound -or $null -eq $script:root.Data.Interop){Throw-R2Fault 'R2_INTEROP_UNBOUND'}
        }
        function New-R2NativeBuffer([object]$Context,[object]$Slot,[uint32]$Capacity,[uint32]$Alignment=8) {
            Assert-R2ContextReference $Context; Assert-R2PlanSlot $Context $Slot
            $s=$script:root.Private.Step
            if($null -eq $s -or -not [object]::ReferenceEquals($s.Slot,$Slot)){Throw-R2Fault 'R2_BUFFER_SLOT'}
            Assert-R2Operation $Context $Slot.Id $s.Operation
            if($Capacity -eq 0 -or $Capacity -gt 1048576 -or $Alignment -notin @(1,2,4,8,16)){Throw-R2Fault 'R2_BUFFER_BOUNDS'}
            $charged=[long]$Capacity+$Alignment-1
            Assert-R2FactStorage $charged
            $localBufferLimit=if($script:root.Private.ContainsKey('PeerRole')){174762L}else{524288L}
            if([bigint]$script:root.Private.BytesReserved+$charged -gt $localBufferLimit){Throw-R2Fault 'R2_BUFFER_GLOBAL_LIMIT'}
            $usage=$script:root.Private.SlotUsage[[string]$Slot.Id]
            if([bigint]$usage.Bytes+$charged -gt [long]$Slot.MaxBytes){Throw-R2Fault 'R2_BUFFER_SLOT_LIMIT'}
            $script:root.Private.BytesReserved+=$charged; $usage.Bytes+=$charged
            $counter=if($s.Cleanup){$script:root.Private.Cleanup}else{$script:root.Private.Work}
            $counter['BufferBytes']=[long]$counter.BufferBytes+$charged
            Add-R2Budget 'Handles'
            $e=New-R2Record 'Buffer' $Context $Slot @{Address=$null;Capacity=$Capacity;Alignment=$Alignment;State=[R2HandleState]::RESERVED;Ownership=[R2HandleOwnership]::OWNED}
            $script:root.Private.Registry.Add($e.View)
            Add-R2Budget 'Calls'
            try{
                $base=[Runtime.InteropServices.Marshal]::AllocHGlobal([int]$charged)
                if($base -eq [IntPtr]::Zero){Throw-R2Fault 'R2_BUFFER_ALLOCATION_NULL'}
                $e.Private['Base']=$base
                $address=[long]$base.ToInt64()
                $padding=($Alignment-($address % $Alignment)) % $Alignment
                $e.Data['Address']=[IntPtr]::new($address+$padding); $e.Data['State']=[R2HandleState]::LIVE
                # Bounded initialization; no allocation growth or unsafe uninitialized output.
                for($i=0;$i -lt $Capacity;$i++){[Runtime.InteropServices.Marshal]::WriteByte($e.Data.Address,$i,0)}
            }catch{Stop-R2Guard $Context $s.Domain 'R2_BUFFER_ALLOCATION_FAILED' $null $e.Data.IssuerSerial;throw}
            return ,$e.View
        }
        function Get-R2BufferEntry([object]$Context,[object]$Buffer,[uint32]$Offset,[uint32]$Count) {
            Assert-R2ContextReference $Context
            $e=Get-R2Registered $Buffer 'Buffer'
            if(-not [object]::ReferenceEquals($e.Data.ContextReference,$Context) -or $e.Data.State -ne [R2HandleState]::LIVE){Throw-R2Fault 'R2_BUFFER_NOT_LIVE'}
            if([bigint]$Offset+$Count -gt $e.Data.Capacity){Throw-R2Fault 'R2_BUFFER_RANGE'}
            return $e
        }
        function Get-R2NativeBufferPointer([object]$Context,[object]$Buffer,[uint32]$Offset=0) {
            $e=Get-R2BufferEntry $Context $Buffer $Offset 0
            return [IntPtr]::Add($e.Data.Address,[int]$Offset)
        }
        function Write-R2NativeBuffer([object]$Context,[object]$Buffer,[uint32]$Offset,[byte[]]$Bytes) {
            if($null -eq $Bytes){Throw-R2Fault 'R2_NULL_BYTES'}
            $e=Get-R2BufferEntry $Context $Buffer $Offset ([uint32]$Bytes.Length)
            Retire-R2BufferFacts $Buffer
            [Runtime.InteropServices.Marshal]::Copy($Bytes,0,[IntPtr]::Add($e.Data.Address,[int]$Offset),$Bytes.Length)
        }
        function Read-R2NativeBuffer([object]$Context,[object]$Buffer,[uint32]$Offset,[uint32]$Count) {
            $e=Get-R2BufferEntry $Context $Buffer $Offset $Count
            $bytes=[byte[]]::new([int]$Count)
            [Runtime.InteropServices.Marshal]::Copy([IntPtr]::Add($e.Data.Address,[int]$Offset),$bytes,0,[int]$Count)
            return ,([Array]::AsReadOnly($bytes))
        }
        function Get-R2NativeBufferSlice([object]$Context,[object]$Buffer,[uint32]$Offset,[uint32]$Length) {
            $e=Get-R2BufferEntry $Context $Buffer $Offset $Length
            if($Length -eq 0){Throw-R2Fault 'R2_EMPTY_BUFFER_SLICE'}
            $slice=New-R2Record 'BufferSlice' $Context $e.Data.OriginalSlotReference @{Address=[IntPtr]::Add($e.Data.Address,[int]$Offset);Capacity=$Length;BufferOwnerReference=$Buffer;Offset=$Offset}
            return ,$slice.View
        }
        function Write-R2NativeReference([object]$Context,[object]$Buffer,[uint32]$Offset,[object]$Reference) {
            $e=Get-R2BufferEntry $Context $Buffer $Offset 8
            Retire-R2BufferFacts $Buffer
            $referenceEntry=Get-R2Registered $Reference ''
            if($referenceEntry.Type -ceq 'Handle'){$pointer=Get-R2HandleValue $Context $Reference}
            elseif($referenceEntry.Type -ceq 'Buffer'){$pointer=Get-R2NativeBufferPointer $Context $Reference}
            elseif($referenceEntry.Type -ceq 'BufferSlice'){
                [void](Get-R2BufferEntry $Context $referenceEntry.Data.BufferOwnerReference $referenceEntry.Data.Offset $referenceEntry.Data.Capacity)
                $pointer=$referenceEntry.Data.Address
            }else{Throw-R2Fault 'R2_REFERENCE_POINTER_KIND'}
            [Runtime.InteropServices.Marshal]::WriteIntPtr($e.Data.Address,[int]$Offset,$pointer)
        }
        function Get-R2LocalAllocationView([object]$Context,[object]$Handle,[uint32]$MaximumBytes) {
            Assert-R2ContextReference $Context
            $h=Get-R2Registered $Handle 'Handle'
            if($h.Data.Kind -ne [R2HandleKind]::LOCAL_ALLOCATION -or $h.Data.State -ne [R2HandleState]::LIVE){Throw-R2Fault 'R2_NOT_LOCAL_ALLOCATION'}
            $name=[string]$h.Data.AcquireFact.ApiId
            if($name -ceq 'ConvertSidToStringSidW'){
                if($MaximumBytes -ne 512){Throw-R2Fault 'R2_SID_STRING_BOUND'}
                # The API's valid SID conversion output is NUL-terminated. Read one
                # WCHAR at a time; do not copy512 bytes past a shorter allocation.
                $actual=0
                for($i=0;$i -lt 256;$i++){
                    $actual=2*($i+1)
                    if([Runtime.InteropServices.Marshal]::ReadInt16($h.Data.LocalValue,2*$i) -eq 0){break}
                    if($i -eq 255){Throw-R2Fault 'R2_SID_STRING_UNTERMINATED'}
                }
                $length=[uint32]$actual
            }elseif($name -ceq 'ConvertStringSecurityDescriptorToSecurityDescriptorW'){
                if($MaximumBytes -gt 4096 -or $MaximumBytes -lt 20){Throw-R2Fault 'R2_DESCRIPTOR_BOUND'}
                $fact=$h.Data.AcquireFact
                $actual=Read-R2FactUInt32 $fact 3
                if($actual -lt 20 -or $actual -gt $MaximumBytes){Throw-R2Fault 'R2_DESCRIPTOR_SIZE'}
                $length=$actual
            }else{Throw-R2Fault 'R2_LOCAL_ALLOCATION_OWNER'}
            $view=New-R2Record 'LocalAllocationView' $Context $h.Data.OriginalSlotReference @{Address=$h.Data.LocalValue;Capacity=$length;HandleOwnerReference=$Handle}
            return ,$view.View
        }
        function Read-R2LocalAllocation([object]$Context,[object]$Handle,[uint32]$Offset,[uint32]$Count,[uint32]$MaxBound) {
            $view=Get-R2LocalAllocationView $Context $Handle $MaxBound
            if([bigint]$Offset+$Count -gt $view.Capacity){Throw-R2Fault 'R2_LOCAL_ALLOCATION_RANGE'}
            $bytes=[byte[]]::new([int]$Count)
            [Runtime.InteropServices.Marshal]::Copy([IntPtr]::Add($view.Address,[int]$Offset),$bytes,0,[int]$Count)
            return ,([Array]::AsReadOnly($bytes))
        }
        function Release-R2NativeBuffer([object]$Context,[object]$Buffer) {
            $e=Get-R2BufferEntry $Context $Buffer 0 0
            $step=$script:root.Private.Step
            if($null -eq $step){Throw-R2Fault 'R2_NO_ACTIVE_STEP'}
            Assert-R2Operation $Context $step.Slot.Id $step.Operation
            Retire-R2BufferFacts $Buffer
            $release=New-R2Record 'BufferReleaseFact' $Context $e.Data.OriginalSlotReference @{ManagedOperation='Marshal.FreeHGlobal';RawStatus=$null;StatusBits=$null;QpcBegin=$null;QpcEnd=$null;ReturnedVoid=[R2Fact]::UNKNOWN}
            $e.Data['ReleaseFact']=$release.View
            Add-R2Budget 'Calls'
            $begin=Read-R2LedgerTimestamp;$release.Data['QpcBegin']=$begin
            $e.Data['State']=[R2HandleState]::CONSUMED
            try{[Runtime.InteropServices.Marshal]::FreeHGlobal($e.Private.Base);$release.Data['ReturnedVoid']=[R2Fact]::TRUE}
            catch{Stop-R2Guard $Context 'External' 'R2_BUFFER_FREE_FAILED' $null $e.Data.IssuerSerial;throw}
            finally{$release.Data['QpcEnd']=Read-R2LedgerTimestamp -ForFault $true}
            $end=$release.Data.QpcEnd
            if($null -eq $end -or $end -lt $begin -or ([bigint]$end-$begin)*10 -gt $Context.Frequency){Throw-R2Fault 'R2_BUFFER_FREE_TIME_UNKNOWN_OR_100MS' $null $e.Data.IssuerSerial}
            Assert-R2Operation $Context $step.Slot.Id $step.Operation
            # Cumulative bytes are never refunded, including after successful release.
        }
        function Reserve-R2Handle([object]$Context,[R2HandleKind]$Kind,[R2HandleOwnership]$Ownership,[object]$Slot) {
            Assert-R2ContextReference $Context; Assert-R2PlanSlot $Context $Slot
            if(-not [Enum]::IsDefined([R2HandleKind],$Kind) -or $Ownership -notin @([R2HandleOwnership]::OWNED,[R2HandleOwnership]::BORROWED)){Throw-R2Fault 'R2_HANDLE_ENUM'}
            $s=$script:root.Private.Step
            if($null -eq $s -or -not [object]::ReferenceEquals($s.Slot,$Slot)){Throw-R2Fault 'R2_HANDLE_SLOT'}
            Assert-R2Operation $Context $Slot.Id $s.Operation
            Add-R2Budget 'Handles'
            $e=New-R2Record 'Handle' $Context $Slot @{Kind=$Kind;LocalValue=$null;SourceProcessReference=$null;TargetProcessReference=$null;SourceHandleReference=$null;RequestedRights=$null;Inheritable=[R2Fact]::UNKNOWN;Ownership=$Ownership;State=[R2HandleState]::RESERVED;AcquireFact=$null;ConsumeFact=$null}
            $e.Private['AttemptFact']=$null; $e.Private['ReleaseOwner']='Native'; $e.Private['Remote']=$false
            $script:root.Private.Registry.Add($e.View)
            return ,$e.View
        }
        function Assert-R2NativeFact([object]$Context,[object]$Fact) {
            Assert-R2ContextReference $Context
            $e=Get-R2Registered $Fact 'NativeFact'
            if(-not [object]::ReferenceEquals($e.Data.ContextReference,$Context)){Throw-R2Fault 'R2_FACT_CONTEXT'}
        }
        function Test-R2NativeStatus([object]$Descriptor,[object]$ReturnValue) {
            switch -CaseSensitive([string]$Descriptor.ReturnConvention){
                'BOOL' {return ([long]$ReturnValue -ne 0)}
                'HANDLE_NULL' {return ($ReturnValue -is [IntPtr] -and $ReturnValue -ne [IntPtr]::Zero)}
                'HANDLE_INVALID' {return ($ReturnValue -is [IntPtr] -and $ReturnValue.ToInt64() -ne -1)}
                'LOCALFREE' {return ($ReturnValue -is [IntPtr] -and $ReturnValue -eq [IntPtr]::Zero)}
                'NTSTATUS' {return ([int]$ReturnValue -eq 0)}
                'PDH' {return ([int]$ReturnValue -eq 0)}
                'NVML' {return ([int]$ReturnValue -eq 0)}
                'VOID' {return $true}
                'BORROWED_PSEUDO' {return ($ReturnValue -is [IntPtr] -and $ReturnValue.ToInt64() -eq -1)}
                'DWORD' {
                    if($null -ne $Descriptor.ErrorSentinel){return ([long]$ReturnValue -ne [long]$Descriptor.ErrorSentinel)}
                    return $true
                }
                default {Throw-R2Fault 'R2_UNKNOWN_STATUS_CONVENTION'}
            }
        }
        function Get-R2NativeFactOutput([object]$Context,[object]$Fact,[uint32]$ArgumentIndex,[uint32]$Offset,[uint32]$Count) {
            Assert-R2NativeFact $Context $Fact
            Retain-R2NativeFact $Context $Fact
            $lease=Get-R2FactLease $Fact $ArgumentIndex $Offset $Count
            if($Offset -eq 0 -and $Count -eq $lease.Length){return ,$lease.ReadOnlyData}
            Assert-R2FactStorage ([long]$Count+128)
            $script:essentialFactBytes+=[long]$Count+128
            $copy=[byte[]]::new([int]$Count)
            [Array]::Copy($lease.Data,[int]$Offset,$copy,0,[int]$Count)
            return ,([Array]::AsReadOnly($copy))
        }
        function Get-R2FactPointer([object]$Fact,[int]$Index,[int]$Offset=0) {
            return [IntPtr]::new((Read-R2FactInt64 $Fact $Index $Offset))
        }
        function Get-R2AcquisitionValues([object]$Fact) {
            $entries=[Collections.Generic.List[object]]::new()
            switch -CaseSensitive([string]$Fact.ApiId){
                'CreateJobObjectW' {$entries.Add(@{Kind=[R2HandleKind]::JOB;Value=$Fact.ReturnValue})}
                'CreateNamedPipeW' {$entries.Add(@{Kind=[R2HandleKind]::PIPE;Value=$Fact.ReturnValue})}
                'CreateEventW' {$entries.Add(@{Kind=[R2HandleKind]::EVENT;Value=$Fact.ReturnValue})}
                'CreateToolhelp32Snapshot' {$entries.Add(@{Kind=[R2HandleKind]::SNAPSHOT;Value=$Fact.ReturnValue})}
                'GetCurrentProcess' {$entries.Add(@{Kind=[R2HandleKind]::PROCESS;Value=$Fact.ReturnValue})}
                'CreateFileW' {$entries.Add(@{Kind=$null;Value=$Fact.ReturnValue;Allowed=@([R2HandleKind]::PIPE,[R2HandleKind]::FILE)})}
                'CreatePipe' {$entries.Add(@{Kind=[R2HandleKind]::PIPE;Value=(Get-R2FactPointer $Fact 0)});$entries.Add(@{Kind=[R2HandleKind]::PIPE;Value=(Get-R2FactPointer $Fact 1)})}
                'CreateProcessW' {$entries.Add(@{Kind=[R2HandleKind]::PROCESS;Value=(Get-R2FactPointer $Fact 9 0)});$entries.Add(@{Kind=[R2HandleKind]::THREAD;Value=(Get-R2FactPointer $Fact 9 8)})}
                'OpenProcessToken' {$entries.Add(@{Kind=[R2HandleKind]::TOKEN;Value=(Get-R2FactPointer $Fact 2)})}
                'ConvertSidToStringSidW' {$entries.Add(@{Kind=[R2HandleKind]::LOCAL_ALLOCATION;Value=(Get-R2FactPointer $Fact 1)})}
                'ConvertStringSecurityDescriptorToSecurityDescriptorW' {$entries.Add(@{Kind=[R2HandleKind]::LOCAL_ALLOCATION;Value=(Get-R2FactPointer $Fact 2)})}
                'DuplicateHandle' {$entries.Add(@{Kind=$null;Value=(Get-R2FactPointer $Fact 3);Allowed=@([R2HandleKind]::PROCESS,[R2HandleKind]::THREAD,[R2HandleKind]::JOB,[R2HandleKind]::PIPE,[R2HandleKind]::EVENT,[R2HandleKind]::TOKEN,[R2HandleKind]::FILE,[R2HandleKind]::SNAPSHOT)})}
            }
            return ,$entries
        }
        function Record-R2HandleAcquisition([object]$Context,[object]$ReservedHandle,[R2ApiId]$ApiId,[long]$RawStatus,[IntPtr]$ReturnedValue,[object]$NativeFact) {
            Assert-R2ContextReference $Context; Assert-R2NativeFact $Context $NativeFact
            $h=Get-R2Registered $ReservedHandle 'Handle'; $f=Get-R2Registered $NativeFact 'NativeFact'
            if($NativeFact.ApiId -ne $ApiId -or $NativeFact.RawStatus -ne $RawStatus -or -not [object]::ReferenceEquals($h.Data.OriginalSlotReference,$NativeFact.OriginalSlotReference)){Throw-R2Fault 'R2_ACQUIRE_FACT_BINDING'}
            if($h.Data.State -ne [R2HandleState]::RESERVED){
                if([object]::ReferenceEquals($h.Data.AcquireFact,$NativeFact) -and $h.Data.LocalValue -eq $ReturnedValue){return}
                Throw-R2Fault 'R2_HANDLE_ACQUIRE_REWRITE'
            }
            if($null -ne $h.Private.AttemptFact -and -not [object]::ReferenceEquals($h.Private.AttemptFact,$NativeFact)){Throw-R2Fault 'R2_ACQUIRE_ATTEMPT_REWRITE'}
            if(-not $f.Private.Completed){Throw-R2Fault 'R2_FACT_NOT_COMPLETED'}
            if(-not $f.Private.ContainsKey('AuthorizingReservation') -or -not [object]::ReferenceEquals($f.Private.AuthorizingReservation,$ReservedHandle)){Throw-R2Fault 'R2_ACQUIRE_RESERVATION_NOT_BOUND_TO_NATIVE_ISSUE'}
            $h.Private.AttemptFact=$NativeFact
            if(-not $f.Private.StatusAccepted){return} # Indeterminate failed outputs remain UNKNOWN.
            $match=$false
            foreach($binding in $f.Private.AcquisitionPlan){
                if([object]::ReferenceEquals($binding.Handle.View,$ReservedHandle) -and $binding.ActualValue -eq $ReturnedValue){$match=$true;break}
            }
            if(-not $match){Throw-R2Fault 'R2_HANDLE_VALUE_NOT_NATIVE_OUTPUT'}
            if([string]$ApiId -ceq 'GetCurrentProcess'){
                if($h.Data.Ownership -ne [R2HandleOwnership]::BORROWED -or $ReturnedValue.ToInt64() -ne -1){Throw-R2Fault 'R2_PSEUDO_OWNERSHIP'}
            }elseif($ReturnedValue -eq [IntPtr]::Zero -or $ReturnedValue.ToInt64() -eq -1){Throw-R2Fault 'R2_INVALID_ACQUIRED_HANDLE'}
            if([string]$ApiId -ceq 'DuplicateHandle'){
                if(-not $h.Private.ContainsKey('DuplicateSource')){Throw-R2Fault 'R2_DUPLICATE_BINDING_MISSING'}
                $source=Get-R2Registered $h.Private.DuplicateSource 'Handle'
                if($source.Data.Kind -ne $h.Data.Kind){Throw-R2Fault 'R2_DUPLICATE_KIND'}
                $a=$f.Private.Arguments
                if(-not [object]::ReferenceEquals($a[0],$h.Data.SourceProcessReference) -or -not [object]::ReferenceEquals($a[1],$source.View) -or -not [object]::ReferenceEquals($a[2],$h.Data.TargetProcessReference) -or $a[4] -ne $h.Data.RequestedRights -or $a[5] -ne $(if($h.Data.Inheritable -eq [R2Fact]::TRUE){1}else{0})){Throw-R2Fault 'R2_DUPLICATE_NATIVE_ARGUMENTS'}
                $h.Data['SourceHandleReference']=$source.View
            }
            if([string]$ApiId -ceq 'CreateFileW'){
                $actualPipe=([string]$f.Private.Arguments[0]).StartsWith('\\.\pipe\',[StringComparison]::Ordinal)
                if(($h.Data.Kind -eq [R2HandleKind]::PIPE) -ne $actualPipe){Throw-R2Fault 'R2_CREATEFILE_KIND'}
            }
            $h.Data['LocalValue']=$ReturnedValue; $h.Data['AcquireFact']=$NativeFact; $h.Data['State']=[R2HandleState]::LIVE
        }
        function Set-R2DuplicateHandleBinding([object]$Context,[object]$ReservedHandle,[object]$SourceHandle,[object]$SourceProcess,[object]$TargetProcess,[uint32]$Rights,[bool]$Inheritable,[bool]$TargetIsLocal) {
            Assert-R2ContextReference $Context
            $h=Get-R2Registered $ReservedHandle 'Handle';$source=Get-R2Registered $SourceHandle 'Handle'
            $sp=Get-R2Registered $SourceProcess 'Handle';$tp=Get-R2Registered $TargetProcess 'Handle'
            if($h.Data.State -ne [R2HandleState]::RESERVED -or $h.Private.ContainsKey('DuplicateSource') -or $source.Data.State -ne [R2HandleState]::LIVE -or $sp.Data.Kind -ne [R2HandleKind]::PROCESS -or $tp.Data.Kind -ne [R2HandleKind]::PROCESS){Throw-R2Fault 'R2_DUPLICATE_BINDING'}
            # Locality comes from an original GetCurrentProcess fact, never the bool alone.
            $local=([string]$tp.Data.AcquireFact.ApiId -ceq 'GetCurrentProcess')
            if($TargetIsLocal -ne $local){Throw-R2Fault 'R2_DUPLICATE_LOCALITY'}
            $h.Private['DuplicateSource']=$SourceHandle;$h.Private.Remote=(-not $local)
            if(-not $local){$h.Data['Ownership']=[R2HandleOwnership]::BORROWED}
            $h.Data['SourceProcessReference']=$SourceProcess;$h.Data['TargetProcessReference']=$TargetProcess
            $h.Data['RequestedRights']=$Rights;$h.Data['Inheritable']=$(if($Inheritable){[R2Fact]::TRUE}else{[R2Fact]::FALSE})
        }
        function Register-R2NativeAcquisitions([object]$Context,[object]$Fact) {
            $f=Get-R2Registered $Fact 'NativeFact'
            $invalid=$false
            foreach($binding in $f.Private.AcquisitionPlan){
                $candidate=$binding.Handle
                if(-not $f.Private.StatusAccepted){$candidate.Private.AttemptFact=$Fact;continue}
                $actual=if($binding.OutputIndex -lt 0){[IntPtr]$Fact.ReturnValue}else{Get-R2FactPointer $Fact $binding.OutputIndex $binding.Offset}
                $binding.ActualValue=$actual
                if(([string]$Fact.ApiId -cne 'GetCurrentProcess') -and ($actual -eq [IntPtr]::Zero -or $actual.ToInt64() -eq -1)){$candidate.Private.AttemptFact=$Fact;$invalid=$true;continue}
                $f.Private['AuthorizingReservation']=$candidate.View
                try{Record-R2HandleAcquisition $Context $candidate.View $Fact.ApiId $Fact.RawStatus $actual $Fact}
                finally{$f.Private.AuthorizingReservation=$null}
            }
            if($invalid){Throw-R2Fault 'R2_INVALID_ACQUIRED_HANDLE' $Fact.RawStatus $Fact.IssuerSerial}
        }
        function New-R2AcquisitionPlan([object]$Context,[R2ApiId]$ApiId,[object[]]$Arguments,[object]$Outputs){
            $plan=[Collections.Generic.List[object]]::new();$position=0
            $specifications=switch -CaseSensitive([string]$ApiId){
                'CreateJobObjectW'{@{Kind=[R2HandleKind]::JOB}}
                'CreateNamedPipeW'{@{Kind=[R2HandleKind]::PIPE}}
                'CreateEventW'{@{Kind=[R2HandleKind]::EVENT}}
                'CreateToolhelp32Snapshot'{@{Kind=[R2HandleKind]::SNAPSHOT}}
                'GetCurrentProcess'{@{Kind=[R2HandleKind]::PROCESS}}
                'CreatePipe'{@{Kind=[R2HandleKind]::PIPE};@{Kind=[R2HandleKind]::PIPE}}
                'CreateProcessW'{@{Kind=[R2HandleKind]::PROCESS};@{Kind=[R2HandleKind]::THREAD}}
                'OpenProcessToken'{@{Kind=[R2HandleKind]::TOKEN}}
                'ConvertSidToStringSidW'{@{Kind=[R2HandleKind]::LOCAL_ALLOCATION}}
                'ConvertStringSecurityDescriptorToSecurityDescriptorW'{@{Kind=[R2HandleKind]::LOCAL_ALLOCATION}}
                'CreateFileW'{@{Kind=$null;Allowed=@([R2HandleKind]::PIPE,[R2HandleKind]::FILE)}}
                'DuplicateHandle'{@{Kind=$null;Allowed=@([R2HandleKind]::PROCESS,[R2HandleKind]::THREAD,[R2HandleKind]::JOB,[R2HandleKind]::PIPE,[R2HandleKind]::EVENT,[R2HandleKind]::TOKEN,[R2HandleKind]::FILE,[R2HandleKind]::SNAPSHOT)}}
            }
            foreach($value in $specifications){
                $candidate=$null
                foreach($e in $script:objects){
                    if($e.Type -cne 'Handle' -or $e.Data.State -ne [R2HandleState]::RESERVED -or $null -ne $e.Private.AttemptFact -or -not [object]::ReferenceEquals($e.Data.OriginalSlotReference,$script:root.Private.Step.Slot)){continue}
                    $already=$false;foreach($binding in $plan){if([object]::ReferenceEquals($binding.Handle,$e)){$already=$true;break}};if($already){continue}
                    if(($null -ne $value.Kind -and $e.Data.Kind -eq $value.Kind) -or ($null -eq $value.Kind -and $e.Data.Kind -in $value.Allowed)){
                        if([string]$ApiId -ceq 'DuplicateHandle' -and (-not $e.Private.ContainsKey('DuplicateSource') -or -not [object]::ReferenceEquals($e.Private.DuplicateSource,$Arguments[1]))){continue}
                        if([string]$ApiId -ceq 'CreateFileW' -and (($e.Data.Kind -eq [R2HandleKind]::PIPE) -ne ([string]$Arguments[0]).StartsWith('\\.\pipe\',[StringComparison]::Ordinal))){continue}
                        $candidate=$e;break
                    }
                }
                if($null -eq $candidate){Throw-R2Fault 'R2_NATIVE_HANDLE_NOT_RESERVED'}
                if([string]$ApiId -ceq 'DuplicateHandle'){
                    if(-not [object]::ReferenceEquals($Arguments[0],$candidate.Data.SourceProcessReference) -or -not [object]::ReferenceEquals($Arguments[2],$candidate.Data.TargetProcessReference) -or $Arguments[4] -ne $candidate.Data.RequestedRights -or $Arguments[5] -ne $(if($candidate.Data.Inheritable -eq [R2Fact]::TRUE){1}else{0})){Throw-R2Fault 'R2_DUPLICATE_NATIVE_ARGUMENTS'}
                }
                $index=-1;$offset=0
                switch -CaseSensitive([string]$ApiId){
                    'CreatePipe'{$index=$position}
                    'CreateProcessW'{$index=9;$offset=8*$position}
                    'OpenProcessToken'{$index=2}
                    'ConvertSidToStringSidW'{$index=1}
                    'ConvertStringSecurityDescriptorToSecurityDescriptorW'{$index=2}
                    'DuplicateHandle'{$index=3}
                }
                $plan.Add([pscustomobject]@{Handle=$candidate;OutputIndex=$index;Offset=$offset;ActualValue=$null});$position++
            }
            return ,$plan
        }
        function Resolve-R2NativePointer([object]$Context,[object]$Value,[string]$Direction,[bool]$Nullable) {
            if($Value -is [IntPtr] -and $Value -eq [IntPtr]::Zero){if($Nullable){return [IntPtr]::Zero};Throw-R2Fault 'R2_NULL_NATIVE_POINTER'}
            $e=Get-R2Registered $Value ''
            if(-not [object]::ReferenceEquals($e.Data.ContextReference,$Context)){Throw-R2Fault 'R2_POINTER_CONTEXT'}
            if($e.Type -ceq 'Buffer'){
                if($e.Data.State -ne [R2HandleState]::LIVE){Throw-R2Fault 'R2_BUFFER_NOT_LIVE'}
                return [IntPtr]$e.Data.Address
            }
            if($e.Type -ceq 'BufferSlice'){
                [void](Get-R2BufferEntry $Context $e.Data.BufferOwnerReference $e.Data.Offset $e.Data.Capacity)
                return [IntPtr]$e.Data.Address
            }
            if($e.Type -ceq 'LocalAllocationView' -and $Direction -ceq 'In'){
                $h=Get-R2Registered $e.Data.HandleOwnerReference 'Handle'
                if($h.Data.State -ne [R2HandleState]::LIVE){Throw-R2Fault 'R2_LOCAL_ALLOCATION_RELEASED'}
                return [IntPtr]$e.Data.Address
            }
            if($e.Type -ceq 'Handle' -and $Direction -ceq 'None'){
                if($e.Data.State -ne [R2HandleState]::LIVE){Throw-R2Fault 'R2_HANDLE_NOT_LIVE'}
                if($e.Private.Remote){Throw-R2Fault 'R2_REMOTE_HANDLE_LOCAL_USE'}
                return [IntPtr]$e.Data.LocalValue
            }
            if($e.Type -ceq 'OpaqueNative' -and $Direction -ceq 'None'){
                if($e.Data.State -ne [R2HandleState]::LIVE -and -not $e.Private.ConsumeInProgress){Throw-R2Fault 'R2_OPAQUE_NOT_LIVE'}
                return [IntPtr]$e.Data.LocalValue
            }
            Throw-R2Fault 'R2_UNREGISTERED_NATIVE_POINTER'
        }
        function New-R2NativeOpaqueReference([object]$Context,[object]$NativeFact) {
            Assert-R2NativeFact $Context $NativeFact
            if($NativeFact.RawStatus -ne 0){Throw-R2Fault 'R2_OPAQUE_NATIVE_FAILED' $NativeFact.RawStatus $NativeFact.IssuerSerial}
            foreach($r in $script:objects){if($r.Type -ceq 'OpaqueNative' -and [object]::ReferenceEquals($r.Data.AcquireFact,$NativeFact)){return ,$r.View}}
            Throw-R2Fault 'R2_OPAQUE_NOT_RESERVED_BEFORE_NATIVE_CALL'
        }
        function Reserve-R2NativeOpaqueReference([object]$Context,[R2ApiId]$ApiId) {
            Assert-R2ContextReference $Context
            if([string]$ApiId -cnotin @('PdhOpenQueryW','PdhAddEnglishCounterW','nvmlDeviceGetHandleByIndex_v2')){Throw-R2Fault 'R2_OPAQUE_ACQUISITION_API'}
            $slot=Get-R2CurrentSlot $Context
            $step=$script:root.Private.Step
            Assert-R2Operation $Context $slot.Id $step.Operation
            Add-R2Budget 'Handles'
            $e=New-R2Record 'OpaqueNative' $Context $slot @{LocalValue=$null;AcquireFact=$null;ConsumeFact=$null;State=[R2HandleState]::RESERVED;Ownership=$(if([string]$ApiId -ceq 'nvmlDeviceGetHandleByIndex_v2'){[R2HandleOwnership]::BORROWED}else{[R2HandleOwnership]::OWNED})}
            $e.Private['AcquisitionApi']=$ApiId;$e.Private['ConsumeInProgress']=$false
            $script:root.Private.Registry.Add($e.View)
            return ,$e.View
        }
        function Register-R2NativeOpaqueAcquisition([object]$Context,[object]$NativeFact) {
            if($NativeFact.RawStatus -ne 0){return}
            $name=[string]$NativeFact.ApiId
            $output=switch -CaseSensitive($name){'PdhOpenQueryW'{2}'PdhAddEnglishCounterW'{3}'nvmlDeviceGetHandleByIndex_v2'{1}default{return}}
            $factEntry=Get-R2Registered $NativeFact 'NativeFact'
            $e=$factEntry.Private.OpaqueReservation
            if($null -eq $e){Throw-R2Fault 'R2_OPAQUE_NOT_RESERVED_BEFORE_NATIVE_CALL'}
            $value=Get-R2FactPointer $NativeFact $output
            if($value -eq [IntPtr]::Zero -or $value.ToInt64() -eq -1){Throw-R2Fault 'R2_OPAQUE_INVALID_POINTER'}
            $e.Data['LocalValue']=$value;$e.Data['AcquireFact']=$NativeFact;$e.Data['State']=[R2HandleState]::LIVE
        }
        function Consume-R2NativeOpaqueReference([object]$Context,[object]$Reference) {
            Assert-R2ContextReference $Context
            $e=Get-R2Registered $Reference 'OpaqueNative'
            if($e.Data.State -ne [R2HandleState]::LIVE -or $e.Data.Ownership -ne [R2HandleOwnership]::OWNED){Throw-R2Fault 'R2_OPAQUE_NOT_CLOSE_OWNED'}
            $api=if([string]$e.Data.AcquireFact.ApiId -ceq 'PdhOpenQueryW'){[R2ApiId]::PdhCloseQuery}else{[R2ApiId]::PdhRemoveCounter}
            Assert-R2Bound $Context
            $slot=Get-R2CurrentSlot $Context
            $fact=New-R2Record 'NativeFact' $Context $slot @{ApiId=$api;RawStatus=$null;StatusBits=$null;QpcBegin=$null;QpcEnd=$null;Outputs=(New-R2View (New-R2Map @{}));ReturnValue=$null}
            $fact.Private['Arguments']=[object[]]@($Reference)
            $fact.Private['Completed']=$false;$fact.Private['StatusAccepted']=$false
            $fact.Private['OpaqueCloseReference']=$Reference
            Retain-R2NativeFact $Context $fact.View
            # Bind the original retained attempt BEFORE consumption/dispatch. A
            # rejected or non-returning invocation remains UNKNOWN, never absent.
            $e.Data['ConsumeFact']=$fact.View
            $e.Data['State']=[R2HandleState]::CONSUMED;$e.Private.ConsumeInProgress=$true
            try{
                $f=Invoke-R2NativeCall $Context $api @($Reference)
                if(-not [object]::ReferenceEquals($e.Data.ConsumeFact,$f)){Throw-R2Fault 'R2_OPAQUE_CLOSE_FACT_SUBSTITUTION'}
                if($f.RawStatus -ne 0){Stop-R2Guard $Context 'External' 'R2_OPAQUE_CLOSE_FAILED' $f.RawStatus $e.Data.IssuerSerial}
                return ,$f
            }finally{$e.Private.ConsumeInProgress=$false}
        }
        function Invoke-R2NativeCall([object]$Context,[R2ApiId]$ApiId,[object[]]$Arguments) {
            try { return ,(Invoke-R2NativeCallCore $Context $ApiId $Arguments) }
            catch {
                # No native call from the fault path; expected raw native statuses
                # return normally and are interpreted by their fixed component.
                Stop-R2Guard $Context 'External' 'R2_NATIVE_DISPATCH_FAILED' $null 0
                throw
            }
        }
        function Invoke-R2NativeCallCore([object]$Context,[R2ApiId]$ApiId,[object[]]$Arguments) {
            Assert-R2Bound $Context
            $s=$script:root.Private.Step
            if($null -eq $s){Throw-R2Fault 'R2_NO_ACTIVE_STEP'}
            Assert-R2Operation $Context $s.Slot.Id $s.Operation
            $name=[string]$ApiId
            if($name.StartsWith('nvml',[StringComparison]::Ordinal) -and $name -cnotin @('nvmlInit_v2','nvmlShutdown')){
                if($null -eq $script:root.Private.NvmlInitFact -or $null -eq $script:root.Private.NvmlInitFact.RawStatus -or $script:root.Private.NvmlInitFact.RawStatus -ne 0 -or $script:root.Private.NvmlShutdownAttempted){Throw-R2Fault 'R2_NVML_SESSION_NOT_LIVE'}
            }
            if($name -cin @('CloseHandle','LocalFree')){Throw-R2Fault 'R2_CLOSE_REQUIRES_CONSUMPTION'}
            if($name -cin @('PdhCloseQuery','PdhRemoveCounter')){
                if($Arguments.Count -ne 1){Throw-R2Fault 'R2_OPAQUE_CLOSE_ARGUMENTS'}
                $opaque=Get-R2Registered $Arguments[0] 'OpaqueNative'
                if(-not $opaque.Private.ConsumeInProgress -or $opaque.Data.State -ne [R2HandleState]::CONSUMED){Throw-R2Fault 'R2_OPAQUE_CLOSE_REQUIRES_CONSUMPTION'}
            }
            if(-not $script:root.Private.ClockReady -and $name -cnotin @('QueryPerformanceCounter','QueryPerformanceFrequency')){Throw-R2Fault 'R2_NATIVE_CLOCK_NOT_READY'}
            $descriptor=Get-R2NativeDescriptor $Context $ApiId
            $method=Get-R2NativeApi $Context $ApiId
            if($Arguments.Count -ne $descriptor.ParameterTypes.Count){Throw-R2Fault 'R2_NATIVE_ARGUMENT_COUNT'}
            $native=[object[]]::new($Arguments.Count)
            $buffers=@{}
            for($i=0;$i -lt $Arguments.Count;$i++){
                $kind=[string]$descriptor.ParamKinds[$i];$direction=[string]$descriptor.BufferDirections[$i]
                switch -CaseSensitive($kind){
                    'Pointer' {
                        $native[$i]=Resolve-R2NativePointer $Context $Arguments[$i] $direction ($i -in $descriptor.NullableParameters)
                        if($native[$i] -ne [IntPtr]::Zero -and $direction -in @('Out','InOut','In')){
                            $be=Get-R2Registered $Arguments[$i] ''
                            if($be.Type -cnotin @('Buffer','BufferSlice','LocalAllocationView')){Throw-R2Fault 'R2_NATIVE_BUFFER_KIND'}
                            if($descriptor.OutputSizes.ContainsKey([string]$i) -and $be.Data.Capacity -lt $descriptor.OutputSizes[[string]$i]){Throw-R2Fault 'R2_NATIVE_OUTPUT_CAPACITY'}
                            if($descriptor.DynamicBufferLengths.ContainsKey([string]$i)){
                                $length=$descriptor.DynamicBufferLengths[[string]$i]
                                $required=[bigint]$Arguments[[int]$length.LengthParameter]*[bigint]$length.UnitBytes
                                if($required -lt 0 -or $required -gt $be.Data.Capacity){Throw-R2Fault 'R2_NATIVE_DYNAMIC_BUFFER_CAPACITY'}
                            }
                            $buffers[[string]$i]=$be
                        }
                    }
                    'String' {if($null -eq $Arguments[$i]){if($i -notin $descriptor.NullableParameters){Throw-R2Fault 'R2_NULL_NATIVE_STRING'};$native[$i]=$null}else{if(-not ($Arguments[$i] -is [string]) -or $Arguments[$i].Length -gt 32767 -or $Arguments[$i].IndexOf([char]0) -ge 0){Throw-R2Fault 'R2_NATIVE_STRING'};$native[$i]=$Arguments[$i]}}
                    'UInt32' {if(-not ($Arguments[$i] -is [uint32])){Throw-R2Fault 'R2_NATIVE_UINT32'};$native[$i]=$Arguments[$i]}
                    'Int32' {if(-not ($Arguments[$i] -is [int])){Throw-R2Fault 'R2_NATIVE_INT32'};$native[$i]=$Arguments[$i]}
                    'UInt16' {if(-not ($Arguments[$i] -is [uint16])){Throw-R2Fault 'R2_NATIVE_UINT16'};$native[$i]=$Arguments[$i]}
                    'UInt64' {if(-not ($Arguments[$i] -is [uint64])){Throw-R2Fault 'R2_NATIVE_UINT64'};$native[$i]=$Arguments[$i]}
                    default {Throw-R2Fault 'R2_NATIVE_PARAMETER_KIND'}
                }
            }
            if($null -ne $descriptor.InformationClassParameter){
                $class=[string]$Arguments[[int]$descriptor.InformationClassParameter]
                if(-not $descriptor.InformationClassLayouts.ContainsKey($class)){Throw-R2Fault 'R2_NATIVE_INFORMATION_CLASS'}
                $layout=Get-R2NativeLayoutDescriptor $Context.Interop $descriptor.InformationClassLayouts[$class]
                $index=[string]$descriptor.InformationClassBufferParameter
                if(-not $buffers.ContainsKey($index) -or $buffers[$index].Data.Capacity -lt $layout.Size){Throw-R2Fault 'R2_NATIVE_INFORMATION_LAYOUT'}
            }
            $outputs=New-R2Map @{}
            $leases=New-R2Map @{}
            foreach($key in $buffers.Keys){
                if([string]$descriptor.BufferDirections[[int]$key] -cnotin @('Out','InOut')){continue}
                $be=$buffers[$key]
                $owner=if($be.Type -ceq 'BufferSlice'){$be.Data.BufferOwnerReference}else{$be.View}
                Retire-R2BufferFacts $owner
                $length=[long]$be.Data.Capacity
                if($descriptor.OutputSizes.ContainsKey($key) -and [long]$descriptor.OutputSizes[$key] -gt 0){$length=[long]$descriptor.OutputSizes[$key]}
                if($descriptor.DynamicBufferLengths.ContainsKey($key)){$len=$descriptor.DynamicBufferLengths[$key];$length=[long]([bigint]$Arguments[[int]$len.LengthParameter]*$len.UnitBytes)}
                if($name -cin @('PdhGetRawCounterArrayW','PdhGetCounterInfoW') -and $key -ceq '3'){$length=[long]$be.Data.Capacity}
                $leases[$key]=[pscustomobject]@{Owner=$owner;Address=$be.Data.Address;Length=$length;Data=$null;ReadOnlyData=$null;Valid=$false}
            }
            if($name -cin @('PdhCloseQuery','PdhRemoveCounter')){
                $fact=Get-R2Registered $opaque.Data.ConsumeFact 'NativeFact'
                if($fact.Data.ApiId -ne $ApiId -or $fact.Private.Completed -or $null -ne $fact.Data.RawStatus -or -not $fact.Private.Retained -or -not [object]::ReferenceEquals($fact.Private.OpaqueCloseReference,$opaque.View) -or -not [object]::ReferenceEquals($fact.Data.ContextReference,$Context) -or -not [object]::ReferenceEquals($fact.Data.OriginalSlotReference,$s.Slot)){Throw-R2Fault 'R2_OPAQUE_CLOSE_FACT_BINDING'}
            }else{
                $fact=New-R2Record 'NativeFact' $Context $s.Slot @{ApiId=$ApiId;RawStatus=$null;StatusBits=$null;QpcBegin=$null;QpcEnd=$null;Outputs=(New-R2View $outputs);ReturnValue=$null}
            }
            Assert-R2FactStorage ([long]$leases.Count*128)
            $script:activeFactBytes+=[long]$leases.Count*128;$fact.Private.StorageCharge+=[long]$leases.Count*128
            foreach($key in $leases.Keys){$outputs[$key]=New-R2View (New-R2Map @{Count=[uint32]$leases[$key].Length;LeaseSerial=$fact.Data.IssuerSerial;ArgumentIndex=[uint32]$key})}
            $fact.Private['OutputLeases']=$leases
            # Original immutable scalars/references bind inputs. Mutable input
            # bytes are NOT claimed to have been snapshotted.
            $fact.Private['Arguments']=$Arguments.Clone();$fact.Private['Completed']=$false;$fact.Private['StatusAccepted']=$false
            $fact.Private['AuthorizingReservation']=$null
            $fact.Private['AcquisitionPlan']=New-R2AcquisitionPlan $Context $ApiId $Arguments $fact.Data.Outputs
            $fact.Private['OpaqueReservation']=$null
            if($name -cin @('PdhOpenQueryW','PdhAddEnglishCounterW','nvmlDeviceGetHandleByIndex_v2')){
                foreach($record in $script:objects){if($record.Type -ceq 'OpaqueNative' -and $record.Data.State -eq [R2HandleState]::RESERVED -and $record.Private.AcquisitionApi -eq $ApiId -and [object]::ReferenceEquals($record.Data.OriginalSlotReference,$s.Slot)){$fact.Private.OpaqueReservation=$record;break}}
                if($null -eq $fact.Private.OpaqueReservation){Throw-R2Fault 'R2_OPAQUE_NOT_RESERVED_BEFORE_NATIVE_CALL'}
            }
            if($name -ceq 'nvmlInit_v2'){
                if($script:root.Private.NvmlInitAttempted){Throw-R2Fault 'R2_NVML_INIT_REISSUE'}
                $script:root.Private.NvmlInitAttempted=$true;$script:root.Private.NvmlInitFact=$fact.View
                Retain-R2NativeFact $Context $fact.View
            }
            if($name -ceq 'nvmlShutdown'){
                if($script:root.Private.NvmlShutdownAttempted -or $null -eq $script:root.Private.NvmlInitFact -or $script:root.Private.NvmlInitFact.RawStatus -ne 0){Throw-R2Fault 'R2_NVML_SHUTDOWN_NOT_OWNED'}
                $script:root.Private.NvmlShutdownAttempted=$true;$script:root.Private.NvmlShutdownFact=$fact.View
                Retain-R2NativeFact $Context $fact.View
            }
            $autoRetain=($fact.Private.AcquisitionPlan.Count -gt 0 -or $null -ne $fact.Private.OpaqueReservation -or $name -ceq 'BCryptGenRandom')
            if($autoRetain){
                if($script:essentialFacts.Count -ge 4096){Throw-R2Fault 'R2_ESSENTIAL_FACT_LIMIT'}
                $needed=0L;foreach($lease in $leases.Values){$needed+=$lease.Length}
                if($needed -gt 4096){Throw-R2Fault 'R2_ACQUISITION_PAYLOAD_LIMIT'}
                Assert-R2FactStorage $needed
                $script:activeFactBytes+=$needed;$fact.Private.StorageCharge+=$needed
                foreach($lease in $leases.Values){$lease.Data=[byte[]]::new([int]$lease.Length);$lease.ReadOnlyData=[Array]::AsReadOnly($lease.Data)}
            }
            Assert-R2Operation $Context $s.Slot.Id $s.Operation
            Add-R2Budget 'Calls'
            $begin=(Read-R2LedgerTimestamp);$fact.Data['QpcBegin']=$begin
            try{
                $returned=$method.Invoke($null,$native)
                $lastError=[Runtime.InteropServices.Marshal]::GetLastWin32Error()
            }catch{
                Stop-R2Guard $Context $s.Domain 'R2_NATIVE_INVOKE_EXCEPTION' $null $fact.Data.IssuerSerial
                $fact.Data['QpcEnd']=(Read-R2LedgerTimestamp -ForFault $true)
                throw
            }
            $fact.Data['ReturnValue']=$returned
            $raw=if($returned -is [IntPtr]){$returned.ToInt64()}elseif($null -eq $returned){$null}else{[long]$returned}
            $fact.Data['RawStatus']=$raw
            $fact.Data['StatusBits']=$(if($descriptor.SetLastError){[uint32]([long]$lastError -band 4294967295L)}elseif($null -ne $raw){[uint32]([long]$raw -band 4294967295L)}else{$null})
            $fact.Private.Completed=$true;$fact.Private.StatusAccepted=Test-R2NativeStatus $descriptor $returned
            if($name -cin @('PdhCloseQuery','PdhRemoveCounter') -and $raw -ne 0){Stop-R2Guard $Context 'External' 'R2_OPAQUE_CLOSE_FAILED' $raw $opaque.Data.IssuerSerial}
            if($fact.Private.StatusAccepted -and $name -cin @('PdhGetRawCounterArrayW','PdhGetCounterInfoW') -and $leases.ContainsKey('3')){
                $sizeIndex=if($name -ceq 'PdhGetCounterInfoW'){'2'}else{'1'}
                $actualBytes=[Runtime.InteropServices.Marshal]::ReadInt32($buffers[$sizeIndex].Data.Address)
                if($actualBytes -lt 0 -or $actualBytes -gt $leases['3'].Length){Throw-R2Fault 'R2_PDH_RETURNED_BYTES_RANGE' $raw $fact.Data.IssuerSerial}
                $leases['3'].Length=[long]$actualBytes
                $outputs['3']=New-R2View (New-R2Map @{Count=[uint32]$actualBytes;LeaseSerial=$fact.Data.IssuerSerial;ArgumentIndex=[uint32]3})
            }
            foreach($key in $leases.Keys){
                $leases[$key].Valid=$fact.Private.StatusAccepted
                if($lastError -eq 122 -and (($name -ceq 'GetTokenInformation' -and $key -ceq '4') -or ($name -ceq 'InitializeProcThreadAttributeList' -and $key -ceq '3'))){$leases[$key].Valid=$true}
                if($descriptor.ReturnConvention -ceq 'PDH' -and $fact.Data.StatusBits -eq [uint32]2147485650 -and $key -in @('1','2')){$leases[$key].Valid=$true}
            }
            # Register all documented valid acquisition outputs BEFORE another fallible
            # native operation, elapsed-time rejection, reporting, or caller code.
            Register-R2NativeAcquisitions $Context $fact.View
            Register-R2NativeOpaqueAcquisition $Context $fact.View
            if($autoRetain){Retain-R2NativeFact $Context $fact.View}
            $end=(Read-R2LedgerTimestamp);$fact.Data['QpcEnd']=$end
            if($end -lt $begin -or ([bigint]$end-$begin)*10 -gt $script:root.Data.Frequency){Throw-R2Fault 'R2_NATIVE_100MS' $raw $fact.Data.IssuerSerial}
            Assert-R2Operation $Context $s.Slot.Id $s.Operation
            return ,$fact.View
        }
        function Initialize-R2NativeClock([object]$Context) {
            Assert-R2Bound $Context
            if($script:root.Private.ClockReady -or $script:root.Private.ContainsKey('ClockAttempted')){Throw-R2Fault 'R2_CLOCK_REINITIALIZE'}
            $script:root.Private['ClockAttempted']=$true
            $slot=Get-R2CurrentSlot $Context
            $buffer=New-R2NativeBuffer $Context $slot 8 8
            $f=Invoke-R2NativeCall $Context ([R2ApiId]::QueryPerformanceFrequency) @($buffer)
            if($f.RawStatus -eq 0){Throw-R2Fault 'R2_QPF_FAILED' $f.StatusBits $f.IssuerSerial}
            $hz=Read-R2FactInt64 $f 0
            Retain-R2NativeFact $Context $f
            if($hz -ne $script:root.Data.Frequency -or $hz -le 0){Throw-R2Fault 'R2_QPF_MISMATCH'}
            $f=Invoke-R2NativeCall $Context ([R2ApiId]::QueryPerformanceCounter) @($buffer)
            if($f.RawStatus -eq 0){Throw-R2Fault 'R2_QPC_FAILED' $f.StatusBits $f.IssuerSerial}
            $q=Read-R2FactInt64 $f 0
            Retain-R2NativeFact $Context $f
            if($q -lt $f.QpcBegin -or $q -gt $f.QpcEnd -or $q -lt $script:root.Data.Q0 -or ([bigint]$f.QpcEnd-$script:root.Data.Q0)*10 -gt $hz){Throw-R2Fault 'R2_CLOCK_EPOCH_AGREEMENT'}
            $script:root.Private.ClockReady=$true;$script:root.Private.LastQpc=$q
            $script:root.Private['ClockBufferReference']=$buffer
            return ,$f
        }
        function Get-R2NativeQpc([object]$Context) {
            Assert-R2Bound $Context
            if(-not $script:root.Private.ClockReady){Throw-R2Fault 'R2_NATIVE_CLOCK_NOT_READY'}
            $f=Invoke-R2NativeCall $Context ([R2ApiId]::QueryPerformanceCounter) @($script:root.Private.ClockBufferReference)
            $q=Read-R2FactInt64 $f 0
            if($f.RawStatus -eq 0 -or $q -lt $script:root.Private.LastQpc -or $q -lt $f.QpcBegin -or $q -gt $f.QpcEnd){Throw-R2Fault 'R2_QPC_DISCONTINUITY'}
            $script:root.Private.LastQpc=$q
            return [long]$q
        }
        function Get-R2InvocationNonce([object]$Context) {
            Assert-R2Bound $Context
            if($null -ne $script:root.Private.Nonce){return ,$script:root.Private.Nonce}
            if($script:root.Private.NonceAttempted){Throw-R2Fault 'R2_NONCE_RETRY'}
            $script:root.Private.NonceAttempted=$true
            $b=New-R2NativeBuffer $Context (Get-R2CurrentSlot $Context) 32 8
            $f=Invoke-R2NativeCall $Context ([R2ApiId]::BCryptGenRandom) @([IntPtr]::Zero,$b,[uint32]32,[uint32]2)
            if($f.RawStatus -lt 0){Throw-R2Fault 'R2_NONCE_NATIVE_FAILED' $f.RawStatus $f.IssuerSerial}
            $bytes=Get-R2NativeFactOutput $Context $f 1 0 32
            if($bytes.Count -ne 32){Throw-R2Fault 'R2_NONCE_LENGTH'}
            $script:root.Private.Nonce=$bytes
            Release-R2NativeBuffer $Context $b
            return ,$script:root.Private.Nonce
        }
        function Consume-R2Handle([object]$Context,[object]$Handle) {
            Assert-R2Bound $Context
            $h=Get-R2Registered $Handle 'Handle'
            if($h.Data.Ownership -ne [R2HandleOwnership]::OWNED -or $h.Data.State -ne [R2HandleState]::LIVE -or $h.Private.Remote){Throw-R2Fault 'R2_HANDLE_NOT_CLOSE_OWNED'}
            $step=$script:root.Private.Step
            if($null -eq $step){Throw-R2Fault 'R2_NO_ACTIVE_STEP'}
            Assert-R2Operation $Context $step.Slot.Id $step.Operation
            $api=if($h.Data.Kind -eq [R2HandleKind]::LOCAL_ALLOCATION){[R2ApiId]::LocalFree}else{[R2ApiId]::CloseHandle}
            $fact=New-R2Record 'NativeFact' $Context $step.Slot @{ApiId=$api;RawStatus=$null;StatusBits=$null;QpcBegin=$null;QpcEnd=$null;Outputs=(New-R2View (New-R2Map @{}));ReturnValue=$null}
            $fact.Private['Arguments']=[object[]]@($Handle)
            $fact.Private['Completed']=$false;$fact.Private['StatusAccepted']=$false
            Retain-R2NativeFact $Context $fact.View
            # Issue the private one-use pointer token only after evidence storage
            # is reserved, so a rejected reservation cannot accumulate tokens.
            $token=New-R2Record 'ClosePointer' $Context $step.Slot @{Address=$h.Data.LocalValue;HandleReference=$Handle;Used=$false}
            $fact.Private['CloseTokenReference']=$token.View
            $token.Private['CloseFactReference']=$fact.View
            # Bind the original retained attempt before consumption/dispatch.
            # A rejected or non-returning invocation remains UNKNOWN, never absent.
            $h.Data['ConsumeFact']=$fact.View
            $h.Data['State']=[R2HandleState]::CONSUMED
            try{
                $result=Invoke-R2NativeClose $Context $api $token
                if(-not [object]::ReferenceEquals($result,$h.Data.ConsumeFact)){Throw-R2Fault 'R2_CLOSE_FACT_SUBSTITUTION'}
                return ,$result
            }catch{Stop-R2Guard $Context 'External' 'R2_HANDLE_CLOSE_EXCEPTION' $null $h.Data.IssuerSerial;throw}
        }
        function Invoke-R2NativeClose([object]$Context,[R2ApiId]$ApiId,[object]$TokenEntry) {
            Assert-R2Bound $Context
            $token=Get-R2Registered $TokenEntry.View 'ClosePointer'
            if($token.Data.Used -or $ApiId -notin @([R2ApiId]::CloseHandle,[R2ApiId]::LocalFree)){Throw-R2Fault 'R2_CLOSE_TOKEN'}
            $h=Get-R2Registered $token.Data.HandleReference 'Handle'
            $expected=if($h.Data.Kind -eq [R2HandleKind]::LOCAL_ALLOCATION){[R2ApiId]::LocalFree}else{[R2ApiId]::CloseHandle}
            if($ApiId -ne $expected -or $h.Data.State -ne [R2HandleState]::CONSUMED){Throw-R2Fault 'R2_CLOSE_OWNER'}
            $token.Data['Used']=$true
            $s=$script:root.Private.Step
            if($null -eq $s){Throw-R2Fault 'R2_NO_ACTIVE_STEP'}
            $fact=Get-R2Registered $h.Data.ConsumeFact 'NativeFact'
            if($fact.Data.ApiId -ne $ApiId -or $fact.Private.Completed -or $null -ne $fact.Data.RawStatus -or -not $fact.Private.Retained -or -not [object]::ReferenceEquals($fact.Data.ContextReference,$Context) -or -not [object]::ReferenceEquals($fact.Data.OriginalSlotReference,$s.Slot) -or -not [object]::ReferenceEquals($token.Data.ContextReference,$Context) -or -not [object]::ReferenceEquals($token.Data.OriginalSlotReference,$s.Slot) -or $token.Data.Address -ne $h.Data.LocalValue -or -not [object]::ReferenceEquals($fact.Private.CloseTokenReference,$token.View) -or -not [object]::ReferenceEquals($token.Private.CloseFactReference,$fact.View) -or -not [object]::ReferenceEquals($fact.Private.Arguments[0],$h.View)){Throw-R2Fault 'R2_CLOSE_FACT_BINDING'}
            Assert-R2Operation $Context $s.Slot.Id $s.Operation
            $m=Get-R2NativeApi $Context $ApiId
            Add-R2Budget 'Calls'
            $begin=(Read-R2LedgerTimestamp);$fact.Data['QpcBegin']=$begin
            $ret=$m.Invoke($null,[object[]]@($token.Data.Address))
            $err=[Runtime.InteropServices.Marshal]::GetLastWin32Error()
            $fact.Data['ReturnValue']=$ret;$fact.Data['RawStatus']=$(if($ret -is [IntPtr]){$ret.ToInt64()}else{[long]$ret});$fact.Data['StatusBits']=[uint32]([long]$err -band 4294967295L)
            $fact.Private['Completed']=$true;$fact.Private['StatusAccepted']=$(if($ApiId -eq [R2ApiId]::LocalFree){$ret -eq [IntPtr]::Zero}else{[long]$ret -ne 0})
            # Preserve the actual failure as primary before any fallible clock.
            if(-not $fact.Private.StatusAccepted){Stop-R2Guard $Context 'External' 'R2_HANDLE_CLOSE_FAILED' $fact.Data.StatusBits $h.Data.IssuerSerial}
            $end=Read-R2LedgerTimestamp -ForFault $true;$fact.Data['QpcEnd']=$end
            if($null -eq $end -or $end -lt $begin -or ([bigint]$end-$begin)*10 -gt $script:root.Data.Frequency){Throw-R2Fault 'R2_CLOSE_TIME_UNKNOWN_OR_100MS' $fact.Data.RawStatus $fact.Data.IssuerSerial}
            return ,$fact.View
        }
        function Get-R2HandleValue([object]$Context,[object]$Handle) {
            Assert-R2ContextReference $Context
            $h=Get-R2Registered $Handle 'Handle'
            if($h.Data.State -ne [R2HandleState]::LIVE -or $h.Private.Remote){Throw-R2Fault 'R2_HANDLE_VALUE_UNAVAILABLE'}
            return [IntPtr]$h.Data.LocalValue
        }
        function Record-R2RemoteDuplicateClosure([object]$Context,[object]$RemoteDuplicate,[object]$OriginalChildJoinFact) {
            Assert-R2ContextReference $Context;Assert-R2NativeFact $Context $OriginalChildJoinFact
            $handle=Get-R2Registered $RemoteDuplicate 'Handle'
            $fact=Get-R2Registered $OriginalChildJoinFact 'NativeFact'
            if(-not $handle.Private.Remote -or $handle.Data.State -ne [R2HandleState]::LIVE -or [string]$OriginalChildJoinFact.ApiId -cne 'WaitForSingleObject' -or $OriginalChildJoinFact.RawStatus -ne 0 -or $fact.Private.Arguments.Count -ne 2 -or $fact.Private.Arguments[1] -ne 0 -or -not [object]::ReferenceEquals($fact.Private.Arguments[0],$handle.Data.TargetProcessReference)){Throw-R2Fault 'R2_REMOTE_HANDLE_RELEASE_NOT_OBSERVED'}
            # Actual original process signaled: its handle table was destroyed.
            # This is an observed release, never a local CloseHandle on that value.
            $handle.Data['ConsumeFact']=$OriginalChildJoinFact;$handle.Data['State']=[R2HandleState]::CONSUMED
        }
        function Get-R2NativeFactArguments([object]$Context,[object]$Fact) {
            Assert-R2NativeFact $Context $Fact
            $e=Get-R2Registered $Fact 'NativeFact'
            return ,([Array]::AsReadOnly([object[]]$e.Private.Arguments.Clone()))
        }
        function Get-R2LedgerSnapshot([object]$Context) {
            Assert-R2ContextReference $Context
            # The original view has no setters; all collection values are readonly.
            return ,$script:root.View
        }
        function Get-R2NvmlInitializationFact([object]$Context){
            Assert-R2ContextReference $Context
            $fact=$script:root.Private.NvmlInitFact
            if($null -ne $fact -and $null -ne $fact.RawStatus -and $fact.RawStatus -eq 0){return ,$fact}
            return $null
        }
        function Get-R2NvmlShutdownFact([object]$Context){
            Assert-R2ContextReference $Context
            return ,$script:root.Private.NvmlShutdownFact
        }
        function Reserve-R2ComponentIdentity([object]$Context,[object]$Slot,[string]$Kind) {
            Assert-R2ContextReference $Context; Assert-R2PlanSlot $Context $Slot
            if($Kind -cnotin @('Child','Peer','PendingIo','Gauge','Target','Cleanup')){Throw-R2Fault 'R2_COMPONENT_KIND'}
            $step=$script:root.Private.Step
            if($null -eq $step -or -not [object]::ReferenceEquals($step.Slot,$Slot)){Throw-R2Fault 'R2_COMPONENT_SLOT'}
            Assert-R2Operation $Context $Slot.Id $step.Operation
            $record=New-R2Record 'ComponentIdentity' $Context $Slot @{Kind=$Kind}
            return ,$record.View
        }
        function Register-R2RoleJobs([object]$Context,[object]$External,[object]$Prep) {
            Assert-R2ContextReference $Context
            if($null -ne $script:root.Private.Jobs.External -or $null -ne $script:root.Private.Jobs.Prep){Throw-R2Fault 'R2_JOB_REBIND'}
            $externalEntry=Get-R2Registered $External 'Handle';$prepEntry=Get-R2Registered $Prep 'Handle'
            if([object]::ReferenceEquals($External,$Prep)){Throw-R2Fault 'R2_JOB_ALIAS'}
            foreach($e in @($externalEntry,$prepEntry)){
                if($e.Data.Kind -ne [R2HandleKind]::JOB -or $e.Data.State -ne [R2HandleState]::LIVE -or $e.Data.Ownership -ne [R2HandleOwnership]::OWNED -or [string]$e.Data.AcquireFact.ApiId -cne 'CreateJobObjectW'){Throw-R2Fault 'R2_JOB_OWNER'}
            }
            $script:root.Private.Jobs['External']=$External;$script:root.Private.Jobs['Prep']=$Prep
        }
        function Register-R2PeerReference([object]$Context,[object]$Peer) {
            Assert-R2ContextReference $Context
            # Fixed original process owner validates its OWN reference registry;
            # a matching set of fields is never an issuer.
            Assert-R2PeerReference $Context $Peer
            foreach($existing in $script:root.Private.Peers){if([object]::ReferenceEquals($existing,$Peer)){Throw-R2Fault 'R2_PEER_REBIND'}}
            if($script:root.Private.Peers.Count -ge 3){Throw-R2Fault 'R2_PEER_LIMIT'}
            $script:root.Private.Peers.Add($Peer)
        }
        function Reserve-R2BootstrapAllowance([object]$Context,[object]$Child) {
            Assert-R2ContextReference $Context
            Assert-R2ChildReference $Context $Child
            if($script:root.Data.StopState -eq [R2Fact]::TRUE -or $Child.State -ne [R2ChildState]::RESERVED){Throw-R2Fault 'R2_BOOTSTRAP_RESERVE_BEFORE_BIRTH'}
            $role=[string]$Child.Role
            if($role -cnotin @('CONTROLLER','WATCHDOG','TRANSPORT') -or $script:root.Private.ContainsKey('PeerRole') -or $script:root.Private.Allotments.ContainsKey($role)){Throw-R2Fault 'R2_BOOTSTRAP_ALLOTMENT_REISSUE'}
            # Portions were removed from root's own limits at construction. This
            # voucher reserves a portion BEFORE birth and is never refunded.
            $portion=New-R2View (New-R2Map @{ChildReference=$Child;Role=$Child.Role;BootstrapCalls=16384L;WorkCalls=600000L;CleanupCalls=$(if($role -ceq 'TRANSPORT'){66666L}else{66667L});WorkHandles=96L;CleanupHandles=32L;WorkFaults=4L;CleanupFaults=4L;WorkObservations=45000L;CleanupObservations=5000L;BufferBytes=174762L;DiskInstances=32L;OriginalQ0=$Context.Q0;PrepDeadline=$Context.PrepDeadline;ExternalDeadline=$Context.ExternalDeadline})
            $script:root.Private.Allotments.Add($role,$portion)
            return ,$portion
        }
        function Import-R2BootstrapOwnership([object]$Context,[object]$Quarantine,[object]$Proof) {
            Assert-R2ContextReference $Context
            if($script:root.Private.ContainsKey('BootstrapSource') -or $script:root.Private.Bound){Throw-R2Fault 'R2_BOOTSTRAP_IMPORT_REISSUE'}
            $promotion=Get-R2BootstrapPromotionData $Context $Quarantine $Proof
            $fields=$promotion.Fields
            $role=[string]$fields.Role
            if($role -cnotin @('CONTROLLER','WATCHDOG','TRANSPORT') -or $promotion.Calls -lt 0 -or $promotion.Calls -gt 16384 -or $promotion.BufferBytes -gt 16384 -or $promotion.HandleCount -gt 96 -or $promotion.HandleCount -lt 1 -or $promotion.StorageBytes -lt 0 -or [bigint]$promotion.BufferBytes+$promotion.StorageBytes -gt 174762){Throw-R2Fault 'R2_BOOTSTRAP_IMPORT_LIMIT'}
            $script:root.Private['PeerRole']=$fields.Role
            $script:root.Private['BootstrapSource']=$Quarantine
            $script:root.Private['BootstrapMappings']=[Collections.Generic.List[object]]::new()
            $script:root.Private.Limits['Work']=@{Births=0L;Handles=96L;Faults=4L;Observations=45000L;Calls=600000L}
            $script:root.Private.Limits['Cleanup']=@{Births=0L;Handles=32L;Faults=4L;Observations=5000L;Calls=$(if($role -ceq 'TRANSPORT'){66666L}else{66667L})}
            $script:root.Private.Work['Calls']=[long]$promotion.Calls
            $script:root.Private['BootstrapChargedCalls']=[long]$promotion.Calls
            $script:root.Private.BytesReserved=[long]$promotion.BufferBytes+[long]$promotion.StorageBytes
            $script:root.Private.Work['BufferBytes']=[long]$promotion.BufferBytes
            $script:root.Private.Work['Handles']=[long]$promotion.HandleCount
            $script:root.Private.Nonce=[Array]::AsReadOnly([byte[]]$fields.InvocationNonce)
            $script:root.Private.NonceAttempted=$true
            $slot=$fields.OriginalSlotReference
            Assert-R2PlanSlot $Context $slot
            $usage=$promotion.SlotUsage
            if($null -eq $usage.FirstStartedQpc -or $null -eq $usage.LastQpc -or $usage.FirstStartedQpc -lt $Context.Q0 -or $usage.LastQpc -lt $usage.FirstStartedQpc -or $usage.Calls -ne $promotion.Calls -or $usage.Handles -ne $promotion.HandleCount -or $usage.Bytes -ne $promotion.BufferBytes -or $usage.Births -ne 0 -or $usage.Calls -gt [long]$slot.MaxCalls -or $usage.Handles -gt [long]$slot.MaxHandles -or $usage.Bytes -gt [long]$slot.MaxBytes -or [long]$slot.MaxDurationTicks -le 0){Throw-R2Fault 'R2_BOOTSTRAP_ORIGINAL_SLOT_USAGE'}
            $domain=switch -CaseSensitive([string]$slot.Phase){'Prep'{'Prep'}'PREP'{'Prep'}'External'{'External'}'EXTERNAL'{'External'}default{Throw-R2Fault 'R2_BOOTSTRAP_SLOT_PHASE'}}
            $localEnd=[bigint]$usage.FirstStartedQpc+[bigint]$slot.MaxDurationTicks
            $workEnd=[bigint](Get-R2DomainDeadline $domain)-60*[bigint]$Context.Frequency
            $workEnd=[bigint]::Min($workEnd,[bigint]$Context.ExternalDeadline-60*[bigint]$Context.Frequency)
            if($localEnd -gt [long]::MaxValue -or $usage.LastQpc -ge $localEnd -or $usage.LastQpc -ge $workEnd){Throw-R2Fault 'R2_BOOTSTRAP_ORIGINAL_SLOT_DEADLINE'}
            if(-not $script:root.Private.ContainsKey('SlotUsage')){$script:root.Private['SlotUsage']=@{}}
            $key=[string]$slot.Id
            if($script:root.Private.SlotUsage.ContainsKey($key)){Throw-R2Fault 'R2_BOOTSTRAP_SLOT_USAGE_REISSUE'}
            # These are the same cumulative bootstrap attempts, including closed
            # handles and released buffers. Promotion never restores an allowance.
            $script:root.Private.SlotUsage[$key]=@{Births=0L;Handles=[long]$usage.Handles;Calls=[long]$usage.Calls;Bytes=[long]$usage.Bytes;FirstStartedQpc=[long]$usage.FirstStartedQpc}
            $script:root.Private['BootstrapSlot']=$slot
            $script:root.Private['BootstrapUsage']=$usage
            $script:root.Private['BootstrapFirstStartedQpc']=[long]$usage.FirstStartedQpc
            $script:root.Private['BootstrapLastQpc']=[long]$usage.LastQpc
            foreach($fact in $promotion.NativeFacts){
                $e=New-R2Record 'NativeFact' $Context $slot @{ApiId=$fact.ApiId;RawStatus=$fact.RawStatus;StatusBits=$fact.StatusBits;QpcBegin=$fact.QpcBegin;QpcEnd=$fact.QpcEnd;Outputs=$fact.Outputs;ReturnValue=$fact.ReturnValue;BootstrapFactReference=$fact}
                $e.Private['Completed']=($null -ne $fact.RawStatus);$e.Private['StatusAccepted']=$false;$e.Private['Arguments']=[object[]]@()
                Retain-R2NativeFact $Context $e.View
                $script:root.Private.BootstrapMappings.Add([pscustomobject]@{Original=$fact;Promoted=$e.View})
            }
            foreach($transfer in $promotion.Transfers){
                if($transfer.Type -ceq 'Buffer'){
                    $e=New-R2Record 'Buffer' $Context $slot @{Address=$transfer.Address;Capacity=$transfer.Capacity;Alignment=$transfer.Alignment;State=$transfer.State;Ownership=[R2HandleOwnership]::OWNED;BootstrapReference=$transfer.Original}
                    $e.Private['Base']=$transfer.BaseAddress
                }else{
                    $acquire=$null;$consume=$null
                    foreach($mapping in $script:root.Private.BootstrapMappings){if([object]::ReferenceEquals($mapping.Original,$transfer.AcquireFact)){$acquire=$mapping.Promoted};if([object]::ReferenceEquals($mapping.Original,$transfer.ConsumeFact)){$consume=$mapping.Promoted}}
                    $e=New-R2Record 'Handle' $Context $slot @{Kind=$transfer.Kind;LocalValue=$transfer.LocalValue;SourceProcessReference=$null;TargetProcessReference=$null;SourceHandleReference=$null;RequestedRights=$null;Inheritable=[R2Fact]::UNKNOWN;Ownership=$transfer.Ownership;State=$transfer.State;AcquireFact=$acquire;ConsumeFact=$consume;BootstrapReference=$transfer.Original}
                    $e.Private['AttemptFact']=$acquire;$e.Private['ReleaseOwner']='Native';$e.Private['Remote']=$false
                }
                $script:root.Private.Registry.Add($e.View)
                $script:root.Private.BootstrapMappings.Add([pscustomobject]@{Original=$transfer.Original;Promoted=$e.View})
            }
            foreach($mapping in $script:root.Private.BootstrapMappings){
                if([object]::ReferenceEquals($mapping.Original,$fields.ExternalJobHandle)){$script:root.Private.Jobs['External']=$mapping.Promoted}
                if([object]::ReferenceEquals($mapping.Original,$fields.PrepJobHandle)){$script:root.Private.Jobs['Prep']=$mapping.Promoted}
            }
            if($null -eq $script:root.Private.Jobs.External -or $null -eq $script:root.Private.Jobs.Prep){Throw-R2Fault 'R2_BOOTSTRAP_ORIGINAL_JOBS_MISSING'}
        }
        function Get-R2PromotedBootstrapHandle([object]$Context,[object]$Quarantine,[object]$OldHandle) {
            Assert-R2ContextReference $Context
            Assert-R2BootstrapPromotion $Context $Quarantine
            if(-not [object]::ReferenceEquals($script:root.Private.BootstrapSource,$Quarantine)){Throw-R2Fault 'R2_BOOTSTRAP_SOURCE_SUBSTITUTION'}
            foreach($mapping in $script:root.Private.BootstrapMappings){if([object]::ReferenceEquals($mapping.Original,$OldHandle)){return ,$mapping.Promoted}}
            Throw-R2Fault 'R2_BOOTSTRAP_OBJECT_NOT_PROMOTED'
        }
        function Reconcile-R2BootstrapCharges([object]$Context,[object]$Quarantine) {
            Assert-R2BootstrapPromotion $Context $Quarantine
            if(-not [object]::ReferenceEquals($script:root.Private.BootstrapSource,$Quarantine)){Throw-R2Fault 'R2_BOOTSTRAP_SOURCE_SUBSTITUTION'}
            $delta=[long]$Quarantine.Calls-[long]$script:root.Private.BootstrapChargedCalls
            $slot=$script:root.Private.BootstrapSlot
            Assert-R2PlanSlot $Context $slot
            $usage=$script:root.Private.BootstrapUsage
            $local=$script:root.Private.SlotUsage[[string]$slot.Id]
            if($null -eq $local -or $usage.FirstStartedQpc -ne $script:root.Private.BootstrapFirstStartedQpc -or $local.FirstStartedQpc -ne $usage.FirstStartedQpc -or $usage.Calls -ne $Quarantine.Calls -or $usage.Handles -ne $local.Handles -or $usage.Bytes -ne $local.Bytes -or $usage.LastQpc -lt $script:root.Private.BootstrapLastQpc){Throw-R2Fault 'R2_BOOTSTRAP_RECONCILE_BINDING'}
            if($delta -lt 0 -or $Quarantine.Calls -gt 16384 -or [bigint]$script:root.Private.Work.Calls+$delta -gt $script:root.Private.Limits.Work.Calls -or [bigint]$local.Calls+$delta -gt [long]$slot.MaxCalls){Throw-R2Fault 'R2_BOOTSTRAP_RECONCILE_LIMIT'}
            $script:root.Private.Work['Calls']=[long]$script:root.Private.Work.Calls+$delta
            $local.Calls=[long]$local.Calls+$delta
            $script:root.Private.BootstrapChargedCalls=[long]$Quarantine.Calls
            $script:root.Private.BootstrapLastQpc=[long]$usage.LastQpc
            $domain=switch -CaseSensitive([string]$slot.Phase){'Prep'{'Prep'}'PREP'{'Prep'}'External'{'External'}'EXTERNAL'{'External'}default{Throw-R2Fault 'R2_BOOTSTRAP_SLOT_PHASE'}}
            $workEnd=[bigint]::Min([bigint](Get-R2DomainDeadline $domain),[bigint]$Context.ExternalDeadline)-60*[bigint]$Context.Frequency
            if([bigint]$usage.LastQpc -ge [bigint]$local.FirstStartedQpc+[bigint]$slot.MaxDurationTicks -or [bigint]$usage.LastQpc -ge $workEnd){Throw-R2Fault 'R2_BOOTSTRAP_ORIGINAL_SLOT_DEADLINE'}
        }
        Export-ModuleMember -Function Get-R2LedgerTimestamp,Record-R2RemoteDuplicateClosure,Reconcile-R2BootstrapCharges,Retain-R2NativeFact,Retire-R2NativeFact,Get-R2NvmlInitializationFact,Get-R2NvmlShutdownFact
        Export-ModuleMember -Function Assert-R2ContextReference,Assert-R2PlanSlot,Get-R2CurrentSlot,New-R2LedgerState,Stop-R2Guard,Get-R2Deadline,Begin-R2LedgerCleanup,Enter-R2LedgerStep,Assert-R2Operation,Exit-R2LedgerStep,Add-R2BirthAttempt,Add-R2ObservationAttempt,Reserve-R2DiskInstances,Bind-R2Interop,New-R2NativeBuffer,Get-R2NativeBufferPointer,Get-R2NativeBufferSlice,Write-R2NativeBuffer,Write-R2NativeReference,Read-R2NativeBuffer,Release-R2NativeBuffer,Get-R2LocalAllocationView,Read-R2LocalAllocation,Reserve-R2Handle,Assert-R2NativeFact,Record-R2HandleAcquisition,Set-R2DuplicateHandleBinding,Invoke-R2NativeCall,Get-R2NativeFactOutput,Initialize-R2NativeClock,Get-R2NativeQpc,Get-R2InvocationNonce,Consume-R2Handle,Get-R2HandleValue,Get-R2NativeFactArguments,Get-R2LedgerSnapshot,Reserve-R2ComponentIdentity,Register-R2RoleJobs,Register-R2PeerReference,Reserve-R2BootstrapAllowance,Import-R2BootstrapOwnership,Get-R2PromotedBootstrapHandle,Reserve-R2NativeOpaqueReference,New-R2NativeOpaqueReference,Consume-R2NativeOpaqueReference
    }
    Import-Module -ModuleInfo $privateModule -Global -ErrorAction Stop
    return ,(New-R2LedgerState $Q0 $Frequency $Plan)
}

function New-R2BootstrapQuarantine {
    param([Parameter(Mandatory)][object]$Plan,[Parameter(Mandatory)][IntPtr]$InheritedReaderLocator)
    if(Get-Module -Name Route2BootstrapQuarantine){throw 'R2_BOOTSTRAP_REISSUE'}
    Assert-R2StaticPlan $Plan
    Initialize-R2LedgerEnums
    if($InheritedReaderLocator -eq [IntPtr]::Zero -or $InheritedReaderLocator.ToInt64() -eq -1){throw 'R2_BOOTSTRAP_READER_LOCATOR'}
    $bootstrapModule=New-Module -Name Route2BootstrapQuarantine -ScriptBlock {
        $script:q=$null;$script:records=[Collections.Generic.List[object]]::new()
        $script:recordIndex=[Runtime.CompilerServices.ConditionalWeakTable[object,object]]::new()
        $script:bootstrapRetired=[Runtime.CompilerServices.ConditionalWeakTable[object,object]]::new()
        $script:bootstrapActive=[Collections.Generic.List[object]]::new(48)
        $script:bootstrapStorageBytes=0L
        $script:ownerThread=[Threading.Thread]::CurrentThread.ManagedThreadId
        $script:issuer=[object]::new();$script:sequence=0L
        function New-R2BootstrapMap([hashtable]$Fields){
            $map=[Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
            foreach($key in $Fields.Keys){$map.Add($key,$Fields[$key])};return ,$map
        }
        function New-R2BootstrapView($Map){return ,([Collections.ObjectModel.ReadOnlyDictionary[string,object]]::new($Map))}
        function New-R2BootstrapRecord([string]$Type,[hashtable]$Fields){
            if($Type -cin @('Handle','Candidate','Buffer')){
                if($script:q.Data.HandleCount -ge 96){throw 'R2_BOOTSTRAP_HANDLE_LIMIT'}
                $script:q.Data['HandleCount']=[long]$script:q.Data.HandleCount+1
            }
            $script:sequence++
            $d=New-R2BootstrapMap $Fields
            $d['IssuerIdentity']=$script:issuer;$d['IssuerSerial']=[uint64]$script:sequence
            $d['PlanReference']=$script:q.Data.PlanReference
            $v=New-R2BootstrapView $d
            $r=[pscustomobject]@{Type=$Type;Data=$d;View=$v;Private=(New-R2BootstrapMap @{})}
            if($Type -ceq 'Fact'){
                if($script:bootstrapActive.Count -ge 48){throw 'R2_BOOTSTRAP_ACTIVE_FACT_LIMIT'}
                Assert-R2BootstrapStorage 256
                $script:bootstrapStorageBytes+=256;$r.Private['StorageCharge']=256L;$r.Private['Retained']=$false
                $script:bootstrapActive.Add($r)
            }elseif($Type -cne 'BufferSlice'){$script:records.Add($r)}
            $script:recordIndex.Add($v,$r);return $r
        }
        function Assert-R2BootstrapStorage([long]$Additional){
            if($Additional -lt 0 -or [bigint]$script:q.Data.BufferBytes+$script:bootstrapStorageBytes+$Additional -gt 174762){$script:q.Data['Fault']='R2_BOOTSTRAP_FACT_STORAGE_LIMIT';throw 'R2_BOOTSTRAP_FACT_STORAGE_LIMIT'}
        }
        function Retire-R2BootstrapFact([object]$Quarantine,[object]$Fact){
            Assert-R2BootstrapQuarantineReference $Quarantine
            $retiredSerial=$null
            if($null -ne $Fact -and $script:bootstrapRetired.TryGetValue($Fact,[ref]$retiredSerial)){return}
            $r=Get-R2BootstrapRecord $Fact 'Fact'
            if($r.Private.Retained){return}
            $script:bootstrapRetired.Add($r.View,[object]$r.Data.IssuerSerial)
            [void]$script:recordIndex.Remove($r.View);[void]$script:bootstrapActive.Remove($r)
            $script:bootstrapStorageBytes-=[long]$r.Private.StorageCharge;$r.Private.Clear()
        }
        function Retire-R2BootstrapBufferFacts([object]$Quarantine,[object]$Buffer){
            $owner=Get-R2BootstrapRecord $Buffer ''
            if($owner.Type -ceq 'BufferSlice'){$Buffer=$owner.Data.BufferOwnerReference}
            for($i=$script:bootstrapActive.Count-1;$i -ge 0;$i--){
                $r=$script:bootstrapActive[$i]
                if(-not $r.Private.ContainsKey('Leases')){continue}
                foreach($lease in $r.Private.Leases.Values){if([object]::ReferenceEquals($lease.Owner,$Buffer)){Retire-R2BootstrapFact $Quarantine $r.View;break}}
            }
        }
        function Retain-R2BootstrapFact([object]$Quarantine,[object]$Fact){
            $r=Get-R2BootstrapRecord $Fact 'Fact'
            if($r.Private.Retained){return}
            if($script:q.Private.Facts.Count -ge 1024){throw 'R2_BOOTSTRAP_ESSENTIAL_FACT_LIMIT'}
            $needed=0L
            if($r.Private.ContainsKey('Leases')){foreach($lease in $r.Private.Leases.Values){if($lease.Valid -and $null -eq $lease.Data){$needed+=$lease.Length}}}
            if($needed -gt 4096){throw 'R2_BOOTSTRAP_TRANSIENT_PAYLOAD_NOT_ESSENTIAL'}
            Assert-R2BootstrapStorage $needed
            $script:bootstrapStorageBytes+=$needed;$r.Private.StorageCharge+=$needed
            if($r.Private.ContainsKey('Leases')){
                foreach($lease in $r.Private.Leases.Values){if($lease.Valid){if($null -eq $lease.Data){$lease.Data=[byte[]]::new([int]$lease.Length)};if($null -ne $lease.Owner){[Runtime.InteropServices.Marshal]::Copy($lease.Address,$lease.Data,0,$lease.Data.Length);$lease.Owner=$null;$lease.Address=[IntPtr]::Zero}}}
            }
            $r.Private.Retained=$true;[void]$script:bootstrapActive.Remove($r);$script:q.Private.Facts.Add($r.View)
        }
        function Retain-R2BootstrapNativeFact([object]$Quarantine,[object]$Fact){
            Assert-R2BootstrapQuarantineReference $Quarantine
            Retain-R2BootstrapFact $Quarantine $Fact
        }
        function Get-R2BootstrapRecord([object]$Reference,[string]$Type){
            if([Threading.Thread]::CurrentThread.ManagedThreadId -ne $script:ownerThread){throw 'R2_BOOTSTRAP_OWNER_THREAD'}
            $r=$null
            if($null -eq $Reference -or -not $script:recordIndex.TryGetValue($Reference,[ref]$r) -or -not [object]::ReferenceEquals($r.View,$Reference)){throw 'R2_BOOTSTRAP_UNISSUED'}
            if($Type -and $r.Type -cne $Type){throw 'R2_BOOTSTRAP_RECORD_KIND'}
            return $r
        }
        function Assert-R2BootstrapQuarantineReference([object]$Quarantine){
            $r=Get-R2BootstrapRecord $Quarantine 'Quarantine'
            if(-not [object]::ReferenceEquals($r,$script:q)){throw 'R2_BOOTSTRAP_REFERENCE'}
        }
        function Add-R2BootstrapCall([object]$Quarantine){
            Assert-R2BootstrapQuarantineReference $Quarantine
            if($script:q.Data.Fault -or $script:q.Data.Admitted){throw 'R2_BOOTSTRAP_TERMINAL'}
            if($script:q.Data.Calls -ge 16384){$script:q.Data['Fault']='R2_BOOTSTRAP_CALL_LIMIT';throw 'R2_BOOTSTRAP_CALL_LIMIT'}
            $step=$script:q.Private.Step
            if($null -eq $step -or $step.Calls -ge $step.Limit){throw 'R2_BOOTSTRAP_STEP_LIMIT'}
            $step.Calls++
            $script:q.Data['Calls']=[long]$script:q.Data.Calls+1
        }
        function Read-R2BootstrapTimestamp {
            Add-R2BootstrapCall $script:q.View
            $now=[Diagnostics.Stopwatch]::GetTimestamp()
            if($null -ne $script:q.Private.LastQpc -and $now -lt $script:q.Private.LastQpc){$script:q.Data['Fault']='R2_BOOTSTRAP_CLOCK_REVERSED';throw 'R2_BOOTSTRAP_CLOCK_REVERSED'}
            if($null -eq $script:q.Private.FirstStartedQpc){$script:q.Private.FirstStartedQpc=$now}
            $script:q.Private.LastQpc=$now
            return $now
        }
        function Enter-R2BootstrapStep([object]$Quarantine,[bool]$Observer=$false){
            Assert-R2BootstrapQuarantineReference $Quarantine
            if($null -ne $script:q.Private.Step -or $script:q.Data.Admitted -or $script:q.Data.Fault){throw 'R2_BOOTSTRAP_STEP_STATE'}
            $script:q.Private.Step=[pscustomobject]@{StartedQpc=$null;Calls=0;Limit=$(if($Observer){12}else{48})}
            $script:q.Private.Step.StartedQpc=Read-R2BootstrapTimestamp
        }
        function Exit-R2BootstrapStep([object]$Quarantine){
            Assert-R2BootstrapQuarantineReference $Quarantine
            $step=$script:q.Private.Step
            if($null -eq $step){throw 'R2_BOOTSTRAP_NO_STEP'}
            # Admission can finish during this step; close its bracket using the
            # same reserved quota without reopening native consumer authority.
            if($script:q.Data.Calls -ge 16384 -or $step.Calls -ge $step.Limit){$script:q.Private.Step=$null;throw 'R2_BOOTSTRAP_STEP_CLOCK_BUDGET'}
            $script:q.Data['Calls']=[long]$script:q.Data.Calls+1;$step.Calls++
            if($script:q.Data.Admitted){
                # Reserve this final actual QPC against the already authenticated
                # original slot AND global partition before issuing the clock.
                $script:q.Private.TransferSlotUsage['Calls']=[long]$script:q.Data.Calls
                try{Reconcile-R2BootstrapCharges $script:q.Data.PromotedContext $Quarantine}catch{$script:q.Private.Step=$null;throw}
            }
            $end=[Diagnostics.Stopwatch]::GetTimestamp()
            $reversed=($null -ne $script:q.Private.LastQpc -and $end -lt $script:q.Private.LastQpc)
            $script:q.Private.LastQpc=$end
            if($script:q.Data.Admitted){$script:q.Private.TransferSlotUsage['LastQpc']=$end}
            $script:q.Private.Step=$null
            for($i=$script:bootstrapActive.Count-1;$i -ge 0;$i--){Retire-R2BootstrapFact $Quarantine $script:bootstrapActive[$i].View}
            if($script:q.Data.Admitted){Reconcile-R2BootstrapCharges $script:q.Data.PromotedContext $Quarantine}
            if($reversed -or ([bigint]$end-$step.StartedQpc)*10 -gt [Diagnostics.Stopwatch]::Frequency){$script:q.Data['Fault']='R2_BOOTSTRAP_STEP_100MS';throw 'R2_BOOTSTRAP_STEP_100MS'}
        }
        function New-R2BootstrapState([object]$Plan,[IntPtr]$Reader){
            if($null -ne $script:q){throw 'R2_BOOTSTRAP_REISSUE'}
            $d=New-R2BootstrapMap @{PlanReference=$Plan;InheritedReader=$null;Calls=0L;HandleCount=0L;BufferBytes=0L;Fault=$null;Admitted=$false;PromotedContext=$null;NativeFacts=$null;IssuerIdentity=$script:issuer;IssuerSerial=[uint64]0}
            $v=New-R2BootstrapView $d
            $facts=[Collections.Generic.List[object]]::new();$d['NativeFacts']=$facts.AsReadOnly()
            $script:q=[pscustomobject]@{Type='Quarantine';Data=$d;View=$v;Private=(New-R2BootstrapMap @{Facts=$facts;Interop=$null;PromotionProof=$null;PromotionFields=$null;Step=$null;FirstStartedQpc=$null;LastQpc=$null;PendingReads=[Collections.Generic.List[object]]::new()})}
            $script:records.Add($script:q)
            $script:recordIndex.Add($v,$script:q)
            $readerEntry=New-R2BootstrapRecord 'Candidate' @{Address=$Reader;LocalValue=$Reader;Kind=[R2HandleKind]::PIPE;Ownership=[R2HandleOwnership]::UNKNOWN;State=[R2HandleState]::RESERVED;AcquireFact=$null;ConsumeFact=$null;Purpose='InheritedReader'}
            $d['InheritedReader']=$readerEntry.View
            return ,$v
        }
        function Get-R2BootstrapInheritedReader([object]$Quarantine){Assert-R2BootstrapQuarantineReference $Quarantine;return ,$script:q.Data.InheritedReader}
        function New-R2BootstrapHandleCandidate([object]$Quarantine,[IntPtr]$Value,[R2HandleKind]$Kind){
            Assert-R2BootstrapQuarantineReference $Quarantine
            if($script:q.Data.Admitted -or $script:q.Data.Fault -or $Value -eq [IntPtr]::Zero -or $Value.ToInt64() -eq -1 -or $Kind -cnotin @([R2HandleKind]::PROCESS,[R2HandleKind]::JOB,[R2HandleKind]::EVENT)){throw 'R2_BOOTSTRAP_CANDIDATE'}
            $candidateCount=0
            foreach($existing in $script:records){if($existing.Type -ceq 'Candidate'){$candidateCount++}}
            if($candidateCount -ge 16){throw 'R2_BOOTSTRAP_CANDIDATE_LIMIT'}
            $r=New-R2BootstrapRecord 'Candidate' @{Address=$Value;LocalValue=$Value;Kind=$Kind;Ownership=[R2HandleOwnership]::UNKNOWN;State=[R2HandleState]::RESERVED;AcquireFact=$null;ConsumeFact=$null;Purpose='RootDuplicate'}
            return ,$r.View
        }
        function New-R2BootstrapBuffer([object]$Quarantine,[uint32]$Capacity,[uint32]$Alignment=8){
            Assert-R2BootstrapQuarantineReference $Quarantine
            if($Capacity -eq 0 -or $Capacity -gt 4096 -or $Alignment -notin @(1,2,4,8,16) -or [bigint]$script:q.Data.BufferBytes+$Capacity+$Alignment-1 -gt 16384){throw 'R2_BOOTSTRAP_BUFFER_LIMIT'}
            Assert-R2BootstrapStorage ([long]$Capacity+$Alignment-1)
            $script:q.Data['BufferBytes']=[long]$script:q.Data.BufferBytes+$Capacity+$Alignment-1
            $r=New-R2BootstrapRecord 'Buffer' @{Address=$null;Capacity=$Capacity;Alignment=$Alignment;State=[R2HandleState]::RESERVED}
            Add-R2BootstrapCall $Quarantine
            $base=[Runtime.InteropServices.Marshal]::AllocHGlobal([int]($Capacity+$Alignment-1))
            $r.Private['Base']=$base
            $n=$base.ToInt64();$pad=($Alignment-($n % $Alignment)) % $Alignment
            $r.Data['Address']=[IntPtr]::new($n+$pad);$r.Data['State']=[R2HandleState]::LIVE
            for($i=0;$i -lt $Capacity;$i++){[Runtime.InteropServices.Marshal]::WriteByte($r.Data.Address,$i,0)}
            return ,$r.View
        }
        function Get-R2BootstrapBufferEntry([object]$Quarantine,[object]$Buffer,[uint32]$Offset,[uint32]$Count){
            Assert-R2BootstrapQuarantineReference $Quarantine
            $r=Get-R2BootstrapRecord $Buffer ''
            if($r.Type -cnotin @('Buffer','BufferSlice') -or [bigint]$Offset+$Count -gt $r.Data.Capacity){throw 'R2_BOOTSTRAP_BUFFER_RANGE'}
            $owner=if($r.Type -ceq 'Buffer'){$r}else{Get-R2BootstrapRecord $r.Data.BufferOwnerReference 'Buffer'}
            if($owner.Data.State -ne [R2HandleState]::LIVE -or $owner.Private.ContainsKey('Transferred')){throw 'R2_BOOTSTRAP_BUFFER_NOT_LIVE'}
            return $r
        }
        function Get-R2BootstrapBufferSlice([object]$Quarantine,[object]$Buffer,[uint32]$Offset,[uint32]$Length){
            $r=Get-R2BootstrapBufferEntry $Quarantine $Buffer $Offset $Length
            $owner=if($r.Type -ceq 'Buffer'){$r.View}else{$r.Data.BufferOwnerReference}
            $slice=New-R2BootstrapRecord 'BufferSlice' @{Address=[IntPtr]::Add($r.Data.Address,[int]$Offset);Capacity=$Length;BufferOwnerReference=$owner}
            return ,$slice.View
        }
        function Write-R2BootstrapBuffer([object]$Quarantine,[object]$Buffer,[uint32]$Offset,[byte[]]$Bytes){
            $r=Get-R2BootstrapBufferEntry $Quarantine $Buffer $Offset ([uint32]$Bytes.Length)
            Retire-R2BootstrapBufferFacts $Quarantine $Buffer
            [Runtime.InteropServices.Marshal]::Copy($Bytes,0,[IntPtr]::Add($r.Data.Address,[int]$Offset),$Bytes.Length)
        }
        function Read-R2BootstrapBuffer([object]$Quarantine,[object]$Buffer,[uint32]$Offset,[uint32]$Count){
            $r=Get-R2BootstrapBufferEntry $Quarantine $Buffer $Offset $Count
            $bytes=[byte[]]::new([int]$Count);[Runtime.InteropServices.Marshal]::Copy([IntPtr]::Add($r.Data.Address,[int]$Offset),$bytes,0,$bytes.Length)
            return ,([Array]::AsReadOnly($bytes))
        }
        function Write-R2BootstrapReference([object]$Quarantine,[object]$Buffer,[uint32]$Offset,[object]$Reference){
            $r=Get-R2BootstrapBufferEntry $Quarantine $Buffer $Offset 8
            Retire-R2BootstrapBufferFacts $Quarantine $Buffer
            $p=Get-R2BootstrapRecord $Reference ''
            if($p.Type -cnotin @('Buffer','BufferSlice','Handle','Candidate')){throw 'R2_BOOTSTRAP_POINTER_KIND'}
            [Runtime.InteropServices.Marshal]::WriteIntPtr($r.Data.Address,[int]$Offset,$p.Data.Address)
        }
        function Release-R2BootstrapBuffer([object]$Quarantine,[object]$Buffer){
            $r=Get-R2BootstrapBufferEntry $Quarantine $Buffer 0 0
            if($r.Type -cne 'Buffer'){throw 'R2_BOOTSTRAP_SLICE_FREE'}
            if($r.Private.ContainsKey('PendingIoCount') -and $r.Private.PendingIoCount -gt 0){throw 'R2_BOOTSTRAP_BUFFER_IO_PENDING'}
            Retire-R2BootstrapBufferFacts $Quarantine $Buffer
            $r.Data['State']=[R2HandleState]::CONSUMED
            Add-R2BootstrapCall $Quarantine
            [Runtime.InteropServices.Marshal]::FreeHGlobal($r.Private.Base)
        }
        function Invoke-R2BootstrapNative([object]$Quarantine,[object]$Interop,[R2ApiId]$ApiId,[object[]]$Arguments){
            Assert-R2BootstrapQuarantineReference $Quarantine
            try{return ,(Invoke-R2BootstrapNativeCore $Quarantine $Interop $ApiId $Arguments)}
            catch{if(-not $script:q.Data.Fault){$script:q.Data['Fault']='R2_BOOTSTRAP_NATIVE_FAILURE'};throw}
        }
        function Invoke-R2BootstrapNativeCore([object]$Quarantine,[object]$Interop,[R2ApiId]$ApiId,[object[]]$Arguments){
            $descriptor=Get-R2BootstrapNativeDescriptor $Quarantine $Interop $ApiId
            $method=Get-R2BootstrapNativeApi $Quarantine $Interop $ApiId
            if($null -eq $script:q.Private.Interop){$script:q.Private.Interop=$Interop}
            elseif(-not [object]::ReferenceEquals($script:q.Private.Interop,$Interop)){throw 'R2_BOOTSTRAP_INTEROP_REPLACEMENT'}
            $name=[string]$ApiId
            if($name -cin @('CloseHandle','LocalFree')){throw 'R2_BOOTSTRAP_CLOSE_OWNER'}
            if($name -ceq 'WaitForSingleObject' -and $Arguments[1] -ne 0){throw 'R2_BOOTSTRAP_BLOCKING_WAIT'}
            if($name -ceq 'CreateToolhelp32Snapshot' -and ($Arguments[0] -ne 2 -or $Arguments[1] -ne 0)){throw 'R2_BOOTSTRAP_SNAPSHOT_FLAGS'}
            if($name -ceq 'CreateEventW'){
                if($Arguments[1] -ne 1 -or $Arguments[2] -ne 0 -or $null -ne $Arguments[3]){throw 'R2_BOOTSTRAP_READ_EVENT_FLAGS'}
                $sa=Get-R2BootstrapBufferEntry $Quarantine $Arguments[0] 0 24
                if([Runtime.InteropServices.Marshal]::ReadInt32($sa.Data.Address,0) -ne 24 -or [Runtime.InteropServices.Marshal]::ReadIntPtr($sa.Data.Address,8) -ne [IntPtr]::Zero -or [Runtime.InteropServices.Marshal]::ReadInt32($sa.Data.Address,16) -ne 0){throw 'R2_BOOTSTRAP_READ_EVENT_ATTRIBUTES'}
            }
            if($name -ceq 'CreateFileW'){
                if(-not ([string]$Arguments[0]).StartsWith('\\.\pipe\',[StringComparison]::Ordinal) -or $Arguments[0].Length -gt 255 -or $Arguments[1] -ne [uint32]3221225472 -or $Arguments[2] -ne 0 -or $Arguments[4] -ne 3 -or $Arguments[5] -ne [uint32]1073741824){throw 'R2_BOOTSTRAP_NAMEDCLIENT_FLAGS'}
            }
            $pending=$null
            if($name -cin @('GetOverlappedResult','CancelIoEx')){
                foreach($entry in $script:q.Private.PendingReads){if([object]::ReferenceEquals($entry.Handle,$Arguments[0]) -and [object]::ReferenceEquals($entry.Overlap,$Arguments[1]) -and -not $entry.Completed){$pending=$entry;break}}
                if($null -eq $pending -or ($name -ceq 'GetOverlappedResult' -and $Arguments[3] -ne 0)){throw 'R2_BOOTSTRAP_PENDING_READ_BINDING'}
            }
            if($Arguments.Count -ne $descriptor.ParameterTypes.Count){throw 'R2_BOOTSTRAP_ARGUMENT_COUNT'}
            $native=[object[]]::new($Arguments.Count);$buffers=@{}
            for($i=0;$i -lt $Arguments.Count;$i++){
                $kind=[string]$descriptor.ParamKinds[$i];$direction=[string]$descriptor.BufferDirections[$i]
                if($kind -ceq 'Pointer'){
                    if($Arguments[$i] -is [IntPtr] -and $Arguments[$i] -eq [IntPtr]::Zero){if($i -notin $descriptor.NullableParameters){throw 'R2_BOOTSTRAP_NULL_POINTER'};$native[$i]=[IntPtr]::Zero;continue}
                    $p=Get-R2BootstrapRecord $Arguments[$i] ''
                    if($p.Type -cin @('Buffer','BufferSlice')){
                        [void](Get-R2BootstrapBufferEntry $Quarantine $p.View 0 0)
                        if($descriptor.OutputSizes.ContainsKey([string]$i) -and $p.Data.Capacity -lt $descriptor.OutputSizes[[string]$i]){throw 'R2_BOOTSTRAP_OUTPUT_CAPACITY'}
                        if($descriptor.DynamicBufferLengths.ContainsKey([string]$i)){$length=$descriptor.DynamicBufferLengths[[string]$i];if([bigint]$Arguments[[int]$length.LengthParameter]*$length.UnitBytes -gt $p.Data.Capacity){throw 'R2_BOOTSTRAP_BUFFER_LENGTH'}}
                        $native[$i]=$p.Data.Address;$buffers[[string]$i]=$p
                    }elseif($direction -ceq 'None' -and $p.Type -cin @('Handle','Candidate')){
                        if($p.Type -ceq 'Handle' -and $p.Data.State -ne [R2HandleState]::LIVE){throw 'R2_BOOTSTRAP_HANDLE_NOT_LIVE'}
                        if($p.Type -ceq 'Candidate' -and (($p.Data.Purpose -ceq 'InheritedReader' -and $name -cne 'ReadFile') -or ($p.Data.Purpose -ceq 'RootDuplicate' -and $name -cnotin @('GetProcessId','GetProcessTimes','WaitForSingleObject')))){throw 'R2_BOOTSTRAP_CANDIDATE_USE'}
                        $native[$i]=$p.Data.Address
                    }else{throw 'R2_BOOTSTRAP_UNREGISTERED_POINTER'}
                }elseif($kind -ceq 'String'){
                    if($null -ne $Arguments[$i] -and (-not ($Arguments[$i] -is [string]) -or $Arguments[$i].Length -gt 4096 -or $Arguments[$i].IndexOf([char]0) -ge 0)){throw 'R2_BOOTSTRAP_STRING'}
                    $native[$i]=$Arguments[$i]
                }else{
                    $required=switch($kind){'UInt32'{[uint32]}'Int32'{[int]}'UInt16'{[uint16]}'UInt64'{[uint64]}default{throw 'R2_BOOTSTRAP_SCALAR_KIND'}}
                    if($Arguments[$i].GetType() -ne $required){throw 'R2_BOOTSTRAP_SCALAR_WIDTH'};$native[$i]=$Arguments[$i]
                }
            }
            $outputs=New-R2BootstrapMap @{};$leases=New-R2BootstrapMap @{}
            foreach($key in $buffers.Keys){
                if([string]$descriptor.BufferDirections[[int]$key] -cnotin @('Out','InOut')){continue}
                $be=$buffers[$key];$owner=if($be.Type -ceq 'BufferSlice'){$be.Data.BufferOwnerReference}else{$be.View}
                Retire-R2BootstrapBufferFacts $Quarantine $owner
                $length=[long]$be.Data.Capacity
                if($descriptor.OutputSizes.ContainsKey($key) -and [long]$descriptor.OutputSizes[$key] -gt 0){$length=[long]$descriptor.OutputSizes[$key]}
                if($descriptor.DynamicBufferLengths.ContainsKey($key)){$spec=$descriptor.DynamicBufferLengths[$key];$length=[long]([bigint]$Arguments[[int]$spec.LengthParameter]*$spec.UnitBytes)}
                $leases[$key]=[pscustomobject]@{Owner=$owner;Address=$be.Data.Address;Length=$length;Data=$null;ReadOnlyData=$null;Valid=$false}
            }
            $acquired=[Collections.Generic.List[object]]::new(1)
            $fact=New-R2BootstrapRecord 'Fact' @{ApiId=$ApiId;RawStatus=$null;StatusBits=$null;QpcBegin=$null;QpcEnd=$null;ReturnValue=$null;Outputs=(New-R2BootstrapView $outputs);AcquiredHandles=$acquired.AsReadOnly()}
            $fact.Private['Arguments']=$Arguments.Clone()
            $fact.Private['Leases']=$leases
            Assert-R2BootstrapStorage ([long]$leases.Count*128)
            $script:bootstrapStorageBytes+=[long]$leases.Count*128;$fact.Private.StorageCharge+=[long]$leases.Count*128
            foreach($key in $leases.Keys){$outputs[$key]=New-R2BootstrapView (New-R2BootstrapMap @{Count=[uint32]$leases[$key].Length;LeaseSerial=$fact.Data.IssuerSerial;ArgumentIndex=[uint32]$key})}
            $reserved=$null;$outputIndex=-1
            $reservedKind=switch -CaseSensitive($name){
                'GetCurrentProcess'{[R2HandleKind]::PROCESS}
                'CreateToolhelp32Snapshot'{[R2HandleKind]::SNAPSHOT}
                'CreateFileW'{[R2HandleKind]::PIPE}
                'CreateEventW'{[R2HandleKind]::EVENT}
                'OpenProcessToken'{$outputIndex=2;[R2HandleKind]::TOKEN}
                'ConvertSidToStringSidW'{$outputIndex=1;[R2HandleKind]::LOCAL_ALLOCATION}
                'ConvertStringSecurityDescriptorToSecurityDescriptorW'{$outputIndex=2;[R2HandleKind]::LOCAL_ALLOCATION}
            }
            if($null -ne $reservedKind){
                $reserved=New-R2BootstrapRecord 'Handle' @{Address=$null;LocalValue=$null;Kind=$reservedKind;Ownership=$(if($name -ceq 'GetCurrentProcess'){[R2HandleOwnership]::BORROWED}else{[R2HandleOwnership]::OWNED});State=[R2HandleState]::RESERVED;AcquireFact=$null;ConsumeFact=$null}
                $reserved.Private['AttemptFact']=$fact.View
                if($outputIndex -ge 0 -and (-not $leases.ContainsKey([string]$outputIndex) -or $leases[[string]$outputIndex].Length -lt 8)){throw 'R2_BOOTSTRAP_ACQUISITION_OUTPUT_CAPACITY'}
            }
            $autoRetain=($null -ne $reserved -or $name -cin @('GetProcessId','GetProcessTimes','GetNamedPipeServerProcessId','WaitForSingleObject','GetTokenInformation'))
            if($autoRetain){
                if($script:q.Private.Facts.Count -ge 1024){throw 'R2_BOOTSTRAP_ESSENTIAL_FACT_LIMIT'}
                $needed=0L;foreach($lease in $leases.Values){$needed+=$lease.Length}
                if($needed -gt 4096){throw 'R2_BOOTSTRAP_ACQUISITION_PAYLOAD_LIMIT'}
                Assert-R2BootstrapStorage $needed
                $script:bootstrapStorageBytes+=$needed;$fact.Private.StorageCharge+=$needed
                foreach($lease in $leases.Values){$lease.Data=[byte[]]::new([int]$lease.Length);$lease.ReadOnlyData=[Array]::AsReadOnly($lease.Data)}
            }
            if($name -ceq 'ReadFile'){
                $pipe=Get-R2BootstrapRecord $Arguments[0] ''
                if($native[4] -eq [IntPtr]::Zero){if($pipe.Type -cne 'Candidate' -or $pipe.Data.Purpose -cne 'InheritedReader'){throw 'R2_BOOTSTRAP_NAMED_READ_REQUIRES_OVERLAPPED'}}
                else{
                    foreach($entry in $script:q.Private.PendingReads){if(-not $entry.Completed -and ([object]::ReferenceEquals($entry.Handle,$Arguments[0]) -or [object]::ReferenceEquals($entry.Overlap,$Arguments[4]))){throw 'R2_BOOTSTRAP_SECOND_PENDING_READ'}}
                    $ov=Get-R2BootstrapBufferEntry $Quarantine $Arguments[4] 0 32
                    $eventValue=[Runtime.InteropServices.Marshal]::ReadIntPtr($ov.Data.Address,24)
                    $event=$null
                    foreach($r in $script:records){if($r.Type -ceq 'Handle' -and $r.Data.Kind -eq [R2HandleKind]::EVENT -and $r.Data.State -eq [R2HandleState]::LIVE -and $r.Data.LocalValue -eq $eventValue){$event=$r;break}}
                    if($null -eq $event){throw 'R2_BOOTSTRAP_READ_EVENT_NOT_ORIGINAL'}
                    $pins=[Collections.Generic.List[object]]::new()
                    foreach($ref in @($Arguments[1],$Arguments[3],$Arguments[4])){
                        $r=Get-R2BootstrapBufferEntry $Quarantine $ref 0 0
                        if($r.Type -ceq 'BufferSlice'){$r=Get-R2BootstrapRecord $r.Data.BufferOwnerReference 'Buffer'}
                        if(-not $r.Private.ContainsKey('PendingIoCount')){$r.Private['PendingIoCount']=0L}
                        $r.Private['PendingIoCount']=[long]$r.Private.PendingIoCount+1;$pins.Add($r)
                    }
                    if(-not $event.Private.ContainsKey('PendingIoCount')){$event.Private['PendingIoCount']=0L};$event.Private['PendingIoCount']=[long]$event.Private.PendingIoCount+1;$pins.Add($event)
                    $pending=[pscustomobject]@{Handle=$Arguments[0];Overlap=$Arguments[4];Completed=$false;Pins=$pins;IssueFact=$fact.View;CompletionFact=$null}
                    $script:q.Private.PendingReads.Add($pending)
                }
            }
            Add-R2BootstrapCall $Quarantine
            $begin=(Read-R2BootstrapTimestamp);$fact.Data['QpcBegin']=$begin
            $ret=$method.Invoke($null,$native)
            $err=[Runtime.InteropServices.Marshal]::GetLastWin32Error()
            $fact.Data['ReturnValue']=$ret;$fact.Data['RawStatus']=$(if($ret -is [IntPtr]){$ret.ToInt64()}elseif($null -eq $ret){$null}else{[long]$ret});$fact.Data['StatusBits']=[BitConverter]::ToUInt32([BitConverter]::GetBytes([int]$err),0)
            $accepted=switch -CaseSensitive([string]$descriptor.ReturnConvention){'BOOL'{[long]$ret -ne 0}'HANDLE_INVALID'{$ret.ToInt64() -ne -1}'HANDLE_NULL'{$ret -ne [IntPtr]::Zero}'BORROWED_PSEUDO'{$ret.ToInt64() -eq -1}'DWORD'{$true}default{$false}}
            foreach($key in $leases.Keys){$leases[$key].Valid=$accepted;if($name -ceq 'GetTokenInformation' -and $err -eq 122 -and $key -ceq '4'){$leases[$key].Valid=$true}}
            if($null -ne $reserved -and $accepted){
                $value=if($outputIndex -lt 0){[IntPtr]$ret}else{[IntPtr]::new([Runtime.InteropServices.Marshal]::ReadInt64($leases[[string]$outputIndex].Address))}
                if(($name -cne 'GetCurrentProcess') -and ($value -eq [IntPtr]::Zero -or $value.ToInt64() -eq -1)){throw 'R2_BOOTSTRAP_INVALID_NATIVE_HANDLE'}
                $reserved.Data['Address']=$value;$reserved.Data['LocalValue']=$value;$reserved.Data['State']=[R2HandleState]::LIVE;$reserved.Data['AcquireFact']=$fact.View
                $acquired.Add($reserved.View)
            }
            if($autoRetain){Retain-R2BootstrapFact $Quarantine $fact.View}
            if($null -ne $pending -and (($name -ceq 'ReadFile' -and ([long]$ret -ne 0 -or $err -ne 997)) -or ($name -ceq 'GetOverlappedResult' -and ([long]$ret -ne 0 -or $err -eq 995)))){
                $pending.Completed=$true;$pending.CompletionFact=$fact.View
                foreach($pin in $pending.Pins){$pin.Private['PendingIoCount']=[long]$pin.Private.PendingIoCount-1}
                $pending.Pins.Clear()
                $script:q.Private['LastCompletedRead']=$pending
                [void]$script:q.Private.PendingReads.Remove($pending)
            }
            $end=(Read-R2BootstrapTimestamp);$fact.Data['QpcEnd']=$end
            if($end -lt $begin -or ([bigint]$end-$begin)*10 -gt [Diagnostics.Stopwatch]::Frequency){throw 'R2_BOOTSTRAP_NATIVE_100MS'}
            return ,$fact.View
        }
        function Close-R2BootstrapHandle([object]$Quarantine,[object]$Interop,[object]$Handle){
            Assert-R2BootstrapQuarantineReference $Quarantine
            $h=Get-R2BootstrapRecord $Handle 'Handle'
            if($h.Data.Ownership -ne [R2HandleOwnership]::OWNED -or $h.Data.State -ne [R2HandleState]::LIVE -or $h.Private.ContainsKey('Transferred')){throw 'R2_BOOTSTRAP_NOT_CLOSE_OWNER'}
            if($h.Private.ContainsKey('PendingIoCount') -and $h.Private.PendingIoCount -gt 0){throw 'R2_BOOTSTRAP_HANDLE_IO_PENDING'}
            foreach($entry in $script:q.Private.PendingReads){if(-not $entry.Completed -and [object]::ReferenceEquals($entry.Handle,$Handle)){throw 'R2_BOOTSTRAP_PIPE_IO_PENDING'}}
            $h.Data['State']=[R2HandleState]::CONSUMED
            $api=if($h.Data.Kind -eq [R2HandleKind]::LOCAL_ALLOCATION){[R2ApiId]::LocalFree}else{[R2ApiId]::CloseHandle}
            $m=Get-R2BootstrapNativeApi $Quarantine $Interop $api
            $f=New-R2BootstrapRecord 'Fact' @{ApiId=$api;RawStatus=$null;StatusBits=$null;QpcBegin=$null;QpcEnd=$null;ReturnValue=$null;Outputs=(New-R2BootstrapView (New-R2BootstrapMap @{}));AcquiredHandles=[Array]::AsReadOnly([object[]]@())}
            Retain-R2BootstrapFact $Quarantine $f.View
            $h.Data['ConsumeFact']=$f.View
            Add-R2BootstrapCall $Quarantine
            $begin=(Read-R2BootstrapTimestamp);$f.Data['QpcBegin']=$begin
            $ret=$m.Invoke($null,[object[]]@($h.Data.LocalValue));$err=[Runtime.InteropServices.Marshal]::GetLastWin32Error()
            $f.Data['ReturnValue']=$ret;$f.Data['RawStatus']=$(if($ret -is [IntPtr]){$ret.ToInt64()}else{[long]$ret});$f.Data['StatusBits']=[BitConverter]::ToUInt32([BitConverter]::GetBytes([int]$err),0)
            $end=(Read-R2BootstrapTimestamp);$f.Data['QpcEnd']=$end
            if(($api -eq [R2ApiId]::CloseHandle -and $f.Data.RawStatus -eq 0) -or ($api -eq [R2ApiId]::LocalFree -and $ret -ne [IntPtr]::Zero) -or $end -lt $begin -or ([bigint]$end-$begin)*10 -gt [Diagnostics.Stopwatch]::Frequency){$script:q.Data['Fault']='R2_BOOTSTRAP_CLOSE_FAILED';throw 'R2_BOOTSTRAP_CLOSE_FAILED'}
            return ,$f.View
        }
        function Consume-R2BootstrapAdmission([object]$Quarantine,[object]$Proof){
            Assert-R2BootstrapQuarantineReference $Quarantine
            if($script:q.Data.Admitted -or $script:q.Data.Fault){throw 'R2_BOOTSTRAP_ADMISSION_TERMINAL'}
            foreach($entry in $script:q.Private.PendingReads){if(-not $entry.Completed){throw 'R2_BOOTSTRAP_ADMISSION_IO_PENDING'}}
            Assert-R2BootstrapAdmissionProof $Quarantine $Proof
            $fields=Get-R2BootstrapAdmissionFields $Quarantine $Proof
            if(-not [object]::ReferenceEquals($fields.Interop,$script:q.Private.Interop) -or $fields.Frequency -ne [Diagnostics.Stopwatch]::Frequency -or $fields.Role -notin @([R2Role]::CONTROLLER,[R2Role]::WATCHDOG,[R2Role]::TRANSPORT)){throw 'R2_BOOTSTRAP_ADMISSION_FIELDS'}
            $q0=[long]$fields.Q0;$hz=[long]$fields.Frequency
            if($q0 -le 0 -or $fields.PrepDeadline -ne [bigint]$q0+1800*[bigint]$hz -or $fields.ExternalDeadline -ne [bigint]$q0+6000*[bigint]$hz -or $null -ne $fields.StudyDeadline -or $fields.InvocationNonce.Count -ne 32){throw 'R2_BOOTSTRAP_ORIGINAL_DEADLINES'}
            $script:q.Private.PromotionProof=$Proof;$script:q.Private.PromotionFields=$fields
            $context=New-R2Ledger $q0 $hz $script:q.Data.PlanReference
            $script:q.Data['PromotedContext']=$context
            Import-R2BootstrapOwnership $context $Quarantine $Proof
            $script:q.Data['Admitted']=$true
            Bind-R2Interop $context $script:q.Private.Interop
            return ,$context
        }
        function Assert-R2BootstrapPromotion([object]$Context,[object]$Quarantine){
            Assert-R2BootstrapQuarantineReference $Quarantine
            Assert-R2ContextReference $Context
            if(-not [object]::ReferenceEquals($script:q.Data.PromotedContext,$Context) -or $null -eq $script:q.Private.PromotionProof){throw 'R2_BOOTSTRAP_PROMOTION_REFERENCE'}
            Assert-R2BootstrapAdmissionProof $Quarantine $script:q.Private.PromotionProof
        }
        function Get-R2BootstrapPromotionData([object]$Context,[object]$Quarantine,[object]$Proof){
            Assert-R2BootstrapPromotion $Context $Quarantine
            if(-not [object]::ReferenceEquals($Proof,$script:q.Private.PromotionProof)){throw 'R2_BOOTSTRAP_PROMOTION_PROOF'}
            if($script:q.Private.ContainsKey('TransferManifest')){return ,$script:q.Private.TransferManifest}
            $transfers=[Collections.Generic.List[object]]::new()
            foreach($r in $script:records){
                if($r.Type -ceq 'Buffer'){
                    if($r.Data.State -eq [R2HandleState]::LIVE){
                        $transfers.Add((New-R2BootstrapView (New-R2BootstrapMap @{Type='Buffer';Original=$r.View;Address=$r.Data.Address;Capacity=$r.Data.Capacity;Alignment=$r.Data.Alignment;BaseAddress=$r.Private.Base;State=$r.Data.State})))
                        $r.Private['Transferred']=$Context
                    }
                }elseif($r.Type -ceq 'Handle'){
                    $transfers.Add((New-R2BootstrapView (New-R2BootstrapMap @{Type='Handle';Original=$r.View;LocalValue=$r.Data.LocalValue;Kind=$r.Data.Kind;Ownership=$r.Data.Ownership;State=$r.Data.State;AcquireFact=$r.Data.AcquireFact;ConsumeFact=$r.Data.ConsumeFact})))
                    $r.Private['Transferred']=$Context
                }elseif($r.Type -ceq 'Candidate'){
                    $admitted=$false
                    foreach($original in $script:q.Private.PromotionFields.OwnedCandidateHandles){if([object]::ReferenceEquals($original,$r.View)){$admitted=$true;break}}
                    if($admitted){
                        $transfers.Add((New-R2BootstrapView (New-R2BootstrapMap @{Type='Handle';Original=$r.View;LocalValue=$r.Data.LocalValue;Kind=$r.Data.Kind;Ownership=[R2HandleOwnership]::OWNED;State=[R2HandleState]::LIVE;AcquireFact=$null;ConsumeFact=$null})))
                        $r.Private['Transferred']=$Context
                    }
                }
            }
            # The first charged native timestamp predates admission. The live
            # read-only usage view also carries the one final admission-exit QPC.
            $usage=New-R2BootstrapMap @{Births=0L;Calls=[long]$script:q.Data.Calls;Handles=[long]$script:q.Data.HandleCount;Bytes=[long]$script:q.Data.BufferBytes;FirstStartedQpc=$script:q.Private.FirstStartedQpc;LastQpc=$script:q.Private.LastQpc}
            $script:q.Private['TransferSlotUsage']=$usage
            $manifest=New-R2BootstrapView (New-R2BootstrapMap @{Fields=$script:q.Private.PromotionFields;Calls=$script:q.Data.Calls;HandleCount=$script:q.Data.HandleCount;BufferBytes=$script:q.Data.BufferBytes;StorageBytes=$script:bootstrapStorageBytes;SlotUsage=(New-R2BootstrapView $usage);NativeFacts=$script:q.Data.NativeFacts;Transfers=$transfers.AsReadOnly()})
            $script:q.Private['TransferManifest']=$manifest
            return ,$manifest
        }
        Export-ModuleMember -Function New-R2BootstrapState,Assert-R2BootstrapQuarantineReference,Enter-R2BootstrapStep,Exit-R2BootstrapStep,Get-R2BootstrapInheritedReader,New-R2BootstrapHandleCandidate,New-R2BootstrapBuffer,Get-R2BootstrapBufferSlice,Write-R2BootstrapBuffer,Read-R2BootstrapBuffer,Write-R2BootstrapReference,Release-R2BootstrapBuffer,Invoke-R2BootstrapNative,Close-R2BootstrapHandle,Consume-R2BootstrapAdmission,Assert-R2BootstrapPromotion,Get-R2BootstrapPromotionData,Retain-R2BootstrapNativeFact
    }
    Import-Module -ModuleInfo $bootstrapModule -Global -ErrorAction Stop
    return ,(New-R2BootstrapState $Plan $InheritedReaderLocator)
}
