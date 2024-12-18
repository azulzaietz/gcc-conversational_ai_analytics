import os
import google.auth
import pyarrow.parquet as pq
import pandas as pd
import pyarrow as pa
from datetime import datetime   
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
      self.storage_client = storage.Client(project = self.project_id, credentials = creds)
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
    try:
      retry_policy = retry.Retry(
        initial = 30,
        maximum = 810.0,
        multiplier = 2
      )

      bucket = self.storage_client.bucket(bucket_name)
      blob_name = f'{str(datetime.now().year)}/{filename}'
      blob = bucket.blob(blob_name)

      path_to_file = '/tmp/'+filename
      if os.path.isfile(path_to_file): 
          blob.upload_from_filename(path_to_file, retry = retry_policy)
      print('Uploaded file into gcs')
    except Exception as e:
      raise e

  def upload_record(self, ingest_record_df):
    """Uploads the updated parquet file

    Args:
        ingest_record_df (pandas.DataFrame): dataframe with the record keeper schema
    """
    print('Uploading parquet record file')
    table = pa.Table.from_pandas(ingest_record_df)
    pq.write_table(table, '/tmp/ingest_filename_record.parquet')

    self.upload_to_gcs(bucket_name=self.ingest_record_bucket_id, 
                         filename='ingest_filename_record.parquet') 

  def verify_file(self, case_manager_email):
    """Verifies if parquet file exists, if it doesn't it creates the parquet file
        to later call check_current_file

    Args:
        case_manager_email (str): email of the case manager in the filename

    Returns:
        pandas.DataFrame: updated dataframe
    """
    bucket = self.storage_client.get_bucket(self.ingest_record_bucket_id)
    blob = bucket.blob(f'{str(datetime.now().year)}/ingest_filename_record.parquet')
    
    if blob.exists():
      print('Parquet exists')
      blob.download_to_filename('/tmp/ingest_filename_record.parquet')
      self.ingest_record_df = pd.read_parquet('/tmp/ingest_filename_record.parquet')
    else: 
      print('Parquet does not exists')
      columns = ["occurrence_timestamp", "filename", "includes_case_manager_email", "processed", "error", "error_message"]
      self.ingest_record_df = pd.DataFrame(columns=columns)      

    return self.check_current_file(case_manager_email)

  def add_row(self, row_content):
    """Adds a row to dataframe

    Args:
        row_content (pandas.DataFrame): dataframe with the row

    Returns:
        pandas.DataFrame: updated dataframe
    """
    new_row = pd.DataFrame(row_content)
    self.ingest_record_df = pd.concat([self.ingest_record_df, new_row], ignore_index=True)
    self.upload_record(self.ingest_record_df)
    return self.ingest_record_df

  def create_no_case_manager_record(self):
    """Generates a new row to insert if filename does not include case manager email

    Returns:
        dict: dictionary with current values 
    """
    current_timestamp = datetime.now()
    record = { "occurrence_timestamp": [str(current_timestamp)],
               "filename": [self.five9_filename],
               "includes_case_manager_email": [False],
               "processed": [False],
               "error": [False],
               "error_message": [None] }
    return record

  def create_processed_record(self):
    """Generates a new row to insert if file was processed successfully

    Returns:
        dict: dictionary with current values 
    """
    current_timestamp = datetime.now()
    record = { "occurrence_timestamp": [str(current_timestamp)],
               "filename": [self.five9_filename],
               "includes_case_manager_email": [True],
               "processed": [True],
               "error": [False],
               "error_message": [None] }
    return record

  def create_re_processed_record(self):
    """Generates a new row to replace existing error row if next iteration is successful

    Returns:
        list: list of new values
    """
    current_timestamp = datetime.now()
    return [str(current_timestamp), self.five9_filename, True, True, False, None]

  def create_error_record(self, error_message):
    """Generates a new row to replace existing if error happens

    Args:
        error_message (str): Exception error message

    Returns:
        list: list of new values
    """
    current_timestamp = datetime.now()
    return [str(current_timestamp), self.five9_filename, True, False, True, error_message]

  def replace_row(self, new_row):
    """Replaces the value of a row 

    Args:
        new_row (list): List of new values to replace the row with

    Returns:
        pandas.DataFrame: updated dataframe
    """
    self.ingest_record_df.loc[self.ingest_record_df["filename"] == self.five9_filename] = new_row
    self.upload_record(self.ingest_record_df)
    return self.ingest_record_df

  def check_current_file(self, case_manager_email):
    """Verifies the current filename to see if was processed 
       or complies with business requirements

    Args:
        case_manager_email (str): case manager email

    Raises:
        Exception: No case manager email in filename
        Exception: Repeated file with no case manager email
        Exception: File is processing or was already processed

    Returns:
        pandas.DataFrame: dataframe for the parquet file
    """
    print('Checking if file was already processed')
    if (case_manager_email is None):
      #Ignore and add to parquet and log error
      print('No case manager')
      if(self.five9_filename in self.ingest_record_df["filename"].values):
        raise Exception('Repeated file with no case manager email')
      else:
        raise Exception('No case manager email in filename')
    if (self.five9_filename in self.ingest_record_df["filename"].values):
      if (self.ingest_record_df.loc[self.ingest_record_df["filename"] == self.five9_filename, "processed"].values[0] == True):
        #Ignore and log error
        print('Repeated file')
        raise Exception('File is processing or was already processed')
      else:
        if (self.ingest_record_df.loc[self.ingest_record_df["filename"] == self.five9_filename, "includes_case_manager_email"].values[0] == True):
          print('Will re process file')
          return self.replace_row(self.create_re_processed_record()) 
    else: 
      print('Will process file')
      self.add_row(self.create_processed_record())
      return self.ingest_record_df
  
  