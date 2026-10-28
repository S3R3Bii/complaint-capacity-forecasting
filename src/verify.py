"""Independent arithmetic and lineage checks using stdlib, not analysis helpers."""
from pathlib import Path
from collections import defaultdict
from datetime import datetime, timezone
import csv
import hashlib
import json
import math

ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/'results'

def rows(name):
    with (RESULTS/name).open(newline='',encoding='utf-8') as f:
        return list(csv.DictReader(f))

def close(actual,expected):
    assert math.isclose(actual,expected,rel_tol=1e-10,abs_tol=1e-9),(actual,expected)

def quantile(values,q):
    ordered=sorted(values); position=(len(ordered)-1)*q
    low=math.floor(position); high=math.ceil(position)
    return ordered[low]+(position-low)*(ordered[high]-ordered[low])

def main():
    checks=[]; source_values={}
    manifest=json.loads((ROOT/'data/manifest.json').read_text())
    assert len(manifest)==102
    for item in manifest:
        p=ROOT/item['file']; assert hashlib.sha256(p.read_bytes()).hexdigest()==item['sha256']
        j=json.loads(p.read_text()); assert sum(j['product_counts'].values())==j['total_complaints']
        for product,count in j['product_counts'].items():
            assert isinstance(count,int) and count>=0
            source_values[(j['period_start_inclusive'],product)]=count
    checks.append('All 102 source hashes and exact aggregate totals reconcile')
    for lag in [2,3]:
        summary=json.loads((RESULTS/f'lag{lag}_summary.json').read_text())
        features=rows(f'lag{lag}_features.csv')
        assert len(features)==540
        assert len({(r['month'],r['product']) for r in features})==540
        for r in features:
            close(float(r['complaints']),source_values[(r['month'],r['product'])])
            y,m=map(int,r['month'][:7].split('-'))
            for offset in [lag,lag+1,lag+2,12]:
                month_number=y*12+m-1-offset
                source=f'{month_number//12}-{month_number%12+1:02d}-01'
                assert r[f'source_month_{offset}']==source
                close(float(r[f'lag_{offset}']),source_values[(source,r['product'])])
        cv=rows(f'lag{lag}_validation_predictions.csv')
        by_model=defaultdict(list); residuals=defaultdict(list)
        for r in cv:
            assert '2023-01-01'<=r['month']<'2024-07-01'
            err=float(r['complaints'])-float(r['prediction'])
            by_model[r['model']].append(abs(err)/float(r['scale']))
            residuals[r['model']].append(err/float(r['scale']))
        scores={k:math.fsum(v)/len(v) for k,v in by_model.items()}
        winner=min(scores,key=lambda k:(scores[k],k))
        assert winner==summary['selected_model']
        close(scores[winner],summary['validation_score'])
        test=rows(f'lag{lag}_test_predictions.csv'); error=defaultdict(list)
        for r in test:
            assert '2024-07-01'<=r['month']<='2026-06-01'
            absolute=abs(float(r['complaints'])-float(r['prediction']))/float(r['scale'])
            close(absolute,float(r['normalized_absolute_error']))
            error[r['model']].append(absolute)
        for model,values in error.items():
            assert len(values)==144
            close(math.fsum(values)/len(values),summary['test_normalized_mae'][model])
        costs=defaultdict(list)
        for r in rows(f'lag{lag}_capacity_policies.csv'):
            ratio=int(r['cost_ratio']); q=quantile(residuals[r['model']],ratio/(ratio+1))
            close(q,float(r['residual_quantile']))
            capacity=max(0,float(r['prediction'])+q*float(r['scale']))
            close(capacity,float(r['capacity']))
            under=max(0,float(r['complaints'])-capacity);over=max(0,capacity-float(r['complaints']))
            close(under,float(r['under']));close(over,float(r['over']))
            loss=(ratio*under+over)/float(r['scale'])
            close(loss,float(r['normalized_cost']))
            costs[(ratio,r['model'])].append(loss)
        for comp in summary['capacity_comparisons']:
            for field,model in [('ml_mean_cost',comp['ml_model']),('baseline_mean_cost',comp['baseline'])]:
                vals=costs[(comp['cost_ratio'],model)];close(math.fsum(vals)/len(vals),comp[field])
        checks.append(f'Lag {lag}: all source-feature joins, temporal boundaries, model selection, errors, quantiles and capacity losses independently recomputed')
    receipt={'timestamp_utc':datetime.now(timezone.utc).isoformat(),'status':'PASS within enumerated checks',
      'checks':checks,'limitations':['Final-snapshot data cannot verify historical publication availability.',
         'Resampling intervals are descriptive uncertainty under a chosen six-month block assumption.',
         'No production deployment, actual cost saving or causal effect was tested.']}
    receipt['artifact_sha256']={p.relative_to(ROOT).as_posix():hashlib.sha256(p.read_bytes()).hexdigest()
        for p in sorted(RESULTS.glob('*')) if p.is_file() and p.name!='verification.json'}
    (RESULTS/'verification.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps({'status':receipt['status'],'checks':checks},indent=2))

if __name__=='__main__':main()
