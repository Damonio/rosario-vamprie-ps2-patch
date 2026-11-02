Add-Type -AssemblyName System.Drawing

$outDir = Join-Path $PSScriptRoot "..\translations\textures"
if (-not (Test-Path $outDir)) {
    New-Item -ItemType Directory -Path $outDir -Force | Out-Null
}

# ==========================================
# 1. Title Menu Buttons (ac9000000.png)
# ==========================================
$srcPath = Join-Path $PSScriptRoot "..\extracted_textures\ac9000000.png"
if (Test-Path $srcPath) {
    $src = [System.Drawing.Bitmap]::FromFile($srcPath)
    $bmp = New-Object System.Drawing.Bitmap($src.Width, $src.Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.DrawImage($src, 0, 0)

    # Read gradient slices from row 4 (y=265..292) at x=95 (purple) and x=287 (pink)
    $sy4 = 265
    $purpleSlice = @()
    $pinkSlice = @()
    for ($i = 0; $i -le 27; $i++) {
        $purpleSlice += $src.GetPixel(95, $sy4 + $i)
        $pinkSlice += $src.GetPixel(287, $sy4 + $i)
    }

    # Erase Japanese text on all 7 ribbons using original gradient
    for ($row = 0; $row -lt 7; $row++) {
        $sy = 9 + $row * 64
        for ($i = 0; $i -le 27; $i++) {
            $cPurp = $purpleSlice[$i]
            $cPink = $pinkSlice[$i]
            for ($x = 38; $x -le 154; $x++) {
                $bmp.SetPixel($x, $sy + $i, $cPurp)
            }
            for ($x = 230; $x -le 346; $x++) {
                $bmp.SetPixel($x, $sy + $i, $cPink)
            }
        }
    }

    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAlias

    $labels = @('New Game', 'Continue', 'Options', 'Gallery', 'Memories', 'Music', 'Events')
    $font = New-Object System.Drawing.Font('Arial Black', 11.0)
    $sf = New-Object System.Drawing.StringFormat
    $sf.Alignment = [System.Drawing.StringAlignment]::Center
    $sf.LineAlignment = [System.Drawing.StringAlignment]::Center

    $fillBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 255, 190))
    $strokePen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(40, 15, 5), 3.0)
    $strokePen.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round

    for ($row = 0; $row -lt 7; $row++) {
        $sy = 9 + $row * 64
        $cy = $sy + 14.0
        $text = $labels[$row]

        # Col 1: Purple (Center x = 96)
        $path1 = New-Object System.Drawing.Drawing2D.GraphicsPath
        $path1.AddString($text, $font.FontFamily, [int]$font.Style, 11.0, [System.Drawing.PointF]::new(96.0, $cy), $sf)
        $g.DrawPath($strokePen, $path1)
        $g.FillPath($fillBrush, $path1)

        # Col 2: Pink (Center x = 288)
        $path2 = New-Object System.Drawing.Drawing2D.GraphicsPath
        $path2.AddString($text, $font.FontFamily, [int]$font.Style, 11.0, [System.Drawing.PointF]::new(288.0, $cy), $sf)
        $g.DrawPath($strokePen, $path2)
        $g.FillPath($fillBrush, $path2)
    }

    $dstPath = Join-Path $outDir "ac9000000.png"
    $bmp.Save($dstPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose()
    $bmp.Dispose()
    $src.Dispose()
    Write-Host "Created $dstPath"
}

# ==========================================
# 2. In-Game HUD Skip / Auto (ac1009910.png)
# ==========================================
$srcPath = Join-Path $PSScriptRoot "..\extracted_textures\ac1009910.png"
if (Test-Path $srcPath) {
    $src = [System.Drawing.Bitmap]::FromFile($srcPath)
    $bmp = New-Object System.Drawing.Bitmap($src.Width, $src.Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.DrawImage($src, 0, 0)

    $clearBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(0, 0, 0, 0))
    $g.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceCopy
    # Clear text regions on left side
    $g.FillRectangle($clearBrush, [System.Drawing.Rectangle]::new(0, 0, 162, 192))
    $g.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceOver

    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAlias

    $font = New-Object System.Drawing.Font('Arial Black', 11.5)
    $sf = New-Object System.Drawing.StringFormat
    $sf.Alignment = [System.Drawing.StringAlignment]::Center
    $sf.LineAlignment = [System.Drawing.StringAlignment]::Center

    $whiteBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 255, 255))
    $dimBrush   = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(220, 220, 220))
    $darkPen    = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(55, 20, 10), 3.0)
    $darkPen.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round

    # Band 0 & 1 (Normal Skip & Auto)
    # Skip: center y = 16.0, x = 60
    $p = New-Object System.Drawing.Drawing2D.GraphicsPath
    $p.AddString("SKIP", $font.FontFamily, [int]$font.Style, 12.0, [System.Drawing.PointF]::new(60.0, 16.0), $sf)
    $g.DrawPath($darkPen, $p)
    $g.FillPath($whiteBrush, $p)

    # Auto: center y = 48.5, x = 60
    $p = New-Object System.Drawing.Drawing2D.GraphicsPath
    $p.AddString("AUTO", $font.FontFamily, [int]$font.Style, 12.0, [System.Drawing.PointF]::new(60.0, 48.5), $sf)
    $g.DrawPath($darkPen, $p)
    $g.FillPath($whiteBrush, $p)

    # Band 2 & 3 (Variant 2)
    $p = New-Object System.Drawing.Drawing2D.GraphicsPath
    $p.AddString("SKIP", $font.FontFamily, [int]$font.Style, 12.0, [System.Drawing.PointF]::new(60.0, 80.0), $sf)
    $g.DrawPath($darkPen, $p)
    $g.FillPath($whiteBrush, $p)

    $p = New-Object System.Drawing.Drawing2D.GraphicsPath
    $p.AddString("AUTO", $font.FontFamily, [int]$font.Style, 12.0, [System.Drawing.PointF]::new(60.0, 112.5), $sf)
    $g.DrawPath($darkPen, $p)
    $g.FillPath($whiteBrush, $p)

    # Band 4 & 5 (Dimmed Variant 3)
    $p = New-Object System.Drawing.Drawing2D.GraphicsPath
    $p.AddString("SKIP", $font.FontFamily, [int]$font.Style, 12.0, [System.Drawing.PointF]::new(60.0, 144.0), $sf)
    $g.DrawPath($darkPen, $p)
    $g.FillPath($dimBrush, $p)

    $p = New-Object System.Drawing.Drawing2D.GraphicsPath
    $p.AddString("AUTO", $font.FontFamily, [int]$font.Style, 12.0, [System.Drawing.PointF]::new(60.0, 176.5), $sf)
    $g.DrawPath($darkPen, $p)
    $g.FillPath($dimBrush, $p)

    $dstPath = Join-Path $outDir "ac1009910.png"
    $bmp.Save($dstPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose()
    $bmp.Dispose()
    $src.Dispose()
    Write-Host "Created $dstPath"
}

# ==========================================
# 3. Title Start Prompt (ic900006.png)
# ==========================================
$srcPath = Join-Path $PSScriptRoot "..\extracted_textures\ic900006.png"
if (Test-Path $srcPath) {
    $src = [System.Drawing.Bitmap]::FromFile($srcPath)
    $bmp = New-Object System.Drawing.Bitmap($src.Width, $src.Height, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g = [System.Drawing.Graphics]::FromImage($bmp)
    $g.DrawImage($src, 0, 0)

    # Clear old Japanese text area x: 30..450, keep heart on the right
    $clearBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(0, 0, 0, 0))
    $g.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceCopy
    $g.FillRectangle($clearBrush, [System.Drawing.Rectangle]::new(25, 0, 442, 64))
    $g.CompositingMode = [System.Drawing.Drawing2D.CompositingMode]::SourceOver

    # Draw soft yellow/pink oval glow behind text
    $glowPath = New-Object System.Drawing.Drawing2D.GraphicsPath
    $glowPath.AddEllipse(35, 8, 410, 48)
    $glowBrush = New-Object System.Drawing.Drawing2D.PathGradientBrush($glowPath)
    $glowBrush.CenterColor = [System.Drawing.Color]::FromArgb(180, 255, 255, 210)
    $glowBrush.SurroundColors = @([System.Drawing.Color]::FromArgb(0, 255, 230, 240))
    $g.FillPath($glowBrush, $glowPath)

    $g.SmoothingMode = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAlias

    $font = New-Object System.Drawing.Font('Arial Black', 16.0)
    $sf = New-Object System.Drawing.StringFormat
    $sf.Alignment = [System.Drawing.StringAlignment]::Center
    $sf.LineAlignment = [System.Drawing.StringAlignment]::Center

    $textBrush = New-Object System.Drawing.SolidBrush([System.Drawing.Color]::FromArgb(255, 255, 170))
    $purplePen = New-Object System.Drawing.Pen([System.Drawing.Color]::FromArgb(120, 40, 180), 4.5)
    $purplePen.LineJoin = [System.Drawing.Drawing2D.LineJoin]::Round

    $p = New-Object System.Drawing.Drawing2D.GraphicsPath
    $p.AddString("PRESS START BUTTON", $font.FontFamily, [int]$font.Style, 16.0, [System.Drawing.PointF]::new(245.0, 32.0), $sf)
    $g.DrawPath($purplePen, $p)
    $g.FillPath($textBrush, $p)

    $dstPath = Join-Path $outDir "ic900006.png"
    $bmp.Save($dstPath, [System.Drawing.Imaging.ImageFormat]::Png)
    $g.Dispose()
    $bmp.Dispose()
    $src.Dispose()
    Write-Host "Created $dstPath"
}
