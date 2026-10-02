import json
import csv
from pathlib import Path

base = Path("/home/blanca/gia_3/PAID")

files = [
    "dataset_5000.csv",
    "clustering_dataset.csv",
    "hotel_clustering_output.csv",
    "idss_predicciones_20260502_1215.csv",
    "idss_alertas_20260502_1215.csv",
    "idss_alto_riesgo_20260502_1215.csv",
    "idss_recommendations_output.csv",
]

for f in files:
    with (base / f).open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        rows = [row for _, row in zip(range(3), reader)]
        print("\nFILE", f)
        print(reader.fieldnames)
        for row in rows:
            print(row)

nb = json.loads((base / "idss_hotelero.ipynb").read_text(encoding="utf-8"))
print("\nNOTEBOOK cells", len(nb.get("cells", [])))
for i, c in enumerate(nb.get("cells", [])[:14]):
    src = "".join(c.get("source", []))
    if src.strip():
        print("\nCELL", i, c.get("cell_type"))
        print(src[:1200])
