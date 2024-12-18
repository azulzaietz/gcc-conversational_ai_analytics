import os
import json
import google.auth
import google.auth.transport.requests
import requests
import vertexai
import google.cloud.logging
from vertexai.generative_models import GenerativeModel, GenerationConfig
from google.cloud import storage
from google.cloud import bigquery
from datetime import datetime
from record import RecordKeeper

class CoachingFeedbackGenerator:
    def __init__(self, project_id, location_id, model_name, insights_endpoint, 
                 insights_api_version, ccai_insights_location_id, conversation_id,
                 dataset_name, table_name, scorecard_id, ingest_record_bucket_id, 
                 target_tags, target_values):
        self.project_id = project_id
        self.location_id = location_id
        self.model_name = model_name
        self.insights_endpoint = insights_endpoint
        self.insights_api_version = insights_api_version
        self.ccai_insights_location_id = ccai_insights_location_id
        self.conversation_id = conversation_id
        self.creds = self.get_credentials()
        self.oauth_token = self.get_oauth_token()
        vertexai.init(project=self.project_id, location=self.location_id, credentials=self.creds)
        self.model = GenerativeModel(model_name)
        self.dataset_name = dataset_name
        self.table_name = table_name
        self.scorecard_id = scorecard_id
        self.ingest_record_bucket_id = ingest_record_bucket_id
        self.target_tags = target_tags.split(",")
        self.target_values = target_values.split(",")

        self.storage_client = storage.Client(project=self.project_id, credentials=self.creds)

    def get_credentials(self):
        creds, _ = google.auth.default(scopes=['https://www.googleapis.com/auth/cloud-platform'])
        return creds

    def get_oauth_token(self):
        auth_req = google.auth.transport.requests.Request()
        self.creds.refresh(auth_req)
        return self.creds.token

    def get_transcript(self):
        """Calls the CCAI endpoint to download the transcript

        Returns:
            dict: CCAI stored transcript
        """
        ccai_conversation_url = (
            'https://{}/{}/projects/{}/locations/{}/conversations/{}'
        ).format(self.insights_endpoint, self.insights_api_version, self.project_id, 
                 self.ccai_insights_location_id, self.conversation_id)
        headers = {
            'charset': 'utf-8',
            'Content-type': 'application/json',
            'Authorization': 'Bearer {}'.format(self.oauth_token),
            }
        r = requests.get(ccai_conversation_url, headers=headers)
        return json.loads(r.text)

    def log_error(self, exception_message):
        """Logs an error in Cloud Logging

        Args:
            exception_message (str): Exception error message
        """
        creds = self.creds
        client = google.cloud.logging.Client(project = self.project_id, credentials = creds)
        logger = client.logger(name="cf_feedback_generator_logger")

        entry = dict()
        entry['message'] = 'An error ocurred when using GenAI to generate coaching feedback'
        entry['exception_message'] = exception_message
        entry['conversation_id'] = self.conversation_id
        entry['ccai_insights_endpoint'] = self.insights_endpoint
        entry['ccai_insights_version'] = self.insights_api_version
        entry['ccai_insights_location'] = self.ccai_insights_location_id
        
        logger.log_struct(entry,severity="ERROR",)

        print('Error logged')

    def get_latest_revision(self):
        """Gets the latests version of the scorecard for QAI

        Returns:
            str: version id
        """
        try:
            url = (
                'https://{}/{}/projects/{}/locations/{}/qaScorecards/{}/revisions'
                ).format(self.insights_endpoint, self.insights_api_version, self.project_id, self.ccai_insights_location_id, self.scorecard_id)

            headers = {
                'charset': 'utf-8',
                'Content-type': 'application/json',
                'Authorization': 'Bearer {}'.format(self.oauth_token),
            }
            r = requests.get(url, headers=headers)

            response_text = json.loads(r.text)

            most_recent_revision = max(
                response_text['qaScorecardRevisions'],
                key=lambda x: datetime.fromisoformat(x['createTime'].replace('Z', '+00:00'))
            )

            return most_recent_revision['name'].split("/")[-1]

        except Exception as e:
            print("An error occurred while requesting the latest revision ID: {}".format(e))

    def get_qa_questions(self):
        """Gets all the questions from the scorecard

        Returns:
            dict: dictionary with the questions as key and the instructions as values
        """

        latest_revision_id = self.get_latest_revision()

        ccai_conversation_url = (
            'https://{}/{}/projects/{}/locations/{}/qaScorecards/{}/revisions/{}/qaQuestions'
        ).format(self.insights_endpoint, self.insights_api_version, self.project_id, 
                 self.ccai_insights_location_id, self.scorecard_id, latest_revision_id)

        headers = {
            'charset': 'utf-8',
            'Content-type': 'application/json',
            'Authorization': 'Bearer {}'.format(self.oauth_token),
            }
        r = requests.get(ccai_conversation_url, headers=headers)

        response_text = json.loads(r.text)

        qaQuestions = dict()
        for question in response_text['qaQuestions']:
            qaQuestions[question['questionBody']] = {"instructions": f"{question['answerInstructions']}"}

        return qaQuestions

    def extract_questions(self, qa_questions):
        """
        Extracts questions from a CCAI conversation based on provided criteria.

        Args:
            qa_questions (dict): Dictionary with the questions as key and the 
                                    instructions as values.
            target_tags (list): List of tags to filter questions.
            target_values (list): List of answer values to exclude.

        Returns:
            Tuple(dict, list): Dictionary of feedback structure and list of questions.
        """
        questions_feedback = dict()
        questions_list = []
        results = []

        for question in qa_questions:
            if any(tag in question['tags'] for tag in self.target_tags):
                if 'naValue' in question['answerValue']:
                    continue
                if question['answerValue']['boolValue'] not in self.target_values:
                    question_content = {
                        'conversation_id': question['conversation'],
                        'question_id': question['qaQuestion'],
                        'question': question['questionBody'],
                        'feedback': None
                    }
                    results.append(question_content)
                    questions_list.append(question['questionBody'])

        questions_feedback['results'] = results
        return questions_feedback, questions_list

    def generate_prompt(self, transcript, subset_questions, questions_feedback):
        """From the CCAI conversation it extracts the QAI evaluation scores
           where it is only Yes (1) or No (0)

        Args:
            transcript (dict): dictionary with the transcript from CCAI
            subset_questions (dict): dictionary with the questions and instructions
            questions_feedback (dict): dictionary with the format of the feedback output

        Returns:
            Tuple(dict, list): dictionary of feedback structure and list of questions
        """
        prompt = f"""
            <OBJECTIVE_AND_PERSONA>
            You are a customer service coach specializing in support programs
            Your primary role is to analyze customer interactions (provided as text transcripts) and provide constructive feedback to agents.
            Your goal is to help agents improve their communication skills, performance and adherence to company policies while maintaining a supportive and motivating tone.
            </OBJECTIVE_AND_PERSONA>

            <INSTRUCTIONS>
            You will receive:
            - A redacted Transcript in JSON format
            - Coaching Questions (rubric) in JSON format

            Your job is to:
            1. Carefully read and analyze the entire transcript.
            2. For each coaching question:
                - Review the specific instructions and use the given rubric as base to generate the coaching feedback.
                - Assume the agent did not meet the criteria (received a negative score).
                - Identify specific moments in the transcript where improvement is needed.
            3. Create comprehensive coaching feedback for each question that:
                - Identifies the specific gap between current performance and expected standards.
                - Provides clear examples from the transcript of what could have been done differently.
                - Offers step-by-step guidance on how to improve
                When giving feedback:
                - **Be specific**: Focus on particular interactions or phrases that need improvement.
                - ** Be relevant**: Focus on the context of the call and offer suggest improvments that can improve the caller experience
                - **Be constructive**: Offer actionable suggestions that the agent can implement immediately to improve their performance.
                - **Focus on improvement**: Highlight patterns of behavior and suggest practical training or practice techniques where necessary.
                - **Be short and to the point**: Provide the feedback in not more than 2 sentences per question which should inolve all the needed information in a clear manner

            4. Preserve the original Feedback JSON structure, including all key-value pairs, nesting, and formatting. Only modify the "feedback" key to add the feedback. Do not change "question", "question_id".
            </INSTRUCTIONS>

            <CONTEXT>

            Conversation topics:
            - Welcome call (patient onboarding): To welcome and onboard the new patient to the Program
            - Coverage determination communications : To provide the patient with information about their insurance coverage determination
            - Device training : To be used to preview the device training program for patients already on therapy
            - Restart : To re-enroll eligible patients back into the Program
            </CONTEXT>

            <INPUTS>
            Transcript: {transcript}
            Coaching Questions: {subset_questions}
            </INPUTS>

            <OUTPUT>
            Feedback: {questions_feedback}
            </OUTPUT>

            <VALIDATION>
            Before providing any response:
            1. Verify the request aligns with coaching mission
            2. Ensure response meets all formatting requirements
            3. Confirm feedback addresses score improvement
            4. Ensure feedback is relevant to the context of the call
            5.If unable to meet these criteria, respond with "I am not able to answer this question"
            </VALIDATION>
        """
        return prompt

    def generate_coaching_feedback(self, prompt, response_schema):
        """Calls VertexAI to get a response for coaching feedback

        Args:
            prompt (str): prompt to use with Gemini
            response_schema (dict): dictionary with the expected schema output

        Returns:
            dict: dictionary with the gemini response
        """
        contents = [prompt]
        response = self.model.generate_content(contents,
                                          generation_config=GenerationConfig(
                                            temperature=0,
                                            response_mime_type="application/json",
                                            response_schema=response_schema)
                                          )

        print(f"respuesta a generate_coaching_feedback {response}")
        return json.loads(response.text)

    def insert_feedback_to_bigquery(self, json_data):
        """Inserts the feedback generated in BigQuery

        Args:
            json_data (dict): dictionary with the gemini response
        """
        client = bigquery.Client(project=self.project_id)

        table_ref = client.dataset(self.dataset_name).table(self.table_name)
        table = client.get_table(table_ref)

        # Convert JSON to rows format expected by BigQuery
        rows_to_insert = [{
            'conversationName': json_data['conversation_id'],
            'qaQuestion': json_data['question_id'],
            'feedback': json_data['feedback']
        }]

        try:
            errors = client.insert_rows(table, rows_to_insert)

            if errors == []:
                print('Data inserted successfully')
            else:
                print('Errors occurred while inserting data:', errors)

        except Exception as e:
            print(f'Error occurred: {str(e)}')
        
        return

    def run(self):
        """Runs the functions to get the transcript, questions and instructions to prompt gemini

        Returns:
            dict: coaching feedback 
        """
        conversation = self.get_transcript()
        five9_filename = conversation['labels']['five9_filename']
        self.record_keeper = RecordKeeper(self.ingest_record_bucket_id, five9_filename, self.storage_client)
        
        try:
            transcript = conversation['transcript']['transcriptSegments']
            qa_questions_dict = conversation['latestAnalysis']['analysisResult']['callAnalysisMetadata']['qaScorecardResults'][0]['qaAnswers']
            print(qa_questions_dict)
            questions_feedback, qa_questions_list = self.extract_questions(qa_questions_dict)
            scorecard = self.get_qa_questions()
            subset_questions = {key: scorecard[key] for key in qa_questions_list if key in scorecard}
            
            response_schema = {
                "type": "object",
                "properties": {
                    "results": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                            "conversation_id": {"type": "string"},
                                            "question_id": {"type": "string"},
                                            "question": {"type": "string"},
                                            "feedback": {"type": "string"}
                                        },
                                        "required": ["question_id", "question", "feedback"]
                                    },
                        "required": ["items"]
                        }
                    },
                    "required": ["results"]
                }

            prompt = self.generate_prompt(transcript, subset_questions, questions_feedback)
            coaching = self.generate_coaching_feedback(prompt, response_schema)

            print(questions_feedback)
            print(qa_questions_list)
            print(coaching['results'])

            for question_feedback in coaching['results']:
                self.insert_feedback_to_bigquery(question_feedback)

            self.record_keeper.replace_row(self.record_keeper.create_processed_record())
            print(f"respuesta a generate_coaching_feedback {coaching}")
            return coaching
        except Exception as e:
            self.log_error(str(e)) 
            self.record_keeper.replace_row(
            self.record_keeper.create_error_record(f'An error ocurred when using GenAI to generate coaching feedback: {str(e)}'))
