import functions_framework
import os
from lib import SpeechToTextCaller

# Triggered by a change in a storage bucket
@functions_framework.http
def main(request):
    event = request.get_json()
    print("Cloud event: {}".format(event))

    #Getting variables
    project_id = os.environ.get('PROJECT_ID')
    transcript_bucket_id = os.environ.get('TRANSCRIPT_BUCKET_ID')
    formatted_audio_file_name = event.get("name")
    formatted_audio_bucket_id = event.get("bucket")
    recognizer_path = os.environ.get('RECOGNIZER_PATH')
    ingest_record_bucket_id = os.environ.get('INGEST_RECORD_BUCKET_ID')

    stt_caller = SpeechToTextCaller (
    project_id,
    transcript_bucket_id,
    formatted_audio_file_name, 
    formatted_audio_bucket_id,
    ingest_record_bucket_id,
    recognizer_path
    )

    event_dict = stt_caller.transcribe()
    return event_dict