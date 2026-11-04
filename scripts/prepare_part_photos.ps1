param([Parameter(Mandatory = $true)][string]$Manifest)
# Local thumbnail encoding only. No network, credentials or catalog writes.
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$photoRoot = Join-Path $PSScriptRoot '..\counterpilot\static\parts'
[System.IO.Directory]::CreateDirectory($photoRoot) | Out-Null
$encoder = [System.Drawing.Imaging.ImageCodecInfo]::GetImageEncoders() | Where-Object MimeType -eq 'image/jpeg'
foreach ($entry in (Get-Content -LiteralPath $Manifest -Raw | ConvertFrom-Json)) {
    if ($entry.kind -notmatch '^[a-z_]+$') { throw 'Invalid part type filename' }
    $source = [System.Drawing.Image]::FromFile($entry.path)
    $bitmap = New-Object System.Drawing.Bitmap 480, 360
    $graphics = [System.Drawing.Graphics]::FromImage($bitmap)
    $parameters = New-Object System.Drawing.Imaging.EncoderParameters 1
    try {
        $graphics.Clear([System.Drawing.ColorTranslator]::FromHtml('#f7f8f4'))
        $graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
        $scale = [Math]::Min(480.0 / $source.Width, 360.0 / $source.Height)
        $width = [int]($source.Width * $scale)
        $height = [int]($source.Height * $scale)
        $graphics.DrawImage($source, [int]((480-$width)/2), [int]((360-$height)/2), $width, $height)
        $parameters.Param[0] = New-Object System.Drawing.Imaging.EncoderParameter ([System.Drawing.Imaging.Encoder]::Quality), ([long]84)
        $bitmap.Save((Join-Path $photoRoot ($entry.kind + '.jpg')), $encoder, $parameters)
    } finally { $parameters.Dispose(); $graphics.Dispose(); $bitmap.Dispose(); $source.Dispose() }
}
Write-Output 'Prepared local 480 x 360 JPEG part photos.'
