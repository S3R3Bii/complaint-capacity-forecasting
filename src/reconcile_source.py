"""Independently compare disjoint monthly counts with one whole-period query."""
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
import hashlib
import json
import requests

ROOT = Path(__file__).resolve().parents[1]
API = 'https://www.consumerfinance.gov/data-research/consumer-complaints/search/api/v1/'

def query(start, end):
    response = requests.get(API, params={'size': 1, 'no_aggs': 'false',
        'date_received_min': start, 'date_received_max': end}, timeout=90)
    response.raise_for_status()
    raw = response.json()
    assert not raw['timed_out'] and raw['_shards']['failed'] == 0
    assert raw['hits']['total']['relation'] == 'eq'
    group = raw['aggregations']['product']['product']
    assert group['sum_other_doc_count'] == group['doc_count_error_upper_bound'] == 0
    counts = {b['key']: b['doc_count'] for b in group['buckets']}
    assert sum(counts.values()) == raw['hits']['total']['value']
    return response.url, counts

if __name__ == '__main__':
    monthly = Counter()
    manifest = json.loads((ROOT/'data/manifest.json').read_text())
    assert len(manifest) == 102
    for entry in manifest:
        path = ROOT/entry['file']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
        monthly.update(json.loads(path.read_text())['product_counts'])
    url, whole = query('2018-01-01', '2026-06-30')
    probe_url, probe = query('2025-01-01', '2025-01-01')
    differences = {k: monthly[k]-whole.get(k, 0) for k in set(monthly)|set(whole)
                   if monthly[k] != whole.get(k, 0)}
    receipt = {'timestamp_utc': datetime.now(timezone.utc).isoformat(),
        'status': 'PASS' if not differences and sum(probe.values()) > 0 else 'FAIL',
        'monthly_total': sum(monthly.values()), 'whole_period_total': sum(whole.values()),
        'product_count': len(whole), 'differences': differences,
        'whole_period_source': url, 'same_day_probe_source': probe_url,
        'same_day_probe_total': sum(probe.values()),
        'conclusion': 'Live API maximum is inclusive; disjoint calendar-month queries use the final day.',
        'manifest_sha256': hashlib.sha256((ROOT/'data/manifest.json').read_bytes()).hexdigest()}
    (ROOT/'results/source_reconciliation.json').write_text(json.dumps(receipt, indent=2))
    print(json.dumps(receipt, indent=2))
    assert receipt['status'] == 'PASS', 'Monthly source reconciliation failed.'
