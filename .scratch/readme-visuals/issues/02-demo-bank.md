# 02: Demo bank

Spec: [0002, Demo bank](../../../docs/specs/0002-study-app.md#demo-bank). Log: RV-D2, RV-D9, RV-D25.

**What to build:** `docs/demo/demo-bank.csv` holds 25 original PMLE-style questions. A visitor can import it and practice, and every README image is captured from it.

**Blocked by:** none

**Status:** resolved

**Model tier:** heavy
**Effort:** high
**Where:** cli
**Constraints:** Write every question new. Never read or reword `exam-bank/pmle/` content or any question site. Follow the CSV contract in 0001 exactly.

- [x] 25 rows in the CSV contract columns, **Lineage** `created`
- [x] **Sections** and **Subdomains** from `templates/exams/pmle.example.yaml`, at least 5 **Subdomains** covered
- [x] A real explanation per choice
- [x] Each correct answer checked against current Google Cloud docs
- [x] 1 or 2 **Uncertain answers**
- [x] The Demo bank `section_weights` line written in this ticket's comments, for ticket 06

**Verify:**

- A test runs the Bank check on it through `makeServer` with the fake adapter, and the bank is accepted
- User: review the 25 questions before ticket 04 runs

## Comments

- 2026-11-18: `scripts/build_demo_bank.py` writes `docs/demo/demo-bank.csv`: 25 original questions, 14 Subdomains across all 6 Sections, Lineage `created`, 2 Uncertain answers (3.3 input pipeline, 4.2 serving cost). IDs via the skill's `ids.question_id`. Multi-select answers use `A,B` per the CSV contract.
- `app/tests/demo-bank.test.js`: the bank loads to `home` with no warnings under the Settings below.
- section_weights line for ticket 06: `section_weights: 1:13,2:16,3:21,4:20,5:18,6:13`. Exam name: `PMLE (demo)`.
- Product names follow the 2026 rename of Vertex AI to Gemini Enterprise Agent Platform; questions avoid renamed product names where a concept works. Waiting on user review of the 25 questions; rerun `scripts/capture_readme.py` after any edit.
- 2026-11-18, docs check: all 25 answers stand. Checked on docs.cloud.google.com only (cloud.google.com redirects there). No answer letter or question changed, so IDs are unchanged. Two explanations were fixed. Row 20 now says that Model Monitoring alerts reach Pub/Sub through a notification channel. Row 25 no longer credits Agent Platform with the attribution methods, because Vertex Explainable AI was deprecated on 2026-03-16. Uncertain stays on rows 13 (3.3, "first") and 18 (4.2, "most"), the two judgment-call wordings. Row 18's GPU-to-CPU cost case has no single doc that states it, and Scale To Zero (Preview) exists but does not fit a 300 ms target. Review-sheet Uncertain markers restored. No capture rerun: the hero uses row 1, and the changed explanations and flags do not appear in the GIFs or stills.
- Docs per row (paths under `https://docs.cloud.google.com/`):
  - 1: `bigquery/docs/reference/standard-sql/bigqueryml-syntax-create-glm` (LOGISTIC_REG)
  - 2: `.../bigqueryml-syntax-create-time-series` (TIME_SERIES_ID_COL; holidays only with HOLIDAY_REGION)
  - 3: `document-ai/docs/processors-list` (Invoice parser, pretrained: supplier_name, due_date, total_amount)
  - 4, 5: `bigquery/docs/reference/standard-sql/bigqueryml-syntax-standard-scaler`, `...-hash-bucketize`; the log transform and embeddings rest on ML fundamentals
  - 6: `vertex-ai/docs/tabular-data/bp-tabular` (target leakage)
  - 7: `vertex-ai/docs/workbench/instances/custom-container`
  - 8: `gemini-enterprise-agent-platform/machine-learning/experiments/intro-vertex-ai-experiments`, `architecture/ml-on-gcp-best-practices`
  - 9: AutoML edge export to TFLite, from the AutoML API reference only; no current product page
  - 10, 11: `create-glm` (EARLY_STOP, L2_REG, AUTO_CLASS_WEIGHTS), `bp-tabular` (class imbalance)
  - 12: `tpu/docs/intro-to-tpu` (matrix-dominated, weeks of training), `functions/quotas` (Cloud Run functions limits)
  - 13: `tpu/docs/performance-guide`, `tpu/docs/troubleshooting/trouble-tf` (prefetch, parallel TFRecord reads)
  - 14: `vertex-ai/docs/predictions/get-batch-predictions` (BigQuery in and out)
  - 15: `bigquery/docs/bigqueryml-transform`, tf.Transform (cloud.google.com/architecture page now redirects to tensorflow.org)
  - 16: `vertex-ai/docs/predictions/autoscaling` (autoscaling needs max > min)
  - 17: `vertex-ai/docs/general/deployment` (traffic split)
  - 18: `vertex-ai/docs/predictions/configure-compute` (CPU-only machine types)
  - 19: `vertex-ai/docs/pipelines/introduction` (KFP, ML Metadata lineage)
  - 20: `gemini-enterprise-agent-platform/machine-learning/model-monitoring/using-model-monitoring` (Pub/Sub channel), `architecture/mlops-continuous-delivery-and-automation-pipelines-in-machine-learning`
  - 21: same MLOps page (validate the model before promotion)
  - 22: `sensitive-data-protection/docs/deidentify-sensitive-data`
  - 23: `gemini-enterprise-agent-platform/machine-learning/evaluation/intro-evaluation-fairness`
  - 24: `vertex-ai/docs/model-monitoring/overview` (skew and drift from distributions, no labels needed)
  - 25: `vertex-ai/docs/explainable-ai/overview` (Sampled Shapley, integrated gradients, XRAI; deprecated)

## Build notes

- Modules added or removed: none
- Interface names changed: none
- New cross-module calls: none
- Docs mismatch: docs pages mix "Vertex AI" and "Agent Platform" (for example, Vertex Explainable AI and Vertex AI Inference), so the bank keeps product names out of its answers where it can
