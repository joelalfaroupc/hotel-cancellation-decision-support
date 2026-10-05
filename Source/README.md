# Analysis and training

This directory restores the team’s final academic delivery. Notebook outputs and recorded results are historical; they were not regenerated for this restoration. Input/output paths were adapted to this public layout.

From the repository root, in the activated Python environment:

```bash
python -m pip install -r Source/requirements.txt
jupyter lab Source
python Source/train_model.py
python Source/train_model_cv.py
```

Open notebooks from the repository root or `Source/`. `EDA.ipynb` explores `Data/dataset_5000.csv`; `preprocessament.ipynb` produces fresh splits under `runs/dades_preprocessades_ml/` and clustering inputs under `runs/dades_preprocessades_clustering/`. The clustering notebook reads the archived clustering input and writes `runs/hotel_clustering_output.csv`.

The trainers use the archived **65-feature** splits in `Data/dades_preprocessades_ml/`. Baseline and cross-validation outputs go to `runs/baseline/` and `runs/cross_validation/`, preserving the original artifacts in `Models/`. To use newly generated preprocessing results, explicitly change `DATA_DIR` to that run’s directory in the trainer before running it. Cross-validation also generates SHAP artifacts and can take several minutes.

The source delivery contains a reproducibility inconsistency: the archived baseline/final summaries and final model record **63 features**, while the supplied splits and preprocessor use **65**. The archived model expects numerical `num__arrival_date_year`; the supplied splits instead encode that year as three categorical columns. These data cannot be passed directly to the archived 63-feature model. Rerunning training on the supplied splits creates a new 65-feature result and does not reproduce those historical 63-feature metrics.

The dashboard uses a separate **65-feature** snapshot in `Interficie/model_artifacts/`. The archived pipeline/model and dashboard model are distinct; their results must not be combined. Neither full notebook execution nor training was rerun during restoration. Dependencies remain unpinned; installing current versions may change results or serialized-artifact compatibility.
