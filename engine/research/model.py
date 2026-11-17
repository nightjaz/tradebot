"""Signal combination: equal-weight z-score baseline and walk-forward ridge."""
from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.linear_model import Ridge


def equal_weight(z: dict[str, pd.DataFrame], signs: dict[str, float]) -> pd.DataFrame:
    """Average of sign-adjusted z-scores. Missing z (e.g. no recent earnings) counts as neutral 0,
    but a stock needs at least one live signal to be scored."""
    stack = [z[k].mul(signs[k]) for k in signs]
    live = sum(s.notna().astype(int) for s in stack)
    total = sum(s.fillna(0) for s in stack)
    return (total / len(stack)).where(live > 0)


def _design(z: dict[str, pd.DataFrame], fwd: pd.DataFrame | None, dates) -> tuple[np.ndarray, np.ndarray | None, pd.MultiIndex]:
    names = list(z)
    cols = [z[k].loc[dates].stack(future_stack=True).rename(k) for k in names]
    X = pd.concat(cols, axis=1)
    X = X[X.notna().any(axis=1)].fillna(0.0)
    y = None
    if fwd is not None:
        f = fwd.loc[dates]
        # demeaned cross-sectional target: we only care about relative returns
        f = f.sub(f.mean(axis=1), axis=0).stack(future_stack=True)
        y = f.reindex(X.index)
        keep = y.notna()
        X, y = X[keep], y[keep]
        y = y.clip(y.quantile(0.01), y.quantile(0.99)).values
    return X.values, y, X.index


def walk_forward_ridge(z: dict[str, pd.DataFrame], fwd: pd.DataFrame, alpha: float,
                       first_test_year: int, last_year: int, embargo: int = 5,
                       train_start: str = "2015-01-01") -> tuple[pd.DataFrame, dict]:
    """Retrain at the start of every calendar year on an expanding window that ends `embargo`
    trading days before the test year (labels reach 2 days ahead, so this stops overlap)."""
    dates = next(iter(z.values())).index
    preds = pd.DataFrame(np.nan, index=dates, columns=next(iter(z.values())).columns)
    coefs = {}
    for year in range(first_test_year, last_year + 1):
        test = dates[(dates >= f"{year}-01-01") & (dates <= f"{year}-12-31")]
        if len(test) == 0:
            continue
        train = dates[(dates >= train_start) & (dates < f"{year}-01-01")]
        train = train[:-embargo] if embargo else train
        X, y, _ = _design(z, fwd, train)
        if len(y) < 1000:
            continue
        m = Ridge(alpha=alpha, fit_intercept=False).fit(X, y)
        coefs[year] = dict(zip(z.keys(), m.coef_))
        Xt, _, idx = _design(z, None, test)
        p = pd.Series(m.predict(Xt), index=idx).unstack()
        preds.loc[p.index, p.columns] = p
    return preds, coefs
