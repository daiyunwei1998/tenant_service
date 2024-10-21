# app/services/pdf_generator.py

from jinja2 import Environment, FileSystemLoader, select_autoescape
from weasyprint import HTML
import os
from typing import Dict

from app.core.config import settings  # Ensure this imports your settings

# Initialize Jinja2 environment
template_env = Environment(
    loader=FileSystemLoader(searchpath=os.path.join(os.path.dirname(__file__), '../templates')),
    autoescape=select_autoescape(['html', 'xml'])
)

def generate_invoice_pdf(billing_history: Dict) -> bytes:
    """
    Generates a PDF invoice from billing history data.

    Args:
        billing_history (Dict): Billing history data.

    Returns:
        bytes: Generated PDF content.
    """
    # Load the HTML template
    template = template_env.get_template('invoice_template.html')

    # Render the HTML with billing data
    html_out = template.render(billing_history=billing_history)

    # Convert HTML to PDF
    pdf = HTML(string=html_out).write_pdf()

    return pdf
