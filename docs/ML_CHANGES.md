# ML and forecasting changes

## Implemented

1. **Complete daily calendar.** Missing transaction days and the trailing interval through the dataset cutoff are represented as zero sales. This requires complete transaction capture; missing source records cannot safely be interpreted as zero sales without that assumption.
2. **Select forecasts on past data.** For each eligible store/product series, compare weekly repetition, recent mean and a regularized Prophet model on the last 14 historical days. Refit the selected method on all available history. The forecast backtest uses an additional outer future interval, separate from that historical selection interval.
3. **Regularize classifiers.** Reduce tree depth, increase leaf-size/minimum-child constraints and add XGBoost regularization.
4. **Simulate edge cases only inside training folds.** Zero stock, very large stock, inactivity, demand shocks and boundary cases are generated from the current training partition only. Each cross-validation fold independently generates its simulations. Real observations receive higher weight than each simulation. These are explicit policy simulations, not newly collected ground-truth data.
5. **Keep reporting honest.** Preserve grouped validation, class-level metrics, the prior model artifacts, stress tests and the distinction between policy decisions and learned-model support. Label the current re-evaluation as development evidence because the historical test split has already been inspected.
6. **Publish consistently.** Updated forecasts, stock predictions and transfer recommendations reach the dashboard through an atomic database operation. Prediction records carry the selected demand method.

## Measured development results

| Measure | Previous | Current |
|---|---:|---:|
| Classifier macro F1 against policy labels | 0.718 | 1.000 |
| Mean grouped training-partition validation macro F1 | 0.727 | 0.973 |
| No-sales stress agreement with stock policy | 13.3% | 100% |
| Unseen store/product stress agreement | 68.1% | 100% |
| Extra randomized stress agreement | Not measured | 99.0% over 1,000 cases |
| Daily forecast MAE | 1.582 | 1.114 |
| Weekly naive forecast MAE | 1.211 | 1.211 |
| Forecast RMSE | 2.346 | 2.695 |
| Forecast WAPE | 262.1% | 184.6% |

The new forecasting strategy improves MAE by roughly 30%, and improves on the weekly baseline's MAE by roughly 8%, on this development backtest. RMSE worsens, meaning large errors remain a problem. WAPE remains high on sparse demand. MAE alone is not sufficient to declare the forecasts good.

The perfect classifier development F1 does not establish real-world accuracy. The classifier is trained to reproduce known rules, the simulations cover those rules, forecast changes also change some policy labels, and the historical split has already been used during development. The before/after F1 values are therefore not an independent same-target final comparison. Three stores and 175 stock snapshots are insufficient to establish production generalization.

## Still needed

- Confirm who created the spreadsheets, how sales/stock were collected, and whether categories/prices are authentic.
- Collect additional independent stores and multiple dated stock snapshots.
- Obtain retailer-reviewed labels and actual replenishment/stockout outcomes.
- Reserve future periods and stores that remain untouched until final evaluation.
- Improve large forecast errors, evaluate additional rolling origins, and calibrate uncertainty before relying on automated purchasing decisions.

No genuine independent business F1 can be promised without that evidence. Current stock outputs remain explicit policy decisions, with separate model support.
