import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from idss_engine import (
    CLUSTERING_PATH,
    MODEL_PATH,
    ORIGINAL_PATH,
    RULES_PATH,
    IDSSEngine,
    INTERFICIE_DIR,
    REPO_ROOT,
    to_plain_json,
)


TARGET = INTERFICIE_DIR / "dashboard_data.js"
RISK_ORDER = ["CRITICO", "ALTO", "MEDIO", "BAJO"]
DASHBOARD_PER_RISK = 5
TARGET_MIN_ROWS = 24


def display_path(path):
    resolved = Path(path).resolve()
    try:
        return resolved.relative_to(REPO_ROOT).as_posix()
    except ValueError:
        return resolved.as_posix()


def as_int(value, default=0):
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def as_float(value, default=0.0):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def month_to_week(month):
    return {
        "January": 2,
        "February": 7,
        "March": 11,
        "April": 15,
        "May": 19,
        "June": 24,
        "July": 28,
        "August": 32,
        "September": 36,
        "October": 41,
        "November": 45,
        "December": 49,
    }.get(str(month), 26)


def browser_row(item, idx, original):
    arrival_month = item.get("arrival_date_month", "")
    total_nights = as_int(item.get("total_nights"), 1)
    total_guests = as_int(item.get("total_guests"), 1)
    deposit_type = item.get("deposit_type") if item.get("deposit_type") != "Unknown" else original.get("deposit_type", "Unknown")
    return {
        "id": f"BK-{20260000 + idx}",
        "hotel": item.get("hotel", ""),
        "country": original.get("country", "N/D") or "N/D",
        "lead_time": as_int(item.get("lead_time")),
        "arrival": f"{as_int(item.get('arrival_date_day_of_month'), 1)} {arrival_month} {as_int(item.get('arrival_date_year'), 2016)}",
        "arrival_month": arrival_month,
        "week": as_int(item.get("arrival_date_week_number"), month_to_week(arrival_month)),
        "gender": item.get("gender_account", ""),
        "meal": item.get("meal", ""),
        "market_segment": item.get("market_segment", ""),
        "distribution_channel": item.get("distribution_channel", ""),
        "repeated_guest": as_int(item.get("is_repeated_guest")),
        "previous_cancellations": as_int(item.get("previous_cancellations")),
        "previous_bookings_not_canceled": as_int(item.get("previous_bookings_not_canceled")),
        "room_type": item.get("reserved_room_type", ""),
        "customer_type": item.get("customer_type", ""),
        "deposit_type": deposit_type,
        "special_requests": as_int(item.get("total_of_special_requests")),
        "has_agent": as_int(item.get("has_agent")),
        "has_company": as_int(item.get("has_company")),
        "total_nights": total_nights,
        "total_guests": total_guests,
        "adr_per_guest": as_float(item.get("adr_per_guest")),
        "adr": as_float(item.get("adr"), as_float(item.get("adr_per_guest")) * max(total_guests, 1)),
        "is_family_booking": as_int(item.get("is_family_booking")),
        "country_risk": item.get("country_risk", "Unknown"),
        "profile": item.get("profile", ""),
        "cluster": str(item.get("cluster", "")),
        "cancel_prob": as_float(item.get("cancel_prob")),
        "risk_level": item.get("risk_level", "BAJO"),
        "priority": as_int(item.get("priority"), 3),
        "channels": item.get("channels", []),
        "timing": item.get("timing", []),
        "actions": item.get("actions", []),
        "global_rules": item.get("global_rules", []),
        "profile_description": item.get("profile_description", ""),
        "spend_total": as_float(item.get("spend_total")),
        "urgency_score": as_float(item.get("urgency_score")),
        "causes": item.get("causes", []),
        "status": "Pendiente",
        "engine_trace": item.get("engine_trace", ""),
    }


def select_dashboard_rows(rows):
    selected = []
    selected_ids = set()
    for risk in RISK_ORDER:
        bucket = [row for row in rows if row["risk_level"] == risk]
        for row in bucket[:DASHBOARD_PER_RISK]:
            selected.append(row)
            selected_ids.add(row["id"])
    profiles = sorted({row["profile"] for row in rows})
    present_profiles = {row["profile"] for row in selected}
    for profile in profiles:
        if profile in present_profiles:
            continue
        candidate = next((row for row in rows if row["profile"] == profile and row["id"] not in selected_ids), None)
        if not candidate:
            continue
        selected.append(candidate)
        selected_ids.add(candidate["id"])
        present_profiles.add(profile)
    if len(selected) < TARGET_MIN_ROWS:
        for row in rows:
            if row["id"] in selected_ids:
                continue
            selected.append(row)
            selected_ids.add(row["id"])
            if len(selected) == TARGET_MIN_ROWS:
                break
    selected.sort(key=lambda row: (RISK_ORDER.index(row["risk_level"]), -row["urgency_score"]))
    return selected


def main():
    engine = IDSSEngine()
    clustering = engine.artifacts.clustering_df.copy()
    original = engine.artifacts.original_df.copy()
    enriched = engine.enrich(clustering)

    paired = []
    for idx, item in enumerate(enriched, start=1):
        original_row = original.iloc[idx - 1].to_dict() if idx - 1 < len(original) else {}
        paired.append(browser_row(item, idx, original_row))

    paired.sort(key=lambda row: row["urgency_score"], reverse=True)
    display_rows = select_dashboard_rows(paired)

    metadata = {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "mode": "integrated_idss_engine",
        "dashboard_rows": len(display_rows),
        "rows_per_risk": DASHBOARD_PER_RISK,
        "scored_reference_rows": len(paired),
        "model": display_path(MODEL_PATH),
        "rules": display_path(RULES_PATH),
        "clustering": display_path(CLUSTERING_PATH),
        "original": display_path(ORIGINAL_PATH),
        "pipeline": [
            "XGBoost best_model.joblib calcula la probabilidad de cancelacion.",
            "Los centroides del clustering TLP asignan cluster y perfil a cada reserva.",
            "reglas_negocio_idss_experto.yaml genera canales, timing y acciones desde el perfil TLP y el nivel de riesgo.",
            "El dashboard muestra una cartera inicial ampliada, equilibrada por riesgo y con representacion de todos los perfiles TLP.",
            "Si ALTO y CRITICO comparten umbral en YAML, el motor separa CRITICO con un corte operativo mas exigente para mantener los cuatro niveles.",
        ],
    }

    payload = (
        "window.IDSS_RESERVATIONS = "
        + json.dumps(to_plain_json(display_rows), ensure_ascii=False, indent=2)
        + ";\n\nwindow.IDSS_METADATA = "
        + json.dumps(to_plain_json(metadata), ensure_ascii=False, indent=2)
        + ";\n\nwindow.IDSS_ENGINE_CONFIG = "
        + json.dumps(to_plain_json(engine.export_browser_config()), ensure_ascii=False, indent=2)
        + ";\n"
    )
    TARGET.write_text(payload, encoding="utf-8")
    print(f"Wrote {len(display_rows)} dashboard reservations from {len(paired)} scored rows to {TARGET}")


if __name__ == "__main__":
    main()
