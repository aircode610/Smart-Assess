# exam_processor.py
import os
import json
import sys
import re
import logging
import google.generativeai as genai

# Add parent directory to path to import config and other modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.services.vision_api import GeminiVisionAPI
from app.models.data_model import QuestionAnswer, StudentExam, AnswerKey

from flask import current_app

logger = logging.getLogger(__name__)


class ExamProcessor:
    """Processor for exam papers and answer keys."""

    def __init__(self, vision_api=None):
        """Initialize the exam processor.

        Args:
            vision_api (GeminiVisionAPI, optional): Vision API for processing.
                If None, a new instance will be created.
        """
        self.vision_api = vision_api or GeminiVisionAPI()

    def process_student_exam(self, exam_image_path: str, default_student_id: str, exam_id: str) -> StudentExam:
        """Process a student's exam paper.

        Args:
            exam_image_path (str): Path to the exam image
            default_student_id (str): Default ID to use if name extraction fails
            exam_id (str): ID of the exam

        Returns:
            StudentExam: The processed student exam
        """
        logger.info(f"Processing exam, default ID: {default_student_id}, exam: {exam_id}")

        # Analyze the exam using the vision API
        api_result = self.vision_api.analyze_exam(exam_image_path)

        # Extract student name if available
        student_id = default_student_id
        student_name = api_result.get("student_name", "Unknown")

        if student_name and student_name != "Unknown":
            # Use the student name as the ID, but sanitize it for filename use
            student_id = re.sub(r'[^\w]', '_', student_name).lower()
            logger.info(f"Extracted student name: {student_name}")

        # Create a StudentExam object
        student_exam = StudentExam(
            student_id=student_id,
            exam_id=exam_id,
            student_name=student_name
        )

        # Extract questions and answers from the API result
        if "questions" in api_result:
            for q in api_result["questions"]:
                # Create the location info
                location_data = q.get("location", {"page": 1})

                # Create a proper AnswerLocation object
                from app.models.data_model import AnswerLocation
                location = AnswerLocation(
                    page=location_data.get("page", 1),
                    bounding_box=location_data.get("bounding_box"),
                    text_spans=location_data.get("text_spans", [])
                )

                answer = QuestionAnswer(
                    question_number=q["number"],
                    answer_text=q["answer"],
                    location=location
                )
                student_exam.answers.append(answer)
            logger.info(f"Extracted {len(student_exam.answers)} answers")
        else:
            logger.warning(f"No questions found in API result for student {student_id}, exam {exam_id}")

        # Save the student exam data
        save_path = student_exam.save(current_app.config['RESULTS_DIR'])
        logger.info(f"Saved student exam data to {save_path}")

        return student_exam

    def process_answer_key(self, answer_key_path: str, exam_id: str) -> AnswerKey:
        """Process an answer key image or PDF.

        Args:
            answer_key_path (str): Path to the answer key file
            exam_id (str): ID of the exam

        Returns:
            AnswerKey: The processed answer key
        """
        logger.info(f"Processing answer key for exam {exam_id}")

        # Analyze the answer key using the vision API
        api_result = self.vision_api.analyze_answer_key(answer_key_path)

        # Create an AnswerKey object
        answer_key = AnswerKey(exam_id=exam_id)

        # Extract answers from the API result
        if "answers" in api_result:
            for ans in api_result["answers"]:
                # Store the correct answer text
                answer_key.answers[ans["number"]] = ans["correct_answer"]

                # Store the location information if available
                if "location" in ans:
                    # We'll store this in a separate dictionary for location info
                    if not hasattr(answer_key, 'answer_locations'):
                        answer_key.answer_locations = {}

                    # Create a location object similar to what we use for student answers
                    from app.models.data_model import AnswerLocation
                    location = AnswerLocation(
                        page=ans["location"].get("page", 1),
                        bounding_box=ans["location"].get("bounding_box"),
                        text_spans=ans["location"].get("text_spans", [])
                    )

                    answer_key.answer_locations[ans["number"]] = location
        else:
            logger.warning(f"No answers found in API result for exam {exam_id}")

        # Save the answer key data
        save_path = answer_key.save(current_app.config['RESULTS_DIR'])
        logger.info(f"Saved answer key data to {save_path}")

        return answer_key

    def _clean_pdf_answer_text(self, text):
        """Clean up text extracted from PDFs to normalize for better comparison.

        Args:
            text (str): The raw text extracted from PDF

        Returns:
            str: Cleaned text
        """
        if not text:
            return ""

        # Remove extra whitespace and normalize spaces
        cleaned = re.sub(r'\s+', ' ', text.strip())

        # Remove common PDF artifacts like form field markers
        cleaned = re.sub(r'□|■|☐|☑|☒', '', cleaned)

        # Remove unwanted characters that might appear in PDFs
        cleaned = re.sub(r'[^\w\s.,;:?!\'"-]', '', cleaned)

        return cleaned.strip()

    def compare_with_answer_key(self, student_exam: StudentExam, answer_key: AnswerKey,
                                exam_subject="English") -> StudentExam:
        """Compare a student's answers with the answer key using Gemini for intelligent comparison.

        Args:
            student_exam (StudentExam): The student's exam
            answer_key (AnswerKey): The answer key
            exam_subject (str): The subject of the exam

        Returns:
            StudentExam: The updated student exam with correctness indicators and feedback
        """
        logger.info(f"Comparing student {student_exam.student_id}'s answers with answer key")

        correct_count = 0
        total_questions = len(student_exam.answers)

        # Process questions in batches to minimize API calls
        questions_to_evaluate = []

        for answer in student_exam.answers:
            question_number = answer.question_number

            if question_number in answer_key.answers:
                correct_answer = answer_key.answers[question_number]

                # Clean up answer text from PDFs which might contain extra whitespace or formatting
                cleaned_answer = self._clean_pdf_answer_text(answer.answer_text)

                # Add location information when available (for both student answer and reference answer)
                location_context = ""

                # Add student answer location if available
                if hasattr(answer, 'location') and answer.location:
                    location_context += f"""
                    Student answer location:
                    - Page: {answer.location.page}
                    - Coordinates: {answer.location.bounding_box if answer.location.bounding_box else 'Not available'}
                    """

                # Add reference answer location if available
                if hasattr(answer_key, 'answer_locations') and question_number in answer_key.answer_locations:
                    ref_location = answer_key.answer_locations[question_number]
                    location_context += f"""
                    Reference answer location:
                    - Page: {ref_location.page}
                    - Coordinates: {ref_location.bounding_box if ref_location.bounding_box else 'Not available'}
                    """

                # Add to the list of questions to evaluate
                questions_to_evaluate.append({
                    "question_number": question_number,
                    "student_answer": cleaned_answer,
                    "reference_answer": correct_answer,
                    "location_context": location_context.strip()
                })
            else:
                logger.warning(f"Question {question_number} not found in answer key")
                answer.is_correct = None

        # Use Gemini to evaluate all answers at once
        if questions_to_evaluate:
            evaluation_results = self._evaluate_answers_with_gemini(
                questions_to_evaluate, exam_subject)

            # Process the evaluation results
            for answer in student_exam.answers:
                question_number = answer.question_number

                # Check if the question number exists in the results
                if question_number in evaluation_results:
                    result = evaluation_results[question_number]

                    # Handle different formats of is_correct (boolean or string)
                    if isinstance(result.get("is_correct"), str):
                        is_correct_value = result.get("is_correct", "").lower() == "true"
                    else:
                        is_correct_value = bool(result.get("is_correct", False))

                    # Set basic fields
                    answer.is_correct = is_correct_value
                    answer.evaluation_reason = result.get("reason", "")

                    if is_correct_value:
                        answer.error_type = None
                        answer.misconception = None
                        answer.reference_to_answer = None
                        answer.learning_topics = []
                        correct_count += 1
                    else:
                        # Set detailed error information
                        answer.error_type = result.get("error_type", "unknown")
                        answer.misconception = result.get("misconception", "")
                        answer.reference_to_answer = result.get("reference_to_answer", "")

                        # Handle learning topics (might be a list or a string)
                        learning_topics = result.get("learning_topics", [])
                        if isinstance(learning_topics, str):
                            # Convert comma-separated string to list
                            answer.learning_topics = [topic.strip() for topic in learning_topics.split(",")]
                        else:
                            answer.learning_topics = learning_topics
                else:
                    # If no result for this question, use default values
                    answer.is_correct = False
                    answer.error_type = "not_evaluated"
                    answer.evaluation_reason = "Could not evaluate this answer"
                    answer.misconception = None
                    answer.reference_to_answer = None
                    answer.learning_topics = []

        # Calculate score as percentage
        if total_questions > 0:
            student_exam.score = (correct_count / total_questions) * 100

        # Save the updated student exam data
        student_exam.save(current_app.config['RESULTS_DIR'])

        return student_exam

    def _evaluate_answers_with_gemini(self, questions_to_evaluate, exam_subject="English"):
        """Use Gemini to evaluate student answers with detailed educational feedback.

        Args:
            questions_to_evaluate (list): List of dictionaries with question info
            exam_subject (str): The subject of the exam

        Returns:
            dict: Detailed evaluation results by question number
        """
        # Format the questions first
        formatted_questions = ""
        for q in questions_to_evaluate:
            formatted_questions += f"""
            Question {q['question_number']}:
            - Reference answer: "{q['reference_answer']}"
            - Student answer: "{q['student_answer']}"
            """

            # Add location context if available
            if 'location_context' in q and q['location_context']:
                formatted_questions += f"""
            - Location Information:
              {q['location_context']}
                """

        # Enhanced prompt with PDF support clarification
        prompt = f"""
        You are an expert {exam_subject} teacher evaluating student exam answers from a PDF document. 
        Provide detailed, educational feedback that helps students learn from their mistakes.

        For each answer, evaluate:

        1. CORRECTNESS: Is the student's answer conceptually correct compared to the reference answer? (true/false)

        2. EXPLANATION: Provide a brief, clear explanation of your evaluation.

        3. ERROR ANALYSIS (for incorrect answers only):
           - ERROR TYPE: Classify the error based on {exam_subject} concepts
           - MISCONCEPTION: Identify any specific misconception demonstrated in the answer

        4. LEARNING GUIDANCE (for incorrect answers only):
           - REFERENCE: Point to specific parts of the correct answer the student should focus on
           - LEARNING TOPICS: Suggest 2-3 specific topics the student should review to improve

        Here are the questions to evaluate:

        {formatted_questions}

        IMPORTANT: Format your response as valid JSON with this exact structure:
        {{
            "1": {{
                "is_correct": true/false,
                "reason": "explanation of evaluation",
                "error_type": "specific error classification based on {exam_subject}",
                "misconception": "identified misconception",
                "reference_to_answer": "specific part of correct answer to focus on",
                "learning_topics": ["topic1", "topic2", "topic3"]
            }},
            "2": {{ ... }},
            ...
        }}

        For correct answers, only include "is_correct" and "reason" fields.
        Use the exact question numbers as keys in the JSON.
        """

        try:
            # Call Gemini for evaluation
            genai_model = genai.GenerativeModel("gemini-1.5-pro")
            response = genai_model.generate_content(prompt)
            raw_text = response.text

            # Print the raw response for debugging
            logger.debug("Raw Gemini response:")
            logger.debug(raw_text)

            # Extract JSON from the response - handle code blocks if present
            if "```json" in raw_text:
                # Extract JSON from code block
                json_start = raw_text.find("```json") + 7
                json_end = raw_text.find("```", json_start)
                json_str = raw_text[json_start:json_end].strip()
            else:
                # Try to find JSON directly
                json_start = raw_text.find('{')
                json_end = raw_text.rfind('}') + 1
                json_str = raw_text[json_start:json_end] if json_start >= 0 and json_end > json_start else ""

            # Debug the extracted JSON string
            logger.debug("Extracted JSON string:")
            logger.debug(json_str)

            if json_str:
                try:
                    evaluation_results = json.loads(json_str)
                    logger.info("Successfully parsed JSON results")

                    # Ensure all question numbers are strings for consistent lookup
                    standardized_results = {}
                    for key, value in evaluation_results.items():
                        standardized_results[str(key)] = value

                    return standardized_results
                except json.JSONDecodeError as e:
                    logger.error(f"JSON decode error: {e}")
                    logger.error(f"Failed to parse JSON: {str(e)}, JSON string: {json_str}")
                    return {}
            else:
                logger.error("Failed to extract JSON from Gemini response")
                return {}

        except Exception as e:
            logger.error(f"Error evaluating answers with Gemini: {str(e)}")
            return {}