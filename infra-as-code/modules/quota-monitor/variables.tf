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


variable "project_id" {
  type = string
  description = "Project ID in which resources will be deployed"
}

variable "ccai_insights_location" {
  type = string
  description = ""
}

variable "alert_email_addresses" {
  type = string
  description = "List of email addresses that should be alerted"
}

variable "monitoring_duration" {
  type = string
  description = ""
  default = "60s"
}

variable "monitoring_evaluation_interval" {
  type = string
  description = ""
  default = "60s"
}

variable "alert_treshold" {
  type = string
  description = "Alert treshold"
  default = "0.8"
}


