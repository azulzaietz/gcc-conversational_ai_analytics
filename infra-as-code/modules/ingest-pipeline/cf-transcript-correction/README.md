# GenAI Business Key Word fixer

This function calls Vertex AI Generative models in order to fix the transcript key words

## Functionality

1. **Download:** downloads the transcript file
2. **Prompts Gemini for transcript fix:** Gives gemini instructions with the transcript and audio file as input for analysis. Expects Gemini to give a formatted answer
3. **Upload to storage:** Uploads the answer as the new transcript
4. **Prompts Gemini for audio categorization**: Gives gemini instructions to categorize the audio file. Can be used in order to filter audios that are voicemail, from patients, etc. 
5. **Updates the audio file metadata**: Updates the file metadata in GCS for the audio file in order to use as quality metadata in CCAI
6. **Sends a response:** Sends an HTTP response with the payload

## Usage

1. **Prerequisites:**
    - Google Cloud project with necessary permissions
2. **Execution:**
    - Cloud Function is triggered through a Cloud Workflow call when the function calling for STT transcription is finished.

## Dependencies
```
functions-framework==3.*
google-auth==2.17.0
google-cloud-storage==2.8.0
google.cloud.logging==3.11.0
google-cloud-aiplatform==1.69.0
```

## Environment Variables
| Field | Description | Type | Example |
|---|---|---|---|
|PROJECT_ID| ID of the project | `string` | `my-project-id` |
|LOCATION_ID | Name of the region to call Gemini | `string` | `us-central1` |
|MODEL_NAME | Name of the model to be used in the Gemini call | `string` | `gemini-1.5-flash-002` |

## Output

1. **Transcript of audio file**: A json file stored in the specified bucket.
2. **List of categories**: List of the categories for the audio fle.
3. **Response**: A dictionary that contains:

| Field | Description | Type | Example |
|---|---|---|---|
| `event_bucket` | Name of the bucket where the EventArc was triggered | `string` | `bucket-name` |
| `event_filename` | Name of the blob that triggered the EventArc | `string` | `test-file.flac` |
| `transcript_bucket` | Bucket id where the transcription is stored | `string` | `bucket-name` |
| `transcript_filename` | Name of the blob with the transcription | `string` | `transcript-file.json` |

## Choosing Gemini 1.5 Pro vs Gemini 1.5 Flash
Flash is a well balanced model that supports up to 1 million tokens, as it is only audio files that are less than an hour long, it is better to set de terraform variable MODEL_NAME as `gemini-1.5-flash-002` instead of `gemini-1.5-pro-002`.