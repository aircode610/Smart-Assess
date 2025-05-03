# config.py
import os
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# Base configuration class
class Config:
    # Flask configuration
    SECRET_KEY = os.getenv("SECRET_KEY") or "your-secret-key"  # Use a secure key in production
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data")
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB max file size

    # API Configuration
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_MODEL = "gemini-1.5-flash"

    # Directory paths
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    DATA_DIR = os.path.join(BASE_DIR, "data")
    EXAMS_DIR = os.path.join(DATA_DIR, "exams")
    ANSWERS_DIR = os.path.join(DATA_DIR, "answers")
    RESULTS_DIR = os.path.join(DATA_DIR, "results")

    # Ensure directories exist
    for directory in [DATA_DIR, EXAMS_DIR, ANSWERS_DIR, RESULTS_DIR]:
        os.makedirs(directory, exist_ok=True)

    # Model prompts
    EXAM_ANALYSIS_PROMPT = """
    Analyze this exam document (which may contain multiple pages). 

    For each question on the exam:
    1. Identify the question number
    2. Extract the student's complete answer to that question
    3. Determine the precise location of the answer:
       - The page number where the answer appears
       - The bounding box coordinates of the answer (approximated as x1,y1,x2,y2 values between 0-1)
       - If the answer spans multiple regions, identify each text span with its own coordinates

    Format your response as a valid JSON object with this structure:
    {
      "student_name": "Full Name if present, otherwise leave empty",
      "questions": [
        {
          "number": "1",
          "answer": "The complete transcribed student answer for question 1",
          "location": {
            "page": 1,
            "bounding_box": {"x1": 0.1, "y1": 0.2, "x2": 0.8, "y2": 0.3},
            "text_spans": [
              {"text": "first part of answer", "page": 1, "bbox": {"x1": 0.1, "y1": 0.2, "x2": 0.8, "y2": 0.25}},
              {"text": "second part of answer", "page": 1, "bbox": {"x1": 0.1, "y1": 0.25, "x2": 0.8, "y2": 0.3}}
            ]
          }
        },
        ...
      ]
    }

    Be as precise as possible with the coordinates to enable accurate highlighting of answers in the document.
    """

    ANSWER_KEY_PROMPT = """
    Analyze this answer key document (which may contain multiple pages).

    For each question in the answer key:
    1. Extract the question number
    2. Extract the complete correct answer text
    3. Note which page the answer appears on
    4. If an answer spans multiple pages, include the complete answer
    5. Identify the bounding box coordinates of the answer (as x1,y1,x2,y2 values between 0-1)
    6. For each answer that spans multiple regions, identify each text span with coordinates

    Format your response as a valid JSON object with this structure:
    {
      "answers": [
        {
          "number": "1",
          "correct_answer": "The complete correct answer for question 1",
          "location": {
            "page": 1,
            "bounding_box": {"x1": 0.1, "y1": 0.2, "x2": 0.8, "y2": 0.3},
            "text_spans": [
              {"text": "first part of answer", "page": 1, "bbox": {"x1": 0.1, "y1": 0.2, "x2": 0.8, "y2": 0.25}},
              {"text": "second part of answer", "page": 1, "bbox": {"x1": 0.1, "y1": 0.25, "x2": 0.8, "y2": 0.3}}
            ]
          }
        },
        ...
      ]
    }

    Be as precise as possible with the coordinates to enable accurate answer comparison.
    """


class DevelopmentConfig(Config):
    DEBUG = True
    TESTING = False


class TestingConfig(Config):
    DEBUG = True
    TESTING = True


class ProductionConfig(Config):
    DEBUG = False
    TESTING = False


# Configure based on environment variable
config = {
    'development': DevelopmentConfig,
    'testing': TestingConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}


def get_config():
    config_name = os.getenv('FLASK_ENV', 'default')
    return config[config_name]