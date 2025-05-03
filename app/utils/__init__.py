# app/utils/__init__.py
# This file marks the utils directory as a Python package
# Helper functions and utilities can be imported here for easy access

# Example utility function that could be useful across the app
from . import file_utils
def get_file_extension(filename):
    """
    Get the extension of a file.

    Args:
        filename (str): The name of the file

    Returns:
        str: The file extension (lowercase, without the dot)
    """
    if '.' in filename:
        return filename.rsplit('.', 1)[1].lower()
    return ''