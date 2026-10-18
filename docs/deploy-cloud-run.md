# Deploying to Google Cloud Run

One image (`Dockerfile`), deployed several times:

| Deployment | Cloud Run type | Command | Reads | Writes |
|---|---|---|---|---|
| API | **service** | `rm-dashboard-serve` (image default) | Firestore | nothing (read-only store) |
| `rm-outlook` | **job** | `rm-dashboard-outlook` | Firestore, Vertex AI | Firestore |
| `rm-analyse` | **job** | `rm-dashboard-analyse` | Firestore, Vertex AI | Firestore |
| `rm-reconcile` | **job** | `rm-dashboard-reconcile` | Firestore, Vertex AI | Firestore |
| `rm-mandate-reconcile` | **job** | `rm-dashboard-mandate-reconcile` | Firestore, Vertex AI | Firestore |
| `rm-actions` | **job** | `rm-dashboard-actions` | Firestore, Vertex AI | Firestore |
| `rm-overview` | **job** | `rm-dashboard-overview` | Firestore, Vertex AI | Firestore |
| `rm-scenarios` | **job** | `rm-dashboard-scenarios` | Firestore, Vertex AI | Firestore |

There is no SQLite in the cloud. Source data and artifacts both live in Firestore (`RM_DATA_SOURCE` and `RM_ARTIFACT_STORE`
= `firestore:<project>`); the runners write each artifact as they produce it, and the API sees a date as soon as a runner has written to it.

**Why jobs, not services, for the runners:** a Cloud Run service must listen on `$PORT` and is cut off after at most 60 minutes per
request; a runner is a command that runs to completion and exits, which is what a job is, and a job task can run up to 168 hours. You
start a job from the console (**Execute**) or with `gcloud run jobs execute`. The API is the only service.

## Variables used below

```sh
export PROJECT=my-project REGION=europe-west1 AS_OF=2026-08-26
export SA=rm-dashboard@$PROJECT_ID.iam.gserviceaccount.com
export IMAGE=$REGION-docker.pkg.dev/$PROJECT_ID/rm-dashboard/app:latest
gcloud config set project $PROJECT_ID
```

## 1. One-time setup

```sh
gcloud services enable run.googleapis.com firestore.googleapis.com aiplatform.googleapis.com \
  artifactregistry.googleapis.com cloudbuild.googleapis.com

gcloud firestore databases create --location=$REGION            # Native mode, "(default)" database
gcloud artifacts repositories create rm-dashboard --repository-format=docker --location=$REGION

gcloud iam service-accounts create rm-dashboard
gcloud projects add-iam-policy-binding $PROJECT_ID --member=serviceAccount:$SA --role=roles/datastore.user      # Firestore read/write
gcloud projects add-iam-policy-binding $PROJECT_ID --member=serviceAccount:$SA --role=roles/aiplatform.user     # Vertex AI (Gemini)
```

## 2. Build the image

```sh
gcloud builds submit --tag $IMAGE .
```

The image defaults to `RM_MODEL_PROVIDER=vertex` and `RM_MODEL_NAME=gemini-3.8-flash`. It contains neither `sample/` nor `rm.db`.

## 3. Load the source data into Firestore (once, from your machine)

Needs the `firestore` extra and your own credentials (`gcloud auth application-default login`):

```sh
uv sync --extra firestore
uv run rm-dashboard-load source --to firestore:$PROJECT_ID --replace
```

Re-run only when the dataset files change. (`rm-dashboard-load artifacts --from sqlite:... --to firestore:$PROJECT_ID` still copies an
existing SQLite store or `reports/` folder into Firestore, for migrating old runs; it is not part of the normal flow.)

## 4. Create the runner jobs

Same settings for all of them; only the name and command change.

```sh
COMMON_ENV="RM_DATA_SOURCE=firestore:$PROJECT_ID/rm-dashboard,RM_ARTIFACT_STORE=firestore:$PROJECT_ID/rm-dashboard,RM_MAX_CONCURRENCY=2,GOOGLE_CLOUD_PROJECT=$PROJECT_ID"

for stage in outlook analyse reconcile mandate-reconcile actions overview scenarios; do
  gcloud run jobs create rm-$stage \
    --image $IMAGE --region $REGION --service-account $SA \
    --command rm-dashboard-$stage --args="--as-of,$AS_OF" \
    --tasks 1 --max-retries 1 --task-timeout 1h \
    --cpu 1 --memory 2Gi \
    --set-env-vars "$COMMON_ENV"
done
```

What keeps a run from stopping before it is finished:

- **`--task-timeout 1h`** (maximum 168h). The default is 10 minutes, and that is what ends a run early. One client with `gemini-3.8-flash`
  took about 8 minutes, so size it from a test run.
- **`--max-retries 1`**. A retry starts the command again; it is safe because every artifact is written under a fixed address and a
  re-run replaces it. Scenarios resume where they stopped, since finished results are already in Firestore. Use `0` to avoid paying
  twice for model calls when a stage fails for a reason a retry cannot fix.
- **`--tasks 1`**: a runner parallelises inside the task with `RM_MAX_CONCURRENCY` (clients, instruments or scenario units at once). Raise it
  if Vertex quota allows; 429 errors show as `outcome=error` log records.

Per-stage options go in `--args`, for example `--args="--as-of,$AS_OF,--clients,CL-0001"` or `--args="--as-of,$AS_OF,--force"` (outlook, scenarios).

## 5. Run them, in this order

Each stage reads the output of the earlier ones, so wait for each to finish (`--wait` blocks and fails if the job fails):

```sh
for stage in outlook analyse reconcile mandate-reconcile actions overview; do
  gcloud run jobs execute rm-$stage --region $REGION --wait || break
done
gcloud run jobs execute rm-scenarios --region $REGION --wait     # independent of the others; can run any time, even alongside outlook
```

| # | Job | Needs first |
|---|---|---|
| 1 | `rm-outlook` | source data |
| 2 | `rm-analyse` | outlook (a missing outlook is a gap, not a failure) |
| 3 | `rm-reconcile` | analyse |
| 4 | `rm-mandate-reconcile` | analyse |
| 5 | `rm-actions` | analyse (uses reconcile and mandate-reconcile when present) |
| 6 | `rm-overview` | analyse, reconcile, actions |
| - | `rm-scenarios` | source data only |

Reconcile and mandate-reconcile do not depend on each other and can run at the same time.

In the console: Cloud Run -> Jobs -> the job -> **Execute** (use *Execute with overrides* to change `--as-of` or `--clients` for one run).
From the CLI, `gcloud run jobs execute rm-analyse --region $REGION --args="--as-of,2026-09-30"` does the same.

Follow a run in Cloud Logging, filtered on the job. Every model call logs `llm_call ... outcome=ok|error` and each stage ends with an
`llm_summary` line (calls, tokens, failures).

## 6. Deploy the API service

```sh
gcloud run deploy rm-dashboard-api \
  --image $IMAGE --region $REGION --service-account $SA \
  --set-env-vars "RM_DATA_SOURCE=firestore:$PROJECT_ID,RM_ARTIFACT_STORE=firestore:$PROJECT_ID"
```

The default command is `rm-dashboard-serve` on `$PORT`. Add `--allow-unauthenticated` only if the API should be public. It reads Firestore
live, so results appear while a stage is still running and the service never needs redeploying for new data.

## After a code change

```sh
gcloud builds submit --tag $IMAGE .
for stage in outlook analyse reconcile mandate-reconcile actions overview scenarios; do
  gcloud run jobs update rm-$stage --image $IMAGE --region $REGION
done
gcloud run deploy rm-dashboard-api --image $IMAGE --region $REGION
```
