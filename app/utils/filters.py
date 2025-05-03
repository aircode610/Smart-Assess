# app/utils/filters.py
import os
import datetime
from humanize import naturalsize  # We'll use this library for human-readable file sizes


def format_filesize(filename, base_dir=None):
    """Format file size in a human-readable way."""
    if base_dir is None:
        from flask import current_app
        try:
            base_dir = current_app.config['EXAMS_DIR']
        except RuntimeError:
            # Not in Flask context
            return "Unknown"

    try:
        file_path = os.path.join(base_dir, filename)
        if os.path.exists(file_path):
            size_bytes = os.path.getsize(file_path)
            return naturalsize(size_bytes)
        return "File not found"
    except Exception as e:
        return "Error"


def format_filedate(filename, base_dir=None):
    """Format file modification date in a human-readable way."""
    if base_dir is None:
        from flask import current_app
        try:
            base_dir = current_app.config['EXAMS_DIR']
        except RuntimeError:
            # Not in Flask context
            return "Unknown"

    try:
        file_path = os.path.join(base_dir, filename)
        if os.path.exists(file_path):
            mtime = os.path.getmtime(file_path)
            date = datetime.datetime.fromtimestamp(mtime)
            return date.strftime("%Y-%m-%d %H:%M")
        return "File not found"
    except Exception as e:
        return "Error"