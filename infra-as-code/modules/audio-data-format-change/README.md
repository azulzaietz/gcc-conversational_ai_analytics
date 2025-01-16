## Create the Buckets
If incoming raw audio files are not in flac file format, format change is required to be ingested by CCAI Speech-to-text. Outputs of the script will be stored in separate buckets different from the landing bucket.

`original-audio-files`: Landing bucket for the raw audio files
`formatted-audio-files`: Intermediate bucket to store formatted audio files
`formatted-audio-metadata`: Intermediate bucket to store formatted audio metadata

Two buckets are needed for the output as CCAI Insights requires metadata to be stored in a different bucket.

## Building permissions
This module is built with [Cloud Foundation Fabric v31.1.0 for Cloud Function v2](https://github.com/GoogleCloudPlatform/cloud-foundation-fabric/tree/v31.1.0/modules/cloud-function-v2) which does not support the variable for an specific service account for building stage. In order to use this variable and avoid giving permissions to the Default compute service please refer to Cloud Foundation Fabric v.34.1.0. 

As this variable is not supported, the default service account used is the Default Compute Service Account, therefore, this account needs to be granted permissions which is done through terraform. Please review the `permissions.tf` file for the following permissions: 
 - `roles/artifactregistry.createOnPushWriter`: Needed to build the cloud function artifact
 - `roles/logging.logWriter`: Needed to log build job status. If this is not enabled and there's an error during the build it will not log the details of the error. 
 - `roles/storage.objectAdmin`: Needed for backend process of the build. 

## Terraform variables

| name | description | type | required | default | example |
|---|---|:---:|:---:|:---:|:---:|
|project_id|Project ID in which the resources will be provisioned|`string`|Yes|||
|region|Region in which the resources will be provisioned|`string`|Yes||`us-central1`|
|formatted_audio_bucket_id|Bucket ID where the formatted audio files will be stored|`string`|Yes||`formatted-audio-files`|
|metadata_bucket_id|Bucket ID where the formatted audio metadata will be stored|`string`|Yes||`formatted-audio-metadata`|
|number_of_channels|Number of channels from the raw audio files|`number`|Yes|`2`||
|service_account_email|Service Account used as identity by the Cloud Function|`string`|Yes|||
|cf_bucket_name|Bucket name to use for storing the Cloud Function bundle|`string`|Yes|||
|function_name|Cloud Function name|`string`|Yes||`audio-format-change`|
|trigger_bucket_name|Name of the bucket which triggers the Cloud Function|`string`|Yes||`original-audio-files`|
|hex_key| Name of the secret in secret manager for the hashing key value| `string` | Yes |  | `original-filename-key` |
|ingest_record_bucket_id|Bucket ID where the parquet for record keeping is|`string`|Yes||`ingest-record-bucket`|