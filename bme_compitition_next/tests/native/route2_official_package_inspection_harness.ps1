# SOURCE ONLY / UNRUN. Synthetic in-memory fixtures; no owner activation,
# official archive access, files, imports of package code, or production main.
# Running this harness requires a separately lawful runtime boundary.
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$source = [IO.Path]::GetFullPath([IO.Path]::Combine($PSScriptRoot, '..\..\scripts\route2_official_package_inspection.ps1'))
$tokens = $null; $parseErrors = $null
$ast = [Management.Automation.Language.Parser]::ParseFile($source, [ref]$tokens, [ref]$parseErrors)
if ($parseErrors.Count -ne 0) { throw 'PRODUCTION_PARSE_ERRORS' }
$fixtureModule=New-Module -Name H4SyntheticFixtureContext -ArgumentList $ast -ScriptBlock {
param($ast)
$names = @('Fail','Now','Check-Active','Sha-Bytes','H4-JsonBytes','H4-U16','H4-U32','H4-ReadAt','H4-Path','H4-Denied','H4-Positive','H4-Crc','H4-Preview','H4-Transport','H4-Inspect')
$definitions = $ast.FindAll({param($node) $node -is [Management.Automation.Language.FunctionDefinitionAst]}, $false)
# Exact production function bodies, not a second parser implementation. Main and
# all activation/process/file-opening functions are deliberately excluded.
foreach ($name in $names) {
    $matches = @($definitions | Where-Object { $_.Name -ceq $name })
    if ($matches.Count -ne 1) { throw ('HELPER_NOT_UNIQUE:' + $name) }
    if ($matches[0].Extent.Text -match '\[(?:System\.)?IO\.(?:File|FileStream|Directory)\]') { throw 'PURE_HELPER_HAS_FILE_ACCESS' }
    . ([scriptblock]::Create($matches[0].Extent.Text))
}
$script:ActiveStop = [Diagnostics.Stopwatch]::GetTimestamp() + [Diagnostics.Stopwatch]::Frequency * 120
$script:passed = 0
function Assert($Condition, [string]$Message) { if (-not $Condition) { throw $Message } }
function Case([string]$Name, [scriptblock]$Body) { & $Body; $script:passed++; [Console]::WriteLine('PASS ' + $Name) }
function Refuses([scriptblock]$Body,[string]$ExpectedCode='') {
    $failed=$false; $code=''
    try { & $Body | Out-Null } catch {
        $failed=$true; $error=$_.Exception
        for($d=0;$d -lt 8;$d++) { if($error.Data.Contains('Route2FixedCode')) { $code=[string]$error.Data['Route2FixedCode'] }; if($null -eq $error.InnerException) { break }; $error=$error.InnerException }
    }
    Assert $failed 'EXPECTED_REFUSAL'
    if($ExpectedCode.Length -gt 0) { Assert ($code -ceq $ExpectedCode) ('WRONG_REFUSAL:'+ $code) }
}
function Bytes([string]$Text) { return ,([Text.UTF8Encoding]::new($false,$true).GetBytes($Text)) }
function New-Fixture($Members) {
    $out = [IO.MemoryStream]::new(); $w=[IO.BinaryWriter]::new($out)
    $central=[IO.MemoryStream]::new(); $cw=[IO.BinaryWriter]::new($central)
    try {
        foreach ($m in $Members) {
            $name=Bytes $m.Name; $data=[byte[]]$m.Bytes; $packed=$data
            $method=0; if ($m.Contains('Method')) { $method=[int]$m.Method }
            if ($method -eq 8) {
                $cm=[IO.MemoryStream]::new(); $ds=[IO.Compression.DeflateStream]::new($cm,[IO.Compression.CompressionMode]::Compress,$true)
                try { $ds.Write($data,0,$data.Length) } finally { $ds.Dispose() }
                $packed=$cm.ToArray(); $cm.Dispose()
            }
            $crc=H4-Crc $data; if ($m.Contains('Crc')) { $crc=[uint32]$m.Crc }
            $flags=2048; if ($m.Contains('Flags')) { $flags=[int]$m.Flags }
            $attrs=[uint32]0; if ($m.Contains('Attrs')) { $attrs=[uint32]$m.Attrs }
            $extra=[byte[]]@(); if ($m.Contains('Extra')) { $extra=[byte[]]$m.Extra }
            $offset=[uint32]$out.Position
            $w.Write([uint32]67324752); $w.Write([uint16]20); $w.Write([uint16]$flags); $w.Write([uint16]$method)
            $w.Write([uint32]0); $w.Write([uint32]$crc); $w.Write([uint32]$packed.Length); $w.Write([uint32]$data.Length)
            $w.Write([uint16]$name.Length); $w.Write([uint16]$extra.Length); $w.Write($name); $w.Write($extra); $w.Write($packed)
            $cw.Write([uint32]33639248); $cw.Write([uint16]788); $cw.Write([uint16]20); $cw.Write([uint16]$flags); $cw.Write([uint16]$method)
            $cw.Write([uint32]0); $cw.Write([uint32]$crc); $cw.Write([uint32]$packed.Length); $cw.Write([uint32]$data.Length)
            $cw.Write([uint16]$name.Length); $cw.Write([uint16]$extra.Length); $cw.Write([uint16]0); $cw.Write([uint16]0); $cw.Write([uint16]0)
            $cw.Write($attrs); $cw.Write($offset); $cw.Write($name); $cw.Write($extra)
        }
        $cbytes=$central.ToArray(); $co=[uint32]$out.Position; $w.Write($cbytes)
        $w.Write([uint32]101010256); $w.Write([uint16]0); $w.Write([uint16]0); $w.Write([uint16]$Members.Count); $w.Write([uint16]$Members.Count)
        $w.Write([uint32]$cbytes.Length); $w.Write($co); $w.Write([uint16]0)
        return ,$out.ToArray()
    } finally { $cw.Dispose(); $central.Dispose(); $w.Dispose(); $out.Dispose() }
}
function Inspect([byte[]]$Fixture) {
    $s=[IO.MemoryStream]::new($Fixture,$false)
    try { return H4-Inspect $s } finally { $s.Dispose() }
}
Case 'CRC external oracle' { Assert ((H4-Crc (Bytes '123456789')) -eq [uint32]3421780262) 'CRC_ORACLE' }
Case 'stored complete document' {
    $r=Inspect (New-Fixture @(@{Name='README.md';Bytes=(Bytes '123456789');Crc=[uint32]3421780262}))
    Assert $r.metadata_complete 'METADATA'; Assert $r.documents[0].full 'FULL'; Assert ($r.documents[0].encoding -eq 'identity-base64') 'IDENTITY'
    Assert ([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($r.documents[0].payload_base64)) -ceq '123456789') 'TEXT'
}
Case 'deflated bounded slice' { $r=Inspect (New-Fixture @(@{Name='docs/RULES.txt';Bytes=(Bytes ('rules '+('abc '*40)));Method=8})); Assert $r.documents[0].full 'DEFLATE' }
Case 'deny data payload with safe README' {
    $r=Inspect (New-Fixture @(@{Name='README.md';Bytes=(Bytes 'rules')},@{Name='data/labels.csv';Bytes=(Bytes 'DO_NOT_OPEN')}))
    Assert ($r.payload_ordinals.Count -eq 1 -and $r.payload_ordinals[0] -eq 0) 'DATA_PAYLOAD_OPENED'
}
Case 'ASCII and Chinese original wrappers denied' {
    foreach ($p in @('ground_truth_2026/README.md','DATA/README.md',(([char]0x6570).ToString()+[char]0x636e+'/README.md'))) {
        $r=Inspect (New-Fixture @(@{Name=$p;Bytes=(Bytes 'not selected')})); Assert ($r.documents.Count -eq 0) 'DENY_WRAPPER'
    }
}
Case 'compound GT separator wrappers denied before removal' {
    foreach ($wrapper in @('ground truth','ground-truth','ground.truth','ground__truth','ground truth 2026','ground-truth-2026','ground.truth.2026','ground__truth__2026')) {
        $r=Inspect (New-Fixture @(@{Name=($wrapper+'/README.md');Bytes=(Bytes 'DO_NOT_READ_GT_WRAPPER')}))
        Assert ($r.metadata_complete -and $r.categories.denied -eq 1) 'COMPOUND_DENY_CLASSIFICATION'
        Assert ($r.documents.Count -eq 0 -and $r.candidates.Count -eq 0) 'COMPOUND_DENY_SELECTED_DOCUMENT'
        Assert ($r.payload_ordinals.Count -eq 0) 'COMPOUND_DENY_PAYLOAD_OPENED'
        Assert ($script:H4PayloadReads.Count -eq 0) 'COMPOUND_DENY_READ_LEDGER'
    }
}
Case 'safe common wrapper and shallow location' { $r=Inspect (New-Fixture @(@{Name='official/docs/RULES.md';Bytes=(Bytes 'rules')})); Assert ($r.documents.Count -eq 1) 'WRAPPER' }
Case 'no recursive positive admission' { $r=Inspect (New-Fixture @(@{Name='official/docs/deep/README.md';Bytes=(Bytes 'rules')})); Assert ($r.documents.Count -eq 0) 'RECURSIVE' }
Case 'hidden traversal devices depth and aliases' {
    foreach ($p in @('.hidden/README.md','../README.md','C:/README.md','docs\README.md','CON.txt',(('x/'*17)+'README.md'))) { Refuses { Inspect (New-Fixture @(@{Name=$p;Bytes=(Bytes 'x')})) } }
    Refuses { Inspect (New-Fixture @(@{Name='README.md';Bytes=(Bytes 'x')},@{Name='readme.MD';Bytes=(Bytes 'y')})) }
}
Case 'symlink extras encryption descriptor unsupported method' {
    foreach ($m in @(@{Name='README.md';Bytes=(Bytes 'x');Attrs=[uint32]2717843456},@{Name='README.md';Bytes=(Bytes 'x');Extra=[byte[]](1,0,0,0)},@{Name='README.md';Bytes=(Bytes 'x');Flags=2049},@{Name='README.md';Bytes=(Bytes 'x');Flags=2056},@{Name='README.md';Bytes=(Bytes 'x');Method=12})) { Refuses { Inspect (New-Fixture @($m)) } }
}
Case 'truncated comment ZIP64 central and overlap corruption' {
    $b=New-Fixture @(@{Name='README.md';Bytes=(Bytes 'rules')})
    Refuses { Inspect ([byte[]]$b[0..($b.Length-2)]) }
    $c=[byte[]]$b.Clone(); $c[$c.Length-2]=1; Refuses { Inspect $c }
    $c=[byte[]]$b.Clone(); $c[$c.Length-14]=255; $c[$c.Length-13]=255; $c[$c.Length-12]=255; $c[$c.Length-11]=255; Refuses { Inspect $c } 'ZIP64_UNSUPPORTED'
    $c=[byte[]]$b.Clone(); $c[0]=0; Refuses { Inspect $c }
    $c=New-Fixture @(@{Name='README.md';Bytes=(Bytes 'a')},@{Name='RULES.md';Bytes=(Bytes 'b')})
    $co=[int](H4-U32 $c ($c.Length-6)); $second=$co+46+9; [Array]::Clear($c,$second+42,4); Refuses { Inspect $c }
    $c=New-Fixture @(@{Name='README.md';Bytes=(New-Object byte[] 60)},@{Name='RULES.md';Bytes=(Bytes 'b')})
    $co=[int](H4-U32 $c ($c.Length-6)); $second=$co+55
    [Array]::Copy($c,99,$c,39,39)
    [Array]::Copy([BitConverter]::GetBytes([uint32]39),0,$c,$second+42,4)
    Refuses { Inspect $c } 'ZIP_OVERLAP_ALIAS_OR_UNCLAIMED_GAP'
}
Case 'CRC mismatch UTF8 and text controls' {
    foreach ($m in @(@{Name='README.md';Bytes=(Bytes 'rules');Crc=[uint32]0},@{Name='README.md';Bytes=[byte[]](255)},@{Name='README.md';Bytes=[byte[]](65,0,66)},@{Name='README.md';Bytes=(Bytes ([char]0x85).ToString())})) { Refuses { Inspect (New-Fixture @($m)) } }
}
Case 'member and candidate limits' {
    Refuses { Inspect (New-Fixture @(@{Name='README.md';Bytes=(New-Object byte[] 262145)})) } 'TEXT_MEMBER_SIZE_OR_RATIO'
    $members=@(); foreach ($d in @('','doc/','docs/','rules/','spec/')) { foreach ($n in @('README.md','RULES.md','TASK.md','SUBMISSION.md','METRIC.md','METRICS.md','SCORING.md','INSTRUCTIONS.md')) { $members+=@{Name=($d+$n);Bytes=(Bytes 'x')} } }
    Refuses { Inspect (New-Fixture $members) }
    $members=@(); foreach($stem in @('README','RULES','TASK','SUBMISSION','METRIC','METRICS','SCORING','INSTRUCTIONS')) { foreach($ext in @('md','txt','rst')) { $members+=@{Name=(('a'*450)+'/'+$stem+'.'+$ext);Bytes=(Bytes 'x')} } }
    Refuses { Inspect (New-Fixture $members) } 'CANDIDATE_METADATA_LIMIT'
}
Case 'transport gzip full roundtrip and budget fallback' {
    $records=New-Object 'System.Collections.Generic.List[object]'; $data=Bytes ('document '+('abcde '*6000))
    H4-Transport $records 0 $data (H4-Crc $data) 32768
    Assert ($records[0].full -and $records[0].encoding -eq 'gzip-base64') 'GZIP_FULL'
    $input=[IO.MemoryStream]::new([Convert]::FromBase64String($records[0].payload_base64)); $gz=[IO.Compression.GZipStream]::new($input,[IO.Compression.CompressionMode]::Decompress)
    $out=[IO.MemoryStream]::new(); try { $gz.CopyTo($out); Assert ((Sha-Bytes $out.ToArray()) -ceq (Sha-Bytes $data)) 'ROUNDTRIP' } finally { $gz.Dispose(); $input.Dispose(); $out.Dispose() }
    $records=New-Object 'System.Collections.Generic.List[object]'; H4-Transport $records 1 $data (H4-Crc $data) 350
    Assert (-not $records[0].full) 'FALLBACK'; Assert ($records[0].status -ceq 'EVIDENCE_TRANSPORT_UNRESOLVED') 'STATUS'
    Assert ((H4-JsonBytes @($records.ToArray())).Length -le 350) 'WIRE_BUDGET'
}
Case 'UTF8 preview boundary' {
    $b=Bytes ('a'+([char]0x4e2d).ToString()); $p=H4-Preview $b 3
    Assert ([Text.UTF8Encoding]::new($false,$true).GetString($p) -ceq 'a') 'PREVIEW_BOUNDARY'
}
Case 'nonexpandable gzip overflow and aggregate fallback budget' {
    $random=[Random]::new(1337); $data=New-Object byte[] 4096
    for($i=0;$i -lt $data.Length;$i++) { $data[$i]=[byte]$random.Next(32,127) }
    $records=New-Object 'System.Collections.Generic.List[object]'
    H4-Transport $records 0 (Bytes 'short rules') (H4-Crc (Bytes 'short rules')) 1000
    H4-Transport $records 1 $data (H4-Crc $data) 1000
    Assert ($records.Count -eq 2 -and $records[0].full -and -not $records[1].full) 'AGGREGATE_FALLBACK'
    Assert ($records[1].status -ceq 'EVIDENCE_TRANSPORT_UNRESOLVED') 'OVERFLOW_STATUS'
    Assert ((H4-JsonBytes @($records.ToArray())).Length -le 1000) 'AGGREGATE_WIRE'
    Assert (-not $records[1].Contains('preview_base64')) 'DUPLICATED_PREVIEW'
}
Case 'name encoding and Unicode normalization aliases' {
    $unicode=([char]0x4e2d).ToString()+'.md'
    Refuses { Inspect (New-Fixture @(@{Name=$unicode;Bytes=(Bytes 'x');Flags=0})) }
    $a=([char]0xe9).ToString()+'.txt'; $b='e'+([char]0x301).ToString()+'.txt'
    Refuses { Inspect (New-Fixture @(@{Name=$a;Bytes=(Bytes 'x')},@{Name=$b;Bytes=(Bytes 'y')})) }
    Refuses { Inspect (New-Fixture @(@{Name=(('a'*513)+'.md');Bytes=(Bytes 'x')})) }
    $fixture=New-Fixture @(@{Name='README.md';Bytes=(Bytes 'x')})
    $co=[int](H4-U32 $fixture ($fixture.Length-6)); $fixture[30]=255; $fixture[$co+46]=255
    Refuses { Inspect $fixture }
}
Case 'ratio aggregate structural and central caps' {
    Refuses { Inspect (New-Fixture @(@{Name='README.md';Bytes=(Bytes ('a'*10000));Method=8})) } 'TEXT_MEMBER_SIZE_OR_RATIO'
    $members=@(); foreach ($n in @('README.md','RULES.md','TASK.md','SUBMISSION.md','METRIC.md','METRICS.md')) { $members+=@{Name=$n;Bytes=(Bytes ('a'*200000))} }
    Refuses { Inspect (New-Fixture $members) } 'TEXT_AGGREGATE_LIMIT'
    $s=[IO.MemoryStream]::new([byte[]](0,0,0),$false)
    try { $script:H4StructuralBytes=16777216; Refuses { H4-ReadAt $s 0 1 } 'ZIP_STRUCTURAL_BUDGET' } finally { $s.Dispose() }
    $b=New-Fixture @(@{Name='README.md';Bytes=(Bytes 'rules')})
    [Array]::Copy([BitConverter]::GetBytes([uint32]8388609),0,$b,$b.Length-10,4)
    Refuses { Inspect $b }
}
Case 'more than eight safe members refuses payload selection' {
    $members=@(); foreach($n in @('README.md','RULES.md','TASK.md','SUBMISSION.md','METRIC.md','METRICS.md','SCORING.md','INSTRUCTIONS.md','evaluate.py')) { $members+=@{Name=$n;Bytes=(Bytes 'x')} }
    $r=Inspect (New-Fixture $members)
    Assert ($r.status -ceq 'METADATA_COMPLETE_DOCUMENT_SELECTION_UNRESOLVED' -and $r.payload_ordinals.Count -eq 0) 'SELECTION_LIMIT'
}
Case 'static fixed main and no broad execution surface' {
    $text=$ast.Extent.Text
    foreach ($bad in @('Get-Disk','Get-Partition','Get-Volume','Get-CimInstance','Add-Type','ZipArchive','ExtractToDirectory','Invoke-Expression','TestBypass','ArchivePath =')) { Assert (-not $text.Contains($bad)) ('FORBIDDEN:'+ $bad) }
    Assert ($text.Contains('route2-h4-official-nongt-inspection-2026-10-16-004')) 'POLICY_ID'
    Assert ($text.Contains('route2_h4_official_nongt_inspection_policy_v4')) 'POLICY_SCHEMA'
    Assert ($text.Contains('route2-h4-safe-text-v4')) 'CLASSIFIER_VERSION'
    Assert ($text.Contains('695efa21fea9c51652602f898f5da1936810801696e1538139a50e249d327ec2')) 'POLICY_HASH'
    Assert (-not $text.Contains('route2_h4_official_nongt_inspection_policy_v3')) 'SUPERSEDED_POLICY'
    Assert ($text.Contains('E:/e091f6df5b8f4fd1a62a5e43dda404b1_\u8d5b\u98982.zip')) 'FIXED_INPUT'
}
[Console]::WriteLine('Synthetic cases passed: ' + $script:passed)
}
# Module scope contains all copied helper functions and fixture state. Do not
# export/import it; no production script main or receipt is evaluated.
$fixtureModule=$null
