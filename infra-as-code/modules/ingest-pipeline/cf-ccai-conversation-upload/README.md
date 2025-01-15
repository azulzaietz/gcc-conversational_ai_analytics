# CCAI Insights Uploader Cloud Function

This Cloud Function uploads audio conversations and their corresponding transcripts to Contact Center AI Insights. It uses the CCAI Insights API to ingest conversation data for analysis and reporting.

## Functionality

1. **Retrieves transcript:** It retrieves the corresponding transcript from another designated GCS bucket.
2. **Extracts metadata:** The function extracts relevant metadata from the audio file, such as agent ID, customer ID, and any custom labels.
3. **Uploads to CCAI Insights:** It constructs a conversation object with the audio, transcript, and metadata, and uploads it to CCAI Insights using the `conversations:upload` API endpoint.
4. **Error handling and logging:** The function includes error handling to catch exceptions during the upload process and logs any errors to Cloud Logging for debugging.

## Prerequisites

- **Google Cloud Project:** A Google Cloud Project with billing enabled.
- **Service Account:** A service account with the following permissions:
    - `roles/storage.objectViewer` to access files in Google Cloud Storage.
    - `roles/contactcenterinsights.editor` to upload conversations to CCAI Insights.
- **Cloud Storage Buckets:** Two Cloud Storage buckets:
    - One for storing the audio files.
    - One for storing the transcripts.
- **CCAI Insights:** A CCAI Insights instance in the same project or a different project with proper permissions.
- **API Enablement:** Ensure that the Contact Center AI Insights API is enabled in your project.

## Environment Variables

- `CCAI_INSIGHTS_PROJECT_ID`: The project ID of your CCAI Insights instance.
- `CCAI_INSIGHTS_LOCATION_ID`: The location ID of your CCAI Insights instance (e.g., `us-central1`).
- `TRANSCRIPT_BUCKET_NAME`: The name of the bucket containing the transcripts.
- `INGEST_RECORD_BUCKET_ID`: The bucket ID for storing ingestion records.

## Additional Notes

- **Authentication:** The function uses OAuth 2.0 for authentication with the CCAI Insights API.
- **Metadata:** The function extracts metadata from the audio file's metadata field in Cloud Storage. You can customize this to include additional metadata as needed.
- **Error Logging:** The function logs errors to Cloud Logging. You can configure logging to suit your needs.
- **Rate Limiting:** Be aware of the CCAI Insights API's rate limits and adjust your function's behavior accordingly.
