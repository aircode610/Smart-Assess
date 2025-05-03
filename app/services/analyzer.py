import os
import json
import logging
import re
import google.generativeai as genai
from collections import defaultdict, Counter
from typing import Dict, List, Optional, Set, Any
import sys

# Add parent directory to path to import config and other modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from app.models.data_model import StudentExam, AnswerKey, ExamAnalysis

from flask import current_app

logger = logging.getLogger(__name__)


class ExamAnalyzer:
    """Analyzer for exam results to find patterns and generate insights."""

    def analyze_exam(self, exam_id: str, student_exams: List[StudentExam], answer_key: AnswerKey) -> ExamAnalysis:
        """Analyze the exam results across all students.

        Args:
            exam_id (str): ID of the exam
            student_exams (List[StudentExam]): List of student exams
            answer_key (AnswerKey): The answer key

        Returns:
            ExamAnalysis: The exam analysis
        """
        logger.info(f"Analyzing exam {exam_id} for {len(student_exams)} students")

        # Create an ExamAnalysis object
        analysis = ExamAnalysis(
            exam_id=exam_id,
            student_exams=student_exams,
            answer_key=answer_key
        )

        # Calculate question difficulty
        analysis.question_difficulty = self._calculate_difficulty(student_exams)

        # Identify raw error patterns
        raw_error_patterns = self._identify_error_patterns(student_exams)

        # Then group semantically similar patterns using Gemini
        analysis.error_patterns = self._group_error_patterns_with_gemini(raw_error_patterns)

        # Sort the results by question number
        self._sort_analysis_by_question_number(analysis)

        # Save the analysis
        save_path = analysis.save(current_app.config['RESULTS_DIR'])
        logger.info(f"Saved exam analysis to {save_path}")

        return analysis

    def _calculate_difficulty(self, student_exams: List[StudentExam]) -> Dict[str, float]:
        """Calculate difficulty level for each question based on student performance.

        Args:
            student_exams (List[StudentExam]): List of student exams

        Returns:
            Dict[str, float]: Dictionary mapping question numbers to difficulty scores (0-1)
                              where higher values indicate more difficult questions
        """
        # Get all question numbers
        question_numbers = set()
        for exam in student_exams:
            for answer in exam.answers:
                question_numbers.add(answer.question_number)

        # Calculate difficulty for each question
        difficulty = {}
        for question_number in question_numbers:
            # Count correct and total attempts
            correct_count = 0
            total_count = 0

            for exam in student_exams:
                for answer in exam.answers:
                    if answer.question_number == question_number:
                        total_count += 1
                        if answer.is_correct:
                            correct_count += 1

            # Calculate difficulty as percentage of incorrect answers
            if total_count > 0:
                difficulty[question_number] = 1.0 - (correct_count / total_count)
            else:
                difficulty[question_number] = 0.0

        return difficulty

    def _identify_error_patterns(self, student_exams: List[StudentExam]) -> Dict[str, Dict[str, int]]:
        """Identify common error patterns for each question.

        Args:
            student_exams (List[StudentExam]): List of student exams

        Returns:
            Dict[str, Dict[str, int]]: Dictionary mapping question numbers to error types and counts
        """
        # Initialize error patterns dictionary
        error_patterns = defaultdict(Counter)

        # Count error types for each question
        for exam in student_exams:
            for answer in exam.answers:
                if not answer.is_correct and answer.error_type:
                    error_patterns[answer.question_number][answer.error_type] += 1

        # Convert Counter objects to regular dictionaries
        return {q: dict(counts) for q, counts in error_patterns.items()}

    def find_common_errors(self, student_exams: List[StudentExam], answer_key: AnswerKey) -> Dict[str, List[str]]:
        """Find common incorrect answers for each question.

        Args:
            student_exams (List[StudentExam]): List of student exams
            answer_key (AnswerKey): The answer key

        Returns:
            Dict[str, List[str]]: Dictionary mapping question numbers to lists of common incorrect answers
        """
        # Group answers by question number
        answers_by_question = defaultdict(list)
        for exam in student_exams:
            for answer in exam.answers:
                if not answer.is_correct:  # Only include incorrect answers
                    answers_by_question[answer.question_number].append(answer.answer_text)

        # Find common incorrect answers
        common_errors = {}
        for question_number, answers in answers_by_question.items():
            # Count occurrences of each answer
            answer_counts = Counter(answers)

            # Get the most common incorrect answers (those occurring more than once)
            common = [ans for ans, count in answer_counts.most_common() if count > 1]

            if common:
                common_errors[question_number] = common

        return common_errors

    def generate_heatmap_data(self, analysis: ExamAnalysis) -> Dict[str, float]:
        """Generate data for a difficulty heatmap.

        Args:
            analysis (ExamAnalysis): The exam analysis

        Returns:
            Dict[str, float]: Dictionary mapping question numbers to difficulty scores
        """
        # Just return the difficulty scores directly
        return analysis.question_difficulty

    def generate_error_report(self, analysis: ExamAnalysis) -> Dict[str, Dict[str, Any]]:
        """Generate a detailed error report for each question, incorporating PDF location data.

        Args:
            analysis (ExamAnalysis): The exam analysis

        Returns:
            Dict[str, Dict[str, Any]]: Detailed error report sorted by question number
        """
        # Get all question numbers and sort them numerically
        question_numbers = list(analysis.question_difficulty.keys())

        # Sort questions numerically
        def get_sort_key(q):
            try:
                return int(q)
            except ValueError:
                return q  # Keep as string if not convertible to int

        sorted_questions = sorted(question_numbers, key=get_sort_key)

        # Use OrderedDict to maintain the sorted order
        from collections import OrderedDict
        report = OrderedDict()

        # Build the report with sorted question numbers
        for question_number in sorted_questions:
            # Get difficulty
            difficulty = analysis.question_difficulty.get(question_number, 0.0)

            # Get error patterns
            error_patterns = analysis.error_patterns.get(question_number, {})

            # Get correct answer and location
            correct_answer = None
            answer_location = None
            if analysis.answer_key:
                correct_answer = analysis.answer_key.answers.get(question_number)
                if hasattr(analysis.answer_key, 'answer_locations'):
                    answer_location = analysis.answer_key.answer_locations.get(question_number)

            # Find all student answers for this question
            student_answers = []
            for student_exam in analysis.student_exams:
                for answer in student_exam.answers:
                    if answer.question_number == question_number:
                        student_answers.append({
                            'student_id': student_exam.student_id,
                            'student_name': student_exam.student_name,
                            'is_correct': answer.is_correct,
                            'answer_text': answer.answer_text,
                            'error_type': answer.error_type,
                            'location': answer.location if hasattr(answer, 'location') else None
                        })

            # Analyze spatial patterns using location data
            spatial_patterns = self._analyze_spatial_patterns(question_number, student_answers)

            # Build report for this question
            report[question_number] = {
                "difficulty": difficulty,
                "difficulty_level": self._categorize_difficulty(difficulty),
                "error_patterns": error_patterns,
                "correct_answer": correct_answer,
                "answer_location": answer_location.to_dict() if hasattr(answer_location,
                                                                        'to_dict') else answer_location,
                "spatial_patterns": spatial_patterns,
                "student_count": sum(error_patterns.values())
            }

        return report

    def _analyze_spatial_patterns(self, question_number: str, student_answers: List[Dict]) -> Dict:
        """Analyze spatial error patterns using PDF location data.

        Args:
            question_number (str): The question number
            student_answers (List[Dict]): List of student answers with location data

        Returns:
            Dict: Spatial pattern analysis
        """
        # Initialize spatial patterns
        spatial_patterns = {
            "has_location_data": False,
            "location_coverage": 0.0,  # Percentage of answers with location data
            "page_distribution": {},  # Distribution of answers by page
            "common_areas": []  # Areas with high error rates
        }

        # Count answers with location data
        answers_with_location = [a for a in student_answers if a.get('location')]
        total_answers = len(student_answers)

        if total_answers == 0 or len(answers_with_location) == 0:
            return spatial_patterns

        spatial_patterns["has_location_data"] = True
        spatial_patterns["location_coverage"] = len(answers_with_location) / total_answers * 100

        # Analyze page distribution
        page_counts = {}
        for answer in answers_with_location:
            location = answer.get('location')
            page = location.page if hasattr(location, 'page') else location.get('page', 1)

            if page in page_counts:
                page_counts[page] += 1
            else:
                page_counts[page] = 1

        spatial_patterns["page_distribution"] = page_counts

        # Analyze common areas with errors
        error_areas = []
        for answer in answers_with_location:
            if answer.get('is_correct') == False:
                location = answer.get('location')

                # Handle different location data structures
                if hasattr(location, 'bounding_box'):
                    bbox = location.bounding_box
                else:
                    bbox = location.get('bounding_box')

                if bbox:
                    error_areas.append({
                        'page': location.page if hasattr(location, 'page') else location.get('page', 1),
                        'bbox': bbox,
                        'error_type': answer.get('error_type', 'unknown')
                    })

        # Group error areas by proximity
        # (Simplified - in a real implementation, you'd cluster by spatial proximity)
        spatial_patterns["common_areas"] = error_areas[:5]  # Just take the first 5 for now

        return spatial_patterns

    def _categorize_difficulty(self, difficulty_score: float) -> str:
        """Categorize a difficulty score into a level.

        Args:
            difficulty_score (float): The difficulty score (0-1)

        Returns:
            str: The difficulty level (easy, medium, hard)
        """
        if difficulty_score < 0.3:
            return "easy"
        elif difficulty_score < 0.7:
            return "medium"
        else:
            return "hard"

    def _sort_analysis_by_question_number(self, analysis: ExamAnalysis) -> None:
        """Sort all analysis data by question number.

        Args:
            analysis (ExamAnalysis): The exam analysis to sort
        """
        # Extract all question numbers and sort them numerically
        question_numbers = list(analysis.question_difficulty.keys())

        # Convert to integers for sorting if they're numeric
        def get_sort_key(q):
            try:
                return int(q)
            except ValueError:
                return q  # Keep as string if not convertible to int

        sorted_questions = sorted(question_numbers, key=get_sort_key)

        # Sort the questions list
        analysis.questions = sorted_questions

        # Sort question_difficulty
        sorted_difficulty = {q: analysis.question_difficulty[q] for q in sorted_questions}
        analysis.question_difficulty = sorted_difficulty

        # Sort error_patterns if it exists
        if hasattr(analysis, 'error_patterns') and analysis.error_patterns:
            # Only include questions that are in the sorted list
            sorted_errors = {q: analysis.error_patterns[q] for q in sorted_questions if q in analysis.error_patterns}
            analysis.error_patterns = sorted_errors

    def _group_error_patterns_with_gemini(self, error_patterns: Dict[str, Dict[str, int]]) -> Dict[str, Dict[str, int]]:
        """Use Gemini API to group semantically similar error patterns.

        Args:
            error_patterns (Dict[str, Dict[str, int]]): Raw error patterns by question

        Returns:
            Dict[str, Dict[str, int]]: Grouped error patterns
        """
        import google.generativeai as genai
        grouped_patterns = {}

        # Initialize the Gemini model
        try:
            genai_model = genai.GenerativeModel("gemini-1.5-pro")
        except Exception as e:
            logger.error(f"Failed to initialize Gemini model: {str(e)}")
            return error_patterns  # Return original patterns if Gemini initialization fails

        for question_number, error_types in error_patterns.items():
            # Skip grouping if there are very few error types (1 or 2)
            if len(error_types) <= 2:
                grouped_patterns[question_number] = dict(error_types)
                continue

            # Format the error types as a list with their counts
            error_list = []
            for error_type, count in error_types.items():
                error_list.append(f"{error_type}: {count}")

            prompt = f"""
            You are analyzing student exam error patterns. Below is a list of error types with their counts 
            for Question {question_number}. Group these error types by semantic similarity (meaning), 
            combining those that represent the same fundamental concept even if they use different words or phrasing.

            For example, "vocabulary misuse" and "incorrect word choice" would be grouped together,
            or "calculation error" and "arithmetic mistake" would be combined.

            Use the most descriptive and concise label for each group. The goal is to simplify the error 
            analysis while preserving meaningful distinctions between different types of errors.

            Error types:
            {', '.join(error_list)}

            Format your response as a JSON object like this:
            {{
                "grouped_errors": {{
                    "descriptive_error_label_1": N, // Sum of counts for this semantic group
                    "descriptive_error_label_2": M,
                    ...
                }}
            }}

            Only include the JSON object in your response, nothing else.
            """

            try:
                response = genai_model.generate_content(prompt)
                raw_text = response.text

                # Extract JSON from the response
                import json
                import re

                # Find JSON content in response
                json_match = re.search(r'```json\s*(.*?)\s*```', raw_text, re.DOTALL)
                if json_match:
                    json_str = json_match.group(1)
                else:
                    json_start = raw_text.find('{')
                    json_end = raw_text.rfind('}') + 1
                    json_str = raw_text[json_start:json_end] if json_start >= 0 and json_end > json_start else ""

                if json_str:
                    try:
                        result = json.loads(json_str)
                        if 'grouped_errors' in result:
                            grouped_patterns[question_number] = result['grouped_errors']
                            logger.info(
                                f"Question {question_number}: Successfully grouped {len(error_types)} error types into {len(result['grouped_errors'])} categories")
                            continue
                    except json.JSONDecodeError as e:
                        logger.error(f"JSON decode error for question {question_number}: {str(e)}")

                logger.warning(f"Failed to extract valid JSON response for question {question_number}")

            except Exception as e:
                logger.error(f"Error grouping with Gemini for question {question_number}: {str(e)}")

            # Fallback to original patterns if Gemini processing fails
            grouped_patterns[question_number] = dict(error_types)

        return grouped_patterns