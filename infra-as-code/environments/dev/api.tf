variable "gcp_service_list" {
  description ="The list of apis necessary for the project"
  type = list(string)
  default = [
    "cloudresourcemanager.googleapis.com",
    "serviceusage.googleapis.com",
    "cloudfunctions.googleapis.com",
    "logging.googleapis.com",
    "contactcenterinsights.googleapis.com",
    "speech.googleapis.com",
    "bigquery.googleapis.com",
    "workflowexecutions.googleapis.com",
    "workflows.googleapis.com",
    "artifactregistry.googleapis.com",
    "eventarc.googleapis.com",
    "pubsub.googleapis.com",
    "cloudresourcemanager.googleapis.com",
    "cloudbuild.googleapis.com",
    "compute.googleapis.com",
    "dlp.googleapis.com",
    "aiplatform.googleapis.com",
    "cloudscheduler.googleapis.com",
    "dialogflow.googleapis.com"
  ]
}

resource "google_project_service" "gcp_services" {
  for_each = toset(var.gcp_service_list)
  project = var.project_id
  service = each.key
}