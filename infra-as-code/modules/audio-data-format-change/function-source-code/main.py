import functions_framework
import os
from lib import AudioFormatterRunner

# Triggered by a change in a storage bucket
@functions_framework.cloud_event
def main(cloud_event):
    #Getting event data
    data = cloud_event.data

    #Getting variables
    project_id = os.environ.get('PROJECT_ID')
    raw_audio_bucket_id = data['bucket']
    raw_audio_file_name = data['name']
    formatted_audio_bucket_id = os.environ.get('FORMATTED_AUDIO_BUCKET_ID')
    metadata_bucket_id = os.environ.get('METADATA_BUCKET_ID')
    number_of_channels = os.environ.get('NUMBER_OF_CHANNELS')
    hash_key = os.environ.get('HASH_KEY')
    ingest_record_bucket_id = os.environ.get('INGEST_RECORD_BUCKET_ID')

    audio_formatter = AudioFormatterRunner (
    project_id,
    raw_audio_bucket_id,
    raw_audio_file_name,
    formatted_audio_bucket_id,
    metadata_bucket_id,
    hash_key,
    ingest_record_bucket_id,
    number_of_channels
    )

    audio_formatter.run_format()

