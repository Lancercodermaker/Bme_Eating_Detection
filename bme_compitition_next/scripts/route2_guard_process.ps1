# SOURCE ONLY: selected Windows C00 process/channel mechanisms. No initializer
# invokes native code. The original entry loads definitions after its q0.
# All native calls (including cleanup) use the original ledger wrapper.
# Entry drives process/channel continuations in ordinary guard steps (Observer
# false), retaining the original slot's cumulative quota and original deadlines.
# The native C component's independent 48/12 limits are not changed here.

function Initialize-R2ProcessOwner {
    if (Get-Module -Name Route2OriginalProcess) { return }
    $owner = New-Module -Name Route2OriginalProcess -ScriptBlock {
        $script:contexts = [Collections.Generic.List[object]]::new()
        $script:records = [Runtime.CompilerServices.ConditionalWeakTable[object,object]]::new()
        $script:bootstrap = $null
        $script:proofs = [Collections.Generic.List[object]]::new()
        $script:thread = [Threading.Thread]::CurrentThread.ManagedThreadId

        function New-R2ProcessMap([hashtable]$Fields) {
            $d=[Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
            foreach($k in $Fields.Keys){$d.Add([string]$k,$Fields[$k])}
            return ,$d
        }
        function New-R2ProcessView($Data) {
            return ,([Collections.ObjectModel.ReadOnlyDictionary[string,object]]::new($Data))
        }
        function Get-R2ProcessOwnerState($Context) {
            Assert-R2ContextReference $Context
            if([Threading.Thread]::CurrentThread.ManagedThreadId -ne $script:thread){throw 'R2_PROCESS_OWNER_THREAD'}
            foreach($r in $script:contexts){if([object]::ReferenceEquals($r.Context,$Context)){return $r}}
            $r=[pscustomobject]@{Context=$Context;External=$null;Prep=$null;Current=$null;Root=$null;RootPid=$null;StopEvent=$null;N=$null;JobsAttempted=$false;JobStage=0;JobReadbackPending=$false;JobQueryPool=$null;TerminalIssued=$false;StopEventAttempted=$false;PrepTerminateAttempted=$false;PrepTerminateFact=$null;Children=[Collections.Generic.List[object]]::new();Peers=[Collections.Generic.List[object]]::new();LocalPeer=$null;BootstrapAttempted=$false;Facts=[Collections.Generic.List[object]]::new()}
            $script:contexts.Add($r)
            return $r
        }
        function New-R2ProcessRecord($Context,$Slot,[string]$Kind,[hashtable]$Fields) {
            Assert-R2PlanSlot $Context $Slot
            $identity=Reserve-R2ComponentIdentity $Context $Slot $Kind
            $d=New-R2ProcessMap $Fields
            $d['IssuerIdentity']=$identity.IssuerIdentity;$d['IssuerSerial']=$identity.IssuerSerial
            $d['ContextReference']=$Context;$d['PlanReference']=$Context.PlanReference;$d['OriginalSlotReference']=$Slot
            $d['PrepDeadline']=$Context.PrepDeadline;$d['ExternalDeadline']=$Context.ExternalDeadline
            $d['StudyDeadline']=$Context.StudyDeadline;$d['DeadlineOwnerReference']=$Context
            $e=[pscustomobject]@{Kind=$Kind;Data=$d;View=(New-R2ProcessView $d);Private=(New-R2ProcessMap @{})}
            $script:records.Add($e.View,$e)
            return $e
        }
        function Get-R2ProcessRecord($Context,$Reference,[string]$Kind) {
            $null=Get-R2ProcessOwnerState $Context
            $e=$null
            if($null -ne $Reference -and $script:records.TryGetValue($Reference,[ref]$e)){
                    $kindMatches=($e.Kind -ceq $Kind -or ($Kind -ceq 'Peer' -and $e.Kind -ceq 'LocalPeer'))
                    if(-not $kindMatches -or -not [object]::ReferenceEquals($e.Data.ContextReference,$Context) -or -not [object]::ReferenceEquals($e.Data.PlanReference,$Context.PlanReference)){throw 'R2_PROCESS_REFERENCE_BINDING'}
                    Assert-R2PlanSlot $Context $e.Data.OriginalSlotReference
                    return $e
            }
            throw 'R2_PROCESS_UNISSUED_REFERENCE'
        }
        function Stop-R2ProcessFault($Context,[string]$Code,$Fact=$null,[uint64]$Serial=0) {
            if($null -ne $Fact){Retain-R2NativeFact $Context $Fact}
            $status=if($null -eq $Fact){$null}elseif($null -ne $Fact.StatusBits){[long]$Fact.StatusBits}else{[long]$Fact.RawStatus}
            Stop-R2Guard $Context 'External' $Code $status $Serial
            throw $Code
        }
        function Assert-R2ProcessLive($Context) {
            Assert-R2ContextReference $Context
            if($Context.StopState -eq [R2Fact]::TRUE){throw 'R2_PROCESS_TERMINAL_WORK'}
        }
        function Invoke-R2ProcessNative($Context,[R2ApiId]$Api,[object[]]$Arguments) {
            return ,(Invoke-R2NativeCall $Context $Api $Arguments)
        }
        function Get-R2ProcessFactSummary($Fact) {
            return ,(New-R2ProcessView (New-R2ProcessMap @{ApiId=$Fact.ApiId;IssuerSerial=$Fact.IssuerSerial;RawStatus=$Fact.RawStatus;StatusBits=$Fact.StatusBits;QpcBegin=$Fact.QpcBegin;QpcEnd=$Fact.QpcEnd}))
        }
        function Add-R2ProcessStatusSummary($History,$Fact) {
            if($History.Count -ge 32){$History.RemoveAt(0)}
            $History.Add((Get-R2ProcessFactSummary $Fact))
        }
        function Assert-R2ProcessBool($Context,$Fact,[string]$Code) {
            if($Fact.RawStatus -eq 0){Stop-R2ProcessFault $Context $Code $Fact $Fact.IssuerSerial}
        }
        function New-R2ProcessBuffer($Context,[uint32]$Size) {
            return ,(New-R2NativeBuffer $Context (Get-R2CurrentSlot $Context) $Size 8)
        }
        function Set-R2ProcessU32($Context,$Buffer,[uint32]$Offset,[uint32]$Value){Write-R2NativeBuffer $Context $Buffer $Offset ([BitConverter]::GetBytes($Value))}
        function Set-R2ProcessU64($Context,$Buffer,[uint32]$Offset,[uint64]$Value){Write-R2NativeBuffer $Context $Buffer $Offset ([BitConverter]::GetBytes($Value))}
        function Get-R2ProcessU32($Context,$Buffer,[uint32]$Offset){return [BitConverter]::ToUInt32([byte[]](Read-R2NativeBuffer $Context $Buffer $Offset 4),0)}
        function Get-R2ProcessU64($Context,$Buffer,[uint32]$Offset){return [BitConverter]::ToUInt64([byte[]](Read-R2NativeBuffer $Context $Buffer $Offset 8),0)}
        function New-R2ProcessHandle($Context,[R2HandleKind]$Kind,[R2HandleOwnership]$Ownership=[R2HandleOwnership]::OWNED){return ,(Reserve-R2Handle $Context $Kind $Ownership (Get-R2CurrentSlot $Context))}
        function Assert-R2ProcessHandle($Context,$Handle,$Fact){
            if($Handle.State -ne [R2HandleState]::LIVE){Stop-R2ProcessFault $Context 'R2_PROCESS_ACQUIRE_FAILED' $Fact $Handle.IssuerSerial}
        }
        function New-R2ProcessDuplicate($Context,$Source,$Target,[uint32]$Rights,[bool]$Inherit,[bool]$Local,[uint32]$Options=0) {
            $r=Get-R2ProcessOwnerState $Context
            $h=New-R2ProcessHandle $Context $Source.Kind
            Set-R2DuplicateHandleBinding $Context $h $Source $r.Current $Target $Rights $Inherit $Local
            $out=New-R2ProcessBuffer $Context 8
            $f=Invoke-R2ProcessNative $Context ([R2ApiId]::DuplicateHandle) @($r.Current,$Source,$Target,$out,[uint32]$Rights,[int]$Inherit,[uint32]$Options)
            Assert-R2ProcessHandle $Context $h $f
            Release-R2NativeBuffer $Context $out
            return ,$h
        }
        function Get-R2ActualProcessorCount($Context) {
            $g=Invoke-R2ProcessNative $Context ([R2ApiId]::GetActiveProcessorGroupCount) @()
            if($g.RawStatus -ne 1){Stop-R2ProcessFault $Context 'R2_SINGLE_GROUP_REQUIRED' $g}
            $n=Invoke-R2ProcessNative $Context ([R2ApiId]::GetActiveProcessorCount) @([uint16]0)
            if($n.RawStatus -lt 1 -or $n.RawStatus -gt 64){Stop-R2ProcessFault $Context 'R2_PROCESSOR_COUNT' $n}
            $r=Get-R2ProcessOwnerState $Context
            if($null -ne $r.N -and $r.N -ne $n.RawStatus){Stop-R2ProcessFault $Context 'R2_PROCESSOR_COUNT_CHANGED' $n}
            if($null -eq $r.N){Retain-R2NativeFact $Context $g;Retain-R2NativeFact $Context $n;$r.Facts.Add($g);$r.Facts.Add($n)}
            return [uint32]$n.RawStatus
        }
        function Assert-R2RoleJobLimits($Context,$Job,[bool]$Prep) {
            $r=Get-R2ProcessOwnerState $Context
            if($null -eq $r.JobQueryPool){$r.JobQueryPool=[pscustomobject]@{Limits=(New-R2ProcessBuffer $Context 144);Cpu=(New-R2ProcessBuffer $Context 8);Length=(New-R2ProcessBuffer $Context 4);Released=$false}}
            if($r.JobQueryPool.Released){Stop-R2ProcessFault $Context 'R2_JOB_QUERY_POOL_CONSUMED'}
            $b=$r.JobQueryPool.Limits;$len=$r.JobQueryPool.Length
            $f=Invoke-R2ProcessNative $Context ([R2ApiId]::QueryInformationJobObject) @($Job,[int]9,$b,[uint32]144,$len)
            Assert-R2ProcessBool $Context $f 'R2_JOB_LIMIT_QUERY'
            $flags=if($Prep){[uint32]0x2200}else{[uint32]0x2A08}
            $memory=if($Prep){[uint64]4294967296}else{[uint64]536870912}
            if((Get-R2ProcessU32 $Context $len 0) -ne 144 -or (Get-R2ProcessU32 $Context $b 16) -ne $flags -or (Get-R2ProcessU64 $Context $b 120) -ne $memory -or (Get-R2ProcessU32 $Context $b 40) -ne $(if($Prep){0}else{4})){Stop-R2ProcessFault $Context 'R2_JOB_LIMIT_READBACK' $f}
            if($r.JobReadbackPending){Retain-R2NativeFact $Context $f;$r.Facts.Add($f)}
            $b=$r.JobQueryPool.Cpu
            $f=Invoke-R2ProcessNative $Context ([R2ApiId]::QueryInformationJobObject) @($Job,[int]15,$b,[uint32]8,$len)
            Assert-R2ProcessBool $Context $f 'R2_JOB_CPU_QUERY'
            $rate=[uint32][Math]::Floor(($(if($Prep){20000.0}else{10000.0}))/$r.N)
            if((Get-R2ProcessU32 $Context $len 0) -ne 8 -or (Get-R2ProcessU32 $Context $b 0) -ne 5 -or (Get-R2ProcessU32 $Context $b 4) -ne $rate){Stop-R2ProcessFault $Context 'R2_JOB_CPU_READBACK' $f}
            if($r.JobReadbackPending){Retain-R2NativeFact $Context $f;$r.Facts.Add($f)}
        }
        function New-R2RoleJobs($Context) {
            Assert-R2ProcessLive $Context
            if($null -ne $script:bootstrap -and [object]::ReferenceEquals($script:bootstrap.Context,$Context)){throw 'R2_CHILD_ENDPOINT_CANNOT_ISSUE_JOBS'}
            $r=Get-R2ProcessOwnerState $Context
            if($r.JobStage -eq 4){return 'CONFIGURED'}
            if(-not $r.JobsAttempted){$r.JobsAttempted=$true;$r.N=Get-R2ActualProcessorCount $Context}
            if($r.JobReadbackPending){$prep=($r.JobStage -eq 1);$job=if($prep){$r.Prep}else{$r.External};Assert-R2RoleJobLimits $Context $job $prep;$r.JobReadbackPending=$false;$r.JobStage++;return 'PENDING'}
            if($r.JobStage -lt 2){
                $prep=($r.JobStage -eq 1)
                $rate=[uint32][Math]::Floor(($(if($prep){20000.0}else{10000.0}))/$r.N)
                if($rate -lt 1 -or $rate -gt 10000){Stop-R2ProcessFault $Context 'R2_JOB_CPU_RATE_INVALID'}
                $job=New-R2ProcessHandle $Context ([R2HandleKind]::JOB)
                $f=Invoke-R2ProcessNative $Context ([R2ApiId]::CreateJobObjectW) @([IntPtr]::Zero,$null)
                Assert-R2ProcessHandle $Context $job $f
                if($prep){$r.Prep=$job}else{$r.External=$job}
                $b=New-R2ProcessBuffer $Context 144
                Set-R2ProcessU32 $Context $b 16 $(if($prep){[uint32]0x2200}else{[uint32]0x2A08})
                Set-R2ProcessU32 $Context $b 40 $(if($prep){[uint32]0}else{[uint32]4})
                Set-R2ProcessU64 $Context $b 120 $(if($prep){[uint64]4294967296}else{[uint64]536870912})
                $f=Invoke-R2ProcessNative $Context ([R2ApiId]::SetInformationJobObject) @($job,[int]9,$b,[uint32]144)
                Assert-R2ProcessBool $Context $f 'R2_JOB_LIMIT_SET';Release-R2NativeBuffer $Context $b
                $b=New-R2ProcessBuffer $Context 8;Set-R2ProcessU32 $Context $b 0 5;Set-R2ProcessU32 $Context $b 4 $rate
                $f=Invoke-R2ProcessNative $Context ([R2ApiId]::SetInformationJobObject) @($job,[int]15,$b,[uint32]8)
                Assert-R2ProcessBool $Context $f 'R2_JOB_CPU_SET';Release-R2NativeBuffer $Context $b
                $r.JobReadbackPending=$true;return 'PENDING'
            }
            if($r.JobStage -eq 2){
            $r.Current=New-R2ProcessHandle $Context ([R2HandleKind]::PROCESS) ([R2HandleOwnership]::BORROWED)
            $f=Invoke-R2ProcessNative $Context ([R2ApiId]::GetCurrentProcess) @();Assert-R2ProcessHandle $Context $r.Current $f
            $f=Invoke-R2ProcessNative $Context ([R2ApiId]::AssignProcessToJobObject) @($r.External,$r.Current)
            Assert-R2ProcessBool $Context $f 'R2_ROOT_JOB_ASSIGN'
            $membership=New-R2ProcessBuffer $Context 4
            foreach($binding in @(@($r.External,$true),@($r.Prep,$false))){
                $f=Invoke-R2ProcessNative $Context ([R2ApiId]::IsProcessInJob) @($r.Current,$binding[0],$membership);Assert-R2ProcessBool $Context $f 'R2_ROOT_MEMBERSHIP_QUERY'
                if(((Get-R2ProcessU32 $Context $membership 0) -ne 0) -ne $binding[1]){Stop-R2ProcessFault $Context 'R2_ROOT_MEMBERSHIP' $f}
            }
            Release-R2NativeBuffer $Context $membership
            $r.JobStage=3;return 'PENDING'
            }
            $r.Root=New-R2ProcessDuplicate $Context $r.Current $r.Current ([uint32]0x101001) $false $true
            $r.StopEvent=New-R2ProcessHandle $Context ([R2HandleKind]::EVENT)
            $sa=New-R2ProcessBuffer $Context 24;Set-R2ProcessU32 $Context $sa 0 24
            $f=Invoke-R2ProcessNative $Context ([R2ApiId]::CreateEventW) @($sa,[int]1,[int]0,$null)
            Assert-R2ProcessHandle $Context $r.StopEvent $f;Release-R2NativeBuffer $Context $sa
            Register-R2RoleJobs $Context $r.External $r.Prep
            $r.JobStage=4
            $r.RootPid=Get-R2RootPidCached $Context
            return 'CONFIGURED'
        }

        function Get-R2PlanChildRole($Context,$Slot) {
            Assert-R2PlanSlot $Context $Slot
            if($Slot.ContainsKey('ChildRole')){
                if(-not ($Slot.ChildRole -is [R2Role]) -or $Slot.ChildRole -eq [R2Role]::ROOT -or -not [Enum]::IsDefined([R2Role],$Slot.ChildRole)){Stop-R2ProcessFault $Context 'R2_PLAN_CHILD_ROLE'}
                return $Slot.ChildRole
            }
            switch -CaseSensitive([string]$Slot.ProducerName){
                'CONTROLLER' {return [R2Role]::CONTROLLER}
                'WATCHDOG' {return [R2Role]::WATCHDOG}
                'TRANSPORT' {return [R2Role]::TRANSPORT}
                default {return [R2Role]::PREP}
            }
        }
        function New-R2ChildReservation($Context,$PlanSlot) {
            Assert-R2ProcessLive $Context;Assert-R2PlanSlot $Context $PlanSlot
            $r=Get-R2ProcessOwnerState $Context
            foreach($c in $r.Children){if([object]::ReferenceEquals($c.Data.OriginalSlotReference,$PlanSlot) -and $c.Data.State -eq [R2ChildState]::RESERVED){Stop-R2ProcessFault $Context 'R2_CHILD_RESERVATION_DUPLICATE'}}
            $facts=[Collections.Generic.List[object]]::new();$identities=[Collections.Generic.List[object]]::new()
            $e=New-R2ProcessRecord $Context $PlanSlot 'Child' @{OriginalPiProcess=$null;OriginalPiThread=$null;OriginalPid=$null;OriginalTid=$null;ProcessCreationFileTime=$null;ThreadCreationFileTime=$null;Role=(Get-R2PlanChildRole $Context $PlanSlot);PrepMembership=[R2Fact]::UNKNOWN;ExternalMembership=[R2Fact]::UNKNOWN;BirthFact=$null;IdentityFacts=$identities.AsReadOnly();State=[R2ChildState]::RESERVED;SuspendedObserved=[R2Fact]::UNKNOWN;ResumeFact=$null;TerminateFact=$null;JoinFact=$null;ExitCode=$null;ExitObservedQpc=$null;StdoutEof=[R2Fact]::UNKNOWN;StderrEof=[R2Fact]::UNKNOWN;NativeFacts=$facts.AsReadOnly()}
            $e.Private['Facts']=$facts;$e.Private['IdentityFacts']=$identities;$e.Private['Peer']=$null;$e.Private['BirthAttempted']=$false;$e.Private['BirthStage']=0;$e.Private['ConfirmStage']=0;$e.Private['ResumeAttempted']=$false;$e.Private['ResumeStage']=0;$e.Private['ResumeCheckQpc']=$null;$e.Private['TerminateAttempted']=$false;$e.Private['Threads']=$null;$e.Private['ExitCodeAttempted']=$false;$e.Private['CleanupComplete']=$false;$e.Private['CleanupUnknown']=$false
            $r.Children.Add($e)
            return ,$e.View
        }
        function ConvertTo-R2QuotedArgument($Context,[string]$Value) {
            Assert-R2Utf16 $Context $Value 32766
            if($Value.Length -gt 0 -and $Value -notmatch '[\s"]'){return $Value}
            $s=[Text.StringBuilder]::new();$null=$s.Append('"');$slashes=0
            foreach($ch in $Value.ToCharArray()){
                if($ch -eq [char]92){$slashes++;continue}
                if($ch -eq [char]34){$null=$s.Append([char]92,2*$slashes+1);$null=$s.Append($ch);$slashes=0;continue}
                if($slashes){$null=$s.Append([char]92,$slashes);$slashes=0};$null=$s.Append($ch)
            }
            if($slashes){$null=$s.Append([char]92,2*$slashes)};$null=$s.Append('"')
            return $s.ToString()
        }
        function Assert-R2Utf16($Context,[string]$Value,[int]$Limit) {
            if($null -eq $Value -or $Value.Length -gt $Limit -or $Value.IndexOf([char]0) -ge 0){Stop-R2ProcessFault $Context 'R2_UTF16_BOUNDS'}
            for($i=0;$i -lt $Value.Length;$i++){
                if([char]::IsHighSurrogate($Value[$i])){if($i+1 -ge $Value.Length -or -not [char]::IsLowSurrogate($Value[$i+1])){Stop-R2ProcessFault $Context 'R2_UTF16_SURROGATE'};$i++}
                elseif([char]::IsLowSurrogate($Value[$i])){Stop-R2ProcessFault $Context 'R2_UTF16_SURROGATE'}
            }
        }
        function New-R2LaunchBuffers($Context,$Child) {
            $c=Get-R2ProcessRecord $Context $Child 'Child';$slot=$c.Data.OriginalSlotReference
            Assert-R2Utf16 $Context $slot.ApplicationLiteral 32766;Assert-R2Utf16 $Context $slot.CwdLiteral 32766
            if($slot.ApplicationLiteral -notmatch '^(?:[A-Za-z]:[\\/]|\\\\[^\\/]+[\\/][^\\/]+[\\/])' -or $slot.CwdLiteral -notmatch '^(?:[A-Za-z]:[\\/]|\\\\[^\\/]+[\\/][^\\/]+[\\/])'){Stop-R2ProcessFault $Context 'R2_LAUNCH_ABSOLUTE_PATH'}
            $argv=@($slot.Argv);if($argv.Count -eq 0 -or $argv.Count -gt 128 -or $argv[0] -cne $slot.ApplicationLiteral){Stop-R2ProcessFault $Context 'R2_LAUNCH_ARGV0'}
            if([IO.Path]::GetFileName($slot.ApplicationLiteral).Equals('powershell.exe',[StringComparison]::OrdinalIgnoreCase)){
                if($argv -notcontains '-NoProfile' -or $argv -notcontains '-File'){Stop-R2ProcessFault $Context 'R2_POWERSHELL_FIXED_FILE_PROFILE'}
                foreach($argument in $argv){if($argument -match '^-(?:c|command|e|ec|enc|encodedcommand)$'){Stop-R2ProcessFault $Context 'R2_POWERSHELL_COMMAND_MODE'}}
            }
            $peer=$c.Private.Peer;$replacementCount=0;$parts=[Collections.Generic.List[string]]::new();$argIndex=0;$commandLength=0
            if($null -ne $peer -and (-not $slot.ContainsKey('BootstrapArgumentIndex') -or -not ($slot.BootstrapArgumentIndex -is [uint32]) -or $slot.BootstrapArgumentIndex -ge $argv.Count -or $argv[$slot.BootstrapArgumentIndex] -cne '{R2_INHERITED_READER}')){Stop-R2ProcessFault $Context 'R2_LAUNCH_LOCATOR_BINDING'}
            foreach($arg in $argv){
                if(-not ($arg -is [string])){Stop-R2ProcessFault $Context 'R2_LAUNCH_ARGV_TYPE'}
                if($arg -ceq '{R2_INHERITED_READER}'){
                    if($null -eq $peer -or $argIndex -ne $slot.BootstrapArgumentIndex){Stop-R2ProcessFault $Context 'R2_LAUNCH_UNPLANNED_LOCATOR'}
                    $arg=(Get-R2HandleValue $Context $peer.Private.InheritedReader).ToInt64().ToString([Globalization.CultureInfo]::InvariantCulture);$replacementCount++
                }elseif($arg.Contains('{R2_INHERITED_READER}')){Stop-R2ProcessFault $Context 'R2_LAUNCH_LOCATOR_TEMPLATE'}
                $quoted=ConvertTo-R2QuotedArgument $Context $arg;$commandLength+=$quoted.Length+$(if($argIndex -eq 0){0}else{1})
                if($commandLength -gt 32766){Stop-R2ProcessFault $Context 'R2_COMMAND_LINE_CAPACITY'}
                $parts.Add($quoted)
                $argIndex++
            }
            if($null -ne $peer -and $replacementCount -ne 1){Stop-R2ProcessFault $Context 'R2_LAUNCH_LOCATOR_COUNT'}
            $line=[string]::Join(' ',$parts.ToArray());Assert-R2Utf16 $Context $line 32766
            $lineBytes=[Text.Encoding]::Unicode.GetBytes($line+[char]0)
            $cmd=New-R2ProcessBuffer $Context ([uint32]$lineBytes.Length);Write-R2NativeBuffer $Context $cmd 0 $lineBytes
            $env=[Collections.Generic.SortedDictionary[string,string]]::new([StringComparer]::OrdinalIgnoreCase)
            foreach($pair in $slot.EnvironmentPairs){
                $key=$pair.Name;$value=$pair.Value
                if(-not ($key -is [string]) -or -not ($value -is [string]) -or $key.Length -eq 0 -or $key.Contains('=') -or $key -in @('CL','_CL_','LINK') -or $env.ContainsKey($key)){Stop-R2ProcessFault $Context 'R2_LAUNCH_ENVIRONMENT'}
                Assert-R2Utf16 $Context $key 32766;Assert-R2Utf16 $Context $value 32766;$env.Add($key,$value)
            }
            $s=[Text.StringBuilder]::new();foreach($pair in $env.GetEnumerator()){if([bigint]$s.Length+$pair.Key.Length+$pair.Value.Length+3 -gt 32767){Stop-R2ProcessFault $Context 'R2_ENVIRONMENT_CAPACITY'};$null=$s.Append($pair.Key+'='+$pair.Value+[char]0)}
            $null=$s.Append([char]0);if($env.Count -eq 0){$null=$s.Append([char]0)}
            if($s.Length -gt 32767){Stop-R2ProcessFault $Context 'R2_ENVIRONMENT_CAPACITY'}
            $bytes=[Text.Encoding]::Unicode.GetBytes($s.ToString());$eb=New-R2ProcessBuffer $Context ([uint32]$bytes.Length);Write-R2NativeBuffer $Context $eb 0 $bytes
            return [pscustomobject]@{Command=$cmd;Environment=$eb}
        }
        function New-R2SuspendedChild($Context,$PlanSlot) {
            Assert-R2ProcessLive $Context;Assert-R2PlanSlot $Context $PlanSlot
            $r=Get-R2ProcessOwnerState $Context
            if($r.JobStage -ne 4 -or $null -eq $r.Prep -or $null -eq $r.External){Stop-R2ProcessFault $Context 'R2_JOBS_REQUIRED'}
            $child=$null;foreach($e in $r.Children){if([object]::ReferenceEquals($e.Data.OriginalSlotReference,$PlanSlot) -and $e.Data.State -eq [R2ChildState]::RESERVED){$child=$e.View;break}}
            if($null -eq $child){
                foreach($existing in $r.Children){if([object]::ReferenceEquals($existing.Data.OriginalSlotReference,$PlanSlot) -and $existing.Data.State -ne [R2ChildState]::RESERVED){$child=$existing.View;break}}
            }
            if($null -eq $child){return ,(New-R2ChildReservation $Context $PlanSlot)}
            $c=Get-R2ProcessRecord $Context $child 'Child'
            if($c.Data.State -eq [R2ChildState]::BORN_SUSPENDED){
                if($c.Private.ContainsKey('BirthBuffers')){
                    $c.Private['AttributeDeleteAttempted']=$true
                    $null=Invoke-R2ProcessNative $Context ([R2ApiId]::DeleteProcThreadAttributeList) @($c.Private.AttributeList)
                    foreach($buffer in $c.Private.BirthBuffers){if($null -ne $buffer){Release-R2NativeBuffer $Context $buffer}}
                    $c.Private.Remove('BirthBuffers') | Out-Null;return ,$child
                }
                Confirm-R2Birth $Context $child;return ,$child
            }
            if($c.Data.State -eq [R2ChildState]::BIRTH_CONFIRMED){if($null -ne $c.Private.Peer -and -not $c.Private.Peer.Private.BootstrapWritten){Complete-R2PeerBootstrapWrite $Context $c.Private.Peer.View};return ,$child}
            if($c.Data.State -ne [R2ChildState]::RESERVED){return ,$child}
            if($c.Data.Role -ne [R2Role]::PREP -and ($null -eq $c.Private.Peer -or $c.Private.Peer.Private.SetupStage -lt 4)){$null=New-R2Peer $Context $child;return ,$child}
            if($c.Private.BirthAttempted){Stop-R2ProcessFault $Context 'R2_BIRTH_RETRY'};$c.Private.BirthAttempted=$true
            Add-R2BirthAttempt $Context
            $launch=New-R2LaunchBuffers $Context $child
            $count=[uint32]$(if($null -ne $c.Private.Peer){2}else{1});$size=New-R2ProcessBuffer $Context 8
            $f=Invoke-R2ProcessNative $Context ([R2ApiId]::InitializeProcThreadAttributeList) @([IntPtr]::Zero,$count,[uint32]0,$size)
            $needed=Get-R2ProcessU64 $Context $size 0
            if($f.RawStatus -ne 0 -or $f.StatusBits -ne 122 -or $needed -lt 24 -or $needed -gt 65536){Stop-R2ProcessFault $Context 'R2_ATTRIBUTE_SIZING' $f}
            $attrs=New-R2ProcessBuffer $Context ([uint32]$needed)
            $f=Invoke-R2ProcessNative $Context ([R2ApiId]::InitializeProcThreadAttributeList) @($attrs,$count,[uint32]0,$size);Assert-R2ProcessBool $Context $f 'R2_ATTRIBUTE_INITIALIZE'
            $c.Private['AttributeList']=$attrs;$c.Private['AttributeInitializeFact']=Get-R2ProcessFactSummary $f;$c.Private['AttributeDeleteAttempted']=$false
            $jobList=New-R2ProcessBuffer $Context 8;$job=if($c.Data.Role -eq [R2Role]::PREP){$r.Prep}else{$r.External}
            Write-R2NativeReference $Context $jobList 0 $job
            $f=Invoke-R2ProcessNative $Context ([R2ApiId]::UpdateProcThreadAttribute) @($attrs,[uint32]0,[uint64]0x2000D,$jobList,[uint64]8,[IntPtr]::Zero,[IntPtr]::Zero);Assert-R2ProcessBool $Context $f 'R2_ATTRIBUTE_JOB'
            $handleList=$null
            if($null -ne $c.Private.Peer){
                $handleList=New-R2ProcessBuffer $Context 8;Write-R2NativeReference $Context $handleList 0 $c.Private.Peer.Private.InheritedReader
                $f=Invoke-R2ProcessNative $Context ([R2ApiId]::UpdateProcThreadAttribute) @($attrs,[uint32]0,[uint64]0x20002,$handleList,[uint64]8,[IntPtr]::Zero,[IntPtr]::Zero);Assert-R2ProcessBool $Context $f 'R2_ATTRIBUTE_HANDLES'
            }
            $si=New-R2ProcessBuffer $Context 112;Set-R2ProcessU32 $Context $si 0 112;Write-R2NativeReference $Context $si 104 $attrs
            $pi=New-R2ProcessBuffer $Context 24
            $c.Data['OriginalPiProcess']=New-R2ProcessHandle $Context ([R2HandleKind]::PROCESS)
            $c.Data['OriginalPiThread']=New-R2ProcessHandle $Context ([R2HandleKind]::THREAD)
            $flags=[uint32]0x80404;if($c.Data.Role -eq [R2Role]::PREP){$flags=$flags -bor [uint32]0x1000000}
            $inherit=[int]$(if($null -ne $c.Private.Peer){1}else{0})
            $f=Invoke-R2ProcessNative $Context ([R2ApiId]::CreateProcessW) @($PlanSlot.ApplicationLiteral,$launch.Command,[IntPtr]::Zero,[IntPtr]::Zero,$inherit,$flags,$launch.Environment,$PlanSlot.CwdLiteral,$si,$pi)
            Retain-R2NativeFact $Context $f;$c.Data['BirthFact']=$f;$c.Private.Facts.Add($f)
            # The ledger retains all actual PI outputs before any timing/status fault.
            Assert-R2ProcessBool $Context $f 'R2_CREATE_PROCESS';Assert-R2ProcessHandle $Context $c.Data.OriginalPiProcess $f;Assert-R2ProcessHandle $Context $c.Data.OriginalPiThread $f
            $c.Data['OriginalPid']=Get-R2ProcessU32 $Context $pi 16;$c.Data['OriginalTid']=Get-R2ProcessU32 $Context $pi 20
            $c.Data['State']=[R2ChildState]::BORN_SUSPENDED
            $c.Private['AttributeList']=$attrs;$c.Private['BirthBuffers']=@($size,$attrs,$jobList,$handleList,$si,$pi,$launch.Command,$launch.Environment)
            return ,$child
        }
        function Get-R2ProcessCreation($Context,$Handle,[bool]$Thread=$false) {
            $buffers=@();for($i=0;$i -lt 4;$i++){$buffers+=,(New-R2ProcessBuffer $Context 8)}
            $api=if($Thread){[R2ApiId]::GetThreadTimes}else{[R2ApiId]::GetProcessTimes}
            $f=Invoke-R2ProcessNative $Context $api @($Handle,$buffers[0],$buffers[1],$buffers[2],$buffers[3]);Assert-R2ProcessBool $Context $f 'R2_CREATION_TIME'
            $time=Get-R2ProcessU64 $Context $buffers[0] 0
            if($time -eq 0){Stop-R2ProcessFault $Context 'R2_CREATION_TIME_ZERO' $f}
            Retain-R2NativeFact $Context $f
            foreach($b in $buffers){Release-R2NativeBuffer $Context $b}
            return [pscustomobject]@{Value=$time;Fact=$f}
        }
        function Confirm-R2Birth($Context,$Child) {
            Assert-R2ProcessLive $Context;$c=Get-R2ProcessRecord $Context $Child 'Child';$r=Get-R2ProcessOwnerState $Context
            if($c.Data.State -ne [R2ChildState]::BORN_SUSPENDED){Stop-R2ProcessFault $Context 'R2_BIRTH_CONFIRM_STATE'}
            if($c.Private.ConfirmStage -eq 0){
              foreach($binding in @(@([R2ApiId]::GetProcessId,$c.Data.OriginalPiProcess,$c.Data.OriginalPid),@([R2ApiId]::GetThreadId,$c.Data.OriginalPiThread,$c.Data.OriginalTid),@([R2ApiId]::GetProcessIdOfThread,$c.Data.OriginalPiThread,$c.Data.OriginalPid))){
                $f=Invoke-R2ProcessNative $Context $binding[0] @($binding[1]);Retain-R2NativeFact $Context $f;$c.Private.IdentityFacts.Add($f)
                if($f.RawStatus -eq 0 -or $f.RawStatus -ne $binding[2]){Stop-R2ProcessFault $Context 'R2_ORIGINAL_PI_IDENTITY' $f}
            }
              $c.Private.ConfirmStage=1;return
            }
            if($c.Private.ConfirmStage -eq 1){$p=Get-R2ProcessCreation $Context $c.Data.OriginalPiProcess;$c.Data['ProcessCreationFileTime']=$p.Value;$c.Private.IdentityFacts.Add($p.Fact);$c.Private.ConfirmStage=2;return}
            if($c.Private.ConfirmStage -eq 2){$t=Get-R2ProcessCreation $Context $c.Data.OriginalPiThread $true;if($t.Value -lt $c.Data.ProcessCreationFileTime){Stop-R2ProcessFault $Context 'R2_THREAD_CREATION_ORDER' $t.Fact};$c.Data['ThreadCreationFileTime']=$t.Value;$c.Private.IdentityFacts.Add($t.Fact);$c.Private.ConfirmStage=3;return}
            if($c.Private.ConfirmStage -lt 5){
            $out=New-R2ProcessBuffer $Context 4
            $prep=($c.Private.ConfirmStage -eq 3)
                $job=if($prep){$r.Prep}else{$r.External};$f=Invoke-R2ProcessNative $Context ([R2ApiId]::IsProcessInJob) @($c.Data.OriginalPiProcess,$job,$out);Assert-R2ProcessBool $Context $f 'R2_BIRTH_MEMBERSHIP_QUERY'
                $member=(Get-R2ProcessU32 $Context $out 0) -ne 0;$expected=if($prep){$c.Data.Role -eq [R2Role]::PREP}else{$c.Data.Role -ne [R2Role]::PREP}
                $name=if($prep){'PrepMembership'}else{'ExternalMembership'};$c.Data[$name]=$(if($member){[R2Fact]::TRUE}else{[R2Fact]::FALSE});Retain-R2NativeFact $Context $f;$c.Private.IdentityFacts.Add($f)
                if($member -ne $expected){Stop-R2ProcessFault $Context 'R2_BIRTH_MEMBERSHIP' $f}
                Assert-R2RoleJobLimits $Context $job $prep
            Release-R2NativeBuffer $Context $out;$c.Private.ConfirmStage++;return
            }
            $null=Get-R2ActualProcessorCount $Context
            $f=Invoke-R2ProcessNative $Context ([R2ApiId]::WaitForSingleObject) @($c.Data.OriginalPiProcess,[uint32]0)
            if($f.RawStatus -ne 258){Stop-R2ProcessFault $Context 'R2_SUSPENDED_CHILD_NOT_LIVE' $f}
            $c.Data['SuspendedObserved']=[R2Fact]::TRUE;$c.Data['State']=[R2ChildState]::BIRTH_CONFIRMED
        }
        function Resume-R2OwnedChild($Context,$Child) {
            Assert-R2ProcessLive $Context;$c=Get-R2ProcessRecord $Context $Child 'Child'
            if($c.Data.State -ne [R2ChildState]::BIRTH_CONFIRMED -or $c.Private.ResumeAttempted){Stop-R2ProcessFault $Context 'R2_RESUME_STATE'}
            if($null -ne $c.Private.Peer -and -not $c.Private.Peer.Private.BootstrapWritten){Stop-R2ProcessFault $Context 'R2_BOOTSTRAP_BEFORE_RESUME'}
            $null=Get-R2ActualProcessorCount $Context
            $r=Get-R2ProcessOwnerState $Context;$out=New-R2ProcessBuffer $Context 4
            if($c.Private.ResumeStage -eq 0){
                Assert-R2RoleJobLimits $Context $r.Prep $true
                $f=Invoke-R2ProcessNative $Context ([R2ApiId]::IsProcessInJob) @($c.Data.OriginalPiProcess,$r.Prep,$out);Assert-R2ProcessBool $Context $f 'R2_RESUME_PREP_MEMBERSHIP_QUERY'
                if(((Get-R2ProcessU32 $Context $out 0) -ne 0) -ne ($c.Data.Role -eq [R2Role]::PREP)){Stop-R2ProcessFault $Context 'R2_RESUME_PREP_MEMBERSHIP' $f}
                Release-R2NativeBuffer $Context $out;$c.Private.ResumeCheckQpc=Get-R2LedgerTimestamp $Context;$c.Private.ResumeStage=1;return 'PENDING'
            }
            Assert-R2RoleJobLimits $Context $r.External $false
            foreach($prep in @($true,$false)){
                $job=if($prep){$r.Prep}else{$r.External};$expected=if($prep){$c.Data.Role -eq [R2Role]::PREP}else{$c.Data.Role -ne [R2Role]::PREP}
                $f=Invoke-R2ProcessNative $Context ([R2ApiId]::IsProcessInJob) @($c.Data.OriginalPiProcess,$job,$out);Assert-R2ProcessBool $Context $f 'R2_RESUME_MEMBERSHIP_QUERY'
                if(((Get-R2ProcessU32 $Context $out 0) -ne 0) -ne $expected){Stop-R2ProcessFault $Context 'R2_RESUME_MEMBERSHIP' $f}
            }
            Release-R2NativeBuffer $Context $out
            $resumeQpc=Get-R2LedgerTimestamp $Context
            if($resumeQpc -lt $c.Private.ResumeCheckQpc -or ([bigint]$resumeQpc-$c.Private.ResumeCheckQpc)*10 -gt $Context.Frequency){Stop-R2ProcessFault $Context 'R2_RESUME_PRECHECK_STALE'}
            $c.Private.ResumeAttempted=$true;$c.Data['State']=[R2ChildState]::RESUME_REQUESTED
            $f=Invoke-R2ProcessNative $Context ([R2ApiId]::ResumeThread) @($c.Data.OriginalPiThread);Retain-R2NativeFact $Context $f;$c.Data['ResumeFact']=$f;$c.Private.Facts.Add($f)
            if($f.RawStatus -ne 1){Stop-R2ProcessFault $Context 'R2_RESUME_SUSPEND_COUNT' $f}
            # A successful ResumeThread is a request; RUNNING_OBSERVED remains absent.
        }

        function Get-R2CurrentSidSecurity($Context) {
            $r=Get-R2ProcessOwnerState $Context
            $token=New-R2ProcessHandle $Context ([R2HandleKind]::TOKEN);$out=New-R2ProcessBuffer $Context 8
            $f=Invoke-R2ProcessNative $Context ([R2ApiId]::OpenProcessToken) @($r.Current,[uint32]8,$out);Assert-R2ProcessHandle $Context $token $f
            $len=New-R2ProcessBuffer $Context 4
            $f=Invoke-R2ProcessNative $Context ([R2ApiId]::GetTokenInformation) @($token,[int]1,[IntPtr]::Zero,[uint32]0,$len)
            $needed=Get-R2ProcessU32 $Context $len 0
            if($f.RawStatus -ne 0 -or $f.StatusBits -ne 122 -or $needed -lt 16 -or $needed -gt 4096){Stop-R2ProcessFault $Context 'R2_TOKEN_USER_SIZING' $f}
            $user=New-R2ProcessBuffer $Context $needed
            $f=Invoke-R2ProcessNative $Context ([R2ApiId]::GetTokenInformation) @($token,[int]1,$user,$needed,$len);Assert-R2ProcessBool $Context $f 'R2_TOKEN_USER_READ'
            $returned=Get-R2ProcessU32 $Context $len 0
            if($returned -lt 16 -or $returned -gt $needed){Stop-R2ProcessFault $Context 'R2_TOKEN_USER_LENGTH' $f}
            $base=[uint64](Get-R2NativeBufferPointer $Context $user 0).ToInt64();$sid=Get-R2ProcessU64 $Context $user 0
            if([bigint]$sid -lt $base -or [bigint]$sid+8 -gt [bigint]$base+$returned){Stop-R2ProcessFault $Context 'R2_TOKEN_SID_RANGE' $f}
            $offset=[uint32]($sid-$base);$head=[byte[]](Read-R2NativeBuffer $Context $user $offset 8)
            $sidLength=[uint32](8+4*$head[1])
            if($head[0] -ne 1 -or $head[1] -gt 15 -or [bigint]$offset+$sidLength -gt $returned){Stop-R2ProcessFault $Context 'R2_TOKEN_SID_FORMAT' $f}
            $sidBytes=[byte[]](Read-R2NativeBuffer $Context $user $offset $sidLength)
            $sidRef=Get-R2NativeBufferSlice $Context $user $offset $sidLength
            $stringAllocation=New-R2ProcessHandle $Context ([R2HandleKind]::LOCAL_ALLOCATION)
            $f=Invoke-R2ProcessNative $Context ([R2ApiId]::ConvertSidToStringSidW) @($sidRef,$out);Assert-R2ProcessHandle $Context $stringAllocation $f
            $nativeString=[byte[]]::new(512);$end=-1
            for($i=0;$i -lt 256;$i++){$pair=[byte[]](Read-R2LocalAllocation $Context $stringAllocation ([uint32](2*$i)) 2 512);$nativeString[2*$i]=$pair[0];$nativeString[2*$i+1]=$pair[1];if($pair[0] -eq 0 -and $pair[1] -eq 0){$end=$i;break}}
            if($end -lt 1){Stop-R2ProcessFault $Context 'R2_SID_STRING_UNTERMINATED' $f}
            $sidString=[Text.Encoding]::Unicode.GetString($nativeString,0,2*$end)
            if($sidString -cnotmatch '^S-1-[0-9]+(?:-[0-9]+){1,15}$'){Stop-R2ProcessFault $Context 'R2_SID_STRING_INVALID' $f}
            $descriptor=New-R2ProcessHandle $Context ([R2HandleKind]::LOCAL_ALLOCATION)
            $f=Invoke-R2ProcessNative $Context ([R2ApiId]::ConvertStringSecurityDescriptorToSecurityDescriptorW) @('D:P(A;;GA;;;'+$sidString+')',[uint32]1,$out,$len);Assert-R2ProcessHandle $Context $descriptor $f
            $descriptorLength=Get-R2ProcessU32 $Context $len 0
            if($descriptorLength -lt 20 -or $descriptorLength -gt 4096){Stop-R2ProcessFault $Context 'R2_SECURITY_DESCRIPTOR_LENGTH' $f}
            $bytes=[byte[]](Read-R2LocalAllocation $Context $descriptor 0 $descriptorLength $descriptorLength)
            Assert-R2SidDescriptorBytes $Context $bytes $sidBytes
            # Native pointers never outlive their local allocation; copy the fully
            # checked self-relative descriptor to the registered fixed buffer.
            $sd=New-R2ProcessBuffer $Context $descriptorLength;Write-R2NativeBuffer $Context $sd 0 $bytes
            return [pscustomobject]@{Descriptor=$sd;SidBytes=[Array]::AsReadOnly($sidBytes);TemporaryHandles=@($descriptor,$stringAllocation,$token);TemporaryBuffers=@($out,$len,$user)}
        }
        function Assert-R2SidAt($Context,[byte[]]$Bytes,[uint32]$Offset,[uint32]$Limit) {
            if([bigint]$Offset+8 -gt $Limit -or $Limit -gt $Bytes.Length){Stop-R2ProcessFault $Context 'R2_DESCRIPTOR_SID_BOUNDS'}
            $n=[uint32](8+4*$Bytes[$Offset+1])
            if($Bytes[$Offset] -ne 1 -or $Bytes[$Offset+1] -gt 15 -or [bigint]$Offset+$n -gt $Limit){Stop-R2ProcessFault $Context 'R2_DESCRIPTOR_SID_FORMAT'}
            return $n
        }
        function Assert-R2SidDescriptorBytes($Context,[byte[]]$Bytes,[byte[]]$Sid) {
            if($Bytes.Length -lt 20 -or $Bytes[0] -ne 1 -or $Bytes[1] -ne 0){Stop-R2ProcessFault $Context 'R2_DESCRIPTOR_HEADER'}
            $control=[BitConverter]::ToUInt16($Bytes,2)
            if(($control -band 0x9004) -ne 0x9004 -or ($control -band 0x10) -ne 0 -or [BitConverter]::ToUInt32($Bytes,12) -ne 0){Stop-R2ProcessFault $Context 'R2_DESCRIPTOR_CONTROL'}
            foreach($i in @(4,8)){$o=[BitConverter]::ToUInt32($Bytes,$i);if($o -ne 0){$null=Assert-R2SidAt $Context $Bytes $o ([uint32]$Bytes.Length)}}
            $acl=[BitConverter]::ToUInt32($Bytes,16)
            if($acl -lt 20 -or [bigint]$acl+8 -gt $Bytes.Length){Stop-R2ProcessFault $Context 'R2_DACL_RANGE'}
            $size=[BitConverter]::ToUInt16($Bytes,[int]$acl+2);$aces=[BitConverter]::ToUInt16($Bytes,[int]$acl+4)
            if($Bytes[$acl] -ne 2 -or $aces -ne 1 -or $size -lt 16 -or [bigint]$acl+$size -gt $Bytes.Length){Stop-R2ProcessFault $Context 'R2_DACL_HEADER'}
            $ace=[int]$acl+8;$aceSize=[BitConverter]::ToUInt16($Bytes,$ace+2)
            if($Bytes[$ace] -ne 0 -or $Bytes[$ace+1] -ne 0 -or $aceSize -ne 8+$Sid.Length -or $size -ne 8+$aceSize -or [BitConverter]::ToUInt32($Bytes,$ace+4) -ne 0x10000000){Stop-R2ProcessFault $Context 'R2_DACL_ACE'}
            $n=Assert-R2SidAt $Context $Bytes ([uint32]($ace+8)) ([uint32]($acl+$size))
            if($n -ne $Sid.Length){Stop-R2ProcessFault $Context 'R2_DACL_SID_LENGTH'}
            for($i=0;$i -lt $Sid.Length;$i++){if($Bytes[$ace+8+$i] -ne $Sid[$i]){Stop-R2ProcessFault $Context 'R2_DACL_SID_MISMATCH'}}
        }
        function Assert-R2PeerReference($Context,$Peer) { $p=Get-R2ProcessRecord $Context $Peer 'Peer';if($p.Kind -cne 'Peer'){throw 'R2_ROOT_PEER_REQUIRED'} }
        function Assert-R2ChildReference($Context,$Child) { $null=Get-R2ProcessRecord $Context $Child 'Child' }
        function New-R2Peer($Context,$Child) {
            Assert-R2ProcessLive $Context;$c=Get-R2ProcessRecord $Context $Child 'Child';$r=Get-R2ProcessOwnerState $Context
            if($r.JobStage -ne 4 -or $null -eq $r.Root -or $null -eq $r.StopEvent){Stop-R2ProcessFault $Context 'R2_PEER_ORIGINAL_ROOT_REQUIRED'}
            if($c.Data.Role -notin @([R2Role]::CONTROLLER,[R2Role]::WATCHDOG,[R2Role]::TRANSPORT) -or $c.Data.State -ne [R2ChildState]::RESERVED){Stop-R2ProcessFault $Context 'R2_PEER_RESERVATION_STATE'}
            if($null -ne $c.Private.Peer){return ,(Continue-R2PeerSetup $Context $c.Private.Peer.View)}
            foreach($other in $r.Peers){if($other.Private.Role -eq $c.Data.Role){Stop-R2ProcessFault $Context 'R2_PEER_ROLE_DUPLICATE'}}
            $facts=[Collections.Generic.List[object]]::new();$dups=[Collections.Generic.List[object]]::new()
            $p=New-R2ProcessRecord $Context $c.Data.OriginalSlotReference 'Peer' @{OriginalChildReference=$Child;OriginalRootProcessReference=$r.Root;RootHandle=$null;ProcessHandle=$null;PrepJobHandle=$null;ExternalJobHandle=$null;StopEventHandle=$null;PipeHandle=$null;Duplicates=$dups.AsReadOnly();CurrentSidBytes=$null;ClientPid=$null;ClientProcessCreationFileTime=$null;ClientIdentityFact=$null;InvocationNonce=(Get-R2InvocationNonce $Context);TxSequence=[uint64]0;RxSequence=[uint64]0;PendingConnect=$null;PendingRead=$null;PendingWrite=$null;LastHeartbeatQpc=$null;HeartbeatDueQpc=$null;ReadyFact=$null;StopFact=$null;JoinFact=$null;PipeState=[R2PipeState]::RESERVED;State=[R2PeerState]::RESERVED;ConnectionCount=[uint32]0;NativeFacts=$facts.AsReadOnly()}
            $p.Private['Facts']=$facts;$p.Private['Duplicates']=$dups;$p.Private['Role']=$c.Data.Role;$p.Private['RootSide']=$true;$p.Private['BootstrapWritten']=$false;$p.Private['BootstrapAttempted']=$false;$p.Private['BootstrapStage']=0;$p.Private['WireSerial']=$p.Data.IssuerSerial;$p.Private['EchoSent']=$false;$p.Private['IncomingCount']=0;$p.Private['IncomingLength']=64;$p.Private['Incoming']=[byte[]]::new(4096);$p.Private['EofExpected']=$false;$p.Private['EofFact']=$null;$p.Private['NativeConnectionObserved']=[R2Fact]::UNKNOWN;$p.Private['DisconnectAttempted']=$false;$p.Private['CleanupReadStopped']=$false;$p.Private['CleanupUnknown']=$false;$p.Private['CleanupComplete']=$false;$p.Private['SetupStage']=0;$p.Private['Security']=$null
            $c.Private.Peer=$p;$r.Peers.Add($p);Register-R2PeerReference $Context $p.View
            $null=Reserve-R2BootstrapAllowance $Context $Child
            $nonce=[byte[]]$p.Data.InvocationNonce;$hex=([BitConverter]::ToString($nonce)).Replace('-','').ToLowerInvariant()
            $p.Private['PipeName']='\\.\pipe\r2-'+$hex+'-'+$p.Data.IssuerSerial.ToString([Globalization.CultureInfo]::InvariantCulture)
            Assert-R2Utf16 $Context $p.Private.PipeName 255
            return ,$p.View
        }
        function Continue-R2PeerSetup($Context,$Peer) {
            $p=Get-R2ProcessRecord $Context $Peer 'Peer';$r=Get-R2ProcessOwnerState $Context
            if($p.Private.SetupStage -eq 4){return ,$Peer}
            if($p.Private.SetupStage -eq 0){$p.Private.Security=Get-R2CurrentSidSecurity $Context;$p.Data['CurrentSidBytes']=$p.Private.Security.SidBytes;$p.Private.SetupStage=1;return ,$Peer}
            if($p.Private.SetupStage -eq 1){
                foreach($handle in $p.Private.Security.TemporaryHandles){$null=Consume-R2Handle $Context $handle}
                foreach($buffer in $p.Private.Security.TemporaryBuffers){Release-R2NativeBuffer $Context $buffer}
                $p.Private.SetupStage=2;return ,$Peer
            }
            if($p.Private.SetupStage -eq 2){
            $security=$p.Private.Security
            $sa=New-R2ProcessBuffer $Context 24;Set-R2ProcessU32 $Context $sa 0 24;Write-R2NativeReference $Context $sa 8 $security.Descriptor
            $p.Data['PipeHandle']=New-R2ProcessHandle $Context ([R2HandleKind]::PIPE)
            $f=Invoke-R2ProcessNative $Context ([R2ApiId]::CreateNamedPipeW) @($p.Private.PipeName,[uint32]0x40080003,[uint32]8,[uint32]1,[uint32]4096,[uint32]4096,[uint32]0,$sa)
            Assert-R2ProcessHandle $Context $p.Data.PipeHandle $f;$p.Private.Facts.Add($f);$p.Data['PipeState']=[R2PipeState]::CREATED
            $read=New-R2ProcessHandle $Context ([R2HandleKind]::PIPE);$write=New-R2ProcessHandle $Context ([R2HandleKind]::PIPE)
            $ro=New-R2ProcessBuffer $Context 8;$wo=New-R2ProcessBuffer $Context 8
            $f=Invoke-R2ProcessNative $Context ([R2ApiId]::CreatePipe) @($ro,$wo,$sa,[uint32]4096)
            Assert-R2ProcessHandle $Context $read $f;Assert-R2ProcessHandle $Context $write $f
            Release-R2NativeBuffer $Context $sa;Release-R2NativeBuffer $Context $security.Descriptor
            $p.Private['AnonymousReader']=$read;$p.Private['AnonymousWriter']=$write
            $p.Private['InheritedReader']=New-R2ProcessDuplicate $Context $read $r.Current ([uint32]0) $true $true ([uint32]2)
            Release-R2NativeBuffer $Context $ro;Release-R2NativeBuffer $Context $wo
            $p.Private.SetupStage=3;return ,$Peer
            }
            $io=New-R2PendingIo $Context $p.View ([R2IoOperation]::CONNECT)
            $null=Start-R2PeerIo $Context $io 0
            $p.Data['State']=[R2PeerState]::BOOTSTRAP_PENDING
            $p.Private.SetupStage=4
            return ,$p.View
        }
        function New-R2PendingIo($Context,$Peer,[R2IoOperation]$IoOperation) {
            $p=Get-R2ProcessRecord $Context $Peer 'Peer'
            if(-not [Enum]::IsDefined([R2IoOperation],$IoOperation)){Stop-R2ProcessFault $Context 'R2_IO_ENUM'}
            $key=switch($IoOperation){CONNECT{'PendingConnect'} READ{'PendingRead'} WRITE{'PendingWrite'}}
            if($null -ne $p.Data[$key]){Stop-R2ProcessFault $Context 'R2_IO_DIRECTION_OCCUPIED'}
            $i=New-R2ProcessRecord $Context $p.Data.OriginalSlotReference 'PendingIo' @{PeerReference=$Peer;Operation=$IoOperation;OverlappedAddress=$null;BufferAddress=$null;BufferCapacity=[uint32]4096;BufferOwnerReference=$null;EventHandle=$null;BytesTransferred=$null;State=[R2IoState]::RESERVED;IssueFact=$null;CancelFact=$null;CompletionFact=$null}
            # Occupancy is reserved before any event/buffer acquisition.
            $p.Data[$key]=$i.View;$i.Private['Key']=$key;$i.Private['Requested']=[uint32]0;$i.Private['CancelAttempted']=$false
            if(-not $p.Private.ContainsKey('IoPools')){$p.Private['IoPools']=@{}}
            $poolKey=[string]$IoOperation
            if(-not $p.Private.IoPools.ContainsKey($poolKey)){
                $pool=[pscustomobject]@{Overlapped=(New-R2ProcessBuffer $Context 32);Buffer=(New-R2ProcessBuffer $Context 4096);Count=(New-R2ProcessBuffer $Context 4);Event=$null;Released=$false}
                $p.Private.IoPools.Add($poolKey,$pool)
                $pool.Event=New-R2ProcessHandle $Context ([R2HandleKind]::EVENT)
                $sa=New-R2ProcessBuffer $Context 24;Set-R2ProcessU32 $Context $sa 0 24
                $f=Invoke-R2ProcessNative $Context ([R2ApiId]::CreateEventW) @($sa,[int]1,[int]0,$null);Assert-R2ProcessHandle $Context $pool.Event $f;Release-R2NativeBuffer $Context $sa
            }
            $pool=$p.Private.IoPools[$poolKey]
            if($pool.Released){Stop-R2ProcessFault $Context 'R2_IO_POOL_CONSUMED'}
            $i.Private['Overlapped']=$pool.Overlapped;$i.Private['Buffer']=$pool.Buffer;$i.Private['Count']=$pool.Count
            $event=$pool.Event;$i.Data['EventHandle']=$event
            # This direction's prior issue is fully completed/released before
            # occupancy was cleared. ReadFile/WriteFile reset their manual event
            # on issue; the original live handle is never consumed/reacquired.
            Write-R2NativeBuffer $Context $i.Private.Overlapped 0 ([byte[]]::new(32))
            Set-R2ProcessU32 $Context $i.Private.Count 0 0
            Write-R2NativeReference $Context $i.Private.Overlapped 24 $event
            $i.Data['OverlappedAddress']=Get-R2NativeBufferPointer $Context $i.Private.Overlapped 0;$i.Data['BufferAddress']=Get-R2NativeBufferPointer $Context $i.Private.Buffer 0;$i.Data['BufferOwnerReference']=$i.Private.Buffer
            return ,$i.View
        }
        function Start-R2PeerIo($Context,$Io,[uint32]$Count) {
            $i=Get-R2ProcessRecord $Context $Io 'PendingIo';$p=Get-R2ProcessRecord $Context $i.Data.PeerReference 'Peer'
            if($i.Data.State -ne [R2IoState]::RESERVED -or $Count -gt 4096){Stop-R2ProcessFault $Context 'R2_IO_ISSUE_STATE'}
            $i.Private.Requested=$Count;$i.Data['State']=[R2IoState]::ISSUED
            switch($i.Data.Operation){
                CONNECT {$f=Invoke-R2ProcessNative $Context ([R2ApiId]::ConnectNamedPipe) @($p.Data.PipeHandle,$i.Private.Overlapped)}
                READ {$f=Invoke-R2ProcessNative $Context ([R2ApiId]::ReadFile) @($p.Data.PipeHandle,$i.Private.Buffer,$Count,$i.Private.Count,$i.Private.Overlapped)}
                WRITE {$f=Invoke-R2ProcessNative $Context ([R2ApiId]::WriteFile) @($p.Data.PipeHandle,$i.Private.Buffer,$Count,$i.Private.Count,$i.Private.Overlapped)}
            }
            $i.Data['IssueFact']=$f
            if($f.RawStatus -ne 0 -or ($i.Data.Operation -eq [R2IoOperation]::CONNECT -and $f.StatusBits -eq 535)){
                $i.Data['CompletionFact']=$f;$i.Data['BytesTransferred']=$(if($i.Data.Operation -eq [R2IoOperation]::CONNECT){[uint32]0}else{Get-R2ProcessU32 $Context $i.Private.Count 0});$i.Data['State']=[R2IoState]::COMPLETED
                if($i.Data.Operation -eq [R2IoOperation]::CONNECT){Retain-R2NativeFact $Context $f;$p.Private['ConnectionFact']=$f;$p.Private.NativeConnectionObserved=[R2Fact]::TRUE}
            }elseif($f.StatusBits -eq 997){$i.Data['State']=[R2IoState]::PENDING}
            elseif($i.Data.Operation -eq [R2IoOperation]::READ -and $f.StatusBits -eq 109){$i.Data['CompletionFact']=$f;$i.Data['State']=[R2IoState]::COMPLETED;Record-R2ExpectedPeerEof $Context $i.View $f}
            else{$i.Data['CompletionFact']=$f;$i.Data['State']=[R2IoState]::COMPLETED;Stop-R2ProcessFault $Context 'R2_PIPE_IO_ISSUE' $f}
            if($i.Data.State -eq [R2IoState]::PENDING -and $i.Data.Operation -eq [R2IoOperation]::CONNECT){$p.Data['PipeState']=[R2PipeState]::CONNECT_PENDING}
            return ,$i.View
        }
        function Complete-R2PeerIoStep($Context,$Io) {
            $i=Get-R2ProcessRecord $Context $Io 'PendingIo';$p=Get-R2ProcessRecord $Context $i.Data.PeerReference 'Peer'
            if($i.Data.State -eq [R2IoState]::COMPLETED){return ,$i.View}
            if($i.Data.State -notin @([R2IoState]::PENDING,[R2IoState]::CANCEL_REQUESTED)){Stop-R2ProcessFault $Context 'R2_IO_COMPLETE_STATE'}
            $f=Invoke-R2ProcessNative $Context ([R2ApiId]::GetOverlappedResult) @($p.Data.PipeHandle,$i.Private.Overlapped,$i.Private.Count,[int]0)
            if($f.RawStatus -eq 0 -and $f.StatusBits -eq 996){return 'PENDING'}
            $i.Data['CompletionFact']=$f
            if($f.RawStatus -eq 0 -and $f.StatusBits -notin @(995,109)){$i.Data['State']=[R2IoState]::COMPLETED;Stop-R2ProcessFault $Context 'R2_PIPE_IO_COMPLETION' $f}
            $i.Data['BytesTransferred']=$(if($f.RawStatus -ne 0){Get-R2ProcessU32 $Context $i.Private.Count 0}else{$null});$i.Data['State']=[R2IoState]::COMPLETED
            if($f.RawStatus -eq 0 -and $f.StatusBits -eq 109){Record-R2ExpectedPeerEof $Context $i.View $f}
            if($f.RawStatus -ne 0 -and $i.Data.Operation -eq [R2IoOperation]::CONNECT){Retain-R2NativeFact $Context $f;$p.Private['ConnectionFact']=$f;$p.Private.NativeConnectionObserved=[R2Fact]::TRUE}
            if($i.Data.BytesTransferred -gt $i.Private.Requested -and $i.Data.Operation -ne [R2IoOperation]::CONNECT){Stop-R2ProcessFault $Context 'R2_PIPE_IO_EXCESS_BYTES' $f}
            return ,$i.View
        }
        function Record-R2ExpectedPeerEof($Context,$Io,$Fact) {
            $i=Get-R2ProcessRecord $Context $Io 'PendingIo';$p=Get-R2ProcessRecord $Context $i.Data.PeerReference 'Peer'
            if($i.Data.Operation -ne [R2IoOperation]::READ -or $Fact.RawStatus -ne 0 -or $Fact.StatusBits -ne 109){Stop-R2ProcessFault $Context 'R2_INVALID_EOF_EVIDENCE' $Fact}
            if(-not $p.Private.EofExpected){Stop-R2ProcessFault $Context 'R2_UNEXPECTED_PEER_EOF' $Fact}
            Retain-R2NativeFact $Context $Fact
            if($null -eq $p.Private.EofFact){$p.Private.EofFact=$Fact;$p.Private.Facts.Add($Fact)}
            $i.Data['BytesTransferred']=[uint32]0;$p.Data['PipeState']=[R2PipeState]::EOF_OBSERVED
        }
        function Release-R2PeerIo($Context,$Io) {
            $i=Get-R2ProcessRecord $Context $Io 'PendingIo';$p=Get-R2ProcessRecord $Context $i.Data.PeerReference 'Peer'
            if($i.Data.State -ne [R2IoState]::COMPLETED){Stop-R2ProcessFault $Context 'R2_IO_RELEASE_BEFORE_COMPLETION'}
            foreach($fact in @($i.Data.IssueFact,$i.Data.CompletionFact,$i.Data.CancelFact)){if($null -ne $fact){Retire-R2NativeFact $Context $fact}}
            $i.Data['State']=[R2IoState]::RELEASED;$p.Data[$i.Private.Key]=$null
        }
        function Request-R2PeerIoCancellation($Context,$Io) {
            $i=Get-R2ProcessRecord $Context $Io 'PendingIo';$p=Get-R2ProcessRecord $Context $i.Data.PeerReference 'Peer'
            if($i.Data.State -eq [R2IoState]::COMPLETED){return}
            if($i.Private.CancelAttempted){return}
            if($i.Data.State -notin @([R2IoState]::PENDING,[R2IoState]::ISSUED)){Stop-R2ProcessFault $Context 'R2_IO_CANCEL_STATE'}
            $i.Private.CancelAttempted=$true;$i.Data['State']=[R2IoState]::CANCEL_REQUESTED
            $f=Invoke-R2ProcessNative $Context ([R2ApiId]::CancelIoEx) @($p.Data.PipeHandle,$i.Private.Overlapped);$i.Data['CancelFact']=$f
            if($f.RawStatus -eq 0 -and $f.StatusBits -ne 1168){Stop-R2Guard $Context 'External' 'R2_CANCEL_IO_FAILED' $f.StatusBits $i.Data.IssuerSerial}
            # Neither TRUE nor ERROR_NOT_FOUND means drained. Completion is separate.
        }
        function New-R2WireBytes($Context,$Peer,[uint16]$Kind,[byte[]]$Payload) {
            $p=Get-R2ProcessRecord $Context $Peer 'Peer'
            if($Kind -lt 1 -or $Kind -gt 8 -or $null -eq $Payload -or $Payload.Length -gt 4032 -or $p.Data.TxSequence -eq [uint64]::MaxValue){Stop-R2ProcessFault $Context 'R2_FRAME_BOUNDS'}
            $p.Data['TxSequence']=[uint64]($p.Data.TxSequence+1)
            $bytes=[byte[]]::new(64+$Payload.Length)
            [Array]::Copy([BitConverter]::GetBytes([uint32]$bytes.Length),0,$bytes,0,4);[Array]::Copy([BitConverter]::GetBytes([uint16]1),0,$bytes,4,2);[Array]::Copy([BitConverter]::GetBytes($Kind),0,$bytes,6,2)
            [Array]::Copy([BitConverter]::GetBytes([uint64]$p.Data.TxSequence),0,$bytes,8,8);[Array]::Copy([BitConverter]::GetBytes([long](Get-R2NativeQpc $Context)),0,$bytes,16,8)
            [Array]::Copy([BitConverter]::GetBytes([uint64]$p.Private.WireSerial),0,$bytes,24,8);[Array]::Copy([byte[]]$p.Data.InvocationNonce,0,$bytes,32,32);[Array]::Copy($Payload,0,$bytes,64,$Payload.Length)
            return ,$bytes
        }
        function Complete-R2PeerBootstrapWrite($Context,$Peer) {
            $p=Get-R2ProcessRecord $Context $Peer 'Peer';$c=Get-R2ProcessRecord $Context $p.Data.OriginalChildReference 'Child';$r=Get-R2ProcessOwnerState $Context
            if($p.Private.BootstrapWritten -or $c.Data.State -ne [R2ChildState]::BIRTH_CONFIRMED){Stop-R2ProcessFault $Context 'R2_BOOTSTRAP_WRITE_STATE'}
            if($p.Private.BootstrapStage -eq 0){
                if($p.Private.BootstrapAttempted){Stop-R2ProcessFault $Context 'R2_BOOTSTRAP_WRITE_RETRY'}
                $p.Private.BootstrapAttempted=$true;$p.Private['RootTime']=Get-R2ProcessCreation $Context $r.Root
                $p.Private['RootIdFact']=Invoke-R2ProcessNative $Context ([R2ApiId]::GetProcessId) @($r.Root)
                Retain-R2NativeFact $Context $p.Private.RootIdFact
                if($p.Private.RootIdFact.RawStatus -le 0){Stop-R2ProcessFault $Context 'R2_ROOT_IDENTITY' $p.Private.RootIdFact}
                $p.Private.BootstrapStage=1;return
            }
            $bindings=@(@('RootHandle',$r.Root,[uint32]0x101001),@('PrepJobHandle',$r.Prep,[uint32]0x0C),@('ExternalJobHandle',$r.External,[uint32]0x0C),@('StopEventHandle',$r.StopEvent,[uint32]0x100002))
            if($p.Private.BootstrapStage -le 4){
                $binding=$bindings[$p.Private.BootstrapStage-1];$dup=New-R2ProcessDuplicate $Context $binding[1] $c.Data.OriginalPiProcess $binding[2] $false $false;$p.Data[$binding[0]]=$dup;$p.Private.Duplicates.Add($dup)
                $p.Private.BootstrapStage++;return
            }
            if($p.Private.BootstrapStage -ne 5){Stop-R2ProcessFault $Context 'R2_BOOTSTRAP_WRITE_PHASE'}
            # Reserve the sole write phase before generating or issuing bytes.
            $p.Private.BootstrapStage=6;$rootTime=$p.Private.RootTime;$r2RootIdFact=$p.Private.RootIdFact
            $p.Data['ProcessHandle']=$c.Data.OriginalPiProcess
            $name=[Text.Encoding]::Unicode.GetBytes($p.Private.PipeName+[char]0);$sid=[byte[]]$p.Data.CurrentSidBytes;$payload=[byte[]]::new(144+$sid.Length+$name.Length)
            [Array]::Copy([BitConverter]::GetBytes([uint32]$r2RootIdFact.RawStatus),0,$payload,0,4);[Array]::Copy([BitConverter]::GetBytes([uint64]$rootTime.Value),0,$payload,8,8)
            [Array]::Copy([BitConverter]::GetBytes([uint32]$c.Data.OriginalPid),0,$payload,16,4);[Array]::Copy([BitConverter]::GetBytes([uint64]$c.Data.ProcessCreationFileTime),0,$payload,24,8)
            [Array]::Copy([BitConverter]::GetBytes([long]$Context.Q0),0,$payload,32,8);[Array]::Copy([BitConverter]::GetBytes([long]$Context.Frequency),0,$payload,40,8)
            [Array]::Copy([BitConverter]::GetBytes([long]$Context.PrepDeadline),0,$payload,48,8);[Array]::Copy([BitConverter]::GetBytes([long]$Context.ExternalDeadline),0,$payload,56,8)
            $j=0;foreach($dup in $p.Private.Duplicates){[Array]::Copy([BitConverter]::GetBytes([long]$dup.LocalValue.ToInt64()),0,$payload,64+16*$j,8);[Array]::Copy([BitConverter]::GetBytes([uint64]$dup.IssuerSerial),0,$payload,72+16*$j,8);$j++}
            [Array]::Copy([BitConverter]::GetBytes([uint32]$name.Length),0,$payload,128,4);[Array]::Copy([BitConverter]::GetBytes([uint32]$c.Data.OriginalSlotReference.Id),0,$payload,132,4);[Array]::Copy([BitConverter]::GetBytes([uint32]$c.Data.Role),0,$payload,136,4);[Array]::Copy([BitConverter]::GetBytes([uint32]$sid.Length),0,$payload,140,4);[Array]::Copy($sid,0,$payload,144,$sid.Length);[Array]::Copy($name,0,$payload,144+$sid.Length,$name.Length)
            $p.Private['BootstrapPayload']=[Array]::AsReadOnly($payload)
            $wire=New-R2WireBytes $Context $Peer 1 $payload;$buffer=New-R2ProcessBuffer $Context ([uint32]$wire.Length);Write-R2NativeBuffer $Context $buffer 0 $wire;$count=New-R2ProcessBuffer $Context 4
            # Only the one synchronous anonymous write is allowed. Its actual
            # QPC bracket is enforced by the ledger; a requested 4KiB pipe is no
            # guarantee that this call is nonblocking or schedulable in 100ms.
            $f=Invoke-R2ProcessNative $Context ([R2ApiId]::WriteFile) @($p.Private.AnonymousWriter,$buffer,[uint32]$wire.Length,$count,[IntPtr]::Zero)
            $p.Private['BootstrapWriteFact']=$f
            Retain-R2NativeFact $Context $f
            Assert-R2ProcessBool $Context $f 'R2_BOOTSTRAP_WRITE'
            if((Get-R2ProcessU32 $Context $count 0) -ne $wire.Length){Stop-R2ProcessFault $Context 'R2_BOOTSTRAP_SHORT_WRITE' $f}
            $p.Private.BootstrapWritten=$true
            foreach($h in @($p.Private.AnonymousReader,$p.Private.InheritedReader,$p.Private.AnonymousWriter)){$null=Consume-R2Handle $Context $h}
            Release-R2NativeBuffer $Context $buffer;Release-R2NativeBuffer $Context $count
        }
        function Confirm-R2PeerConnectionStep($Context,$Peer) {
            $p=Get-R2ProcessRecord $Context $Peer 'Peer'
            if($p.Data.PipeState -eq [R2PipeState]::CONNECTED_VERIFIED){return 'CONNECTED'}
            if($null -eq $p.Data.PendingConnect){Stop-R2ProcessFault $Context 'R2_CONNECT_NOT_REGISTERED'}
            $complete=Complete-R2PeerIoStep $Context $p.Data.PendingConnect;if($complete -is [string]){return 'PENDING'}
            $c=Get-R2ProcessRecord $Context $p.Data.OriginalChildReference 'Child'
            if($null -eq $c.Data.OriginalPid -or $null -eq $c.Data.ProcessCreationFileTime -or $p.Data.ConnectionCount -ne 0){Stop-R2ProcessFault $Context 'R2_CONNECT_CHILD_IDENTITY'}
            $out=New-R2ProcessBuffer $Context 4;$f=Invoke-R2ProcessNative $Context ([R2ApiId]::GetNamedPipeClientProcessId) @($p.Data.PipeHandle,$out);Assert-R2ProcessBool $Context $f 'R2_PIPE_CLIENT_PID'
            Retain-R2NativeFact $Context $f
            $id=Get-R2ProcessU32 $Context $out 0;$time=Get-R2ProcessCreation $Context $c.Data.OriginalPiProcess
            if($id -ne $c.Data.OriginalPid -or $time.Value -ne $c.Data.ProcessCreationFileTime){Stop-R2ProcessFault $Context 'R2_PIPE_CLIENT_IDENTITY' $f}
            $p.Data['ClientPid']=$id;$p.Data['ClientProcessCreationFileTime']=$time.Value;$p.Data['ClientIdentityFact']=$f;$p.Data['ConnectionCount']=[uint32]1;$p.Data['PipeState']=[R2PipeState]::CONNECTED_VERIFIED;$p.Data['State']=[R2PeerState]::CONNECTED_VERIFIED
            Release-R2NativeBuffer $Context $out;Release-R2PeerIo $Context $p.Data.PendingConnect
            # The endpoint-owning original root echoes its retained bootstrap
            # bindings over the actual named endpoint before peer READY.
            return 'CONNECTED'
        }
        function Send-R2PeerFrame($Context,$Peer,[uint16]$FrameKind,[byte[]]$BoundedPayload) {
            $p=Get-R2ProcessRecord $Context $Peer 'Peer'
            if($Context.StopState -eq [R2Fact]::TRUE -and $FrameKind -notin @(6,7,8)){throw 'R2_TERMINAL_FRAME_KIND'}
            if($p.Data.PipeState -ne [R2PipeState]::CONNECTED_VERIFIED){$null=Confirm-R2PeerConnectionStep $Context $Peer;return 'PENDING'}
            if($p.Private.RootSide -and -not $p.Private.EchoSent -and -not $p.Private.ContainsKey('EchoWriting')){
                $p.Private['EchoWriting']=$true
                try{$echoResult=Send-R2PeerFrame $Context $Peer 3 ([byte[]]$p.Private.BootstrapPayload)}finally{$p.Private.Remove('EchoWriting') | Out-Null}
                if($echoResult -ceq 'SENT'){$p.Private.EchoSent=$true}
                return 'PENDING'
            }
            if($null -ne $p.Data.PendingWrite){
                $old=Get-R2ProcessRecord $Context $p.Data.PendingWrite 'PendingIo'
                if($old.Private.FrameKind -ne $FrameKind -or $null -eq $BoundedPayload -or $old.Private.Payload.Count -ne $BoundedPayload.Length){Stop-R2ProcessFault $Context 'R2_PENDING_SEND_REPLACEMENT'}
                for($j=0;$j -lt $BoundedPayload.Length;$j++){if($old.Private.Payload[$j] -ne $BoundedPayload[$j]){Stop-R2ProcessFault $Context 'R2_PENDING_SEND_REPLACEMENT'}}
                $complete=Complete-R2PeerIoStep $Context $p.Data.PendingWrite
                if($complete -is [string]){return 'PENDING'}
                $old=Get-R2ProcessRecord $Context $p.Data.PendingWrite 'PendingIo'
                if($old.Data.CompletionFact.RawStatus -eq 0 -or $old.Data.BytesTransferred -ne $old.Private.Requested){Stop-R2ProcessFault $Context 'R2_FRAME_WRITE_INCOMPLETE' $old.Data.CompletionFact}
                Release-R2PeerIo $Context $p.Data.PendingWrite
                # Completion does not send the supplied frame a second time.
                return 'SENT'
            }
            if($FrameKind -eq 1 -or $FrameKind -lt 2 -or $FrameKind -gt 8 -or ($p.Private.RootSide -and $FrameKind -eq 2)){Stop-R2ProcessFault $Context 'R2_FRAME_DIRECTION'}
            $wire=New-R2WireBytes $Context $Peer $FrameKind $BoundedPayload
            $io=New-R2PendingIo $Context $Peer ([R2IoOperation]::WRITE);$i=Get-R2ProcessRecord $Context $io 'PendingIo';$i.Private['FrameKind']=$FrameKind;$i.Private['Payload']=[Array]::AsReadOnly([byte[]]$BoundedPayload.Clone());Write-R2NativeBuffer $Context $i.Private.Buffer 0 $wire
            $null=Start-R2PeerIo $Context $io ([uint32]$wire.Length)
            if($i.Data.State -eq [R2IoState]::PENDING){return 'PENDING'}
            if($i.Data.BytesTransferred -ne $wire.Length){Stop-R2ProcessFault $Context 'R2_FRAME_SHORT_WRITE' $i.Data.CompletionFact}
            Release-R2PeerIo $Context $io
            return 'SENT'
        }
        function Assert-R2WireFrame($Context,$Peer,[byte[]]$Bytes) {
            $p=Get-R2ProcessRecord $Context $Peer 'Peer'
            if($Bytes.Length -lt 64 -or $Bytes.Length -gt 4096 -or [BitConverter]::ToUInt32($Bytes,0) -ne $Bytes.Length -or [BitConverter]::ToUInt16($Bytes,4) -ne 1){Stop-R2ProcessFault $Context 'R2_FRAME_HEADER'}
            $kind=[BitConverter]::ToUInt16($Bytes,6);$sequence=[BitConverter]::ToUInt64($Bytes,8);$serial=[BitConverter]::ToUInt64($Bytes,24)
            if($kind -lt 2 -or $kind -gt 8 -or $p.Data.RxSequence -eq [uint64]::MaxValue -or $sequence -ne [uint64]($p.Data.RxSequence+1) -or $serial -ne $p.Private.WireSerial -or (-not $p.Private.RootSide -and $kind -eq 2)){Stop-R2ProcessFault $Context 'R2_FRAME_BINDING'}
            for($i=0;$i -lt 32;$i++){if($Bytes[32+$i] -ne $p.Data.InvocationNonce[$i]){Stop-R2ProcessFault $Context 'R2_FRAME_NONCE'}}
            $sender=[BitConverter]::ToInt64($Bytes,16);$now=Get-R2NativeQpc $Context
            if($sender -lt $Context.Q0 -or $sender -gt $now -or ([bigint]$now-$sender)*10 -gt $Context.Frequency){Stop-R2ProcessFault $Context 'R2_FRAME_NATIVE_STALE'}
            if($kind -eq 2 -and $null -ne $p.Data.ReadyFact){Stop-R2ProcessFault $Context 'R2_PEER_READY_REPLAY'}
            $p.Data['RxSequence']=$sequence
            if($kind -eq 3){$p.Data['LastHeartbeatQpc']=$sender;$p.Data['HeartbeatDueQpc']=[long]([bigint]$sender+[bigint]$Context.Frequency/10)}
            if($kind -eq 2){Retain-R2NativeFact $Context $p.Private.LastReadFact;$p.Data['State']=[R2PeerState]::READY_OBSERVED;$p.Data['ReadyFact']=$p.Private.LastReadFact}
            if($kind -eq 6){$p.Data['State']=[R2PeerState]::STOP_LATCHED;if($null -eq $p.Data.StopFact){Retain-R2NativeFact $Context $p.Private.LastReadFact;$p.Data['StopFact']=$p.Private.LastReadFact};Stop-R2Guard $Context 'External' 'R2_PEER_STOP' $null $p.Data.IssuerSerial}
            if($kind -eq 8){if(-not $p.Private.ContainsKey('ExitingFact')){Retain-R2NativeFact $Context $p.Private.LastReadFact;$p.Private['ExitingFact']=$p.Private.LastReadFact};$p.Data['State']=[R2PeerState]::EXITING_OBSERVED}
            $payload=[byte[]]::new($Bytes.Length-64);[Array]::Copy($Bytes,64,$payload,0,$payload.Length)
            return ,(New-R2ProcessView (New-R2ProcessMap @{TotalBytes=[uint32]$Bytes.Length;Abi=[uint16]1;Kind=$kind;Sequence=$sequence;SenderQpc=$sender;ObjectSerial=$serial;Payload=[Array]::AsReadOnly($payload);NativeFact=$p.Private.LastReadFact}))
        }
        function Receive-R2PeerFrame($Context,$Peer) {
            $p=Get-R2ProcessRecord $Context $Peer 'Peer'
            if($p.Data.PipeState -ne [R2PipeState]::CONNECTED_VERIFIED){$null=Confirm-R2PeerConnectionStep $Context $Peer;return 'PENDING'}
            if($p.Private.RootSide -and -not $p.Private.EchoSent){$null=Send-R2PeerFrame $Context $Peer 3 ([byte[]]$p.Private.BootstrapPayload);return 'PENDING'}
            if($null -eq $p.Data.PendingRead){
                $io=New-R2PendingIo $Context $Peer ([R2IoOperation]::READ)
                $null=Start-R2PeerIo $Context $io ([uint32]($p.Private.IncomingLength-$p.Private.IncomingCount))
                if($io.State -eq [R2IoState]::PENDING){return 'PENDING'}
            }
            $complete=Complete-R2PeerIoStep $Context $p.Data.PendingRead;if($complete -is [string]){return 'PENDING'}
            $i=Get-R2ProcessRecord $Context $p.Data.PendingRead 'PendingIo';$p.Private['LastReadFact']=$i.Data.CompletionFact
            if($i.Data.CompletionFact.RawStatus -eq 0 -and $i.Data.CompletionFact.StatusBits -eq 995){Release-R2PeerIo $Context $i.View;return 'CANCELLED'}
            if($i.Data.CompletionFact.RawStatus -eq 0 -and $i.Data.CompletionFact.StatusBits -eq 109){
                Release-R2PeerIo $Context $i.View
                return 'EOF'
            }
            if($i.Data.CompletionFact.RawStatus -ne 0 -and $i.Data.BytesTransferred -eq 0){Stop-R2ProcessFault $Context 'R2_PIPE_ZERO_BYTE_MESSAGE' $i.Data.CompletionFact}
            $bytes=[byte[]](Read-R2NativeBuffer $Context $i.Private.Buffer 0 $i.Data.BytesTransferred);[Array]::Copy($bytes,0,$p.Private.Incoming,$p.Private.IncomingCount,$bytes.Length);$p.Private.IncomingCount+=$bytes.Length
            if($p.Private.IncomingCount -eq 64 -and $p.Private.IncomingLength -eq 64){$length=[BitConverter]::ToUInt32($p.Private.Incoming,0);if($length -lt 64 -or $length -gt 4096){Stop-R2ProcessFault $Context 'R2_FRAME_LENGTH'};$p.Private.IncomingLength=[int]$length}
            if($p.Private.IncomingCount -lt $p.Private.IncomingLength){Release-R2PeerIo $Context $i.View;return 'PENDING'}
            $wire=[byte[]]::new($p.Private.IncomingLength);[Array]::Copy($p.Private.Incoming,0,$wire,0,$wire.Length);$p.Private.IncomingCount=0;$p.Private.IncomingLength=64
            $frame=Assert-R2WireFrame $Context $Peer $wire
            Release-R2PeerIo $Context $i.View
            return ,$frame
        }

        function Request-R2ChildTermination($Context,$Child,[uint32]$ExitCode) {
            $c=Get-R2ProcessRecord $Context $Child 'Child'
            if($null -eq $c.Data.OriginalPiProcess -or $c.Data.OriginalPiProcess.State -ne [R2HandleState]::LIVE){return}
            if($c.Private.TerminateAttempted){return}
            $c.Private.TerminateAttempted=$true;$c.Data['State']=[R2ChildState]::TERMINATE_REQUESTED
            $f=Invoke-R2ProcessNative $Context ([R2ApiId]::TerminateProcess) @($c.Data.OriginalPiProcess,$ExitCode);Retain-R2NativeFact $Context $f;$c.Data['TerminateFact']=$f;$c.Private.Facts.Add($f)
            if($f.RawStatus -eq 0){Stop-R2Guard $Context 'External' 'R2_TERMINATE_PROCESS_FAILED' $f.StatusBits $c.Data.IssuerSerial}
        }
        function Request-R2RoleStop($Context,[uint32]$ExitCode=1) {
            $r=Get-R2ProcessOwnerState $Context
            if($Context.StopState -ne [R2Fact]::TRUE){Stop-R2Guard $Context 'External' 'R2_STOP_REQUESTED' $null 0}
            $r.TerminalIssued=$true
            if(-not $r.StopEventAttempted){
                $r.StopEventAttempted=$true
                if($null -ne $r.StopEvent -and $r.StopEvent.State -eq [R2HandleState]::LIVE){$f=Invoke-R2ProcessNative $Context ([R2ApiId]::SetEvent) @($r.StopEvent);Retain-R2NativeFact $Context $f;$r.Facts.Add($f);if($f.RawStatus -eq 0){Stop-R2Guard $Context 'External' 'R2_STOP_EVENT_FAILED' $f.StatusBits $r.StopEvent.IssuerSerial}}
                return 'PENDING'
            }
            # Root belongs to external: terminate prep first. External termination
            # is a final finish action after durable receipt/independent joins.
            if($r.PrepTerminateAttempted){return 'REQUESTED'}
            $r.PrepTerminateAttempted=$true
            if($null -ne $r.Prep -and $r.Prep.State -eq [R2HandleState]::LIVE){
                $f=Invoke-R2ProcessNative $Context ([R2ApiId]::TerminateJobObject) @($r.Prep,$ExitCode);Retain-R2NativeFact $Context $f;$r.Facts.Add($f)
                $r.PrepTerminateFact=$f
                if($f.RawStatus -ne 0){foreach($child in $r.Children){if($child.Data.Role -eq [R2Role]::PREP -and $child.Data.State -notin @([R2ChildState]::EXIT_OBSERVED,[R2ChildState]::JOINED)){$child.Data['State']=[R2ChildState]::TERMINATE_REQUESTED}}}
                else{Stop-R2Guard $Context 'External' 'R2_PREP_JOB_TERMINATE_FAILED' $f.StatusBits $r.Prep.IssuerSerial}
            }
            return 'REQUESTED'
        }
        function Invoke-R2TerminationFallbackStep($Context,[uint32]$ExitCode=1) {
            $r=Get-R2ProcessOwnerState $Context
            if(-not $r.TerminalIssued -or -not $r.PrepTerminateAttempted){$null=Request-R2RoleStop $Context $ExitCode;return 'PENDING'}
            foreach($c in $r.Children){
                $prepFailed=($null -eq $r.PrepTerminateFact -or $r.PrepTerminateFact.RawStatus -eq 0)
                if(($c.Data.Role -ne [R2Role]::PREP -or $prepFailed) -and -not $c.Private.TerminateAttempted -and $null -ne $c.Data.OriginalPiProcess -and $c.Data.State -notin @([R2ChildState]::EXIT_OBSERVED,[R2ChildState]::JOINED)){
                    Request-R2ChildTermination $Context $c.View $ExitCode;return 'PENDING'
                }
            }
            return 'REQUESTED'
        }
        function Read-R2PeerCleanupStep($Context,$Peer) {
            $p=Get-R2ProcessRecord $Context $Peer 'Peer'
            if($null -ne $p.Private.EofFact){return 'EOF'}
            if($p.Private.CleanupReadStopped){return 'NO_EOF'}
            if($null -eq $p.Data.PendingRead){
                $io=New-R2PendingIo $Context $Peer ([R2IoOperation]::READ);$i=Get-R2ProcessRecord $Context $io 'PendingIo';$i.Private['CleanupRead']=$true
                $null=Start-R2PeerIo $Context $io 4032
                if($io.State -eq [R2IoState]::PENDING){return 'PENDING'}
            }
            $i=Get-R2ProcessRecord $Context $p.Data.PendingRead 'PendingIo'
            if($i.Data.State -eq [R2IoState]::ISSUED){
                # The native wrapper may throw after issuing the read but before
                # returning its fact. Keep its buffers/event occupied, record
                # the unknown return and request cancellation exactly once.
                $i.Private['CleanupIssueUnknown']=$true;$p.Private.CleanupUnknown=$true
                Request-R2PeerIoCancellation $Context $i.View
                return 'PENDING'
            }
            if($i.Data.State -ne [R2IoState]::COMPLETED){if((Complete-R2PeerIoStep $Context $i.View) -is [string]){return 'PENDING'}}
            $fact=$i.Data.CompletionFact
            if($fact.RawStatus -eq 0 -and $fact.StatusBits -eq 109){Release-R2PeerIo $Context $i.View;return 'EOF'}
            if($i.Private.ContainsKey('CleanupIssueUnknown')){
                # Only actual completion permits release. A completed unknown
                # issue never starts another read or supplies missing EOF.
                Retain-R2NativeFact $Context $fact
                Release-R2PeerIo $Context $i.View
                $p.Private.CleanupReadStopped=$true
                return 'NO_EOF'
            }
            if($fact.RawStatus -ne 0 -and $i.Data.BytesTransferred -gt 0){Release-R2PeerIo $Context $i.View;return 'PENDING'}
            # Cleanup consumes raw bytes only. It never authenticates, starts an
            # echo, parses an application frame or converts zero/232 into EOF.
            $p.Private.CleanupReadStopped=$true;$p.Private.CleanupUnknown=$true
            Retain-R2NativeFact $Context $fact
            Stop-R2Guard $Context 'External' 'R2_CLEANUP_READ_WITHOUT_EOF' $fact.StatusBits $p.Data.IssuerSerial
            Release-R2PeerIo $Context $i.View
            return 'NO_EOF'
        }
        function Release-R2PeerPoolStep($Context,$Peer,$Pool) {
            $p=Get-R2ProcessRecord $Context $Peer 'Peer'
            if(-not $Pool.PSObject.Properties['ReleaseActions']){$Pool | Add-Member -NotePropertyName ReleaseActions -NotePropertyValue @{Buffer='UNATTEMPTED';Overlapped='UNATTEMPTED';Count='UNATTEMPTED';Event='UNATTEMPTED'};$Pool | Add-Member -NotePropertyName ReleaseComplete -NotePropertyValue $false}
            if($Pool.ReleaseComplete){return 'COMPLETE'}
            foreach($key in @('Buffer','Overlapped','Count','Event')){
                if($Pool.ReleaseActions[$key] -ne 'UNATTEMPTED'){continue}
                $Pool.ReleaseActions[$key]='UNKNOWN';$resource=$Pool.$key
                try{
                    if($null -eq $resource -or $resource.State -eq [R2HandleState]::RESERVED){$Pool.ReleaseActions[$key]='DONE'}
                    elseif($key -eq 'Event'){
                        if($resource.State -eq [R2HandleState]::LIVE){$null=Consume-R2Handle $Context $resource}
                        if($null -ne $resource.ConsumeFact -and $resource.ConsumeFact.RawStatus -ne 0){$Pool.ReleaseActions[$key]='DONE'}
                    }elseif($resource.State -eq [R2HandleState]::LIVE){Release-R2NativeBuffer $Context $resource;$Pool.ReleaseActions[$key]='DONE'}
                }catch{Stop-R2Guard $Context 'External' 'R2_IO_POOL_RELEASE_FAILED' $null $p.Data.IssuerSerial}
                if($Pool.ReleaseActions[$key] -ne 'DONE'){$p.Private.CleanupUnknown=$true}
                return 'PENDING'
            }
            $Pool.ReleaseComplete=$true
            $Pool.Released=($Pool.ReleaseActions.Values -notcontains 'UNKNOWN')
            return 'COMPLETE'
        }
        function Close-R2PeerStep($Context,$Peer) {
            $p=Get-R2ProcessRecord $Context $Peer 'Peer';$p.Private.EofExpected=$true
            if($p.Private.CleanupComplete){return $(if($p.Private.CleanupUnknown){'CLOSED_RESIDUE'}else{'CLOSED'})}
            foreach($key in @('PendingConnect','PendingWrite','PendingRead')){
                if($null -eq $p.Data[$key]){continue}
                $i=Get-R2ProcessRecord $Context $p.Data[$key] 'PendingIo'
                if($key -eq 'PendingRead' -and $i.Private.ContainsKey('CleanupRead')){continue}
                if($i.Data.State -eq [R2IoState]::RESERVED -and $null -eq $i.Data.IssueFact){$i.Data['State']=[R2IoState]::RELEASED;$p.Data[$key]=$null;return 'PENDING'}
                if($i.Data.State -ne [R2IoState]::COMPLETED){
                    Request-R2PeerIoCancellation $Context $i.View
                    if((Complete-R2PeerIoStep $Context $i.View) -is [string]){return 'PENDING'}
                }
                if($i.Data.Operation -eq [R2IoOperation]::READ -and $null -ne $i.Data.CompletionFact -and $i.Data.CompletionFact.RawStatus -ne 0 -and $i.Data.BytesTransferred -eq 0){
                    Retain-R2NativeFact $Context $i.Data.CompletionFact;$p.Private.CleanupReadStopped=$true;$p.Private.CleanupUnknown=$true
                    Stop-R2Guard $Context 'External' 'R2_PIPE_ZERO_BYTE_MESSAGE' $null $p.Data.IssuerSerial
                }
                Release-R2PeerIo $Context $i.View;return 'PENDING'
            }
            # Root drains a previously verified connected endpoint without the
            # normal receive/authentication/HEARTBEAT path. A partial bootstrap
            # or the closing child endpoint keeps its absent EOF proof absent.
            if($p.Private.RootSide -and $p.Data.ConnectionCount -eq 1 -and $null -eq $p.Private.EofFact -and -not $p.Private.CleanupReadStopped){
                if((Read-R2PeerCleanupStep $Context $Peer) -eq 'PENDING'){return 'PENDING'}
            }
            if($null -ne $p.Data.PendingRead){return 'PENDING'}
            if($p.Private.RootSide -and $p.Private.NativeConnectionObserved -eq [R2Fact]::TRUE -and -not $p.Private.DisconnectAttempted){
                $p.Private.DisconnectAttempted=$true;$p.Data['PipeState']=[R2PipeState]::DISCONNECT_REQUESTED
                try{
                    $f=Invoke-R2ProcessNative $Context ([R2ApiId]::DisconnectNamedPipe) @($p.Data.PipeHandle);Retain-R2NativeFact $Context $f;$p.Private.Facts.Add($f)
                    if($f.RawStatus -eq 0 -and $f.StatusBits -ne 233){$p.Private.CleanupUnknown=$true;Stop-R2Guard $Context 'External' 'R2_PIPE_DISCONNECT_FAILED' $f.StatusBits $p.Data.IssuerSerial}
                }catch{
                    $p.Private.CleanupUnknown=$true
                    # The once flag also bounds this secondary fault attempt.
                    # Reporting failure cannot prevent the other close actions.
                    try{Stop-R2Guard $Context 'External' 'R2_PIPE_DISCONNECT_EXCEPTION' $null $p.Data.IssuerSerial}catch{}
                }
                return 'PENDING'
            }
            if($null -ne $p.Data.PipeHandle -and $p.Data.PipeHandle.State -eq [R2HandleState]::LIVE){
                try{$null=Consume-R2Handle $Context $p.Data.PipeHandle}catch{$p.Private.CleanupUnknown=$true;Stop-R2Guard $Context 'External' 'R2_PIPE_CLOSE_FAILED' $null $p.Data.IssuerSerial}
                if($null -eq $p.Data.PipeHandle.ConsumeFact -or $p.Data.PipeHandle.ConsumeFact.RawStatus -eq 0){$p.Private.CleanupUnknown=$true}
                return 'PENDING'
            }
            if($p.Private.ContainsKey('IoPools')){foreach($pool in $p.Private.IoPools.Values){if(-not $pool.PSObject.Properties['ReleaseComplete'] -or -not $pool.ReleaseComplete){$null=Release-R2PeerPoolStep $Context $Peer $pool;return 'PENDING'}}}
            $p.Private.CleanupComplete=$true
            $p.Data['PipeState']=$(if($p.Private.CleanupUnknown){[R2PipeState]::FAULTED}else{[R2PipeState]::CLOSED})
            return $(if($p.Private.CleanupUnknown){'CLOSED_RESIDUE'}else{'CLOSED'})
        }
        function Join-R2OwnedChildStep($Context,$Child) {
            $c=Get-R2ProcessRecord $Context $Child 'Child'
            if($c.Private.CleanupComplete -or $c.Data.State -eq [R2ChildState]::JOINED){return ,$Child}
            if($null -eq $c.Data.OriginalPiProcess -or ($null -eq $c.Data.JoinFact -and $c.Data.OriginalPiProcess.State -ne [R2HandleState]::LIVE)){return 'PENDING'}
            if($null -eq $c.Data.JoinFact){
                $f=Invoke-R2ProcessNative $Context ([R2ApiId]::WaitForSingleObject) @($c.Data.OriginalPiProcess,[uint32]0)
                if($f.RawStatus -eq 258){return 'PENDING'}
                if($f.RawStatus -ne 0){Stop-R2ProcessFault $Context 'R2_PROCESS_JOIN_WAIT' $f}
                Retain-R2NativeFact $Context $f;$c.Private.Facts.Add($f);$c.Data['JoinFact']=$f;$c.Data['ExitObservedQpc']=$f.QpcEnd;$c.Data['State']=[R2ChildState]::EXIT_OBSERVED
                return 'PENDING'
            }
            if(-not $c.Private.ExitCodeAttempted){
                $c.Private.ExitCodeAttempted=$true;$out=$null
                try{
                    $out=New-R2ProcessBuffer $Context 4;$code=Invoke-R2ProcessNative $Context ([R2ApiId]::GetExitCodeProcess) @($c.Data.OriginalPiProcess,$out);Retain-R2NativeFact $Context $code;$c.Private['ExitCodeFact']=$code;$c.Private.Facts.Add($code)
                    if($code.RawStatus -ne 0){$c.Data['ExitCode']=Get-R2ProcessU32 $Context $out 0}else{$c.Private.CleanupUnknown=$true;Stop-R2Guard $Context 'External' 'R2_PROCESS_EXIT_CODE' $code.StatusBits $c.Data.IssuerSerial}
                }catch{$c.Private.CleanupUnknown=$true;Stop-R2Guard $Context 'External' 'R2_PROCESS_EXIT_CODE_UNKNOWN' $null $c.Data.IssuerSerial}
                finally{if($null -ne $out -and $out.State -eq [R2HandleState]::LIVE){try{Release-R2NativeBuffer $Context $out}catch{$c.Private.CleanupUnknown=$true;Stop-R2Guard $Context 'External' 'R2_EXIT_CODE_BUFFER_RELEASE' $null $c.Data.IssuerSerial}}}
                return 'PENDING'
            }
            if($null -ne $c.Private.Peer){
                foreach($duplicate in $c.Private.Peer.Private.Duplicates){if($duplicate.State -eq [R2HandleState]::LIVE){Record-R2RemoteDuplicateClosure $Context $duplicate $c.Data.JoinFact;return 'PENDING'}}
                $closed=Close-R2PeerStep $Context $c.Private.Peer.View
                if($closed -eq 'PENDING'){return 'PENDING'}
                if($closed -eq 'CLOSED_RESIDUE'){$c.Private.CleanupUnknown=$true}
                $c.Private.Peer.Data['JoinFact']=$c.Data.JoinFact
            }
            # Stdout/stderr facts stay UNKNOWN unless original streams were
            # actually selected and observed. No redirected stream is created by
            # this API; named peer EOF is a separately retained channel fact.
            foreach($handle in @($c.Data.OriginalPiThread,$c.Data.OriginalPiProcess)){
                if($handle.State -eq [R2HandleState]::LIVE){try{$null=Consume-R2Handle $Context $handle}catch{$c.Private.CleanupUnknown=$true;Stop-R2Guard $Context 'External' 'R2_JOIN_HANDLE_CLOSE_FAILED' $null $c.Data.IssuerSerial};if($null -eq $handle.ConsumeFact -or $handle.ConsumeFact.RawStatus -eq 0){$c.Private.CleanupUnknown=$true};return 'PENDING'}
            }
            $peerProof=($null -eq $c.Private.Peer -or ($null -ne $c.Private.Peer.Private.EofFact -and $c.Private.Peer.Private.BootstrapWritten -and $c.Private.Peer.Data.ConnectionCount -eq 1))
            $c.Private.CleanupComplete=$true
            if(-not $c.Private.CleanupUnknown -and $null -ne $c.Data.ExitCode -and $peerProof){$c.Data['State']=[R2ChildState]::JOINED;if($null -ne $c.Private.Peer){$c.Private.Peer.Data['State']=[R2PeerState]::JOINED}}
            return ,$Child
        }
        function Get-R2OwnedProcessSnapshot($Context) {
            $r=Get-R2ProcessOwnerState $Context
            return ,(New-R2ProcessView (New-R2ProcessMap @{ExternalJob=$r.External;PrepJob=$r.Prep;OriginalRootHandle=$r.Root;BorrowedCurrentProcess=$r.Current;StopEvent=$r.StopEvent;N=$r.N;Children=[Array]::AsReadOnly([object[]]@($r.Children | ForEach-Object {$_.View}));Peers=[Array]::AsReadOnly([object[]]@($r.Peers | ForEach-Object {$_.View}));NativeFacts=$r.Facts.AsReadOnly()}))
        }
        function Get-R2ProcessProgress($Context) {
            $r=Get-R2ProcessOwnerState $Context;$rows=[Collections.Generic.List[object]]::new()
            foreach($c in $r.Children){
                $p=$c.Private.Peer
                $row=New-R2ProcessView (New-R2ProcessMap @{ChildReference=$c.View;State=$c.Data.State;ConfirmStage=[uint32]$c.Private.ConfirmStage;PeerReference=$(if($null -eq $p){$null}else{$p.View});PeerSetupStage=$(if($null -eq $p){$null}else{[uint32]$p.Private.SetupStage});BootstrapWriteFact=$(if($null -eq $p -or -not $p.Private.ContainsKey('BootstrapWriteFact')){$null}else{$p.Private.BootstrapWriteFact});BootstrapWritten=$(if($null -eq $p){[R2Fact]::UNKNOWN}elseif($p.Private.BootstrapWritten){[R2Fact]::TRUE}else{[R2Fact]::UNKNOWN});ExitCodeAttempted=[bool]$c.Private.ExitCodeAttempted;CleanupActionsComplete=[bool]$c.Private.CleanupComplete;CleanupHasUnknownResidue=[bool]$c.Private.CleanupUnknown})
                $rows.Add($row)
            }
            return ,(New-R2ProcessView (New-R2ProcessMap @{JobSetupStage=[uint32]$r.JobStage;ExternalJobReference=$r.External;PrepJobReference=$r.Prep;Children=$rows.AsReadOnly();LocalPeerReference=$r.LocalPeer}))
        }
        function Close-R2ProcessBuffersStep($Context) {
            $r=Get-R2ProcessOwnerState $Context
            foreach($c in $r.Children){
                if($c.Private.ContainsKey('AttributeInitializeFact') -and -not $c.Private.AttributeDeleteAttempted){
                    $c.Private.AttributeDeleteAttempted=$true
                    $f=Invoke-R2ProcessNative $Context ([R2ApiId]::DeleteProcThreadAttributeList) @($c.Private.AttributeList);$c.Private['AttributeDeleteStatus']=Get-R2ProcessFactSummary $f
                    return 'PENDING'
                }
                if($c.Private.ContainsKey('BirthBuffers')){
                    foreach($buffer in $c.Private.BirthBuffers){if($null -ne $buffer -and $buffer.State -eq [R2HandleState]::LIVE){Release-R2NativeBuffer $Context $buffer;return 'PENDING'}}
                    $c.Private.Remove('BirthBuffers') | Out-Null
                }
            }
            if($null -ne $r.JobQueryPool -and -not $r.JobQueryPool.Released){
                foreach($buffer in @($r.JobQueryPool.Limits,$r.JobQueryPool.Cpu,$r.JobQueryPool.Length)){if($buffer.State -eq [R2HandleState]::LIVE){Release-R2NativeBuffer $Context $buffer;return 'PENDING'}}
                $r.JobQueryPool.Released=$true
            }
            if($r.PSObject.Properties['ThreadPool'] -and -not $r.ThreadPool.Released){
                if($null -ne $r.ThreadScan){
                    if($r.ThreadScan.Snapshot.State -eq [R2HandleState]::LIVE){$null=Consume-R2Handle $Context $r.ThreadScan.Snapshot;return 'PENDING'}
                    $r.ThreadScan=$null
                }
                foreach($buffer in @($r.ThreadPool.JobList,$r.ThreadPool.ExternalJobList,$r.ThreadPool.Length,$r.ThreadPool.Entry)){if($buffer.State -eq [R2HandleState]::LIVE){Release-R2NativeBuffer $Context $buffer;return 'PENDING'}}
                $r.ThreadPool.Released=$true
            }
            return 'CLOSED'
        }
        function Request-R2ExternalJobTermination($Context,[uint32]$ExitCode=1) {
            $r=Get-R2ProcessOwnerState $Context
            if(-not $r.PSObject.Properties['ExternalTerminationFact']){$r | Add-Member -NotePropertyName ExternalTerminationFact -NotePropertyValue $null;$r | Add-Member -NotePropertyName ExternalTerminationAttempted -NotePropertyValue $false}
            if($r.ExternalTerminationAttempted){return}
            if($Context.StopState -ne [R2Fact]::TRUE){Stop-R2Guard $Context 'External' 'R2_EXTERNAL_TERMINAL_REQUEST' $null 0}
            # FINISH ONLY: the original root is a member of this actual job.
            # The caller must have retained its durable terminal receipt first.
            $r.ExternalTerminationAttempted=$true
            if($null -ne $r.External -and $r.External.State -eq [R2HandleState]::LIVE){
                $f=Invoke-R2ProcessNative $Context ([R2ApiId]::TerminateJobObject) @($r.External,$ExitCode);Retain-R2NativeFact $Context $f;$r.ExternalTerminationFact=$f;$r.Facts.Add($f)
                if($f.RawStatus -eq 0){Stop-R2Guard $Context 'External' 'R2_EXTERNAL_JOB_TERMINATE_FAILED' $f.StatusBits $r.External.IssuerSerial}
            }
        }
        function Invoke-R2ExternalTerminationFallbackStep($Context,[uint32]$ExitCode=1) {
            $r=Get-R2ProcessOwnerState $Context
            if(-not $r.PSObject.Properties['ExternalTerminationAttempted'] -or -not $r.ExternalTerminationAttempted){throw 'R2_EXTERNAL_JOB_TERMINATION_FIRST'}
            if($null -ne $r.ExternalTerminationFact -and $r.ExternalTerminationFact.RawStatus -ne 0){return 'REQUESTED'}
            foreach($child in $r.Children){
                if(-not $child.Private.TerminateAttempted -and $null -ne $child.Data.OriginalPiProcess -and $child.Data.State -notin @([R2ChildState]::EXIT_OBSERVED,[R2ChildState]::JOINED)){Request-R2ChildTermination $Context $child.View $ExitCode;return 'PENDING'}
            }
            if(-not $r.PSObject.Properties['RootTerminationAttempted']){$r | Add-Member -NotePropertyName RootTerminationAttempted -NotePropertyValue $false}
            if(-not $r.RootTerminationAttempted -and $null -ne $r.Root -and $r.Root.State -eq [R2HandleState]::LIVE){
                $r.RootTerminationAttempted=$true
                $f=Invoke-R2ProcessNative $Context ([R2ApiId]::TerminateProcess) @($r.Root,$ExitCode);Retain-R2NativeFact $Context $f;$r.Facts.Add($f)
                if($f.RawStatus -eq 0){Stop-R2Guard $Context 'External' 'R2_ROOT_TERMINATION_FAILED' $f.StatusBits $r.Root.IssuerSerial}
            }
            return 'REQUESTED'
        }
        function Read-R2FixedJobProcessSet($Context,$Job,$Buffer,$Length) {
            $f=Invoke-R2ProcessNative $Context ([R2ApiId]::QueryInformationJobObject) @($Job,[int]3,$Buffer,[uint32]40,$Length);Assert-R2ProcessBool $Context $f 'R2_OWNED_JOB_PROCESS_SET'
            $assigned=Get-R2ProcessU32 $Context $Buffer 0;$count=Get-R2ProcessU32 $Context $Buffer 4;$bytes=Get-R2ProcessU32 $Context $Length 0
            if($assigned -ne $count -or $count -gt 4 -or $bytes -lt 8+8*$count -or $bytes -gt 40){Stop-R2ProcessFault $Context 'R2_OWNED_JOB_PROCESS_SET_SIZE' $f}
            $ids=[Collections.Generic.HashSet[uint32]]::new()
            for($i=0;$i -lt $count;$i++){$r2ProcessId=Get-R2ProcessU64 $Context $Buffer ([uint32](8+8*$i));if($r2ProcessId -eq 0 -or $r2ProcessId -gt [uint32]::MaxValue -or -not $ids.Add([uint32]$r2ProcessId)){Stop-R2ProcessFault $Context 'R2_OWNED_JOB_PROCESS_SET_PID' $f}}
            return [pscustomobject]@{Ids=$ids;Fact=$f}
        }
        function Read-R2OwnedThreadsStep($Context) {
            $r=Get-R2ProcessOwnerState $Context
            if(-not ($r.PSObject.Properties.Name -contains 'ThreadScan')){$r | Add-Member -NotePropertyName ThreadScan -NotePropertyValue $null}
            if($null -eq $r.ThreadScan){
                if(-not $r.PSObject.Properties['ThreadPool']){$r | Add-Member -NotePropertyName ThreadPool -NotePropertyValue ([pscustomobject]@{JobList=(New-R2ProcessBuffer $Context 40);ExternalJobList=(New-R2ProcessBuffer $Context 40);Length=(New-R2ProcessBuffer $Context 4);Entry=(New-R2ProcessBuffer $Context 28);Released=$false})}
                if($r.ThreadPool.Released){Stop-R2ProcessFault $Context 'R2_THREAD_POOL_CONSUMED'}
                $b=$r.ThreadPool.JobList;$len=$r.ThreadPool.Length
                $prepSet=Read-R2FixedJobProcessSet $Context $r.Prep $b $len
                $externalSet=Read-R2FixedJobProcessSet $Context $r.External $r.ThreadPool.ExternalJobList $len
                $snapshot=New-R2ProcessHandle $Context ([R2HandleKind]::SNAPSHOT);$f=Invoke-R2ProcessNative $Context ([R2ApiId]::CreateToolhelp32Snapshot) @([uint32]4,[uint32]0);Assert-R2ProcessHandle $Context $snapshot $f
                $entry=$r.ThreadPool.Entry;Set-R2ProcessU32 $Context $entry 0 28
                $r.ThreadScan=[pscustomobject]@{Snapshot=$snapshot;Entry=$entry;Pids=$prepSet.Ids;ExternalPids=$externalSet.Ids;First=$true;Count=0;Prep=[Collections.Generic.List[object]]::new();External=[Collections.Generic.List[object]]::new();Seen=[Collections.Generic.HashSet[uint32]]::new();QpcBegin=$prepSet.Fact.QpcBegin;Facts=[Collections.Generic.List[object]]::new()}
                Add-R2ProcessStatusSummary $r.ThreadScan.Facts $prepSet.Fact;Add-R2ProcessStatusSummary $r.ThreadScan.Facts $externalSet.Fact;Add-R2ProcessStatusSummary $r.ThreadScan.Facts $f
                return 'PENDING'
            }
            $s=$r.ThreadScan
            # Four entries per ordinary guard step, including all charged clock
            # calls. This PowerShell scan is not the native C 12-call observer.
            # The caller keeps independent observations running between steps.
            for($j=0;$j -lt 4;$j++){
                $api=if($s.First){[R2ApiId]::Thread32First}else{[R2ApiId]::Thread32Next};$s.First=$false
                Set-R2ProcessU32 $Context $s.Entry 0 28;$f=Invoke-R2ProcessNative $Context $api @($s.Snapshot,$s.Entry);Add-R2ProcessStatusSummary $s.Facts $f
                if($f.RawStatus -eq 0){
                    if($f.StatusBits -ne 18){Stop-R2ProcessFault $Context 'R2_THREAD_ENUM_STATUS' $f}
                    $prepSet=Read-R2FixedJobProcessSet $Context $r.Prep $r.ThreadPool.JobList $r.ThreadPool.Length
                    $externalSet=Read-R2FixedJobProcessSet $Context $r.External $r.ThreadPool.ExternalJobList $r.ThreadPool.Length
                    Add-R2ProcessStatusSummary $s.Facts $prepSet.Fact;Add-R2ProcessStatusSummary $s.Facts $externalSet.Fact
                    if(-not $s.Pids.SetEquals($prepSet.Ids) -or -not $s.ExternalPids.SetEquals($externalSet.Ids)){Stop-R2ProcessFault $Context 'R2_THREAD_COHORT_CHANGED'}
                    $q=Get-R2NativeQpc $Context
                    if(([bigint]$q-$s.QpcBegin)*10 -gt $Context.Frequency){Stop-R2ProcessFault $Context 'R2_THREAD_OBSERVATION_STALE' $f}
                    $null=Consume-R2Handle $Context $s.Snapshot
                    $result=New-R2ProcessView (New-R2ProcessMap @{QpcBegin=$s.QpcBegin;QpcEnd=$q;PrepThreads=$s.Prep.AsReadOnly();ExternalThreads=$s.External.AsReadOnly();NativeStatuses=$s.Facts.AsReadOnly()});$r.ThreadScan=$null
                    return ,$result
                }
                $s.Count++;if($s.Count -gt 4096){Stop-R2ProcessFault $Context 'R2_THREAD_ENUM_BOUND' $f}
                $tid=Get-R2ProcessU32 $Context $s.Entry 8;$r2ProcessId=Get-R2ProcessU32 $Context $s.Entry 12
                if($tid -eq 0 -or -not $s.Seen.Add($tid)){Stop-R2ProcessFault $Context 'R2_THREAD_ENUM_ID' $f}
                $row=New-R2ProcessView (New-R2ProcessMap @{Tid=$tid;OwnerPid=$r2ProcessId;NativeStatus=(Get-R2ProcessFactSummary $f)})
                if($s.Pids.Contains($r2ProcessId)){$s.Prep.Add($row);if($s.Prep.Count -gt 4){Stop-R2ProcessFault $Context 'R2_PREP_MONITORED_THREADS_4' $f}}
                else{
                    if($s.ExternalPids.Contains($r2ProcessId)){$s.External.Add($row)}
                }
            }
            return 'PENDING'
        }
        function Get-R2RootPidCached($Context) {
            $r=Get-R2ProcessOwnerState $Context
            if($null -eq $r.RootPid){
                $f=Invoke-R2ProcessNative $Context ([R2ApiId]::GetProcessId) @($r.Root)
                if($f.RawStatus -eq 0){Stop-R2ProcessFault $Context 'R2_ROOT_PID' $f}
                $r.RootPid=[uint32]$f.RawStatus
            }
            return [uint32]$r.RootPid
        }

        function Get-R2BootstrapOwner($Quarantine,$Interop) {
            Assert-R2BootstrapQuarantineReference $Quarantine
            if($null -eq $script:bootstrap){
                if(-not [object]::ReferenceEquals($Quarantine.PlanReference,(Get-R2InteropPlanReference $Interop))){throw 'R2_BOOTSTRAP_PLAN_IDENTITY'}
                $script:bootstrap=[pscustomobject]@{Quarantine=$Quarantine;Interop=$Interop;Stage=0;Fault=$null;Data=$null;Count=$null;Times=$null;Entry=$null;Overlapped=$null;Event=$null;Reader=(Get-R2BootstrapInheritedReader $Quarantine);Current=$null;Root=$null;Jobs=$null;StopEvent=$null;Client=$null;Snapshot=$null;SnapshotFirst=$true;SnapshotCount=0;SelfCount=0;SelfPid=$null;SelfCreation=$null;ParentPid=$null;Boot=$null;Payload=$null;Sid=$null;RootPid=$null;RootCreation=$null;Role=$null;Slot=$null;Nonce=$null;WireSerial=$null;Candidates=[Collections.Generic.List[object]]::new();Proof=$null;Context=$null;ReadIssued=$false;ReadPending=$false;ReadCompleted=$false;Incoming=[byte[]]::new(4096);IncomingCount=0;IncomingLength=64;LocalPeer=$null;QpcAfterEcho=$null}
            }
            if(-not [object]::ReferenceEquals($script:bootstrap.Quarantine,$Quarantine) -or -not [object]::ReferenceEquals($script:bootstrap.Interop,$Interop)){throw 'R2_BOOTSTRAP_OWNER_SUBSTITUTION'}
            if($script:bootstrap.Fault){throw $script:bootstrap.Fault}
            return $script:bootstrap
        }
        function Invoke-R2PeerBootstrapNative($b,[R2ApiId]$Api,[object[]]$Arguments) {
            return ,(Invoke-R2BootstrapNative $b.Quarantine $b.Interop $Api $Arguments)
        }
        function Assert-R2BootstrapBool($Fact,[string]$Code){if($Fact.RawStatus -eq 0){throw $Code}}
        function Read-R2BootstrapU32($b,$Buffer,[uint32]$Offset){return [BitConverter]::ToUInt32([byte[]](Read-R2BootstrapBuffer $b.Quarantine $Buffer $Offset 4),0)}
        function Read-R2BootstrapU64($b,$Buffer,[uint32]$Offset){return [BitConverter]::ToUInt64([byte[]](Read-R2BootstrapBuffer $b.Quarantine $Buffer $Offset 8),0)}
        function Read-R2BootstrapCreation($b,$Handle) {
            $refs=@();for($i=0;$i -lt 4;$i++){$refs+=,(Get-R2BootstrapBufferSlice $b.Quarantine $b.Times ([uint32](8*$i)) 8)}
            $f=Invoke-R2PeerBootstrapNative $b ([R2ApiId]::GetProcessTimes) @($Handle,$refs[0],$refs[1],$refs[2],$refs[3]);Assert-R2BootstrapBool $f 'R2_BOOTSTRAP_CREATION_NATIVE'
            $v=Read-R2BootstrapU64 $b $b.Times 0;if($v -eq 0){throw 'R2_BOOTSTRAP_CREATION_ZERO'}
            return $v
        }
        function Assert-R2BootstrapRootLive($b) {
            $f=Invoke-R2PeerBootstrapNative $b ([R2ApiId]::GetProcessId) @($b.Root)
            if($f.RawStatus -ne $b.ParentPid -or $f.RawStatus -ne $b.RootPid){throw 'R2_BOOTSTRAP_ROOT_PARENT_ID'}
            $v=Read-R2BootstrapCreation $b $b.Root
            if($v -ne $b.RootCreation -or $v -gt $b.SelfCreation){throw 'R2_BOOTSTRAP_ROOT_CREATION'}
            $f=Invoke-R2PeerBootstrapNative $b ([R2ApiId]::WaitForSingleObject) @($b.Root,[uint32]0)
            if($f.RawStatus -ne 258){throw 'R2_BOOTSTRAP_ROOT_NOT_LIVE'}
        }
        function Read-R2BootstrapCurrentSid($b) {
            $out=Get-R2BootstrapBufferSlice $b.Quarantine $b.Times 0 8
            $f=Invoke-R2PeerBootstrapNative $b ([R2ApiId]::OpenProcessToken) @($b.Current,[uint32]8,$out);Assert-R2BootstrapBool $f 'R2_BOOTSTRAP_TOKEN_OPEN'
            $token=$f.AcquiredHandles[0]
            $f=Invoke-R2PeerBootstrapNative $b ([R2ApiId]::GetTokenInformation) @($token,[int]1,[IntPtr]::Zero,[uint32]0,$b.Count)
            $n=Read-R2BootstrapU32 $b $b.Count 0
            if($f.RawStatus -ne 0 -or $f.StatusBits -ne 122 -or $n -lt 16 -or $n -gt 4096){throw 'R2_BOOTSTRAP_TOKEN_SIZE'}
            $tokenCapacity=$n;$tokenBuffer=Get-R2BootstrapBufferSlice $b.Quarantine $b.Data 0 $n
            $f=Invoke-R2PeerBootstrapNative $b ([R2ApiId]::GetTokenInformation) @($token,[int]1,$tokenBuffer,$n,$b.Count);Assert-R2BootstrapBool $f 'R2_BOOTSTRAP_TOKEN_READ'
            $n=Read-R2BootstrapU32 $b $b.Count 0;$sidAddress=Read-R2BootstrapU64 $b $b.Data 0;$base=[uint64]$b.Data.Address.ToInt64()
            if($n -lt 16 -or $n -gt $tokenCapacity -or [bigint]$sidAddress -lt $base -or [bigint]$sidAddress+8 -gt [bigint]$base+$n){throw 'R2_BOOTSTRAP_TOKEN_SID_RANGE'}
            $o=[uint32]($sidAddress-$base);$header=[byte[]](Read-R2BootstrapBuffer $b.Quarantine $b.Data $o 8);$length=[uint32](8+4*$header[1])
            if($header[0] -ne 1 -or $header[1] -gt 15 -or [bigint]$o+$length -gt $n){throw 'R2_BOOTSTRAP_TOKEN_SID_FORMAT'}
            $actual=[byte[]](Read-R2BootstrapBuffer $b.Quarantine $b.Data $o $length)
            if($actual.Length -ne $b.Sid.Length){throw 'R2_BOOTSTRAP_TOKEN_SID_LENGTH'}
            for($i=0;$i -lt $actual.Length;$i++){if($actual[$i] -ne $b.Sid[$i]){throw 'R2_BOOTSTRAP_TOKEN_SID_MISMATCH'}}
            $null=Close-R2BootstrapHandle $b.Quarantine $b.Interop $token
        }
        function Read-R2BootstrapEchoStep($b) {
            if(-not $b.ReadIssued){
                $remaining=[uint32]($b.IncomingLength-$b.IncomingCount)
                $f=Invoke-R2PeerBootstrapNative $b ([R2ApiId]::ReadFile) @($b.Client,$b.Data,$remaining,$b.Count,$b.Overlapped)
                $b.ReadIssued=$true
                if($f.RawStatus -eq 0){if($f.StatusBits -ne 997){throw 'R2_BOOTSTRAP_ECHO_READ'};$b.ReadPending=$true;return 'PENDING'}
            }
            if($b.ReadPending){
                $f=Invoke-R2PeerBootstrapNative $b ([R2ApiId]::GetOverlappedResult) @($b.Client,$b.Overlapped,$b.Count,[int]0)
                if($f.RawStatus -eq 0 -and $f.StatusBits -eq 996){return 'PENDING'}
                Assert-R2BootstrapBool $f 'R2_BOOTSTRAP_ECHO_COMPLETION';$b.ReadPending=$false
            }
            $n=Read-R2BootstrapU32 $b $b.Count 0
            if($n -eq 0 -or $n -gt $b.IncomingLength-$b.IncomingCount){throw 'R2_BOOTSTRAP_ECHO_LENGTH'}
            $bytes=[byte[]](Read-R2BootstrapBuffer $b.Quarantine $b.Data 0 $n);[Array]::Copy($bytes,0,$b.Incoming,$b.IncomingCount,$bytes.Length);$b.IncomingCount+=$bytes.Length;$b.ReadIssued=$false
            if($b.IncomingCount -eq 64 -and $b.IncomingLength -eq 64){
                $length=[BitConverter]::ToUInt32($b.Incoming,0);if($length -lt 64 -or $length -gt 4096){throw 'R2_BOOTSTRAP_ECHO_SIZE'};$b.IncomingLength=[int]$length
            }
            if($b.IncomingCount -lt $b.IncomingLength){
                # The previous read completed before this OVERLAPPED is reset.
                Write-R2BootstrapBuffer $b.Quarantine $b.Overlapped 0 ([byte[]]::new(32));Write-R2BootstrapReference $b.Quarantine $b.Overlapped 24 $b.Event
                return 'PENDING'
            }
            $wire=$b.Incoming
            if([BitConverter]::ToUInt16($wire,4) -ne 1 -or [BitConverter]::ToUInt16($wire,6) -ne 3 -or [BitConverter]::ToUInt64($wire,8) -ne 2 -or [BitConverter]::ToUInt64($wire,24) -ne $b.WireSerial -or $b.IncomingLength -ne 64+$b.Payload.Length){throw 'R2_BOOTSTRAP_ECHO_BINDING'}
            for($i=0;$i -lt 32;$i++){if($wire[32+$i] -ne $b.Nonce[$i]){throw 'R2_BOOTSTRAP_ECHO_NONCE'}}
            for($i=0;$i -lt $b.Payload.Length;$i++){if($wire[64+$i] -ne $b.Payload[$i]){throw 'R2_BOOTSTRAP_ECHO_DUPLICATION_SERIALS'}}
            $sender=[BitConverter]::ToInt64($wire,16);$now=[long]$f.QpcEnd;$hz=[BitConverter]::ToInt64($b.Payload,40)
            if($sender -lt [BitConverter]::ToInt64($b.Payload,32) -or $sender -gt $now -or ([bigint]$now-$sender)*10 -gt $hz){throw 'R2_BOOTSTRAP_ECHO_NOT_FRESH'}
            Retain-R2BootstrapNativeFact $b.Quarantine $f
            Assert-R2BootstrapRootLive $b
            $b.QpcAfterEcho=$now;$b.ReadCompleted=$true
            return 'VERIFIED'
        }
        function Assert-R2BootstrapAdmissionProof($Quarantine,$Proof) {
            Assert-R2BootstrapQuarantineReference $Quarantine
            foreach($p in $script:proofs){
                if([object]::ReferenceEquals($p.View,$Proof) -and [object]::ReferenceEquals($p.Quarantine,$Quarantine) -and [object]::ReferenceEquals($p.Owner,$script:bootstrap) -and $p.Owner.ReadCompleted -and $p.Owner.Stage -ge 5 -and -not $p.Owner.Fault){return}
            }
            throw 'R2_BOOTSTRAP_UNISSUED_PROOF'
        }
        function Get-R2BootstrapAdmissionFields($Quarantine,$Proof) {
            Assert-R2BootstrapAdmissionProof $Quarantine $Proof
            foreach($p in $script:proofs){if([object]::ReferenceEquals($p.View,$Proof)){return ,$p.Fields}}
            throw 'R2_BOOTSTRAP_FIELDS_MISSING'
        }
        function Consume-R2PeerBootstrap($Quarantine,$Interop) {
            $b=Get-R2BootstrapOwner $Quarantine $Interop
            if($null -ne $b.Context){return ,$b.Context}
            Enter-R2BootstrapStep $Quarantine $false
            try{return ,(Consume-R2PeerBootstrapStep $b)}catch{$b.Fault='R2_BOOTSTRAP_PROCESS_FAILURE';throw}
            finally{Complete-R2BootstrapStepIfActive $Quarantine}
        }
        function Consume-R2PeerBootstrapStep($b) {
            $q=$b.Quarantine
            if($null -ne $b.Context){return ,$b.Context}
            if($b.Stage -eq 0){
                $b.Data=New-R2BootstrapBuffer $q 4096 8;$b.Count=New-R2BootstrapBuffer $q 4 8;$b.Times=New-R2BootstrapBuffer $q 32 8;$b.Entry=New-R2BootstrapBuffer $q 568 8;$b.Overlapped=New-R2BootstrapBuffer $q 32 8
                $f=Invoke-R2PeerBootstrapNative $b ([R2ApiId]::ReadFile) @($b.Reader,$b.Data,[uint32]4096,$b.Count,[IntPtr]::Zero);Assert-R2BootstrapBool $f 'R2_BOOTSTRAP_ANONYMOUS_READ'
                $n=Read-R2BootstrapU32 $b $b.Count 0
                if($n -lt 208 -or $n -gt 4096){throw 'R2_BOOTSTRAP_ANONYMOUS_SIZE'}
                $wire=[byte[]](Read-R2BootstrapBuffer $q $b.Data 0 $n)
                if([BitConverter]::ToUInt32($wire,0) -ne $n -or [BitConverter]::ToUInt16($wire,4) -ne 1 -or [BitConverter]::ToUInt16($wire,6) -ne 1 -or [BitConverter]::ToUInt64($wire,8) -ne 1){throw 'R2_BOOTSTRAP_ANONYMOUS_HEADER'}
                $payload=[byte[]]::new($n-64);[Array]::Copy($wire,64,$payload,0,$payload.Length);$b.Payload=$payload;$b.Boot=$wire
                $nameLength=[BitConverter]::ToUInt32($payload,128);$sidLength=[BitConverter]::ToUInt32($payload,140)
                if($nameLength -lt 20 -or $nameLength -gt 512 -or $nameLength%2 -ne 0 -or $sidLength -lt 8 -or $sidLength -gt 68 -or 144+$sidLength+$nameLength -ne $payload.Length){throw 'R2_BOOTSTRAP_NAME_SID_LENGTH'}
                $nameOffset=144+[int]$sidLength;$name=[Text.Encoding]::Unicode.GetString($payload,$nameOffset,[int]$nameLength-2)
                if($payload[$payload.Length-1] -ne 0 -or $payload[$payload.Length-2] -ne 0 -or $name.IndexOf([char]0) -ge 0 -or -not $name.StartsWith('\\.\pipe\r2-',[StringComparison]::Ordinal)){throw 'R2_BOOTSTRAP_PIPE_NAME'}
                $b | Add-Member -NotePropertyName PipeName -NotePropertyValue $name
                $b.Sid=[byte[]]::new($sidLength);[Array]::Copy($payload,144,$b.Sid,0,$sidLength)
                if($b.Sid[0] -ne 1 -or $b.Sid[1] -gt 15 -or 8+4*$b.Sid[1] -ne $sidLength){throw 'R2_BOOTSTRAP_SID_FORMAT'}
                $b.Nonce=[byte[]]::new(32);[Array]::Copy($wire,32,$b.Nonce,0,32);$b.WireSerial=[BitConverter]::ToUInt64($wire,24)
                $hex=([BitConverter]::ToString($b.Nonce)).Replace('-','').ToLowerInvariant();$expectedName='\\.\pipe\r2-'+$hex+'-'+$b.WireSerial.ToString([Globalization.CultureInfo]::InvariantCulture)
                if($name -cne $expectedName){throw 'R2_BOOTSTRAP_ENDPOINT_BINDING'}
                $b.RootPid=[BitConverter]::ToUInt32($payload,0);$b.RootCreation=[BitConverter]::ToUInt64($payload,8)
                $role=[BitConverter]::ToUInt32($payload,136);$slotId=[BitConverter]::ToUInt32($payload,132)
                if($role -notin @(1,2,3) -or $b.WireSerial -eq 0){throw 'R2_BOOTSTRAP_ROLE_SERIAL'}
                foreach($slot in $q.PlanReference.Slots){if($slot.Id -eq $slotId){$b.Slot=$slot;break}}
                if($null -eq $b.Slot){throw 'R2_BOOTSTRAP_ORIGINAL_SLOT_ROLE'}
                $plannedRole=if($b.Slot.ContainsKey('ChildRole')){
                    if(-not ($b.Slot.ChildRole -is [R2Role])){throw 'R2_BOOTSTRAP_STATIC_ROLE_TYPE'}
                    [uint32]$b.Slot.ChildRole
                }else{
                    switch -CaseSensitive([string]$b.Slot.ProducerName){'CONTROLLER'{[uint32]1}'WATCHDOG'{[uint32]2}'TRANSPORT'{[uint32]3}default{throw 'R2_BOOTSTRAP_STATIC_ROLE_PRODUCER'}}
                }
                if($plannedRole -ne $role){throw 'R2_BOOTSTRAP_ORIGINAL_SLOT_ROLE'};$b.Role=[R2Role]$plannedRole
                $values=[Collections.Generic.HashSet[long]]::new();$serials=[Collections.Generic.HashSet[uint64]]::new()
                for($i=0;$i -lt 4;$i++){
                    $value=[BitConverter]::ToInt64($payload,64+16*$i);$serial=[BitConverter]::ToUInt64($payload,72+16*$i)
                    if($value -le 0 -or $serial -eq 0 -or -not $values.Add($value) -or -not $serials.Add($serial)){throw 'R2_BOOTSTRAP_DUPLICATE_LOCATORS'}
                    $kind=if($i -eq 0){[R2HandleKind]::PROCESS}elseif($i -eq 3){[R2HandleKind]::EVENT}else{[R2HandleKind]::JOB}
                    $candidate=New-R2BootstrapHandleCandidate $q ([IntPtr]::new($value)) $kind;$b.Candidates.Add($candidate)
                }
                $b.Root=$b.Candidates[0];$b.Jobs=@($b.Candidates[1],$b.Candidates[2]);$b.StopEvent=$b.Candidates[3]
                $f=Invoke-R2PeerBootstrapNative $b ([R2ApiId]::GetCurrentProcess) @();$b.Current=$f.AcquiredHandles[0]
                $f=Invoke-R2PeerBootstrapNative $b ([R2ApiId]::GetProcessId) @($b.Current);$b.SelfPid=[uint32]$f.RawStatus
                $b.SelfCreation=Read-R2BootstrapCreation $b $b.Current
                if($b.SelfPid -eq 0 -or $b.SelfPid -ne [BitConverter]::ToUInt32($payload,16) -or $b.SelfCreation -ne [BitConverter]::ToUInt64($payload,24)){throw 'R2_BOOTSTRAP_SELF_IDENTITY'}
                $f=Invoke-R2PeerBootstrapNative $b ([R2ApiId]::CreateToolhelp32Snapshot) @([uint32]2,[uint32]0)
                if($f.ReturnValue.ToInt64() -eq -1){throw 'R2_BOOTSTRAP_PARENT_SNAPSHOT'};$b.Snapshot=$f.AcquiredHandles[0];$b.Stage=1
                return 'PENDING'
            }
            if($b.Stage -eq 1){
                for($j=0;$j -lt 4;$j++){
                    Write-R2BootstrapBuffer $q $b.Entry 0 ([BitConverter]::GetBytes([uint32]568))
                    $api=if($b.SnapshotFirst){[R2ApiId]::Process32FirstW}else{[R2ApiId]::Process32NextW};$b.SnapshotFirst=$false
                    $f=Invoke-R2PeerBootstrapNative $b $api @($b.Snapshot,$b.Entry)
                    if($f.RawStatus -eq 0){
                        if($f.StatusBits -ne 18 -or $b.SelfCount -ne 1 -or $b.ParentPid -eq 0 -or $b.ParentPid -eq $b.SelfPid){throw 'R2_BOOTSTRAP_PARENT_ENUMERATION'}
                        $null=Close-R2BootstrapHandle $q $b.Interop $b.Snapshot;Assert-R2BootstrapRootLive $b;$b.Stage=2;return 'PENDING'
                    }
                    $b.SnapshotCount++;if($b.SnapshotCount -gt 4096){throw 'R2_BOOTSTRAP_PARENT_ENUMERATION_BOUND'}
                    if((Read-R2BootstrapU32 $b $b.Entry 8) -eq $b.SelfPid){Retain-R2BootstrapNativeFact $q $f;$b.SelfCount++;$b.ParentPid=Read-R2BootstrapU32 $b $b.Entry 32}
                }
                return 'PENDING'
            }
            if($b.Stage -eq 2){
                Read-R2BootstrapCurrentSid $b
                $f=Invoke-R2PeerBootstrapNative $b ([R2ApiId]::CreateFileW) @($b.PipeName,[uint32]3221225472,[uint32]0,[IntPtr]::Zero,[uint32]3,[uint32]1073741824,[IntPtr]::Zero)
                if($f.ReturnValue.ToInt64() -eq -1){throw 'R2_BOOTSTRAP_NAMED_CLIENT_OPEN'};$b.Client=$f.AcquiredHandles[0]
                $f=Invoke-R2PeerBootstrapNative $b ([R2ApiId]::GetNamedPipeServerProcessId) @($b.Client,$b.Count);Assert-R2BootstrapBool $f 'R2_BOOTSTRAP_NAMED_SERVER_PID'
                if((Read-R2BootstrapU32 $b $b.Count 0) -ne $b.ParentPid){throw 'R2_BOOTSTRAP_NAMED_SERVER_PARENT'}
                Assert-R2BootstrapRootLive $b;$b.Stage=3;return 'PENDING'
            }
            if($b.Stage -eq 3){
                Write-R2BootstrapBuffer $q $b.Times 0 ([byte[]]::new(32));Write-R2BootstrapBuffer $q $b.Times 0 ([BitConverter]::GetBytes([uint32]24))
                $sa=Get-R2BootstrapBufferSlice $q $b.Times 0 24
                $f=Invoke-R2PeerBootstrapNative $b ([R2ApiId]::CreateEventW) @($sa,[int]1,[int]0,$null)
                if($f.ReturnValue -eq [IntPtr]::Zero){throw 'R2_BOOTSTRAP_ECHO_EVENT'};$b.Event=$f.AcquiredHandles[0]
                Write-R2BootstrapReference $q $b.Overlapped 24 $b.Event;$b.Stage=4;return 'PENDING'
            }
            if($b.Stage -eq 4){
                if((Read-R2BootstrapEchoStep $b) -cne 'VERIFIED'){return 'PENDING'}
                $b.Stage=5
                $owned=[Collections.Generic.List[object]]::new();$owned.Add($b.Reader);foreach($candidate in $b.Candidates){$owned.Add($candidate)}
                $fields=New-R2ProcessView (New-R2ProcessMap @{Interop=$b.Interop;Q0=[BitConverter]::ToInt64($b.Payload,32);Frequency=[BitConverter]::ToInt64($b.Payload,40);PrepDeadline=[BitConverter]::ToInt64($b.Payload,48);ExternalDeadline=[BitConverter]::ToInt64($b.Payload,56);StudyDeadline=$null;Role=$b.Role;InvocationNonce=[Array]::AsReadOnly([byte[]]$b.Nonce.Clone());OwnedCandidateHandles=$owned.AsReadOnly();OriginalSlotReference=$b.Slot;CurrentSidBytes=[Array]::AsReadOnly([byte[]]$b.Sid.Clone());RootPid=$b.RootPid;RootCreation=$b.RootCreation;SelfPid=$b.SelfPid;SelfCreation=$b.SelfCreation;WireSerial=$b.WireSerial;RootHandle=$b.Root;PrepJobHandle=$b.Jobs[0];ExternalJobHandle=$b.Jobs[1];StopEventHandle=$b.StopEvent;ClientHandle=$b.Client;BorrowedCurrentProcess=$b.Current;EchoNativeFacts=$q.NativeFacts})
                $proof=New-R2ProcessView (New-R2ProcessMap @{QuarantineReference=$q;PlanReference=$q.PlanReference})
                $script:proofs.Add([pscustomobject]@{View=$proof;Quarantine=$q;Owner=$b;Fields=$fields});$b.Proof=$proof
                return 'PENDING'
            }
            if($b.Stage -eq 5){
                # No pending request remains: kernel completion was observed.
                $null=Close-R2BootstrapHandle $q $b.Interop $b.Event
                foreach($buffer in @($b.Data,$b.Count,$b.Times,$b.Entry,$b.Overlapped)){Release-R2BootstrapBuffer $q $buffer}
                $b.Context=New-R2PeerLedger $b.Proof $q.PlanReference $b.Interop;$b.Stage=6
                return ,$b.Context
            }
            throw 'R2_BOOTSTRAP_INVALID_STAGE'
        }
        function Get-R2LocalPeer($Context) {
            Assert-R2ContextReference $Context
            [void](Assert-R2ObservationOrigin $Context (Get-R2ObservationOrigin $Context))
            $b=$script:bootstrap
            if($null -eq $b -or $b.Stage -ne 6 -or -not [object]::ReferenceEquals($Context,$b.Context)){throw 'R2_LOCAL_PEER_ADMISSION_REQUIRED'}
            Assert-R2BootstrapAdmissionProof $b.Quarantine $b.Proof
            if($null -ne $b.LocalPeer){return ,$b.LocalPeer}
            $slot=Get-R2CurrentSlot $Context
            if(-not [object]::ReferenceEquals($slot,$b.Slot)){throw 'R2_LOCAL_PEER_SLOT_BINDING'}
            $r=Get-R2ProcessOwnerState $Context
            $r.Current=Get-R2PromotedBootstrapHandle $Context $b.Quarantine $b.Current
            $r.Root=Get-R2PromotedBootstrapHandle $Context $b.Quarantine $b.Root
            $r.Prep=Get-R2PromotedBootstrapHandle $Context $b.Quarantine $b.Jobs[0]
            $r.External=Get-R2PromotedBootstrapHandle $Context $b.Quarantine $b.Jobs[1]
            $r.StopEvent=Get-R2PromotedBootstrapHandle $Context $b.Quarantine $b.StopEvent
            $reader=Get-R2PromotedBootstrapHandle $Context $b.Quarantine $b.Reader
            if($reader.State -eq [R2HandleState]::LIVE){$null=Consume-R2Handle $Context $reader}
            $pipe=Get-R2PromotedBootstrapHandle $Context $b.Quarantine $b.Client
            $facts=[Collections.Generic.List[object]]::new()
            # CHILD ENDPOINT is a separate local record, never a reconstructed
            # root R2OwnedChild/R2Peer. Its issuer consumes only the retained
            # native proof and original promoted references above.
            $identity=Reserve-R2ComponentIdentity $Context $slot 'Peer'
            $d=New-R2ProcessMap @{IssuerIdentity=$identity.IssuerIdentity;IssuerSerial=$identity.IssuerSerial;ContextReference=$Context;PlanReference=$Context.PlanReference;OriginalSlotReference=$slot;PrepDeadline=$Context.PrepDeadline;ExternalDeadline=$Context.ExternalDeadline;StudyDeadline=$Context.StudyDeadline;DeadlineOwnerReference=$Context;LocalEndpointKind='CHILD_ENDPOINT';ActualSelfPid=$b.SelfPid;ActualSelfCreationFileTime=$b.SelfCreation;KernelParentPid=$b.ParentPid;RawRootChildWireSerial=$b.WireSerial;OriginalRootProcessReference=$r.Root;RootHandle=$r.Root;PrepJobHandle=$r.Prep;ExternalJobHandle=$r.External;StopEventHandle=$r.StopEvent;PipeHandle=$pipe;CurrentSidBytes=[Array]::AsReadOnly([byte[]]$b.Sid.Clone());InvocationNonce=(Get-R2InvocationNonce $Context);TxSequence=[uint64]0;RxSequence=[uint64]2;PendingConnect=$null;PendingRead=$null;PendingWrite=$null;LastHeartbeatQpc=$null;HeartbeatDueQpc=$null;PipeState=[R2PipeState]::CONNECTED_VERIFIED;State=[R2PeerState]::CONNECTED_VERIFIED;ConnectionCount=[uint32]1;NativeFacts=$facts.AsReadOnly();BootstrapNativeFacts=$b.Quarantine.NativeFacts}
            $p=[pscustomobject]@{Kind='LocalPeer';Data=$d;View=(New-R2ProcessView $d);Private=(New-R2ProcessMap @{Facts=$facts;RootSide=$false;WireSerial=$b.WireSerial;IncomingCount=0;IncomingLength=64;Incoming=[byte[]]::new(4096);EofExpected=$false;EofFact=$null;NativeConnectionObserved=[R2Fact]::TRUE;DisconnectAttempted=$false;CleanupReadStopped=$false;CleanupUnknown=$false;CleanupComplete=$false;BootstrapWritten=$true;EchoSent=$true})}
            $script:records.Add($p.View,$p);$b.LocalPeer=$p.View;$r.LocalPeer=$p.View
            return ,$p.View
        }
        Export-ModuleMember -Function New-R2RoleJobs,New-R2ChildReservation,New-R2SuspendedChild,Confirm-R2Birth,Resume-R2OwnedChild,New-R2Peer,New-R2PendingIo,Send-R2PeerFrame,Receive-R2PeerFrame,Join-R2OwnedChildStep,Request-R2ChildTermination,Request-R2RoleStop,Request-R2ExternalJobTermination,Invoke-R2TerminationFallbackStep,Invoke-R2ExternalTerminationFallbackStep,Close-R2PeerStep,Close-R2ProcessBuffersStep,Read-R2OwnedThreadsStep,Get-R2OwnedProcessSnapshot,Get-R2ProcessProgress,Assert-R2PeerReference,Assert-R2ChildReference,Consume-R2PeerBootstrap,Assert-R2BootstrapAdmissionProof,Get-R2BootstrapAdmissionFields,Get-R2LocalPeer
    }
    Import-Module $owner -Global -Force
}

function New-R2RoleJobs {
    param([Parameter(Mandatory)][object]$Context)
    Initialize-R2ProcessOwner
    Route2OriginalProcess\New-R2RoleJobs $Context
}

function Consume-R2PeerBootstrap {
    param([Parameter(Mandatory)][object]$Quarantine,[Parameter(Mandatory)][object]$Interop)
    Initialize-R2ProcessOwner
    Route2OriginalProcess\Consume-R2PeerBootstrap $Quarantine $Interop
}
