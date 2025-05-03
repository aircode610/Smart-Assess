# app/routes/analysis.py
import os
import json
import difflib
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, jsonify, send_file, \
    make_response, session
from werkzeug.utils import secure_filename  # Add this line
from app.services.exam_processor import ExamProcessor
from app.services.analyzer import ExamAnalyzer
from app.services.vision_api import GeminiVisionAPI
from app.services.pdf_highlighter import PDFHighlighter
import io

analysis_bp = Blueprint('analysis', __name__)


@analysis_bp.route('/process', methods=['POST'])
def process():
    """Process exams and answer keys."""
    exam_id = request.form.get('exam_id', 'default_exam')
    exam_files = request.form.getlist('exam_files')
    answer_key_file = request.form.get('answer_key_file')

    if not exam_files:
        flash('No exam files selected')
        return redirect(url_for('exams.list'))

    if not answer_key_file:
        flash('No answer key file selected')
        return redirect(url_for('exams.list'))

    try:
        # Initialize services
        api = GeminiVisionAPI()
        processor = ExamProcessor(api)
        analyzer = ExamAnalyzer()

        # Process answer key
        answer_key_path = os.path.join(current_app.config['ANSWERS_DIR'], answer_key_file)
        answer_key = processor.process_answer_key(answer_key_path, exam_id)

        # Process exam files
        student_exams = []
        for i, exam_file in enumerate(exam_files):
            exam_path = os.path.join(current_app.config['EXAMS_DIR'], exam_file)
            default_student_id = f"student_{i + 1:02d}"

            # Process the exam
            student_exam = processor.process_student_exam(exam_path, default_student_id, exam_id)

            # Compare with answer key
            student_exam = processor.compare_with_answer_key(student_exam, answer_key, "English")

            student_exams.append(student_exam)

            # Associate the exam file with the student ID in the session
            if 'pdf_mappings' not in session:
                session['pdf_mappings'] = {}

            session['pdf_mappings'][f"{student_exam.student_id}_{exam_id}"] = exam_file
            session.modified = True

        # Analyze the exam results
        analysis = analyzer.analyze_exam(exam_id, student_exams, answer_key)

        flash('Analysis completed successfully')
        return redirect(url_for('analysis.results', exam_id=exam_id))

    except Exception as e:
        flash(f'Error processing exams: {str(e)}')
        return redirect(url_for('exams.list'))


@analysis_bp.route('/list')
def list():
    """List all analysis results."""
    results_dir = current_app.config['RESULTS_DIR']
    analysis_files = [f for f in os.listdir(results_dir) if f.startswith('analysis_') and f.endswith('.json')]

    results = []
    for file in analysis_files:
        file_path = os.path.join(results_dir, file)
        with open(file_path, 'r') as f:
            data = json.load(f)
            exam_id = data.get('exam_id', 'Unknown')
            student_count = data.get('student_count', 0)
            question_count = len(data.get('questions', []))

            results.append({
                'exam_id': exam_id,
                'student_count': student_count,
                'question_count': question_count,
                'filename': file
            })

    return render_template('analysis/list.html', results=results)


@analysis_bp.route('/results/<exam_id>')
def results(exam_id):
    """Display analysis results for a specific exam."""
    results_dir = current_app.config['RESULTS_DIR']
    answers_dir = current_app.config['ANSWERS_DIR']
    analysis_file = os.path.join(results_dir, f'analysis_{exam_id}.json')

    if not os.path.exists(analysis_file):
        flash(f'Analysis for exam {exam_id} not found')
        return redirect(url_for('analysis.list'))

    with open(analysis_file, 'r') as f:
        analysis_data = json.load(f)

    # Find answer key file if exists
    answer_key_file = None

    # Look for PDF answer key
    for file in os.listdir(answers_dir):
        if file.lower().endswith('.pdf') and exam_id in file:
            answer_key_file = file
            break

    # Get student exams for this analysis
    student_files = [f for f in os.listdir(results_dir) if
                     f.endswith(f'_{exam_id}.json') and not f.startswith('analysis_') and not f.startswith('key_')]

    students = []
    for file in student_files:
        file_path = os.path.join(results_dir, file)
        with open(file_path, 'r') as f:
            data = json.load(f)
            students.append({
                'student_id': data.get('student_id', 'Unknown'),
                'student_name': data.get('student_name', 'Unknown'),
                'score': data.get('score', 0)
            })

    # Sort students by score (descending)
    students.sort(key=lambda x: x['score'], reverse=True)

    return render_template('analysis/results.html',
                           exam_id=exam_id,
                           analysis=analysis_data,
                           students=students,
                           answer_key_file=answer_key_file)


# Updated route that handles PDF highlighting
@analysis_bp.route('/student/<student_id>/<exam_id>/pdf')
def student_exam_pdf(student_id, exam_id):
    """View a student's exam PDF with highlights."""

    # Get highlight_mode from query parameters (errors_only or all)
    highlight_mode = request.args.get('mode', 'errors_only')
    errors_only = (highlight_mode == 'errors_only')

    # Find student data
    results_dir = current_app.config['RESULTS_DIR']
    student_file = os.path.join(results_dir, f"{student_id}_{exam_id}.json")

    if not os.path.exists(student_file):
        flash(f"Student exam not found")
        return redirect(url_for('analysis.results', exam_id=exam_id))

    # Load student data
    with open(student_file, 'r') as f:
        student_data = json.load(f)

    # Find the original exam file
    exams_dir = current_app.config['EXAMS_DIR']
    exam_file = None

    # First check if we have a stored mapping for this student in the pdf_mappings
    if 'pdf_mappings' in session and f"{student_id}_{exam_id}" in session['pdf_mappings']:
        mapped_pdf = session['pdf_mappings'][f"{student_id}_{exam_id}"]
        if os.path.exists(os.path.join(exams_dir, mapped_pdf)):
            exam_file = mapped_pdf
            current_app.logger.info(f"Using mapped PDF from processing: {exam_file}")

    # If no mapping, check for manual selection
    if not exam_file and 'pdf_selections' in session and f"{student_id}_{exam_id}" in session['pdf_selections']:
        selected_pdf = session['pdf_selections'][f"{student_id}_{exam_id}"]
        if os.path.exists(os.path.join(exams_dir, selected_pdf)):
            exam_file = selected_pdf
            current_app.logger.info(f"Using manually selected PDF: {exam_file}")

    # Still no file? Try to find the best match automatically
    if not exam_file:
        best_match = find_best_matching_pdf(student_data, exam_id, exams_dir)
        if best_match:
            exam_file = best_match
            # Store this match for future use
            if 'pdf_mappings' not in session:
                session['pdf_mappings'] = {}
            session['pdf_mappings'][f"{student_id}_{exam_id}"] = exam_file
            session.modified = True
            current_app.logger.info(f"Automatically found matching PDF: {exam_file}")

    if not exam_file:
        flash(f"Exam PDF file not found for student {student_id}")
        return redirect(url_for('analysis.student_detail', student_id=student_id, exam_id=exam_id))

    # Format answer locations for the highlighter
    answer_locations = PDFHighlighter.format_answers_for_highlighting(student_data)

    # Log information for debugging
    current_app.logger.info(f"Highlighting PDF {exam_file} with {len(answer_locations)} answers")

    # Log sample of the answer locations for debugging
    if answer_locations and len(answer_locations) > 0:
        sample = answer_locations[0]
        current_app.logger.info(f"Sample answer: Q{sample.get('question_number')}, " +
                                f"correct: {sample.get('is_correct')}, " +
                                f"page: {sample.get('location', {}).get('page')}")

    # Get the path to the original PDF
    original_pdf_path = os.path.join(exams_dir, exam_file)

    # Create highlighted PDF
    try:
        highlighted_pdf = PDFHighlighter.create_highlighted_pdf(
            original_pdf_path,
            answer_locations,
            errors_only=errors_only
        )

        # Return the PDF as a response
        response = make_response(highlighted_pdf)
        response.headers['Content-Type'] = 'application/pdf'
        response.headers['Content-Disposition'] = f'inline; filename="{student_id}_{exam_id}_highlighted.pdf"'

        # Add cache-control headers to prevent caching issues
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'

        return response

    except Exception as e:
        current_app.logger.error(f"Error creating highlighted PDF: {str(e)}")
        flash(f"Error creating highlighted PDF: {str(e)}")
        return redirect(url_for('analysis.student_detail', student_id=student_id, exam_id=exam_id))


def find_best_matching_pdf(student_data, exam_id, exams_dir):
    """Find the best matching PDF file for a student based on name and exam ID.

    Args:
        student_data (dict): Student data from JSON
        exam_id (str): Exam ID
        exams_dir (str): Directory containing exam PDFs

    Returns:
        str or None: Best matching PDF filename or None if no match found
    """
    student_id = student_data.get('student_id', '')
    student_name = student_data.get('student_name', '').lower()

    pdf_files = [f for f in os.listdir(exams_dir) if f.endswith('.pdf')]
    if not pdf_files:
        return None

    # If there's only one PDF, use it
    if len(pdf_files) == 1:
        return pdf_files[0]

    # Create different match scores based on various criteria
    match_scores = {}

    for pdf_file in pdf_files:
        filename_lower = pdf_file.lower()
        score = 0

        # Check for exact student ID match (highest priority)
        if student_id and student_id.lower() in filename_lower:
            score += 100

        # Check for student name match
        if student_name and student_name != 'unknown':
            # Split student name into parts
            name_parts = student_name.split()
            for part in name_parts:
                if len(part) > 2 and part in filename_lower:  # Avoid matching short name parts
                    score += 50

        # Check for exam ID match
        if exam_id and exam_id.lower() in filename_lower:
            score += 30

        # Use difflib for fuzzy matching of student name
        if student_name and student_name != 'unknown':
            # Remove extension for better matching
            filename_without_ext = os.path.splitext(filename_lower)[0]
            similarity = difflib.SequenceMatcher(None, student_name, filename_without_ext).ratio()
            score += similarity * 20  # Scale similarity to be worth up to 20 points

        match_scores[pdf_file] = score

    # Find the highest scoring PDF
    if match_scores:
        best_match = max(match_scores.items(), key=lambda x: x[1])
        # Only return a match if it has a reasonable score
        if best_match[1] > 10:  # Minimum threshold for confidence
            return best_match[0]

    # Default to first PDF if no good match found and there's more than one PDF
    if len(pdf_files) > 0:
        return pdf_files[0]

    return None


@analysis_bp.route('/student/<student_id>/<exam_id>/download-pdf')
def download_highlighted_pdf(student_id, exam_id):
    """Download a student's exam PDF with highlights."""

    # Get highlight_mode from query parameters (errors_only or all)
    highlight_mode = request.args.get('mode', 'errors_only')
    errors_only = (highlight_mode == 'errors_only')

    # Find student data
    results_dir = current_app.config['RESULTS_DIR']
    student_file = os.path.join(results_dir, f"{student_id}_{exam_id}.json")

    if not os.path.exists(student_file):
        flash(f"Student exam not found")
        return redirect(url_for('analysis.results', exam_id=exam_id))

    # Load student data
    with open(student_file, 'r') as f:
        student_data = json.load(f)

    # Find the original exam file using the same logic as in student_exam_pdf
    exams_dir = current_app.config['EXAMS_DIR']
    exam_file = None

    # Check for mapping or selection
    if 'pdf_mappings' in session and f"{student_id}_{exam_id}" in session['pdf_mappings']:
        mapped_pdf = session['pdf_mappings'][f"{student_id}_{exam_id}"]
        if os.path.exists(os.path.join(exams_dir, mapped_pdf)):
            exam_file = mapped_pdf

    if not exam_file and 'pdf_selections' in session and f"{student_id}_{exam_id}" in session['pdf_selections']:
        selected_pdf = session['pdf_selections'][f"{student_id}_{exam_id}"]
        if os.path.exists(os.path.join(exams_dir, selected_pdf)):
            exam_file = selected_pdf

    # Try to find a match
    if not exam_file:
        exam_file = find_best_matching_pdf(student_data, exam_id, exams_dir)

    if not exam_file:
        flash(f"Exam PDF file not found for student {student_id}")
        return redirect(url_for('analysis.student_detail', student_id=student_id, exam_id=exam_id))

    # Format answer locations for the highlighter
    answer_locations = PDFHighlighter.format_answers_for_highlighting(student_data)

    # Get the path to the original PDF
    original_pdf_path = os.path.join(exams_dir, exam_file)

    # Create highlighted PDF
    try:
        highlighted_pdf = PDFHighlighter.create_highlighted_pdf(
            original_pdf_path,
            answer_locations,
            errors_only=errors_only
        )

        # Create a file-like object for sending
        pdf_file = io.BytesIO(highlighted_pdf)
        pdf_file.seek(0)

        mode_text = "errors" if errors_only else "all_answers"
        filename = f"{student_data.get('student_name', student_id)}_{exam_id}_{mode_text}.pdf"
        filename = secure_filename(filename)

        # Return as attachment (download)
        return send_file(
            pdf_file,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=filename
        )

    except Exception as e:
        current_app.logger.error(f"Error creating highlighted PDF for download: {str(e)}")
        flash(f"Error creating highlighted PDF: {str(e)}")
        return redirect(url_for('analysis.student_detail', student_id=student_id, exam_id=exam_id))


@analysis_bp.route('/report/<exam_id>')
def report(exam_id):
    """Generate a detailed report for a specific exam."""
    results_dir = current_app.config['RESULTS_DIR']
    analysis_file = os.path.join(results_dir, f'analysis_{exam_id}.json')

    if not os.path.exists(analysis_file):
        flash(f'Analysis for exam {exam_id} not found')
        return redirect(url_for('analysis.list'))

    with open(analysis_file, 'r') as f:
        analysis_data = json.load(f)

    # Initialize analyzer
    analyzer = ExamAnalyzer()

    # Get student exams and answer key
    student_exams = []
    answer_key = None

    student_files = [f for f in os.listdir(results_dir) if
                     f.endswith(f'_{exam_id}.json') and not f.startswith('analysis_') and not f.startswith('key_')]
    key_file = os.path.join(results_dir, f'key_{exam_id}.json')

    # Load answer key if exists
    if os.path.exists(key_file):
        with open(key_file, 'r') as f:
            key_data = json.load(f)
            # Create AnswerKey object
            from app.models.data_model import AnswerKey
            answer_key = AnswerKey(exam_id=exam_id, answers=key_data.get('answers', {}))

    # Load student exams
    for file in student_files:
        file_path = os.path.join(results_dir, file)
        with open(file_path, 'r') as f:
            data = json.load(f)

            # Create StudentExam object
            from app.models.data_model import StudentExam, QuestionAnswer
            student_exam = StudentExam(
                student_id=data.get('student_id', 'Unknown'),
                exam_id=exam_id,
                student_name=data.get('student_name', 'Unknown'),
                score=data.get('score', 0)
            )

            # Add answers
            for ans_data in data.get('answers', []):
                answer = QuestionAnswer(
                    question_number=ans_data.get('question_number', ''),
                    answer_text=ans_data.get('answer_text', ''),
                    is_correct=ans_data.get('is_correct', None),
                    error_type=ans_data.get('error_type', None),
                    evaluation_reason=ans_data.get('evaluation_reason', None),
                    learning_topics=ans_data.get('learning_topics', []),
                    reference_to_answer=ans_data.get('reference_to_answer', None),
                    misconception=ans_data.get('misconception', None)
                )
                student_exam.answers.append(answer)

            student_exams.append(student_exam)

    # Create ExamAnalysis object with loaded data
    from app.models.data_model import ExamAnalysis
    analysis = ExamAnalysis(
        exam_id=exam_id,
        student_exams=student_exams,
        answer_key=answer_key,
        question_difficulty=analysis_data.get('question_difficulty', {}),
        error_patterns=analysis_data.get('error_patterns', {})
    )

    # Generate report
    report_data = analyzer.generate_error_report(analysis)

    # Convert difficulty values from 0-1 to 0-100 scale for display
    # And count difficulty levels
    easy_count = 0
    medium_count = 0
    hard_count = 0

    for q_num, q_data in report_data.items():
        if 'difficulty' in q_data:
            q_data['difficulty'] = q_data['difficulty'] * 100
            # Recategorize based on the new scale
            if q_data['difficulty'] < 30:
                q_data['difficulty_level'] = 'easy'
                easy_count += 1
            elif q_data['difficulty'] < 70:
                q_data['difficulty_level'] = 'medium'
                medium_count += 1
            else:
                q_data['difficulty_level'] = 'hard'
                hard_count += 1

    # Calculate difficulty profile counts
    difficulty_profile = {
        'easy_count': easy_count,
        'medium_count': medium_count,
        'hard_count': hard_count
    }

    return render_template('analysis/report.html',
                           exam_id=exam_id,
                           report=report_data,
                           analysis=analysis_data,
                           difficulty_profile=difficulty_profile)


@analysis_bp.route('/student/<student_id>/<exam_id>')
def student_detail(student_id, exam_id):
    """Show detailed analysis for a specific student's exam."""

    results_dir = current_app.config['RESULTS_DIR']
    student_file = os.path.join(results_dir, f"{student_id}_{exam_id}.json")

    if not os.path.exists(student_file):
        flash(f"Student exam not found")
        return redirect(url_for('analysis.results', exam_id=exam_id))

    with open(student_file, 'r') as f:
        student_data = json.load(f)

    # Find the original exam file automatically
    exams_dir = current_app.config['EXAMS_DIR']

    # Get all available PDF files
    all_pdfs = [f for f in os.listdir(exams_dir) if f.endswith('.pdf')]

    # Check for automatic mapping from processing
    exam_file = None
    if 'pdf_mappings' in session and f"{student_id}_{exam_id}" in session['pdf_mappings']:
        mapped_pdf = session['pdf_mappings'][f"{student_id}_{exam_id}"]
        if os.path.exists(os.path.join(exams_dir, mapped_pdf)):
            exam_file = mapped_pdf
            current_app.logger.info(f"Using PDF mapping: {exam_file}")

    # If there's a manual selection already, use that instead
    if 'pdf_selections' in session and f"{student_id}_{exam_id}" in session['pdf_selections']:
        selected_pdf = session['pdf_selections'][f"{student_id}_{exam_id}"]
        if os.path.exists(os.path.join(exams_dir, selected_pdf)):
            exam_file = selected_pdf
            current_app.logger.info(f"Using manual PDF selection: {exam_file}")

    # If no PDF is associated yet, find the best match
    if not exam_file:
        exam_file = find_best_matching_pdf(student_data, exam_id, exams_dir)
        if exam_file:
            # Store this match for future use
            if 'pdf_mappings' not in session:
                session['pdf_mappings'] = {}
            session['pdf_mappings'][f"{student_id}_{exam_id}"] = exam_file
            session.modified = True
            current_app.logger.info(f"Automatically matched PDF: {exam_file}")

    return render_template('analysis/student_detail.html',
                           student=student_data,
                           exam_id=exam_id,
                           exam_file=exam_file,
                           all_pdfs=all_pdfs)


@analysis_bp.route('/student/<student_id>/<exam_id>/select-pdf')
def select_exam_pdf(student_id, exam_id):
    """Select a specific PDF file for a student."""
    pdf_file = request.args.get('pdf_file')

    print(f"Selecting PDF: {pdf_file} for student {student_id}, exam {exam_id}")

    if pdf_file:
        # Check if the file exists
        exams_dir = current_app.config['EXAMS_DIR']
        pdf_path = os.path.join(exams_dir, pdf_file)

        if not os.path.exists(pdf_path):
            flash(f"Selected PDF file '{pdf_file}' does not exist")
            return redirect(url_for('analysis.student_detail', student_id=student_id, exam_id=exam_id))

        # Store the selection in a session variable
        if 'pdf_selections' not in session:
            session['pdf_selections'] = {}

        session['pdf_selections'][f"{student_id}_{exam_id}"] = pdf_file
        session.modified = True  # Important: mark the session as modified

        print(f"Stored PDF selection in session: {session['pdf_selections']}")
        flash(f"PDF file '{pdf_file}' selected for student {student_id}")
    else:
        flash("No PDF file selected")

    return redirect(url_for('analysis.student_detail', student_id=student_id, exam_id=exam_id))


@analysis_bp.route('/student/<student_id>/<exam_id>/original-pdf')
def original_exam_pdf(student_id, exam_id):
    """Serve the original exam PDF."""
    # Find the original exam file using the same logic as in student_detail
    exams_dir = current_app.config['EXAMS_DIR']
    exam_file = None

    # Debug logging
    print(f"Serving original PDF for student: {student_id}, exam: {exam_id}")

    # Check for automatic mapping from processing
    if 'pdf_mappings' in session and f"{student_id}_{exam_id}" in session['pdf_mappings']:
        mapped_pdf = session['pdf_mappings'][f"{student_id}_{exam_id}"]
        if os.path.exists(os.path.join(exams_dir, mapped_pdf)):
            exam_file = mapped_pdf
            print(f"Using PDF mapping: {exam_file}")

    # Check if we have a stored manual selection for this student
    if not exam_file and 'pdf_selections' in session and f"{student_id}_{exam_id}" in session['pdf_selections']:
        selected_pdf = session['pdf_selections'][f"{student_id}_{exam_id}"]
        if os.path.exists(os.path.join(exams_dir, selected_pdf)):
            exam_file = selected_pdf
            print(f"Using selected PDF: {exam_file}")

    # Try to find best match
    if not exam_file:
        # Find student data
        results_dir = current_app.config['RESULTS_DIR']
        student_file = os.path.join(results_dir, f"{student_id}_{exam_id}.json")

        if os.path.exists(student_file):
            with open(student_file, 'r') as f:
                student_data = json.load(f)

            exam_file = find_best_matching_pdf(student_data, exam_id, exams_dir)
            if exam_file:
                print(f"Using best matching PDF: {exam_file}")

    if not exam_file:
        print("No matching PDF file found")
        flash(f"No PDF file found for student {student_id}")
        return "No PDF file found", 404

    # Get the path to the original PDF
    original_pdf_path = os.path.join(exams_dir, exam_file)
    print(f"Attempting to serve PDF from: {original_pdf_path}")

    try:
        # Verify the file exists and has content
        if not os.path.exists(original_pdf_path):
            print(f"File not found: {original_pdf_path}")
            return "File not found", 404

        file_size = os.path.getsize(original_pdf_path)
        if file_size == 0:
            print(f"File exists but is empty: {original_pdf_path}")
            return "File is empty", 404

        print(f"File exists with size: {file_size} bytes")

        # IMPORTANT: Read the file into memory first, just like the download route does
        with open(original_pdf_path, 'rb') as file:
            pdf_data = file.read()

        print(f"Successfully read {len(pdf_data)} bytes of PDF data")

        # Create a BytesIO object to serve the file from memory
        pdf_io = io.BytesIO(pdf_data)
        pdf_io.seek(0)

        # Return using send_file with the in-memory file
        response = send_file(
            pdf_io,
            mimetype='application/pdf',
            as_attachment=False,
            download_name=f"{student_id}_{exam_id}_original.pdf"
        )

        # Add cache-control headers to prevent caching issues
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'

        return response

    except Exception as e:
        print(f"Error serving PDF: {str(e)}")
        return f"Error: {str(e)}", 500