from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path


def _fmt_bytes(n: int) -> str:
    if n == 0:
        return "—"
    mb = n / (1024 * 1024)
    return f"{n // 1024} KB" if mb < 1 else f"{mb:.0f} MB"


class PluginFormat(str, Enum):
    AU   = "AU"
    VST3 = "VST3"
    VST2 = "VST2"


class UsageStatus(str, Enum):
    USED     = "Used"
    UNUSED   = "Unused"
    SCANNING = "Scanning"


@dataclass
class PluginRecord:
    bundle_path:  Path
    bundle_name:  str           # e.g. "FabFilter Pro-L 2.component"
    format:       PluginFormat
    display_name: str           # e.g. "Pro-L 2"
    vendor:       str           # e.g. "FabFilter"
    version:      str
    bundle_id:    str
    size_bytes:   int = 0

    # AU-specific
    au_cache_key:    str = ""   # "FabFilter: Pro-L 2"  (Reaper/AU cache Vendor:Name)
    au_type:         str = ""   # 4cc e.g. "aumf"
    au_subtype:      str = ""   # 4cc e.g. "FL2p"
    au_manufacturer: str = ""   # 4cc e.g. "FabF"

    # VST3-specific
    vst3_guid: str = ""         # "{XXXXXXXX-XXXX-XXXX-XXXX-XXXXXXXXXXXX}"

    status:       UsageStatus = UsageStatus.SCANNING
    session_refs: list[str] = field(default_factory=list)

    # Normalized key for grouping AU+VST3 twins of the same plugin
    family_key:   str = ""

    is_quarantined: bool = False

    def size_mb(self) -> str:
        return _fmt_bytes(self.size_bytes)


@dataclass
class QuarantineEntry:
    bundle_name:     str
    format:          str
    original_path:   str
    quarantine_path: str
    quarantined_at:  str    # ISO-8601
    display_name:    str
    vendor:          str
    version:         str
    was_status:      str
    size_bytes:      int = 0

    def size_mb(self) -> str:
        return _fmt_bytes(self.size_bytes)
