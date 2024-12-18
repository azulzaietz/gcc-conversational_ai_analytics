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
import os
from audio_redaction import AudioRedaction

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
    bucket = event.get("transcript_bucket")
    file_name = event.get("transcript_filename")
    print("Detected change in Cloud Storage bucket: {}".format(bucket))
    
    project_id = os.environ.get('PROJECT_ID')
    redacted_audios_bucket_name = os.environ.get('REDACTED_AUDIOS_BUCKET_NAME')

    redactor = AudioRedaction(bucket, file_name, project_id)

    redactor.redact_audio(event, redacted_audios_bucket_name) 

    return event
