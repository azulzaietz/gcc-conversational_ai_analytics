# Ingest Pipeline

This pipeline automates the process of ingesting audio data into Contact Center AI (CCAI) Insights and exporting the analyzed data to BigQuery. It leverages several Google Cloud services to achieve this.

## Modules

### 1. `ingest-pipeline`
This module is the core of the pipeline. It's a set of Cloud Functions orchestrated via Cloud Workflows to upload conversations and transcripts into CCAI.

### 2. `cf-ccai-conversation-upload`
This Cloud Function ingests transcripts into CCAI. A successful ingestion triggers CCAI analysis. This is configured via the CCAI Insights project setting located in the `utils` folder.

### 3. `cf-stt-transcript`
This Cloud Function calls Cloud Speech-to-Text (STT) to generate transcripts from audio files.

### 4. `cf-transcript-correction`
This Cloud Function utilizes a Vertex AI generative model (Gemini) to correct key business terms within the generated transcripts, ensuring accuracy and consistency.

### 5. `cf-feedback-generator`
Triggered after a conversation is uploaded into CCAI and analyzed, this Cloud Function identifies specific Quality Assurance (QA) questions that the agent needs feedback on based on their performance. Feedback for these questions is generated using the Vertex AI generative model. Finally, the feedback is exported to a BigQuery table.

### 6. `cf-export-to-bq-incremental`
This Cloud Function is triggered every 15 minutes to perform the following:
- Runs a SQL query on the main CCAI table (if the table doesn't exist, it performs a full load) to determine the latest analysis date.
- Uses the latest analysis date to filter the time range for the CCAI Insights export service to BigQuery. (Note: The table needs to exist before running the export service.)
- Triggers a merge statement on the conversation name and latest analysis date to update the main BigQuery table with the latest CCAI Insights data.

## Workflow

The `ingest-pipeline` module orchestrates the execution of these Cloud Functions in the following sequence:

1.  Audio data is uploaded to a Cloud Storage bucket, triggering the `cf-stt-transcript` function.
   
2.  `cf-stt-transcript` transcribes the audio into text using Cloud STT and stores the transcript in another Cloud Storage bucket.
   
3.  The successful creation of the transcript triggers the `cf-transcript-correction` function.
   
4.  `cf-transcript-correction` uses Gemini to correct key business terms in the transcript.
   
5.  The corrected transcript triggers the `cf-ccai-conversation-upload` function.
   
6.  `cf-ccai-conversation-upload` ingests the corrected transcript into CCAI, which automatically triggers CCAI analysis.
   
7.  After CCAI analysis is complete, the `cf-feedback-generator` function is triggered.
   
8.  `cf-feedback-generator` generates feedback on the conversation using another Gemini model and writes it to BigQuery.
   
9.  Meanwhile, the `cf-export-to-bq-incremental` function runs every 15 minutes to export the latest CCAI Insights data to BigQuery and then to Snowflake.

## Error Handling

The pipeline includes error handling to provide informative messages in case of failures at any step.

## Output

Upon successful completion of each step, the corresponding Cloud Function returns the status of the operation, indicating the completion of its task. The final output is the updated data in BigQuery, reflecting the latest CCAI Insights analysis.