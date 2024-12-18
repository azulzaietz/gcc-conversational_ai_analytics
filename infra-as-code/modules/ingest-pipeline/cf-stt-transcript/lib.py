import os
import uuid
import re
import json
import glob
import google.auth
import google.auth.transport.requests
import google.cloud.logging
import requests
import time
from google.cloud import storage
from google.cloud.speech_v2 import SpeechClient
from google.cloud.speech_v2.types import cloud_speech
from record import RecordKeeper

class SpeechToTextCaller:
  project_id: str
  transcript_file_uri: str
  transcript_bucket_uri: str
  formatted_audio_bucket_id: str
  formatted_audio_file_name: str
  recognizer_path: str
  five9_filename: str
  event_dict = dict()

  storage_client = None
  speech_client = None

  def __init__(
    self,
    project_id,
    transcript_bucket_id,
    formatted_audio_file_name,
    formatted_audio_bucket_id,
    ingest_record_bucket_id,
    recognizer_path
    ):

    self.project_id = project_id
    self.formatted_audio_bucket_id = formatted_audio_bucket_id
    self.formatted_audio_file_name = formatted_audio_file_name
    self.transcript_bucket_uri = f'gs://{transcript_bucket_id}'
    self.recognizer_path = recognizer_path

    creds = self.get_credentials()
    self.storage_client = storage.Client(credentials=creds)

    self.get_audiofile_metadata(formatted_audio_bucket_id, formatted_audio_file_name)

    self.record_keeper = RecordKeeper(ingest_record_bucket_id, self.five9_filename, self.storage_client) 

    print(f'Starting transcript on: {self.formatted_audio_file_name}')

  def get_credentials(self):
    creds, _ = google.auth.default(
        scopes=['https://www.googleapis.com/auth/cloud-platform'])

    print('Getting credentials')
    return creds

  def get_oauth_token(self):
    creds = self.get_credentials()
    auth_req = google.auth.transport.requests.Request()
    creds.refresh(auth_req)
    return creds.token

  def get_gcs_uri(self, bucket, object_name):
    return 'gs://{}/{}'.format(bucket, object_name)

  def extract_bucket_and_filename(self, uri):
    """Extracts the bucket and the blob's filename

    Args:
        uri (str): gsutil URI

    Returns:
        Tuple (str,str): bucket name and blob's name
    """
    if "://" in uri:
        uri = uri.split("://", 1)[1]

    bucket, filename = uri.split("/", 1)
    return bucket, filename

  def get_audiofile_metadata(self, bucket_name, object_name):
    """Get metadata from a gcs blob

    Args:
        bucket_name (string): Name of the bucket
        object_name (string): Name of the blob
    """
    bucket = self.storage_client.bucket(bucket_name)
    blob = bucket.get_blob(object_name)

    print("Bucket name: {}".format(bucket))
    print("Blob: {}".format(blob))

    if blob.metadata:
      self.five9_filename =  blob.metadata['five9_filename']
      print("Retrieved metadata from file")
    else: 
      print("Unable to retrieve metadata")
      raise Exception('Unable to retrieve original filename')

  def order_transcript(self, bucket_name, filename):
    """Downloads the transcript and orders the transcript by offset
       in order to have the turns correctly and avoids the empty transcripts
       and uploads the ordered transcript to gcs

    Args:
        bucket_name (str): Bucket name
        filename (str): Blob name
    """
    bucket = self.storage_client.bucket(bucket_name)
    blob = bucket.blob(filename)

    contents = blob.download_as_text()
    transcript_data = json.loads(contents)

    sorted_results = sorted(
        (item for item in transcript_data["results"] if "alternatives" in item),
        key=lambda x: float(x["resultEndOffset"].replace("s", "")) )

    transcript_data["results"] = sorted_results

    modified_contents = json.dumps(transcript_data, indent=2)
    blob.upload_from_string(modified_contents, content_type='application/json')
    print(f"Modified JSON file '{filename}' successfully updated in bucket '{bucket_name}'.")

  def transcribe_multichannel(self, audio_file_uri):
    """Calls the Speech Client to do a transcription for a dual-channel file
       located in GCS

    Args:
        audio_file_uri (str): gsutil URI to the audio file in GCS

    Raises:
        Exception: Speech client exception for the LRO

    Returns:
        dict: Dictionary with the audio metadata to send as HTTP response
    """
    print('Starting Speech client')
    creds = self.get_credentials()
    speech_client = SpeechClient(credentials = creds)

    config = cloud_speech.RecognitionConfig(
        auto_decoding_config=cloud_speech.AutoDetectDecodingConfig()
    )

    file_metadata = cloud_speech.BatchRecognizeFileMetadata(uri=audio_file_uri)

    request = cloud_speech.BatchRecognizeRequest(
        recognizer=self.recognizer_path,
        config=config,
        files=[file_metadata],
        recognition_output_config=cloud_speech.RecognitionOutputConfig(
            #inline_response_config=cloud_speech.InlineOutputConfig(),
            gcs_output_config = cloud_speech.GcsOutputConfig(uri=self.transcript_bucket_uri)
        ),
    )

    operation = speech_client.batch_recognize(request=request)
    
    print("Waiting for operation to complete...")
    for i in range(60):
      if operation.done() == True:
        operation_data = operation.operation
        if hasattr(operation_data, 'error') and str(operation_data.error) != '':
            print(f'Operation error: {operation_data.error}')
            raise Exception(str(operation_data.error))
        else:
          print('Transcription finished')
          response = operation.result()
          break
      else:
        print(f'Operation still running, sleeping...')
        time.sleep(30)

    print(f'Response from speech client:  {response}')

    transcript_uri = ''
    for filename, file_result in response.results.items():
        if file_result.cloud_storage_result:
            transcript_uri = file_result.cloud_storage_result.uri
            print(f'Filename: {filename}, Cloud Storage URI: {transcript_uri}')
        else:
            print(f'Filename: {filename} has no cloud_storage_result.')

    transcript_bucket, transcript_filename = self.extract_bucket_and_filename(transcript_uri)
    self.event_dict['transcript_bucket'] = transcript_bucket
    self.event_dict['transcript_filename'] = transcript_filename
    self.event_dict['event_bucket'] = self.formatted_audio_bucket_id
    self.event_dict['event_filename'] = self.formatted_audio_file_name
    self.event_dict['five9_filename'] = self.five9_filename

    self.order_transcript(transcript_bucket, transcript_filename)

    return self.event_dict

  def log_error(self, exception_message):
    """Logs an error in Cloud Logging

    Args:
        exception_message (str): Exception message to log as error
    """
    creds = self.get_credentials()
    client = google.cloud.logging.Client(project = self.project_id, credentials = creds)
    logger = client.logger(name="cf_stt_transcript_logger")

    entry = dict()
    entry['message'] = 'An error ocurred when using Cloud Speech for transcription'
    entry['exception_message'] = exception_message
    entry['audio_file_gcs_path'] = 'gs://{}/{}'.format(self.formatted_audio_bucket_id, self.formatted_audio_file_name)

    logger.log_struct(entry,severity="ERROR",)

    print('Error logged')

  def transcribe(self):
    """Calls the RecordKeeper and error logger 
       if there is an error during transcription

    Returns:
        _type_: _description_
    """
    audio_uri = self.get_gcs_uri(self.formatted_audio_bucket_id, self.formatted_audio_file_name)
    print(audio_uri)
    try:
      event_dict = self.transcribe_multichannel(audio_uri)
      self.record_keeper.replace_row(self.record_keeper.create_processed_record())
      print("Finished")
      return event_dict
    except Exception as e:
      self.log_error(str(e))
      self.record_keeper.replace_row(
        self.record_keeper.create_error_record(f'An error ocurred during STT transcript call: {str(e)}'))