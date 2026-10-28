"""Retrospective, delayed-information capacity study. No complaint-level data."""
import os
os.environ.setdefault('OMP_NUM_THREADS', '2')
os.environ.setdefault('OPENBLAS_NUM_THREADS', '2')
from pathlib import Path
from datetime import datetime, timezone
import hashlib
import json
import sqlite3
import time
import platform

import numpy as np
import pandas as pd
import sklearn
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.linear_model import Ridge
from sklearn.ensemble import HistGradientBoostingRegressor

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'results'
SEED = 20261028
PRODUCTS = ['Checking or savings account', 'Debt collection',
            'Money transfer, virtual currency, or money service',
            'Mortgage', 'Student loan', 'Vehicle loan or lease']
SHORT = dict(zip(PRODUCTS, ['Checking / savings', 'Debt collection', 'Money transfers',
                          'Mortgage', 'Student loans', 'Vehicle loans']))
FOLDS = [('2023-01-01', '2023-07-01'), ('2023-07-01', '2024-01-01'),
         ('2024-01-01', '2024-07-01')]
TEST_START = '2024-07-01'

def save_json(name, value):
    (OUT/name).write_text(json.dumps(value, indent=2, allow_nan=False), encoding='utf-8')

def build_database():
    db = sqlite3.connect(':memory:')
    db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
      CREATE TABLE snapshots(month TEXT PRIMARY KEY, total INTEGER NOT NULL CHECK(total>=0),
        retrieved_utc TEXT NOT NULL, source_sha256 TEXT NOT NULL);
      CREATE TABLE product_counts(month TEXT REFERENCES snapshots(month), product TEXT,
        complaints INTEGER NOT NULL CHECK(complaints>=0), PRIMARY KEY(month, product));
    ''')
    manifest = json.loads((ROOT/'data/manifest.json').read_text())
    for entry in manifest:
        path = ROOT/entry['file']
        assert hashlib.sha256(path.read_bytes()).hexdigest() == entry['sha256']
        raw = json.loads(path.read_text())
        assert sum(raw['product_counts'].values()) == raw['total_complaints']
        db.execute('INSERT INTO snapshots VALUES (?,?,?,?)',
                   (raw['period_start_inclusive'], raw['total_complaints'],
                    raw['retrieved_utc'], entry['sha256']))
        db.executemany('INSERT INTO product_counts VALUES (?,?,?)',
            [(raw['period_start_inclusive'], k, v) for k,v in raw['product_counts'].items()])
    # Every category used in forecasting must be represented in every month.
    counts = dict(db.execute('SELECT product,COUNT(*) FROM product_counts GROUP BY product'))
    assert all(counts[p] == 102 for p in PRODUCTS)
    for name, count in db.execute('SELECT month,COUNT(*) FROM snapshots GROUP BY month'):
        assert count == 1
    db.commit()
    connection = sqlite3.connect(ROOT/'data/aggregate_counts.sqlite')
    db.backup(connection); connection.close()
    return db

def feature_frame(db, delay):
    lags = [delay, delay+1, delay+2, 12]
    fields = ',\n'.join(f'LAG(complaints,{lag}) OVER w AS lag_{lag}, '
                       f'LAG(month,{lag}) OVER w AS source_month_{lag}' for lag in lags)
    sql = f'''WITH lagged AS (
      SELECT month,product,complaints,{fields}
      FROM product_counts
      WINDOW w AS (PARTITION BY product ORDER BY month)
    ) SELECT * FROM lagged WHERE month >= '2019-01-01'
      AND product IN ({','.join('?' for p in PRODUCTS)}) ORDER BY month,product;'''
    (ROOT/'sql').mkdir(exist_ok=True)
    (ROOT/'sql'/f'features_lag{delay}.sql').write_text(sql,encoding='utf-8')
    frame = pd.read_sql_query(sql,db,params=PRODUCTS)
    assert len(frame) == 90*6 and frame.notna().all().all()
    dates = pd.to_datetime(frame.month)
    for lag in lags:
        expected = (dates.dt.to_period('M')-lag).astype(str)+'-01'
        assert (frame[f'source_month_{lag}'] == expected).all()
        frame[f'log_lag_{lag}'] = np.log1p(frame[f'lag_{lag}'])
    frame['month_sin'] = np.sin(2*np.pi*dates.dt.month/12)
    frame['month_cos'] = np.cos(2*np.pi*dates.dt.month/12)
    frame['trend'] = (dates.dt.year-2019)*12+dates.dt.month-1
    initial = frame[frame.month < '2023-01-01']
    scales = initial.groupby('product').complaints.median().to_dict()
    frame['scale'] = frame['product'].map(scales)
    assert (frame.scale>0).all()
    return frame, lags, scales

def candidates():
    specs = [{'name':n,'kind':'baseline'} for n in ['last_available','trailing_mean','seasonal']]
    for alpha in [0.1,1,10,100]:
        specs.append({'name':f'ridge_a{alpha}','kind':'ridge','alpha':alpha})
    for depth in [2,3]:
        for lr in [.05,.1]:
            for l2 in [0,1]:
                specs.append({'name':f'boost_d{depth}_lr{lr}_l2{l2}', 'kind':'boost',
                              'max_depth':depth,'learning_rate':lr,'l2_regularization':l2})
    return specs

def predict(spec, train, target, lags):
    name = spec['name']
    if spec['kind'] == 'baseline':
        if name == 'last_available': return target[f'lag_{lags[0]}'].to_numpy(float)
        if name == 'trailing_mean': return target[[f'lag_{v}' for v in lags[:3]]].mean(axis=1).to_numpy()
        return target['lag_12'].to_numpy(float)
    features = [f'log_lag_{v}' for v in lags]+['month_sin','month_cos','trend']
    transformer = ColumnTransformer([
        ('numeric', StandardScaler(), features),
        ('product', OneHotEncoder(handle_unknown='error',sparse_output=False), ['product'])])
    if spec['kind'] == 'ridge':
        regressor = Ridge(alpha=spec['alpha'])
    else:
        regressor = HistGradientBoostingRegressor(
            max_iter=100, max_depth=spec['max_depth'], learning_rate=spec['learning_rate'],
            l2_regularization=spec['l2_regularization'], min_samples_leaf=12,
            early_stopping=False,random_state=SEED)
    pipeline = make_pipeline(transformer,regressor)
    pipeline.fit(train, np.log1p(train.complaints))
    return np.maximum(0,np.expm1(pipeline.predict(target)))

def moving_block_interval(monthly_delta, draws=2000):
    x = np.asarray(monthly_delta,float)
    rng = np.random.default_rng(SEED)
    length = 6
    blocks = [np.arange(start,start+length)%len(x) for start in range(len(x))]
    means = []
    for _ in range(draws):
        idx = np.concatenate([blocks[i] for i in rng.integers(0,len(blocks),4)])[:len(x)]
        means.append(float(x[idx].mean()))
    return np.quantile(means,[.025,.975]).tolist()

def run_scenario(db, delay):
    frame,lags,scales = feature_frame(db,delay)
    validation, scores = {},[]
    for spec in candidates():
        print(f'lag {delay}: validating {spec["name"]}', flush=True)
        start_time = time.perf_counter()
        fold_predictions=[]
        for fold,(start,end) in enumerate(FOLDS):
            training = frame[frame.month < start]
            valid = frame[(frame.month >= start)&(frame.month < end)].copy()
            assert training.month.max() < valid.month.min()
            valid['prediction'] = predict(spec,training,valid,lags)
            valid['fold']=fold+1
            fold_predictions.append(valid[['month','product','complaints','scale','prediction','fold']])
        cv = pd.concat(fold_predictions)
        validation[spec['name']] = cv
        errors = np.abs(cv.complaints-cv.prediction)/cv.scale
        scores.append({**spec,'cv_normalized_mae':float(errors.mean()),
                       'elapsed_seconds':time.perf_counter()-start_time})
    scores.sort(key=lambda x:(x['cv_normalized_mae'],x['name']))
    winner = scores[0]
    ml_winner = next(s for s in scores if s['kind']!='baseline')
    # A simple baseline is allowed to win; no ML promotion after viewing the test.
    included = [s for s in candidates() if s['kind']=='baseline' or s['name']==winner['name']
                or s['name']==ml_winner['name']]
    training = frame[frame.month<TEST_START]
    target = frame[frame.month>=TEST_START].copy()
    point_predictions, capacities = [],[]
    for spec in included:
        test = target[['month','product','complaints','scale']].copy()
        test['prediction'] = predict(spec,training,target,lags)
        test['model'] = spec['name']
        point_predictions.append(test)
        cv = validation[spec['name']]
        normalized_residual = (cv.complaints-cv.prediction)/cv.scale
        for ratio in [1,3,9]:
            quantile = ratio/(ratio+1)
            correction = float(np.quantile(normalized_residual,quantile))
            policy = test.copy()
            policy['cost_ratio'] = ratio
            policy['residual_quantile'] = correction
            policy['capacity'] = np.maximum(0,policy.prediction+correction*policy.scale)
            policy['under'] = np.maximum(0,policy.complaints-policy.capacity)
            policy['over'] = np.maximum(0,policy.capacity-policy.complaints)
            policy['cost'] = ratio*policy.under+policy.over
            policy['normalized_cost'] = policy.cost/policy.scale
            capacities.append(policy)
    predictions = pd.concat(point_predictions,ignore_index=True)
    policies = pd.concat(capacities,ignore_index=True)
    predictions['normalized_absolute_error'] = np.abs(predictions.complaints-predictions.prediction)/predictions.scale
    baseline_names = [s['name'] for s in scores if s['kind']=='baseline']
    baseline = baseline_names[0] # chosen using validation, not final test
    comparisons=[]
    for ratio in [1,3,9]:
        part=policies[policies.cost_ratio==ratio]
        month_loss=part.groupby(['month','model']).normalized_cost.mean().unstack()
        delta=month_loss[ml_winner['name']]-month_loss[baseline]
        comparisons.append({'cost_ratio':ratio,'ml_model':ml_winner['name'],'baseline':baseline,
             'ml_mean_cost':float(month_loss[ml_winner['name']].mean()),
             'baseline_mean_cost':float(month_loss[baseline].mean()),
             'paired_difference_ml_minus_baseline':float(delta.mean()),
             'block_resampling_interval_95':moving_block_interval(delta)})
    prefix=f'lag{delay}'
    pd.DataFrame(scores).to_csv(OUT/f'{prefix}_tuning.csv',index=False)
    pd.concat([v.assign(model=k) for k,v in validation.items()]).to_csv(OUT/f'{prefix}_validation_predictions.csv',index=False)
    predictions.to_csv(OUT/f'{prefix}_test_predictions.csv',index=False)
    policies.to_csv(OUT/f'{prefix}_capacity_policies.csv',index=False)
    frame.to_csv(OUT/f'{prefix}_features.csv',index=False)
    summary={'delay_months':delay,'selected_model':winner['name'],
       'selected_ml_model':ml_winner['name'],'selected_baseline':baseline,
       'initial_training_rows':288,'validation_rows':108,'test_rows':144,
       'product_scales':scales,'validation_score':winner['cv_normalized_mae'],
       'test_normalized_mae':predictions.groupby('model').normalized_absolute_error.mean().to_dict(),
       'capacity_comparisons':comparisons}
    save_json(f'{prefix}_summary.json',summary)
    return summary

def main():
    OUT.mkdir(exist_ok=True)
    db=build_database()
    summaries=[run_scenario(db,delay) for delay in [2,3]]
    save_json('execution.json',{'completed_utc':datetime.now(timezone.utc).isoformat(),
       'python':platform.python_version(),'numpy':np.__version__,'pandas':pd.__version__,
       'scikit_learn':sklearn.__version__,'seed':SEED,'source_snapshots':102,
       'selected_products':6,'models_per_delay':15,'validation_folds':3,
       'main_scenario':summaries[0],'sensitivity_scenario':summaries[1],
       'scope':'Retrospective final-snapshot replay; no live operation or actual staffing-cost claim.'})
    print(json.dumps(summaries,indent=2))

if __name__=='__main__': main()
