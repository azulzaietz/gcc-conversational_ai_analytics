# STT Caller

This function calls Cloud Speech in order to generate the audio file transcript

## Functionality

1. **Download:** 
2. **File order**
3. **Upload to storage**
4. **Sends a response**

## Usage

1. **Prerequisites:**
    - Google Cloud project with necessary permissions
2. **Execution:**
    - Cloud Function is triggered through a Cloud Workflow call when a `google.cloud.storage.object.v1.finalized` event occurs.

## Dependencies
```
functions-framework==3.*
google-auth==2.17.0
google-cloud-storage==2.8.0
google.cloud.logging==3.11.0
google-cloud-speech==2.27.0
```

## Environment Variables
| Field | Description | Type | Example |
|---|---|---|---|
|PROJECT_ID| ID of the project | `string` | `my-project-id` |
|TRANSCRIPT_BUCKET_ID | Name of the bucket where transcripts will be stored | `string` | `bucket-name` |
|RECOGNIZER_PATH | Path of the recognizer in the project. Recognizer must be global and follow the structure: `projects/{PROJECT_ID}/locations/global/recognizers/{RECOGNIZER_NAME}` | `string` | `projects/my-project-id/locations/global/recognizers/recognizer-name` |
|INGEST_RECORD_BUCKET_ID| ID of the bucket for the parquet file | `string` | `bucket-name |

## Output

1. **Transcript of audio file**: A json file stored in the specified bucket.
2. **Response**: A dictionary that contains:

| Field | Description | Type | Example |
|---|---|---|---|
| `event_bucket` | Name of the bucket where the EventArc was triggered | `string` | `bucket-name` |
| `event_filename` | Name of the blob that triggered the EventArc | `string` | `test-file.flac` |
| `transcript_bucket` | Bucket id where the transcription is stored | `string` | `bucket-name` |
| `transcript_filename` | Name of the blob with the transcription | `string` | `transcript-file.json` |
