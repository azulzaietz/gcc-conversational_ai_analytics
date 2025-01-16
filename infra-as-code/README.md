# Google Case Manager AI Assistant CCAI Features

This project involves a data pipeline which processes raw audio files, changes the audio format to be consumed by Cloud Speech in order to generate a transcript and sends it to CCAI for data augmentation. 

## Architecture 

![CCAI data pipeline architecture diagram](architecture.png)

## Project structure 
```
infra-as-code/ 
├── environments/ 
│ └── dev/ 
│   └── terraform files/
├── modules/ 
│ └── audio-data-format-change/
│ └── ingest-pipeline/
│   └── cf-audio-redaction/
│   └── cf-ccai-conversation-upload/
│   └── cf-stt-transcript/
│   └── cf-transcript-correction/
│   └── cf-feedback-generator/
│   └── cf-export-to-bq-incremental
│   └── workflow/ 
└── utils/
```

- **Environments**: This folder contains the main terraform files for each environment. Such as: Service account permissions, primitives modules, API activation, required variables to run the terraform, backend and terraform version. 
- **Modules**: Contains all the Cloud functions and Workflow created for the data pipeline. 
    - **audio-data-format-change**: Cloud function to transform raw audio files into Cloud Speech required format.
    - **ingest-pipeline**: Set of cloud functions called through Cloud Workflows to upload the conversation and transcript into CCAI
        - *cf-stt-transcript*: calls Cloud speech to generate transcript
        - *cf-transcript-correction*: calls Gemini to correct business key words and labels the conversation
        - *cf-audio-redaction*: uses FFmpeg to redact sensitive information identified by DLP from audio files.
        - *cf-ccai-conversation-upload*: calls uploadConversation to ingest transcript into CCAI
        - *cf-feedback-generator*: calls Gemini to generate coaching feedback according to CCAI QAI scoring and inserts it into a table
        - *cf-export-to-bq-incremental*: call the export endpoint to export CCAI data into BigQuery
        - *workflow*: contains the Cloud workflow YAML for HTTP orchestration
- **Utils**: Required python/scripts that need to run before terraform since the current version of terraform does not support the creation of such resources. 

## Set up this project
Before running `terraform init` and `terraform apply` for this project it is necessary to:
1. Go to the Utils folder and open the [`create-items.sh`](utils/create-items.sh) file to create the speech recognizer. 
2. Set the variables according to your project and naming conventions. Variables to change:

| Variable name | Description | Type | Change required | Example | 
|----------|----------|----------|----------|----------|
|PROJECT_ID| ID of the Google project | `string` | YES | `case-manager-ai-assistant` |
|SPEECH_ENDPOINT| Endpoint to send the request | `string` | IF NECESSARY | `speech.googleapis.com` |
|RECOGNIZER_ID| Name of the recognizer which later will be used as a variable in terraform | `string` |YES |`project-recognizer`| 

3. Run the bash script with `bash utils/create-items.sh`
4. Manually create a backend bucket for the terraform. This is required as terraform init downloads all dependencies and stores the terraform state in the bucket. Name must be globally unique.
5. Once created change the value of `bucket` in the file `environments/dev/backend.tf` for the one that was created in step 4
6. Create `environments/dev/terraform.tfvars` and set the values for each variable in `environments/dev/variables.tf`. Example: 

```
project_id = "<project_id>"
region = "us-central1"
insights_endpoint = "contactcenterinsights.googleapis.com"
insights_api_version = "v1"
env = "dev"
ccai_insights_project_id = "<ccai_project_id>
ccai_insights_location_id = "us-central1"
pipeline_name = "ingest-pipeline"
recognizer_path = "projects/case-manager-ai-assistant-dev/locations/global/recognizers/stt-call-recognizer"
hash_key = "<hash_key>"
hash_secret_name = "original-filename-key"
bq_external_connection_name = "ccai-pipeline-record"
dataset_name = "ccai_insights_export"
feedback_table_name = "coaching_feedback"
scorecard_id = "<scorecard_id>"
```

7. Run `terraform -chdir=environments/<env> init` and `terraform -chdir=environments/<env> apply`. Change `<env>` according to the environment needed. 
8. Go to the Utils folder and edit the file `update-settings.sh`. **This step and step 9 are optional, do not follow if project will not use DLP**. Variables to change:

| Variable name | Description | Type | Example | 
|----------|----------|----------|----------|
|PROJECT_ID| Google Project ID | `string` | `case-manager-ai-assistant` |
|LOCATION| Location where the templates were created | `string` | `us-central1` |
|INSPECT_TEMPLATE_ID| ID of the inspect template created by terraform | `string` | `184466429764461575` |
|DEIDENTIFY_TEMPLATE_ID| ID of the deidentify template created by terraform | `string` | `6891154579008730158` | 

9. Run the bash scripts in the Utils folder. `bash utils/update-settings.sh` to change the template to a project level.
10. Run the [analyze settings](utils/analyze-setting.sh) in the Utils folder with `bash utils/analyze-setting.sh` to update the analysis annotator settings for CCAI Insights. 
11. Create the tables for feedback, CCAI export and staging according to [create-tables.sql](utils/create-tables.sql). **Important**: It is recommended to create the export table by manually exporting in CCAI as schema might change, clone the table for staging and modify `MERGE` in [export](modules/ingest-pipeline/cf-export-to-bq-incremental/lib.py). Only create the external table for the parquet file if it exists in the bucket `ingest-record-bucket`.

## Dual project settings
Project is configure to work as a single project or dual project. Audio file processing and transcription which includes PII would be part of `project_id` whereas non-PII data would be deployed on the `ccai_insights_project_id`, which only includes CCAI and its export to BigQuery

If `ccai_insights_project_id` is equal to `project_id` then terraform with work as if it is one single project. Otherwise it will create a service account for the CCAI project where it will be deployed separately. 

## Start testing

**Execution:**
- Cloud Function is triggered through an EventArc when a `google.cloud.storage.object.v1.finalized` event occurs. To start testing, send a **dual-channel** audio file to the trigger bucket `original-audio-files.*`. This will trigger the cloud function to change the audio file format to a supported format by Cloud Speech and upload the conversation into CCAI, each conversation will have their ID and Cloud Storage audio blob associated.
 
If any input file is located in a different bucket, they could be transferred through gsutil with the following command: 

- **Multiple files**: Use the [notebook](utils/batch_pipeline_trigger.ipynb) prepared
- **One file**:
  `gsutil cp gs://source-bucket/my-file.wav gs://destination-bucket/my-file.wav`

Where the destination bucket is the bucket created by terraform under the module "trigger_bucket". 

## Terraform Variables 
| name | description | type | required | default | example |
|---|---|:---:|:---:|:---:|:---:|
|project_id| ID of Google Project | `string` | Yes | | `case-manager-ai-assistant` |
|region| Region where resources will be created | `string` | Yes | | `us-central1` |
|env| Environment where it is being deployed | `string` | Yes | | `dev` |
|insights_endpoint| Endpoint to be used according to the region for CCAI Insights | `string` | Yes | | `contactcenterinsights.googleapis.com` |
|insights_api_version| CCAI API version | `string` | Yes | | `v1` |
|ccai_insights_project_id| ID of Google Project where CCAI is| `string` | Yes | | `case-manager-ai-assistant` |
|ccai_insights_location_id| Location ID for CCAI Insights | `string` | Yes | | `us-central1` | 
|pipeline_name| Name of the pipeline | `string` | Yes | | `data-pipeline` |
|hash_key| Hexadecimal string key to be used for hashing | `string` | Yes | | `8c99c71b18acf58cea54e613e8d140909ced8c3eda4a93b6d1673cf9a7d3bdf8` |
|recognizer_path| Complete path of the recognizer created with the bash script. Must follow structure: `projects/{PROJECT_ID}/locations/global/recognizers/{RECOGNIZER_NAME}` | `string` | Yes | | `projects/my-project-id/locations/global/recognizers/recognizer-name` |
|model_name| Name of the model to use in Gemini call| `string` | Yes | `gemini-1.5-flash-002` | `gemini-1.5-flash-002` |
|hash_secret_name| Name of the secret in secret manager for the hashing key value| `string` | Yes |  | `original-filename-key` |
|bq_external_connection_name| Name of the external connection created in BigQuery | `string` | Yes |  | `ccai-pipeline-record` |
|dataset_name| BigQuery dataset name | `string` | Yes |  | `ccai_insights` |
|feedback_table_name| BigQuery table name to store feedback | `string` | Yes |  | `coaching_feedback` |
|scorecard_id| ID of the QAI scorecard to use a base for feedback instructions | `string` | Yes |  | `242501912243980191` |

## CCAI Insights Regionalization
This project uses global country grouping with location at us-central1. Review [CCAI Insights available regions](https://cloud.google.com/contact-center/insights/docs/regionalization) if the project requires a specific location due to policies. Change the terraform variable `insights_endpoint` and `ccai_insights_location_id` according to the project's location requirements. 

## Project Error Handling:
This project is configured to not process any audio where its filename does not include the case manager email as it is an inbound call to voicemail. Finally, it will not process again any audio file that was processed previously and was sucessful. 

Each step of the workflow has an explonential retry with a maximum of 5 attempts, after this, it will log in a parquet file and Cloud Logging. 

### Parquet for Record Keeping
Each cloud function includes a RecordKeeper class in charge of working with a parquet file that is automatically created after the first file ingestion, it will create a blob with the current year as prefix. Example: `2024/ingest_filename_record.parquet`. Additionally, it will be created with the following schema:
|column_name| type | description | example |
|-----------|------|-------------|---------|
|`occurrence_timestamp`| `str` |UTC timestamp in the ISO 8601 format, indicates the time the record was added to the parquet file. | `2024-10-31 16:42:03.972940` |
|`filename`| `str` | with original filename, hashed according to the specified hashing logic.  | `7a5550db270ea59a1b935df308a9061131b9bd51ecba78ca03f23c74a1ec02d4` |
|`includes_case_manager_email`| `bool`| if true the filename includes the case manager email address. Must be present in the file name in order to be processed. | `true` |
|`processed`| `bool`| if true, the file was processed successfully throughout the pipeline. | `false` |
|`error`| `bool`| if true, the file processing failed to be processed in any part of the pipeline. | `true` |
|`error_message`| `str` | If error occurs, the error message will be written to the error message column | |

### Cloud Logging 
Errors in the pipeline will also produce a log which can be query in Cloud Logging or be set up as a message service for inmediate notification and handling.

Each log contains metadata about the file that failed to process. Each Cloud Function also has a logger name which can be use to query. 
- **cf_audio_format_change_logger**: Audio format change cloud function
- **cf_stt_transcript_logger**: STT cloud function
- **cf_genai_word_fix_logger**: Gemini call for word fixing and call categorization
- **cf_insights_uploader_logger**: Conversation Upload API call
- **cf_feedback_generator_logger**: Gemini call for feedback generation

## Snowflake integration
Any integration can be done by using the [`cf-export-to-bq-incremental`](modules/ingest-pipeline/cf-export-to-bq-incremental/lib.py) through the `export_staging_table_to_pandas_df` function. This can be then used in the Snowflake staging table. For nested columns, such as record or repeated fields, pandas.DataFrame will have them as `ARRAY[OBJECTS]` which is supported by Snowflake.  

## Data Loss Prevention
Terraform includes the DLP templates creation but if they will not be used it is not necessary to run [update-settings.sh](utils/update-settings.sh)

## Updating a QAI Scorecard
As pipeline is event based, modifying the scorecard will not impact already ingested conversations. Use the notebook [batch_analyze_and_feedback](utils/batch_analyze_and_feedback.ipynb) to run analysis and feedback generation manually over conversation stored in CCAI Insights.