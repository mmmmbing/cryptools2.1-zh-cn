# rebuild.ps1
# Rebuild Chinese (zh-CN) satellite assemblies from translated strings.
#
# Strategy per satellite:
#   1. Read every embedded .resources from the German satellite.
#   2. Replace only String values with their translation; keep Bitmap/Icon/null
#      payloads byte-identical.
#   3. Rewrite the resource under the *target* culture name
#      (e.g. Foo.de.resources -> Foo.zh-CN.resources), because ResourceManager
#      resolves the culture suffix from the embedded resource name.
#   4. Generate a tiny C# AssemblyInfo with AssemblyCulture("zh-CN") and compile
#      it together with the .resources files via csc.exe, so the produced DLL is
#      a real satellite assembly that .NET will probe in a zh-CN folder.

param(
    [string]$Root      = "E:\开源软件\CrypTool 2",
    [string]$OutDir    = "",
    [string]$BuildDir  = "",
    [string]$Csc       = "C:\Windows\Microsoft.NET\Framework64\v4.0.30319\csc.exe"
)

$ErrorActionPreference = "Stop"
if (-not $OutDir)   { $OutDir   = Join-Path $PSScriptRoot "..\out\zh-CN" }
if (-not $BuildDir) { $BuildDir = Join-Path $PSScriptRoot "..\build" }
$OutDir   = [IO.Path]::GetFullPath($OutDir)
$BuildDir = [IO.Path]::GetFullPath($BuildDir)
New-Item -ItemType Directory -Force -Path $OutDir   | Out-Null
New-Item -ItemType Directory -Force -Path $BuildDir | Out-Null

$cachePath = Join-Path $PSScriptRoot "..\data\translation-cache.json"
if (-not (Test-Path $cachePath)) { throw "translation-cache.json missing; run translate.py first" }

# PowerShell's ConvertFrom-Json uses a case-insensitive dictionary, and German
# text contains strings differing only by capitalisation ("Verschlüsselter
# Text" / "verschlüsselter Text"). Reading the cache directly therefore fails
# with DUPLICATE KEYS. Use the flattened SHA-1 keyed form instead
# (produced by scripts\flatten-cache.py); SHA-1 keeps lookups case-sensitive.
$flatPath = Join-Path $PSScriptRoot "..\data\translation-flat.json"
if (-not (Test-Path $flatPath)) {
    $py = $null
    foreach ($cand in @("python3", "python")) {
        $c = Get-Command $cand -ErrorAction SilentlyContinue
        if ($c) { $py = $c.Source; break }
    }
    if (-not $py) { throw "translation-flat.json missing and no python found; run scripts\flatten-cache.py" }
    & $py (Join-Path $PSScriptRoot "flatten-cache.py") | Out-Host
}

$flatRecords = Get-Content $flatPath -Raw -Encoding UTF8 | ConvertFrom-Json
$cache = @{}
foreach ($rec in $flatRecords) { $cache[$rec.h] = $rec.t }

function Get-Sha1([string]$text) {
    $sha = [Security.Cryptography.SHA1]::Create()
    try {
        $bytes = [Text.Encoding]::UTF8.GetBytes($text)
        return ([BitConverter]::ToString($sha.ComputeHash($bytes)) -replace '-', '').ToLowerInvariant()
    } finally { $sha.Dispose() }
}

function Get-Translation([string]$src) {
    if ([string]::IsNullOrEmpty($src)) { return $src }
    $h = Get-Sha1 $src
    if ($cache.ContainsKey($h)) { return [string]$cache[$h] }
    # Multi-line resources carry CRLF, but the CSV/JSON round-trip that fed the
    # translator normalised them to LF. Retry with the normalised form so
    # 181 line-break-bearing entries (including the long HTML help pages)
    # resolve instead of silently falling back to German.
    $norm = $src -replace "`r`n", "`n"
    if ($norm -ne $src) {
        $h2 = Get-Sha1 $norm
        if ($cache.ContainsKey($h2)) { return [string]$cache[$h2] }
    }
    return $null
}

$satellites = Get-ChildItem -LiteralPath $Root -Recurse -File -Filter '*.resources.dll' |
              Where-Object { $_.Directory.Name -eq 'de' }
Write-Host "Rebuilding $($satellites.Count) satellites -> $OutDir"

$totalOk = 0; $totalMiss = 0; $built = 0
$report = [System.Collections.Generic.List[object]]::new()

foreach ($file in $satellites) {
    $relParent = $file.Directory.Parent.FullName.Substring($Root.Length).TrimStart('\')
    $targetDir = if ($relParent) { Join-Path (Join-Path $OutDir $relParent) 'zh-CN' } else { Join-Path $OutDir 'zh-CN' }
    New-Item -ItemType Directory -Force -Path $targetDir | Out-Null

    $asmName = [IO.Path]::GetFileNameWithoutExtension($file.Name)   # e.g. CrypWin.resources
    $workDir = Join-Path $BuildDir $asmName
    New-Item -ItemType Directory -Force -Path $workDir | Out-Null

    $asm = [System.Reflection.Assembly]::LoadFile($file.FullName)
    $resFiles = @()
    $okCount = 0; $missCount = 0

    foreach ($resName in $asm.GetManifestResourceNames()) {
        # Foo.de.resources -> Foo.zh-CN.resources (culture suffix drives probing)
        $zhName = $resName -replace '\.de\.resources$', '.zh-CN.resources'
        if ($zhName -eq $resName) { $zhName = "$resName.zh-CN" }

        $resPath = Join-Path $workDir $zhName
        $in = $asm.GetManifestResourceStream($resName)
        $reader = New-Object System.Resources.ResourceReader($in)

        $set = New-Object 'System.Collections.Generic.List[object]'
        $enum = $reader.GetEnumerator()
        while ($enum.MoveNext()) {
            $key = [string]$enum.Key
            $val = $enum.Value
            if ($val -is [string] -and -not [string]::IsNullOrEmpty($val)) {
                $zh = Get-Translation $val
                if ($null -eq $zh) {
                    # No translation available: keep the German text so the UI
                    # degrades to a readable language instead of showing nothing.
                    $zh = $val
                    $missCount++
                } else { $okCount++ }
                $set.Add([pscustomobject]@{ Key = $key; Value = $zh; Kind = 'string' })
            } else {
                # Bitmap / Icon / null: preserve the original object untouched.
                $set.Add([pscustomobject]@{ Key = $key; Value = $val; Kind = 'other' })
            }
        }
        $reader.Close(); $in.Close()

        # ResourceWriter must run on the same objects to preserve binary types.
        $out = [IO.File]::Create($resPath)
        $writer = New-Object System.Resources.ResourceWriter($out)
        foreach ($entry in $set) {
            if ($entry.Kind -eq 'string') { $writer.AddResource($entry.Key, [string]$entry.Value) }
            else { $writer.AddResource($entry.Key, $entry.Value) }
        }
        $writer.Close(); $out.Close()
        $resFiles += $resPath
    }

    # Satellite identity: culture must be zh-CN, no public key (originals unsigned).
    $ver = $asm.GetName().Version
    $verStr = if ($ver) { $ver.ToString() } else { "1.0.0.0" }
    $csPath = Join-Path $workDir 'AssemblyInfo.cs'
    $cs = @"
using System.Reflection;
[assembly: AssemblyVersion("$verStr")]
[assembly: AssemblyCulture("zh-CN")]
"@
    [IO.File]::WriteAllText($csPath, $cs, [Text.UTF8Encoding]::new($false))

    $outDll = Join-Path $targetDir ($asmName + '.dll')

    # Match the source assembly's PE machine type. The German satellites are
    # PE32+ / x86_64; compiling with the default AnyCPU target yields an x86
    # PE32 image whose architecture disagrees with the original, and the CLR
    # then refuses to probe it alongside the shipped assemblies.
    $srcMachine = $null
    try {
        $fs = [IO.File]::OpenRead($file.FullName)
        $br = New-Object IO.BinaryReader($fs)
        $fs.Position = 0x3C
        $peOff = $br.ReadInt32()
        $fs.Position = $peOff + 4
        $srcMachine = $br.ReadUInt16()
        $br.Close(); $fs.Close()
    } catch { }
    $machineArg = if ($srcMachine -eq 0x8664) { '/platform:x64' }
                  elseif ($srcMachine -eq 0x14c) { '/platform:x86' }
                  else { '/platform:anycpu' }

    $args = @('/nologo', '/target:library', $machineArg, "/out:$outDll",
              "/resource:$($resFiles[0]),$([IO.Path]::GetFileName($resFiles[0]))")
    for ($i = 1; $i -lt $resFiles.Count; $i++) {
        $args += "/resource:$($resFiles[$i]),$([IO.Path]::GetFileName($resFiles[$i]))"
    }
    $args += $csPath

    $proc = Start-Process -FilePath $Csc -ArgumentList $args -NoNewWindow -Wait -PassThru `
                          -RedirectStandardOutput (Join-Path $workDir 'csc.out') `
                          -RedirectStandardError  (Join-Path $workDir 'csc.err')
    if ($proc.ExitCode -ne 0) {
        $err = Get-Content (Join-Path $workDir 'csc.err') -Raw -ErrorAction SilentlyContinue
        Write-Host "FAILED $asmName : $err"
        $report.Add([pscustomobject]@{ assembly=$asmName; ok=$false; error=$err; strings=$okCount; missing=$missCount })
    } else {
        $built++
        $report.Add([pscustomobject]@{ assembly=$asmName; ok=$true; error=$null; strings=$okCount; missing=$missCount })
    }

    $totalOk += $okCount; $totalMiss += $missCount
    Remove-Item -Recurse -Force $workDir -ErrorAction SilentlyContinue
}

Write-Host ""
Write-Host "=== RESULT ==="
Write-Host "satellites built      : $built / $($satellites.Count)"
Write-Host "translated strings    : $totalOk"
Write-Host "fell back to German   : $totalMiss"

$reportPath = Join-Path $PSScriptRoot "..\data\rebuild-report.json"
[IO.File]::WriteAllText($reportPath, ($report | ConvertTo-Json -Depth 4), [Text.UTF8Encoding]::new($false))
Write-Host "report: $reportPath"
