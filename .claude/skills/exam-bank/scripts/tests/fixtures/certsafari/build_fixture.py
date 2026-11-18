"""Regenerates practice-questions.html, invented questions in the live CertSafari markup shape."""

import pathlib


def art(label, num, stem, opts, answer_html, expl, extra=""):
    lis = "".join(
        f'<li class="flex gap-2 text-sm text-foreground"><span class="font-medium text-muted-foreground">'
        f'{l}<!-- -->.</span><span>{t}</span></li>' for l, t in opts)
    ex = "".join(
        f'<li class="text-muted-foreground"><span class="font-medium text-foreground">{l}<!-- -->.</span> '
        f'<!-- -->{t}</li>' for l, t in expl)
    det = (f'<details class="mt-4 group"><summary class="cursor-pointer">Show answer &amp; explanation</summary>'
           f'<div class="mt-3 rounded-md border p-4 text-sm">{answer_html}<ul class="mt-3 space-y-2">{ex}</ul>'
           f'</div></details>') if answer_html is not None else ""
    return (f'<article class="rounded-lg border p-5"><p class="mb-2 text-xs font-medium uppercase">{label}</p>'
            f'<h3 class="text-base font-medium"><span class="text-muted-foreground mr-1.5">{num}<!-- -->.</span>'
            f'{stem}{extra}</h3><ol class="mt-3 space-y-1.5">{lis}</ol>{det}</article>')


dash = '<span class="font-normal text-muted-foreground"> � <!-- -->{}</span></p>'


def one(letter, text):
    return '<p class="font-medium">Correct answer<!-- -->: <!-- -->' + letter + dash.format(text)


two = ('<p class="font-medium">Correct answer<!-- -->s<!-- -->: <!-- -->A, C'
       + dash.format("Train on Spot VMs with checkpoints; Cache the preprocessed dataset in Cloud Storage"))
arts = [
    art("Subdomain 1.1: Choosing managed training tools.", 1,
        "A team logs click data to a table named <code>web_clicks</code> and wants churn predictions "
        "without writing model code. What should they use?",
        [("A", "A custom training job on GPUs"), ("B", "BigQuery ML with a logistic regression model"),
         ("C", "A self-managed Kubeflow cluster")], one("B", "BigQuery ML with a logistic regression model"),
        [("A", "Incorrect. Custom training adds code the team wants to avoid."),
         ("B", "Correct. BigQuery ML trains in SQL where the data already lives."),
         ("C", "Incorrect. Running Kubeflow yourself adds upkeep.")]),
    art("Subdomain 1.2: Tuning training cost.", 2,
        "A nightly training run on Vertex AI costs too much and finishes late. "
        "Which two changes cut both cost and run time? (Select two)",
        [("A", "Train on Spot VMs with checkpoints"), ("B", "Double the number of epochs"),
         ("C", "Cache the preprocessed dataset in Cloud Storage"), ("D", "Move training to a larger always-on VM"),
         ("E", "Export the model as a CSV file")], two,
        [("A", "Correct. Spot VMs cost less, and checkpoints survive preemption."),
         ("B", "Incorrect. More epochs make the run longer."),
         ("C", "Correct. A cached dataset skips the slow preprocessing step."),
         ("D", "Incorrect. An always-on VM bills between runs."),
         ("E", "Incorrect. A CSV export does not change training.")],
        '<span class="ml-1.5 text-sm font-normal text-muted-foreground">(Select <!-- -->2<!-- -->)</span>'),
    art("2.1: Watching models for drift.", 3,
        "Prediction quality falls a month after launch while traffic stays flat. What should you check first?",
        [("A", "The serving region"), ("B", "Feature drift against the training data")],
        one("B", "Feature drift against the training data"),
        [("B", "Correct. Drift explains a quiet drop in quality.")]),
    art("Subdomain 3.1: Reading pipeline diagrams.", 4,
        'The diagram shows a training pipeline.<img src="/diagram.png" alt="diagram"> Which step is missing?',
        [("A", "Model evaluation"), ("B", "Data validation")], one("B", "Data validation"),
        [("A", "Incorrect. Evaluation is drawn."), ("B", "Correct. Validation is absent.")]),
    art("Subdomain 3.1: Reading pipeline diagrams.", 5,
        "Which storage class suits a training archive read once a year?",
        [("A", "Standard"), ("B", "Nearline"), ("C", "Coldline"), ("D", "Archive"), ("E", "Regional"),
         ("F", "Dual-region"), ("G", "Multi-region")], one("D", "Archive"), []),
    art("Subdomain 3.2: Serving online predictions.", 6,
        "An endpoint must answer in under 100 ms. Which serving setup fits?",
        [("A", "Batch prediction jobs"), ("B", "An online endpoint with autoscaling")], None, []),
]
html = ('<!DOCTYPE html><html><head><title>Sample practice questions</title></head><body><main>'
        '<section class="mt-10"><h2>Domain 1: Sample ML engineering domain</h2><div class="mt-4 space-y-4">'
        + "".join(arts) + '</div></section></main></body></html>')
(pathlib.Path(__file__).parent / "practice-questions.html").write_text(html, encoding="utf-8")
