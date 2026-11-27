<#
.SYNOPSIS
    Draw the Fly Notes icon (a yellow sticky note with a green check mark) and write
    assets/fly_notes.ico with every size from 16 to 256 px.

.DESCRIPTION
    Each size is drawn on its own, not scaled down from the largest one, so the small
    sizes used by the taskbar and title bar stay sharp. The .ico stores PNG images,
    which Windows Vista and later read.

    powershell -NoProfile -File scripts/make_icon.ps1 [-PreviewDir <folder>]

    -PreviewDir also saves each size as a PNG there.
#>
param(
    [string]$OutFile = (Join-Path $PSScriptRoot "..\assets\fly_notes.ico"),
    [string]$PreviewDir = ""
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$Sizes = 16, 24, 32, 48, 64, 128, 256

function Get-Color([string]$hex) { [System.Drawing.ColorTranslator]::FromHtml($hex) }

$NoteFill = Get-Color "#FFE45C"
$BandFill = Get-Color "#F7CF33"
$FoldFill = Get-Color "#E0B21F"
$Outline = Get-Color "#8A6A00"
$Check = Get-Color "#2E8A47"

function New-IconBitmap([int]$s) {
    $bmp = New-Object System.Drawing.Bitmap $s, $s, ([System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode = "AntiAlias"
    $g.PixelOffsetMode = "Half"
    $g.Clear([System.Drawing.Color]::Transparent)

    # Note outline: square with rounded top/left corners and a folded bottom-right corner.
    # Sizes up to 24 px get no folded corner (it would crowd the check mark) and a
    # thicker check; up to 32 px the outline is 1 px.
    $small = $s -le 24
    $line = if ($s -le 32) { 1.0 } else { $s / 40.0 }
    $m = [Math]::Max(1.0, [Math]::Round($s * 0.06)) + $line / 2
    $r = [Math]::Max(1.0, $s * 0.08)
    $fold = if ($small) { 0 } else { [Math]::Round($s * 0.26) }
    $x1 = $m; $y1 = $m; $x2 = $s - $m; $y2 = $s - $m

    $note = New-Object System.Drawing.Drawing2D.GraphicsPath
    $note.AddArc($x1, $y1, 2 * $r, 2 * $r, 180, 90)
    $note.AddArc($x2 - 2 * $r, $y1, 2 * $r, 2 * $r, 270, 90)
    $note.AddLine($x2, $y1 + $r, $x2, $y2 - $fold)
    $note.AddLine($x2, $y2 - $fold, $x2 - $fold, $y2)
    $note.AddArc($x1, $y2 - 2 * $r, 2 * $r, 2 * $r, 90, 90)
    $note.CloseFigure()

    $g.FillPath((New-Object System.Drawing.SolidBrush $NoteFill), $note)

    # Darker band along the top, like the sticky strip of a real note.
    $g.SetClip($note)
    $band = [Math]::Max(2.0, [Math]::Round($s * 0.2))
    $g.FillRectangle((New-Object System.Drawing.SolidBrush $BandFill), 0, 0, $s, $y1 + $band)
    $g.ResetClip()

    # The folded corner.
    if (-not $small) {
        $flap = [System.Drawing.PointF[]]@(
            (New-Object System.Drawing.PointF ($x2 - $fold), ($y2 - $fold)),
            (New-Object System.Drawing.PointF $x2, ($y2 - $fold)),
            (New-Object System.Drawing.PointF ($x2 - $fold), $y2)
        )
        $g.FillPolygon((New-Object System.Drawing.SolidBrush $FoldFill), $flap)
    }

    $pen = New-Object System.Drawing.Pen $Outline, $line
    $pen.LineJoin = "Round"
    $g.DrawPath($pen, $note)
    if (-not $small) { $g.DrawPolygon($pen, $flap) }

    # Green check mark, a little above centre where the fold takes the bottom-right.
    $cw = if ($small) { [Math]::Max(2.0, $s * 0.15) } else { $s * 0.12 }
    $checkPen = New-Object System.Drawing.Pen $Check, $cw
    $checkPen.StartCap = "Round"; $checkPen.EndCap = "Round"; $checkPen.LineJoin = "Round"
    $c = if ($small) { 0.25, 0.56, 0.43, 0.74, 0.76, 0.38 } else { 0.27, 0.55, 0.43, 0.69, 0.73, 0.37 }
    $pts = [System.Drawing.PointF[]]@(
        (New-Object System.Drawing.PointF ($s * $c[0]), ($s * $c[1])),
        (New-Object System.Drawing.PointF ($s * $c[2]), ($s * $c[3])),
        (New-Object System.Drawing.PointF ($s * $c[4]), ($s * $c[5]))
    )
    $g.DrawLines($checkPen, $pts)

    $g.Dispose()
    return $bmp
}

$pngs = @()
foreach ($s in $Sizes) {
    $bmp = New-IconBitmap $s
    $ms = New-Object System.IO.MemoryStream
    $bmp.Save($ms, [System.Drawing.Imaging.ImageFormat]::Png)
    if ($PreviewDir) {
        New-Item -ItemType Directory -Force $PreviewDir | Out-Null
        $bmp.Save((Join-Path $PreviewDir "icon-$s.png"), [System.Drawing.Imaging.ImageFormat]::Png)
    }
    $bmp.Dispose()
    $pngs += , $ms.ToArray()
}

# ICONDIR + one ICONDIRENTRY per size, then the PNG data.
$out = New-Object System.IO.MemoryStream
$w = New-Object System.IO.BinaryWriter $out
$w.Write([UInt16]0); $w.Write([UInt16]1); $w.Write([UInt16]$Sizes.Count)
$offset = 6 + 16 * $Sizes.Count
for ($i = 0; $i -lt $Sizes.Count; $i++) {
    $dim = if ($Sizes[$i] -ge 256) { 0 } else { $Sizes[$i] }
    $w.Write([byte]$dim); $w.Write([byte]$dim); $w.Write([byte]0); $w.Write([byte]0)
    $w.Write([UInt16]1); $w.Write([UInt16]32)
    $w.Write([UInt32]$pngs[$i].Length); $w.Write([UInt32]$offset)
    $offset += $pngs[$i].Length
}
foreach ($p in $pngs) { $w.Write($p) }
$w.Flush()
$target = Join-Path (Resolve-Path -LiteralPath (Split-Path $OutFile)).Path (Split-Path $OutFile -Leaf)
[System.IO.File]::WriteAllBytes($target, $out.ToArray())
Write-Output "Wrote $target ($($Sizes -join ', ') px)"
