[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
$root=Split-Path $PSScriptRoot -Parent
$compiler='C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe'
$source=Join-Path $root 'source/windows'
$files=@('Deployment.cs','Gateway.cs','Artifacts.cs','Client.cs','Portal.cs','Wizard.cs') | ForEach-Object { Join-Path $source $_ }
& $compiler /nologo /codepage:65001 /target:winexe /platform:x64 /r:System.Net.Http.dll /r:System.Web.Extensions.dll /r:System.Security.dll /r:System.IO.Compression.dll /r:System.IO.Compression.FileSystem.dll /r:System.Windows.Forms.dll /r:System.Drawing.dll "/out:$PSScriptRoot/MiniPCConnect.exe" @files
if($LASTEXITCODE -ne 0){throw 'Helper compilation failed'}
Write-Host 'Helper rebuilt. Have company IT sign/approve it before publication; publish a fresh SHA256SUMS.txt after packaging.'
