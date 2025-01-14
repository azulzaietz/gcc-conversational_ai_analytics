import pickle
import functions_framework
import os
import google.auth
import google.auth.transport.requests
from google.auth import impersonated_credentials
from google.cloud import contact_center_insights_v1
import google.cloud.dlp_v2
import requests
import json
import os
import time
from google.cloud import storage
import google.auth
import google.auth.transport.requests
import google.cloud.logging
from record import RecordKeeper

class InsightsUploader:
    """
    A class to upload conversations and their transcripts to Contact Center AI Insights.

    Attributes:
        project_id (str): The Google Cloud project ID.
        insights_endpoint (str): The endpoint for the Contact Center AI Insights API.
        insights_api_version (str): The version of the Contact Center AI Insights API.
        ccai_insights_project_id (str): The project ID for CCAI Insights.
        ccai_insights_location_id (str): The location ID for CCAI Insights.
        ingest_record_bucket_id (str): The bucket ID for storing ingestion records.
    """
    def __init__(self, project_id, insights_endpoint, insights_api_version, ccai_insights_project_id, ccai_insights_location_id, ingest_record_bucket_id):
        """
        Initializes InsightsUploader with project and API settings.

        Retrieves an OAuth token for authentication.
        """
        self.project_id = project_id
        self.insights_endpoint = insights_endpoint
        self.insights_api_version = insights_api_version
        self.ccai_insights_project_id = ccai_insights_project_id
        self.ccai_insights_location_id = ccai_insights_location_id
        self.oauth_token = self.get_oauth_token()
        self.ingest_record_bucket_id = ingest_record_bucket_id

    def get_client_credentials(self):
        """
        Retrieves default client credentials for Google Cloud authentication.

        Returns:
            google.auth.credentials.Credentials: The client credentials.
        """
        creds, _ = google.auth.default(
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
        return creds

    def get_oauth_token(self):
        """
        Obtains an OAuth token using client credentials.

        Returns:
            str: The OAuth token.
        """
        creds = self.get_client_credentials()
        auth_req = google.auth.transport.requests.Request()
        creds.refresh(auth_req)
        return creds.token

    def get_gcs_uri(self, bucket, object_name):
        """
        Constructs a Google Cloud Storage URI from bucket and object name.

        Args:
            bucket (str): The bucket name.
            object_name (str): The object name.

        Returns:
            str: The GCS URI.
        """
        return 'gs://{}/{}'.format(bucket, object_name)

    def get_audiofile_metadata(self, bucket_name, object_name):
        """
        Retrieves metadata from a Google Cloud Storage blob.

        Args:
            bucket_name (str): The bucket name.
            object_name (str): The object name.

        Returns:
            dict: The metadata extracted from the blob.

        Raises:
            Exception: If unable to retrieve metadata.
        """
        creds = self.get_client_credentials()
        storage_client = storage.Client(credentials=creds)
        bucket = storage_client.bucket(bucket_name)
        blob = bucket.get_blob(object_name)

        print("Bucket name: {}".format(bucket))
        print("Blob: {}".format(blob))

        if blob.metadata:
            metadata = dict()
            #TODO define agent ID with corresponding value in case it's needed
            metadata['qualityMetadata'] = {"agentInfo":[{"agentId": "Undefined"}]}
            metadata['agentId'] = "Undefined"
            metadata['labels'] = dict()
            if 'five9_filename' in blob.metadata: 
                metadata['labels']['five9_filename'] = blob.metadata['five9_filename']
            if 'patient_id' in blob.metadata:
                metadata['labels']['patient_phone_number'] = blob.metadata['patient_id']
            if 'categories' in blob.metadata:
                metadata['labels']['categories'] = blob.metadata['categories']

            print("Retrieved metadata from file")
            return metadata
        else: 
            raise Exception("Unable to retrieve metadata of agent")

    def log_error(self, operation_message, gcs_audio_uri, gcs_transcript_uri, endpoint_url):
        """
        Logs an error message to Cloud Logging.

        Args:
            operation_message (str): The error message.
            gcs_audio_uri (str): The GCS URI of the audio file.
            gcs_transcript_uri (str): The GCS URI of the transcript file.
            endpoint_url (str): The URL of the API endpoint.
        """
        creds = self.get_client_credentials()
        client = google.cloud.logging.Client(project = self.project_id, credentials = creds)
        logger = client.logger(name="cf_insights_uploader_logger")

        entry = dict()
        entry['function'] = 'An error occurred running the CCAI Insights upload conversation'
        entry['operation_message'] = operation_message
        entry['audio_file_gcs_path'] = gcs_audio_uri
        entry['transcript_file_gcs_path'] = gcs_transcript_uri
        entry['called_endpoint'] = endpoint_url
        
        logger.log_struct(entry,severity="ERROR",)

        print('Error logged')

    def upload_insights_conversation(self, gcs_transcript_uri, metadata, gcs_audio_uri):
        """
        Uploads a conversation to Contact Center AI Insights.

        Args:
            gcs_transcript_uri (str): The GCS URI of the transcript file.
            metadata (dict): Metadata associated with the conversation.
            gcs_audio_uri (str): The GCS URI of the audio file.

        Returns:
            str: The operation name for the upload request.

        Raises:
            Exception: If an error occurs during the upload.
        """
        upload_conversation_url = (
            'https://{}/{}/projects/{}/locations/{}/conversations:upload'
        ).format(self.insights_endpoint, self.insights_api_version, self.ccai_insights_project_id, self.ccai_insights_location_id)
        headers = {
            'charset': 'utf-8',
            'Content-type': 'application/json',
            'Authorization': 'Bearer {}'.format(self.oauth_token),
        }
        data = dict()
        source = {'data_source': {'gcs_source': {'transcript_uri': gcs_transcript_uri, 'audio_uri': gcs_audio_uri} } }
        data['conversation'] = metadata | source if metadata else source
        data['conversation']['call_metadata'] = {'agent_channel':1, 'customer_channel': 2}
        data['conversationId'] = gcs_audio_uri.split('/')[-1].replace('.flac', '')

        r = requests.post(upload_conversation_url, headers=headers, json=data)
        if r.status_code == requests.codes.ok:
            print('Status ok')
            operation = r.json()
            operation_name = r.json()['name']
            return operation_name
        else:
            print('Status not ok')
            try:
                r.raise_for_status()
            except requests.exceptions.RequestException as e:
                print(f'An error occurred running the CCAI Insights upload conversation operation: {e.response.text}')
                raise Exception(f'{e.response.text}')

    def upload(self, event):
        """
        Cloud Function entry point for uploading conversations.

        Processes a Cloud Storage event trigger to upload the corresponding conversation and transcript to CCAI Insights.

        Args:
            event (dict): The Cloud Storage event data.
        """
        transcript_bucket_name = event.get("transcript_bucket")
        transcript_file_name = event.get("transcript_filename")

        event_bucket = event.get("event_bucket")
        event_filename = event.get("event_filename")

        print("Bucket name: {}".format(transcript_bucket_name))
        print("File name: {}".format(transcript_file_name))

        transcript_uri = self.get_gcs_uri(transcript_bucket_name, transcript_file_name)
        audio_uri = self.get_gcs_uri("redacted-audio-files", event_filename)
        metadata = self.get_audiofile_metadata(event_bucket, event_filename)

        record_keeper = RecordKeeper(self.ingest_record_bucket_id, event.get('five9_filename'))

        if not audio_uri:
            print('No audio to ingest')
            return 

        try:
            operation_name = self.upload_insights_conversation(transcript_uri, metadata, audio_uri)
            print('Created operation ID: {}'.format(operation_name))
            record_keeper.replace_row(record_keeper.create_processed_record())
            return operation_name
        except Exception as e:
            upload_conversation_url = ('https://{}/{}/projects/{}/locations/{}/conversations:upload').format(self.insights_endpoint, self.insights_api_version, self.ccai_insights_project_id, self.ccai_insights_location_id)
            self.log_error(str(e), audio_uri, transcript_uri, upload_conversation_url)
            record_keeper.replace_row(
                record_keeper.create_error_record(f'An error ocurred during upload conversation: {str(e)}'))