[CmdletBinding()]
param(
    [switch]$SkipBuild,
    [ValidatePattern('^MiniPC-Connect[-A-Za-z0-9.]+\.zip$')]
    [string]$OutputName='MiniPC-Connect-Company-Handoff-v2-20261025.zip'
)
$ErrorActionPreference='Stop'
$pilot=Split-Path $PSScriptRoot -Parent
$original=Test-Path -LiteralPath (Join-Path $pilot 'connect/windows/Deployment.cs')
if($original){
    $server=Join-Path $pilot 'connect/server'
    $portal=Join-Path $pilot 'connect/portal'
    $native=Join-Path $pilot 'connect/windows'
    $binary=Join-Path $pilot 'connect/build/MiniPCConnect.exe'
    $helperBuild=Join-Path $PSScriptRoot 'build-helper.ps1'
    $docs=Join-Path $PSScriptRoot 'handoff'
    $rootDocs=$docs
}else{
    $server=Join-Path $pilot 'server'
    $portal=Join-Path $pilot 'portal'
    $native=Join-Path $pilot 'source/windows'
    $binary=Join-Path $pilot 'windows/MiniPCConnect.exe'
    $helperBuild=Join-Path $pilot 'windows/build-helper.ps1'
    $docs=Join-Path $pilot 'handoff'
    $rootDocs=$pilot
}
if(-not $SkipBuild){
    if($original){ & (Join-Path $pilot 'connect/build.ps1') }
    else{ & $helperBuild }
    if($LASTEXITCODE -ne 0){throw 'Native build failed'}
}
$release=Join-Path $pilot 'releases'
New-Item -ItemType Directory -Force -Path $release | Out-Null
$path=Join-Path $release $OutputName
if(Test-Path -LiteralPath $path){throw 'Release already exists. Choose a new -OutputName; do not overwrite an accepted release.'}
Add-Type -AssemblyName System.IO.Compression.FileSystem
Add-Type -AssemblyName System.IO.Compression
$entries=[ordered]@{}
$entries['windows/MiniPCConnect.exe']=$binary
$entries['windows/build-helper.ps1']=$helperBuild
foreach($name in @('README.md','ACCEPTANCE.md')){
    $entries[$name]=Join-Path $(if($original){$PSScriptRoot}else{$pilot}) $name
}
foreach($name in @('00-START-HERE-FA.md','CODEX-HANDOFF.md')){$entries[$name]=Join-Path $rootDocs $name}
foreach($file in Get-ChildItem -LiteralPath $docs -File){
    if($file.Extension -in @('.md','.json') -and $file.Name -notin @('00-START-HERE-FA.md','CODEX-HANDOFF.md')){
        $entries["handoff/$($file.Name)"]=$file.FullName
    }
}
foreach($name in @('index.html','style.css','app.js')){$entries["portal/$name"]=Join-Path $portal $name}
foreach($file in Get-ChildItem -LiteralPath $server -File){
    if($file.Extension -eq '.py' -or $file.Name -eq 'requirements.txt'){$entries["server/$($file.Name)"]=$file.FullName}
}
foreach($file in Get-ChildItem -LiteralPath (Join-Path $server 'tests') -Filter '*.py' -File){$entries["server/tests/$($file.Name)"]=$file.FullName}
foreach($file in Get-ChildItem -LiteralPath $PSScriptRoot -File){
    if($file.Extension -in @('.py','.json') -or $file.Name -eq 'build-package.ps1'){$entries["company/$($file.Name)"]=$file.FullName}
}
foreach($file in Get-ChildItem -LiteralPath $native -Filter '*.cs' -File){$entries["source/windows/$($file.Name)"]=$file.FullName}
foreach($entry in $entries.GetEnumerator()){
    if(-not (Test-Path -LiteralPath $entry.Value -PathType Leaf)){throw "Missing source: $($entry.Key)"}
}
$temporary=$path+'.'+[Guid]::NewGuid().ToString('N')+'.partial'
$stream=[IO.File]::Open($temporary,[IO.FileMode]::CreateNew,[IO.FileAccess]::ReadWrite)
$archive=[IO.Compression.ZipArchive]::new($stream,[IO.Compression.ZipArchiveMode]::Create,$true)
$manifest=[Collections.Generic.List[string]]::new()
try{
    foreach($entry in $entries.GetEnumerator()){
        [IO.Compression.ZipFileExtensions]::CreateEntryFromFile($archive,$entry.Value,$entry.Key,[IO.Compression.CompressionLevel]::Optimal)|Out-Null
        $manifest.Add((Get-FileHash -LiteralPath $entry.Value -Algorithm SHA256).Hash.ToLowerInvariant()+'  '+$entry.Key)
    }
    $checksum=$archive.CreateEntry('MANIFEST.sha256')
    $writer=[IO.StreamWriter]::new($checksum.Open(),[Text.UTF8Encoding]::new($false))
    try{$writer.Write(($manifest -join "`n")+"`n")}finally{$writer.Dispose()}
}finally{$archive.Dispose();$stream.Dispose()}
Move-Item -LiteralPath $temporary -Destination $path
$hash=(Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant()
[IO.File]::WriteAllText(($path+'.sha256'),"$hash  $OutputName`n",[Text.UTF8Encoding]::new($false))
Write-Host "Portable package: $path"
Write-Host "SHA256: $hash"
