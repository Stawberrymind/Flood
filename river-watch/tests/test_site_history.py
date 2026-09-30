"""The public charts must retain observation dates, revisions and unknowns."""
import json

from river_watch.site_history import recent_readings


def record(tmp_path, name, *, issue='2026-09-29', observed='29-09-2026', clock='06:00',
           generated='2026-09-29T09:00:00Z', level=1639.32):
    payload = {'issue_date': issue, 'generated_utc': generated, 'bulletin': {
        'as_on_date': observed, 'as_on_time': clock, 'bhakra_level_ft': level,
        'bhakra_inflow_cusecs': 19364, 'bhakra_outflow_cusecs': 26688,
    }}
    (tmp_path / name).write_text(json.dumps(payload), encoding='utf-8')
    return payload


def test_observation_date_not_issue_date_and_latest_not_counted_twice(tmp_path):
    latest = record(tmp_path, '2026-09-29.json', observed='28-09-2026')
    (tmp_path / 'latest.json').write_text(json.dumps(latest), encoding='utf-8')
    result = recent_readings(tmp_path, latest)
    assert len(result['readings']) == 1
    row = result['readings'][0]
    assert row['date'] == '2026-09-28'
    assert row['dams']['Bhakra']['inflow_cusecs'] == 19364
    assert row['dams']['Pong']['level_ft'] is None


def test_rerun_correction_is_used_without_rewriting_original(tmp_path):
    latest = record(tmp_path, '2026-09-29.json')
    original = (tmp_path / '2026-09-29.json').read_bytes()
    record(tmp_path, '2026-09-29_rerun_20260929T110000.json',
           generated='2026-09-29T11:00:00Z', level=None)
    rows = recent_readings(tmp_path, latest)['readings']
    assert len(rows) == 1
    assert rows[0]['dams']['Bhakra']['level_ft'] is None
    assert 'rerun' in rows[0]['record']
    assert (tmp_path / '2026-09-29.json').read_bytes() == original


def test_bad_values_do_not_become_measurements(tmp_path):
    for level in [True, '1639.32', -1, float('inf')]:
        latest = record(tmp_path, '2026-09-29.json', level=level)
        assert recent_readings(tmp_path, latest)['readings'][0]['dams']['Bhakra']['level_ft'] is None


def test_invalid_future_and_out_of_window_bulletins_are_excluded(tmp_path):
    latest = record(tmp_path, '2026-09-29.json')
    record(tmp_path, '2026-09-28.json', issue='2026-09-28', observed='29-09-2026')
    record(tmp_path, '2026-09-27.json', issue='2026-09-27', observed='31-09-2026')
    record(tmp_path, '2026-08-01.json', issue='2026-08-01', observed='01-08-2026')
    record(tmp_path, '2026-09-26.json', issue='2026-09-26', observed='26-09-2026', clock='26:00')
    record(tmp_path, '2026-09-24.json', issue='2026-09-24', observed='24-09-2026', clock='18:00',
           generated='2026-09-24T09:00:00Z')
    (tmp_path / '2026-09-25.json').write_text('broken', encoding='utf-8')
    rows = recent_readings(tmp_path, latest)['readings']
    assert [r['date'] for r in rows] == ['2026-09-29']


def test_most_recent_reading_time_wins_over_a_later_run_of_an_older_bulletin(tmp_path):
    latest = record(tmp_path, '2026-09-29.json', clock='18:00', level=1640,
                    generated='2026-09-29T13:00:00Z')
    record(tmp_path, '2026-09-29_rerun_20260929T120000.json', clock='06:00',
           generated='2026-09-29T14:00:00Z', level=1639)
    row = recent_readings(tmp_path, latest)['readings'][0]
    assert row['time'] == '18:00'
    assert row['dams']['Bhakra']['level_ft'] == 1640
