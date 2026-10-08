# --- lepao-research-notice v1 (do not remove; see LICENSE) ---
# 乐跑协议研究（Lepao Research） · https://github.com/dan-cun/lepao3
# Copyright (c) 2026 dan-cun · 技术讨论 QQ 1224145544（仅作技术讨论，不提供代打卡）
# 许可证 LRL-1.0（乐跑研究协议 1.0）：仅供学习 · 不可牟利 · 再发布须署名引用原始仓库 · 声明不得删除
# 删除或篡改本块即依 LRL-1.0 第三条自动终止授权；衍生版须继续以 LRL-1.0 授权并标注修改说明。
# --- end lepao-research-notice ---

"""Read-only Windows utilisation samples. No personal files, network or subprocesses."""
import ctypes
import os
import time
from ctypes import wintypes


class SystemSampler:
    def __init__(self):
        self.started = time.monotonic()
        self.previous = None

    def sample(self):
        result = {"cpu": None, "ram": None, "disk": None,
                  "seconds": int(time.monotonic() - self.started)}
        if os.name != "nt":
            return result
        kernel = ctypes.WinDLL("kernel32", use_last_error=True)
        try:
            idle, system, user = wintypes.FILETIME(), wintypes.FILETIME(), wintypes.FILETIME()
            get_times = kernel.GetSystemTimes
            get_times.argtypes = [ctypes.POINTER(wintypes.FILETIME)] * 3
            get_times.restype = wintypes.BOOL
            if get_times(ctypes.byref(idle), ctypes.byref(system), ctypes.byref(user)):
                values = tuple((item.dwHighDateTime << 32) | item.dwLowDateTime
                               for item in (idle, system, user))
                if self.previous is not None:
                    idle_delta = values[0] - self.previous[0]
                    total_delta = values[1] + values[2] - self.previous[1] - self.previous[2]
                    if total_delta > 0 and idle_delta >= 0:
                        result["cpu"] = max(0, min(100, 100 * (1 - idle_delta / total_delta)))
                self.previous = values
        except (OSError, ValueError, AttributeError):
            self.previous = None
        try:
            class MemoryStatus(ctypes.Structure):
                _fields_ = [("length", wintypes.DWORD), ("load", wintypes.DWORD),
                            *[(name, ctypes.c_ulonglong) for name in (
                                "physical_total", "physical_available", "page_total", "page_available",
                                "virtual_total", "virtual_available", "extended_available")]]
            memory = MemoryStatus()
            memory.length = ctypes.sizeof(memory)
            get_memory = kernel.GlobalMemoryStatusEx
            get_memory.argtypes = [ctypes.POINTER(MemoryStatus)]
            get_memory.restype = wintypes.BOOL
            if get_memory(ctypes.byref(memory)):
                result["ram"] = int(memory.load)
        except (OSError, ValueError, AttributeError):
            pass
        try:
            available, total, free = ctypes.c_ulonglong(), ctypes.c_ulonglong(), ctypes.c_ulonglong()
            get_disk = kernel.GetDiskFreeSpaceExW
            get_disk.argtypes = [wintypes.LPCWSTR, *([ctypes.POINTER(ctypes.c_ulonglong)] * 3)]
            get_disk.restype = wintypes.BOOL
            # Local system volume only; never follow the current directory onto a network share.
            drive = os.environ.get("SystemDrive", "C:")
            if len(drive) != 2 or not drive[0].isascii() or not drive[0].isalpha() or drive[1] != ":":
                drive = "C:"
            volume = drive + "\\"
            if get_disk(volume, ctypes.byref(available), ctypes.byref(total), ctypes.byref(free)) and total.value:
                result["disk"] = max(0, min(100, 100 * (1 - free.value / total.value)))
        except (OSError, ValueError, AttributeError):
            pass
        return result
