from lib import CCAIHelper


ccai_helper = CCAIHelper(
    ccai_insights_project_id="gsd-ccai-insights-offering",
    ccai_insights_location_id="global",
    bigquery_project_id="gsd-ccai-insights-offering",
    bigquery_staging_dataset="ccai_insights_export",
    bigquery_staging_table="export_staging",
    bigquery_final_dataset="ccai_insights_export",
    bigquery_final_table="export"
)

conversationCountBq = ccai_helper.get_conversation_count_bq()
print(f'conversationCountBq:{conversationCountBq}')

try:
    conversationCountInsights = ccai_helper.get_conversation_count_insights()
    print(f'conversationCountInsights:{conversationCountInsights}')
except requests.exceptions.RequestException as e:
    print(f"Error: {e}")