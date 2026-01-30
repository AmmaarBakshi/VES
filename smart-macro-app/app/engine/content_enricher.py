"""
AI Content Enrichment Engine

Provides reusable AI-powered functions for enhancing document content:
- Text improvement (grammar, style, clarity)
- Content summarization
- Auto-formatting suggestions
- Content expansion
- Style consistency checking
"""

from app.ai.llm_client import query_ollama
import re


class ContentEnricher:
    """Central AI enrichment engine with various enhancement capabilities"""
    
    def __init__(self):
        self.default_style = "professional"
    
    def improve_text(self, text, style="professional", intensity="moderate"):
        """
        Enhance grammar, clarity, and style of text.
        
        Args:
            text: Original text to improve
            style: Target style (professional, casual, academic, technical)
            intensity: Enhancement level (light, moderate, aggressive)
        
        Returns:
            Improved text
        """
        if not text or not text.strip():
            return text
        
        intensity_instructions = {
            "light": "Make minimal improvements, fixing only obvious errors.",
            "moderate": "Improve clarity and grammar while maintaining the original meaning.",
            "aggressive": "Significantly enhance the text, improving structure, vocabulary, and flow."
        }
        
        prompt = f"""You are a professional editor. {intensity_instructions.get(intensity, intensity_instructions['moderate'])}

Style: {style}
Original text: {text}

Provide ONLY the improved text without any explanations or additional commentary."""
        
        try:
            improved = query_ollama(prompt)
            # Clean up any markdown or extra formatting
            improved = improved.strip().strip('"').strip("'")
            return improved if improved and not improved.startswith("[Error") else text
        except Exception as e:
            print(f"Error improving text: {e}")
            return text
    
    def summarize_content(self, text, max_length=100):
        """
        Generate a concise summary of the text.
        
        Args:
            text: Text to summarize
            max_length: Maximum length of summary in words
        
        Returns:
            Summary text
        """
        if not text or not text.strip():
            return ""
        
        prompt = f"""Summarize the following text in {max_length} words or less. Be concise and capture the key points.

Text: {text}

Provide ONLY the summary without any preamble."""
        
        try:
            summary = query_ollama(prompt)
            summary = summary.strip().strip('"').strip("'")
            return summary if summary and not summary.startswith("[Error") else ""
        except Exception as e:
            print(f"Error summarizing: {e}")
            return ""
    
    def suggest_improvements(self, text, context=""):
        """
        Provide actionable suggestions for improving the content.
        
        Args:
            text: Text to analyze
            context: Additional context about the document
        
        Returns:
            List of improvement suggestions
        """
        if not text or not text.strip():
            return []
        
        context_info = f"\nContext: {context}" if context else ""
        
        prompt = f"""Analyze the following text and provide 3-5 specific, actionable improvement suggestions.{context_info}

Text: {text}

Format your response as a numbered list. Be specific and constructive."""
        
        try:
            suggestions = query_ollama(prompt)
            # Parse suggestions into a list
            lines = [line.strip() for line in suggestions.split('\n') if line.strip()]
            # Filter out lines that look like suggestions
            suggestions_list = [line for line in lines if re.match(r'^\d+[\.\)]\s+', line) or line.startswith('-')]
            return suggestions_list[:5] if suggestions_list else []
        except Exception as e:
            print(f"Error generating suggestions: {e}")
            return []
    
    def format_as_bullets(self, text):
        """
        Convert text to well-structured bullet points.
        
        Args:
            text: Text to convert
        
        Returns:
            List of bullet points
        """
        if not text or not text.strip():
            return []
        
        prompt = f"""Convert the following text into clear, concise bullet points. Each bullet should be a complete thought.

Text: {text}

Provide ONLY the bullet points, one per line, without bullet symbols or numbers."""
        
        try:
            result = query_ollama(prompt)
            # Split into lines and clean up
            bullets = [line.strip().lstrip('-•*').strip() 
                      for line in result.split('\n') 
                      if line.strip() and not line.strip().startswith('[Error')]
            
            return bullets if bullets else [text]
        except Exception as e:
            print(f"Error formatting bullets: {e}")
            return [text]
    
    def expand_content(self, text, target_length=200):
        """
        Elaborate on brief points to create more detailed content.
        
        Args:
            text: Brief text to expand
            target_length: Target length in words
        
        Returns:
            Expanded text
        """
        if not text or not text.strip():
            return text
        
        prompt = f"""Expand and elaborate on the following text to approximately {target_length} words. 
Add relevant details, examples, or explanations while maintaining accuracy.

Original text: {text}

Provide ONLY the expanded text without any preamble."""
        
        try:
            expanded = query_ollama(prompt)
            expanded = expanded.strip().strip('"').strip("'")
            return expanded if expanded and not expanded.startswith("[Error") else text
        except Exception as e:
            print(f"Error expanding content: {e}")
            return text
    
    def check_consistency(self, texts_list, target_style="professional"):
        """
        Ensure style consistency across multiple text segments.
        
        Args:
            texts_list: List of text segments to check
            target_style: Desired consistent style
        
        Returns:
            List of texts with consistent style
        """
        if not texts_list:
            return []
        
        consistent_texts = []
        
        # First, analyze the predominant style
        sample_text = " ".join(texts_list[:3])  # Use first few texts as reference
        
        for text in texts_list:
            if not text or not text.strip():
                consistent_texts.append(text)
                continue
            
            prompt = f"""Rewrite the following text to match this style: {target_style}. 
Ensure it's consistent with professional writing standards.

Text: {text}

Provide ONLY the rewritten text."""
            
            try:
                consistent = query_ollama(prompt)
                consistent = consistent.strip().strip('"').strip("'")
                consistent_texts.append(consistent if consistent and not consistent.startswith("[Error") else text)
            except Exception as e:
                print(f"Error checking consistency: {e}")
                consistent_texts.append(text)
        
        return consistent_texts
    
    def fix_grammar(self, text):
        """
        Fix grammar and spelling errors in text.
        
        Args:
            text: Text to fix
        
        Returns:
            Corrected text
        """
        if not text or not text.strip():
            return text
        
        prompt = f"""Fix all grammar and spelling errors in the following text. Keep the original meaning and style.

Text: {text}

Provide ONLY the corrected text without explanations."""
        
        try:
            fixed = query_ollama(prompt)
            fixed = fixed.strip().strip('"').strip("'")
            return fixed if fixed and not fixed.startswith("[Error") else text
        except Exception as e:
            print(f"Error fixing grammar: {e}")
            return text
    
    def enhance_clarity(self, text):
        """
        Make text clearer and easier to understand.
        
        Args:
            text: Text to clarify
        
        Returns:
            Clearer version of text
        """
        if not text or not text.strip():
            return text
        
        prompt = f"""Rewrite the following text to be clearer and easier to understand. 
Use simple language and remove ambiguity.

Text: {text}

Provide ONLY the clarified text."""
        
        try:
            clear = query_ollama(prompt)
            clear = clear.strip().strip('"').strip("'")
            return clear if clear and not clear.startswith("[Error") else text
        except Exception as e:
            print(f"Error enhancing clarity: {e}")
            return text


# Convenience functions for quick access
def improve_text(text, style="professional", intensity="moderate"):
    """Quick access to text improvement"""
    enricher = ContentEnricher()
    return enricher.improve_text(text, style, intensity)


def summarize(text, max_length=100):
    """Quick access to summarization"""
    enricher = ContentEnricher()
    return enricher.summarize_content(text, max_length)


def get_suggestions(text, context=""):
    """Quick access to improvement suggestions"""
    enricher = ContentEnricher()
    return enricher.suggest_improvements(text, context)
