"""Training-fold-only policy simulations for sparse stock edge cases.

These add coverage of explicit business rules, not independent real evidence.
"""
import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, ClassifierMixin, clone
from sklearn.preprocessing import StandardScaler
from sklearn.utils.class_weight import compute_sample_weight
from inventory_policy import policy_metrics, stock_policy_label


def simulate(row, changes):
    r=row.copy();r.update(changes)
    r['stock_value']=r['stock_qty']*r['retail_price']
    r['velocity_trend']=r['recent_avg']/(r['historical_avg']+0.1)
    r['sales_volatility']=r['recent_std']/(r['recent_avg']+0.1)
    r['is_active']=int(r['days_since_last_sale']<=7)
    r['is_dormant']=r['days_since_over_90']=int(r['days_since_last_sale']>90)
    r['price_velocity_interaction']=r['retail_price']*r['velocity_trend']
    r.update(policy_metrics(stock_qty=r['stock_qty'],forecast_30d=r['forecast_30d'],forecast_7d=r['forecast_7d'],recent_qty=r['recent_qty']))
    return r


class PolicyAugmentedClassifier(ClassifierMixin, BaseEstimator):
    def __init__(self, estimator):self.estimator=estimator
    def fit(self,X,y):
        X=pd.DataFrame(X).copy()
        rows=[];labels=[]
        for r in X.to_dict('records'):
            demand=max(r['forecast_30d'],r['recent_qty'],1)
            changes=[{'stock_qty':0}, {'stock_qty':demand*12},
                {'recent_qty':0,'recent_avg':0,'recent_std':0,'days_since_last_sale':365},
                {'recent_qty':r['recent_qty']*10,'recent_avg':r['recent_avg']*10,'recent_std':r['recent_std']*10}]
            changes += [{'stock_qty':(demand+1)*coverage} for coverage in (0.59,0.81,2.01,4.01)]
            for change in changes:
                variant=simulate(r,change);rows.append(variant);labels.append(stock_policy_label(variant))
        augmented=pd.concat([X,pd.DataFrame(rows,columns=X.columns)],ignore_index=True)
        target=np.concatenate([np.asarray(y),np.asarray(labels)])
        # Original observations retain four times the weight of each simulation.
        weights=compute_sample_weight('balanced',target)*np.concatenate([np.full(len(X),4.0),np.ones(len(rows))])
        self.scaler_=StandardScaler().fit(augmented)
        self.model_=clone(self.estimator).fit(self.scaler_.transform(augmented),target,sample_weight=weights)
        self.classes_=self.model_.classes_;self.n_features_in_=X.shape[1]
        self.synthetic_rows_=len(rows)
        return self
    def predict(self,X):return self.model_.predict(self.scaler_.transform(X))
    def predict_proba(self,X):return self.model_.predict_proba(self.scaler_.transform(X))
