param(
    [string]$Path,
    [string]$Monitor = "primary",   # "primary", or a 0-based monitor index
    [switch]$List                   # list connected monitors as JSON and exit
)

Add-Type -TypeDefinition @"
using System;
using System.Collections.Generic;
using System.Runtime.InteropServices;

[StructLayout(LayoutKind.Sequential)]
public struct WpRect { public int Left, Top, Right, Bottom; }

[ComImport, Guid("B92B56A9-8B55-4E14-9A89-0199BBB6F93B"),
 InterfaceType(ComInterfaceType.InterfaceIsIUnknown)]
public interface IDesktopWallpaper
{
    void SetWallpaper([MarshalAs(UnmanagedType.LPWStr)] string monitorID,
                      [MarshalAs(UnmanagedType.LPWStr)] string wallpaper);
    [return: MarshalAs(UnmanagedType.LPWStr)]
    string GetWallpaper([MarshalAs(UnmanagedType.LPWStr)] string monitorID);
    [return: MarshalAs(UnmanagedType.LPWStr)]
    string GetMonitorDevicePathAt(uint monitorIndex);
    uint GetMonitorDevicePathCount();
    WpRect GetMonitorRECT([MarshalAs(UnmanagedType.LPWStr)] string monitorID);
    void SetBackgroundColor(uint color);
    uint GetBackgroundColor();
    void SetPosition(int position);
    int GetPosition();
    void SetSlideshow(IntPtr items);
    void GetSlideshow(out IntPtr items);
    void SetSlideshowOptions(int options, uint slideshowTick);
    void GetSlideshowOptions(out int options, out uint slideshowTick);
    void AdvanceSlideshow([MarshalAs(UnmanagedType.LPWStr)] string monitorID, int direction);
    void GetStatus(out int state);
    void Enable([MarshalAs(UnmanagedType.Bool)] bool enable);
}

[ComImport, Guid("C2CF3110-460E-4FC1-B9D0-8A1C0C9CC4BD")]
public class DesktopWallpaperClass { }

public static class PerMonitorWallpaper
{
    // connected monitors only: "index|id|width|height|isPrimary" per line
    public static string ListMonitors()
    {
        var dw = (IDesktopWallpaper)new DesktopWallpaperClass();
        uint count = dw.GetMonitorDevicePathCount();
        var lines = new List<string>();
        int idx = 0;
        for (uint i = 0; i < count; i++)
        {
            string id = dw.GetMonitorDevicePathAt(i);
            try
            {
                WpRect r = dw.GetMonitorRECT(id);  // throws for disconnected monitors
                bool primary = (r.Left == 0 && r.Top == 0);
                lines.Add(string.Format("{0}|{1}|{2}|{3}|{4}",
                    idx, id, r.Right - r.Left, r.Bottom - r.Top, primary ? 1 : 0));
                idx++;
            }
            catch { }
        }
        return string.Join("\n", lines);
    }

    public static string Set(string path, string target)
    {
        var dw = (IDesktopWallpaper)new DesktopWallpaperClass();
        string[] lines = ListMonitors().Split('\n');
        string chosen = null;
        foreach (string line in lines)
        {
            string[] f = line.Split('|');
            if (target == "primary" ? f[4] == "1" : f[0] == target) { chosen = f[1]; break; }
        }
        if (chosen == null) throw new Exception("monitor not found: " + target);
        dw.SetWallpaper(chosen, path);
        return chosen;
    }
}
"@

if ($List) {
    [PerMonitorWallpaper]::ListMonitors() -split "`n" | ForEach-Object {
        $f = $_ -split '\|'
        [PSCustomObject]@{ index = [int]$f[0]; id = $f[1]; width = [int]$f[2]; height = [int]$f[3]; primary = ($f[4] -eq '1') }
    } | ConvertTo-Json
    exit 0
}

if (-not $Path) { Write-Error "Provide -Path or -List"; exit 1 }
$id = [PerMonitorWallpaper]::Set((Resolve-Path $Path).Path, $Monitor)
Write-Output "Wallpaper set on monitor: $id"
