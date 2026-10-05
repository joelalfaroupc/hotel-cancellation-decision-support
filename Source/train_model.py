import json
import os
from pathlib import Path

os.environ["OMP_NUM_THREADS"] = "1"
os.environ["OPENBLAS_NUM_THREADS"] = "1"
os.environ["MKL_NUM_THREADS"] = "1"
os.environ["VECLIB_MAXIMUM_THREADS"] = "1"
os.environ["NUMEXPR_NUM_THREADS"] = "1"

import joblib
import pandas as pd
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression, SGDClassifier
from sklearn.naive_bayes import GaussianNB
from sklearn.svm import LinearSVC
from sklearn.tree import DecisionTreeClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)


RANDOM_STATE = 42
REPO_ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = REPO_ROOT / "Data" / "dades_preprocessades_ml"
OUTPUT_DIR = REPO_ROOT / "runs" / "baseline"
SELECTION_METRIC = "f1"


def load_split(data_dir: Path, split_name: str) -> tuple[pd.DataFrame, pd.Series]:
    X = pd.read_csv(data_dir / f"X_{split_name}.csv")
    y = pd.read_csv(data_dir / f"y_{split_name}.csv").iloc[:, 0]
    return X, y


def get_models() -> dict[str, object]:
    return {
        "dummy_most_frequent": DummyClassifier(strategy="most_frequent"),
        "logistic_regression": LogisticRegression(
            max_iter=2000,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            solver="liblinear",
        ),
        "linear_svc": LinearSVC(
            class_weight="balanced",
            random_state=RANDOM_STATE,
        ),
        "sgd_classifier": SGDClassifier(
            loss="log_loss",
            penalty="l2",
            max_iter=2000,
            tol=1e-3,
            class_weight="balanced",
            random_state=RANDOM_STATE,
        ),
        "decision_tree": DecisionTreeClassifier(
            max_depth=8,
            min_samples_leaf=10,
            class_weight="balanced",
            random_state=RANDOM_STATE,
        ),
        "gaussian_nb": GaussianNB(),
        "logistic_regression_l1": LogisticRegression(
            max_iter=2000,
            class_weight="balanced",
            random_state=RANDOM_STATE,
            solver="liblinear",
            penalty="l1",
        ),
    }


def get_scores(model, X: pd.DataFrame) -> pd.Series | None:
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

    if y_score is not None:
        metrics["roc_auc"] = float(roc_auc_score(y, y_score))
    else:
        metrics["roc_auc"] = None

    return metrics


def main() -> None:
    data_dir = DATA_DIR
    output_dir = OUTPUT_DIR
    models_dir = output_dir / "models"
    output_dir.mkdir(parents=True, exist_ok=True)
    models_dir.mkdir(parents=True, exist_ok=True)

    X_train, y_train = load_split(data_dir, "train")
    X_val, y_val = load_split(data_dir, "val")
    X_test, y_test = load_split(data_dir, "test")

    models = get_models()
    leaderboard_rows = []
    trained_models: dict[str, object] = {}

    for model_name, model in models.items():
        current_model = clone(model)
        current_model.fit(X_train, y_train)
        trained_models[model_name] = current_model

        train_metrics = evaluate_model(current_model, X_train, y_train)
        val_metrics = evaluate_model(current_model, X_val, y_val)

        leaderboard_rows.append(
            {
                "model": model_name,
                "train_accuracy": train_metrics["accuracy"],
                "train_f1": train_metrics["f1"],
                "val_accuracy": val_metrics["accuracy"],
                "val_precision": val_metrics["precision"],
                "val_recall": val_metrics["recall"],
                "val_f1": val_metrics["f1"],
                "val_roc_auc": val_metrics["roc_auc"],
            }
        )

        joblib.dump(current_model, models_dir / f"{model_name}.joblib")
        print(
            f"{model_name}: "
            f"val_accuracy={val_metrics['accuracy']:.4f}, "
            f"val_f1={val_metrics['f1']:.4f}, "
            f"val_roc_auc={val_metrics['roc_auc']:.4f}"
            if val_metrics["roc_auc"] is not None
            else f"{model_name}: "
            f"val_accuracy={val_metrics['accuracy']:.4f}, "
            f"val_f1={val_metrics['f1']:.4f}, "
            "val_roc_auc=N/A"
        )

    leaderboard = pd.DataFrame(leaderboard_rows)
    sort_column = f"val_{SELECTION_METRIC}"
    leaderboard = leaderboard.sort_values(
        by=[sort_column, "val_accuracy"],
        ascending=False,
        na_position="last",
    ).reset_index(drop=True)
    leaderboard.to_csv(output_dir / "leaderboard.csv", index=False)

    best_model_name = leaderboard.iloc[0]["model"]
    best_model = trained_models[best_model_name]
    best_val_metrics = evaluate_model(best_model, X_val, y_val)
    best_test_metrics = evaluate_model(best_model, X_test, y_test)

    confusion = confusion_matrix(y_test, best_model.predict(X_test))
    pd.DataFrame(
        confusion,
        index=["actual_0", "actual_1"],
        columns=["pred_0", "pred_1"],
    ).to_csv(output_dir / f"{best_model_name}_test_confusion_matrix.csv")

    test_predictions = pd.DataFrame(
        {
            "y_true": y_test.reset_index(drop=True),
            "y_pred": best_model.predict(X_test),
        }
    )
    y_test_score = get_scores(best_model, X_test)
    if y_test_score is not None:
        test_predictions["score"] = y_test_score
    test_predictions.to_csv(
        output_dir / f"{best_model_name}_test_predictions.csv",
        index=False,
    )

    joblib.dump(best_model, output_dir / "best_model.joblib")

    summary = {
        "best_model": best_model_name,
        "selection_metric": SELECTION_METRIC,
        "validation_metrics": best_val_metrics,
        "test_metrics": best_test_metrics,
        "train_rows": int(len(X_train)),
        "validation_rows": int(len(X_val)),
        "test_rows": int(len(X_test)),
        "n_features": int(X_train.shape[1]),
    }
    with open(output_dir / "best_model_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print("\nLeaderboard:")
    print(leaderboard.to_string(index=False))
    print(f"\nBest model: {best_model_name}")
    print("Test metrics:")
    for metric_name, metric_value in best_test_metrics.items():
        if metric_value is None:
            print(f"  {metric_name}: N/A")
        else:
            print(f"  {metric_name}: {metric_value:.4f}")


if __name__ == "__main__":
    main()
