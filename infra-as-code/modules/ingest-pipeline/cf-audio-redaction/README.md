# Audio Redaction Cloud Function

This Cloud Function redacts sensitive information from audio files using Google Cloud's DLP API and FFmpeg. 

## Functionality

1. **Downloads and analyzes transcript:** It downloads the corresponding transcript (assumed to be in JSON format with word-level timestamps) from another GCS bucket.
2. **Identifies sensitive information:**  The function uses the DLP API to scan the transcript for sensitive data, such as names, addresses, phone numbers, and other PII.
3. **Redacts audio:** Based on the DLP findings and the timestamps in the transcript, the function uses FFmpeg to precisely mute the segments of the audio containing sensitive information.
4. **Uploads redacted files:** The redacted audio file is uploaded to a designated GCS bucket.

## Prerequisites

- **Google Cloud Project:**  A Google Cloud Project with billing enabled.
- **Service Account:** A service account with the following permissions:
    - `roles/storage.objectAdmin` for accessing and modifying files in Google Cloud Storage.
    - `roles/dlp.user` for using the DLP API.
- **Cloud Storage Buckets:** Three Cloud Storage buckets:
    - One for storing the source audio files.
    - One for storing the transcripts.
    - One for storing the redacted audio files.
- **FFmpeg:** FFmpeg must be installed in the Cloud Function environment. This can be done by including it in the function's dependencies or by building a custom container image.
- **Transcript Format:**  The transcripts must be in JSON format and include word-level timestamps, as shown in the example below:

```json
{
  "results": [
    {
      "alternatives": [
        {
          "transcript": "This is an example transcript with some sensitive information like a name, John Doe, and a phone number, 555-123-4567.",
          "confidence": 0.95,
          "words": [
            {"word": "This", "startOffset": "0s", "endOffset": "0.5s"},
            {"word": "is", "startOffset": "0.5s", "endOffset": "0.8s"},
            // ... other words ...
            {"word": "John", "startOffset": "5.2s", "endOffset": "5.6s"},
            {"word": "Doe", "startOffset": "5.6s", "endOffset": "6.0s"},
            // ... other words ...
            {"word": "555-123-4567", "startOffset": "10.1s", "endOffset": "11.2s"}
          ]
        }
      ]
    }
  ]
}