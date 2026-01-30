import os
from docx import Document
from app.ai.llm_client import query_ollama

def process_word_document(file_path, instruction="Fix grammar and make professional"):
    """
    Reads a .docx file, processes each paragraph with AI, and saves a new copy.
    """
    try:
        doc = Document(file_path)
        
        # Loop through paragraphs (skipping empty ones to save time)
        total_paragraphs = len([p for p in doc.paragraphs if p.text.strip()])
        processed_count = 0

        print(f"Processing {total_paragraphs} paragraphs...")

        for paragraph in doc.paragraphs:
            if paragraph.text.strip():
                # Send original text + user instruction to AI
                full_prompt = f"Instruction: {instruction}\n\nText: {paragraph.text}"
                
                # Get result from AI
                new_text = query_ollama(full_prompt)
                
                # Replace text in the document
                paragraph.text = new_text
                processed_count += 1
                print(f" - Processed paragraph {processed_count}/{total_paragraphs}")

        # Save the new file
        dir_name = os.path.dirname(file_path)
        base_name = os.path.basename(file_path)
        new_path = os.path.join(dir_name, f"PROCESSED_{base_name}")
        
        doc.save(new_path)
        return new_path

    except Exception as e:
        print(f"Error processing file: {e}")
        return None


def enrich_word_document(file_path, options, style="professional"):
    """
    Enhance an existing Word document with AI-powered improvements.
    
    Args:
        file_path: Path to .docx file
        options: Dict of enhancement options {
            'improve_paragraphs': bool,
            'add_summary': bool,
            'fix_consistency': bool,
            'auto_format': bool
        }
        style: Target style for text improvements
    
    Returns:
        Path to enhanced document
    """
    try:
        from app.engine.content_enricher import ContentEnricher
        from docx.shared import Pt, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
        import time
        
        enricher = ContentEnricher()
        doc = Document(file_path)
        
        # Collect all paragraphs for consistency check
        all_paragraphs = [p for p in doc.paragraphs if p.text.strip()]
        
        # Improve paragraphs
        if options.get('improve_paragraphs', False):
            print(f"Improving {len(all_paragraphs)} paragraphs...")
            for idx, paragraph in enumerate(all_paragraphs):
                if paragraph.text.strip():
                    original = paragraph.text
                    improved = enricher.improve_text(original, style=style, intensity="moderate")
                    paragraph.text = improved
                    print(f" - Processed paragraph {idx + 1}/{len(all_paragraphs)}")
        
        # Fix consistency
        if options.get('fix_consistency', False):
            print("Ensuring style consistency...")
            paragraph_texts = [p.text for p in all_paragraphs if p.text.strip()]
            if paragraph_texts:
                consistent_texts = enricher.check_consistency(paragraph_texts, target_style=style)
                
                # Apply consistent texts back
                text_idx = 0
                for paragraph in doc.paragraphs:
                    if paragraph.text.strip() and text_idx < len(consistent_texts):
                        paragraph.text = consistent_texts[text_idx]
                        text_idx += 1
        
        # Add document summary at the beginning
        if options.get('add_summary', False):
            print("Generating document summary...")
            # Collect all text
            full_text = " ".join([p.text for p in all_paragraphs])
            
            if full_text.strip():
                summary = enricher.summarize_content(full_text[:2000], max_length=150)
                
                if summary:
                    # Insert summary at the beginning
                    summary_para = doc.paragraphs[0].insert_paragraph_before("Executive Summary")
                    summary_para.style = 'Heading 1'
                    
                    content_para = doc.paragraphs[1].insert_paragraph_before(summary)
                    content_para.style = 'Normal'
                    
                    # Add spacing
                    doc.paragraphs[2].insert_paragraph_before("")
        
        # Apply formatting
        if options.get('auto_format', False):
            print("Applying formatting...")
            for paragraph in doc.paragraphs:
                # Set consistent font
                for run in paragraph.runs:
                    run.font.name = 'Calibri'
                    if run.font.size is None or run.font.size < Pt(11):
                        run.font.size = Pt(11)
                
                # Set line spacing
                paragraph.paragraph_format.line_spacing = 1.15
                paragraph.paragraph_format.space_after = Pt(6)
        
        # Save enhanced document
        base_name = os.path.basename(file_path)
        name_without_ext = os.path.splitext(base_name)[0]
        dir_name = os.path.dirname(file_path)
        new_path = os.path.join(dir_name, f"{name_without_ext}_ENHANCED_{int(time.time())}.docx")
        
        doc.save(new_path)
        print(f"✅ Enhanced document saved: {new_path}")
        return new_path
        
    except Exception as e:
        print(f"Word Enrichment Error: {e}")
        return None


def suggest_word_improvements(file_path):
    """
    Analyze Word document and provide improvement suggestions.
    
    Args:
        file_path: Path to .docx file
    
    Returns:
        List of suggestions
    """
    try:
        from app.engine.content_enricher import ContentEnricher
        
        enricher = ContentEnricher()
        doc = Document(file_path)
        
        suggestions = []
        suggestions.append("=== Document Analysis ===\n")
        
        # Count paragraphs
        paragraphs = [p for p in doc.paragraphs if p.text.strip()]
        suggestions.append(f"Total Paragraphs: {len(paragraphs)}")
        
        # Word count
        total_words = sum(len(p.text.split()) for p in paragraphs)
        suggestions.append(f"Total Words: {total_words}")
        suggestions.append("")
        
        # Get AI suggestions for first few paragraphs
        if paragraphs:
            sample_text = " ".join([p.text for p in paragraphs[:3]])
            if sample_text:
                ai_suggestions = enricher.suggest_improvements(
                    sample_text,
                    context="Word document"
                )
                
                if ai_suggestions:
                    suggestions.append("💡 Content Improvement Suggestions:")
                    suggestions.extend(ai_suggestions)
        
        return suggestions
        
    except Exception as e:
        return [f"Error analyzing document: {e}"]
