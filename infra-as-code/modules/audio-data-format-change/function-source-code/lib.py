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
    
    self.metadata['five9_filename'] = hmac.new(self.hash_key, trigger_file.encode(), encoding).hexdigest()
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

  def get_case_manager_from_filename(self, trigger_filename):
    """Uses regex to search for the case manager email
        sets the metadata for case manager email as None if is not found

    Args:
        trigger_filename (str): Raw filename from Five9
    """
    pattern = r'[\w.+-]+@[\w-]+\.[\w.-]+' 

    match = re.search(pattern, trigger_filename)
    self.metadata['case_manager_email'] = match.group(0) if match else None

  def get_create_date_from_filename(self, trigger_filename):
    """Uses regex to find the timestamp from the filename
       expects the filename to be such as: [mm_dd_yyyy]/ [hh_mm_ss APM]

    Args:
        trigger_filename (str): Raw filename from Five9

    Raises:
        Exception: Could not find timestamp in filename
    """
    pattern = r'(\d{1,2}_\d{1,2}_\d{4})/.*@ (\d{1,2}_\d{2}_\d{2} [APM]{2})'

    match = re.search(pattern, trigger_filename)

    if match:
      date_str = match.group(1)  
      time_str = match.group(2)  

      date_obj = datetime.strptime(date_str, "%m_%d_%Y")
      formatted_date = date_obj.strftime("%Y-%m-%d")
      self.create_date = formatted_date
      time_obj = datetime.strptime(time_str, "%I_%M_%S %p")
      formatted_time = time_obj.strftime("%H:%M:%SZ")
      
      self.metadata['create_timestamp'] = f"{formatted_date} {formatted_time}"
    else: 
      raise Exception('Could not find timestamp in filename')

  def get_phone_number_from_filename(self, trigger_filename):
    """Uses regex to retrieve the phone number from filename
       expects the number to be XXXXXXXXXX

    Args:
        trigger_filename (str): Raw filename from Five9

    Raises:
        Exception: Could not find phone number in filename
    """
    encoding = hashlib.sha256

    pattern = r'\d{10}'
    match = re.search(pattern,  trigger_filename)
    if match: 
      patient_phone_number = match.group(0)
      hashed_phone_number = hmac.new(self.hash_key, patient_phone_number.encode(), encoding).hexdigest()
      self.metadata['patient_id'] = hashed_phone_number
    else:
      raise Exception('Could not find phone number in filename')

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
    # self.get_create_date_from_filename(trigger_filename)
    # self.get_phone_number_from_filename(trigger_filename)

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
    entry['hashed_filename'] = self.metadata['five9_filename']

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
    self.get_case_manager_from_filename(trigger_file)

    self.record_keeper = RecordKeeper(self.ingest_record_bucket_id, self.metadata['five9_filename'], self.storage_client)
    
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