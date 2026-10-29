# extract.ps1
# Extract all localizable strings from CrypTool 2 German satellite assemblies.
# Output: data/strings.json  (flat list) and data/by-assembly.json (grouped)

param(
    [string]$Root = "E:\开源软件\CrypTool 2",
    [string]$OutDir = ""
)

$ErrorActionPreference = "Stop"
if (-not $OutDir) { $OutDir = Join-Path $PSScriptRoot "..\data" }
$OutDir = (Resolve-Path -LiteralPath $OutDir).Path

Write-Host "Scanning $Root for *.resources.dll ..."
$satellites = Get-ChildItem -LiteralPath $Root -Recurse -File -Filter '*.resources.dll' -ErrorAction SilentlyContinue |
    Where-Object { $_.Directory.Name -eq 'de' }

Write-Host "Found $($satellites.Count) German satellite assemblies."

$flat = [System.Collections.Generic.List[object]]::new()
$failures = [System.Collections.Generic.List[object]]::new()

foreach ($file in $satellites) {
    # Relative directory of the satellite's culture folder (de), e.g. "" or "CrypPlugins"
    $relParent = $file.Directory.Parent.FullName.Substring($Root.Length).TrimStart('\')

    try {
        $asm = [System.Reflection.Assembly]::LoadFile($file.FullName)
        foreach ($resName in $asm.GetManifestResourceNames()) {
            $stream = $asm.GetManifestResourceStream($resName)
            if (-not $stream) { continue }
            $reader = New-Object System.Resources.ResourceReader($stream)
            try {
                $enum = $reader.GetEnumerator()
                while ($enum.MoveNext()) {
                    $flat.Add([pscustomobject]@{
                        assembly   = $file.Name
                        rel_parent = $relParent
                        resource   = $resName
                        key        = [string]$enum.Key
                        source_de  = [string]$enum.Value
                    })
                }
            } finally { $reader.Close(); $stream.Close() }
        }
    } catch {
        $failures.Add([pscustomobject]@{ assembly = $file.FullName; error = $_.Exception.Message })
    }
}

Write-Host "Extracted $($flat.Count) entries; failures: $($failures.Count)"

$json = $flat | ConvertTo-Json -Depth 4
[IO.File]::WriteAllText((Join-Path $OutDir 'strings.json'), $json, [Text.UTF8Encoding]::new($false))

# Grouped view, easier for review
$grouped = $flat | Group-Object assembly | ForEach-Object {
    [pscustomobject]@{
        assembly   = $_.Name
        rel_parent = $_.Group[0].rel_parent
        count      = $_.Count
        entries    = $_.Group | Select-Object resource, key, source_de
    }
}
$json2 = $grouped | ConvertTo-Json -Depth 6
[IO.File]::WriteAllText((Join-Path $OutDir 'by-assembly.json'), $json2, [Text.UTF8Encoding]::new($false))

if ($failures.Count -gt 0) {
    $json3 = $failures | ConvertTo-Json -Depth 4
    [IO.File]::WriteAllText((Join-Path $OutDir 'failures.json'), $json3, [Text.UTF8Encoding]::new($false))
}

Write-Host "Written: strings.json, by-assembly.json"
