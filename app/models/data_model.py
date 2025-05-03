# data_model.py
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Any
import json
import os


@dataclass
class AnswerLocation:
    """Represents the location of an answer within a document."""
    page: int
    bounding_box: Optional[Dict[str, float]] = None  # x1, y1, x2, y2 coordinates
    text_spans: Optional[List[Dict[str, Any]]] = field(default_factory=list)  # For multiple text regions

    def to_dict(self):
        """Convert location to dictionary."""
        return {
            "page": self.page,
            "bounding_box": self.bounding_box,
            "text_spans": self.text_spans
        }


@dataclass
class QuestionAnswer:
    """Represents a student's answer to a specific question."""
    question_number: str
    answer_text: str
    is_correct: Optional[bool] = None
    location: AnswerLocation = field(default_factory=lambda: AnswerLocation(page=1))
    error_type: Optional[str] = None
    evaluation_reason: Optional[str] = None
    learning_topics: List[str] = field(default_factory=list)
    reference_to_answer: Optional[str] = None
    misconception: Optional[str] = None

    def to_dict(self):
        return {
            "question_number": self.question_number,
            "answer_text": self.answer_text,
            "is_correct": self.is_correct,
            "location": {
                "page": self.location.page,
                "bounding_box": self.location.bounding_box,
                "text_spans": self.location.text_spans
            },
            "error_type": self.error_type,
            "evaluation_reason": self.evaluation_reason,
            "learning_topics": self.learning_topics,
            "reference_to_answer": self.reference_to_answer,
            "misconception": self.misconception
        }

@dataclass
class StudentExam:
    """Represents a student's exam with all their answers."""
    student_id: str
    exam_id: str
    student_name: Optional[str] = None  # Add this line for the student's full name
    answers: List[QuestionAnswer] = field(default_factory=list)
    score: Optional[float] = None

    def to_dict(self):
        return {
            "student_id": self.student_id,
            "exam_id": self.exam_id,
            "student_name": self.student_name,  # Include in the dictionary
            "answers": [ans.to_dict() for ans in self.answers],
            "score": self.score
        }

    def save(self, directory):
        """Save the student exam data to a JSON file."""
        filename = f"{self.student_id}_{self.exam_id}.json"
        filepath = os.path.join(directory, filename)

        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

        return filepath


@dataclass
class AnswerKey:
    """Represents the answer key for an exam."""
    exam_id: str
    answers: Dict[str, str] = field(default_factory=dict)  # question_number -> correct_answer
    answer_locations: Dict[str, AnswerLocation] = field(default_factory=dict)  # question_number -> location

    def to_dict(self):
        return {
            "exam_id": self.exam_id,
            "answers": self.answers,
            "answer_locations": {
                qnum: loc.to_dict() if hasattr(loc, 'to_dict') else loc
                for qnum, loc in self.answer_locations.items()
            } if hasattr(self, 'answer_locations') else {}
        }

    def save(self, directory):
        """Save the answer key to a JSON file."""
        filename = f"key_{self.exam_id}.json"
        filepath = os.path.join(directory, filename)

        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

        return filepath


@dataclass
class ExamAnalysis:
    """Represents the analysis of all students' performance on an exam."""
    exam_id: str
    student_exams: List[StudentExam] = field(default_factory=list)
    answer_key: Optional[AnswerKey] = None
    question_difficulty: Dict[str, float] = field(default_factory=dict)  # question_number -> difficulty score
    error_patterns: Dict[str, Dict[str, int]] = field(default_factory=dict)  # question_number -> {error_type -> count}

    def to_dict(self):
        return {
            "exam_id": self.exam_id,
            "student_count": len(self.student_exams),
            "questions": list(self.question_difficulty.keys()),
            "question_difficulty": self.question_difficulty,
            "error_patterns": self.error_patterns
        }

    def save(self, directory):
        """Save the exam analysis to a JSON file."""
        filename = f"analysis_{self.exam_id}.json"
        filepath = os.path.join(directory, filename)

        with open(filepath, 'w') as f:
            json.dump(self.to_dict(), f, indent=2)

        return filepath