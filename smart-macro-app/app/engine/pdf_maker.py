from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os
import textwrap

def create_filled_pdf(content, output_path):
    """
    Generates a new PDF file with the AI-generated content.
    """
    try:
        c = canvas.Canvas(output_path, pagesize=letter)
        width, height = letter
        
        # Title
        c.setFont("Helvetica-Bold", 16)
        c.drawString(50, height - 50, "Smart Generated Document")
        
        # Body Content
        c.setFont("Helvetica", 12)
        text_object = c.beginText(50, height - 80)
        
        # Wrap text to fit page
        wrapper = textwrap.TextWrapper(width=80) 
        lines = content.split('\n')
        
        for line in lines:
            wrapped_lines = wrapper.wrap(line)
            for w_line in wrapped_lines:
                text_object.textLine(w_line)
            
            # Simple page break logic
            if text_object.getY() < 50:
                c.drawText(text_object)
                c.showPage()
                text_object = c.beginText(50, height - 50)
                c.setFont("Helvetica", 12)

        c.drawText(text_object)
        c.save()
        return output_path
    except Exception as e:
        return f"Error creating PDF: {e}"