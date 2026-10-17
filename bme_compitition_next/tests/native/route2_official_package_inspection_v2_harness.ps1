# SOURCE ONLY / UNRUN. This harness is not an H5 runtime entry point.
# It reads main SOURCE, extracts ONLY whitelisted pure helper declarations into
# an isolated synthetic module, and never invokes main/Collect/receipt/issuer.
# No fixed archive access, project/native/Python/compiler/Add-Type/WSL/science.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$source=[IO.Path]::GetFullPath([IO.Path]::Combine($PSScriptRoot,'..','..','scripts','route2_official_package_inspection_v2.ps1'))
$tokens=$null;$parseErrors=$null
$ast=[Management.Automation.Language.Parser]::ParseFile($source,[ref]$tokens,[ref]$parseErrors)
if($parseErrors.Count -ne 0){throw 'SOURCE_PARSE_ERRORS'}
$allow=@('Fail','Sha-Bytes','H5-JsonBytes','H5-NewContext','H5-Tick','H5-Problem','H5-Stop','H5-U16','H5-U32','H5-Slice','H5-Crc','H5-ReadAt','H5-StrictUtf8','H5-Extras','H5-PathCheck','H5-Denied','H5-TypeSemantics','H5-LegacySafety','H5-NameSemantics','H5-Positive','H5-CentralLengths','H5-SelectedCounts','H5-SelectedMember','H5-SelectedTotals','H5-Directory','H5-Inventory','H5-Unpack','H5-Plain','H5-Preview','H5-Transport','H5-XmlBody','H5-Docx','H5-Inspect')
$functions=$ast.FindAll({param($n)$n -is [Management.Automation.Language.FunctionDefinitionAst]},$false)
$declarations=[Collections.Generic.List[string]]::new()
foreach($name in $allow){$hit=@($functions|Where-Object{$_.Name -ceq $name});if($hit.Count -ne 1){throw ('WHITELIST_COUNT_'+$name)};$declarations.Add($hit[0].Extent.Text)}
# Only declaration AST extents enter this module. Never dot-source the source.
$module=New-Module -Name Route2H5SyntheticOnly -ScriptBlock ([scriptblock]::Create(($declarations.ToArray() -join "`n")))
$checks=0
function Assert-True([bool]$Value,[string]$Code){if(-not $Value){throw $Code};$script:checks++}
function Assert-Equal($A,$B,[string]$Code){Assert-True ($A -ceq $B) $Code}
function Bytes([string]$S){return ,([Text.UTF8Encoding]::new($false,$true).GetBytes($S))}
function Join-Bytes([byte[][]]$Arrays){$m=[IO.MemoryStream]::new();try{foreach($b in $Arrays){$m.Write($b,0,$b.Length)};return ,$m.ToArray()}finally{$m.Dispose()}}
function Extra([int]$Id,[byte[]]$Data){$m=[IO.MemoryStream]::new();$w=[IO.BinaryWriter]::new($m);try{$w.Write([uint16]$Id);$w.Write([uint16]$Data.Length);$w.Write($Data);$w.Flush();return ,$m.ToArray()}finally{$w.Dispose();$m.Dispose()}}
function Entry([string]$Name,[byte[]]$Data){return @{name=(Bytes $Name);data=$Data;method=0;flags=2048;made_by=20;central_extra=[byte[]]::new(0);local_extra=[byte[]]::new(0);descriptor=0;crc_override=$null;offset_override=$null;attrs=0;needed=20;comment=[byte[]]::new(0)}}
function Zip([object[]]$Entries){
    $m=[IO.MemoryStream]::new();$w=[IO.BinaryWriter]::new($m);$central=[IO.MemoryStream]::new();$cw=[IO.BinaryWriter]::new($central);$locations=[Collections.Generic.List[object]]::new()
    try{
        foreach($e in $Entries){
            $local=$m.Position;$packed=$e.data
            if($e.method -eq 8){$z=[IO.MemoryStream]::new();$df=[IO.Compression.DeflateStream]::new($z,[IO.Compression.CompressionMode]::Compress,$true);try{$df.Write($e.data,0,$e.data.Length)}finally{$df.Dispose()};$packed=$z.ToArray();$z.Dispose()}
            $crc=& $module {param($b)H5-Crc $b} $e.data;if($null -ne $e.crc_override){$crc=[uint32]$e.crc_override}
            $flags=$e.flags;if($e.descriptor -ne 0){$flags=$flags -bor 8}
            $w.Write([uint32]67324752);$w.Write([uint16]$e.needed);$w.Write([uint16]$flags);$w.Write([uint16]$e.method);$w.Write([uint16]0);$w.Write([uint16]0)
            if($e.descriptor -ne 0){$w.Write([uint32]0);$w.Write([uint32]0);$w.Write([uint32]0)}else{$w.Write([uint32]$crc);$w.Write([uint32]$packed.Length);$w.Write([uint32]$e.data.Length)}
            $w.Write([uint16]$e.name.Length);$w.Write([uint16]$e.local_extra.Length);$w.Write([byte[]]$e.name);$w.Write([byte[]]$e.local_extra);$payload=$m.Position;$w.Write([byte[]]$packed)
            if($e.descriptor -eq 16){$w.Write([uint32]134695760)}
            if($e.descriptor -ne 0){$w.Write([uint32]$crc);$w.Write([uint32]$packed.Length);$w.Write([uint32]$e.data.Length)}
            $locations.Add(@{local=$local;payload=$payload;bytes=$e.data;packed=$packed;crc=$crc})
            $cw.Write([uint32]33639248);$cw.Write([uint16]$e.made_by);$cw.Write([uint16]$e.needed);$cw.Write([uint16]$flags);$cw.Write([uint16]$e.method);$cw.Write([uint16]0);$cw.Write([uint16]0);$cw.Write([uint32]$crc);$cw.Write([uint32]$packed.Length);$cw.Write([uint32]$e.data.Length);$cw.Write([uint16]$e.name.Length);$cw.Write([uint16]$e.central_extra.Length);$cw.Write([uint16]$e.comment.Length);$cw.Write([uint16]0);$cw.Write([uint16]0);$cw.Write([uint32]$e.attrs)
            $offset=$local;if($null -ne $e.offset_override){$offset=$e.offset_override};$cw.Write([uint32]$offset);$cw.Write([byte[]]$e.name);$cw.Write([byte[]]$e.central_extra);$cw.Write([byte[]]$e.comment)
        }
        $cw.Flush();$cb=$central.ToArray();$co=$m.Position;$w.Write($cb);$w.Write([uint32]101010256);$w.Write([uint16]0);$w.Write([uint16]0);$w.Write([uint16]$Entries.Length);$w.Write([uint16]$Entries.Length);$w.Write([uint32]$cb.Length);$w.Write([uint32]$co);$w.Write([uint16]0);$w.Flush()
        return @{bytes=$m.ToArray();central=$cb;central_offset=$co;locations=@($locations.ToArray());sha=(& $module {param($b)Sha-Bytes $b} $cb)}
    }finally{$cw.Dispose();$central.Dispose();$w.Dispose();$m.Dispose()}
}
function Outer([object]$First){$e=[Collections.Generic.List[object]]::new();$e.Add($First);for($i=1;$i -lt 10;$i++){$e.Add((Entry ('opaque'+$i+'.bin') ([byte[]]@(1,2,3))))};return Zip @($e.ToArray())}
function Inspect($Fixture){return & $module {param($f)$c=H5-NewContext;$s=[IO.MemoryStream]::new($f.bytes,$false);try{H5-Inspect $c $s $f.bytes.Length 10 $f.sha}finally{$s.Dispose()}} $Fixture}
function No-Payload($F,[string]$Code){Assert-Equal $F.selected_payload_reads.Count 0 ($Code+'_NO_PAYLOAD');Assert-Equal $F.selected_payload_attempted_bytes 0 ($Code+'_NO_ATTEMPT');Assert-True (-not $F.collection_complete) ($Code+'_INCOMPLETE')}
function Diagnostic($F,[string]$Code,[string]$Field,$Observed,$Expected){$hit=@($F.errors|Where-Object{$_.code -ceq $Code});Assert-True ($hit.Count -gt 0) ($Code+'_PRESENT');Assert-Equal $hit[0].field $Field ($Code+'_FIELD');Assert-Equal $hit[0].observed $Observed ($Code+'_OBSERVED');Assert-Equal (ConvertTo-Json -InputObject $hit[0].expected -Compress) (ConvertTo-Json -InputObject $Expected -Compress) ($Code+'_EXPECTED')}
function Unicode-Path([byte[]]$Raw,[string]$Name,[switch]$BadCrc){$m=[IO.MemoryStream]::new();$w=[IO.BinaryWriter]::new($m);try{$w.Write([byte]1);$crc=& $module {param($b)H5-Crc $b} $Raw;if($BadCrc){$crc=$crc -bxor 1};$w.Write([uint32]$crc);$w.Write((Bytes $Name));$w.Flush();return Extra 28789 $m.ToArray()}finally{$w.Dispose();$m.Dispose()}}

# External standard oracle, independent of fixture builder output.
Assert-Equal (& $module {H5-Crc ([Text.Encoding]::ASCII.GetBytes('123456789'))}) ([uint32]3421780262) 'CRC_123456789_CBF43926'
$fx=Outer (Entry 'docs/README.txt' (Bytes 'exact text'))
$f=Inspect $fx
Assert-True $f.collection_complete 'TEN_ENTRY_SUCCESS'
Assert-Equal $f.inventory.actual_parsed_count 10 'TEN_ACTUAL'
Assert-Equal $f.inventory.eocd_declared_count 10 'TEN_DECLARED'
Assert-Equal $f.documents[0].ordinal 0 'EXACT_SELECTED_ORDINAL'
Assert-Equal $f.selected_payload_reads[0].absolute_offset $fx.locations[0].payload 'EXACT_PAYLOAD_OFFSET'
Assert-Equal ([Convert]::ToBase64String($fx.locations[0].bytes)) $f.documents[0].payload_base64 'EXACT_ORIGINAL_BYTES'
Assert-Equal $f.selected_payload_reads[0].returned_bytes 10 'EXACT_RETURNED_BYTES'

# Recognized metadata, safe record-boundary unknowns, duplicates, and truncated
# extra TLV must retain the COMPLETE ten-record inventory before refusing.
$nt=[byte[]]::new(32);$nt[4]=1;$nt[6]=24
$known=Join-Bytes @((Extra 10 $nt),(Extra 21589 ([byte[]]@(1,1,0,0,0))),(Extra 30837 ([byte[]]@(1,1,42,1,43))))
$e=Entry 'README.txt' (Bytes 'known');$e.central_extra=$known;$e.local_extra=$known
Assert-True (Inspect (Outer $e)).collection_complete 'KNOWN_NTFS_UT_UID'
foreach($bad in @((Extra 48879 ([byte[]]@(1,2))), (Join-Bytes @((Extra 21589 ([byte[]]@(0))),(Extra 21589 ([byte[]]@(0))))),([byte[]]@(117,112,9,0,1)))){
    $e=Entry 'README.txt' (Bytes 'unknown');$e.central_extra=$bad;$f=Inspect (Outer $e);No-Payload $f 'EXTRA';Assert-Equal $f.inventory.actual_parsed_count 10 'EXTRA_INVENTORY_CONTINUES'
}
$e=Entry 'README.txt' (Bytes 'unicode');$e.central_extra=Unicode-Path $e.name 'README.txt';$e.local_extra=$e.central_extra
Assert-True (Inspect (Outer $e)).collection_complete 'VALID_UNICODE_BINDING'
$e.central_extra=Unicode-Path $e.name 'README.txt' -BadCrc;No-Payload (Inspect (Outer $e)) 'BAD_UNICODE_CRC'
$e=Entry 'README.txt' (Bytes 'alias');$e.central_extra=Unicode-Path $e.name 'ground---truth/README.txt';No-Payload (Inspect (Outer $e)) 'UNICODE_GT_ALIAS'
foreach($name in @('ground truth/README.txt','ground---truth/README.txt','GT/README.txt','data/README.txt')){
    $f=Inspect (Outer (Entry $name (Bytes 'denied')));Assert-Equal $f.selected_payload_reads.Count 0 'DENY_BEFORE_WRAPPER';Assert-True $f.inventory.records[0].denied 'DENY_MARKER'
}
$zh=ConvertFrom-Json '"\u6570\u636e/README.txt"';$f=Inspect (Outer (Entry $zh (Bytes 'denied')));Assert-Equal $f.selected_payload_reads.Count 0 'CHINESE_GT_DENY'

# Both exact descriptor extents, including CRC equal to the optional signature.
foreach($len in @(12,16)){
    $e=Entry 'README.txt' (Bytes 'descriptor');$e.descriptor=$len;$e.local_extra=Extra 21589 ([byte[]]@(7,1,0,0,0,2,0,0,0,3,0,0,0));$e.central_extra=Extra 21589 ([byte[]]@(7,1,0,0,0));$fx=Outer $e;$f=Inspect $fx
    Assert-True $f.collection_complete ('DESCRIPTOR_'+$len);Assert-Equal $f.inventory.records[0].descriptor_bytes $len 'DESCRIPTOR_EXACT_EXTENT';Assert-Equal $f.selected_payload_reads[0].absolute_offset $fx.locations[0].payload 'LOCAL_EXTRA_PAYLOAD_START'
    $e=Entry 'opaque.bin' ([byte[]]::new(0));$e.descriptor=$len;$e.crc_override=[uint32]134695760;$f=Inspect (Outer $e);Assert-True $f.local_bindings_complete 'SIGNATURE_SHAPED_CRC_BOUNDARY';Assert-Equal $f.selected_payload_reads.Count 0 'SIGNATURE_CRC_INVENTORY_ONLY'
}
$a=Entry 'README.txt' (Bytes 'a');$b=Entry 'other.bin' (Bytes 'b');$b.offset_override=0;$entries=@($a,$b);for($i=2;$i -lt 10;$i++){$entries+=Entry ('opaque'+$i+'.bin') ([byte[]]@(0))};No-Payload (Inspect (Zip $entries)) 'OVERLAP'
$e=Entry 'opaque.bin' (Bytes 'opaque');$e.method=12;$e.needed=46;$f=Inspect (Outer $e);Assert-True $f.metadata_semantics_complete 'UNSELECTED_METHOD12';Assert-Equal $f.selected_payload_reads.Count 0 'OTHER_METHOD_NO_PAYLOAD'
$e=Entry 'README.txt' (Bytes 'wrong crc');$e.crc_override=[uint32]1;$f=Inspect (Outer $e);Assert-True (-not $f.collection_complete) 'CRC_FAILURE';Assert-True ($f.selected_payload_returned_bytes -gt 0) 'CRC_FAILURE_LEDGER_RETAINED'
$e=Entry 'README.txt' (Bytes ('deflate exact '+('x'*100)));$e.method=8;$fx=Outer $e;$f=Inspect $fx;Assert-True $f.collection_complete 'DEFLATE_FIXED_SLICE';Assert-Equal $f.documents[0].payload_base64 ([Convert]::ToBase64String($e.data)) 'DEFLATE_EXACT_BYTES';Assert-Equal $f.selected_payload_reads[0].requested_bytes $fx.locations[0].packed.Length 'DEFLATE_EXACT_COMPRESSED_READ'
$a=Entry 'README.txt' (Bytes 'a');$b=Entry 'readme.TXT' (Bytes 'b');$entries=@($a,$b);for($i=2;$i -lt 10;$i++){$entries+=Entry ('opaque'+$i+'.bin') ([byte[]]@(0))};No-Payload (Inspect (Zip $entries)) 'CASE_ALIAS'
$e=Entry 'README.txt' (Bytes 'link');$e.made_by=788;$e.attrs=[long]2684354560;$f=Inspect (Outer $e);No-Payload $f 'SYMLINK_TYPE';Diagnostic $f 'UNIX_FILE_TYPE_UNSUPPORTED' 'unix_file_type' 40960 @(16384,32768)
# Host-dependent attribute acceptance/refusal preserves all central/local rows.
foreach($case in @(@(20,0,'MSDOS'),@(788,[long]2175008768,'UNIX'),@(2580,128,'NTFS'))){$e=Entry 'README.txt' (Bytes 'regular');$e.made_by=$case[0];$e.attrs=$case[1];$f=Inspect (Outer $e);Assert-True $f.collection_complete ($case[2]+'_REGULAR_ACCEPTED');Assert-Equal $f.inventory.records[0].interpreted_type 'regular_file' 'HOST_REGULAR_TYPE'}
$e=Entry 'README.txt' (Bytes 'unknown host');$e.made_by=65300;$f=Inspect (Outer $e);No-Payload $f 'UNKNOWN_HOST';Diagnostic $f 'ENTRY_HOST_SEMANTICS_UNSUPPORTED' 'made_by_host' 255 @(0,3,10);Assert-Equal $f.inventory.actual_parsed_count 10 'UNKNOWN_HOST_CENTRAL_COMPLETE';Assert-True $f.local_bindings_complete 'UNKNOWN_HOST_LOCAL_COMPLETE'
foreach($case in @(@(20,16),@(788,[long]1106051088),@(2580,16))){$e=Entry 'docs/' ([byte[]]::new(0));$e.made_by=$case[0];$e.attrs=$case[1];$f=Inspect (Outer $e);Assert-True $f.collection_complete 'HOST_DIRECTORY_ACCEPTED';Assert-Equal $f.inventory.records[0].interpreted_type 'directory' 'HOST_DIRECTORY_TYPE'}
foreach($case in @(@(20,16),@(788,[long]1106051088),@(2580,16))){$e=Entry 'README.txt' (Bytes 'type conflict');$e.made_by=$case[0];$e.attrs=$case[1];$f=Inspect (Outer $e);No-Payload $f 'HOST_DIRECTORY_CONFLICT';Diagnostic $f 'ENTRY_TYPE_PATH_CONFLICT' 'path_is_directory' $false $true}
$e=Entry 'README.txt' (Bytes 'hidden');$e.attrs=2;$f=Inspect (Outer $e);No-Payload $f 'DOS_HIDDEN';Diagnostic $f 'DOS_ATTRIBUTES_UNSUPPORTED' 'external_attributes' 2 'only readonly(1),directory(16),archive(32)'
$e=Entry 'README.txt' (Bytes 'reparse');$e.made_by=2580;$e.attrs=1024;$f=Inspect (Outer $e);No-Payload $f 'NTFS_REPARSE';Diagnostic $f 'NTFS_ATTRIBUTES_UNSUPPORTED' 'external_attributes' 1024 'only readonly(1),directory(16),archive(32),normal(128)'
$e=Entry 'README.txt' (Bytes 'unicode');$e.central_extra=Extra 28789 ([byte[]]@(1,0,0,0,0,255));No-Payload (Inspect (Outer $e)) 'INVALID_UNICODE_EXTRA'
$e=Entry 'README.txt' (Bytes 'legacy');$e.flags=0;$e.name=[byte[]]@(128,46,116,120,116);No-Payload (Inspect (Outer $e)) 'LEGACY_NO_UNICODE_BINDING'
$e=Entry 'README.txt' (Bytes 'legacy valid');$e.flags=0;$e.name=[byte[]]@(128,46,116,120,116);$unicodeName=ConvertFrom-Json '"\u8d5b\u9898\u8bf4\u660e.txt"';$e.central_extra=Unicode-Path $e.name $unicodeName;$f=Inspect (Outer $e);Assert-True $f.collection_complete 'LEGACY_VALID_UNICODE_BINDING';Assert-Equal $f.documents[0].ordinal 0 'LEGACY_UNICODE_EXACT_SELECTION'
# A Unicode CRC cannot erase raw ASCII deny tokens or path structure. These
# are raw byte fixtures, not CP437-decoded path authority or fake raw aliases.
$opaque=[byte[]]@(128);$legacyTail=Bytes '.txt'
$legacyCases=@(
    @{raw=(Join-Bytes @((Bytes 'data/'),$opaque,$legacyTail));unicode='README.txt';code='LEGACY_RAW_ASCII_DENY'},
    @{raw=(Join-Bytes @((Bytes 'GT/'),$opaque,$legacyTail));unicode='README.txt';code='LEGACY_RAW_ASCII_DENY'},
    @{raw=(Join-Bytes @((Bytes 'ground---truth/'),$opaque,$legacyTail));unicode='README.txt';code='LEGACY_RAW_ASCII_DENY'},
    @{raw=(Join-Bytes @((Bytes '../'),$opaque,$legacyTail));unicode='README.txt';code='LEGACY_RAW_PATH_UNSAFE_COMPONENT'},
    @{raw=(Join-Bytes @((Bytes 'docs\'),$opaque,$legacyTail));unicode='README.txt';code='LEGACY_RAW_PATH_UNSAFE_CHARACTER_OR_LENGTH'},
    @{raw=(Join-Bytes @((Bytes 'C:'),$opaque,$legacyTail));unicode='README.txt';code='LEGACY_RAW_PATH_UNSAFE_CHARACTER_OR_LENGTH'},
    @{raw=(Join-Bytes @((Bytes '/'),$opaque,$legacyTail));unicode='README.txt';code='LEGACY_RAW_PATH_UNSAFE_CHARACTER_OR_LENGTH'},
    @{raw=(Join-Bytes @((Bytes 'docs//'),$opaque,$legacyTail));unicode='README.txt';code='LEGACY_RAW_PATH_UNSAFE_COMPONENT'},
    @{raw=(Join-Bytes @(([byte[]]@(0)),$opaque,$legacyTail));unicode='README.txt';code='LEGACY_RAW_PATH_UNSAFE_CHARACTER_OR_LENGTH'},
    @{raw=(Join-Bytes @((Bytes '.'),$opaque,$legacyTail));unicode='README.txt';code='LEGACY_RAW_PATH_UNSAFE_COMPONENT'},
    @{raw=(Join-Bytes @((Bytes 'NUL.'),$opaque));unicode='README.txt';code='LEGACY_RAW_PATH_UNSAFE_COMPONENT'},
    @{raw=(Join-Bytes @($opaque,(Bytes '.txt ')));unicode='README.txt';code='LEGACY_RAW_PATH_UNSAFE_COMPONENT'},
    @{raw=(Join-Bytes @((Bytes 'docs/'),$opaque,$legacyTail));unicode=$unicodeName;code='LEGACY_COMPONENT_COUNT_CONFLICT'},
    @{raw=(Join-Bytes @((Bytes 'docs/'),$opaque,$legacyTail));unicode=('rules/'+$unicodeName);code='LEGACY_ASCII_COMPONENT_CONFLICT'},
    @{raw=(Join-Bytes @($opaque,$legacyTail,(Bytes '/')));unicode=$unicodeName;code='LEGACY_DIRECTORY_SHAPE_CONFLICT'},
    @{raw=(Join-Bytes @($opaque,$legacyTail));unicode='README.txt';code='LEGACY_ASCII_SKELETON_CONFLICT'},
    @{raw=(Join-Bytes @($opaque,(Bytes '.md')));unicode=$unicodeName;code='LEGACY_ASCII_SKELETON_CONFLICT'}
)
foreach($case in $legacyCases){$e=Entry 'unused.txt' (Bytes 'must never read');$e.flags=0;$e.name=$case.raw;$e.central_extra=Unicode-Path $e.name $case.unicode;$fx=Outer $e;$f=Inspect $fx;No-Payload $f $case.code;Assert-True (@($f.errors|Where-Object{$_.code -ceq $case.code}).Count -gt 0) 'LEGACY_PRECISE_REFUSAL';Assert-Equal $f.inventory.actual_parsed_count 10 'LEGACY_CENTRAL_INVENTORY_RETAINED';Assert-True $f.local_bindings_complete 'LEGACY_LOCAL_INVENTORY_RETAINED';Assert-Equal $f.inventory.records[0].raw_name_base64 ([Convert]::ToBase64String($e.name)) 'LEGACY_ORIGINAL_RAW_BYTES_UNCHANGED';if($case.code -ceq 'LEGACY_RAW_ASCII_DENY'){Assert-True $f.inventory.records[0].denied 'LEGACY_RAW_DENY_MARKER_RETAINED'}}
foreach($where in @('central','local','both')){$e=Entry 'unused.txt' (Bytes 'unambiguous legacy');$e.flags=0;$e.name=Join-Bytes @((Bytes 'docs/'),$opaque,$legacyTail);$up=Unicode-Path $e.name ('docs/'+$unicodeName);if($where -in @('central','both')){$e.central_extra=$up};if($where -in @('local','both')){$e.local_extra=$up};$fx=Outer $e;$f=Inspect $fx;Assert-True $f.collection_complete ('LEGACY_ASCII_PARENT_PRESERVED_'+$where);Assert-Equal $f.documents[0].ordinal 0 'LEGACY_POSITIVE_ORDINAL';Assert-Equal $f.selected_payload_reads[0].absolute_offset $fx.locations[0].payload 'LEGACY_POSITIVE_PAYLOAD_OFFSET';Assert-Equal $f.documents[0].payload_base64 ([Convert]::ToBase64String($e.data)) 'LEGACY_POSITIVE_EXACT_BYTES'}
$fx=Outer (Entry 'README.txt' (Bytes 'pin'));$fx.sha=('0'*64);No-Payload (Inspect $fx) 'CENTRAL_BINDING_MISMATCH'

# UTF8 and BOM UTF16 original bytes plus distinct derived view.
foreach($be in @($false,$true)){
    $enc=[Text.UnicodeEncoding]::new($be,$true,$true);$data=Join-Bytes @($enc.GetPreamble(),$enc.GetBytes('unicode body'));$fx=Outer (Entry 'README.txt' $data);$f=Inspect $fx;Assert-True $f.collection_complete 'UTF16_SUCCESS';Assert-Equal $f.documents[0].payload_base64 ([Convert]::ToBase64String($data)) 'UTF16_ORIGINAL_PRESERVED';Assert-Equal $f.documents[1].original_encoding 'UTF8_DERIVED_FROM_BOM_UTF16' 'UTF16_DERIVED_DISTINCT'
}
$f=Inspect (Outer (Entry 'README.txt' ([byte[]]@(255,255,0))));Assert-True (-not $f.collection_complete) 'INVALID_UTF8';Assert-True ($f.selected_payload_returned_bytes -gt 0) 'DECODER_FAILURE_LEDGER'
$bom=Join-Bytes @(([byte[]]@(239,187,191)),(Bytes 'BOM body'));$f=Inspect (Outer (Entry 'README.txt' $bom));Assert-True $f.collection_complete 'UTF8_BOM_SUCCESS';Assert-Equal $f.documents[0].payload_base64 ([Convert]::ToBase64String($bom)) 'UTF8_BOM_RAW_PRESERVED'

# A real synthetic OPC container includes metadata-only relationship/type parts.
function Docx-Outer([string]$Xml,$Relationship=$null){if($null -eq $Relationship){$Relationship=Entry '_rels/.rels' (Bytes '<Relationships/>')};$inner=Zip @((Entry '[Content_Types].xml' (Bytes '<Types/>')),$Relationship,(Entry 'word/document.xml' (Bytes $Xml)),(Entry 'word/media/image.bin' ([byte[]]@(0,1,2))));return Outer (Entry 'RULES.docx' $inner.bytes)}
$ns='http://schemas.openxmlformats.org/wordprocessingml/2006/main'
$xml='<w:document xmlns:w="'+$ns+'"><w:body><w:p><w:r><w:t>A</w:t><w:tab/><w:t>B</w:t><w:br/></w:r></w:p><w:tbl><w:tr><w:tc><w:p><w:r><w:t>C</w:t></w:r></w:p></w:tc></w:tr></w:tbl></w:body></w:document>'
$f=Inspect (Docx-Outer $xml);Assert-True $f.collection_complete 'DOCX_BODY_TABLE';Assert-True (-not $f.docx[0].full_document_rendered) 'DOCX_NEVER_RENDERED';Assert-Equal $f.docx[0].xml_ordinal 2 'DOCX_FIXED_XML_ORDINAL';Assert-Equal (@($f.selected_payload_reads|Where-Object{$_.container_ordinal -eq 0}).Count) 1 'DOCX_ONLY_ONE_INNER_PAYLOAD';Assert-Equal ([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($f.documents[1].payload_base64))) "A`tB`n`nC`n`t`n" 'DOCX_FIXED_BODY_FORMAT'
$strict=$xml.Replace($ns,'http://purl.oclc.org/ooxml/wordprocessingml/main');Assert-True (Inspect (Docx-Outer $strict)).collection_complete 'DOCX_STRICT_NAMESPACE'
# Nested w:t and any other element child are rejected after retaining raw XML
# evidence plus both real outer-container and inner-part read ledgers.
foreach($wordNs in @($ns,'http://purl.oclc.org/ooxml/wordprocessingml/main')){
    foreach($child in @('<w:t>B</w:t>','<w:tab/>','<x:child xmlns:x="urn:untrusted"/>')){
        $nestedText='<w:document xmlns:w="'+$wordNs+'"><w:body><w:p><w:r><w:t>A'+$child+'C</w:t></w:r></w:p></w:body></w:document>'
        $f=Inspect (Docx-Outer $nestedText);Assert-True (-not $f.collection_complete) 'XML_TEXT_CHILD_REFUSED';Assert-True (@($f.errors|Where-Object{$_.code -ceq 'XML_TEXT_ELEMENT_CHILD_FORBIDDEN'}).Count -gt 0) 'XML_TEXT_CHILD_DIAGNOSTIC';Assert-Equal $f.selected_payload_reads.Count 2 'XML_TEXT_CHILD_TWO_READS';foreach($read in $f.selected_payload_reads){Assert-True ($read.requested_bytes -gt 0 -and $read.returned_bytes -gt 0 -and $read.complete) 'XML_TEXT_CHILD_NONZERO_ACTUAL_LEDGER'};Assert-Equal $f.documents[0].kind 'docx_raw_word_document_xml' 'XML_TEXT_CHILD_RAW_KIND';Assert-Equal $f.documents[0].payload_base64 ([Convert]::ToBase64String((Bytes $nestedText))) 'XML_TEXT_CHILD_RAW_XML_PRESERVED'
    }
    $leafText='<w:document xmlns:w="'+$wordNs+'"><w:body><w:p><w:r><w:t xml:space="preserve"> A<![CDATA[B]]> C </w:t><w:t/><w:t>D</w:t></w:r></w:p></w:body></w:document>'
    $f=Inspect (Docx-Outer $leafText);Assert-True $f.collection_complete 'XML_LEAF_TEXT_CDATA_WHITESPACE_EMPTY';Assert-Equal ([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($f.documents[1].payload_base64))) " AB C D`n" 'XML_LEAF_EXACT_TEXT';Assert-Equal $f.documents[0].payload_base64 ([Convert]::ToBase64String((Bytes $leafText))) 'XML_LEAF_RAW_XML_PRESERVED'
    $unsupported='<w:document xmlns:w="'+$wordNs+'"><w:body><w:p><w:r><w:t>A</w:t><w:noBreakHyphen/><w:sym w:font="Symbol" w:char="F0A7"/><w:unknownContent w:val="opaque"/><w:t>B</w:t></w:r></w:p></w:body></w:document>'
    $f=Inspect (Docx-Outer $unsupported);Assert-True $f.collection_complete 'XML_UNSUPPORTED_EVIDENCE_COMPLETE';Assert-Equal $f.documents[0].payload_base64 ([Convert]::ToBase64String((Bytes $unsupported))) 'XML_UNSUPPORTED_RAW_PRESERVED';Assert-Equal $f.docx[0].unrendered_counts.no_break_hyphen 1 'XML_NO_BREAK_HYPHEN_COUNT';Assert-Equal $f.docx[0].unrendered_counts.symbols 1 'XML_SYMBOL_COUNT';Assert-Equal $f.docx[0].unrendered_counts.unsupported_wml_content 1 'XML_UNKNOWN_WML_CONTENT_COUNT';Assert-True $f.docx[0].unrendered_relevant_content_unresolved 'XML_UNSUPPORTED_ALWAYS_UNRESOLVED';Assert-True (-not $f.docx[0].full_document_rendered) 'XML_UNSUPPORTED_NOT_RENDERED';Assert-Equal $f.docx[0].scope 'DOCX_FIXED_PART_BODY_ONLY' 'XML_UNSUPPORTED_BODY_ONLY';Assert-Equal ([Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($f.documents[1].payload_base64))) "AB`n" 'XML_FROZEN_FORMATTER_UNCHANGED'
}
# Equal valid Unicode bindings on either/both headers do not rename raw OPC
# metadata, and the relationship payload remains unopened in every success.
foreach($where in @('central','local','both')){$rel=Entry '_rels/.rels' (Bytes '<Relationships/>');$up=Unicode-Path $rel.name '_rels/.rels';if($where -in @('central','both')){$rel.central_extra=$up};if($where -in @('local','both')){$rel.local_extra=$up};$f=Inspect (Docx-Outer $xml $rel);Assert-True $f.collection_complete ('OPC_EQUAL_UNICODE_'+$where);Assert-Equal $f.selected_payload_reads.Count 2 'OPC_ONLY_CONTAINER_AND_XML';$inner=@($f.selected_payload_reads|Where-Object{$_.container_ordinal -eq 0});Assert-Equal $inner.Count 1 'OPC_ONE_INNER_READ';Assert-Equal $inner[0].ordinal 2 'OPC_XML_ONLY_ORDINAL'}
foreach($bad in @('stale','malformed','rename','conflict')){$rel=Entry '_rels/.rels' (Bytes '<Relationships/>');switch($bad){'stale'{$rel.central_extra=Unicode-Path $rel.name '_rels/.rels' -BadCrc};'malformed'{$rel.central_extra=Extra 28789 ([byte[]]@(1))};'rename'{$rel.central_extra=Unicode-Path $rel.name '_rels/renamed.rels'};'conflict'{$rel.central_extra=Unicode-Path $rel.name '_rels/.rels';$rel.local_extra=Unicode-Path $rel.name '_rels/renamed.rels'}};$f=Inspect (Docx-Outer $xml $rel);Assert-True (-not $f.collection_complete) ('OPC_BAD_ALIAS_'+$bad);Assert-Equal $f.selected_payload_reads.Count 1 'OPC_BAD_ALIAS_OUTER_READ_RETAINED';Assert-True ($f.selected_payload_returned_bytes -gt 0) 'OPC_BAD_ALIAS_NONZERO_OUTER_LEDGER';Assert-Equal (@($f.selected_payload_reads|Where-Object{$_.container_ordinal -eq 0}).Count) 0 'OPC_BAD_ALIAS_NO_NESTED_PAYLOAD'}
$f=Inspect (Outer (Entry '_rels/.rels' (Bytes 'outer hidden')));No-Payload $f 'OUTER_OPC_HIDDEN_STILL_REFUSED'
# Exact diagnostic branches use the actual production pure validators. Fixture
# numerics are internal synthetic scope only; Collect retains its literal pins.
function Scope-Record($Overrides){$r=@{ordinal=7;payload_offset=123;method=0;needed=20;compressed_size=10L;uncompressed_size=10L;crc32=[uint32]0};foreach($k in $Overrides.Keys){$r[$k]=$Overrides[$k]};return $r}
function Guard-Result([string]$Kind,$InputData){return & $module {
    param($kind,$inputData)
    $c=H5-NewContext;$threw=$false;$accepted=$true
    try{switch($kind){
        'member'{H5-SelectedMember $c $inputData}
        'counts'{H5-SelectedCounts $c $inputData[0] $inputData[1]}
        'totals'{H5-SelectedTotals $c $inputData[0] $inputData[1]}
        'payload'{$null=H5-Unpack $c ([byte[]]::new(0)) $inputData 262144 20}
        'lengths'{$accepted=H5-CentralLengths $c $inputData}
        default{throw 'UNKNOWN_SYNTHETIC_GUARD'}
    }}catch{$threw=$true;$accepted=$false}
    return @{errors=@($c.errors.ToArray());reads=@($c.reads.ToArray());threw=$threw;accepted=$accepted}
} $Kind $InputData}
function Guard-Diagnostic($G,[string]$Code,[string]$Field,$Observed,$Expected){Diagnostic $G $Code $Field $Observed $Expected;Assert-True (-not $G.accepted) ($Code+'_REFUSED');Assert-Equal $G.reads.Count 0 ($Code+'_NO_READ_ATTEMPTS')}
foreach($case in @(
    @(@{method=12},'SELECTED_METHOD_UNSUPPORTED','method',12,@(0,8)),
    @(@{needed=45},'SELECTED_VERSION_NEEDED_LIMIT','version_needed',45,20),
    @(@{compressed_size=262145L},'SELECTED_COMPRESSED_SIZE_LIMIT','compressed_size',262145L,262144),
    @(@{uncompressed_size=262145L},'SELECTED_UNCOMPRESSED_SIZE_LIMIT','uncompressed_size',262145L,262144),
    @(@{compressed_size=0L;uncompressed_size=1L},'SELECTED_ZERO_COMPRESSED_NONEMPTY','uncompressed_size',1L,0),
    @(@{compressed_size=1L;uncompressed_size=21L},'SELECTED_EXPANSION_RATIO_LIMIT','uncompressed_size',21L,20L)
)){$g=Guard-Result 'member' (Scope-Record $case[0]);Guard-Diagnostic $g $case[1] $case[2] $case[3] $case[4];Assert-True $g.threw 'MEMBER_GUARD_THREW'}
$g=Guard-Result 'member' (Scope-Record @{method=12;needed=45});Guard-Diagnostic $g 'SELECTED_METHOD_UNSUPPORTED' 'method' 12 @(0,8)
foreach($case in @(@(@(9,0),'SELECTED_MEMBER_COUNT_LIMIT','selected_member_count',9,8),@(@(3,3),'SELECTED_DOCX_COUNT_LIMIT','selected_docx_count',3,2))){$g=Guard-Result 'counts' $case[0];Guard-Diagnostic $g $case[1] $case[2] $case[3] $case[4]}
foreach($case in @(@(@(1048577L,0L),'SELECTED_COMPRESSED_TOTAL_LIMIT','compressed_total_bytes'),@(@(0L,1048577L),'SELECTED_UNCOMPRESSED_TOTAL_LIMIT','uncompressed_total_bytes'))){$g=Guard-Result 'totals' $case[0];Guard-Diagnostic $g $case[1] $case[2] 1048577L 1048576}
foreach($case in @(
    @(@{uncompressed_size=262145L},'PAYLOAD_UNCOMPRESSED_SIZE_LIMIT','uncompressed_size',262145L,262144),
    @(@{compressed_size=262145L},'PAYLOAD_COMPRESSED_SIZE_LIMIT','compressed_size',262145L,262144),
    @(@{compressed_size=0L;uncompressed_size=1L},'PAYLOAD_ZERO_COMPRESSED_NONEMPTY','uncompressed_size',1L,0),
    @(@{compressed_size=1L;uncompressed_size=21L},'PAYLOAD_EXPANSION_RATIO_LIMIT','uncompressed_size',21L,20L)
)){$g=Guard-Result 'payload' (Scope-Record $case[0]);Guard-Diagnostic $g $case[1] $case[2] $case[3] $case[4]}
foreach($case in @(@(1025,0,'CENTRAL_NAME_LENGTH_LIMIT','name_bytes',1025,1024),@(0,4097,'CENTRAL_EXTRA_LENGTH_LIMIT','extra_bytes',4097,4096))){$r=@{ordinal=2;central_offset=55;central_extra_offset=99;raw_name=[byte[]]::new($case[0]);raw_extra=[byte[]]::new($case[1])};$g=Guard-Result 'lengths' $r;Guard-Diagnostic $g $case[2] $case[3] $case[4] $case[5]}
foreach($r in @((Scope-Record @{compressed_size=262144L;uncompressed_size=262144L}),(Scope-Record @{compressed_size=10L;uncompressed_size=200L}),(Scope-Record @{compressed_size=0L;uncompressed_size=0L}))){$g=Guard-Result 'member' $r;Assert-True $g.accepted 'MEMBER_EXACT_BOUNDARY_ACCEPTED';Assert-Equal $g.errors.Count 0 'BOUNDARY_NO_DIAGNOSTIC'}
Assert-True (Guard-Result 'counts' @(8,2)).accepted 'COUNT_EXACT_BOUNDARY'
Assert-True (Guard-Result 'totals' @(1048576L,1048576L)).accepted 'TOTAL_EXACT_BOUNDARY'
# Full Inspect integration also distinguishes method and needed-version guards
# before payload, rather than relying only on isolated-validator fixtures.
$e=Entry 'README.txt' (Bytes 'method');$e.method=12;$e.needed=46;$f=Inspect (Outer $e);No-Payload $f 'SELECTED_METHOD_INTEGRATION';Diagnostic $f 'SELECTED_METHOD_UNSUPPORTED' 'method' 12 @(0,8)
$e=Entry 'README.txt' (Bytes 'version');$e.needed=45;$f=Inspect (Outer $e);No-Payload $f 'SELECTED_VERSION_INTEGRATION';Diagnostic $f 'SELECTED_VERSION_NEEDED_LIMIT' 'version_needed' 45 20
$entries=@();foreach($name in @('README.txt','RULES.txt','INSTRUCTIONS.txt','TASK.txt','SUBMISSION.txt','METRIC.txt','METRICS.txt','SCORING.txt','problem_statement.txt')){$entries+=Entry $name (Bytes 'never read')};$entries+=Entry 'opaque.bin' ([byte[]]@(1));$f=Inspect (Zip $entries);No-Payload $f 'NINE_SELECTED_INTEGRATION';Diagnostic $f 'SELECTED_MEMBER_COUNT_LIMIT' 'selected_member_count' 9 8
$entries=@();foreach($name in @('README.docx','RULES.docx','TASK.docx')){$entries+=Entry $name (Bytes 'container never read')};for($i=3;$i -lt 10;$i++){$entries+=Entry ('opaque'+$i+'.bin') ([byte[]]@(1))};$f=Inspect (Zip $entries);No-Payload $f 'THREE_DOCX_INTEGRATION';Diagnostic $f 'SELECTED_DOCX_COUNT_LIMIT' 'selected_docx_count' 3 2
$featureXml='<w:document xmlns:w="'+$ns+'"><w:body><w:p><w:fldSimple w:instr="NEVER EVALUATE"><w:r><w:t>cached</w:t></w:r></w:fldSimple><w:ins><w:r><w:t>revision</w:t></w:r></w:ins><w:altChunk/></w:p></w:body></w:document>'
$f=Inspect (Docx-Outer $featureXml);Assert-True $f.collection_complete 'DOCX_UNRENDERED_BYTES_COMPLETE';Assert-True $f.docx[0].unrendered_relevant_content_unresolved 'DOCX_FIELDS_REVISIONS_UNRESOLVED';Assert-True ($f.docx[0].unrendered_counts.fields -gt 0) 'DOCX_FIELD_COUNT';Assert-True (-not $f.docx[0].full_document_rendered) 'DOCX_FEATURES_NEVER_FULL_RENDER'
$badXml=@('<!DOCTYPE x [<!ENTITY e SYSTEM "file:///never">]><w:document xmlns:w="'+$ns+'"><w:body><w:p><w:r><w:t>&e;</w:t></w:r></w:p></w:body></w:document>','<w:document xmlns:w="'+$ns+'"><w:body>'+('<w:p>'*65)+('</w:p>'*65)+'</w:body></w:document>')
foreach($x in $badXml){$f=Inspect (Docx-Outer $x);Assert-True (-not $f.collection_complete) 'XML_REFUSAL';Assert-True ($f.selected_payload_reads.Count -eq 2) 'XML_POSTREAD_TWO_LEDGERS';Assert-True ($f.selected_payload_returned_bytes -gt 0) 'XML_POSTREAD_RETURNED_NONZERO'}
$attrs='';for($i=0;$i -lt 65;$i++){$attrs+=' a'+$i+'="x"'};$f=Inspect (Docx-Outer ('<w:document xmlns:w="'+$ns+'"><w:body><w:p'+$attrs+'/></w:body></w:document>'));Assert-True (-not $f.collection_complete) 'XML_ATTRIBUTE_LIMIT';Assert-True ($f.selected_payload_reads.Count -eq 2) 'XML_ATTR_LEDGER'
# Direct XML node-budget fixture avoids ZIP container policy becoming the cause.
$nodeXml=Bytes ('<w:document xmlns:w="'+$ns+'"><w:body>'+('<x/>'*100001)+'</w:body></w:document>');$nodeFailed=$false
try{& $module {param($b)$c=H5-NewContext;H5-XmlBody $c $b} $nodeXml|Out-Null}catch{$nodeFailed=$true};Assert-True $nodeFailed 'XML_NODE_LIMIT'
# Transport compression failure/full-fit and aggregate boundary use actual helper.
& $module {
    $c=H5-NewContext;$c.facts=@{};$b=[byte[]]::new(70000);$rng=[Random]::new(17);$rng.NextBytes($b)
    H5-Transport $c 0 -1 'synthetic_raw' $b 'RAW_BYTES' $false
    if($c.documents[0].full -or $c.documents[0].preview_bytes -gt 4096 -or (H5-JsonBytes @($c.documents.ToArray())).Length -gt 32768){throw 'TRANSPORT_PREVIEW_LIMIT'}
    $c=H5-NewContext;$b=[byte[]]::new(50000);H5-Transport $c 0 -1 'compressible' $b 'RAW_BYTES' $false
    if(-not $c.documents[0].full -or $c.documents[0].transport_encoding -cne 'gzip-base64'){throw 'TRANSPORT_GZIP_FULL'}
    $ms=[IO.MemoryStream]::new([Convert]::FromBase64String($c.documents[0].payload_base64),$false);$gz=[IO.Compression.GZipStream]::new($ms,[IO.Compression.CompressionMode]::Decompress);$out=[IO.MemoryStream]::new();try{$gz.CopyTo($out);if($out.Length -ne 50000){throw 'TRANSPORT_GZIP_LENGTH'}}finally{$gz.Dispose();$ms.Dispose();$out.Dispose()}
    $c=H5-NewContext
    for($i=0;$i -lt 40;$i++){H5-Problem $c 'synthetic' 'FIXED_DIAGNOSTIC' $i -1 'field' 'observed' 'expected'}
    if(-not $c.errors_overflow -or $c.errors.Count -gt 32 -or (H5-JsonBytes @($c.errors.ToArray())).Length -gt 8192){throw 'DIAGNOSTIC_LIMIT'}
    $c=H5-NewContext;$b=[byte[]]::new(20000);[Random]::new(19).NextBytes($b)
    for($i=0;$i -lt 8;$i++){try{H5-Transport $c $i -1 'aggregate' $b 'RAW_BYTES' $false}catch{}}
    if((H5-JsonBytes @($c.documents.ToArray())).Length -gt 32768){throw 'DOCUMENT_AGGREGATE_LIMIT'}
}
Write-Output ([ordered]@{schema='route2_h5_synthetic_harness_result_v1';assertions=$checks;scope='SYNTHETIC_HELPERS_ONLY';actual_package_opened=$false;collect_invoked=$false;runtime_authority='NONE'}|ConvertTo-Json -Compress)
