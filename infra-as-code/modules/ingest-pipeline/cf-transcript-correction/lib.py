import os
import json
import glob
import google.auth
import google.auth.transport.requests
import google.cloud.logging
import vertexai
from vertexai.generative_models import GenerativeModel, Part, GenerationConfig
from google.cloud import storage
from record import RecordKeeper

class GenAIFixer:
  project_id: str
  location_id: str
  model_name: str
  transcript_file_name: str
  transcript_bucket_id: str
  formatted_audio_bucket_id: str
  formatted_audio_file_name: str
  prompt: str
  response_schema: str
  gemini_transcript: str
  event_dict = dict()

  storage_client = None

  def __init__(
    self, 
    project_id,
    location_id,
    model_name,
    transcript_bucket_id,
    transcript_file_name,
    formatted_audio_file_name, 
    formatted_audio_bucket_id,
    ingest_record_bucket_id,
    original_file_name,
    client_specific_constraints,
    client_specific_context,
    few_shot_examples
    ):

    self.project_id = project_id
    self.location_id = location_id
    self.model_name = model_name
    self.formatted_audio_bucket_id = formatted_audio_bucket_id
    self.formatted_audio_file_name = formatted_audio_file_name
    self.transcript_bucket_id = transcript_bucket_id
    self.transcript_file_name = transcript_file_name
    self.gemini_transcript = str()

    creds = self.get_credentials()
    self.storage_client = storage.Client(project=self.project_id, credentials=creds)

    self.original_transcript = self.download_from_gcs(self.transcript_bucket_id, self.transcript_file_name)
    self.transcript = self.extract_transcripts(self.original_transcript)

    self.record_keeper = RecordKeeper(ingest_record_bucket_id, original_file_name, self.storage_client)
    self.event_dict['original_file_name'] = original_file_name

    self.client_specific_constraints = client_specific_constraints
    self.client_specific_context = client_specific_context
    self.few_shot_examples = few_shot_examples


    self.prompt = f"""
    <OBJECTIVE_AND_PERSONA>
      You are an expert audio transcription editor. Your primary goal is to correct errors in transcripts while preserving the original JSON format. You have a strong understanding of the provided terminology and are familiar with common transcription challenges.
    </OBJECTIVE_AND_PERSONA>

    <INSTRUCTIONS>
      You will receive an audio file and its corresponding transcript in JSON format. Your job is to:
      1. Carefully listen to the entire audio file.
      2. Review the entire transcript provided.
      3. Compare, Identify and correct any discrepancies between the audio and the transcript. Pay close attention to:
          * **Key Terms:** Ensure accuracy in transcribing all key terms, names, and phrases specific to the client.  
          * **Speaker Misattribution:** Correctly identify and label different speakers.
          * **General Errors:** Fix misspellings, grammatical errors, and any other inaccuracies.
          * **Keep the fillers:** Keep any fillers used. Example: "Mhm"
      3. Preserve the original JSON structure, including all key-value pairs, nesting, and formatting. Only the text content within the transcript should be modified, keep the same amount of objects in the input transcript.

    </INSTRUCTIONS>

    <CONSTRAINTS>
    Dos and don'ts for the following aspects:
      {self.client_specific_constraints}
    </CONSTRAINTS>

    <CONTEXT>
      {self.client_specific_context}
    </CONTEXT>

    <FEW_SHOT_EXAMPLES>
      Example of transcripts with correct terminology:
        {self.few_shot_examples}
    </FEW_SHOT_EXAMPLES>

    <INPUTS>
      Transcript: {self.transcript} 
    </INPUTS>

    <OUTPUTS>
      Return the transcript with the correct response_schema
    </OUTPUTS>

    Remember that before you answer, you must check to see if the answer complies with your mission. If not, you must respond, "I am not able to answer this question"
    """

    self.response_schema = {
    "type": "array",
    "items": {
        "type": "object",
        "properties": {
            "index": {
                "type": "integer",
                "description": "Index position of the transcript"
            },
            "transcript": {
                "type": "string",
                "description": "The transcript text"
            },
            "channelTag": {
                "type": "integer",
                "description": "Channel identifier"
            }
        },
        "required": ["index", "transcript", "channelTag"]
        }
    }

    print(f'Starting transcript fix on: {self.transcript_file_name}')
    print(f'Using prompt: {self.prompt}')

  def get_credentials(self):
    creds, _ = google.auth.default(
        scopes=['https://www.googleapis.com/auth/cloud-platform'])
    
    print('Getting credentials')
    return creds
  
  def get_oauth_token(self):
    creds = self.get_client_credentials()
    auth_req = google.auth.transport.requests.Request()
    creds.refresh(auth_req)
    return creds.token

  def get_gcs_uri(self, bucket, object_name):
    return 'gs://{}/{}'.format(bucket, object_name)


  def download_from_gcs(self, bucket_id, filename):
    """Downloads transcript contents from GCS

    Args:
        bucket_id (str): Bucket name
        filename (str): Blob name

    Returns:
        str: Transcript
    """
    bucket = self.storage_client.get_bucket(bucket_id)
    blob = bucket.blob(filename)

    content = blob.download_as_text()
    json_data = json.loads(content)

    print('Downloaded transcript from gcs')
    return json_data

  def upload_json_to_gcs(self, bucket_name, filename, transcript):
    """Uploads the fixed transcript to GCS

    Args:
        bucket_name (str): Bucket name
        filename (str): Blob name
        transcript (dict): Output transcript by Gemini
    """
    bucket = self.storage_client.bucket(bucket_name)
    blob = bucket.blob(filename)

    json_data = json.dumps(transcript,indent=2)
    blob.upload_from_string(json_data, content_type='application/json')

    print(f"File {filename} uploaded to {bucket_name}.")

  def transcript_word_fix(self):
    """Initializes the VertexAI client to start transcript word fix

    Raises:
        e: Could fail when loading the json string or response does not include valid items
    """
    print('Starting Vertex Client')
    creds = self.get_credentials()
    vertexai.init(project=self.project_id, location=self.location_id, credentials=creds)

    model = GenerativeModel(self.model_name)

    prompt = self.prompt

    audio_file_uri = self.get_gcs_uri(self.formatted_audio_bucket_id, self.formatted_audio_file_name)
    audio_file = Part.from_uri(audio_file_uri, mime_type="audio/flac")

    contents = [audio_file, prompt]
    
    token_number = model.count_tokens(prompt)

    if token_number.total_tokens > 8193:
      print('Too many tokens')
      return 

    print('Calling API')
    response = model.generate_content(contents,
                                      generation_config=GenerationConfig(
                                        temperature=0,
                                        response_mime_type="application/json",
                                        response_schema=self.response_schema
                                        )
                                      )
   
    fixed_transcript = rf'{response.text}'
    print(fixed_transcript)

    try:
      fixed_transcript = json.loads(fixed_transcript)
      if response.text != "I am not able to answer this question" or response.candidate.finish_reason != "MAX_TOKENS":
        if len(self.transcript) == len(fixed_transcript):
          self.update_transcript(self.original_transcript, fixed_transcript)
          self.upload_json_to_gcs(self.transcript_bucket_id, self.transcript_file_name, self.gemini_transcript)
      else: 
        print('Will use original transcript')
        return
    except Exception as e:
        raise e

  def extract_transcripts(self, stt_transcript):
    """Loops through whole transcript and ignores offsets, keeps 
       only the transcript, channel and its index

    Args:
        stt_transcript (dict): STT transcription downloaded from GCS

    Returns:
        list[dict]: List of dictionaries with transcript values
    """
    transcripts = []
    for i, results in enumerate(stt_transcript['results']): 
        transcripts.append({"index": i, "transcript": results["alternatives"][0]["transcript"], "channelTag": results["channelTag"]})
    return transcripts

  def update_transcript(self, original_transcript, fixed_transcript):
    """Updates the existing transcript with the fixed transcript from Gemini

    Args:
        original_transcript (dict): STT transcription downloaded from GCS
        fixed_transcript (list[dict]): List of dictionaries 
    """
    for i, results in enumerate(original_transcript['results']): 
      if results["alternatives"][0]["transcript"] != fixed_transcript[i]['transcript']:
        results["alternatives"][0]["transcript"] = fixed_transcript[i]['transcript']
    self.gemini_transcript = original_transcript

  def log_error(self, exception_message):
    """Logs an error in Cloud Logging

    Args:
        exception_message (str): Exception message to log as error
    """
    creds = self.get_credentials()
    client = google.cloud.logging.Client(project = self.project_id, credentials = creds)
    logger = client.logger(name="cf_genai_word_fix_logger")

    entry = dict()
    entry['message'] = 'An error ocurred when using GenAI to fix business words'
    entry['exception_message'] = exception_message
    entry['audio_file_gcs_path'] = 'gs://{}/{}'.format(self.formatted_audio_bucket_id, self.formatted_audio_file_name)
    entry['original_transcript_file_gcs_path'] = 'gs://{}/{}'.format(self.transcript_bucket_id, self.transcript_file_name)
    entry['gemini_transcript'] = self.gemini_transcript

    logger.log_struct(entry,severity="ERROR",)

    print('Error logged')

  def fix(self):
    """Calls the transcript fix and audio categorization
        Sets the HTTP response. Calls the RecordKeeper and error logger 
        if there is an error during transcription

    Returns:
        _type_: _description_
    """
    try:
      self.transcript_word_fix()
      print('Finished')
      self.event_dict['transcript_bucket'] = self.transcript_bucket_id
      self.event_dict['transcript_filename'] = self.transcript_file_name
      self.event_dict['event_bucket'] = self.formatted_audio_bucket_id
      self.event_dict['event_filename'] = self.formatted_audio_file_name
      self.record_keeper.replace_row(self.record_keeper.create_processed_record())
      return self.event_dict
    except Exception as e:
      self.log_error(str(e)) 
      self.record_keeper.replace_row(
      self.record_keeper.create_error_record(f'An error ocurred during GenAI transcript fix: {str(e)}'))