from __future__ import annotations

import json
import math
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
import yaml
from sklearn.preprocessing import StandardScaler


INTERFICIE_DIR = Path(__file__).resolve().parent
REPO_ROOT = INTERFICIE_DIR.parent
MODEL_ARTIFACTS_DIR = INTERFICIE_DIR / "model_artifacts"
MODEL_PATH = MODEL_ARTIFACTS_DIR / "best_model.joblib"
RULES_PATH = INTERFICIE_DIR / "reglas_negocio_idss_experto.yaml"
CLUSTERING_PATH = INTERFICIE_DIR / "hotel_clustering_output.csv"
ORIGINAL_PATH = INTERFICIE_DIR / "dataset_5000.csv"

NUMERIC_FEATURES = [
    "lead_time",
    "arrival_date_week_number",
    "arrival_date_day_of_month",
    "previous_cancellations",
    "previous_bookings_not_canceled",
    "adr",
    "required_car_parking_spaces",
    "total_of_special_requests",
    "total_nights",
    "total_guests",
    "adr_per_guest",
]

BIN_FEATURES = ["is_repeated_guest", "has_agent", "has_company", "is_family_booking"]

CATEGORICAL_FEATURES = [
    "hotel",
    "arrival_date_year",
    "arrival_date_month",
    "gender_account",
    "meal",
    "country_risk",
    "market_segment",
    "distribution_channel",
    "reserved_room_type",
    "customer_type",
]

CLUSTER_NUM_FEATURES = [
    "lead_time",
    "total_nights",
    "total_guests",
    "adr_per_guest",
    "total_of_special_requests",
    "is_family_booking",
    "previous_cancellations",
    "has_agent",
    "is_repeated_guest",
]

MEAL_MAP = {"Undefined": 0, "SC": 1, "BB": 2, "HB": 3, "FB": 4}
SEGMENT_MAP = {
    "Groups": 0,
    "Corporate": 1,
    "Offline TA/TO": 2,
    "Direct": 3,
    "Online TA": 4,
    "Aviation": 2,
    "Complementary": 3,
}
CTYPE_MAP = {"Contract": 0, "Group": 1, "Transient-Party": 2, "Transient": 3}
RISK_MAP = {"Low": 0, "Medium": 1, "High": 2}

CLUSTER_FEATURES = CLUSTER_NUM_FEATURES + [
    "is_resort",
    "meal_enc",
    "segment_enc",
    "ctype_enc",
    "risk_enc",
    "spend_total",
    "booking_complexity",
]

PROFILE_BY_CLUSTER = {
    0: "Planificador Anticipado",
    1: "Reserva de Ultima Hora",
    2: "Viajero Premium",
    3: "Turista Familiar",
    4: "Viajero Estandar",
    5: "Corporativo Fiel",
}

RISK_WEIGHT = {"CRITICO": 4, "ALTO": 3, "MEDIO": 2, "BAJO": 1}

DEFAULT_THRESHOLDS = {"BAJO": 0.30, "MEDIO": 0.55, "ALTO": 0.55, "CRITICO": 0.85}

PROFILE_OBJECTIVES = {
    "Planificador Anticipado": "reducir incertidumbre con seguimiento escalonado y facilitar cambios antes que cancelaciones",
    "Reserva de Ultima Hora": "confirmar llegada y proteger inventario con acciones rapidas de bajo coste",
    "Viajero Premium": "retener revenue alto con trato personalizado y beneficios de valor anadido",
    "Turista Familiar": "resolver dudas logisticas y asegurar que la estancia encaja con las necesidades del grupo",
    "Viajero Estandar": "automatizar confirmaciones y escalar solo cuando el riesgo justifica esfuerzo humano",
    "Corporativo Fiel": "proteger la relacion comercial y validar cambios de patron con el contacto corporativo",
}


def as_int(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(float(value))
    except (TypeError, ValueError):
        return default


def as_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def normalize_text(value: Any) -> str:
    text = str(value or "")
    text = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF]", "", text)
    text = unicodedata.normalize("NFKD", text)
    text = "".join(ch for ch in text if not unicodedata.combining(ch))
    text = re.sub(r"[^a-zA-Z0-9 ]+", " ", text)
    return re.sub(r"\s+", " ", text).strip().lower()


def clean_profile_name(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"[\U0001F000-\U0001FAFF\u2600-\u27BF]", "", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def mode_value(series: pd.Series) -> str:
    values = series.dropna().astype(str)
    if values.empty:
        return "N/D"
    return values.mode().iloc[0]


def numeric_summary(series: pd.Series) -> dict[str, float]:
    values = pd.to_numeric(series, errors="coerce").dropna()
    if values.empty:
        return {"media": 0.0, "mediana": 0.0}
    return {"media": round(float(values.mean()), 2), "mediana": round(float(values.median()), 2)}


def fallback_rules() -> dict[str, Any]:
    return {
        "umbrales_riesgo": DEFAULT_THRESHOLDS.copy(),
        "cluster_profiles": {str(key): {"nombre": value} for key, value in PROFILE_BY_CLUSTER.items()},
        "perfiles": {},
        "reglas_globales": [],
    }


def load_rules(rules_path: Path) -> dict[str, Any]:
    rules = yaml.safe_load(rules_path.read_text(encoding="utf-8")) or fallback_rules()
    rules.setdefault("umbrales_riesgo", DEFAULT_THRESHOLDS.copy())
    rules.setdefault("cluster_profiles", {str(key): {"nombre": value} for key, value in PROFILE_BY_CLUSTER.items()})
    rules.setdefault("perfiles", {})
    rules["reglas_globales"] = []
    return rules


def generate_cluster_profiles(clustering_df: pd.DataFrame, rules: dict[str, Any]) -> dict[str, dict[str, Any]]:
    profiles_config = rules.get("cluster_profiles", {}) or {}
    generated: dict[str, dict[str, Any]] = {}
    global_stats = {
        feature: pd.to_numeric(clustering_df.get(feature, 0), errors="coerce").fillna(0).mean()
        for feature in CLUSTER_NUM_FEATURES
        if feature in clustering_df
    }

    for cluster, group in clustering_df.groupby("cluster"):
        cluster_key = str(int(cluster))
        configured = profiles_config.get(cluster_key, {})
        name = clean_profile_name(configured.get("nombre") or PROFILE_BY_CLUSTER.get(int(cluster), "Viajero Estandar"))
        discriminants: list[str] = []
        for feature, global_mean in global_stats.items():
            cluster_mean = pd.to_numeric(group.get(feature, 0), errors="coerce").fillna(0).mean()
            diff = cluster_mean - global_mean
            if abs(diff) < max(abs(global_mean) * 0.2, 0.2):
                continue
            direction = "alto" if diff > 0 else "bajo"
            discriminants.append(f"{feature} {direction} ({cluster_mean:.2f} vs {global_mean:.2f})")

        generated[cluster_key] = {
            "cluster": int(cluster),
            "nombre": name,
            "descripcion": configured.get(
                "descripcion_datos",
                f"Perfil TLP {name} identificado por el clustering del notebook hotel_clustering.ipynb.",
            ),
            "logica_negocio": configured.get("logica_negocio", PROFILE_OBJECTIVES.get(name, "")),
            "variables_distintivas": configured.get("variables_distintivas") or discriminants[:5],
            "tamano": int(len(group)),
            "peso": round(float(len(group) / max(len(clustering_df), 1)), 4),
            "metricas": {
                "lead_time": numeric_summary(group.get("lead_time", pd.Series(dtype=float))),
                "total_nights": numeric_summary(group.get("total_nights", pd.Series(dtype=float))),
                "adr_per_guest": numeric_summary(group.get("adr_per_guest", pd.Series(dtype=float))),
                "total_guests": numeric_summary(group.get("total_guests", pd.Series(dtype=float))),
                "segmento_dominante": mode_value(group.get("market_segment", pd.Series(dtype=str))),
                "tipo_cliente_dominante": mode_value(group.get("customer_type", pd.Series(dtype=str))),
                "deposito_dominante": mode_value(group.get("deposit_type", pd.Series(dtype=str))),
            },
        }
    return generated


def add_basic_features(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    has_raw_adr = "adr" in out.columns
    defaults = {
        "children": 0,
        "babies": 0,
        "adults": 1,
        "stays_in_weekend_nights": 0,
        "stays_in_week_nights": 1,
        "adr": 0,
        "agent": np.nan,
        "company": np.nan,
        "total_of_special_requests": 0,
        "previous_cancellations": 0,
        "previous_bookings_not_canceled": 0,
        "is_repeated_guest": 0,
        "required_car_parking_spaces": 0,
        "arrival_date_year": 2016,
        "arrival_date_week_number": 26,
        "arrival_date_day_of_month": 1,
        "hotel": "City Hotel",
        "arrival_date_month": "January",
        "gender_account": "Female",
        "meal": "BB",
        "country_risk": "Medium",
        "market_segment": "Online TA",
        "distribution_channel": "TA/TO",
        "reserved_room_type": "A",
        "customer_type": "Transient",
        "deposit_type": "Unknown",
    }
    for col, value in defaults.items():
        if col not in out.columns:
            out[col] = value

    for col in [
        "children",
        "babies",
        "adults",
        "stays_in_weekend_nights",
        "stays_in_week_nights",
        "adr",
        "lead_time",
        "arrival_date_year",
        "arrival_date_week_number",
        "arrival_date_day_of_month",
        "previous_cancellations",
        "previous_bookings_not_canceled",
        "required_car_parking_spaces",
        "total_of_special_requests",
    ]:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)

    if "total_nights" not in out.columns:
        out["total_nights"] = out["stays_in_weekend_nights"] + out["stays_in_week_nights"]
    out["total_nights"] = pd.to_numeric(out["total_nights"], errors="coerce").fillna(1).clip(lower=1)

    if "total_guests" not in out.columns:
        out["total_guests"] = out["adults"] + out["children"] + out["babies"]
    out["total_guests"] = pd.to_numeric(out["total_guests"], errors="coerce").fillna(1).replace(0, 1)

    if "adr_per_guest" not in out.columns:
        out["adr_per_guest"] = out["adr"] / out["total_guests"].replace(0, 1)
    out["adr_per_guest"] = pd.to_numeric(out["adr_per_guest"], errors="coerce").fillna(0)

    if not has_raw_adr:
        out["adr"] = out["adr_per_guest"] * out["total_guests"].replace(0, 1)

    if "has_agent" not in out.columns:
        out["has_agent"] = out["agent"].notna().astype(int)
    if "has_company" not in out.columns:
        out["has_company"] = out["company"].notna().astype(int)
    if "is_family_booking" not in out.columns:
        out["is_family_booking"] = ((out["children"] > 0) | (out["babies"] > 0)).astype(int)

    if "spend_total" not in out.columns:
        out["spend_total"] = out["adr_per_guest"] * out["total_guests"] * out["total_nights"]

    out["booking_complexity"] = pd.to_numeric(out["total_of_special_requests"], errors="coerce").fillna(0) + pd.to_numeric(
        out["is_family_booking"], errors="coerce"
    ).fillna(0)

    for col in BIN_FEATURES:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0).astype(int)
    for col in CATEGORICAL_FEATURES:
        out[col] = out[col].fillna("Unknown").astype(str)
    out["deposit_type"] = out["deposit_type"].fillna("Unknown").astype(str)

    return out


def build_model_matrix(raw_df: pd.DataFrame, model: Any, reference_df: pd.DataFrame) -> pd.DataFrame:
    df = add_basic_features(raw_df)
    reference = add_basic_features(reference_df)
    expected = [str(col) for col in model.feature_names_in_]
    matrix = pd.DataFrame(index=df.index)

    for feature in expected:
        if feature.startswith("num__"):
            col = feature.replace("num__", "", 1)
            values = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0)
            ref_values = pd.to_numeric(reference.get(col, 0), errors="coerce").fillna(0)
            std = ref_values.std(ddof=0) or 1.0
            matrix[feature] = (values - ref_values.mean()) / std
        elif feature.startswith("bin__"):
            col = feature.replace("bin__", "", 1)
            matrix[feature] = pd.to_numeric(df.get(col, 0), errors="coerce").fillna(0).astype(int)
        elif feature.startswith("cat__"):
            raw = feature.replace("cat__", "", 1)
            match_col = None
            for col in sorted(CATEGORICAL_FEATURES, key=len, reverse=True):
                if raw.startswith(col + "_"):
                    match_col = col
                    category = raw[len(col) + 1 :]
                    break
            matrix[feature] = (df.get(match_col, "").astype(str) == category).astype(int) if match_col else 0
        else:
            matrix[feature] = 0
    return matrix[expected]


def build_cluster_features(raw_df: pd.DataFrame) -> pd.DataFrame:
    out = add_basic_features(raw_df)
    out["is_resort"] = (out["hotel"].astype(str) == "Resort Hotel").astype(int)
    out["meal_enc"] = out["meal"].map(MEAL_MAP).fillna(1)
    out["segment_enc"] = out["market_segment"].map(SEGMENT_MAP).fillna(2)
    out["ctype_enc"] = out["customer_type"].map(CTYPE_MAP).fillna(3)
    out["risk_enc"] = out["country_risk"].map(RISK_MAP).fillna(1)
    for col in CLUSTER_FEATURES:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0)
    return out[CLUSTER_FEATURES]


@dataclass
class IdssArtifacts:
    model: Any
    rules: dict[str, Any]
    clustering_df: pd.DataFrame
    original_df: pd.DataFrame
    scaler: StandardScaler
    centroids: pd.DataFrame
    cluster_profiles: dict[str, dict[str, Any]]


class IDSSEngine:
    def __init__(
        self,
        model_path: Path = MODEL_PATH,
        rules_path: Path = RULES_PATH,
        clustering_path: Path = CLUSTERING_PATH,
        original_path: Path = ORIGINAL_PATH,
    ) -> None:
        model = joblib.load(model_path)
        rules = load_rules(rules_path)
        clustering_df = pd.read_csv(clustering_path)
        original_df = pd.read_csv(original_path)
        if "deposit_type" not in clustering_df.columns and "deposit_type" in original_df.columns:
            original_clean = add_basic_features(original_df).drop_duplicates().reset_index(drop=True)
            if len(clustering_df) == len(original_clean):
                clustering_df["deposit_type"] = original_clean["deposit_type"].values
        clustering_df = add_basic_features(clustering_df)

        features = build_cluster_features(clustering_df)
        scaler = StandardScaler()
        scaled = pd.DataFrame(scaler.fit_transform(features), columns=CLUSTER_FEATURES)
        scaled["cluster"] = clustering_df["cluster"].astype(int).values
        centroids = scaled.groupby("cluster")[CLUSTER_FEATURES].mean().sort_index()
        cluster_profiles = generate_cluster_profiles(clustering_df, rules)

        self.artifacts = IdssArtifacts(model, rules, clustering_df, original_df, scaler, centroids, cluster_profiles)

    def predict_probability(self, df: pd.DataFrame) -> np.ndarray:
        matrix = build_model_matrix(df, self.artifacts.model, self.artifacts.original_df)
        return self.artifacts.model.predict_proba(matrix)[:, 1]

    def assign_profile(self, df: pd.DataFrame) -> pd.DataFrame:
        if "cluster" in df.columns:
            clusters = pd.to_numeric(df["cluster"], errors="coerce").fillna(4).astype(int).to_numpy()
        else:
            features = build_cluster_features(df)
            scaled = self.artifacts.scaler.transform(features)
            centroid_values = self.artifacts.centroids.values
            centroid_clusters = self.artifacts.centroids.index.to_numpy()
            distances = ((scaled[:, None, :] - centroid_values[None, :, :]) ** 2).sum(axis=2)
            clusters = centroid_clusters[distances.argmin(axis=1)]
        return pd.DataFrame(
            {
                "cluster": clusters,
                "profile": [self.profile_name_from_cluster(int(cluster)) for cluster in clusters],
            },
            index=df.index,
        )

    def profile_name_from_cluster(self, cluster: int) -> str:
        profile = self.artifacts.cluster_profiles.get(str(cluster), {})
        return clean_profile_name(profile.get("nombre") or PROFILE_BY_CLUSTER.get(cluster, "Viajero Estandar"))

    def cluster_profile_for(self, profile: str, context: dict[str, Any]) -> dict[str, Any]:
        cluster = as_int(context.get("cluster"), -1)
        profile_data = self.artifacts.cluster_profiles.get(str(cluster))
        if profile_data:
            return profile_data
        return {
            "cluster": cluster,
            "nombre": profile,
            "descripcion": f"Perfil TLP {profile} asignado por cercania a centroides del clustering.",
            "logica_negocio": PROFILE_OBJECTIVES.get(profile, ""),
            "variables_distintivas": [],
        }

    def risk_level(self, probability: float) -> str:
        thresholds = self.effective_thresholds()
        if probability >= thresholds["CRITICO"]:
            return "CRITICO"
        if probability >= thresholds["ALTO"]:
            return "ALTO"
        if probability >= thresholds["BAJO"]:
            return "MEDIO"
        return "BAJO"

    def effective_thresholds(self) -> dict[str, float]:
        raw = self.artifacts.rules.get("umbrales_riesgo", {})
        bajo = as_float(raw.get("BAJO", 0.30))
        alto = as_float(raw.get("ALTO", 0.55))
        critico = as_float(raw.get("CRITICO", 0.75))
        if critico <= alto:
            critico = min(0.95, alto + 0.15)
        return {"BAJO": bajo, "ALTO": alto, "CRITICO": critico}

    def safe_context(self, row: pd.Series, probability: float) -> dict[str, Any]:
        context = add_basic_features(pd.DataFrame([row.to_dict()])).iloc[0].to_dict()
        context["cancel_prob"] = float(probability)
        context["spend_total"] = as_float(context.get("spend_total"))
        return context

    def eval_condition(self, condition: str, context: dict[str, Any]) -> bool:
        allowed_globals = {"__builtins__": {}}
        allowed_locals = dict(context)
        try:
            return bool(eval(condition, allowed_globals, allowed_locals))
        except Exception:
            return False

    def actions_for(self, profile: str, risk: str, context: dict[str, Any]) -> dict[str, Any]:
        profiles = self.artifacts.rules.get("perfiles", {})
        profile_key = profiles.get(profile) and profile
        if not profile_key:
            by_norm = {normalize_text(key): key for key in profiles}
            profile_key = by_norm.get(normalize_text(profile), "Viajero Estandar")

        profile_rules = profiles.get(profile_key, {})
        risk_rules = profile_rules.get(risk) or profile_rules.get("ALTO") or {}
        channels = list(risk_rules.get("canal", []))
        actions = list(risk_rules.get("acciones", []))

        return {
            "profile": profile_key,
            "description": profile_rules.get("descripcion", ""),
            "priority": as_int(risk_rules.get("prioridad"), 3),
            "channels": channels,
            "timing": risk_rules.get("timing_dias", []),
            "actions": [action for action in actions if action],
            "global_rules": [],
        }

    def causes(self, row: pd.Series, probability: float, risk: str, profile_data: dict[str, Any] | None = None) -> list[str]:
        causes = []
        if risk == "CRITICO":
            causes.append("Probabilidad de cancelacion critica calculada por XGBoost")
        elif risk == "ALTO":
            causes.append("Probabilidad de cancelacion alta calculada por XGBoost")
        elif risk == "MEDIO":
            causes.append("Riesgo preventivo medio calculado por XGBoost")
        else:
            causes.append("Riesgo bajo, seguimiento rutinario")
        if profile_data:
            causes.append(f"Perfil TLP asignado desde el cluster {profile_data.get('cluster')}: {profile_data.get('nombre')}")
            variables = profile_data.get("variables_distintivas", []) or []
            if variables:
                causes.append("Variables distintivas del cluster: " + "; ".join(str(item) for item in variables[:3]))
        return causes

    def enrich(self, raw_df: pd.DataFrame) -> list[dict[str, Any]]:
        df = add_basic_features(raw_df)
        probs = self.predict_probability(df)
        profiles = self.assign_profile(df)
        rows = []
        for pos, (_, row) in enumerate(df.iterrows()):
            prob = float(probs[pos])
            risk = self.risk_level(prob)
            context = self.safe_context(row, prob)
            profile = profiles.iloc[pos]["profile"]
            context["cluster"] = int(profiles.iloc[pos]["cluster"])
            profile_data = self.cluster_profile_for(profile, context)
            decision = self.actions_for(profile, risk, context)
            priority = decision["priority"]
            spend = as_float(row.get("spend_total"))
            lead_time = as_int(row.get("lead_time"))
            prev_cancel = as_int(row.get("previous_cancellations"))
            urgency = RISK_WEIGHT.get(risk, 1) * 1000 + prob * 100 + spend / 100 + lead_time / 20 + prev_cancel * 25 + (4 - priority) * 15

            rows.append(
                {
                    **row.to_dict(),
                    "cluster": int(profiles.iloc[pos]["cluster"]),
                    "profile": decision["profile"],
                    "cancel_prob": round(prob, 4),
                    "risk_level": risk,
                    "priority": priority,
                    "channels": decision["channels"],
                    "timing": decision["timing"],
                    "actions": decision["actions"],
                    "global_rules": decision["global_rules"],
                    "profile_description": decision["description"],
                    "cluster_profile": profile_data,
                    "spend_total": round(spend, 2),
                    "urgency_score": round(urgency, 2),
                    "causes": self.causes(row, prob, risk, profile_data),
                    "status": "Pendiente",
                    "engine_trace": "XGBoost calcula P(cancelacion), centroides TLP asignan perfil y las reglas del clustering generan acciones.",
                }
            )
        return rows

    def export_browser_config(self) -> dict[str, Any]:
        features = build_cluster_features(self.artifacts.clustering_df)
        means = features.mean().to_dict()
        stds = features.std(ddof=0).replace(0, 1).to_dict()
        reference = add_basic_features(self.artifacts.original_df)
        model_numeric_stats = {}
        for col in NUMERIC_FEATURES:
            values = pd.to_numeric(reference.get(col, 0), errors="coerce").fillna(0)
            std = float(values.std(ddof=0) or 1.0)
            model_numeric_stats[col] = {"mean": float(values.mean()), "std": std}
        booster = self.artifacts.model.get_booster()
        rules = self.artifacts.rules
        return {
            "cluster_features": CLUSTER_FEATURES,
            "cluster_means": {key: float(value) for key, value in means.items()},
            "cluster_stds": {key: float(value) for key, value in stds.items()},
            "centroids": {
                str(int(cluster)): [float(value) for value in values]
                for cluster, values in self.artifacts.centroids.iterrows()
            },
            "profile_by_cluster": {str(key): value for key, value in PROFILE_BY_CLUSTER.items()},
            "cluster_profiles": self.artifacts.cluster_profiles,
            "thresholds": self.effective_thresholds(),
            "profiles": rules.get("perfiles", {}),
            "global_rules": [],
            "model_features": [str(col) for col in self.artifacts.model.feature_names_in_],
            "model_numeric_stats": model_numeric_stats,
            "xgboost_trees": [json.loads(tree) for tree in booster.get_dump(dump_format="json")],
        }


def to_plain_json(value: Any) -> Any:
    if isinstance(value, dict):
        return {str(key): to_plain_json(val) for key, val in value.items()}
    if isinstance(value, list):
        return [to_plain_json(item) for item in value]
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return float(value)
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


if __name__ == "__main__":
    engine = IDSSEngine()
    sample = engine.artifacts.clustering_df.head(5)
    print(json.dumps(to_plain_json(engine.enrich(sample)), ensure_ascii=False, indent=2))
