"""Aggregation for dashboard charts — pure read of history/meetings."""

from collections import Counter
from datetime import datetime, timedelta, timezone


def _parse_ts(ts):
    """Parse ISO-like ts from history/meeting rows. Returns date string YYYY-MM-DD or None."""
    if not isinstance(ts, str) or not ts:
        return None
    # Try common formats: "2026-08-29 14:30:00", "2026-08-29T14:30:00", "2026-08-29"
    for fmt in ("%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M:%S", "%Y-%m-%d"):
        try:
            dt = datetime.strptime(ts[:19] if len(ts) >= 19 else ts[:10], fmt)
            return dt.date().isoformat()
        except (ValueError, TypeError):
            continue
    try:
        # fallback: first 10 chars as date
        d = ts[:10]
        datetime.strptime(d, "%Y-%m-%d")
        return d
    except Exception:
        return None


def history_stats(limit=200):
    try:
        import config
        rows = config.read_history(limit)
    except Exception:
        rows = []
    total = len(rows)
    # last 7 days: count rows whose ts date within last 7 days (if ts parseable)
    today = datetime.now().date()
    last_7d = 0
    by_provider = Counter()
    durations = []
    success = 0
    for r in rows:
        ts = _parse_ts(r.get("ts", ""))
        if ts:
            try:
                d = datetime.strptime(ts, "%Y-%m-%d").date()
                if (today - d).days < 7 and (today - d).days >= 0:
                    last_7d += 1
            except Exception:
                pass
        prov = (r.get("provider") or r.get("transcribe_provider") or "unknown").strip() or "unknown"
        # normalize empty
        if not prov:
            prov = "unknown"
        by_provider[prov] += 1
        try:
            dur = float(r.get("duration", 0) or 0)
            if dur > 0:
                durations.append(dur)
        except Exception:
            pass
        # success: presence of text
        if (r.get("text") or "").strip():
            success += 1
    avg_duration = sum(durations) / len(durations) if durations else 0
    success_rate = (success / total * 100) if total else 0
    return {
        "total": total,
        "last_7d": last_7d,
        "by_provider": dict(by_provider),
        "avg_duration": avg_duration,
        "success_rate": success_rate,
    }


def meetings_stats():
    try:
        import config
        rows = config.read_meetings()
    except Exception:
        rows = []
    total = len(rows)
    by_status = Counter()
    total_duration = 0
    last_30d = 0
    today = datetime.now().date()
    for r in rows:
        by_status[r.get("status", "unknown") or "unknown"] += 1
        try:
            total_duration += float(r.get("duration", 0) or 0)
        except Exception:
            pass
        ts = _parse_ts(r.get("ts", ""))
        if ts:
            try:
                d = datetime.strptime(ts, "%Y-%m-%d").date()
                if (today - d).days < 30 and (today - d).days >= 0:
                    last_30d += 1
            except Exception:
                pass
    return {
        "total": total,
        "by_status": dict(by_status),
        "total_duration": total_duration,
        "last_30d": last_30d,
    }


def daily_counts(days=14):
    try:
        import config
        rows = config.read_history(limit=500)
    except Exception:
        rows = []
    today = datetime.now().date()
    wanted = [(today - timedelta(days=i)).isoformat() for i in range(days - 1, -1, -1)]
    counter = Counter()
    for r in rows:
        d = _parse_ts(r.get("ts", ""))
        if d:
            counter[d] += 1
    return [(d, counter.get(d, 0)) for d in wanted]


def provider_usage():
    try:
        import config
        rows = config.read_history(limit=500)
    except Exception:
        rows = []
    c = Counter()
    for r in rows:
        prov = (r.get("provider") or r.get("transcribe_provider") or r.get("mode") or "unknown").strip()
        if not prov:
            prov = "unknown"
        c[prov] += 1
    return dict(c)
