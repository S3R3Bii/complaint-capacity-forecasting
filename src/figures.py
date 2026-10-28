"""Figures are drawn from saved test results, not hand-entered numbers."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import FuncFormatter

ROOT=Path(__file__).resolve().parents[1]
RESULTS=ROOT/'results'; FIGURES=ROOT/'figures';FIGURES.mkdir(exist_ok=True)
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':10,'axes.titlesize':13,
    'axes.labelcolor':'#263347','text.color':'#17283d','xtick.color':'#526273',
    'ytick.color':'#526273','axes.spines.top':False,'axes.spines.right':False,
    'axes.spines.left':False,'axes.edgecolor':'#c3cbd4','figure.facecolor':'white',
    'axes.facecolor':'white','savefig.facecolor':'white','svg.fonttype':'none'})
ACCENT='#057b89';BASE='#d17b32';GRAY='#a4adba'
summary=json.loads((RESULTS/'lag2_summary.json').read_text())
pred=pd.read_csv(RESULTS/'lag2_test_predictions.csv')
ml=summary['selected_ml_model'];baseline=summary['selected_baseline']
labels={'last_available':'Last available month','trailing_mean':'Trailing 3-month mean',
        'seasonal':'Same month last year',ml:'Tuned ridge regression'}

def save(fig,name):
    fig.savefig(FIGURES/f'{name}.png',dpi=190,bbox_inches='tight')
    fig.savefig(FIGURES/f'{name}.pdf',bbox_inches='tight')
    plt.close(fig)

fig,axes=plt.subplots(1,2,figsize=(12,4.8),gridspec_kw={'width_ratios':[1,1.3]})
scores=summary['test_normalized_mae']
names=sorted(scores,key=scores.get)
axes[0].barh(range(len(names)),[scores[n] for n in names],color=[ACCENT if n==ml else BASE if n==baseline else GRAY for n in names],height=.55)
axes[0].set_yticks(range(len(names)),[labels[n] for n in names]);axes[0].invert_yaxis()
for i,n in enumerate(names):axes[0].text(scores[n]+.025,i,f'{scores[n]:.3f}',va='center',fontsize=10)
axes[0].set_xlim(0,2.2);axes[0].set_xlabel('Mean absolute error / training product median')
axes[0].set_title('Forecast accuracy',loc='left',pad=14)
comps=summary['capacity_comparisons'];y=np.arange(3)
diff=np.array([r['paired_difference_ml_minus_baseline'] for r in comps])
lo=np.array([r['block_resampling_interval_95'][0] for r in comps]);hi=np.array([r['block_resampling_interval_95'][1] for r in comps])
axes[1].axvline(0,color='#728294',lw=1)
axes[1].errorbar(diff,y,xerr=[diff-lo,hi-diff],fmt='o',color=ACCENT,markersize=7,capsize=5,lw=2)
axes[1].set_yticks(y,['1 : 1','3 : 1','9 : 1']);axes[1].invert_yaxis()
axes[1].set_xlabel('Capacity loss difference: ridge − baseline\nNegative values favor ridge; normalized cost units')
axes[1].set_ylabel('Under-capacity : over-capacity cost')
axes[1].set_title('Decision value is less certain',loc='left',pad=14)
fig.suptitle('A more accurate forecast did not establish a better capacity policy',x=.01,ha='left',fontsize=17,fontweight='bold',y=1.07)
fig.text(.01,-.06,'Test: July 2024–June 2026 · 144 product-months · 6 products · Counts lagged by two months\nIntervals: 95% circular six-month block resampling of 24 test months. Cost ratios are scenarios; no dollar savings measured.',fontsize=9,color='#526273')
fig.tight_layout(w_pad=3)
save(fig,'forecast-and-decision')

short={'Checking or savings account':'Checking / savings','Debt collection':'Debt collection',
 'Money transfer, virtual currency, or money service':'Money transfers','Mortgage':'Mortgage',
 'Student loan':'Student loans','Vehicle loan or lease':'Vehicle loans'}
fig,axes=plt.subplots(2,3,figsize=(12,6.2),sharex=True)
for ax,(product,label) in zip(axes.flat,short.items()):
    sub=pred[pred['product']==product]
    actual=sub[sub.model==baseline]
    dates=pd.to_datetime(actual.month)
    ax.plot(dates,actual.complaints/1000,color='#263347',lw=1.8,label='Observed published count')
    ax.plot(dates,actual.prediction/1000,color=BASE,lw=1.4,ls='--',label='Last available month')
    ax.plot(dates,sub[sub.model==ml].prediction.to_numpy()/1000,color=ACCENT,lw=1.5,label='Tuned ridge')
    ax.set_title(label,loc='left');ax.grid(axis='y',alpha=.17);ax.tick_params(axis='x',rotation=25)
    ax.set_ylabel('Complaints, thousands')
    import matplotlib.dates as mdates
    ax.xaxis.set_major_locator(mdates.MonthLocator(interval=6));ax.xaxis.set_major_formatter(mdates.DateFormatter('%b %Y'))
handles,labs=axes[0,0].get_legend_handles_labels();fig.legend(handles,labs,loc='lower center',ncol=3,bbox_to_anchor=(.5,-.025),frameon=False)
fig.suptitle('Changing demand is uneven across the six product groups',x=.01,ha='left',fontweight='bold',fontsize=16,y=1.02)
fig.text(.01,-.08,'CFPB aggregate counts; retrieved 28 October 2026. Panels use different vertical scales to show within-product movement.\nA complaint count measures published reports, not prevalence of consumer harm or a company-specific staffing requirement.',fontsize=9,color='#526273')
fig.tight_layout()
save(fig,'product-forecast-traces')

tuning=pd.read_csv(RESULTS/'lag2_tuning.csv').sort_values('cv_normalized_mae')
fig,ax=plt.subplots(figsize=(9,6))
colors=[BASE if k=='baseline' else ACCENT if k=='ridge' else '#8793aa' for k in tuning.kind]
ax.barh(np.arange(len(tuning)),tuning.cv_normalized_mae,color=colors,height=.62)
ax.set_yticks(np.arange(len(tuning)),tuning.name);ax.invert_yaxis()
ax.set_xlim(0,float(tuning.cv_normalized_mae.max())*1.18)
for i,value in enumerate(tuning.cv_normalized_mae):ax.text(value+.008,i,f'{value:.3f}',va='center',fontsize=9)
ax.set_xlabel('Validation mean absolute error / training product median')
ax.set_title('The simple baseline won model selection',loc='left',pad=15,fontweight='bold',fontsize=16)
fig.text(.01,-.01,'Three forward validation folds, January 2023–June 2024. Every prespecified candidate is shown.\nOrange: baseline · Teal: ridge · Gray: shallow boosting. Final test performance did not change model selection.',fontsize=9,color='#526273')
fig.tight_layout(rect=[0,.09,1,1])
save(fig,'tuning-comparison')
print('Rendered three source-backed figures as PNG and PDF.')
