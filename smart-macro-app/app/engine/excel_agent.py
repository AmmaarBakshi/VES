import pandas as pd
import os
from app.ai.llm_client import query_ollama
from app.ai.prompts import get_prompt

def process_excel_file(file_path, instruction):
    """
    Reads an Excel file, applies AI to the first column, and saves the result.
    """
    try:
        print(f"Reading Excel: {file_path}")
        df = pd.read_excel(file_path)
        
        # Default to first column
        col_name = df.columns[0]
        
        results = []
        for val in df[col_name]:
            if pd.isna(val) or str(val).strip() == "":
                results.append("")
                continue
            
            # Use the helper to format the prompt
            prompt = get_prompt(instruction, str(val))
            resp = query_ollama(prompt)
            results.append(resp)

        df['AI_Output'] = results
        
        base_name = os.path.basename(file_path)
        dir_name = os.path.dirname(file_path)
        new_path = os.path.join(dir_name, f"PROCESSED_{base_name}")
        
        df.to_excel(new_path, index=False)
        return new_path
    except Exception as e:
        print(f"Excel Error: {e}")
        return f"Error: {e}"


def enrich_excel_file(file_path, options, style="professional"):
    """
    Enhance an existing Excel file with AI-powered improvements.
    
    Args:
        file_path: Path to Excel file
        options: Dict of enhancement options {
            'improve_content': bool,
            'auto_format': bool,
            'add_summaries': bool,
            'fix_consistency': bool
        }
        style: Target style for text improvements
    
    Returns:
        Path to enhanced Excel file
    """
    try:
        from app.engine.content_enricher import ContentEnricher
        from openpyxl import load_workbook
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        import time
        
        enricher = ContentEnricher()
        
        print(f"Reading Excel: {file_path}")
        df = pd.read_excel(file_path)
        
        # Identify text columns (non-numeric)
        text_columns = df.select_dtypes(include=['object']).columns.tolist()
        
        # Improve content in text columns
        if options.get('improve_content', False) and text_columns:
            print("Improving cell content...")
            for col in text_columns:
                improved_values = []
                for val in df[col]:
                    if pd.isna(val) or str(val).strip() == "":
                        improved_values.append(val)
                    else:
                        # Improve text
                        improved = enricher.improve_text(str(val), style=style, intensity="light")
                        improved_values.append(improved)
                
                df[col] = improved_values
        
        # Fix consistency
        if options.get('fix_consistency', False) and text_columns:
            print("Ensuring consistency...")
            for col in text_columns:
                values = [str(v) if not pd.isna(v) else "" for v in df[col]]
                if values:
                    consistent_values = enricher.check_consistency(values, target_style=style)
                    df[col] = consistent_values
        
        # Add summary row
        if options.get('add_summaries', False):
            print("Adding summary insights...")
            summary_row = {}
            
            for col in df.columns:
                if col in text_columns:
                    # Text summary
                    all_text = " ".join([str(v) for v in df[col] if not pd.isna(v)])
                    if all_text.strip():
                        summary = enricher.summarize_content(all_text[:500], max_length=30)
                        summary_row[col] = f"Summary: {summary}" if summary else ""
                    else:
                        summary_row[col] = ""
                else:
                    # Numeric summary
                    try:
                        summary_row[col] = f"Total: {df[col].sum():.2f}"
                    except:
                        summary_row[col] = ""
            
            # Append summary row
            df = pd.concat([df, pd.DataFrame([summary_row])], ignore_index=True)
        
        # Save to temporary file first
        base_name = os.path.basename(file_path)
        name_without_ext = os.path.splitext(base_name)[0]
        dir_name = os.path.dirname(file_path)
        temp_path = os.path.join(dir_name, f"temp_{int(time.time())}.xlsx")
        
        df.to_excel(temp_path, index=False)
        
        # Apply formatting if requested
        if options.get('auto_format', False):
            print("Applying formatting...")
            wb = load_workbook(temp_path)
            ws = wb.active
            
            # Header formatting
            header_fill = PatternFill(start_color="4472C4", end_color="4472C4", fill_type="solid")
            header_font = Font(bold=True, color="FFFFFF", size=12)
            
            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")
            
            # Border for all cells
            thin_border = Border(
                left=Side(style='thin'),
                right=Side(style='thin'),
                top=Side(style='thin'),
                bottom=Side(style='thin')
            )
            
            for row in ws.iter_rows(min_row=1, max_row=ws.max_row, max_col=ws.max_column):
                for cell in row:
                    cell.border = thin_border
                    if cell.row > 1:  # Non-header cells
                        cell.alignment = Alignment(horizontal="left", vertical="top", wrap_text=True)
            
            # Adjust column widths
            for column in ws.columns:
                max_length = 0
                column_letter = column[0].column_letter
                for cell in column:
                    try:
                        if len(str(cell.value)) > max_length:
                            max_length = len(str(cell.value))
                    except:
                        pass
                adjusted_width = min(max_length + 2, 50)
                ws.column_dimensions[column_letter].width = adjusted_width
            
            # Save formatted file
            final_path = os.path.join(dir_name, f"{name_without_ext}_ENHANCED_{int(time.time())}.xlsx")
            wb.save(final_path)
            
            # Remove temp file
            try:
                os.remove(temp_path)
            except:
                pass
        else:
            # Just rename temp file
            final_path = os.path.join(dir_name, f"{name_without_ext}_ENHANCED_{int(time.time())}.xlsx")
            os.rename(temp_path, final_path)
        
        print(f"✅ Enhanced Excel saved: {final_path}")
        return final_path
        
    except Exception as e:
        print(f"Excel Enrichment Error: {e}")
        return f"Error: {e}"


def suggest_excel_improvements(file_path):
    """
    Analyze Excel file and provide improvement suggestions.
    
    Args:
        file_path: Path to Excel file
    
    Returns:
        List of suggestions
    """
    try:
        from app.engine.content_enricher import ContentEnricher
        
        enricher = ContentEnricher()
        df = pd.read_excel(file_path)
        
        suggestions = []
        suggestions.append("=== Excel Data Analysis ===\n")
        
        # Basic stats
        suggestions.append(f"Total Rows: {len(df)}")
        suggestions.append(f"Total Columns: {len(df.columns)}")
        suggestions.append("")
        
        # Check for empty cells
        empty_cells = df.isnull().sum().sum()
        if empty_cells > 0:
            suggestions.append(f"⚠️ Found {empty_cells} empty cells - consider filling or removing")
        
        # Check text columns for improvements
        text_columns = df.select_dtypes(include=['object']).columns.tolist()
        if text_columns:
            suggestions.append(f"\n📝 Text columns found: {', '.join(text_columns)}")
            
            # Sample first text column for suggestions
            if len(df) > 0:
                sample_text = " ".join([str(v) for v in df[text_columns[0]].head(3) if not pd.isna(v)])
                if sample_text:
                    ai_suggestions = enricher.suggest_improvements(
                        sample_text,
                        context="Excel spreadsheet data"
                    )
                    if ai_suggestions:
                        suggestions.append("\n💡 Content Improvement Suggestions:")
                        suggestions.extend(ai_suggestions)
        
        return suggestions
        
    except Exception as e:
        return [f"Error analyzing Excel: {e}"]
