"""Save aggregate counts only; never persist complaint records or narratives."""
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone, timedelta
from pathlib import Path
import hashlib
import json
import time
import requests

ROOT = Path(__file__).resolve().parents[1]
API = 'https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/'

def month_bounds():
    for year in range(2018, 2027):
        for month in range(1, 13):
            if (year, month) > (2026, 6):
                return
            following = (year + 1, 1) if month == 12 else (year, month + 1)
            yield f'{year}-{month:02d}-01', f'{following[0]}-{following[1]:02d}-01'

def retrieve(bounds):
    start, end = bounds
    path = ROOT / 'data' / 'monthly-aggregates' / f'{start[:7]}.json'
    if path.exists():
        return start, 'cached'
    # A same-day probe returned nonzero counts: the live API uses an inclusive
    # maximum despite its documentation describing an exclusive upper bound.
    last_day = (datetime.fromisoformat(end)-timedelta(days=1)).date().isoformat()
    parameters = {'size': 1, 'no_aggs': 'false', 'date_received_min': start,
                  'date_received_max': last_day}
    for attempt in range(2):
        try:
            response = requests.get(API, params=parameters, timeout=60)
            response.raise_for_status()
            raw = response.json()
            assert not raw['timed_out']
            assert raw['_shards']['failed'] == 0
            total = raw['hits']['total']
            assert total['relation'] == 'eq'
            products = raw['aggregations']['product']['product']
            assert products['doc_count_error_upper_bound'] == 0
            assert products['sum_other_doc_count'] == 0
            counts = {b['key']: b['doc_count'] for b in products['buckets']}
            assert sum(counts.values()) == total['value']
            payload = {'source_url': response.url, 'retrieved_utc': datetime.now(timezone.utc).isoformat(),
                       'period_start_inclusive': start, 'period_end_exclusive': end,
                       'api_maximum_inclusive': last_day,
                       'total_complaints': total['value'], 'product_counts': counts,
                       'aggregation_error_bound': 0, 'omitted_bucket_count': 0}
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(payload, indent=2), encoding='utf-8')
            return start, 'retrieved'
        except Exception:
            if attempt == 1:
                raise
            time.sleep(2)

if __name__ == '__main__':
    completed = []
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(retrieve, bounds) for bounds in month_bounds()]
        for future in as_completed(futures):
            completed.append(future.result())
            if len(completed) % 12 == 0:
                print(f'{len(completed)}/102 monthly aggregate snapshots available', flush=True)
    manifest = []
    for path in sorted((ROOT / 'data' / 'monthly-aggregates').glob('*.json')):
        manifest.append({'file': path.relative_to(ROOT).as_posix(),
                         'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    (ROOT / 'data' / 'manifest.json').write_text(json.dumps(manifest, indent=2), encoding='utf-8')
    print(f'Completed {len(completed)} months. No complaint-level records saved.', flush=True)
