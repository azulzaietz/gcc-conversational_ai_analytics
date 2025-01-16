# Copyright 2024 Google LLC
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     https://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

resource "random_id" "bucket_ext" {
  byte_length = 4
}

provider "google" {
  project = "${var.project_id}"
}

data "google_project" "project" {
  project_id = var.project_id
}

#Bucket for the output of the STT Transcript in json format
module "transcript_bucket" {
  source     = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/gcs?ref=v31.1.0&depth=1"
  project_id = var.project_id
  name     = "stt-transcript-${random_id.bucket_ext.id}-${var.env}"
  location = "US"
  versioning = true
}

module "ccai_insights_ingest_pipeline" {
  source = "../../modules/ingest-pipeline"
  project_id = var.project_id
  ccai_insights_project_id = var.ccai_insights_project_id
  region = var.region
  service_account_email = module.ccai_insights_sa.email
  bucket_name = module.formatted_bucket.name
  insights_endpoint = var.insights_endpoint
  insights_api_version = var.insights_api_version
  ccai_insights_location_id = var.ccai_insights_location_id
  pipeline_name = var.pipeline_name
  service_account_id = module.ccai_insights_sa.id
  service_account_id_2 = try(module.ccai_insights_sa_2.id, module.ccai_insights_sa.id) 
  recognizer_path = var.recognizer_path
  stt_function_name = var.stt_function_name
  transcript_bucket_id = module.transcript_bucket.name
  model_name = var.model_name
  genai_function_name = var.genai_function_name
  ingest_record_bucket_id = module.ingest_record_bucket.name
  feedback_generator_function_name = var.feedback_generator_function_name
  dataset_name = var.dataset_name
  feedback_table_name = var.feedback_table_name
  scorecard_id = var.scorecard_id
  redacted_audios_bucket_name = var.redacted_audios_bucket_name
  target_tags = var.target_tags
  target_values = var.target_values

  export_to_bq_function_name = var.export_to_bq_function_name

  bigquery_staging_dataset = "ccai_insights_export"
  bigquery_staging_table = "export_staging"
  bigquery_final_dataset = "ccai_insights_export"
  bigquery_final_table = "export"
  export_to_bq_cron   = "*/15 * * * *"

  client_specific_constraints = var.client_specific_constraints
  client_specific_context = var.client_specific_context
  few_shot_examples = var.few_shot_examples

  depends_on = [ module.ccai_insights_sa, 
                module.ccai_insights_sa_2,
                module.formatted_bucket, 
                resource.google_project_iam_member.gcp_artifact_registry_create,
                resource.google_project_iam_member.gcs_object_admin,
                google_project_service.gcp_services ]
}



# Buckets for the audio formatting cloud function
module "trigger_bucket" {
  source     = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/gcs?ref=v31.1.0&depth=1"
  project_id = var.project_id
  name     = "original-audio-files-${random_id.bucket_ext.id}-${var.env}"
  location = var.region # The trigger must be in the same location as the bucket
  storage_class = "REGIONAL"
  versioning = true
}

module "formatted_bucket" {
  source     = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/gcs?ref=v31.1.0&depth=1"
  project_id = var.project_id
  name     = "formatted-audio-files-${random_id.bucket_ext.id}-${var.env}"
  location = var.region 
  storage_class = "REGIONAL"
  versioning = true
}

module "meta_bucket" {
  source     = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/gcs?ref=v31.1.0&depth=1"
  project_id = var.project_id
  name     = "formatted-audio-metadata-${random_id.bucket_ext.id}-${var.env}"
  location = var.region 
  storage_class = "REGIONAL"
  versioning = true
}

module "redacted_audio_bucket" {
  source     = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/gcs?ref=v31.1.0&depth=1"
  project_id = var.project_id
  name     = var.redacted_audios_bucket_name
  location = var.region 
  storage_class = "REGIONAL"
  versioning = true
}

module "audio_data_format_change" {
  source = "../../modules/audio-data-format-change"
  project_id = var.project_id
  region = var.region
  env = var.env
  service_account_email = module.ccai_insights_sa.email

  function_name = var.audio_format_change_function_name

  formatted_audio_bucket_id = module.formatted_bucket.name
  metadata_bucket_id = module.meta_bucket.name
  ingest_record_bucket_id = module.ingest_record_bucket.name
  number_of_channels = 2
  hash_key = var.hash_secret_name

  trigger_bucket_name = module.trigger_bucket.name
  
  depends_on = [ module.ccai_insights_sa, 
                 resource.google_project_iam_member.gcp_artifact_registry_create,
                 resource.google_project_iam_member.gcs_object_admin,
                 google_project_service.gcp_services ]
}

module "ingest_record_bucket" {
  source     = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/gcs?ref=v31.1.0&depth=1"
  project_id = var.project_id
  name     = "ingest-record-bucket-${random_id.bucket_ext.id}-${var.env}"
  location = var.region 
  storage_class = "REGIONAL"
  versioning = true
}

# Secret manager
module "secret_manager_hash_key" {
  source  = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/secret-manager?ref=v31.1.0&depth=1"
  project_id = var.project_id 

  secrets = {
    (var.hash_secret_name) = {
      locations = null
      keys      = null
    }
  }

  versions = {
    (var.hash_secret_name) = {
      "latest" = {
        enabled = true
        data    = var.hash_key
      }
    }
  }

  depends_on = [ google_project_service.gcp_services ]
}

resource "google_bigquery_connection" "biglake_connection" {
    connection_id = var.bq_external_connection_name
    project = var.project_id
    location = "US"
    cloud_resource {}
}