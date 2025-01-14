#    Copyright 2024 Google LLC

#    Licensed under the Apache License, Version 2.0 (the "License");
#    you may not use this file except in compliance with the License.
#    You may obtain a copy of the License at

#        http://www.apache.org/licenses/LICENSE-2.0

#    Unless required by applicable law or agreed to in writing, software
#    distributed under the License is distributed on an "AS IS" BASIS,
#    WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#    See the License for the specific language governing permissions and
#    limitations under the License.

import os
import json
from google.cloud import storage
import ffmpeg
from google.cloud import dlp
import tempfile

class AudioRedaction:

    def __init__(self, bucket_name, file_name, project_id):
        self.bucket_name = bucket_name
        self.transcript_file_name = file_name
        self.storage_client = storage.Client()
        self.project_id = project_id

    def redact_audio(self, event, redacted_audios_bucket_name):
        """
        Redacts audio based on the provided event data.

        Args:
            event: A dictionary containing information about the audio file.
        """
        
        try:
            json_file = self.download_from_gcs(self.bucket_name, self.transcript_file_name)

            src_bucket_name = event.get("event_bucket")
            audio_file_name = event.get("event_filename")

            print("1) Download original audio from GCS")
            tmp_audio_file = self.download_audio_from_gcs(src_bucket_name, audio_file_name)

            print("2) Call DLP and redact audio file using FFMPEG")
            for result in json_file['results']:

                print("DLP: add findings to transcript")
                redacted_transcript = self.redact_text(result['alternatives'])
                print(redacted_transcript)

                print("Extract intervals for redaction")
                redaction_intervals = self.get_redaction_intervals(result['alternatives'][0])
                print(redaction_intervals)

                self.redact_audio_file(redaction_intervals, tmp_audio_file)

            print("3) Upload redacted audio to corresponding bucket in GCS")
            self.upload_file_to_gcs(redacted_audios_bucket_name, f"/tmp/{tmp_audio_file}", audio_file_name)


            print(json_file)
            with tempfile.NamedTemporaryFile(mode="w", delete=False) as tmp_json_file:
                json.dump(json_file, tmp_json_file, indent=4)
                tmp_json_file_name = tmp_json_file.name

            print("4) Upload modified JSON file to GCS")
            self.upload_file_to_gcs(self.bucket_name, tmp_json_file_name, self.transcript_file_name) 

        except Exception as e:
            print(f"An error occurred: {e}")

    def redact_text(self, data):
        
        data[0]['dlp'] = []

        client = dlp.DlpServiceClient()
        inspect_config = dlp.InspectConfig(
            info_types=
            [
                dlp.InfoType(name="PERSON_NAME"), 
                dlp.InfoType(name="PHONE_NUMBER"),
                dlp.InfoType(name="ORGANIZATION_NAME"),
                dlp.InfoType(name="FIRST_NAME"),
                dlp.InfoType(name="LAST_NAME"),
                dlp.InfoType(name="EMAIL_ADDRESS"),
                dlp.InfoType(name="DATE_OF_BIRTH"),
                dlp.InfoType(name="EMAIL_ADDRESS"),
                dlp.InfoType(name="US_SOCIAL_SECURITY_NUMBER"),
                dlp.InfoType(name="STREET_ADDRESS")
            ],
            include_quote=True
        )
        item = dlp.ContentItem(
            value=data[0]['transcript'],
        )
        request = dlp.InspectContentRequest(
            parent=f"projects/{self.project_id}",  # Correct parent construction
            inspect_config=inspect_config,
            item=item,
        )
        response = client.inspect_content(request=request)
        print(response)

        if response.result.findings:
            for finding in response.result.findings:
                try:
                    if finding.quote:
                        print("Quote: {}".format(finding.quote))
                        data[0]['dlp'].append(finding.quote)
                except AttributeError:
                    pass
            else:
                print("No findings.")

        return data

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
    
    def upload_file_to_gcs(
            self,
            bucket_name,
            source_file_name,
            destination_blob_name
        ):
        """Uploads a local audio file to GCS.

        Args:
            bucket_name: The name of the GCS bucket that will hold the file.
            source_file_name: The name of the source file.
            destination_blob_name: The name of the blob that will be uploaded to GCS.
            project_id: The project ID (not number) to use for redaction.
            impersonated_service_account: The service account to impersonate.
        """
        bucket = self.storage_client.bucket(bucket_name)
        blob = bucket.blob(destination_blob_name)
        blob.upload_from_filename(source_file_name)

        os.remove(source_file_name)
    
    def download_audio_from_gcs(self, src_bucket_name, audio_file_name):
        """Downloads an audio file from Google Cloud Storage to a temporary location.

        Args:
            bucket_id (str): Bucket name
            filename (str): Blob name

        Returns:
            str: audio
        """
        try: 

            bucket = self.storage_client.get_bucket(src_bucket_name)
            blob = bucket.blob(audio_file_name)
            tmp_audio_file = f"{audio_file_name.split("/")[1]}"
            destination_file_name = f"/tmp/{tmp_audio_file}"
            blob.download_to_filename(destination_file_name) 

            # 1. File size comparison
            if os.path.isdir(f'/tmp/{tmp_audio_file}'):
                print(f'Error: {f'/tmp/{tmp_audio_file}'} is a directory, not a file.')
            else:
                file_size = os.path.getsize(f'/tmp/{tmp_audio_file}')
                print(f'File downloaded. Size: {file_size} bytes')

            print('Downloaded audio from gcs')
            return tmp_audio_file
        
        except Exception as e:
            print(f"Error uploading file: {e}")
            return ''

    def redact_audio_file(self, redaction_intervals, tmp_audio_file):
        """Redacts the audio file using ffmpeg."""

        try:

            volume_filters = []
            for element in redaction_intervals:
                filter_str = f"volume=enable='between(t,{element['startOffset'].replace("s", "")},{element['endOffset'].replace("s", "")})':volume=0"
                volume_filters.append(filter_str)

            filter_graph = ",".join(volume_filters)

            if len(volume_filters) == 0:
                return 

            with tempfile.NamedTemporaryFile(suffix='.flac', delete=False) as temp_output:
                temp_output_path = temp_output.name

                (
                    ffmpeg
                    .input(f"/tmp/{tmp_audio_file}")
                    .output(temp_output_path, af=filter_graph)
                    .overwrite_output()
                    .run()
                )

            # Replace the original file with the temporary file
            os.replace(temp_output_path, f"/tmp/{tmp_audio_file}") 

        except ffmpeg.Error as e:
            print(f"Error al procesar el audio: {e}")
        except Exception as e:
            print(f"Error redacting audio file ffmpeg: {e}")
            return ''

    def get_redaction_intervals(self, json_file):
        """Extracts the redaction intervals from the JSON file."""
        redaction_intervals = []
        word_list = [word_item['word'] for word_item in json_file['words']]

        for dlp_entry in json_file['dlp']:
            phrase = dlp_entry.split(' ')
            if len(phrase) >= 2:
                for index, word in enumerate(phrase):
                    for i, element in enumerate(json_file['words']):
                        if i < len(json_file['words']) - 1 and index < len(phrase) - 1:
                            if word == element['word']:
                                if word_list[i:i + len(phrase)] == phrase:
                                    element['index'] = i
                                    found_words = json_file['words'][i:i + len(phrase)]
                                    redaction_intervals.extend(found_words)
            else:
                for index, word in enumerate(phrase):
                    for i, element in enumerate(json_file['words']):
                        if word == element['word']:
                            element['index'] = i
                            redaction_intervals.append(element)
        return redaction_intervals

