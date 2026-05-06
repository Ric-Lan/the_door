# Static Prototype

This is the Phase UI-0 static prototype for the local version viewer.

## Run

From the repository root:

```bash
python -m http.server 8765
```

Then open:

```text
http://127.0.0.1:8765/docs/frontend-local-version-viewer/prototype/
```

The prototype reads only local files from `prototype/data/`.

## Data

| File | Type | Notes |
|---|---|---|
| `data/self-analysis-view-model.json` | Real fixture | Rebuilt from `docs/self-analysis-l1-output.json` using `the_door.core.ui.view_model.export_l1_view_model()` |
| `data/mock-update-report.json` | Mock fixture | Hand-written mock only for testing diff UI behavior |
| `data/mock-update-view-model.json` | Mock view model | Rebuilt from `mock-update-report.json` using `export_update_report_view_model()` |

The mock update data must not be used as evidence of a real The Door analysis.
