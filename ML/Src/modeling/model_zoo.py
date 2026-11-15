"""The candidate models. Deliberately short and regularised: ~230 events cannot support 12 models,
and the 'best' of many models on so little data is partly luck. All are scikit-learn only.

Every model is wrapped in ONE pipeline (impute -> scale -> one-hot -> estimator), so all preprocessing
is fitted on training rows only and is saved together with the model.
"""
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import ExtraTreesClassifier, HistGradientBoostingClassifier, RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from training_utils import CAT_FEATURES, SEED, ClimatologyRate


def preprocessor(numeric_cols):
    return ColumnTransformer([
        ("num", Pipeline([("imp", SimpleImputer(strategy="median")), ("sc", StandardScaler())]), list(numeric_cols)),
        ("cat", OneHotEncoder(handle_unknown="ignore", sparse_output=False), CAT_FEATURES),
    ], verbose_feature_names_out=False)


def with_prep(estimator, numeric_cols):
    return Pipeline([("prep", preprocessor(numeric_cols)), ("model", estimator)])


def baselines():
    """Models every real model must beat. They use only region+window (and the overall rate)."""
    return {
        "Baseline: overall rate": DummyClassifier(strategy="prior"),
        "Baseline: region+window climatology": ClimatologyRate(),
    }


def zoo(numeric_cols):
    cw = "balanced"
    est = {
        "Logistic (L2, C=0.1)": LogisticRegression(C=0.1, class_weight=cw, max_iter=5000),
        "Logistic (L2, C=1)": LogisticRegression(C=1.0, class_weight=cw, max_iter=5000),
        "Random Forest": RandomForestClassifier(n_estimators=200, min_samples_leaf=5, max_features="sqrt",
                                                class_weight="balanced_subsample", random_state=SEED, n_jobs=-1),
        "Extra Trees": ExtraTreesClassifier(n_estimators=200, min_samples_leaf=5, max_features="sqrt",
                                            class_weight=cw, random_state=SEED, n_jobs=-1),
        "HistGradientBoosting": HistGradientBoostingClassifier(max_iter=100, max_depth=3, learning_rate=0.05,
                                                               min_samples_leaf=15, l2_regularization=1.0,
                                                               class_weight=cw, random_state=SEED),
    }
    return {name: with_prep(m, numeric_cols) for name, m in est.items()}
