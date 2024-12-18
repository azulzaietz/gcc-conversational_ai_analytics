import os
import google.auth
import pyarrow.parquet as pq
import pandas as pd
import pyarrow as pa
from datetime import datetime
from google.cloud import storage
from google.api_core import retry 

class RecordKeeper:
  ingest_record_bucket_id: str
  five9_filename: str
  storage_client = None
  ingest_record_df = None
  
  def __init__(
    self, 
    ingest_record_bucket_id,
    five9_filename,
    storage_client = None
    ):

    self.ingest_record_bucket_id = ingest_record_bucket_id
    self.five9_filename = five9_filename
    if storage_client is None:
      creds = self.get_credentials()
      self.storage_client = storage.Client(credentials = creds)
    else:
      self.storage_client = storage_client
    
    print('Finished initializing RecordKeeper')

  def get_credentials(self):
    creds, _ = google.auth.default(
        scopes=['https://www.googleapis.com/auth/cloud-platform'])
    
    print('Getting credentials')
    return creds
  
  def upload_to_gcs(self, bucket_name, filename):
    """Uploads a resource to GCS

    Args:
        bucket_name (string): Bucket ID where the filename needs to be uploaded
        filename (string): The name of the local file to upload
    """
    retry_policy = retry.Retry(
      initial = 30,
      maximum = 810.0,
      multiplier = 2
    )

    try:
      bucket = self.storage_client.bucket(bucket_name)
      blob_name = f'{str(datetime.now().year)}/{filename}'
      blob = bucket.blob(blob_name)

      path_to_file = '/tmp/'+filename
      if os.path.isfile(path_to_file): 
          blob.upload_from_filename(path_to_file, retry=retry_policy)
      print('Uploaded file into gcs')
    except Exception as e:
      raise e

  def upload_record(self, ingest_record_df):
    print('Uploading parquet record file')
    table = pa.Table.from_pandas(ingest_record_df)
    pq.write_table(table, '/tmp/ingest_filename_record.parquet')

    self.upload_to_gcs(bucket_name=self.ingest_record_bucket_id, 
                         filename='ingest_filename_record.parquet') 

  def verify_file(self):
    bucket = self.storage_client.get_bucket(self.ingest_record_bucket_id)
    blob = bucket.blob(f'{str(datetime.now().year)}/ingest_filename_record.parquet')
    
    if blob.exists():
      print('Parquet exists')
      blob.download_to_filename('/tmp/ingest_filename_record.parquet')
      self.ingest_record_df = pd.read_parquet('/tmp/ingest_filename_record.parquet')
    else:
      raise Exception('Parquet file could not be found exists')

  def create_error_record(self, error_message):
    current_timestamp = datetime.now()
    return [str(current_timestamp), self.five9_filename, True, False, True, error_message]
  
  def create_processed_record(self):
    current_timestamp = datetime.now()
    return [str(current_timestamp), self.five9_filename, True, True, False, None]

  def replace_row(self, new_row):
    self.verify_file()
    self.ingest_record_df.loc[self.ingest_record_df["filename"] == self.five9_filename] = new_row
    self.upload_record(self.ingest_record_df)
    return self.ingest_record_df