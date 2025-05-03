# pdf_highlighter.py
import os
import io
import logging
import fitz  # PyMuPDF

# Set up logging
logger = logging.getLogger(__name__)


class PDFHighlighter:
    """Service for highlighting answers on PDF exams using PyMuPDF."""

    @staticmethod
    def create_highlighted_pdf(original_pdf_path, answer_locations, errors_only=True):
        """
        Create a new PDF with answers highlighted using PyMuPDF (text search approach).

        Args:
            original_pdf_path (str): Path to the original exam PDF
            answer_locations (list): List of answer locations with correctness and answer text
            errors_only (bool): If True, only highlight incorrect answers

        Returns:
            bytes: The highlighted PDF as bytes
        """
        if not os.path.exists(original_pdf_path):
            raise FileNotFoundError(f"Original PDF not found: {original_pdf_path}")

        # Log diagnostics
        logger.info(f"Processing PDF: {original_pdf_path}")
        logger.info(f"Total answer locations: {len(answer_locations)}")

        try:
            # Open the PDF with PyMuPDF
            doc = fitz.open(original_pdf_path)

            # Process each answer
            for answer in answer_locations:
                # Skip if errors_only and this is a correct answer
                if errors_only and answer.get('is_correct') is True:
                    continue

                # Get answer text and page number
                answer_text = answer.get('answer_text', '').strip()
                page_num = answer.get('location', {}).get('page', 1)
                question_number = answer.get('question_number', '')
                is_correct = answer.get('is_correct')

                # If no answer text, skip
                if not answer_text:
                    logger.warning(f"No answer text found for question {question_number}")
                    continue

                # Adjust page number (PyMuPDF is 0-indexed while our data is 1-indexed)
                page_idx = page_num - 1

                # Ensure the page index is valid
                if page_idx < 0 or page_idx >= len(doc):
                    logger.warning(f"Invalid page number {page_num} for question {question_number}")
                    continue

                # Get the page
                page = doc[page_idx]

                # Search for the answer text on the page
                found_areas = page.search_for(answer_text)

                # If no text found, try to search for substrings
                if not found_areas and len(answer_text) > 10:
                    # Try with shorter substrings
                    for substring_length in [10, 5, 3]:
                        if len(answer_text) <= substring_length:
                            continue
                        substring = answer_text[:substring_length]
                        found_areas = page.search_for(substring)
                        if found_areas:
                            logger.info(
                                f"Found match using substring of length {substring_length} for Q{question_number}")
                            break

                # If still no text found, use location data if available
                if not found_areas and answer.get('location', {}).get('bounding_box'):
                    bbox = answer.get('location', {}).get('bounding_box')
                    if bbox:
                        # Convert normalized coordinates to absolute
                        page_rect = page.rect
                        x1 = bbox.get('x1', 0) * page_rect.width
                        y1 = bbox.get('y1', 0) * page_rect.height
                        x2 = bbox.get('x2', 0) * page_rect.width
                        y2 = bbox.get('y2', 0) * page_rect.height

                        found_areas = [fitz.Rect(x1, y1, x2, y2)]
                        logger.info(f"Using bounding box coordinates for Q{question_number}")

                # Highlight all found areas
                for rect in found_areas:
                    # Create a new shape
                    shape = page.new_shape()

                    # Set highlight color based on correctness
                    if is_correct is False:
                        color = (1, 0, 0)  # Red
                        fill_opacity = 0.3
                    elif is_correct is True:
                        color = (0, 0.7, 0)  # Green
                        fill_opacity = 0.2
                    else:
                        color = (0, 0, 1)  # Blue
                        fill_opacity = 0.2

                    # Add some padding
                    padding = 3
                    rect = fitz.Rect(
                        rect.x0 - padding,
                        rect.y0 - padding,
                        rect.x1 + padding,
                        rect.y1 + padding
                    )

                    # Draw the rectangle
                    shape.draw_rect(rect)
                    shape.finish(color=color, fill=color, fill_opacity=fill_opacity, width=1.5)

                    # Add question number label
                    if question_number:
                        # Position for the label
                        label_x = rect.x0 - 10
                        label_y = rect.y0

                        text_box = fitz.Rect(label_x - 8, label_y - 8, label_x + 8, label_y + 8)

                        circle_shape = page.new_shape()
                        # Draw a small circle for the label
                        circle_shape.draw_circle((label_x, label_y), 8)

                        if is_correct is False:
                            circle_shape.finish(color=(0.9, 0, 0), fill=(0.9, 0, 0), width=1)
                        elif is_correct is True:
                            circle_shape.finish(color=(0, 0.6, 0), fill=(0, 0.6, 0), width=1)
                        else:
                            circle_shape.finish(color=(0, 0, 0.9), fill=(0, 0, 0.9), width=1)

                        circle_shape.commit()

                        # Add text
                        text = f"Q{question_number}"
                        page.insert_textbox(
                            text_box,
                            text,
                            fontsize=8,
                            color=(1, 1, 1),  # White text
                            align=1  # 0 = left alignment
                        )

                    # Commit the shape
                    shape.commit()

                # Log whether we found anything
                if found_areas:
                    logger.info(f"Highlighted {len(found_areas)} instances for Q{question_number} on page {page_num}")
                else:
                    logger.warning(f"No match found for Q{question_number} answer: '{answer_text[:20]}...'")

            # Save the PDF to a memory buffer
            output_buffer = io.BytesIO()
            doc.save(output_buffer)
            doc.close()

            # Return the PDF bytes
            output_buffer.seek(0)
            return output_buffer.getvalue()

        except Exception as e:
            logger.error(f"Error creating highlighted PDF: {str(e)}")
            raise

    @staticmethod
    def format_answers_for_highlighting(student_exam):
        """
        Format student answers data for the highlighting function.

        Args:
            student_exam (dict): The student exam data from JSON

        Returns:
            list: Formatted answer locations for highlighting
        """
        answer_locations = []

        for answer in student_exam.get('answers', []):
            # Include the answer text which is crucial for the text search approach
            answer_locations.append({
                'question_number': answer.get('question_number'),
                'is_correct': answer.get('is_correct'),
                'answer_text': answer.get('answer_text', ''),
                'location': answer.get('location', {'page': 1})
            })

        return answer_locations