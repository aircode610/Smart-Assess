# Smart Assess

A feedback-driven exam analysis platform empowering professors and students with actionable insights.

## Overview
Smart Assess addresses the gap in detailed feedback after exams. Traditional grading often leaves professors unaware of specific topics where students struggle, while students receive little guidance on areas for improvement. Our platform transforms exams from mere assessments into learning opportunities by providing granular error patterns and targeted study references.

## Features
- **Exam Upload & Management**  
  Upload exam papers and answer keys through a user-friendly interface.  
- **Automated Analysis**  
  Leverages AI to detect common error patterns across student submissions.  
- **Detailed Reports**  
  Generates per-student and overall class reports highlighting strengths, weaknesses, and trending misconceptions.  
- **Resource Recommendations**  
  Provides curated study materials and references based on identified error topics.  
- **PDF Highlighting**  
  Visualizes student mistakes directly on exam PDFs for quick review.

## AI
Smart Assess integrates advanced AI models to:
- **Extract Answers** from scanned or digital exam submissions using Google’s Gemini (Vision) API.  
- **Compare Responses** against the answer key to pinpoint exact locations and types of errors.  
- **Cluster Error Patterns** with unsupervised learning, revealing the most frequent misconceptions.  
- **Recommend Resources** by mapping error clusters to a curated knowledge base of study materials.

## Installation and Setup
1. **Clone the Repository**  
   ```bash
   git clone https://github.com/aircode610/Smart-Assess.git
   cd Smart-Assess
   ```
2. **Create a Virtual Environment**  
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   ```
3. **Environment Variables**  
   - Copy `.env.example` to `.env`  
   - Fill in your Google API credentials, Flask secret key, and any other required settings.
4. **Install Dependencies**  
   ```bash
   pip install -r requirements.txt
   ```

## Running the Project
Start the Flask development server:
```bash
export FLASK_APP=run.py
export FLASK_ENV=development
flask run
```
Open your browser at `http://localhost:5000`.

## Usage Guide
1. **Home Page**  
   Navigate to upload new exams or view existing ones.  
2. **Exam Management**  
   - **Upload**: Submit PDF exam papers and their answer keys.  
   - **List**: See all previously uploaded exams.  
   - **View**: Inspect individual exam details and summary statistics.  
3. **Analysis**  
   - Click “Analyze” on an exam to trigger AI processing.  
   - Review error-pattern clusters and individual student reports.  
   - Download detailed PDF reports with highlighted corrections.  
4. **Resources**  
   Access suggested readings and practice resources aligned with the identified weak topics.

## Project Structure
```
Smart Assess/
│
├── app/                         # Main application package
│   ├── __init__.py              # Flask app initialization
│   ├── routes/                  # Route definitions
│   │   ├── __init__.py
│   │   ├── main.py              # Home page routes
│   │   ├── exams.py             # Exam upload and management
│   │   └── analysis.py          # Analysis and results routes
│   │
│   ├── static/                  # Static files (CSS, JS, images)
│   │   ├── css/
│   │   ├── js/
│   │   └── img/
│   │
│   ├── templates/               # HTML templates
│   │   ├── base.html            # Base template
│   │   ├── index.html           # Home page
│   │   ├── exams/               # Exam-related templates
│   │   │   ├── upload.html      # Exam upload form
│   │   │   ├── list.html        # List all exams
│   │   │   └── view.html        # View exam details
│   │   └── analysis/            # Analysis templates
│   │       ├── results.html     # Analysis results
│   │       ├── report.html      # Detailed reports
│   │       ├── list.html        # List of analyses
│   │       └── student_detail.html # Student detail reports
│   │
│   ├── models/                  # Data models
│   │   ├── __init__.py
│   │   └── data_model.py        # Moved existing data models here
│   │
│   ├── services/                # Business logic
│   │   ├── __init__.py
│   │   ├── vision_api.py        # Gemini API service
│   │   ├── exam_processor.py    # Exam processing
│   │   ├── analyzer.py          # Analysis logic
│   │   └── pdf_highlighter.py   # Highlights incorrect PDF answers
│   │
│   └── utils/                   # Utilities
│       ├── __init__.py
│       ├── file_utils.py        # Images to PDF helper functions
│       └── filters.py           # Helper functions
│
├── data/                        # Data storage
│   ├── exams/                   # Uploaded exam files
│   ├── answers/                 # Uploaded answer keys
│   └── results/                 # Generated results
│
├── config.py                    # Configuration (Flask settings)
├── .env.example                 # Environment variables sample
├── requirements.txt             # Python dependencies
└── run.py                       # Application entry point
```

## Technical Implementation
- **Flask** for web framework and routing  
- **Google Gemini (Vision) API** for OCR and answer extraction  
- **Pandas & NumPy** for data manipulation and error clustering  
- **Scikit-learn** for clustering error patterns  
- **Jinja2** templating for dynamic HTML reports  
- **PyPDF2** (or similar) for PDF highlighting  

## Link to Video
[▶️ Smart Assess Demo Video](https://youtu.be/your-demo-video-link)
