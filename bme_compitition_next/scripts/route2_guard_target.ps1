# SOURCE ONLY. Read-only Windows parent/volume portion of the qualified target
# contract. No file creation, volume mutation, guest call or cross-OS identity
# producer is implemented here. Loading this file defines functions only.
# Drive the continuations in ordinary original ledger steps. Each transition
# performs at most one native query; a whole validation still has <=100 ms.

function Initialize-R2TargetParentOwner {
    if (Get-Module -Name Route2OriginalTargetParent) { return }
    $module = New-Module -Name Route2OriginalTargetParent -ScriptBlock {
        $script:state = $null
        $script:issuer = [object]::new()
        $script:records = [Runtime.CompilerServices.ConditionalWeakTable[object,object]]::new()
        $script:thread = [Threading.Thread]::CurrentThread.ManagedThreadId

        function New-R2TargetMap([hashtable]$Fields) {
            $data = [Collections.Generic.Dictionary[string,object]]::new([StringComparer]::Ordinal)
            foreach ($key in $Fields.Keys) { $data.Add([string]$key,$Fields[$key]) }
            return ,$data
        }
        function New-R2TargetView($Data) {
            return ,([Collections.ObjectModel.ReadOnlyDictionary[string,object]]::new($Data))
        }
        function Stop-R2TargetFault($Context,[string]$Code,$Fact=$null) {
            $status=$null; $serial=[uint64]0
            if ($null -ne $Fact) {
                Retain-R2NativeFact $Context $Fact
                $status=$Fact.StatusBits; $serial=$Fact.IssuerSerial
            }
            Stop-R2Guard $Context 'External' $Code $status $serial
            throw $Code
        }
        function Get-R2TargetState($Context) {
            Assert-R2ContextReference $Context
            if ([Threading.Thread]::CurrentThread.ManagedThreadId -ne $script:thread) { throw 'R2_TARGET_OWNER_THREAD' }
            if ($null -ne $script:state -and -not [object]::ReferenceEquals($script:state.Context,$Context)) {
                Stop-R2TargetFault $Context 'R2_TARGET_CONTEXT_SUBSTITUTION'
            }
            return $script:state
        }
        function Assert-R2TargetWork($Context) {
            if ($Context.StopState -eq [R2Fact]::TRUE) { throw 'R2_TARGET_STOP_LATCHED' }
            $slot=Get-R2CurrentSlot $Context
            Assert-R2PlanSlot $Context $slot
            # Native/allocator dispatch validates the original current operation.
            # Do not invent Operation=0 when the manifest chose another ID.
        }
        function Get-R2TargetRecord($Context,$Reference,[string]$Kind) {
            $state=Get-R2TargetState $Context; $entry=$null
            if ($null -eq $state -or $null -eq $Reference -or -not $script:records.TryGetValue($Reference,[ref]$entry)) {
                Stop-R2TargetFault $Context 'R2_TARGET_UNISSUED_REFERENCE'
            }
            if ($entry.Kind -cne $Kind -or -not [object]::ReferenceEquals($entry.Data.ContextReference,$Context) -or
                -not [object]::ReferenceEquals($entry.Data.PrivateIssuer,$script:issuer)) {
                Stop-R2TargetFault $Context 'R2_TARGET_REFERENCE_BINDING'
            }
            return $entry
        }
        function New-R2TargetRecord($Context,[string]$Kind,[hashtable]$Fields) {
            $state=Get-R2TargetState $Context
            $data=New-R2TargetMap $Fields
            $data['PrivateIssuer']=$script:issuer; $data['ContextReference']=$Context
            $data['PlanReference']=$Context.PlanReference; $data['IssuerSerial']=$state.Identity.IssuerSerial
            $entry=[pscustomobject]@{Kind=$Kind;Data=$data;View=(New-R2TargetView $data)}
            $script:records.Add($entry.View,$entry)
            return $entry
        }
        function Read-R2TargetBytes($Context,$Slice,[uint32]$Count) {
            return ,([byte[]](Read-R2NativeBuffer $Context $Slice.BufferOwnerReference $Slice.Offset $Count))
        }
        function Get-R2TargetGuidRoot($Context,[byte[]]$Bytes) {
            if (($Bytes.Length % 2) -ne 0) { Stop-R2TargetFault $Context 'R2_TARGET_ODD_UTF16' }
            $text=[Text.Encoding]::Unicode.GetString($Bytes); $end=$text.IndexOf([char]0)
            if ($end -lt 0) { Stop-R2TargetFault $Context 'R2_TARGET_UNTERMINATED_PATH' }
            $name=$text.Substring(0,$end)
            if ($name.Length -ne 49 -or -not $name.StartsWith('\\?\Volume{',[StringComparison]::OrdinalIgnoreCase) -or
                $name.Substring(47) -cne '}\') { Stop-R2TargetFault $Context 'R2_TARGET_NONCANONICAL_GUID' }
            $guid=[Guid]::Empty
            if (-not [Guid]::TryParseExact($name.Substring(11,36),'D',[ref]$guid)) { Stop-R2TargetFault $Context 'R2_TARGET_BAD_GUID' }
            return $name
        }
        function Invoke-R2TargetNative($Context,[R2ApiId]$Api,[object[]]$Arguments) {
            return ,(Invoke-R2NativeCall $Context $Api $Arguments)
        }
        function Assert-R2TargetBool($Context,$Fact,[string]$Code) {
            if ($Fact.RawStatus -eq 0) { Stop-R2TargetFault $Context $Code $Fact }
        }
        function Get-R2TargetStatus($Fact) {
            return ,(New-R2TargetView (New-R2TargetMap @{ApiId=$Fact.ApiId;RawStatus=$Fact.RawStatus;StatusBits=$Fact.StatusBits;QpcBegin=$Fact.QpcBegin;QpcEnd=$Fact.QpcEnd;IssuerSerial=$Fact.IssuerSerial}))
        }
        function Read-R2TargetIdentityStage($Context,$State,[int]$Stage,[bool]$Original) {
            # Original handle continuity is required for every readback. No path
            # is reopened and a wire-provided integer cannot replace this handle.
            if ($State.Parent.State -ne [R2HandleState]::LIVE) { Stop-R2TargetFault $Context 'R2_TARGET_PARENT_NOT_LIVE' }
            switch ($Stage) {
                0 {
                    $fact=Invoke-R2TargetNative $Context ([R2ApiId]::GetFileInformationByHandleEx) @($State.Parent,[int]18,$State.Slices.Id,[uint32]24)
                    Assert-R2TargetBool $Context $fact 'R2_TARGET_FILE_ID_FAILED'
                    $bytes=Read-R2TargetBytes $Context $State.Slices.Id 24
                    $volume=[BitConverter]::ToUInt64($bytes,0)
                    $id=[BitConverter]::ToString($bytes,8,16)
                    if ($Original) { $State.VolumeSerial=$volume; $State.FileId=$id }
                    elseif ($State.VolumeSerial -ne $volume -or $State.FileId -cne $id) { Stop-R2TargetFault $Context 'R2_TARGET_FILE_ID_CHANGED' $fact }
                }
                1 {
                    $fact=Invoke-R2TargetNative $Context ([R2ApiId]::GetFileInformationByHandleEx) @($State.Parent,[int]1,$State.Slices.Standard,[uint32]24)
                    Assert-R2TargetBool $Context $fact 'R2_TARGET_STANDARD_INFO_FAILED'
                    $bytes=Read-R2TargetBytes $Context $State.Slices.Standard 24
                    $allocation=[BitConverter]::ToInt64($bytes,0); $eof=[BitConverter]::ToInt64($bytes,8)
                    if ($allocation -lt 0 -or $eof -lt 0 -or [BitConverter]::ToUInt32($bytes,16) -ne 1 -or $bytes[20] -ne 0 -or $bytes[21] -ne 1) {
                        Stop-R2TargetFault $Context 'R2_TARGET_PARENT_STANDARD_INVALID' $fact
                    }
                    $State.LastAllocation=$allocation; $State.LastEof=$eof
                }
                2 {
                    $fact=Invoke-R2TargetNative $Context ([R2ApiId]::GetFileInformationByHandleEx) @($State.Parent,[int]9,$State.Slices.Tag,[uint32]8)
                    Assert-R2TargetBool $Context $fact 'R2_TARGET_TAG_INFO_FAILED'
                    $bytes=Read-R2TargetBytes $Context $State.Slices.Tag 8
                    $attributes=[BitConverter]::ToUInt32($bytes,0)
                    if (($attributes -band 0x400) -ne 0 -or ($attributes -band 0x10) -eq 0 -or [BitConverter]::ToUInt32($bytes,4) -ne 0) {
                        Stop-R2TargetFault $Context 'R2_TARGET_REPARSE_OR_NOT_DIRECTORY' $fact
                    }
                }
                3 {
                    $fact=Invoke-R2TargetNative $Context ([R2ApiId]::GetFinalPathNameByHandleW) @($State.Parent,$State.Slices.Path,[uint32]1024,[uint32]1)
                    if ($fact.RawStatus -eq 0 -or $fact.RawStatus -ge 1024) { Stop-R2TargetFault $Context 'R2_TARGET_FINAL_PATH_FAILED' $fact }
                    $name=Get-R2TargetGuidRoot $Context (Read-R2TargetBytes $Context $State.Slices.Path 2048)
                    if ($fact.RawStatus -ne $name.Length) { Stop-R2TargetFault $Context 'R2_TARGET_FINAL_PATH_LENGTH' $fact }
                    if ($Original) { $State.VolumeGuid=$name }
                    elseif (-not [string]::Equals($State.VolumeGuid,$name,[StringComparison]::OrdinalIgnoreCase)) { Stop-R2TargetFault $Context 'R2_TARGET_VOLUME_CHANGED' $fact }
                }
                4 {
                    $fact=Invoke-R2TargetNative $Context ([R2ApiId]::GetVolumeNameForVolumeMountPointW) @('E:\',$State.Slices.Mapping,[uint32]1024)
                    Assert-R2TargetBool $Context $fact 'R2_TARGET_E_MAPPING_FAILED'
                    $name=Get-R2TargetGuidRoot $Context (Read-R2TargetBytes $Context $State.Slices.Mapping 2048)
                    if (-not [string]::Equals($State.VolumeGuid,$name,[StringComparison]::OrdinalIgnoreCase)) { Stop-R2TargetFault $Context 'R2_TARGET_E_MAPPING_CHANGED' $fact }
                }
                default { Stop-R2TargetFault $Context 'R2_TARGET_IDENTITY_STAGE' }
            }
            if ($Original) { Retain-R2NativeFact $Context $fact; $State.IdentityFacts.Add($fact) }
            return ,$fact
        }
        function Assert-R2TargetInterval($Context,[long]$Begin,[long]$End) {
            if ($Begin -lt $Context.Q0 -or $End -lt $Begin -or ([bigint]$End-$Begin)*10 -gt [bigint]$Context.Frequency) {
                Stop-R2TargetFault $Context 'R2_TARGET_VALIDATION_STALE_OR_INVALID'
            }
        }
        function Open-R2TargetParents($Context,$TargetPlan) {
            $state=Get-R2TargetState $Context; Assert-R2TargetWork $Context
            if (-not [object]::ReferenceEquals($TargetPlan,$Context.PlanReference.TargetPlan) -or $TargetPlan.windowsParentLiteral -cne 'E:\') {
                Stop-R2TargetFault $Context 'R2_TARGET_UNSELECTED_PARENT_POLICY'
            }
            if ($null -eq $state) {
                $slot=Get-R2CurrentSlot $Context
                $identity=Reserve-R2ComponentIdentity $Context $slot 'Target'
                $state=[pscustomobject]@{Context=$Context;Plan=$TargetPlan;Identity=$identity;Stage=0;InitialBegin=$null;Arena=$null;Slices=@{};Parent=$null;Owner=$null;Binding=$null;Ready=$false;Closed=$false;CloseUnknown=$false;ParentCloseAttempted=$false;ArenaCloseAttempted=$false;VolumeSerial=$null;FileId=$null;VolumeGuid=$null;LastAllocation=$null;LastEof=$null;IdentityFacts=[Collections.Generic.List[object]]::new(5);ValidationStage=0;ValidationBegin=$null;ValidationSequence=[uint64]0;Validation=$null;ValidationStatuses=[Collections.Generic.List[object]]::new(5);AllocationPending=$false;AllocationValidation=$null;AllocationRow=$null}
                $script:state=$state
                $state.Owner=New-R2TargetRecord $Context 'ParentOwner' @{OriginalSlotReference=$slot;TargetPlanReference=$TargetPlan;Policy='READ_ONLY_E_ROOT';ParentHandle=$null;VolumeSerial=$null;FileId=$null;VolumeGuid=$null;ParentReady=[R2Fact]::UNKNOWN;Closed=[R2Fact]::FALSE;CarrierPrepared=[R2Fact]::UNKNOWN}
                # This is one bounded parent-query arena, not a carrier or a new
                # storage allowance. All views retain this original buffer owner.
                $before=$Context.Registry.Count
                try { $state.Arena=New-R2NativeBuffer $Context $slot 8192 8 }
                catch {
                    # Allocator failure can follow an actual returned allocation.
                    # Only the NEXT original ledger registry entry from this
                    # synchronous call may be recovered, never caller scalars.
                    if ($Context.Registry.Count -eq $before+1) {
                        $candidate=$Context.Registry[$before]
                        if ([object]::ReferenceEquals($candidate.ContextReference,$Context) -and
                            [object]::ReferenceEquals($candidate.OriginalSlotReference,$slot) -and $candidate.Capacity -eq 8192) {
                            $state.Arena=$candidate
                        }
                    }
                    $state.CloseUnknown=$true
                    throw
                }
                foreach ($row in @(@('Id',0,24),@('Standard',24,24),@('Tag',48,8),@('Path',64,2048),@('Mapping',2112,2048),@('Available',4160,8),@('Total',4168,8),@('Free',4176,8))) {
                    $state.Slices[$row[0]]=Get-R2NativeBufferSlice $Context $state.Arena ([uint32]$row[1]) ([uint32]$row[2])
                }
                $state.Parent=Reserve-R2Handle $Context ([R2HandleKind]::FILE) ([R2HandleOwnership]::OWNED) $slot
                $state.Owner.Data['ParentHandle']=$state.Parent
                return 'PENDING'
            }
            if ($state.Closed -or -not [object]::ReferenceEquals($state.Plan,$TargetPlan)) { Stop-R2TargetFault $Context 'R2_TARGET_REOPEN_OR_PLAN_SUBSTITUTION' }
            if ($state.Ready) {
                if ($state.Parent.State -ne [R2HandleState]::LIVE -or $state.Arena.State -ne [R2HandleState]::LIVE) { Stop-R2TargetFault $Context 'R2_TARGET_READY_OWNER_NOT_LIVE' }
                return ,$state.Owner.View
            }
            if ($state.Stage -eq 0) {
                # Reservation exists before CreateFile. Ledger records an actual
                # returned valid handle before post-call clock/reporting faults.
                $state.Stage=1
                $fact=Invoke-R2TargetNative $Context ([R2ApiId]::CreateFileW) @('E:\',[uint32]0x81,[uint32]1,[IntPtr]::Zero,[uint32]3,[uint32]0x02200000,[IntPtr]::Zero)
                if ($state.Parent.State -ne [R2HandleState]::LIVE) { Stop-R2TargetFault $Context 'R2_TARGET_PARENT_OPEN_FAILED' $fact }
                $state.InitialBegin=$fact.QpcBegin
                return 'PENDING'
            }
            $index=$state.Stage-1
            $fact=Read-R2TargetIdentityStage $Context $state $index $true
            Assert-R2TargetInterval $Context $state.InitialBegin $fact.QpcEnd
            $state.Stage++
            if ($state.Stage -le 5) { return 'PENDING' }
            foreach ($name in @('VolumeSerial','FileId','VolumeGuid')) { $state.Owner.Data[$name]=$state.$name }
            $state.Owner.Data['ParentReady']=[R2Fact]::TRUE
            $state.Binding=New-R2TargetRecord $Context 'DiskBinding' @{OwnerReference=$state.Owner.View;ParentHandle=$state.Parent;LiteralCounterInstanceName='E:';VolumeGuid=$state.VolumeGuid;VolumeSerial=$state.VolumeSerial;FileId=$state.FileId;OriginalIdentityFacts=$state.IdentityFacts.AsReadOnly()}
            $state.Ready=$true
            return ,$state.Owner.View
        }
        function Get-R2OriginalTargetDiskBinding($Context) {
            $state=Get-R2TargetState $Context
            if ($null -eq $state -or -not $state.Ready) { return 'NOT_READY' }
            if ($state.Closed -or $state.Parent.State -ne [R2HandleState]::LIVE -or $state.Arena.State -ne [R2HandleState]::LIVE) { Stop-R2TargetFault $Context 'R2_TARGET_BINDING_CLOSED' }
            return ,$state.Binding.View
        }
        function Get-R2OriginalTargetParentOwner($Context) {
            # Cleanup can obtain the original owner even when Open never returned
            # a completed owner. This getter never creates one or grants work.
            $state=Get-R2TargetState $Context
            if ($null -eq $state) { return 'NOT_READY' }
            return ,$state.Owner.View
        }
        function Assert-R2OriginalTargetDiskBinding($Context,$Binding) {
            $state=Get-R2TargetState $Context; Assert-R2TargetWork $Context
            [void](Get-R2TargetRecord $Context $Binding 'DiskBinding')
            if (-not $state.Ready -or $state.Closed -or -not [object]::ReferenceEquals($Binding,$state.Binding.View)) { Stop-R2TargetFault $Context 'R2_TARGET_BINDING_NOT_CURRENT' }
            if ($state.ValidationStage -eq 0) {
                if ($null -ne $state.Validation) { [void]$script:records.Remove($state.Validation.View); $state.Validation=$null }
                $state.ValidationStatuses.Clear(); $state.ValidationBegin=$null
            }
            $fact=Read-R2TargetIdentityStage $Context $state $state.ValidationStage $false
            if ($null -eq $state.ValidationBegin) { $state.ValidationBegin=$fact.QpcBegin }
            $state.ValidationStatuses.Add((Get-R2TargetStatus $fact))
            Assert-R2TargetInterval $Context $state.ValidationBegin $fact.QpcEnd
            $state.ValidationStage++
            if ($state.ValidationStage -lt 5) { return 'PENDING' }
            if ($state.ValidationSequence -eq [uint64]::MaxValue) { Stop-R2TargetFault $Context 'R2_TARGET_SEQUENCE_EXHAUSTED' }
            $state.ValidationSequence++
            $statuses=[Array]::AsReadOnly([object[]]$state.ValidationStatuses.ToArray())
            $state.Validation=New-R2TargetRecord $Context 'Validation' @{BindingReference=$Binding;Sequence=$state.ValidationSequence;QpcBegin=$state.ValidationBegin;QpcEnd=$fact.QpcEnd;VolumeGuid=$state.VolumeGuid;LiteralCounterInstanceName='E:';NativeStatuses=$statuses}
            $state.ValidationStage=0
            return ,$state.Validation.View
        }
        function Get-R2OriginalTargetValidationFields($Context,$Validation) {
            $state=Get-R2TargetState $Context
            $entry=Get-R2TargetRecord $Context $Validation 'Validation'
            if (-not $state.Ready -or $state.Closed -or $null -eq $state.Validation -or
                -not [object]::ReferenceEquals($state.Validation.View,$Validation) -or $entry.Data.Sequence -ne $state.ValidationSequence -or
                -not [object]::ReferenceEquals($entry.Data.BindingReference,$state.Binding.View) -or $state.Parent.State -ne [R2HandleState]::LIVE -or $state.Arena.State -ne [R2HandleState]::LIVE) {
                Stop-R2TargetFault $Context 'R2_TARGET_VALIDATION_RETIRED'
            }
            $now=Get-R2LedgerTimestamp $Context
            Assert-R2TargetInterval $Context $entry.Data.QpcBegin $now
            return ,$entry.View
        }
        function Read-R2Allocation($Context,$TargetOwner) {
            $state=Get-R2TargetState $Context; Assert-R2TargetWork $Context
            [void](Get-R2TargetRecord $Context $TargetOwner 'ParentOwner')
            if (-not [object]::ReferenceEquals($state.Owner.View,$TargetOwner) -or -not $state.Ready -or $state.Closed) { Stop-R2TargetFault $Context 'R2_TARGET_ALLOCATION_OWNER' }
            if (-not $state.AllocationPending) {
                $validation=Assert-R2OriginalTargetDiskBinding $Context $state.Binding.View
                if ($validation -is [string]) { return 'PENDING' }
                $state.AllocationValidation=$validation; $state.AllocationPending=$true
                return 'PENDING'
            }
            $validation=Get-R2OriginalTargetValidationFields $Context $state.AllocationValidation
            $fact=Invoke-R2TargetNative $Context ([R2ApiId]::GetDiskFreeSpaceExW) @($state.VolumeGuid,$state.Slices.Available,$state.Slices.Total,$state.Slices.Free)
            Assert-R2TargetBool $Context $fact 'R2_TARGET_FREE_SPACE_QUERY_FAILED'
            $available=[BitConverter]::ToUInt64((Read-R2TargetBytes $Context $state.Slices.Available 8),0)
            $total=[BitConverter]::ToUInt64((Read-R2TargetBytes $Context $state.Slices.Total 8),0)
            $free=[BitConverter]::ToUInt64((Read-R2TargetBytes $Context $state.Slices.Free 8),0)
            if ($available -gt $total -or $available -gt $free) { Stop-R2TargetFault $Context 'R2_TARGET_FREE_SPACE_INVALID' $fact }
            Assert-R2TargetInterval $Context $validation.QpcBegin $fact.QpcEnd
            $row=New-R2TargetRecord $Context 'AllocationObservation' @{OwnerReference=$TargetOwner;ParentHandle=$state.Parent;VolumeGuid=$state.VolumeGuid;VolumeSerial=$state.VolumeSerial;FileId=$state.FileId;ObjectKind='EXISTING_PARENT_DIRECTORY';ParentAllocationSize=$state.LastAllocation;ParentEndOfFile=$state.LastEof;AvailableToCaller=$available;TotalAvailableToCaller=$total;TotalFree=$free;QpcBegin=$validation.QpcBegin;QpcEnd=$fact.QpcEnd;NativeStatus=(Get-R2TargetStatus $fact);CarrierAllocation=$null;GuestFree=$null;FloorAdmission=[R2Fact]::UNKNOWN}
            if ($null -ne $state.AllocationRow) { [void]$script:records.Remove($state.AllocationRow.View) }
            $state.AllocationRow=$row; $state.AllocationPending=$false; $state.AllocationValidation=$null
            return ,$row.View
        }
        function Close-R2TargetStep($Context,$TargetOwner) {
            $state=Get-R2TargetState $Context
            [void](Get-R2TargetRecord $Context $TargetOwner 'ParentOwner')
            if (-not [object]::ReferenceEquals($TargetOwner,$state.Owner.View)) { Stop-R2TargetFault $Context 'R2_TARGET_CLOSE_OWNER' }
            if ($state.Closed) { if ($state.CloseUnknown) { return 'CLOSED_RESIDUE' }; return 'CLOSED' }
            # Entry chooses a cleanup step under the ORIGINAL domain/c0. These
            # helpers cannot refresh c0 or turn an expired gate into a new one.
            $slot=Get-R2CurrentSlot $Context
            $domain=switch -CaseSensitive ([string]$slot.Phase) {'Prep'{'Prep'}'PREP'{'Prep'}'External'{'External'}'EXTERNAL'{'External'}'Study'{'Study'}'STUDY'{'Study'}default{throw 'R2_TARGET_CLEANUP_DOMAIN'}}
            [void](Get-R2Deadline $Context $domain $true)
            if (-not $state.ParentCloseAttempted) {
                # Progress belongs to the original cleanup owner, independently
                # of whether a failing pre-dispatch gate consumed the resource.
                # A failed first attempt must not hide the untouched arena.
                $state.ParentCloseAttempted=$true
                if ($null -ne $state.Parent -and $state.Parent.State -eq [R2HandleState]::LIVE) {
                    try { [void](Consume-R2Handle $Context $state.Parent) }
                    catch { $state.CloseUnknown=$true }
                }
                return 'PENDING'
            }
            if ($null -ne $state.Parent -and $state.Parent.State -eq [R2HandleState]::CONSUMED) {
                if ($null -eq $state.Parent.ConsumeFact -or $null -eq $state.Parent.ConsumeFact.RawStatus -or $state.Parent.ConsumeFact.RawStatus -eq 0) { $state.CloseUnknown=$true }
            }
            if ($null -ne $state.Parent -and $state.Parent.State -eq [R2HandleState]::RESERVED -and $state.Stage -ge 1) { $state.CloseUnknown=$true }
            if (-not $state.ArenaCloseAttempted) {
                $state.ArenaCloseAttempted=$true
                if ($null -ne $state.Arena -and $state.Arena.State -eq [R2HandleState]::LIVE) {
                    try { Release-R2NativeBuffer $Context $state.Arena }
                    catch { $state.CloseUnknown=$true }
                }
                return 'PENDING'
            }
            if ($null -ne $state.Arena -and $state.Arena.State -eq [R2HandleState]::CONSUMED) {
                if ($null -eq $state.Arena.ReleaseFact -or $state.Arena.ReleaseFact.ReturnedVoid -ne [R2Fact]::TRUE) { $state.CloseUnknown=$true }
            }
            if ($null -ne $state.Arena -and $state.Arena.State -eq [R2HandleState]::RESERVED) { $state.CloseUnknown=$true }
            if (($null -ne $state.Parent -and $state.Parent.State -eq [R2HandleState]::LIVE) -or
                ($null -ne $state.Arena -and $state.Arena.State -eq [R2HandleState]::LIVE)) { $state.CloseUnknown=$true }
            # Closed private phase means all once-only cleanup actions were
            # attempted. Public native absence stays UNKNOWN if anything remains.
            $state.Closed=$true; $state.Ready=$false
            $state.Owner.Data['Closed']=$(if ($state.CloseUnknown) {[R2Fact]::UNKNOWN} else {[R2Fact]::TRUE})
            if ($null -ne $state.Validation) { [void]$script:records.Remove($state.Validation.View) }
            if ($state.CloseUnknown) { return 'CLOSED_RESIDUE' }
            return 'CLOSED'
        }
        Export-ModuleMember -Function Open-R2TargetParents,Get-R2OriginalTargetParentOwner,Get-R2OriginalTargetDiskBinding,Assert-R2OriginalTargetDiskBinding,Get-R2OriginalTargetValidationFields,Read-R2Allocation,Close-R2TargetStep
    }
    Import-Module $module -Global
}

function Open-R2TargetParents {
    param([Parameter(Mandatory)][object]$Context,[Parameter(Mandatory)][object]$TargetPlan)
    Initialize-R2TargetParentOwner
    Route2OriginalTargetParent\Open-R2TargetParents $Context $TargetPlan
}

function Get-R2OriginalTargetDiskBinding {
    param([Parameter(Mandatory)][object]$Context)
    Assert-R2ContextReference $Context
    if (-not (Get-Module -Name Route2OriginalTargetParent)) { return 'NOT_READY' }
    return ,(Route2OriginalTargetParent\Get-R2OriginalTargetDiskBinding $Context)
}
