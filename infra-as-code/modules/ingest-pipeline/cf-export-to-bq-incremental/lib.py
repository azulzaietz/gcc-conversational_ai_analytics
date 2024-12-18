#    Copyright 2024 Google LLC

#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at

#        http://www.apache.org/licenses/LICENSE-2.0

#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import requests
import json
import google.auth
import google.oauth2.credentials
import google.auth.transport.requests
import time
import datetime
import pandas as pd
import db_dtypes

from google.cloud import bigquery

class InsightsHelper:
    """
    A helper class for interacting with Contact Center AI Insights and BigQuery.

    This class provides methods for:
        - Retrieving an OAuth token for authentication.
        - Getting the status of an operation.
        - Submitting an export request to BigQuery.
        - Executing a merge query in BigQuery.
        - Exporting a BigQuery staging table to a Pandas DataFrame.
        - Getting the latest update timestamp from BigQuery.
        - Getting the conversation count from BigQuery and CCAI Insights.

    Attributes:
        ccai_insights_project_id (str): The project ID for CCAI Insights.
        ccai_insights_location_id (str): The location ID for CCAI Insights.
        bigquery_project_id (str): The project ID for BigQuery.
        bigquery_staging_dataset (str): The dataset for the staging table in BigQuery.
        bigquery_staging_table (str): The name of the staging table in BigQuery.
        bigquery_final_dataset (str): The dataset for the final table in BigQuery.
        bigquery_final_table (str): The name of the final table in BigQuery.
        insights_endpoint (str): The endpoint for the CCAI Insights API.
        insights_api_version (str): The version of the CCAI Insights API.
        bq_client (google.cloud.bigquery.Client): The BigQuery client object.
        staging_table_id (str): The fully qualified ID of the staging table in BigQuery.
        final_table_id (str): The fully qualified ID of the final table in BigQuery.
        insights_url_with_location (str): The base URL for the CCAI Insights API with the location included.
    """
    ccai_insights_project_id: str
    ccai_insights_location_id: str
    bigquery_project_id: str
    bigquery_staging_dataset: str
    bigquery_staging_table: str
    bigquery_final_dataset: str
    bigquery_final_table: str
    insights_endpoint: str
    insights_api_version: str

    bq_client = None

    insights_url_with_location = None

    def __init__(
        self, 
        ccai_insights_project_id,
        ccai_insights_location_id,
        bigquery_project_id,
        bigquery_staging_dataset,
        bigquery_staging_table,
        bigquery_final_dataset,
        bigquery_final_table,
        insights_endpoint,
        insights_api_version
        ):

        self.ccai_insights_project_id = ccai_insights_project_id
        self.ccai_insights_location_id = ccai_insights_location_id
        self.bigquery_project_id = bigquery_project_id
        self.bigquery_staging_dataset = bigquery_staging_dataset
        self.bigquery_staging_table = bigquery_staging_table
        self.bigquery_final_dataset = bigquery_final_dataset
        self.bigquery_final_table = bigquery_final_table
        self.insights_endpoint = insights_endpoint
        self.insights_api_version = insights_api_version

        self.bq_client = bigquery.Client()

        self.staging_table_id = f'{self.bigquery_project_id}.{self.bigquery_staging_dataset}.{self.bigquery_staging_table}'
        self.final_table_id = f'{self.bigquery_project_id}.{self.bigquery_final_dataset}.{self.bigquery_final_table}'

        self.insights_url_with_location = (
            'https://{}/{}/projects/{}/locations/{}'
        ).format(self.insights_endpoint, self.insights_api_version, self.ccai_insights_project_id, self.ccai_insights_location_id)


    def get_token(self):
        """
        Retrieves an OAuth token for authentication.

        Returns:
            str: The OAuth token.
        """
        creds, _ = google.auth.default(
            scopes=['https://www.googleapis.com/auth/cloud-platform'])
        auth_req = google.auth.transport.requests.Request()
        creds.refresh(auth_req)

        return creds.token

    def get_operation(self,operation_name):
        """
        Gets the status of an operation.

        Args:
            operation_name (str): The name of the operation.

        Returns:
            dict: The operation details.
        """
        headers = {
            'charset': 'utf-8',
            'Content-type': 'application/json',
            'Authorization': f'Bearer {self.get_token()}'
        }

        url = (
            'https://{}/{}/{}'
        ).format(self.insights_endpoint, self.insights_api_version, operation_name)

        response = requests.get(url, headers=headers)
        response.raise_for_status()

        return response.json()
    
    def submit_export_request(self, filter):
        """
        Submits an export request to BigQuery.

        Args:
            filter (str): The filter to apply to the export request.

        Returns:
            dict: The response from the export request.
        """
        headers = {
            'charset': 'utf-8',
            'Content-type': 'application/json',
            'Authorization': f'Bearer {self.get_token()}'
        }

        request_data = {
            'parent': f'projects/{self.ccai_insights_project_id}/locations/{self.ccai_insights_location_id}',
            'writeDisposition':'WRITE_TRUNCATE',
            'bigQueryDestination':{
                'projectId':self.bigquery_project_id,
                'dataset':self.bigquery_staging_dataset,
                'table':self.bigquery_staging_table
            },
            'filter':filter
        }
        print('BQ Export Request Data:')
        print(request_data)

        url = f'{self.insights_url_with_location}/insightsdata:export'

        response = requests.post(url, headers=headers, json=request_data)
        response.raise_for_status()

        response_json = response.json()
        
        return response_json
    
    def execute_merge_query(self):
        """
        Executes a merge query in BigQuery to update or insert data from the staging table to the final table.
        """
        merge_query = f'''
            MERGE `{self.final_table_id}` T 
                USING (
                    SELECT 
                    conversationName, 
                    audioFileUri, 
                    dialogflowConversationProfileId, 
                    startTimestampUtc, 
                    loadTimestampUtc, 
                    analysisTimestampUtc, 
                    updateTimestampUtc,
                    conversationUpdateTimestampUtc, 
                    year,
                    month,
                    day, 
                    durationNanos, 
                    silenceNanos, 
                    silencePercentage, 
                    agentSpeakingPercentage, 
                    clientSpeakingPercentage, 
                    agentSentimentScore, 
                    agentSentimentMagnitude, 
                    clientSentimentScore, 
                    clientSentimentMagnitude, 
                    transcript, 
                    turnCount, 
                    languageCode, 
                    medium, 
                    issues,
                    entities,
                    labels,
                    words,
                    sentences,
                    latestSummary,
                    qaScorecardResults,
                    agents
                    FROM `{self.staging_table_id}`) S 
                    ON T.conversationName = S.conversationName 
                WHEN MATCHED AND T.conversationUpdateTimestampUtc != S.conversationUpdateTimestampUtc THEN 
                    UPDATE SET
                        audioFileUri = S.audioFileUri, 
                        dialogflowConversationProfileId = S.dialogflowConversationProfileId, 
                        startTimestampUtc = S.startTimestampUtc, 
                        loadTimestampUtc = S.loadTimestampUtc, 
                        analysisTimestampUtc = S.analysisTimestampUtc, 
                        updateTimestampUtc = S.updateTimestampUtc,
                        conversationUpdateTimestampUtc = S.conversationUpdateTimestampUtc, 
                        year = S.year,
                        month = S.month,
                        day = S.day, 
                        durationNanos = S.durationNanos, 
                        silenceNanos = S.silenceNanos, 
                        silencePercentage = S.silencePercentage, 
                        agentSpeakingPercentage = S.agentSpeakingPercentage, 
                        clientSpeakingPercentage = S.clientSpeakingPercentage, 
                        agentSentimentScore = S.agentSentimentScore, 
                        agentSentimentMagnitude = S.agentSentimentMagnitude, 
                        clientSentimentScore = S.clientSentimentScore, 
                        clientSentimentMagnitude = S.clientSentimentMagnitude, 
                        transcript = S.transcript, 
                        turnCount = S.turnCount, 
                        languageCode = S.languageCode, 
                        medium = S.medium, 
                        issues = S.issues,
                        entities = S.entities,
                        labels = S.labels,
                        words = S.words,
                        sentences = S.sentences,
                        latestSummary = S.latestSummary,
                        qaScorecardResults = S.qaScorecardResults,
                        agents = S.agents
                WHEN NOT MATCHED THEN
                    INSERT ROW
        '''

        print('Merge query to be executed:')
        print(merge_query)

        merge_job = self.bq_client.query(merge_query)  # API request
        merge_result = merge_job.result()  # Waits for query to finish

        print('Merge query result:')
        print(f'job_id: {merge_job.job_id}')
        print(f'num_dml_affected_rows: {merge_job.num_dml_affected_rows}')

    def export_staging_table_to_pandas_df(self):
        try:
            staging_table = self.bq_client.query(f'''SELECT * FROM `{self.staging_table_id}`''')
            df = staging_table.to_dataframe()

            return df

        except Exception as e:
            print(f"An error occurred while exporting staging table into Pandas Dataframe: {e}")
            return None
    
    def get_latest_update_time(self):
        query = f'''
            SELECT MAX(conversationUpdateTimestampUtc) as maxUpdateTimestamp FROM `{self.final_table_id}`
        '''

        bq_job = self.bq_client.query(query)

        bq_job_result = bq_job.result()

        maxUpdateTimestamp = None
        for row in bq_job_result:
            maxUpdateTimestamp = row['maxUpdateTimestamp']

        if maxUpdateTimestamp is not None:
            print(f'maxUpdateTimestamp found: `{maxUpdateTimestamp}`')

            dt = datetime.datetime.fromtimestamp(maxUpdateTimestamp)
            formatted_time = dt.strftime('%Y-%m-%dT%H:%M:%SZ')

            print(f'maxUpdateTimestamp found (formatted): `{formatted_time}`')

            return formatted_time
        else:
            print(f'maxUpdateTimestamp not found!')
            return None
    
    def get_conversation_count_bq(self):
        query = f'''
            SELECT count(*) as conversationCount FROM `{self.final_table_id}`
        '''

        bq_job = self.bq_client.query(query)

        bq_job_result = bq_job.result()

        conversationCount = None
        for row in bq_job_result:
            conversationCount = row['conversationCount']

        if conversationCount is None:
            raise Exception(f'There was a problem fetching the conversation count from `{self.final_table_id}`')

        print(f'BQ conversationCount: `{conversationCount}`')

        return conversationCount

    def get_conversation_count_insights(self):
        headers = {
            'charset': 'utf-8',
            'Content-type': 'application/json',
            'Authorization': f'Bearer {self.get_token()}'
        }

        url = f'{self.insights_url_with_location}/conversations:calculateStats'

        response = requests.get(url, headers=headers)
        response.raise_for_status()

        conversationCount = response.json()['conversationCount']

        print(f'Insights conversationCount: `{conversationCount}`')
        
        return response.json()['conversationCount']
