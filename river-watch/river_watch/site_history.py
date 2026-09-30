"""Compact, dated BBMB readings for the public reservoir graphs.

This is a view of published records, not another forecast or a replacement
for the prospective archive. Reading dates come from the bulletin itself.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
import json
import math
from pathlib import Path
import re


def _number(value):
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return value if math.isfinite(value) and value >= 0 else None


def recent_readings(out_dir: Path, product: dict, days: int = 30) -> dict:
    """Choose the latest published bulletin per observation day within the window.

    Reruns may correct a reading, but never turn a missing value into zero.
    Invalid/future bulletins are excluded. The front end inserts missing days.
    """
    issue = date.fromisoformat(str(product['issue_date']))
    first = issue - timedelta(days=days - 1)
    selected = {}
    for path in sorted(out_dir.glob('*.json')):
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}(?:_rerun_[\w]+)?\.json', path.name):
            continue
        try:
            record = json.loads(path.read_text(encoding='utf-8'))
            record_issue = date.fromisoformat(record['issue_date'])
            bulletin = record['bulletin']
            observed = datetime.strptime(bulletin['as_on_date'], '%d-%m-%Y').date()
            clock = str(bulletin['as_on_time'])
            if not re.fullmatch(r'(?:[01]\d|2[0-3]):[0-5]\d', clock):
                continue
            generated = datetime.fromisoformat(record['generated_utc'].replace('Z', '+00:00'))
            if generated.tzinfo is None:
                continue
            observed_at = datetime.fromisoformat(f'{observed.isoformat()}T{clock}:00+05:30')
            if observed_at > generated:
                continue
            if not first <= observed <= record_issue <= issue:
                continue
        except (KeyError, TypeError, ValueError, OSError):
            continue
        priority = (clock, generated.astimezone(timezone.utc), path.name)
        if observed in selected and priority <= selected[observed][0]:
            continue
        dams = {}
        for name, prefix in [('Bhakra', 'bhakra'), ('Pong', 'pong')]:
            dams[name] = {
                field: _number(bulletin.get(f'{prefix}_{field}'))
                for field in ('level_ft', 'inflow_cusecs', 'outflow_cusecs')
            }
        selected[observed] = (priority, {
            'date': observed.isoformat(), 'time': clock,
            'record': path.name, 'dams': dams,
        })
    return {
        'version': 1, 'window_days': days, 'source': 'BBMB reservoir bulletins',
        'start': first.isoformat(), 'end': issue.isoformat(),
        'readings': [selected[d][1] for d in sorted(selected)],
    }
