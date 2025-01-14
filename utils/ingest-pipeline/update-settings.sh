PROJECT_ID="azulz-430521"
LOCATION="us-central1"

# Define your variables
INSPECT_TEMPLATE_ID="2593198440326867511"
INSPECT_TEMPLATE="projects/${PROJECT_ID}/locations/${LOCATION}/inspectTemplates/${INSPECT_TEMPLATE_ID}" 

DEIDENTIFY_TEMPLATE_ID="1806593199587277310"
DEIDENTIFY_TEMPLATE="projects/${PROJECT_ID}/locations/${LOCATION}/deidentifyTemplates/${DEIDENTIFY_TEMPLATE_ID}"

# Print the request body
echo "{\"redactionConfig\":{\"deidentifyTemplate\":\"${DEIDENTIFY_TEMPLATE}\",\"inspectTemplate\":\"${INSPECT_TEMPLATE}\"}}"

# Construct the API endpoint
ENDPOINT="https://contactcenterinsights.googleapis.com/v1/projects/${PROJECT_ID}/locations/${LOCATION}/settings?updateMask=redactionConfig"

# Perform the update request with curl - Update mask: redactionConfig
curl -X PATCH \
  "${ENDPOINT}" \
  -H "Authorization: Bearer $(gcloud auth application-default print-access-token)" \
  -H "Content-Type: application/json" \
  -v \
  -d "{\"redactionConfig\":{\"deidentifyTemplate\":\"${DEIDENTIFY_TEMPLATE}\",\"inspectTemplate\":\"${INSPECT_TEMPLATE}\"}}" \
  --compressed
  

# Check the response code and output
if [[ $? -eq 0 ]]; then
  echo "Settings updated successfully."
else
  echo "Error updating settings."
fi