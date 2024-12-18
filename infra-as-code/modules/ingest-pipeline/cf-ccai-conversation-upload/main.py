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
from insights_uploader import InsightsUploader

@functions_framework.http
def main(request):
    """
    Cloud Function entry point for processing Cloud Storage events.

    This function is triggered by Cloud Storage events and uploads the corresponding audio and transcript files to Contact Center AI Insights.

    Args:
        request (flask.Request): The request object.

    Returns:
        str: The operation name of the CCAI Insights upload request.
    """
    
    event = request.get_json()
    print("Cloud event: {}".format(event))

    # Gets the GCS bucket name from the CloudEvent
    bucket = event.get("event_bucket")
    print("Detected change in Cloud Storage bucket: {}".format(bucket))

    project_id = os.environ.get('PROJECT_ID')
    insights_endpoint = os.environ.get('INSIGHTS_ENDPOINT') 
    insights_api_version = os.environ.get('INSIGHTS_API_VERSION') 
    ccai_insights_project_id = os.environ.get('CCAI_INSIGHTS_PROJECT_ID')
    ccai_insights_location_id = os.environ.get('CCAI_INSIGHTS_LOCATION_ID') 
    ingest_record_bucket_id = os.environ.get('INGEST_RECORD_BUCKET_ID')

    uploader = InsightsUploader(project_id, insights_endpoint, insights_api_version, ccai_insights_project_id, ccai_insights_location_id, ingest_record_bucket_id)
    operation_name = uploader.upload(event)

    return operation_name
