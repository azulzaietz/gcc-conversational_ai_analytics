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

variable "project_id" {
  type = string
  description = "Project ID in which the resources will be provisioned"
}

variable "region" {
  type = string
  description = "Region in which the resources will be provisioned"
}

variable "formatted_audio_bucket_id" {
  type = string
  description = "Bucket ID where the formatted audio files will be stored"
}

variable "metadata_bucket_id" {
  type = string
  description = "Bucket ID where the formatted audio metadata will be stored"
}

variable "number_of_channels" {
  type = number 
  description = "Number of channels from the raw audio files"
}

variable "service_account_email" {
  type = string
  description = "Service Account used as identity by the Cloud Function"
}

variable "function_name" {
  type = string
  description = "Cloud Function name"
}

variable "trigger_bucket_name" {
  type = string
  description = "Name of the bucket which triggers the Cloud Function"
}

variable "env" {
  type = string
  description = "Name of the environment"
}

variable "hash_key" {
  type = string
  description = "Name of the secret used for the hashing"
}

variable "ingest_record_bucket_id" {
  type = string
  description = "Name of the bucket where parquet file to keep track of processed and failed files"
}