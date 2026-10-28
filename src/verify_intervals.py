"""Check paired block intervals through block means, not concatenated row indices."""
from collections import defaultdict
from pathlib import Path
import csv
import json
import math
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
checks = []
for delay in [2, 3]:
    summary = json.loads((ROOT/f'results/lag{delay}_summary.json').read_text())
    with (ROOT/f'results/lag{delay}_capacity_policies.csv').open(newline='') as stream:
        rows = list(csv.DictReader(stream))
    for comparison in summary['capacity_comparisons']:
        monthly = defaultdict(list)
        for row in rows:
            if int(row['cost_ratio']) == comparison['cost_ratio']:
                monthly[(row['month'], row['model'])].append(float(row['normalized_cost']))
        months = sorted({key[0] for key in monthly})
        assert len(months) == 24
        differences = []
        for month in months:
            left = monthly[(month, comparison['ml_model'])]
            right = monthly[(month, comparison['baseline'])]
            assert len(left) == len(right) == 6
            differences.append(math.fsum(left)/6 - math.fsum(right)/6)
        block_means = np.array([math.fsum(differences[(start+j)%24] for j in range(6))/6
                                for start in range(24)])
        starts = np.random.default_rng(20261028).integers(0, 24, size=(2000, 4))
        result = np.quantile(block_means[starts].mean(axis=1), [.025, .975])
        np.testing.assert_allclose(result, comparison['block_resampling_interval_95'], rtol=1e-10, atol=1e-9)
        checks.append({'delay': delay, 'cost_ratio': comparison['cost_ratio'],
                       'status': 'PASS', 'interval': result.tolist()})
(ROOT/'results/interval_verification.json').write_text(json.dumps(checks, indent=2))
print('PASS: all six paired intervals independently reconstructed from block means.')
