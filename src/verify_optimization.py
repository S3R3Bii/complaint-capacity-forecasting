"""Independent metric arithmetic and timing checks; no fitting-code imports."""
from collections import defaultdict
from pathlib import Path
import csv
import json
import math
import statistics

ROOT = Path(__file__).resolve().parents[1]
R = ROOT / 'results'

def read(name):
    with (R/name).open(newline='', encoding='utf-8') as stream:
        return list(csv.DictReader(stream))

def compare(a, b):
    assert math.isclose(float(a), float(b), rel_tol=1e-10, abs_tol=1e-9), (a,b)

def metrics(rows):
    errors = [float(r['prediction'])-float(r['complaints']) for r in rows]
    normalized = [e/float(r['scale']) for e,r in zip(errors,rows)]
    mse = math.fsum(e*e for e in errors)/len(errors)
    nmse = math.fsum(e*e for e in normalized)/len(errors)
    return {'n':len(rows),'mae_complaints':math.fsum(map(abs,errors))/len(errors),
        'mse_complaints_squared':mse,'rmse_complaints':math.sqrt(mse),
        'normalized_mae':math.fsum(map(abs,normalized))/len(errors),
        'normalized_mse':nmse,'normalized_rmse':math.sqrt(nmse)}

def shifted_month(value, delay):
    year, month = map(int,value[:7].split('-'))
    ordinal=year*12+month-1-delay
    return f'{ordinal//12:04d}-{ordinal%12+1:02d}-01'

def main():
    checks=[]
    for delay in (2,3):
        prefix=f'lag{delay}'
        cv=read(f'{prefix}_validation_predictions.csv')
        test=read(f'{prefix}_test_predictions.csv')
        by_model=defaultdict(list); by_fold=defaultdict(list); test_model=defaultdict(list)
        for row in cv:
            by_model[row['model']].append(row)
            by_fold[(row['model'],row['fold'])].append(row)
        for row in test: test_model[row['model']].append(row)
        assert len(by_model)==15 and len(by_fold)==45
        assert all(len(v)==108 for v in by_model.values())
        assert all(len(v)==36 for v in by_fold.values())
        for file,groups,key in [
            (f'{prefix}_tuning.csv',by_model,lambda r:r['name']),
            (f'{prefix}_fold_metrics.csv',by_fold,lambda r:(r['model'],r['fold'])),
            (f'{prefix}_test_metrics.csv',test_model,lambda r:r['model'])]:
            for reported in read(file):
                for metric,value in metrics(groups[key(reported)]).items():
                    compare(reported[metric],value)
        summary=json.loads((R/f'{prefix}_summary.json').read_text())
        selected=min(by_model,key=lambda name:(metrics(by_model[name])['normalized_mae'],name))
        assert summary['selected_model']==selected
        assert all(float(r['elapsed_seconds'])>=0 and r['status']=='completed'
                   for r in read(f'{prefix}_tuning.csv'))
        assert {(r['month'],r['product']) for r in cv}.isdisjoint(
               {(r['month'],r['product']) for r in test})
        features=read(f'{prefix}_features.csv')
        splits=json.loads((R/f'{prefix}_split_manifest.json').read_text())
        for split in splits:
            cutoff=shifted_month(split['origin'],delay)
            assert split['training_label_end']==cutoff
            expected=[r for r in features if r['month']<=cutoff]
            assert split['training_rows']==len(expected)
            assert all(r['month']<split['evaluation_start'] for r in expected)
        initial=[r for r in features if r['month']<=shifted_month('2023-01-01',delay)]
        per_product=defaultdict(list)
        for row in initial: per_product[row['product']].append(float(row['complaints']))
        for product,values in per_product.items():
            compare(summary['product_scales'][product],statistics.median(values))
        checks.append(f'{prefix}: 15 candidates, 45 fold scores, all test metrics, selection, source-label cutoff and scale availability verified')
    receipt={'status':'PASS','checks':checks,
        'independence':'stdlib CSV arithmetic; no fitting-code or metric-helper imports',
        'limits':'Does not establish historical source vintages, global optimization or a new untouched test.'}
    (R/'optimization_verification.json').write_text(json.dumps(receipt,indent=2),encoding='utf-8')
    print(json.dumps(receipt,indent=2))

if __name__=='__main__': main()
