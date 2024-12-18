# CCAI Coaching Feedback Generator

This function generates coaching feedback for customer service agents based on their conversation transcripts and predefined quality assurance questions. It leverages Google Cloud's Contact Center AI Insights API to retrieve conversation data and Vertex AI's generative models to generate feedback.

## How it works

1. **Retrieve conversation data:** The Cloud Function uses the CCAI Insights API to retrieve the transcript and quality assurance (QA) questions for a given conversation ID.
2. **Extract relevant questions:** It identifies the specific QA questions that the agent needs feedback on based on their performance.
3. **Generate prompt:** It constructs a prompt that includes the transcript, the relevant QA questions, and instructions for the generative model.
4. **Generate feedback:** It sends the prompt to a Vertex AI generative model, which generates constructive feedback for the agent in a structured JSON format.
5. **Write to BigQuery:** The Cloud Function writes the JSON values to BigQuery in a table previously created with the corresponding schema.

## Requirements

- **Contact Center AI Insights API:** Enable the CCAI Insights API in your project.
- **Vertex AI:** Enable the Vertex AI API in your project.
- **Service Account:** A service account with permissions to access the CCAI Insights API and Vertex AI.
- **Create table in BigQuery:**  Create a new table to store the feedback in BigQuery with the following schema:
  ```
    [
      {
        "name": "conversationName",
        "mode": "REQUIRED",
        "type": "STRING",
        "description": "",
        "fields": []
      },
      {
        "name": "qaQuestion",
        "mode": "REQUIRED",
        "type": "STRING",
        "description": "",
        "fields": []
      },
      {
        "name": "feedback",
        "mode": "NULLABLE",
        "type": "STRING",
        "description": "",
        "fields": []
      }
    ]
  ```

## Usage

**Execution:**
  - Cloud Function is triggered through a Cloud Workflow call when the function after a conversation has been uploaded and analyzed.

## Environment variables

    - `PROJECT_ID`: Your Google Cloud project ID.
    - `LOCATION_ID`: The location of your Vertex AI resources.
    - `MODEL_NAME`: The name of your Vertex AI generative model.
    - `INSIGHTS_ENDPOINT`: The endpoint for the CCAI Insights API.
    - `INSIGHTS_API_VERSION`: The version of the CCAI Insights API.
    - `CCAI_INSIGHTS_LOCATION_ID`: The location of your CCAI Insights resources.
    - `DATASET_NAME`: The BigQuery dataset name.
    - `FEEDBACK_TABLE_NAME`: The BigQuery table name to store feedback.
    - `SCORECARD_ID`: CCAI Insights Scorecard ID.
