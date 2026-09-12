[CmdletBinding()]
param(
    [string]$Manifest,
    [string]$Output
)

$ErrorActionPreference = 'Stop'
$scriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

if ([string]::IsNullOrWhiteSpace($Manifest)) {
    $Manifest = Join-Path $scriptRoot 'Unleashed-DualSense-Touch.ipa.manifest.json'
}
if ([string]::IsNullOrWhiteSpace($Output)) {
    $Output = Join-Path $scriptRoot 'Unleashed-DualSense-Touch.ipa'
}

function ConvertTo-HexString {
    param([byte[]]$Bytes)
    return [System.BitConverter]::ToString($Bytes).Replace('-', '')
}

$manifestPath = [System.IO.Path]::GetFullPath($Manifest)
$partsDirectory = [System.IO.Path]::GetDirectoryName($manifestPath)
$outputPath = [System.IO.Path]::GetFullPath($Output)

if (Test-Path -LiteralPath $outputPath) {
    throw "Refusing to overwrite existing output: $outputPath"
}

$metadata = Get-Content -Raw -LiteralPath $manifestPath | ConvertFrom-Json
$buffer = New-Object byte[] (8MB)
$fullHash = [System.Security.Cryptography.IncrementalHash]::CreateHash(
    [System.Security.Cryptography.HashAlgorithmName]::SHA256
)
$outputStream = $null

try {
    $outputStream = [System.IO.File]::Open($outputPath, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write)
    $totalBytes = [int64]0

    foreach ($part in $metadata.parts) {
        $partPath = Join-Path $partsDirectory $part.name
        if (-not (Test-Path -LiteralPath $partPath -PathType Leaf)) {
            throw "Missing release part: $partPath"
        }

        $partInfo = Get-Item -LiteralPath $partPath
        if ($partInfo.Length -ne [int64]$part.size) {
            throw "Size mismatch for $($part.name)"
        }

        $partHash = [System.Security.Cryptography.IncrementalHash]::CreateHash(
            [System.Security.Cryptography.HashAlgorithmName]::SHA256
        )
        $partStream = $null
        try {
            $partStream = [System.IO.File]::OpenRead($partPath)
            while (($count = $partStream.Read($buffer, 0, $buffer.Length)) -gt 0) {
                $outputStream.Write($buffer, 0, $count)
                $partHash.AppendData($buffer, 0, $count)
                $fullHash.AppendData($buffer, 0, $count)
                $totalBytes += $count
            }
            $actualPartHash = ConvertTo-HexString -Bytes ($partHash.GetHashAndReset())
        }
        finally {
            if ($partStream) { $partStream.Dispose() }
            $partHash.Dispose()
        }

        if ($actualPartHash -ne $part.sha256.ToUpperInvariant()) {
            throw "SHA-256 mismatch for $($part.name)"
        }
        Write-Host "Verified $($part.name)"
    }

    $outputStream.Dispose()
    $outputStream = $null
    $actualFullHash = ConvertTo-HexString -Bytes ($fullHash.GetHashAndReset())

    if ($totalBytes -ne [int64]$metadata.size) {
        throw 'Reconstructed IPA size does not match the manifest.'
    }
    if ($actualFullHash -ne $metadata.sha256.ToUpperInvariant()) {
        throw 'Reconstructed IPA SHA-256 does not match the manifest.'
    }

    Write-Host "Ready for Sideloadly: $outputPath"
    Write-Host "SHA-256: $actualFullHash"
}
catch {
    if ($outputStream) { $outputStream.Dispose() }
    if (Test-Path -LiteralPath $outputPath) {
        Remove-Item -LiteralPath $outputPath -Force
    }
    throw
}
finally {
    $fullHash.Dispose()
}
