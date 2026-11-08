$ErrorActionPreference='Stop'
Add-Type -AssemblyName System.Drawing
Add-Type -AssemblyName System.Windows.Forms
Add-Type @'
using System;
using System.Runtime.InteropServices;
public static class HatchReviewCapture {
 public delegate bool WindowCallback(IntPtr h,IntPtr l);
 [DllImport("user32.dll")] public static extern bool EnumWindows(WindowCallback cb,IntPtr l);
 [DllImport("user32.dll")] public static extern bool IsWindowVisible(IntPtr h);
 [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr h,out uint id);
 [DllImport("user32.dll",CharSet=CharSet.Unicode)] public static extern int GetClassName(IntPtr h,System.Text.StringBuilder b,int n);
 [DllImport("user32.dll")] public static extern IntPtr WindowFromPoint(POINT p);
 [DllImport("user32.dll")] public static extern IntPtr GetAncestor(IntPtr h,uint flags);
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr h,int n);
 public static System.Collections.Generic.List<IntPtr> HideIme() {
  var hidden=new System.Collections.Generic.List<IntPtr>();
  EnumWindows((h,l)=>{if(IsWindowVisible(h)) { uint id; GetWindowThreadProcessId(h,out id);
   var cls=new System.Text.StringBuilder(256);GetClassName(h,cls,256);
   var name=System.Diagnostics.Process.GetProcessById((int)id).ProcessName;
   if(name.IndexOf("docker",StringComparison.OrdinalIgnoreCase)>=0 || name.IndexOf("sogou",StringComparison.OrdinalIgnoreCase)>=0 || cls.ToString().IndexOf("sogou",StringComparison.OrdinalIgnoreCase)>=0 || cls.ToString().StartsWith("SoPY_")) {ShowWindow(h,0);hidden.Add(h);}
  }return true;},IntPtr.Zero);return hidden;
 }

 [StructLayout(LayoutKind.Sequential)] public struct RECT { public int Left,Top,Right,Bottom; }
 [StructLayout(LayoutKind.Sequential)] public struct POINT {public int X,Y;}
 [DllImport("user32.dll")] public static extern bool GetClientRect(IntPtr h,out RECT r);
 [DllImport("user32.dll")] public static extern bool ClientToScreen(IntPtr h,ref POINT p);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr h);
 [DllImport("user32.dll")] public static extern bool MoveWindow(IntPtr h,int x,int y,int w,int height,bool repaint);
}
'@
$report='F:\swe\099928\project-02\evidence\rubric-comparison.txt'
$output='F:\swe\099928\project-02\evidence\screenshots\01-rubric-comparison.png'
$hostProcess=Start-Process -FilePath "$env:SystemRoot\System32\conhost.exe" -ArgumentList @('powershell.exe','-NoProfile','-ExecutionPolicy','Bypass','-File','F:\swe\work\hatch-delivery-review\display-hatch-review.ps1','-ReportPath',$report) -PassThru
$process=$null
try {
 $deadline=[DateTime]::UtcNow.AddSeconds(12)
 do {
  Start-Sleep -Milliseconds 250
  $process=Get-Process -Name powershell -ErrorAction SilentlyContinue | Where-Object {$_.MainWindowTitle -eq 'SWE-REVIEW-hatch-4d2944d3'} | Select-Object -First 1
 } while($null -eq $process -and [DateTime]::UtcNow -lt $deadline)
 if($null -eq $process){throw 'Dedicated report terminal has no window handle.'}
 $h=$process.MainWindowHandle
 [void][HatchReviewCapture]::MoveWindow($h,40,40,2440,810,$true)
 [void][HatchReviewCapture]::SetForegroundWindow($h)
 Start-Sleep -Seconds 7
 [System.Windows.Forms.SendKeys]::SendWait('{ESC}')
 [System.Windows.Forms.SendKeys]::SendWait('^ ') 
 Start-Sleep -Milliseconds 600
 $hiddenIme=@([HatchReviewCapture]::HideIme())
 $overlayPoint=New-Object HatchReviewCapture+POINT
 $overlayPoint.X=2110; $overlayPoint.Y=90
 $overlay=[HatchReviewCapture]::WindowFromPoint($overlayPoint)
 $overlayRoot=[HatchReviewCapture]::GetAncestor($overlay,2)
 $overlayClass=New-Object Text.StringBuilder 256
 [void][HatchReviewCapture]::GetClassName($overlayRoot,$overlayClass,256)
 $overlayOwner=0
 [void][HatchReviewCapture]::GetWindowThreadProcessId($overlayRoot,[ref]$overlayOwner)
 Write-Output "Overlay: $overlayRoot $overlayClass $((Get-Process -Id $overlayOwner).ProcessName)"
 if($overlayRoot -ne $h -and $overlayClass.ToString() -match 'Sogou|SoGou|SoPY_|IME|SG'){
  [void][HatchReviewCapture]::ShowWindow($overlayRoot,0)
  $hiddenIme += $overlayRoot
 }
 Start-Sleep -Milliseconds 500
 $r=New-Object HatchReviewCapture+RECT
 $p=New-Object HatchReviewCapture+POINT
 if(-not [HatchReviewCapture]::GetClientRect($h,[ref]$r)){throw 'GetClientRect failed'}
 if(-not [HatchReviewCapture]::ClientToScreen($h,[ref]$p)){throw 'ClientToScreen failed'}
 $w=$r.Right-$r.Left; $height=$r.Bottom-$r.Top
 if($w -lt 2000 -or $height -lt 700){throw "Unexpected client bounds $w x $height"}
 $bitmap=New-Object System.Drawing.Bitmap($w,$height)
 $graphics=[System.Drawing.Graphics]::FromImage($bitmap)
 try {
  $graphics.CopyFromScreen($p.X,$p.Y,0,0,$bitmap.Size)
  $bitmap.Save($output,[System.Drawing.Imaging.ImageFormat]::Png)
 }finally{$graphics.Dispose();$bitmap.Dispose()}
 Write-Output ("Hidden IME windows: " + $hiddenIme.Count)
 Write-Output "CAPTURED $output ${w}x${height}"
}finally{
 if($null -ne $hiddenIme){foreach($imeWindow in $hiddenIme){[void][HatchReviewCapture]::ShowWindow($imeWindow,4)}}
 if($null -ne $process -and -not $process.HasExited){Stop-Process -Id $process.Id -Force}
 if(-not $hostProcess.HasExited){Stop-Process -Id $hostProcess.Id -Force -ErrorAction SilentlyContinue}
}




