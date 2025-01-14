# Copyright 2024 Google LLC
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#     http://www.apache.org/licenses/LICENSE-2.0
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

locals {
  timeout_seconds = 3600
  scheduler_timeout = 1800
}

resource "random_string" "random" {
    length  = 5
    special = false
    lower   = true
}

data "local_file" "orchestration" {
  filename = "${path.module}/workflow/orchestration.yaml"
}

data "google_service_account" "ccai_insights_sa" {
  account_id = var.service_account_id
}

data "google_service_account" "ccai_insights_sa_2" {
  account_id = var.service_account_id_2
}

resource "google_eventarc_trigger" "primary" {
    name = var.pipeline_name
    location = var.region

    service_account = var.service_account_email

    matching_criteria {
        attribute = "type"
        value = "google.cloud.storage.object.v1.finalized"
    }

    matching_criteria {
        attribute = "bucket"
        value = var.bucket_name
    }

    destination {
        workflow = google_workflows_workflow.orchestration.id
    }
}

resource "google_workflows_workflow" "orchestration" {
    project = var.project_id
    name            = var.pipeline_name
    region          = var.region
    service_account = data.google_service_account.ccai_insights_sa.id

    source_contents = data.local_file.orchestration.content

    user_env_vars = {
        cf_ccai_conversation_upload_url = module.cf_conversation_upload.uri
        cf_genai_url = module.cf_genai_transcript_fix.uri
        cf_stt_url = module.cf_stt_transcript.uri
        cf_feedback_generator_url = module.cf_feedback_generator.uri
        cf_audio_redaction_url = module.cf_audio_redaction.uri
        insights_endpoint = var.insights_endpoint
    }

    depends_on = [ module.cf_conversation_upload ]
}

module "cf_bundle_bucket" {
  source     = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/gcs?ref=v31.1.0&depth=1"
  project_id = var.project_id
  name       = "cf-bucket-${random_string.random.result}"
  location   = "US"
  versioning = true
}

module "cf_conversation_upload" {
  source      = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/cloud-function-v2?ref=v31.1.0&depth=1"
  project_id  = var.project_id
  region      = var.region
  name        = var.pipeline_name
  bucket_name = module.cf_bundle_bucket.name
  bundle_config = {
    source_dir  = "${path.module}/cf-ccai-conversation-upload"
    output_path = "${path.module}/cf-ccai-conversation-upload/bundle.zip"
  }
  service_account = data.google_service_account.ccai_insights_sa.email

  function_config = {
    timeout_seconds = local.timeout_seconds
    instance_count  = 250
    memory_mb = 2048
    cpu = "1"
  }

  environment_variables = {
    PROJECT_ID = var.project_id
    INSIGHTS_ENDPOINT = var.insights_endpoint
    INSIGHTS_API_VERSION = var.insights_api_version
    CCAI_INSIGHTS_PROJECT_ID = var.ccai_insights_project_id
    CCAI_INSIGHTS_LOCATION_ID = var.ccai_insights_location_id
    INGEST_RECORD_BUCKET_ID = var.ingest_record_bucket_id
    REDACTED_AUDIOS_BUCKET_NAME = var.redacted_audios_bucket_name
  }
}

resource "google_data_loss_prevention_inspect_template" "custom" {
    parent = "projects/${var.project_id}/locations/${var.region}"
    description = "DLP inspection template"
    display_name = "inspect_template"

    inspect_config {

        info_types {
            name = "AGE"
        }
        info_types {
            name = "BLOOD_TYPE"
        }
        info_types {
            name = "CREDIT_CARD_NUMBER"
        }
        info_types {
            name = "DATE_OF_BIRTH"
        }
        info_types {
            name = "EMAIL_ADDRESS"
        }
        info_types {
            name = "FEMALE_NAME"
        }
        info_types {
            name = "FINANCIAL_ACCOUNT_NUMBER"
        }
        info_types {
            name = "FIRST_NAME"
        }
        info_types {
            name = "GENDER"
        }
        info_types {
            name = "LAST_NAME"
        }
        info_types {
            name = "LOCATION_COORDINATES"
        }
        info_types {
            name = "MALE_NAME"
        }
        info_types {
            name = "MARITAL_STATUS"
        }
        info_types {
            name = "MEDICAL_RECORD_NUMBER"
        }
        info_types {
            name = "PERSON_NAME"
        }
        info_types {
            name = "PHONE_NUMBER"
        }
        info_types {
            name = "STREET_ADDRESS"
        }
        info_types {
            name = "US_HEALTHCARE_NPI"
        }
        info_types {
            name = "US_MEDICARE_BENEFICIARY_ID_NUMBER"
        }
        info_types {
            name = "US_SOCIAL_SECURITY_NUMBER"
        }
        info_types {
            name = "US_STATE"
        }
        info_types {
            name = "US_TOLLFREE_PHONE_NUMBER"
        }

        rule_set {
            info_types {
                name = "PERSON_NAME"
            }
            info_types {
                name = "FIRST_NAME"
            }
            info_types {
                name = "LAST_NAME"
            }
            rules {
                exclusion_rule {
                    dictionary {
                        word_list {
                            words = [""]
                        }
                    }
                    matching_type = "MATCHING_TYPE_FULL_MATCH"
                }
            }
        }

        custom_info_types {
            info_type {
                name = "SPELLED_NAME"
            }

            regex {
                pattern = "[A-Z][A-Z-]+"
            }
        }

        custom_info_types {
            info_type {
                name = "EMAIL_AT"
            }

            regex {
                pattern = "[\\w.-]+ ?(at) ?[\\w.-]+\\.[a-z]+"
            }
        }

        custom_info_types {
            info_type {
                name = "NUMBERS_SEPARATED_BY_SLASH"
            }

            regex {
                pattern = "\\d+(?:/\\d+)+"
            }
        }

        include_quote = true
        
    }
}

resource "google_data_loss_prevention_deidentify_template" "basic" {
    parent = "projects/${var.project_id}/locations/${var.region}"
    description = "DLP de-identification template"
    display_name = "deidentification_template"

    deidentify_config {
        info_type_transformations {
            transformations {
                info_types {
                    name = "AGE"
                }
                info_types {
                    name = "BLOOD_TYPE"
                }
                info_types {
                    name = "CREDIT_CARD_NUMBER"
                }
                info_types {
                    name = "DATE_OF_BIRTH"
                }
                info_types {
                    name = "EMAIL_ADDRESS"
                }
                info_types {
                    name = "FEMALE_NAME"
                }
                info_types {
                    name = "FINANCIAL_ACCOUNT_NUMBER"
                }
                info_types {
                    name = "FIRST_NAME"
                }
                info_types {
                    name = "GENDER"
                }
                info_types {
                    name = "LAST_NAME"
                }
                info_types {
                    name = "LOCATION_COORDINATES"
                }
                info_types {
                    name = "MALE_NAME"
                }
                info_types {
                    name = "MARITAL_STATUS"
                }
                info_types {
                    name = "MEDICAL_RECORD_NUMBER"
                }
                info_types {
                    name = "PERSON_NAME"
                }
                info_types {
                    name = "PHONE_NUMBER"
                }
                info_types {
                    name = "STREET_ADDRESS"
                }
                info_types {
                    name = "US_HEALTHCARE_NPI"
                }
                info_types {
                    name = "US_MEDICARE_BENEFICIARY_ID_NUMBER"
                }
                info_types {
                    name = "US_SOCIAL_SECURITY_NUMBER"
                }
                info_types {
                    name = "US_STATE"
                }
                info_types {
                    name = "US_TOLLFREE_PHONE_NUMBER"
                }
                info_types {
                    name = "SPELLED_NAME"
                }
                info_types {
                    name = "EMAIL_AT"
                }
                info_types {
                    name = "NUMBERS_SEPARATED_BY_SLASH"
                }


                primitive_transformation {
                    replace_with_info_type_config = true
                }
            }

        }
    }
}

# STT Transcript Cloud Function
resource "random_id" "bucket_ext" {
  byte_length = 4
}

module "cf_stt_bundle_bucket" {
  source     = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/gcs?ref=v31.1.0&depth=1"
  project_id = var.project_id
  name       = "cf-bucket-${random_id.bucket_ext.id}"
  location   = "US"
  versioning = true
}

module "cf_stt_transcript" {
  source      = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/cloud-function-v2?ref=v31.1.0&depth=1"
  project_id  = var.project_id
  region      = var.region
  name        = var.stt_function_name
  bucket_name = module.cf_stt_bundle_bucket.name
  bundle_config = {
    source_dir  = "${path.module}/cf-stt-transcript"
    output_path = "${path.module}/cf-stt-transcript/bundle.zip"
  }
  service_account = data.google_service_account.ccai_insights_sa.email

  function_config = {
    timeout_seconds = local.timeout_seconds
    instance_count  = 250
    runtime = "python312"
    memory_mb = 2048
    cpu = "1"
  }

  environment_variables = {
    PROJECT_ID = var.project_id
    TRANSCRIPT_BUCKET_ID = var.transcript_bucket_id
    RECOGNIZER_PATH = var.recognizer_path
    INGEST_RECORD_BUCKET_ID = var.ingest_record_bucket_id
  }
}

# GenAI Cloud function business key word fix
resource "random_id" "genai_bucket_ext" {
  byte_length = 4
}

module "cf_genai_bundle_bucket" {
  source     = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/gcs?ref=v31.1.0&depth=1"
  project_id = var.project_id
  name       = "cf-bucket-${random_id.genai_bucket_ext.id}"
  location   = "US"
  versioning = true
}

module "cf_genai_transcript_fix" {
  source      = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/cloud-function-v2?ref=v31.1.0&depth=1"
  project_id  = var.project_id
  region      = var.region
  name        = var.genai_function_name
  bucket_name = module.cf_genai_bundle_bucket.name
  bundle_config = {
    source_dir  = "${path.module}/cf-transcript-correction"
    output_path = "${path.module}/cf-transcript-correction/bundle.zip"
  }
  service_account = data.google_service_account.ccai_insights_sa.email

  function_config = {
    timeout_seconds = local.timeout_seconds
    entry_point = "main"
    runtime = "python312"
    memory_mb = 2048
    cpu = "1"
    instance_count  = 250
  }

  environment_variables = {
    PROJECT_ID = var.project_id
    LOCATION_ID = var.region
    MODEL_NAME = var.model_name
    INGEST_RECORD_BUCKET_ID = var.ingest_record_bucket_id
    CLIENT_SPECIFIC_CONSTRAINTS = var.client_specific_constraints
    CLIENT_SPECIFIC_CONTEXT = var.client_specific_context
    FEW_SHOT_EXAMPLES = var.few_shot_examples
  }
}

resource "random_id" "export_to_bq_bundle_ext" {
  byte_length = 4
}

module "cf_export_to_bq_bundle_bucket" {
  source     = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/gcs?ref=v31.1.0&depth=1"
  project_id = var.ccai_insights_project_id
  name       = "cf-bucket-${random_id.export_to_bq_bundle_ext.id}"
  location   = "US"
  versioning = true
}

module "cf_export_to_bq" {
  source      = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/cloud-function-v2?ref=v31.1.0&depth=1"
  project_id  = var.ccai_insights_project_id
  region      = var.ccai_insights_location_id
  name        = var.export_to_bq_function_name
  bucket_name = module.cf_export_to_bq_bundle_bucket.name
  bundle_config = {

    source_dir = "${path.module}/cf-export-to-bq-incremental"
    output_path = "${path.module}/cf-export-to-bq-incremental/bundle.zip"
    excludes     = ["__pycache__"]
  }
  service_account = data.google_service_account.ccai_insights_sa_2.email

  function_config = {
    timeout_seconds = local.timeout_seconds
    memory_mb = 8192
    cpu = "2"
  }

  environment_variables = {
    CCAI_INSIGHTS_PROJECT_ID = var.ccai_insights_project_id
    CCAI_INSIGHTS_LOCATION_ID = var.ccai_insights_location_id
    BIGQUERY_PROJECT_ID = var.ccai_insights_project_id
    BIGQUERY_STAGING_DATASET = var.bigquery_staging_dataset
    BIGQUERY_STAGING_TABLE = var.bigquery_staging_table
    BIGQUERY_FINAL_DATASET = var.bigquery_final_dataset
    BIGQUERY_FINAL_TABLE = var.bigquery_final_table
    INSIGHTS_ENDPOINT = var.insights_endpoint
    INSIGHTS_API_VERSION = var.insights_api_version
  }
}

resource "google_cloud_scheduler_job" "ccai_to_bq_scheduler" {
  name     = "${var.export_to_bq_function_name}-scheduler"
  project = var.ccai_insights_project_id
  region = var.ccai_insights_location_id
  schedule = var.export_to_bq_cron
  description = "Schedule to export CCAI Insights conversations to BigQuery"
  attempt_deadline = "${local.scheduler_timeout}s" #30 minutes
  retry_config {
      retry_count = 3
  }
  http_target {
    uri         = module.cf_export_to_bq.uri
    http_method = "POST"
    oidc_token {
        audience              = "${module.cf_export_to_bq.uri}/"
        service_account_email = data.google_service_account.ccai_insights_sa_2.email
    }
  }
}

module "cf_feedback_generator" {
  source      = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/cloud-function-v2?ref=v31.1.0&depth=1"
  project_id  = var.project_id
  region      = var.region
  name        = var.feedback_generator_function_name
  bucket_name = module.cf_bundle_bucket.name
  bundle_config = {
    source_dir  = "${path.module}/cf-feedback-generator"
    output_path = "${path.module}/cf-feedback-generator/bundle.zip"
  }
  service_account = data.google_service_account.ccai_insights_sa.email

  function_config = {
    timeout_seconds = local.timeout_seconds
    instance_count  = 250
    memory_mb = 8192
    cpu = "2"
  }

  environment_variables = {
    PROJECT_ID = var.project_id,
    INSIGHTS_ENDPOINT = var.insights_endpoint,
    INSIGHTS_API_VERSION = var.insights_api_version,
    CCAI_INSIGHTS_LOCATION_ID = var.ccai_insights_location_id,
    LOCATION_ID = var.region,
    MODEL_NAME = var.model_name,
    DATASET_NAME = var.dataset_name,
    FEEDBACK_TABLE_NAME = var.feedback_table_name,
    SCORECARD_ID = var.scorecard_id
    INGEST_RECORD_BUCKET_ID = var.ingest_record_bucket_id
    TARGET_TAGS = var.target_tags
    TARGET_VALUES = var.target_values
  }
}

resource "google_project_iam_member" "ccai_insights_editor" {
  project = var.ccai_insights_project_id
  role    = "roles/contactcenterinsights.editor"
  member  = "serviceAccount:${data.google_service_account.ccai_insights_sa.email}"
}


# Audio Redaction Cloud Function
resource "random_id" "audio_redaction_bucket_ext" {
  byte_length = 4
}

module "cf_audio_redaction_bundle_bucket" {
  source     = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/gcs?ref=v31.1.0&depth=1"
  project_id = var.project_id
  name       = "cf-bucket-${random_id.audio_redaction_bucket_ext.id}"
  location   = "US"
  versioning = true
}

module "cf_audio_redaction" {
  source      = "github.com/GoogleCloudPlatform/cloud-foundation-fabric//modules/cloud-function-v2?ref=v31.1.0&depth=1"
  project_id  = var.project_id
  region      = var.region
  name        = var.audio_redaction_function_name
  bucket_name = module.cf_audio_redaction_bundle_bucket.name
  bundle_config = {
    source_dir  = "${path.module}/cf-audio-redaction"
    output_path = "${path.module}/cf-audio-redaction/bundle.zip"
  }
  service_account = data.google_service_account.ccai_insights_sa.email

  function_config = {
    timeout_seconds = local.timeout_seconds
    instance_count  = 250
    runtime = "python312"
    memory_mb = 2048
    cpu = "1"
  }

  environment_variables = {
    PROJECT_ID = var.project_id
    TRANSCRIPT_BUCKET_ID = var.transcript_bucket_id
    REDACTED_AUDIOS_BUCKET_NAME = var.redacted_audios_bucket_name
  }
}