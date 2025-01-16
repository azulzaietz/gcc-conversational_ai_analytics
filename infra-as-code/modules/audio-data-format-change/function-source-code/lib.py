import os
import uuid
import re
import json
import glob
import google.auth
import google.cloud.logging
import logging
import hashlib
import hmac
from google.cloud import storage
from datetime import datetime
from google.cloud import secretmanager
from record import RecordKeeper

class AudioFormatterRunner:
  project_id: str
  raw_audio_bucket_id: str
  raw_audio_file_name: str
  raw_audio_file_extension: str
  formatted_audio_bucket_id: str
  formatted_audio_file_name: str
  metadata_bucket_id: str
  metadata = dict()
  number_of_channels: int
  hash_key: bytes
  create_date: str
  ingest_record_bucket_id: str

  storage_client = None

  def __init__(
    self, 
    project_id,
    raw_audio_bucket_id,
    raw_audio_file_name, 
    formatted_audio_bucket_id,
    metadata_bucket_id,
    hash_key,
    ingest_record_bucket_id,
    number_of_channels = None
    ):

    self.project_id = project_id
    self.raw_audio_bucket_id = raw_audio_bucket_id
    self.raw_audio_file_name = raw_audio_file_name
    self.formatted_audio_bucket_id = formatted_audio_bucket_id
    self.metadata_bucket_id = metadata_bucket_id
    self.number_of_channels = number_of_channels if number_of_channels else 2
    self.ingest_record_bucket_id = ingest_record_bucket_id

    creds = self.get_credentials()
    self.storage_client = storage.Client(project = self.project_id, credentials = creds)
    secretmanager_client = secretmanager.SecretManagerServiceClient(credentials = creds)

    secret_path = f"projects/{project_id}/secrets/{hash_key}/versions/latest"
    secret_key = secretmanager_client.access_secret_version(name = secret_path).payload.data.decode("UTF-8")
    self.hash_key = bytes.fromhex(secret_key)

  def get_credentials(self):
    creds, _ = google.auth.default(
        scopes=['https://www.googleapis.com/auth/cloud-platform'])
    
    print('Getting credentials')
    return creds

  def get_folder_and_filename(self, blob):
    parts = blob.split("/")

    if (len(parts) != 1):
      filename = parts[-1]         
      folder = parts[-2]   
    else: 
      filename = self.raw_audio_file_name
      folder = ''
    print(f'Got folder name: {folder}, filename: {filename}')
    return f"{folder}/{filename}"

  def download_from_gcs(self):
    """Downloads a specific the triggering blob from the trigger bucket in GCS
        and stores it in a temporary file which is renamed by assigning an UUID 

    Returns:
        string: New filename assigned to the downloaded blob
    """
    print('Starting download')


    encoding = hashlib.sha256

    trigger_file = self.get_folder_and_filename(self.raw_audio_file_name)
    self.raw_audio_file_extension = trigger_file.split('.')[-1]

    new_uuid = str(uuid.uuid4())
    new_filename = f'{new_uuid}.{self.raw_audio_file_extension}'
    
    self.metadata['original_file_name'] = hmac.new(self.hash_key, trigger_file.encode(), encoding).hexdigest()
    self.metadata['conversation_id']= new_uuid

    filename = f'/tmp/{new_filename}'
    print(f'Filename: {self.raw_audio_file_name}. File extension: {self.raw_audio_file_extension}')

    try:
      bucket = self.storage_client.bucket(self.raw_audio_bucket_id)
      blob = bucket.blob(self.raw_audio_file_name)
      blob.download_to_filename(filename)

      print(f'Blob {self.raw_audio_file_name} downloaded to {filename}')
    except Exception as e:
      raise e

    return new_filename, trigger_file

  def upload_to_gcs(self, bucket_name, filename):
    """Uploads a resource to GCS

    Args:
        bucket_name (string): Bucket ID where the filename needs to be uploaded
        filename (string): The name of the local file to upload
    """
    try:
      bucket = self.storage_client.bucket(bucket_name)
      blob_name = f'{self.get_file_creation_date()}/{filename}'
      blob = bucket.blob(blob_name)

      path_to_file = '/tmp/'+filename
      if os.path.isfile(path_to_file): 
          blob.upload_from_filename(path_to_file)

      print('Uploaded file into gcs')
    except Exception as e:
      raise e

  def format_audio(self, filename, trigger_file):
    """Changes the format of the given file to a FLAC file through an ffmpeg command
        system command generates three outputs which are then store in /tmp: 
          .flac, 
          encoding metadata (format-meta.txt)
          log data (ffmpeg-log-data)
        Function then checks for the .flac file, if it exists encoding was successful and calls 
        get_audio_metadata and extract_metadata_from_file. If it doesn't exists encoding failed 
        and calls log_error

    Args:
        filename (string): Name of the downloaded file to encode as flac
    """

    self.formatted_audio_file_name = filename.replace(self.raw_audio_file_extension, 'flac')
    raw_audio_path = '/tmp/' + filename
    formatted_audio_path = '/tmp/' + self.formatted_audio_file_name

    if self.raw_audio_file_extension != 'flac':
      command = f'ffmpeg -hide_banner -i {raw_audio_path} -ac {self.number_of_channels} {formatted_audio_path} -f ffmetadata /tmp/format-meta.txt 2>/tmp/ffmpeg-log-data.txt'
      os.system(command)

    if os.path.isfile(formatted_audio_path) and os.path.getsize(formatted_audio_path) > 0:    
      print(f'Formatted {filename} into {self.formatted_audio_file_name}')
        
      self.get_audio_metadata(formatted_audio_path)
      self.extract_metadata(filename, trigger_file)
      return True

    return False

  def extract_metadata_from_file(self):
    """Extracts metadata from the raw filename, from the ffmpeg encoding log and audio metadata
        by opening each file produced by ffmpeg and reading the contents.
    """
    stream = dict()
    with open('/tmp/audio-meta.txt', 'r') as f:
      content = f.read()
      for line in content.splitlines():
        if 'codec_name' in line:
          stream['codec_name'] = line.split('=')[1].strip()
        elif 'sample_rate' in line:
          stream['sample_rate'] = line.split('=')[1].strip()
        elif 'channels' in line:
          stream['channels'] = line.split('=')[1].strip()
        elif 'channel_layout' in line:
          stream['channel_layout'] = line.split('=')[1].strip()
        elif 'start_time' in line:
          stream['start_time'] = line.split('=')[1].strip()
        elif 'duration' in line:
          stream['duration'] = line.split('=')[1].strip()
        elif 'bits_per_raw_sample' in line:
          stream['bits_per_raw_sample'] = line.split('=')[1].strip()

    self.metadata['stream'] = stream

    file_path = '/tmp/format-meta.txt'
    if os.path.exists(file_path):
      with open(file_path, 'r') as f:
        for line in f:
          if 'encoder' in line:
            self.metadata['encoder'] = line.split('=')[1].strip()

  def get_audio_metadata(self,audio_path):
    """Calls a ffmpeg command to extract the audio metadata, such as streams, sample rate, channels, etc.

    Args:
        audio_path (string): Path to the audio file to extract metadata from
    """
    command = f'ffprobe -loglevel quiet -hide_banner -i {audio_path} -show_streams > /tmp/audio-meta.txt'
    os.system(command)

    print('Extracted stream metadata')

  def get_file_creation_date(self):
    today = datetime.today().date()
    return today.strftime("%m_%d_%y")
  
  def extract_metadata(self, filename, trigger_filename):
    """Extracts metadata from file conversation and original filename

    Args:
        filename (string): Name of the file where metadata will be stored
    """

    self.extract_metadata_from_file()

    filename =  filename.replace(self.raw_audio_file_extension, 'json')

    with open(f'/tmp/{filename}', 'w') as jd:
      json.dump(self.metadata, jd, indent = 2)

    print('Created metadata file')
    print(self.metadata)

  def delete_tmp_files(self):
    """Deletes all tmp files created to free allocated memory
    """
    for filename in os.listdir('/tmp'):
      file_path = os.path.join('/tmp', filename)
      if os.path.isfile(file_path) and filename != 'run':
        os.remove(file_path)
    print('Deleted tmp files')

  def upload_resources(self, filename):
    """Uploads encoded .flac file and its metadata to their respective buckets

    Args:
        filename (string): Name of the downloaded file to encode as flac
    """

    #Upload .flac
    self.upload_to_gcs(self.formatted_audio_bucket_id, self.formatted_audio_file_name)

    #Upload metadata
    filename = filename.replace(self.raw_audio_file_extension, 'json')
    self.upload_to_gcs(self.metadata_bucket_id, filename)
    self.set_blob_metadata()

  def get_ffmpeg_error(self):
    """Retrieves an error from ffmpeg log data if exists
       If it doesn't exists then format change was successful

    Returns:
        str: ffmpeg error message
    """
    with open("/tmp/ffmpeg-log-data.txt", "r") as f:
          error_message = f.read()
          if error_message:
            return error_message

  def get_log_entry(self, error_message):
    entry = dict()
    entry['message'] = 'Audio format change failure'
    entry['error'] = error_message
    entry['raw_file_gcs_path'] = 'gs://{}/{}'.format(self.raw_audio_bucket_id, self.raw_audio_file_name)
    entry['hashed_filename'] = self.metadata['original_file_name']

    return entry

  def log_error(self, error_entry = None, severity = "ERROR"):
    """Logs an error or warning in Cloud Logging if error happens in the cloud function

    Args:
        error_entry (dict, optional): Dictionary with additional data for the log to help troubleshoot. 
          Defaults to None.
        severity (str, optional): Changes the type of log, if it is an error or warning. Defaults to "ERROR".
    """
    creds = self.get_credentials()
    client = google.cloud.logging.Client(project = self.project_id, credentials = creds)
    logger = client.logger(name="cf_audio_format_change_logger")

    if error_entry: 
      entry = self.get_log_entry(error_entry)
      logger.log_struct(entry,severity=severity,)

      print('Error logged')
    else: 
      error_message = self.get_ffmpeg_error()
      entry = self.get_log_entry(error_message)
      logger.log_struct(entry,severity="ERROR",)

      print('Error logged, file format change failed')

  def set_blob_metadata(self):
    """Set a blob's metadata."""
    try: 
      bucket = self.storage_client.bucket(self.formatted_audio_bucket_id)
      blob_name = self.get_file_creation_date() + '/' + self.formatted_audio_file_name
      blob = bucket.get_blob(blob_name)

      metageneration_match_precondition = None

      blob.metadata = self.metadata
      blob.patch()

      print(f"Updated formatted file metadata")
    except Exception as e:
      raise e

  def run_format(self):
    """Runs the format change when the format change is successful 
       it sends the correct payload. 

       Calls verify_file from RecordKeeper to: 
        Verify that filename has a case manager otherwise it will not process and log a warning
        Verify if file was already processed it will log a warning
        Modify the parquet file to keep track of the pipeline step status
    """
    filename, trigger_file = self.download_from_gcs()

    self.record_keeper = RecordKeeper(self.ingest_record_bucket_id, self.metadata['original_file_name'], self.storage_client)
    
    try:
      self.record_keeper.verify_file()
      print(f'New assigned filename: {filename}')
      if(self.format_audio(filename, trigger_file)):
        #Successfully changed format
        print('Changed format')
        self.upload_resources(filename)
      else: 
        #Unsuccessful format change, write on error and delete from processed
        print('Unsucessful')
        self.record_keeper.replace_row(
          self.record_keeper.create_error_record(
            f'An error ocurred while changing audio format: {self.get_ffmpeg_error()}')) 
        self.log_error()
    except Exception as e:
      match str(e):
        # case 'Repeated file with no case manager email':
        #   self.log_error(str(e), "WARNING")
        # case 'File is processing or was already processed':
        #   self.log_error(str(e), "WARNING")
        case _:
          self.record_keeper.replace_row(
            self.record_keeper.create_error_record(
              f'An error ocurred while changing audio format: {str(e)}')) 
          self.log_error(str(e))

    self.delete_tmp_files()
    print("Finished")  