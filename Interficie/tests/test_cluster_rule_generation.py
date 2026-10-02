from __future__ import annotations

import unittest
from pathlib import Path

import yaml


RULES_PATH = Path(__file__).resolve().parents[1] / "reglas_negocio_idss_experto.yaml"


class ClusterRuleGenerationTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.raw_rules = RULES_PATH.read_text(encoding="utf-8")
        cls.rules = yaml.safe_load(cls.raw_rules)

    def test_yaml_only_contains_cluster_rule_sources(self) -> None:
        self.assertIn("cluster_profiles", self.rules)
        self.assertEqual(self.rules.get("reglas_globales"), [])
        self.assertNotIn("condiciones_extra", self.raw_rules)
        self.assertNotIn("criterios_generales", self.raw_rules)
        self.assertNotIn("boxplot", self.raw_rules.lower())
        self.assertNotIn("shap", self.raw_rules.lower())

    def test_every_cluster_profile_has_actions_by_risk(self) -> None:
        cluster_profiles = self.rules["cluster_profiles"]
        profiles = self.rules["perfiles"]
        cluster_names = {profile["nombre"] for profile in cluster_profiles.values()}

        self.assertTrue(cluster_names.issubset(set(profiles)))
        for profile_name in cluster_names:
            profile_rules = profiles[profile_name]
            for risk_level in ("BAJO", "MEDIO", "ALTO", "CRITICO"):
                with self.subTest(profile=profile_name, risk=risk_level):
                    self.assertIn(risk_level, profile_rules)
                    self.assertTrue(profile_rules[risk_level].get("acciones"))


if __name__ == "__main__":
    unittest.main()
