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

resource "google_monitoring_notification_channel" "basic" {
  display_name = "CCAI Insights Notification Channel"
  type         = "email"
  labels = {
    email_address = var.alert_email_addresses
  }
}

resource "google_monitoring_alert_policy" "alert_policy_ConversationsPerProjectPerRegion" {
  display_name = "CCAI Insights Quota Monitoring - ConversationsPerProjectPerRegion"
  combiner     = "OR"
  severity = "CRITICAL"
  conditions {
    display_name = "ConversationsPerProjectPerRegion exceeds alert treshold"
    condition_prometheus_query_language {
      query = <<EOT
        max(
          label_replace(
            last_over_time(
              serviceruntime_googleapis_com:quota_allocation_usage{
                project_id='${var.project_id}', 
                monitored_resource='consumer_quota', 
                quota_metric='contactcenterinsights.googleapis.com/conversationsPerRegion', 
                location='${var.ccai_insights_location}'
              }[1d]
            ),
            'limit_name',
            'ConversationsPerProjectPerRegion',
            '',
            ''
          )
        ) 
        by 
        (service,limit_name,project_id,quota_metric,location) 
        / min(
            last_over_time(
              serviceruntime_googleapis_com:quota_limit{project_id='${var.project_id}', 
              monitored_resource='consumer_quota', 
              quota_metric='contactcenterinsights.googleapis.com/conversationsPerRegion', 
              location='${var.ccai_insights_location}', 
              limit_name='ConversationsPerProjectPerRegion'}[1d]
            )
        ) by (service,limit_name,project_id,quota_metric,location)> ${var.alert_treshold}
      EOT
      duration   = var.monitoring_duration
      evaluation_interval = var.monitoring_evaluation_interval
      alert_rule  = "AlwaysOn"
    }
  }

  notification_channels = [google_monitoring_notification_channel.basic.name]
}

resource "google_monitoring_alert_policy" "alert_policy_AnalysesPerProjectPerRegion" {
  display_name = "CCAI Insights Quota Monitoring - AnalysesPerProjectPerRegion"
  combiner     = "OR"
  severity = "CRITICAL"
  conditions {
    display_name = "AnalysesPerProjectPerRegion exceeds alert treshold"
    condition_prometheus_query_language {
      query = <<EOT
        max(
          label_replace(
            last_over_time(
              serviceruntime_googleapis_com:quota_allocation_usage{
                project_id='${var.project_id}', 
                monitored_resource='consumer_quota', 
                quota_metric='contactcenterinsights.googleapis.com/analysesPerRegion', 
                location='${var.ccai_insights_location}'
              }[1d]
            ),
            'limit_name',
            'AnalysesPerProjectPerRegion',
            '',
            ''
          )
        ) 
        by 
        (service,limit_name,project_id,quota_metric,location) 
        / min(
            last_over_time(
              serviceruntime_googleapis_com:quota_limit{project_id='${var.project_id}', 
              monitored_resource='consumer_quota', 
              quota_metric='contactcenterinsights.googleapis.com/analysesPerRegion', 
              location='${var.ccai_insights_location}', 
              limit_name='AnalysesPerProjectPerRegion'}[1d]
            )
        ) by (service,limit_name,project_id,quota_metric,location)> ${var.alert_treshold}
      EOT
      duration   = var.monitoring_duration
      evaluation_interval = var.monitoring_evaluation_interval
      alert_rule  = "AlwaysOn"
    }
  }

  notification_channels = [google_monitoring_notification_channel.basic.name]
}