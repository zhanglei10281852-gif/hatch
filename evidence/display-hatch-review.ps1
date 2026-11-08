param([string]$ReportPath)
$ErrorActionPreference='Stop'
try {
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class HatchReviewConsole {
 [StructLayout(LayoutKind.Sequential)] public struct COORD {public short X; public short Y;}
 [StructLayout(LayoutKind.Sequential,CharSet=CharSet.Unicode)] public struct FONTINFO {
 public uint cbSize; public uint nFont; public COORD dwFontSize; public int FontFamily; public int FontWeight;
 [MarshalAs(UnmanagedType.ByValTStr,SizeConst=32)] public string FaceName; }
 [DllImport("kernel32.dll",CharSet=CharSet.Unicode,SetLastError=true)] public static extern IntPtr CreateFile(string n,uint access,uint share,IntPtr security,uint creation,uint flags,IntPtr template);
 [DllImport("kernel32.dll")] public static extern IntPtr GetStdHandle(int n);
 [DllImport("kernel32.dll")] public static extern bool GetCurrentConsoleFontEx(IntPtr h,bool max,ref FONTINFO f);
 [DllImport("kernel32.dll",SetLastError=true)] public static extern bool SetCurrentConsoleFontEx(IntPtr h,bool max,ref FONTINFO f);
}
'@
$consoleHandle=[HatchReviewConsole]::CreateFile('CONOUT$',3221225472,3,[IntPtr]::Zero,3,0,[IntPtr]::Zero)
$f=New-Object HatchReviewConsole+FONTINFO
$f.cbSize=[Runtime.InteropServices.Marshal]::SizeOf($f)
$coord=New-Object HatchReviewConsole+COORD
$coord.X=10; $coord.Y=20
$f.dwFontSize=$coord
$f.FontFamily=54; $f.FontWeight=400; $f.FaceName='Consolas'
$ok=[HatchReviewConsole]::SetCurrentConsoleFontEx($consoleHandle,$false,[ref]$f)
"handle=$consoleHandle ok=$ok error=$([Runtime.InteropServices.Marshal]::GetLastWin32Error()) size=$($f.cbSize)" | Add-Content F:\swe\work\hatch-delivery-review\font-diagnostic.txt
[void][HatchReviewConsole]::GetCurrentConsoleFontEx($consoleHandle,$false,[ref]$f)
$f | Format-List * | Out-File F:\swe\work\hatch-delivery-review\font-current.txt
$raw=$Host.UI.RawUI
$raw.WindowSize=New-Object Management.Automation.Host.Size(100,30)
$raw.BufferSize=New-Object Management.Automation.Host.Size(240,150)
$raw.WindowSize=New-Object Management.Automation.Host.Size(240,38)
$raw.WindowTitle='SWE-REVIEW-hatch-4d2944d3'
$raw.BackgroundColor='Black';$raw.ForegroundColor='White'
Start-Sleep -Seconds 4
$ok=[HatchReviewConsole]::SetCurrentConsoleFontEx($consoleHandle,$false,[ref]$f)
"handle=$consoleHandle ok=$ok error=$([Runtime.InteropServices.Marshal]::GetLastWin32Error()) size=$($f.cbSize)" | Add-Content F:\swe\work\hatch-delivery-review\font-diagnostic.txt
[void][HatchReviewConsole]::GetCurrentConsoleFontEx($consoleHandle,$false,[ref]$f)
$f | Format-List * | Out-File F:\swe\work\hatch-delivery-review\font-current.txt
$raw.WindowSize=New-Object Management.Automation.Host.Size(100,30)
$raw.BufferSize=New-Object Management.Automation.Host.Size(240,150)
$raw.WindowSize=New-Object Management.Automation.Host.Size(240,38)
$raw | Format-List * | Out-File F:\swe\work\hatch-delivery-review\console-diagnostic.txt
Clear-Host
Get-Content -LiteralPath $ReportPath -Encoding UTF8 | ForEach-Object { if ($_ -match '^Rubric ID：6|^Rubric 6|^命令|^触发|^duplicate-orphan|^metadata-orphan|^制品|^后端|^代码 |^时序|^对照') { Write-Host $_ -ForegroundColor Yellow } else { Write-Host $_ } }
$raw.WindowPosition=New-Object Management.Automation.Host.Coordinates(0,0)
while($true){Start-Sleep -Seconds 60}

} catch { $_ | Out-String | Set-Content F:\swe\work\hatch-delivery-review\console-error.txt; while($true){Start-Sleep -Seconds 60} }



