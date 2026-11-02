Add-Type -AssemblyName System.Drawing

$baseDir = Join-Path $PSScriptRoot "..\extracted_menu_textures"
$outDir = Join-Path $PSScriptRoot "..\translations\textures"
if (-not (Test-Path $outDir)) {
    New-Item -ItemType Directory -Path $outDir -Force | Out-Null
}

function Clear-Region($g, $x, $y, $w, $h) {
    $clearBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(0, 0, 0, 0))
    $origMode = $g.CompositingMode
    $g.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceCopy
    $g.FillRectangle($clearBrush, [System.Drawing.Rectangle]::new([int]$x, [int]$y, [int]$w, [int]$h))
    $g.CompositingMode = $origMode
    $clearBrush.Dispose()
}

function Draw-TextWithOutline($g, $text, $font, $fillColor, $strokeColor, $strokeWidth, $cx, $cy, $align='Center') {
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAlias

    $sf = New-Object System.Drawing.StringFormat
    if ($align -eq 'Center') {
        $sf.Alignment = [System.Drawing.StringAlignment]::Center
    } elseif ($align -eq 'Near') {
        $sf.Alignment = [System.Drawing.StringAlignment]::Near
    } else {
        $sf.Alignment = [System.Drawing.StringAlignment]::Far
    }
    $sf.LineAlignment = [System.Drawing.StringAlignment]::Center

    $p = New-Object System.Drawing.Drawing2D.GraphicsPath
    $p.AddString($text, $font.FontFamily, [int]$font.Style, $font.Size, [System.Drawing.PointF]::new($cx, $cy), $sf)

    $strokePen = New-Object System.Drawing.Pen($strokeColor, $strokeWidth)
    $strokePen.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round
    $fillBrush = New-Object System.Drawing.SolidBrush($fillColor)

    $g.DrawPath($strokePen, $p)
    $g.FillPath($fillBrush, $p)

    $strokePen.Dispose()
    $fillBrush.Dispose()
    $p.Dispose()
    $sf.Dispose()
}

# =========================================================================
# 1. Options Screen (ac1040000.png) - pac104000.pac
# =========================================================================
$srcPath = Join-Path $baseDir "pac104000_ac1040000.png"
if (Test-Path $srcPath) {
    $src = [System.Drawing.Bitmap]::FromFile($srcPath)
    $bmp = New-Object System.Drawing.Bitmap($src.Width, $src.Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.DrawImage($src, 0, 0)

    # 1. Title "OPTIONS"
    Clear-Region $g 0 0 255 64
    $fontTitle = New-Object System.Drawing.Font('Arial Black', 28.0)
    Draw-TextWithOutline $g "OPTIONS" $fontTitle ([System.Drawing.Color]::FromArgb(255, 230, 255)) ([System.Drawing.Color]::FromArgb(100, 30, 160)) 6.0 125.0 32.0

    # 2. Categories: BGM, SFX, VOICE
    Clear-Region $g 255 0 245 32
    $fontCat = New-Object System.Drawing.Font('Arial Black', 11.5)
    $cGold = [System.Drawing.Color]::FromArgb(255, 250, 190)
    $cBrown = [System.Drawing.Color]::FromArgb(60, 25, 10)
    Draw-TextWithOutline $g "BGM"   $fontCat $cGold $cBrown 3.5 295.0 18.0
    Draw-TextWithOutline $g "SFX"   $fontCat $cGold $cBrown 3.5 375.0 18.0
    Draw-TextWithOutline $g "VOICE" $fontCat $cGold $cBrown 3.5 455.0 18.0

    # 3. VIBRATION
    Clear-Region $g 255 33 135 32
    Draw-TextWithOutline $g "VIBRATION" $fontCat $cGold $cBrown 3.5 320.0 48.0

    # 4. MESSAGE SPEED & AUTO WAIT
    Clear-Region $g 0 65 400 30
    Draw-TextWithOutline $g "MESSAGE SPEED" $fontCat $cGold $cBrown 3.5 87.0 80.0
    Draw-TextWithOutline $g "AUTO WAIT"     $fontCat $cGold $cBrown 3.5 283.0 80.0

    # 5. Buttons Pills
    $pillTexts = @('SLOW', 'NORM', 'FAST', 'MAX', 'ON', 'OFF')
    $fontPill = New-Object System.Drawing.Font('Arial Black', 8.5)
    $pillCenters = @(36.0, 108.0, 180.0, 252.0, 324.0, 396.0)

    $brushPillPurp = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 145, 100, 215))
    $brushPillYel  = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 245, 238, 165))
    $origMode = $g.CompositingMode
    $g.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceCopy
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias

    for ($i = 0; $i -lt 6; $i++) {
        $cx = $pillCenters[$i]
        $g.FillEllipse($brushPillPurp, [int]($cx - 28), 101, 56, 22)
        $g.FillEllipse($brushPillYel,  [int]($cx - 28), 133, 56, 22)
    }
    $g.CompositingMode = $origMode
    $brushPillPurp.Dispose()
    $brushPillYel.Dispose()

    for ($i = 0; $i -lt 6; $i++) {
        $cx = $pillCenters[$i]
        Draw-TextWithOutline $g $pillTexts[$i] $fontPill ([System.Drawing.Color]::FromArgb(255, 255, 255)) ([System.Drawing.Color]::FromArgb(50, 15, 60)) 2.5 $cx 111.5
        Draw-TextWithOutline $g $pillTexts[$i] $fontPill ([System.Drawing.Color]::FromArgb(80, 40, 10)) ([System.Drawing.Color]::FromArgb(255, 250, 180)) 2.5 $cx 143.5
    }

    # 6. Controller Legend
    Clear-Region $g 22 160 55 25
    Clear-Region $g 102 160 65 25
    Clear-Region $g 190 160 65 25
    Clear-Region $g 305 160 130 25
    $fontLegend = New-Object System.Drawing.Font('Arial Black', 9.5)
    Draw-TextWithOutline $g "BACK"    $fontLegend $cGold $cBrown 3.0 48.0 171.5
    Draw-TextWithOutline $g "OK"      $fontLegend $cGold $cBrown 3.0 125.0 171.5
    Draw-TextWithOutline $g "TEST"    $fontLegend $cGold $cBrown 3.0 215.0 171.5
    Draw-TextWithOutline $g "DEFAULT" $fontLegend $cGold $cBrown 3.0 370.0 171.5

    # 7. REVERT
    Clear-Region $g 330 215 85 25
    Draw-TextWithOutline $g "REVERT" $fontLegend $cGold $cBrown 3.0 372.0 227.0

    $dstPath = Join-Path $outDir "ac1040000.png"
    $bmp.Save($dstPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose()
    $bmp.Dispose()
    $src.Dispose()
    Write-Host "Generated: $dstPath"
}

# =========================================================================
# 2. Memories Screen (ac8011000.png) - pac801000.pac
# =========================================================================
$srcPath = Join-Path $baseDir "pac801000_ac8011000.png"
if (Test-Path $srcPath) {
    $src = [System.Drawing.Bitmap]::FromFile($srcPath)
    $bmp = New-Object System.Drawing.Bitmap($src.Width, $src.Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.DrawImage($src, 0, 0)

    # Title "MEMORIES" & "BACK"
    Clear-Region $g 0 0 135 65
    Clear-Region $g 145 0 75 30
    $fontTitle = New-Object System.Drawing.Font('Arial Black', 20.0)
    Draw-TextWithOutline $g "MEMORIES" $fontTitle ([System.Drawing.Color]::FromArgb(255, 230, 255)) ([System.Drawing.Color]::FromArgb(100, 30, 160)) 5.0 65.0 30.0
    $fontLegend = New-Object System.Drawing.Font('Arial Black', 9.5)
    Draw-TextWithOutline $g "BACK" $fontLegend ([System.Drawing.Color]::FromArgb(255, 250, 190)) ([System.Drawing.Color]::FromArgb(60, 25, 10)) 3.0 178.0 16.0

    # Character Ribbons (8 rows)
    $names = @(
        'Moka Akashiya',
        'Kurumu Kurono',
        'Yukari Sendo',
        'Mizore Shirayuki',
        'Ruby Tojo',
        'Kokoa Shuzen',
        'Otonashi Sisters',
        'Others'
    )
    $fontRibbon = New-Object System.Drawing.Font('Arial Black', 9.5)
    $cPurp = [System.Drawing.Color]::FromArgb(255, 128, 1, 253)
    $cPink = [System.Drawing.Color]::FromArgb(255, 229, 71, 91)
    $brushPurp = New-Object System.Drawing.SolidBrush($cPurp)
    $brushPink = New-Object System.Drawing.SolidBrush($cPink)

    $origMode = $g.CompositingMode
    $g.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceCopy
    for ($row = 0; $row -lt 8; $row++) {
        $cy = 92.0 + $row * 55.0
        # Fill left ribbon interior (x: 38..218, y: cy-12..cy+15)
        $g.FillRectangle($brushPurp, 38, [int]($cy - 12), 180, 27)
        # Fill right ribbon interior (x: 295..475, y: cy-12..cy+15)
        $g.FillRectangle($brushPink, 295, [int]($cy - 12), 180, 27)
    }
    $g.CompositingMode = $origMode
    $brushPurp.Dispose()
    $brushPink.Dispose()

    for ($row = 0; $row -lt 8; $row++) {
        $cy = 92.0 + $row * 55.0
        $text = $names[$row]
        Draw-TextWithOutline $g $text $fontRibbon ([System.Drawing.Color]::FromArgb(255, 255, 255)) ([System.Drawing.Color]::FromArgb(60, 5, 40)) 3.0 128.0 $cy
        Draw-TextWithOutline $g $text $fontRibbon ([System.Drawing.Color]::FromArgb(255, 255, 255)) ([System.Drawing.Color]::FromArgb(90, 10, 30)) 3.0 384.0 $cy
    }

    $dstPath = Join-Path $outDir "ac8011000.png"
    $bmp.Save($dstPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose()
    $bmp.Dispose()
    $src.Dispose()
    Write-Host "Generated: $dstPath"
}

# =========================================================================
# 3. Load Header (ac1031100.png) - pac103000.pac
# =========================================================================
$srcPath = Join-Path $baseDir "pac103000_ac1031100.png"
if (Test-Path $srcPath) {
    $src = [System.Drawing.Bitmap]::FromFile($srcPath)
    $bmp = New-Object System.Drawing.Bitmap($src.Width, $src.Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.DrawImage($src, 0, 0)

    Clear-Region $g 0 0 160 60
    Clear-Region $g 20 55 65 30
    $fontTitle = New-Object System.Drawing.Font('Arial Black', 24.0)
    Draw-TextWithOutline $g "LOAD" $fontTitle ([System.Drawing.Color]::FromArgb(220, 255, 100)) ([System.Drawing.Color]::FromArgb(20, 80, 20)) 5.5 80.0 32.0
    $fontLegend = New-Object System.Drawing.Font('Arial Black', 9.5)
    Draw-TextWithOutline $g "BACK" $fontLegend ([System.Drawing.Color]::FromArgb(255, 250, 190)) ([System.Drawing.Color]::FromArgb(60, 25, 10)) 3.0 48.0 72.0

    $dstPath = Join-Path $outDir "ac1031100.png"
    $bmp.Save($dstPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose()
    $bmp.Dispose()
    $src.Dispose()
    Write-Host "Generated: $dstPath"
}

# =========================================================================
# 4. Save Header (ac1021100.png) - pac102000.pac
# =========================================================================
$srcPath = Join-Path $baseDir "pac102000_ac1021100.png"
if (Test-Path $srcPath) {
    $src = [System.Drawing.Bitmap]::FromFile($srcPath)
    $bmp = New-Object System.Drawing.Bitmap($src.Width, $src.Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.DrawImage($src, 0, 0)

    Clear-Region $g 0 0 160 60
    Clear-Region $g 20 55 60 30
    Clear-Region $g 98 55 60 30
    Clear-Region $g 20 85 130 30
    $fontTitle = New-Object System.Drawing.Font('Arial Black', 24.0)
    Draw-TextWithOutline $g "SAVE" $fontTitle ([System.Drawing.Color]::FromArgb(180, 230, 255)) ([System.Drawing.Color]::FromArgb(100, 20, 120)) 5.5 80.0 32.0
    $fontLegend = New-Object System.Drawing.Font('Arial Black', 9.5)
    $cGold = [System.Drawing.Color]::FromArgb(255, 250, 190)
    $cBrown = [System.Drawing.Color]::FromArgb(60, 25, 10)
    Draw-TextWithOutline $g "BACK" $fontLegend $cGold $cBrown 3.0 48.0 72.0
    Draw-TextWithOutline $g "OK"   $fontLegend $cGold $cBrown 3.0 120.0 72.0
    Draw-TextWithOutline $g "ICON" $fontLegend $cGold $cBrown 3.0 65.0 98.0

    $dstPath = Join-Path $outDir "ac1021100.png"
    $bmp.Save($dstPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose()
    $bmp.Dispose()
    $src.Dispose()
    Write-Host "Generated: $dstPath"
}

# =========================================================================
# 5. CG Gallery Header (ac8010000.png) - pac801000.pac
# =========================================================================
$srcPath = Join-Path $baseDir "pac801000_ac8010000.png"
if (Test-Path $srcPath) {
    $src = [System.Drawing.Bitmap]::FromFile($srcPath)
    $bmp = New-Object System.Drawing.Bitmap($src.Width, $src.Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.DrawImage($src, 0, 0)

    Clear-Region $g 0 0 200 65
    Clear-Region $g 20 60 60 30
    Clear-Region $g 95 60 90 30
    Clear-Region $g 20 88 135 30
    Clear-Region $g 35 115 50 25
    Clear-Region $g 115 115 65 25

    $fontTitle = New-Object System.Drawing.Font('Arial Black', 18.0)
    Draw-TextWithOutline $g "CG GALLERY" $fontTitle ([System.Drawing.Color]::FromArgb(210, 230, 255)) ([System.Drawing.Color]::FromArgb(60, 30, 120)) 5.0 95.0 32.0

    $fontLegend = New-Object System.Drawing.Font('Arial Black', 9.0)
    $cGold = [System.Drawing.Color]::FromArgb(255, 250, 190)
    $cBrown = [System.Drawing.Color]::FromArgb(60, 25, 10)
    Draw-TextWithOutline $g "BACK"  $fontLegend $cGold $cBrown 3.0 48.0 75.0
    Draw-TextWithOutline $g "VIEW"  $fontLegend $cGold $cBrown 3.0 128.0 75.0
    Draw-TextWithOutline $g "SCENE" $fontLegend $cGold $cBrown 3.0 75.0 102.0
    Draw-TextWithOutline $g "PREV"  $fontLegend $cGold $cBrown 3.0 60.0 127.0
    Draw-TextWithOutline $g "NEXT"  $fontLegend $cGold $cBrown 3.0 142.0 127.0

    $dstPath = Join-Path $outDir "ac8010000.png"
    $bmp.Save($dstPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose()
    $bmp.Dispose()
    $src.Dispose()
    Write-Host "Generated: $dstPath"
}

# =========================================================================
# 6. Music Header (ac8020000.png) - pac802000.pac
# =========================================================================
$srcPath = Join-Path $baseDir "pac802000_ac8020000.png"
if (Test-Path $srcPath) {
    $src = [System.Drawing.Bitmap]::FromFile($srcPath)
    $bmp = New-Object System.Drawing.Bitmap($src.Width, $src.Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.DrawImage($src, 0, 0)

    Clear-Region $g 0 0 230 65
    Clear-Region $g 248 0 70 28
    Clear-Region $g 248 28 120 28

    $fontTitle = New-Object System.Drawing.Font('Arial Black', 22.0)
    Draw-TextWithOutline $g "MUSIC" $fontTitle ([System.Drawing.Color]::FromArgb(210, 230, 255)) ([System.Drawing.Color]::FromArgb(60, 30, 120)) 5.0 110.0 32.0

    $fontLegend = New-Object System.Drawing.Font('Arial Black', 9.5)
    $cGold = [System.Drawing.Color]::FromArgb(255, 250, 190)
    $cBrown = [System.Drawing.Color]::FromArgb(60, 25, 10)
    Draw-TextWithOutline $g "BACK" $fontLegend $cGold $cBrown 3.0 275.0 14.0
    Draw-TextWithOutline $g "PLAY" $fontLegend $cGold $cBrown 3.0 282.0 41.0

    $dstPath = Join-Path $outDir "ac8020000.png"
    $bmp.Save($dstPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose()
    $bmp.Dispose()
    $src.Dispose()
    Write-Host "Generated: $dstPath"
}

# =========================================================================
# 7. Event List Header (ac8030000.png) - pac803000.pac
# =========================================================================
$srcPath = Join-Path $baseDir "pac803000_ac8030000.png"
if (Test-Path $srcPath) {
    $src = [System.Drawing.Bitmap]::FromFile($srcPath)
    $bmp = New-Object System.Drawing.Bitmap($src.Width, $src.Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.DrawImage($src, 0, 0)

    Clear-Region $g 0 0 310 55
    Clear-Region $g 20 55 60 25
    Clear-Region $g 38 78 115 28
    Clear-Region $g 145 78 140 28

    $fontTitle = New-Object System.Drawing.Font('Arial Black', 20.0)
    Draw-TextWithOutline $g "EVENT LIST" $fontTitle ([System.Drawing.Color]::FromArgb(210, 230, 255)) ([System.Drawing.Color]::FromArgb(60, 30, 120)) 5.0 110.0 28.0

    $fontLegend = New-Object System.Drawing.Font('Arial Black', 8.5)
    $cGold = [System.Drawing.Color]::FromArgb(255, 250, 190)
    $cBrown = [System.Drawing.Color]::FromArgb(60, 25, 10)
    Draw-TextWithOutline $g "BACK" $fontLegend $cGold $cBrown 3.0 48.0 66.0
    Draw-TextWithOutline $g "PREV" $fontLegend $cGold $cBrown 3.0 62.0 90.0
    Draw-TextWithOutline $g "NEXT" $fontLegend $cGold $cBrown 3.0 178.0 90.0

    $dstPath = Join-Path $outDir "ac8030000.png"
    $bmp.Save($dstPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose()
    $bmp.Dispose()
    $src.Dispose()
    Write-Host "Generated: $dstPath"
}

# =========================================================================
# 8. Save Confirmation Prompt (ac1050200.png) - pac105000.pac
# =========================================================================
$srcPath = Join-Path $baseDir "pac105000_ac1050200.png"
if (Test-Path $srcPath) {
    $src = [System.Drawing.Bitmap]::FromFile($srcPath)
    $bmp = New-Object System.Drawing.Bitmap($src.Width, $src.Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.DrawImage($src, 0, 0)

    $rectDlg = [System.Drawing.Rectangle]::new(45, 45, 230, 85)
    $cTop = [System.Drawing.Color]::FromArgb(255, 246, 203, 230)
    $cBot = [System.Drawing.Color]::FromArgb(255, 235, 155, 205)
    $gradBrush = New-Object System.Drawing.Drawing2D.LinearGradientBrush($rectDlg, $cTop, $cBot, [System.Drawing.Drawing2D.LinearGradientMode]::Vertical)
    $origMode = $g.CompositingMode
    $g.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceCopy
    $g.FillRectangle($gradBrush, $rectDlg)

    $cPurpPill = [System.Drawing.Color]::FromArgb(255, 128, 40, 240)
    $cPinkPill = [System.Drawing.Color]::FromArgb(255, 235, 100, 130)
    $brushP = New-Object System.Drawing.SolidBrush($cPurpPill)
    $brushPk = New-Object System.Drawing.SolidBrush($cPinkPill)
    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.FillEllipse($brushP, 18, 221, 78, 22)
    $g.FillEllipse($brushP, 125, 221, 78, 22)
    $g.FillEllipse($brushPk, 18, 261, 78, 22)
    $g.FillEllipse($brushPk, 125, 261, 78, 22)
    $g.CompositingMode = $origMode
    $gradBrush.Dispose()
    $brushP.Dispose()
    $brushPk.Dispose()

    $fontDlg = New-Object System.Drawing.Font('Arial Black', 10.5)
    Draw-TextWithOutline $g "Save your progress" $fontDlg ([System.Drawing.Color]::FromArgb(255, 255, 255)) ([System.Drawing.Color]::FromArgb(150, 40, 140)) 3.5 160.0 72.0
    Draw-TextWithOutline $g "here, chu~?" $fontDlg ([System.Drawing.Color]::FromArgb(255, 255, 255)) ([System.Drawing.Color]::FromArgb(150, 40, 140)) 3.5 160.0 96.0

    $fontBtn = New-Object System.Drawing.Font('Arial Black', 10.0)
    Draw-TextWithOutline $g "YES" $fontBtn ([System.Drawing.Color]::FromArgb(255, 255, 255)) ([System.Drawing.Color]::FromArgb(50, 10, 60)) 3.0 57.0 232.0
    Draw-TextWithOutline $g "NO"  $fontBtn ([System.Drawing.Color]::FromArgb(255, 255, 255)) ([System.Drawing.Color]::FromArgb(50, 10, 60)) 3.0 164.0 232.0
    Draw-TextWithOutline $g "YES" $fontBtn ([System.Drawing.Color]::FromArgb(255, 255, 255)) ([System.Drawing.Color]::FromArgb(80, 10, 30)) 3.0 57.0 272.0
    Draw-TextWithOutline $g "NO"  $fontBtn ([System.Drawing.Color]::FromArgb(255, 255, 255)) ([System.Drawing.Color]::FromArgb(80, 10, 30)) 3.0 164.0 272.0

    $dstPath = Join-Path $outDir "ac1050200.png"
    $bmp.Save($dstPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose()
    $bmp.Dispose()
    $src.Dispose()
    Write-Host "Generated: $dstPath"
}
