import functions_framework
import os
from lib import CoachingFeedbackGenerator

@functions_framework.http
def main(request):
    request_json = request.get_json()

    project_id = os.environ.get('PROJECT_ID')
    location_id = os.environ.get('LOCATION_ID')
    model_name = os.environ.get('MODEL_NAME')
    insights_endpoint = os.environ.get('INSIGHTS_ENDPOINT')
    insights_api_version = os.environ.get('INSIGHTS_API_VERSION')
    ccai_insights_location_id = os.environ.get('CCAI_INSIGHTS_LOCATION_ID')
    dataset_name = os.environ.get('DATASET_NAME')
    feedback_table_name = os.environ.get('FEEDBACK_TABLE_NAME')
    scorecard_id = os.environ.get('SCORECARD_ID')
    ingest_record_bucket_id = os.environ.get('INGEST_RECORD_BUCKET_ID')
    target_tags = os.environ.get('TARGET_TAGS')
    target_values = os.environ.get('TARGET_VALUES')

    conversation_id = request_json.get("conversation_id")

    generator = CoachingFeedbackGenerator(project_id, location_id, model_name, insights_endpoint,
                                        insights_api_version, ccai_insights_location_id, conversation_id,
                                        dataset_name, feedback_table_name, scorecard_id, ingest_record_bucket_id, 
                                        target_tags, target_values)
    coaching = generator.run()
    print(coaching)
    return coaching
