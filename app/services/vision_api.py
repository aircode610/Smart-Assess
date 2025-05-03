# api/vision_api.py
import os
import json
import logging
import base64
import google.generativeai as genai
from PIL import Image
import sys

# Add parent directory to path to import config
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flask import current_app

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class GeminiVisionAPI:
    """Wrapper for Google's Gemini Vision API."""

    def __init__(self, api_key=None):
        """Initialize the Gemini Vision API.

        Args:
            api_key (str, optional): API key for Gemini. Defaults to config value.
        """
        self.api_key = api_key or current_app.config['GEMINI_API_KEY']
        if not self.api_key:
            raise ValueError("Gemini API key is required. Set it in .env file.")

        # Configure the Gemini API
        genai.configure(api_key=self.api_key)

        # Initialize the model
        self.model = genai.GenerativeModel(current_app.config['GEMINI_MODEL'])
        logger.info(f"Initialized Gemini Vision API with model: {current_app.config['GEMINI_MODEL']}")

    def analyze_exam(self, file_path, custom_prompt=None):
        """Analyze an exam image or PDF to extract answers and student information.

        Args:
            file_path (str): Path to the exam file
            custom_prompt (str, optional): Custom prompt to use instead of default

        Returns:
            dict: Extracted exam data in JSON format
        """
        prompt = custom_prompt or current_app.config['EXAM_ANALYSIS_PROMPT']

        try:
            # Check if it's a PDF file
            if file_path.lower().endswith('.pdf'):
                logger.info(f"Processing PDF file: {file_path}")

                # Read the PDF file
                with open(file_path, 'rb') as f:
                    pdf_content = f.read()

                # Convert to base64
                pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')

                # Create multimodal content array
                contents = [
                    prompt,
                    {
                        "inline_data": {  # Changed from inlineData to inline_data
                            "mime_type": "application/pdf",  # Changed from mimeType to mime_type
                            "data": pdf_base64
                        }
                    }
                ]

                # Send to Gemini
                response = self.model.generate_content(contents)
            else:
                # Regular image processing
                image = Image.open(file_path)
                logger.info(f"Loaded image from {file_path}: {image.size}")
                response = self.model.generate_content([prompt, image])

            raw_text = response.text
            logger.info(f"Successfully analyzed exam file: {file_path}")

            # Try to extract JSON from the response
            try:
                # Find JSON content in the response (it might be wrapped in markdown code blocks)
                json_start = raw_text.find('{')
                json_end = raw_text.rfind('}') + 1

                if json_start >= 0 and json_end > json_start:
                    json_str = raw_text[json_start:json_end]
                    parsed_json = json.loads(json_str)
                    return parsed_json
                else:
                    logger.warning("No JSON content found in response")
                    return {"raw_text": raw_text}

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON from response: {str(e)}")
                return {"raw_text": raw_text}

        except Exception as e:
            logger.error(f"Error analyzing exam with Gemini Vision: {str(e)}")
            raise

    def analyze_answer_key(self, answer_key_path, custom_prompt=None):
        """Analyze an answer key image or PDF to extract correct answers.

        Args:
            answer_key_path (str): Path to the answer key file
            custom_prompt (str, optional): Custom prompt to use instead of default

        Returns:
            dict: Extracted answer key data in JSON format
        """
        prompt = custom_prompt or current_app.config['ANSWER_KEY_PROMPT']

        try:
            # Check if it's a PDF file
            if answer_key_path.lower().endswith('.pdf'):
                logger.info(f"Processing PDF file: {answer_key_path}")

                # Read the PDF file
                with open(answer_key_path, 'rb') as f:
                    pdf_content = f.read()

                # Convert to base64
                pdf_base64 = base64.b64encode(pdf_content).decode('utf-8')

                # Create multimodal content array
                contents = [
                    prompt,
                    {
                        "inline_data": {  # Changed from inlineData to inline_data
                            "mime_type": "application/pdf",  # Changed from mimeType to mime_type
                            "data": pdf_base64
                        }
                    }
                ]

                # Send to Gemini
                response = self.model.generate_content(contents)
            else:
                # Regular image processing
                image = Image.open(answer_key_path)
                logger.info(f"Loaded image from {answer_key_path}: {image.size}")
                response = self.model.generate_content([prompt, image])

            raw_text = response.text
            logger.info(f"Successfully analyzed answer key: {answer_key_path}")

            # Try to extract JSON from the response
            try:
                # Find JSON content in the response
                json_start = raw_text.find('{')
                json_end = raw_text.rfind('}') + 1

                if json_start >= 0 and json_end > json_start:
                    json_str = raw_text[json_start:json_end]
                    parsed_json = json.loads(json_str)
                    return parsed_json
                else:
                    logger.warning("No JSON content found in response")
                    return {"raw_text": raw_text}

            except json.JSONDecodeError as e:
                logger.warning(f"Failed to parse JSON from response: {str(e)}")
                return {"raw_text": raw_text}

        except Exception as e:
            logger.error(f"Error analyzing answer key with Gemini Vision: {str(e)}")
            raise

    def load_image(self, image_path):
        """Load an image from a file path.

        Args:
            image_path (str): Path to the image file

        Returns:
            PIL.Image: The loaded image
        """
        try:
            image = Image.open(image_path)
            logger.info(f"Loaded image from {image_path}: {image.size}")
            return image
        except Exception as e:
            logger.error(f"Error loading image from {image_path}: {str(e)}")
            raise