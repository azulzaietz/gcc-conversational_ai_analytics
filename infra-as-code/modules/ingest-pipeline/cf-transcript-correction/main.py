import functions_framework
import os
from lib import GenAIFixer

# Triggered by a change in a storage bucket
@functions_framework.http
def main(request):
    event = request.get_json()
    print("Cloud event: {}".format(event))

    #Getting variables
    formatted_audio_file_name = event.get("event_filename")
    formatted_audio_bucket_id = event.get("event_bucket")
    transcript_bucket_id = event.get("transcript_bucket")
    transcript_file_name = event.get("transcript_filename")
    project_id = os.environ.get('PROJECT_ID')
    location_id = os.environ.get('LOCATION_ID')
    model_name = os.environ.get('MODEL_NAME')
    ingest_record_bucket_id = os.environ.get('INGEST_RECORD_BUCKET_ID')
    five9_filename = event.get("five9_filename")
    client_specific_constraints = os.environ.get("CLIENT_SPECIFIC_CONSTRAINTS")
    client_specific_context = os.environ.get("CLIENT_SPECIFIC_CONTEXT")
    few_shot_examples = os.environ.get("FEW_SHOT_EXAMPLES")


    genai = GenAIFixer (
    project_id,
    location_id,
    model_name,
    transcript_bucket_id,
    transcript_file_name,
    formatted_audio_file_name, 
    formatted_audio_bucket_id,
    ingest_record_bucket_id,
    five9_filename,
    client_specific_constraints,
    client_specific_context,
    few_shot_examples
    )

    event_dict = genai.fix()
    return event_dict