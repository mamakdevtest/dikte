"""Aggregation for dashboard charts — pure read of history/meetings."""

import sys
from collections import Counter
from datetime import datetime, timedelta, timezone


def _could_not_read(what, exc):
    """A read that failed is not an empty file, and the dashboard must not say it is.

    Falling back to "no rows" made a history that could not be read look exactly like a
    history with nothing in it: the dashboard showed `0 dictations`, which is a claim
    about the user's data and a false one. So the failure is reported — to the terminal,
    and to the caller through `unreadable` on the result, which is what the cards read
    before they print a number.
    """
    print(f"dikte: could not read the {what} for the dashboard ({exc})", file=sys.stderr)


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
    except Exception as exc:
        _could_not_read("history", exc)
        return {"total": 0, "last_7d": 0, "by_provider": {}, "avg_duration": 0,
                "success_rate": 0, "unreadable": True}
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
            # `_parse_ts` hands back either a date string it has already verified or None,
            # so the defensive handler that used to sit here could never fire. Deleting it
            # is the burn-down: an untestable claim is not a guard (see the `_parse_ts`
            # contract test).
            d = datetime.strptime(ts, "%Y-%m-%d").date()
            if (today - d).days < 7 and (today - d).days >= 0:
                last_7d += 1
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
    except Exception as exc:
        _could_not_read("meetings", exc)
        return {"total": 0, "by_status": {}, "total_duration": 0, "last_30d": 0,
                "unreadable": True}
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
            # Same contract, same deletion: `_parse_ts` verified it before returning it.
            d = datetime.strptime(ts, "%Y-%m-%d").date()
            if (today - d).days < 30 and (today - d).days >= 0:
                last_30d += 1
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
    except Exception as exc:
        # Reported, not flagged: this feeds a bar chart, and an empty chart is the honest
        # drawing of "no bars to draw". The cards above it carry the flag, so the reader
        # is told why the chart is empty.
        _could_not_read("history", exc)
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
    except Exception as exc:
        # Reported, not flagged: the caller wants provider -> count, and `unreadable`
        # would arrive as a provider named "unreadable" with a True count.
        _could_not_read("history", exc)
        rows = []
    c = Counter()
    for r in rows:
        prov = (r.get("provider") or r.get("transcribe_provider") or r.get("mode") or "unknown").strip()
        if not prov:
            prov = "unknown"
        c[prov] += 1
    return dict(c)
