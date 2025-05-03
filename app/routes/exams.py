# app/routes/exams.py
import os
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app
from werkzeug.utils import secure_filename
import json
import logging
from app.utils.file_utils import convert_image_to_pdf

exams_bp = Blueprint('exams', __name__)
logger = logging.getLogger(__name__)


def allowed_file(filename):
    """Check if the file extension is allowed."""
    return '.' in filename and \
        filename.rsplit('.', 1)[1].lower() in {'jpg', 'jpeg', 'png', 'pdf'}


@exams_bp.route('/upload', methods=['GET', 'POST'])
def upload():
    """Upload exam files or answer keys."""
    if request.method == 'POST':
        # Check if the post request has the file part
        if 'file' not in request.files:
            flash('No file part')
            return redirect(request.url)

        file = request.files['file']
        file_type = request.form.get('file_type', 'exam')  # 'exam' or 'answer'
        exam_id = request.form.get('exam_id', 'default_exam')

        # If user does not select file, browser also submits an empty part without filename
        if file.filename == '':
            flash('No selected file')
            return redirect(request.url)

        # Check file size (limit to 10MB)
        file.seek(0, os.SEEK_END)
        file_size = file.tell()
        file.seek(0)

        if file_size > 10 * 1024 * 1024:  # 10MB limit
            flash('File too large. Maximum size is 10MB')
            return redirect(request.url)

        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)

            # Determine the save directory based on file type
            if file_type == 'exam':
                save_dir = current_app.config['EXAMS_DIR']
            else:  # answer key
                save_dir = current_app.config['ANSWERS_DIR']

            # Save the file initially
            file_path = os.path.join(save_dir, filename)
            file.save(file_path)

            # Check if it's an image file that needs to be converted to PDF
            file_ext = os.path.splitext(filename)[1].lower()
            if file_ext in ['.jpg', '.jpeg', '.png']:
                try:
                    # Convert the image to PDF
                    pdf_path = convert_image_to_pdf(file_path, save_dir)
                    pdf_filename = os.path.basename(pdf_path)

                    # Log success
                    logger.info(f"Converted image {filename} to PDF {pdf_filename}")
                    flash(f'Image converted to PDF successfully: {pdf_filename}')

                except Exception as e:
                    logger.error(f"Failed to convert image to PDF: {str(e)}")
                    flash(f'Error converting image to PDF: {str(e)}')
                    # Keep the original image if conversion fails
                    return redirect(request.url)
            else:
                flash(f'File uploaded successfully: {filename}')

            # Redirect based on the file type
            if file_type == 'exam':
                return redirect(url_for('exams.list'))
            else:
                return redirect(url_for('analysis.list'))

    return render_template('exams/upload.html')


@exams_bp.route('/list')
def list():
    """List all uploaded exam files."""
    exams_dir = current_app.config['EXAMS_DIR']
    answers_dir = current_app.config['ANSWERS_DIR']  # Add this line

    # Get exam files
    exams = [f for f in os.listdir(exams_dir) if os.path.isfile(os.path.join(exams_dir, f)) and allowed_file(f)]

    # Get answer key files - add these lines
    answer_keys = [f for f in os.listdir(answers_dir)
                   if os.path.isfile(os.path.join(answers_dir, f)) and allowed_file(f)]

    # Pass answer_keys to the template
    return render_template('exams/list.html', exams=exams, answer_keys=answer_keys)