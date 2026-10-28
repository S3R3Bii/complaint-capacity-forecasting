# Capacity planning from published complaint counts

Protocol fixed on 28 October 2026 before model fitting or test scoring. The initial API probe checked January 2025 availability; category coverage was inspected across the retrieved snapshot to choose labels that persist for all 102 months. No model result informed these choices.

**Decision.** Choose a monthly capacity forecast when an unhandled complaint and an unused unit of capacity have unequal costs. The population is published CFPB complaints, not all consumer problems, company customer counts, or actual staffing hours.

**Data.** January 2018–June 2026, six consistently named products: checking/savings, debt collection, money transfer, mortgage, student loan, vehicle loan/lease. Use aggregate counts only. Exclude categories that were split or renamed. A stable label does not prove stable reporting behavior.

**Information set.** Forecast month t using counts from t−2 and earlier. A one-complete-month buffer is a declared scenario for publication delay, not verified point-in-time availability. Repeat at lag 3. The downloaded final snapshot may contain revisions; this is a retrospective replay, not proof of live performance.

**Comparisons.** Last available month, trailing available three-month mean, same month last year, ridge regression on log counts, and shallow histogram gradient boosting on log counts. All receive the same lag restrictions. Fit preprocessing within each training fold. Month sine/cosine, calendar trend, product indicator and lagged counts are available predictors. No complaint outcome, company response or future count is permitted.

**Tuning.** Three expanding six-month validation folds cover January 2023–June 2024. Models first train on target months January 2019–December 2022. Select by mean absolute error normalized by each product's training-period median, giving each product equal influence. Ridge alphas: 0.1, 1, 10, 100. Boosting: 100 iterations, depth 2 or 3, learning rate 0.05 or 0.10, L2 penalty 0 or 1, minimum leaf size 12. These are prespecified small-data search choices, not previously demonstrated optima. Seed 20261028.

**Final test.** July 2024–June 2026 stays untouched until selection. Freeze model parameters after fitting through June 2024; advance only the permitted lagged observations. Report all candidates' validation results but do not change selection after seeing the test.

**Capacity policy.** Calibrate positive/negative residual quantiles using out-of-fold validation residuals scaled by product training medians. Evaluate under-capacity:over-capacity cost ratios 1:1, 3:1 and 9:1, using dimensionless cost units. These ratios are sensitivity scenarios, not measured labor costs. Compare policies on normalized and raw loss, unmet observed complaint volume, and unused capacity. No headcount, dollar saving, or realized service improvement claim.

**Checks.** Reconcile product buckets to API totals; verify source hashes, all dates, nonnegative integer counts and unique product-month keys. Execute SQL lag queries and audit their dates. Recompute losses independently from exported predictions. Use six-month moving-block resampling for uncertainty in paired loss differences, with its limited 24-month test horizon stated. Inspect every figure and the compiled private manuscript. Record negative results.

**Contribution.** A reproducible decision evaluation with delayed features, equal-product weighting and asymmetric costs. Existing CFPB reporting and complaint-mining studies already analyze the database. No claim of a new algorithm or globally novel research gap.
