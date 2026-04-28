"""
skills/system_info.py — System stats that JARVIS can report
"""
from __future__ import annotations

import platform
import time

import psutil


def get_system_info() -> dict:
    """Return a dictionary of current system stats."""
    cpu_percent = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory()
    disk = psutil.disk_usage("/")

    battery = None
    bat = psutil.sensors_battery()
    if bat:
        battery = {
            "percent": round(bat.percent, 1),
            "plugged": bat.power_plugged,
            "time_left": str(int(bat.secsleft / 60)) + "min" if bat.secsleft != psutil.POWER_TIME_UNLIMITED else "∞",
        }

    return {
        "os": platform.system(),
        "os_version": platform.mac_ver()[0] or platform.version(),
        "cpu_percent": cpu_percent,
        "cpu_cores": psutil.cpu_count(logical=True),
        "ram_used_gb": round(mem.used / 1e9, 2),
        "ram_total_gb": round(mem.total / 1e9, 2),
        "ram_percent": mem.percent,
        "disk_used_gb": round(disk.used / 1e9, 1),
        "disk_total_gb": round(disk.total / 1e9, 1),
        "disk_percent": disk.percent,
        "battery": battery,
    }


def format_system_info(info: dict) -> str:
    """Format system info into a human-readable string for JARVIS to speak."""
    lines = [
        f"CPU: {info['cpu_percent']}% ({info['cpu_cores']} cores)",
        f"RAM: {info['ram_used_gb']}GB / {info['ram_total_gb']}GB ({info['ram_percent']}%)",
        f"Disk: {info['disk_used_gb']}GB used of {info['disk_total_gb']}GB ({info['disk_percent']}%)",
    ]
    if info["battery"]:
        b = info["battery"]
        plug = "🔌" if b["plugged"] else "🔋"
        lines.append(f"Battery: {plug} {b['percent']}% ({b['time_left']} remaining)")
    return "\n".join(lines)
