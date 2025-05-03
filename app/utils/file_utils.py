# app/utils/file_utils.py
import os
import logging
import img2pdf
from PIL import Image
import io
from flask import current_app

logger = logging.getLogger(__name__)


def convert_image_to_pdf(image_path, output_dir=None, delete_original=True):
    """Convert an image file to PDF format.

    Args:
        image_path (str): Path to the image file
        output_dir (str, optional): Directory to save the PDF file. If None, uses same directory as image
        delete_original (bool): Whether to delete the original image file after conversion

    Returns:
        str: Path to the generated PDF file
    """
    # Use the same directory as image if output_dir is not specified
    if output_dir is None:
        output_dir = os.path.dirname(image_path)

    # Get the filename without extension
    filename = os.path.basename(image_path)
    name, _ = os.path.splitext(filename)
    pdf_filename = f"{name}.pdf"
    output_path = os.path.join(output_dir, pdf_filename)

    try:
        # Open image to handle any potential issues
        image = Image.open(image_path)

        # Convert to RGB if needed (PDF doesn't support transparency)
        if image.mode in ('RGBA', 'LA'):
            background = Image.new('RGB', image.size, (255, 255, 255))
            background.paste(image, mask=image.split()[3] if image.mode == 'RGBA' else image.split()[1])
            image = background

        # For CMYK or other modes that might cause issues
        if image.mode != 'RGB':
            image = image.convert('RGB')

        # Save as temporary JPG file for conversion
        temp_path = os.path.join(output_dir, f"{name}_temp.jpg")
        image.save(temp_path, "JPEG", quality=95)

        # Convert to PDF
        with open(output_path, "wb") as f:
            f.write(img2pdf.convert(temp_path))

        # Clean up temporary file
        if os.path.exists(temp_path):
            os.remove(temp_path)

        # Delete original if requested
        if delete_original and os.path.exists(image_path):
            os.remove(image_path)

        logger.info(f"Successfully converted {image_path} to {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Error converting image to PDF: {str(e)}")
        if os.path.exists(output_path):
            os.remove(output_path)  # Clean up partial output
        raise


def combine_images_to_pdf(image_paths, output_path, delete_originals=True):
    """Combine multiple images into a single PDF file.

    Args:
        image_paths (list): List of paths to image files
        output_path (str): Path where the PDF should be saved
        delete_originals (bool): Whether to delete the original image files after conversion

    Returns:
        str: Path to the generated PDF file
    """
    if not image_paths:
        raise ValueError("No image paths provided")

    try:
        # Prepare images for conversion
        processed_images = []
        temp_files = []

        for img_path in image_paths:
            # Open image
            image = Image.open(img_path)

            # Convert to RGB if needed
            if image.mode in ('RGBA', 'LA'):
                background = Image.new('RGB', image.size, (255, 255, 255))
                background.paste(image, mask=image.split()[3] if image.mode == 'RGBA' else image.split()[1])
                image = background

            if image.mode != 'RGB':
                image = image.convert('RGB')

            # Create temporary file
            temp_path = f"{img_path}_temp.jpg"
            image.save(temp_path, "JPEG", quality=95)
            temp_files.append(temp_path)
            processed_images.append(temp_path)

        # Convert all images to a single PDF
        with open(output_path, "wb") as f:
            f.write(img2pdf.convert(processed_images))

        # Clean up temporary files
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)

        # Delete originals if requested
        if delete_originals:
            for img_path in image_paths:
                if os.path.exists(img_path):
                    os.remove(img_path)

        logger.info(f"Successfully combined {len(image_paths)} images into {output_path}")
        return output_path

    except Exception as e:
        logger.error(f"Error combining images to PDF: {str(e)}")
        if os.path.exists(output_path):
            os.remove(output_path)  # Clean up partial output

        # Clean up any temporary files
        for temp_file in temp_files:
            if os.path.exists(temp_file):
                os.remove(temp_file)

        raise