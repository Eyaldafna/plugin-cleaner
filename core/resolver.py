from __future__ import annotations
from pathlib import Path

from .models import PluginRecord, UsageStatus
from .session_parser import SessionRef


def resolve(records: list[PluginRecord], refs: list[SessionRef]) -> None:
    """Mark PluginRecord.status based on session refs. Mutates records in place."""

    # Build lookup indices
    au_by_cache_key:     dict[str, list[PluginRecord]] = {}
    au_by_4cc:           dict[str, list[PluginRecord]] = {}
    vst3_by_basename:    dict[str, list[PluginRecord]] = {}
    vst3_by_bundle_path: dict[str, list[PluginRecord]] = {}
    vst2_by_basename:    dict[str, list[PluginRecord]] = {}

    for rec in records:
        from .models import PluginFormat
        if rec.format == PluginFormat.AU:
            key = rec.au_cache_key
            if key:
                au_by_cache_key.setdefault(key, []).append(rec)
            # 4cc key: "type|subtype|manufacturer"
            if rec.au_type or rec.au_subtype or rec.au_manufacturer:
                cc = f"{rec.au_type}|{rec.au_subtype}|{rec.au_manufacturer}"
                au_by_4cc.setdefault(cc, []).append(rec)

        elif rec.format == PluginFormat.VST3:
            vst3_by_basename.setdefault(rec.bundle_name, []).append(rec)
            vst3_by_bundle_path.setdefault(str(rec.bundle_path), []).append(rec)

        elif rec.format == PluginFormat.VST2:
            vst2_by_basename.setdefault(rec.bundle_name, []).append(rec)

    def mark_used(recs: list[PluginRecord], source: str) -> None:
        for r in recs:
            r.status = UsageStatus.USED
            if source not in r.session_refs:
                r.session_refs.append(source)

    # Apply refs
    for ref in refs:
        if ref.kind == "au_cache_key":
            recs = au_by_cache_key.get(ref.key)
            if recs:
                mark_used(recs, ref.source)

        elif ref.kind == "au_4cc":
            recs = au_by_4cc.get(ref.key)
            if recs:
                mark_used(recs, ref.source)

        elif ref.kind == "vst3_basename":
            recs = vst3_by_basename.get(ref.key)
            if recs:
                mark_used(recs, ref.source)

        elif ref.kind == "vst3_bundle_path":
            recs = vst3_by_bundle_path.get(ref.key)
            if recs:
                mark_used(recs, ref.source)

        elif ref.kind == "vst2_basename":
            recs = vst2_by_basename.get(ref.key)
            if recs:
                mark_used(recs, ref.source)

    # Finalize: anything still SCANNING → UNUSED
    for rec in records:
        if rec.status == UsageStatus.SCANNING:
            rec.status = UsageStatus.UNUSED
