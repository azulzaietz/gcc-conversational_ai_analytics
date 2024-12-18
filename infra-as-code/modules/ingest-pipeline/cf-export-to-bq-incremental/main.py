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

import functions_framework
import json
import os
import time
import requests

from lib import InsightsHelper

@functions_framework.http
def main(request):
    """
    Cloud Function entry point for exporting CCAI Insights data to BigQuery and then to Snowflake.

    This function performs the following steps:
        1. Retrieves environment variables for project IDs, dataset names, and table names.
        2. Initializes an `InsightsHelper` object to interact with CCAI Insights and BigQuery.
        3. Determines the filter expression for the export request based on the latest update timestamp.
        4. Submits the export request to CCAI Insights.
        5. Polls the operation status until it's complete.
        6. Executes a merge query in BigQuery to update or insert data from the staging table to the final table.
        7. Exports the staging table to a Pandas DataFrame.
        8. (TODO) Uses the DataFrame to export data to Snowflake.
        9. Compares the conversation count in BigQuery and CCAI Insights.

    Args:
        request (flask.Request): The request object.

    Returns:
        str: 'ok' if the function completes successfully.
    """
    CCAI_INSIGHTS_PROJECT_ID=os.environ['CCAI_INSIGHTS_PROJECT_ID']
    CCAI_INSIGHTS_LOCATION_ID=os.environ['CCAI_INSIGHTS_LOCATION_ID']
    BIGQUERY_PROJECT_ID=os.environ['BIGQUERY_PROJECT_ID']
    BIGQUERY_STAGING_DATASET=os.environ['BIGQUERY_STAGING_DATASET']
    BIGQUERY_STAGING_TABLE=os.environ['BIGQUERY_STAGING_TABLE']
    BIGQUERY_FINAL_DATASET=os.environ['BIGQUERY_FINAL_DATASET']
    BIGQUERY_FINAL_TABLE=os.environ['BIGQUERY_FINAL_TABLE']
    INSIGHTS_ENDPOINT = os.environ.get('INSIGHTS_ENDPOINT') 
    INSIGHTS_API_VERSION = os.environ.get('INSIGHTS_API_VERSION') 

    insights_helper = InsightsHelper(
        ccai_insights_project_id=CCAI_INSIGHTS_PROJECT_ID,
        ccai_insights_location_id=CCAI_INSIGHTS_LOCATION_ID,
        bigquery_project_id=BIGQUERY_PROJECT_ID,
        bigquery_staging_dataset=BIGQUERY_STAGING_DATASET,
        bigquery_staging_table=BIGQUERY_STAGING_TABLE,
        bigquery_final_dataset=BIGQUERY_FINAL_DATASET,
        bigquery_final_table=BIGQUERY_FINAL_TABLE,
        insights_endpoint=INSIGHTS_ENDPOINT,
        insights_api_version=INSIGHTS_API_VERSION
    )

    # Filter based on conversation start time and only Analyzed conversations
    
    filter_expression=f'latest_analysis:"*"'
    latest_update_time = insights_helper.get_latest_update_time()

    # if a latest_update_time was found, include it in the filter
    if latest_update_time is None:
        print(f'Could not find a latest_update_time, we will perform a full load!')
    else: 
        filter_expression=f'{filter_expression} update_time > "{latest_update_time}"'

    print(f'Filter used for exporting CCAI Insights Data: `{filter_expression}`')

    try:
        export_operation = insights_helper.submit_export_request(filter=filter_expression)
    except requests.exceptions.RequestException as e:
        print(f'An error occurred running the CCAI Insights export operation: {e.response.text}')
        raise e

    for i in range(30):
        operation_result = insights_helper.get_operation(export_operation['name'])
        operation_name = export_operation['name']
        
        # check if the operation is finished
        if 'done' in operation_result and operation_result['done'] == True:
            if 'error' in operation_result:
                raise Exception(operation_result['error'])
            else:
                print('BigQuery export finished. Result:')
                print(operation_result)
                break
        else:
            print(f'Operation "{operation_name}" still running, sleeping...')
            time.sleep(30) # sleep 20 seconds

    print('Executing merge operation')
    insights_helper.execute_merge_query()
    staging_table_df = insights_helper.export_staging_table_to_pandas_df()

    # TODO: Use the staging_table_df Pandas Dataframe to export data to Snowflake

    convo_count_bq = insights_helper.get_conversation_count_bq()
    convo_count_insights = insights_helper.get_conversation_count_insights()

    convo_count_diff = (1 - (convo_count_bq/convo_count_insights)) * 100
    print(f'Conversation count difference between BQ and Insights: {round(convo_count_diff, 2)}%')

    return 'ok'
