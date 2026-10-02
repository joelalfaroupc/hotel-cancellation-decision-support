from __future__ import annotations

import sys
import unittest
from pathlib import Path

import pandas as pd


INTERFICIE_DIR = Path(__file__).resolve().parents[1]
REPO_ROOT = INTERFICIE_DIR.parent
sys.path.insert(0, str(INTERFICIE_DIR))

import generate_dashboard_data  # noqa: E402
import idss_engine  # noqa: E402


class FakeModel:
    feature_names_in_ = [
        "num__lead_time",
        "cat__arrival_date_year_2016",
        "cat__arrival_date_year_2017",
    ]


class InterficieReproducibilityTest(unittest.TestCase):
    def test_default_artifact_paths_are_inside_interficie(self) -> None:
        expected_model = INTERFICIE_DIR / "model_artifacts" / "best_model.joblib"
        expected_rules = INTERFICIE_DIR / "reglas_negocio_idss_experto.yaml"
        expected_clustering = INTERFICIE_DIR / "hotel_clustering_output.csv"
        expected_original = INTERFICIE_DIR / "dataset_5000.csv"

        self.assertEqual(idss_engine.MODEL_PATH, expected_model)
        self.assertEqual(idss_engine.RULES_PATH, expected_rules)
        self.assertEqual(idss_engine.CLUSTERING_PATH, expected_clustering)
        self.assertEqual(idss_engine.ORIGINAL_PATH, expected_original)

    def test_generate_dashboard_target_is_local_dashboard_data(self) -> None:
        self.assertEqual(generate_dashboard_data.TARGET, INTERFICIE_DIR / "dashboard_data.js")

    def test_metadata_paths_are_interficie_relative_strings(self) -> None:
        self.assertEqual(
            generate_dashboard_data.display_path(idss_engine.MODEL_PATH),
            "Interficie/model_artifacts/best_model.joblib",
        )

    def test_arrival_date_year_is_categorical_for_current_ml_pipeline(self) -> None:
        self.assertNotIn("arrival_date_year", idss_engine.NUMERIC_FEATURES)
        self.assertIn("arrival_date_year", idss_engine.CATEGORICAL_FEATURES)

        raw = pd.DataFrame(
            [
                {
                    "lead_time": 10,
                    "arrival_date_year": 2017,
                }
            ]
        )
        reference = pd.DataFrame(
            [
                {
                    "lead_time": 5,
                    "arrival_date_year": 2016,
                },
                {
                    "lead_time": 15,
                    "arrival_date_year": 2017,
                },
            ]
        )

        matrix = idss_engine.build_model_matrix(raw, FakeModel(), reference)

        self.assertEqual(matrix.loc[0, "cat__arrival_date_year_2016"], 0)
        self.assertEqual(matrix.loc[0, "cat__arrival_date_year_2017"], 1)


if __name__ == "__main__":
    unittest.main()
