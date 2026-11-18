# Demo bank review sheet

Generated from `docs/demo/demo-bank.csv`. Edit questions in `scripts/build_demo_bank.py`. Answers checked against Google docs on 2026-11-18, see ticket 02 comments.

1. **1.1** · answer **B**  
   A retail analytics team keeps three years of customer activity in BigQuery. The analysts know SQL but not Python. They need a churn classifier this week, and the data must not leave BigQuery. What should they do?
   - A) Export the tables to Cloud Storage and train a custom TensorFlow model in a notebook.
   - B) Train a logistic regression model with CREATE MODEL in BigQuery ML.
   - C) Copy the data into Cloud SQL with Dataflow and train there.
   - D) Train a k-means model in BigQuery ML.
2. **1.1** · answer **B**  
   You must forecast daily sales for 400 stores in BigQuery ML. Sales show weekly seasonality and holiday peaks. Which model type fits best?
   - A) linear_reg on the date as a numeric feature.
   - B) ARIMA_PLUS, with the store column as time_series_id_col.
   - C) kmeans on the sales column.
   - D) matrix_factorization on store and date.
3. **1.2** · answer **B**  
   An accounts team receives 5,000 scanned supplier invoices a month. They need the supplier name, due date and total as structured fields. No one on the team builds ML models. What should you use?
   - A) Cloud Vision label detection.
   - B) The Document AI invoice parser.
   - C) A custom CNN trained on labeled invoice images.
   - D) Speech-to-Text on a voice reading of each invoice.
4. **2.1** · answer **B**  
   A linear model uses annual income as a feature. Income is heavily right-skewed, with a few very large values. What is the best preprocessing step?
   - A) One-hot encode income.
   - B) Apply a log transform, then standardize.
   - C) Drop the income feature.
   - D) Replace income with random noise of the same mean.
5. **2.1** · answer **A,B**  
   A neural recommendation model has a product_id feature with 120,000 distinct values. Which two approaches handle it well? (Choose two.)
   - A) Learn an embedding for each product_id.
   - B) Hash product_id into a fixed number of buckets.
   - C) One-hot encode product_id into 120,000 columns.
   - D) Cast product_id to an integer and feed it as a numeric value.
6. **2.1** · answer **B**  
   A churn model scores 99% accuracy on validation but performs poorly in production. One feature, refund_issued_date, is only filled in after a customer has already left. What is the most likely fix?
   - A) Use a larger model.
   - B) Remove features that are not known at prediction time.
   - C) Train for more epochs.
   - D) Make the validation set larger.
7. **2.2** · answer **A**  
   Two data scientists run the same notebook and get different results, because their environments have different library versions. What is the most reliable fix?
   - A) Run the notebook from a custom container image with pinned library versions.
   - B) Restart the kernel before each run.
   - C) Use a larger machine type.
   - D) Clear all cell outputs before committing.
8. **2.3** · answer **A,B**  
   Your team must be able to reproduce any past training run exactly. Which two items must you record for each run? (Choose two.)
   - A) The code version, such as the git commit.
   - B) The exact dataset version or snapshot used.
   - C) Only the final evaluation metric.
   - D) The hostname of the training machine.
9. **3.1** · answer **B**  
   A field-inspection app must classify photos on phones with no network, in under 50 ms. Which approach fits?
   - A) A large ensemble on a GPU-backed online endpoint.
   - B) A compact model, such as a quantized MobileNet, running on the device.
   - C) A nightly batch prediction job.
   - D) A call to a hosted foundation model API.
10. **3.2** · answer **B**  
   Training loss keeps falling, but validation loss starts rising after epoch 5. What should you do?
   - A) Raise the learning rate.
   - B) Add early stopping and regularization, such as dropout or L2.
   - C) Remove the validation set to train on more data.
   - D) Train for many more epochs.
11. **3.2** · answer **A,B**  
   In a fraud dataset, only 0.5% of rows are fraud. The model predicts 'not fraud' for every row. Which two steps help? (Choose two.)
   - A) Use class weights so that errors on fraud cost more.
   - B) Oversample fraud rows in the training split only.
   - C) Oversample fraud rows before the train and test split.
   - D) Drop the fraud rows as outliers.
12. **3.3** · answer **A**  
   You train a large transformer in JAX. It is dominated by dense matrix multiplications, and training will run for weeks. Cost per unit of performance matters most. Which hardware fits best?
   - A) Cloud TPUs.
   - B) A pool of general-purpose CPU VMs.
   - C) A single small inference GPU.
   - D) Cloud Run functions.
13. **3.3** · answer **B** · **Uncertain**  
   GPU utilization stays near 30% during training. Profiling shows the data loader is the bottleneck. What should you do first?
   - A) Move to a larger GPU.
   - B) Parallelize and prefetch the input pipeline, and read from sharded TFRecord files.
   - C) Reduce the batch size to 1.
   - D) Add more layers to the model.
14. **4.1** · answer **B**  
   Each night you must score 200 million rows stored in BigQuery. No one waits for the results until morning. Which serving approach fits?
   - A) An online endpoint called once per row.
   - B) A batch prediction job that reads from BigQuery and writes the results back.
   - C) A function that scores each row as it is inserted.
   - D) A streaming Dataflow job with a model on every worker.
15. **4.1** · answer **B**  
   Online predictions are worse than offline evaluation. You find that the serving code reimplements feature scaling slightly differently from training. What is the best long-term fix?
   - A) Rewrite the serving code more carefully to match training.
   - B) Put the preprocessing inside the exported model, for example with Keras preprocessing layers or tf.Transform.
   - C) Skip preprocessing at serving time.
   - D) Log the raw inputs and compare them weekly.
16. **4.2** · answer **A**  
   An online prediction endpoint gets 10 times its normal traffic every day at lunchtime, and latency breaks the target. What should you change?
   - A) Raise the minimum replica count, and set a maximum above it so the endpoint autoscales on utilization.
   - B) Move to one very large replica.
   - C) Switch to nightly batch prediction.
   - D) Lower the client timeout.
17. **4.2** · answer **B**  
   You trained a new model version and want to release it with low risk. What should you do?
   - A) Replace the current model in place.
   - B) Deploy it to the same endpoint, send it 10% of traffic, then shift more as its metrics hold.
   - C) Ask users to choose the version they prefer.
   - D) Undeploy the old model first, then deploy the new one.
18. **4.2** · answer **A** · **Uncertain**  
   A large model is served on a GPU endpoint, but steady traffic is only about five requests per minute. You need responses within 300 ms. How can you cut serving cost the most?
   - A) Distill or quantize the model so that it serves on a CPU machine type within the latency target.
   - B) Switch to batch prediction once a day.
   - C) Add a second GPU replica for redundancy.
   - D) Raise the autoscaling target to 95% utilization.
19. **5.1** · answer **B**  
   Your preprocessing, training and evaluation steps run by hand from notebooks. You need repeatable runs and a lineage of the artifacts each step produced. What should you do?
   - A) Schedule the notebooks with cron on a VM.
   - B) Define the steps as Kubeflow Pipelines components and run them on a managed pipelines service.
   - C) Keep running the notebooks by hand, but write down each run in a document.
   - D) Run a single script from Cloud Shell.
20. **5.2** · answer **B**  
   You want retraining to start when the serving feature distribution drifts past a threshold, not on a fixed calendar. What should you build?
   - A) Retrain every hour, whatever the data shows.
   - B) A monitoring alert that publishes to Pub/Sub, which triggers a pipeline run.
   - C) A weekly email asking an engineer to check the charts.
   - D) Never retrain, and keep the first model forever.
21. **5.2** · answer **A**  
   An automated pipeline retrains a model every week. Last week, a worse model reached production. What should you add?
   - A) An evaluation step that deploys the new model only if it beats the current model on a fixed holdout set.
   - B) Longer training on each run.
   - C) Deletion of the previous model after each run.
   - D) Skip evaluation to save time.
22. **6.1** · answer **B**  
   Support chat transcripts used to fine-tune a model contain names, phone numbers and card numbers. What should you do before training?
   - A) Train on the raw text and restrict who can access the model.
   - B) De-identify the transcripts with Sensitive Data Protection.
   - C) Remove every transcript that has a number in it.
   - D) Encrypt the training files at rest.
23. **6.1** · answer **B**  
   A loan approval model has high overall accuracy. You must check whether it treats applicant groups unfairly. What should you do?
   - A) Rely on the overall accuracy number.
   - B) Compute evaluation metrics separately for each relevant group and compare them.
   - C) Remove the group attribute and treat the model as fair.
   - D) Retrain with a different random seed.
24. **6.2** · answer **B**  
   Production accuracy has dropped over two months. Labels arrive with a long delay. How can you detect the problem early?
   - A) Wait for the labels, then recompute accuracy.
   - B) Monitor serving features for skew from the training data and for drift over time, and alert past a threshold.
   - C) Retrain on the original training data.
   - D) Turn off logging to reduce latency.
25. **6.2** · answer **B**  
   A customer asks why the model rejected their application. What helps you explain that single prediction?
   - A) Global feature importance from the training run.
   - B) Per-prediction feature attributions, such as SHAP or integrated gradients.
   - C) The model's accuracy on the test set.
   - D) The model's architecture diagram.
