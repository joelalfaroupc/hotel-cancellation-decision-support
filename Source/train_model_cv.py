import json
import os
from pathlib import Path

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import joblib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
from sklearn.ensemble import (
    ExtraTreesClassifier,
    HistGradientBoostingClassifier,
    RandomForestClassifier,
)
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.model_selection import RandomizedSearchCV, StratifiedKFold
from xgboost import XGBClassifier


RANDOM_STATE = 42
REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "Data" / "dades_preprocessades_ml"
OUTPUT_DIR = REPO_ROOT / "runs" / "cross_validation"
CV_FOLDS = 3
N_ITER = 6
SELECTION_METRIC = "f1"
SHAP_SAMPLE_SIZE = 300
SHAP_TOP_FEATURES = 10
SHAP_LOCAL_EXAMPLES = 15


def load_split(data_dir: Path, split_name: str) -> tuple[pd.DataFrame, pd.Series]:
    X = pd.read_csv(data_dir / f"X_{split_name}.csv")
    y = pd.read_csv(data_dir / f"y_{split_name}.csv").iloc[:, 0]
    return X, y


def get_model_spaces(scale_pos_weight: float) -> dict[str, tuple[object, dict[str, list]]]:
    return {
        "random_forest": (
            RandomForestClassifier(
                random_state=RANDOM_STATE,
                n_jobs=1,
                class_weight="balanced",
            ),
            {
                "n_estimators": [200, 300, 500],
                "max_depth": [None, 8, 12, 16],
                "min_samples_split": [2, 5, 10],
                "min_samples_leaf": [1, 2, 4],
                "max_features": ["sqrt", "log2", 0.5],
            },
        ),
        "extra_trees": (
            ExtraTreesClassifier(
                random_state=RANDOM_STATE,
                n_jobs=1,
                class_weight="balanced",
            ),
            {
                "n_estimators": [200, 300, 500],
                "max_depth": [None, 8, 12, 16],
                "min_samples_split": [2, 5, 10],
                "min_samples_leaf": [1, 2, 4],
                "max_features": ["sqrt", "log2", 0.5],
            },
        ),
        "hist_gradient_boosting": (
            HistGradientBoostingClassifier(
                random_state=RANDOM_STATE,
            ),
            {
                "learning_rate": [0.03, 0.05, 0.1],
                "max_iter": [200, 300, 500],
                "max_depth": [None, 6, 10],
                "min_samples_leaf": [10, 20, 40],
                "l2_regularization": [0.0, 0.1, 1.0],
            },
        ),
        "xgboost": (
            XGBClassifier(
                objective="binary:logistic",
                eval_metric="logloss",
                tree_method="hist",
                random_state=RANDOM_STATE,
                n_jobs=1,
                scale_pos_weight=scale_pos_weight,
            ),
            {
                "n_estimators": [200, 300, 500],
                "max_depth": [3, 5, 7],
                "learning_rate": [0.03, 0.05, 0.1],
                "subsample": [0.8, 0.9, 1.0],
                "colsample_bytree": [0.7, 0.85, 1.0],
                "min_child_weight": [1, 3, 5],
            },
        )
    }


def get_scores(model, X: pd.DataFrame) -> np.ndarray | None:
    if hasattr(model, "predict_proba"):
        return model.predict_proba(X)[:, 1]
    if hasattr(model, "decision_function"):
        return model.decision_function(X)
    return None


def evaluate_model(model, X: pd.DataFrame, y: pd.Series) -> dict[str, float | None]:
    y_pred = model.predict(X)
    y_score = get_scores(model, X)

    metrics: dict[str, float | None] = {
        "accuracy": float(accuracy_score(y, y_pred)),
        "precision": float(precision_score(y, y_pred, zero_division=0)),
        "recall": float(recall_score(y, y_pred, zero_division=0)),
        "f1": float(f1_score(y, y_pred, zero_division=0)),
    }
    metrics["roc_auc"] = float(roc_auc_score(y, y_score)) if y_score is not None else None
    return metrics


def to_builtin(value):
    if isinstance(value, dict):
        return {k: to_builtin(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_builtin(v) for v in value]
    if isinstance(value, tuple):
        return [to_builtin(v) for v in value]
    if isinstance(value, np.generic):
        return value.item()
    return value


def get_shap_matrix(shap_values) -> np.ndarray:
    values = shap_values.values if hasattr(shap_values, "values") else shap_values

    if isinstance(values, list):
        return values[1]

    if isinstance(values, np.ndarray) and values.ndim == 3:
        return values[:, :, 1]

    return values


def explain_best_model(
    model,
    X_test: pd.DataFrame,
    output_dir: Path,
) -> list[dict[str, float | str]]:
    shap_dir = output_dir / "shap"
    shap_dir.mkdir(parents=True, exist_ok=True)

    X_sample = X_test.sample(min(len(X_test), SHAP_SAMPLE_SIZE), random_state=RANDOM_STATE)
    explainer = shap.TreeExplainer(model)
    shap_matrix = get_shap_matrix(explainer(X_sample))

    importance = pd.DataFrame(
        {
            "feature": X_sample.columns,
            "mean_abs_shap": np.abs(shap_matrix).mean(axis=0),
        }
    ).sort_values("mean_abs_shap", ascending=False)

    importance.to_csv(shap_dir / "best_model_shap_global_importance.csv", index=False)

    plt.figure(figsize=(10, 6))
    shap.plots.bar(
        shap.Explanation(
            values=shap_matrix,
            base_values=np.zeros(len(X_sample)),
            data=X_sample.to_numpy(),
            feature_names=X_sample.columns.tolist(),
        ),
        max_display=SHAP_TOP_FEATURES,
        show=False,
    )
    plt.tight_layout()
    plt.savefig(shap_dir / "best_model_shap_bar.png", dpi=200, bbox_inches="tight")
    plt.close()

    plt.figure(figsize=(10, 6))
    shap.plots.beeswarm(
        shap.Explanation(
            values=shap_matrix,
            base_values=np.zeros(len(X_sample)),
            data=X_sample.to_numpy(),
            feature_names=X_sample.columns.tolist(),
        ),
        max_display=SHAP_TOP_FEATURES,
        show=False,
    )
    plt.tight_layout()
    plt.savefig(shap_dir / "best_model_shap_beeswarm.png", dpi=200, bbox_inches="tight")
    plt.close()

    sample_scores = get_scores(model, X_sample)
    if sample_scores is None:
        sample_scores = model.predict(X_sample)

    local_rows = []
    ranked_rows = np.argsort(sample_scores)[::-1][:SHAP_LOCAL_EXAMPLES]

    for row_idx in ranked_rows:
        contributions = pd.Series(shap_matrix[row_idx], index=X_sample.columns)
        top_features = contributions.abs().sort_values(ascending=False).head(5)

        row = {
            "row_index": int(X_sample.index[row_idx]),
            "score": float(sample_scores[row_idx]),
        }

        for position, feature in enumerate(top_features.index, start=1):
            row[f"top_feature_{position}"] = feature
            row[f"top_shap_{position}"] = float(contributions[feature])

        local_rows.append(row)

    pd.DataFrame(local_rows).to_csv(
        shap_dir / "best_model_shap_local_examples.csv",
        index=False,
    )

    return to_builtin(
        importance.head(SHAP_TOP_FEATURES).to_dict(orient="records")
    )


def main() -> None:
    data_dir = DATA_DIR
    output_dir = OUTPUT_DIR
    models_dir = output_dir / "models"
    output_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    X_train, y_train = load_split(data_dir, "train")
    X_val, y_val = load_split(data_dir, "val")
    X_test, y_test = load_split(data_dir, "test")

    X_dev = pd.concat([X_train, X_val], ignore_index=True)
    y_dev = pd.concat([y_train, y_val], ignore_index=True)

    class_counts = y_dev.value_counts().sort_index()
    negative_count = int(class_counts.get(0, 0))
    positive_count = int(class_counts.get(1, 1))
    scale_pos_weight = negative_count / max(positive_count, 1)

    cv = StratifiedKFold(
        n_splits=CV_FOLDS,
        shuffle=True,
        random_state=RANDOM_STATE,
    )

    leaderboard_rows = []
    tuned_models: dict[str, object] = {}
    search_summaries = {}

    for model_name, (estimator, param_space) in get_model_spaces(scale_pos_weight).items():
        search = RandomizedSearchCV(
            estimator=estimator,
            param_distributions=param_space,
            n_iter=N_ITER,
            scoring=SELECTION_METRIC,
            cv=cv,
            random_state=RANDOM_STATE,
            n_jobs=1,
            verbose=0,
            refit=True,
        )
        search.fit(X_dev, y_dev)

        best_model = search.best_estimator_
        tuned_models[model_name] = best_model

        dev_metrics = evaluate_model(best_model, X_dev, y_dev)
        test_metrics = evaluate_model(best_model, X_test, y_test)

        leaderboard_rows.append(
            {
                "model": model_name,
                "cv_best_score": float(search.best_score_),
                "dev_accuracy": dev_metrics["accuracy"],
                "dev_f1": dev_metrics["f1"],
                "test_accuracy": test_metrics["accuracy"],
                "test_precision": test_metrics["precision"],
                "test_recall": test_metrics["recall"],
                "test_f1": test_metrics["f1"],
                "test_roc_auc": test_metrics["roc_auc"],
            }
        )

        search_summaries[model_name] = {
            "best_score": float(search.best_score_),
            "best_params": to_builtin(search.best_params_),
            "dev_metrics": dev_metrics,
            "test_metrics": test_metrics,
        }

        joblib.dump(best_model, models_dir / f"{model_name}.joblib")
        print(
            f"{model_name}: cv_best_score={search.best_score_:.4f}, "
            f"test_f1={test_metrics['f1']:.4f}, "
            f"test_roc_auc={test_metrics['roc_auc']:.4f}"
        )

    leaderboard = pd.DataFrame(leaderboard_rows).sort_values(
        by=["cv_best_score", "test_f1"],
        ascending=False,
    ).reset_index(drop=True)
    leaderboard.to_csv(output_dir / "leaderboard.csv", index=False)

    best_model_name = leaderboard.iloc[0]["model"]
    best_model = tuned_models[best_model_name]
    best_test_metrics = evaluate_model(best_model, X_test, y_test)
    top_shap_features = explain_best_model(best_model, X_test, output_dir)

    confusion = confusion_matrix(y_test, best_model.predict(X_test))
    pd.DataFrame(
        confusion,
        index=["actual_0", "actual_1"],
        columns=["pred_0", "pred_1"],
    ).to_csv(output_dir / f"{best_model_name}_test_confusion_matrix.csv")

    predictions = pd.DataFrame(
        {
            "y_true": y_test.reset_index(drop=True),
            "y_pred": best_model.predict(X_test),
        }
    )
    test_scores = get_scores(best_model, X_test)
    if test_scores is not None:
        predictions["score"] = test_scores
    predictions.to_csv(output_dir / f"{best_model_name}_test_predictions.csv", index=False)

    joblib.dump(best_model, output_dir / "best_model.joblib")

    summary = {
        "best_model": best_model_name,
        "selection_metric": SELECTION_METRIC,
        "cv_folds": CV_FOLDS,
        "n_iter": N_ITER,
        "scale_pos_weight": scale_pos_weight,
        "dev_rows": int(len(X_dev)),
        "test_rows": int(len(X_test)),
        "n_features": int(X_dev.shape[1]),
        "model_searches": search_summaries,
        "best_test_metrics": best_test_metrics,
        "best_model_top_shap_features": top_shap_features,
    }
    with open(output_dir / "best_model_summary.json", "w", encoding="utf-8") as f:
        json.dump(to_builtin(summary), f, indent=2)

    print("\nLeaderboard:")
    print(leaderboard.to_string(index=False))
    print(f"\nBest model: {best_model_name}")


if __name__ == "__main__":
    main()
