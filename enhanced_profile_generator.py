import os
import json
from typing import List, Dict, Any
from openai import OpenAI
from pathlib import Path
import re

class EnhancedProfileGenerator:
    def __init__(self):
        """Initialize with OpenAI client and enhanced system prompt"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")
        self.client = OpenAI(api_key=api_key)
        
        self.system_prompt = """You are a world-class expert in HR analytics, leadership psychology, and organizational behavior. You specialize in creating comprehensive employee profiles that combine assessment data with structured HR categories. Your goal is to extract both explicit information and make informed inferences while clearly marking the confidence level of each insight.

You must be extremely careful to distinguish between:
1. EXTRACTED DATA: Information directly stated in documents (high confidence)
2. ASSESSMENT INSIGHTS: Direct scores/results from assessments (high confidence) 
3. INFERRED INSIGHTS: Logical deductions from available data (marked as AI interpretation)
4. MISSING DATA: Categories where insufficient information exists (marked as null)

Always cite sources and indicate confidence levels for your insights."""

    def generate_enhanced_profile(self, document_chunks: List[str], metadata: List[dict] = None, existing_profile: Dict[str, Any] = None) -> str:
        """Generate an enhanced profile with additional HR categories"""
        
        # Identify document types first
        doc_types = self._identify_document_types(document_chunks)
        doc_type_list = ", ".join(doc_types) if doc_types else "Submitted Documents"
        
        # Combine document content
        context = "\n\n".join(document_chunks)
        
        # Build metadata context
        metadata_text = ""
        if metadata and len(metadata) > 0:
            metadata_items = []
            for meta in metadata:
                for key, value in meta.items():
                    if key not in ['file_type', 'filename']:
                        metadata_items.append(f"{key}: {value}")
            metadata_text = "\n".join(metadata_items)

        # Enhanced prompt with tiered confidence structure
        prompt = f"""Based on the following documents, create a comprehensive employee profile with both traditional leadership insights and structured HR data.

DOCUMENT TYPES IDENTIFIED: {doc_type_list}

CRITICAL INSTRUCTIONS FOR DATA CATEGORIZATION:
1. EXTRACTED_DATA: Only include information explicitly stated in documents
2. ASSESSMENT_INSIGHTS: Direct scores/results from formal assessments  
3. INFERRED_INSIGHTS: Mark as AI interpretations with confidence levels
4. MISSING_DATA: Set to null when insufficient information exists

{metadata_text}

DOCUMENT CONTENT:
{context}

Generate a JSON profile with the following structure:

{{
  "traditional_sections": [
    {{"section": "Profile Summary", "content": "...", "sources": "...", "confidence": "high|medium|low"}},
    {{"section": "Key Strengths", "content": "1. ...\n\n2. ...", "sources": "...", "confidence": "high|medium|low"}},
    {{"section": "Potential Derailers", "content": "1. ...\n\n2. ...", "sources": "...", "confidence": "high|medium|low"}},
    {{"section": "Leadership Style", "content": "...", "sources": "...", "confidence": "high|medium|low"}},
    {{"section": "Roles That Would Fit", "content": "1. ...\n\n2. ...", "sources": "...", "confidence": "high|medium|low"}},
    {{"section": "Roles That Would Not Fit", "content": "1. ...\n\n2. ...", "sources": "...", "confidence": "high|medium|low"}}
  ],
  "professional_info": {{
    "current_position": "..." or null,
    "department": "..." or null,
    "years_experience": number or null,
    "education_level": "..." or null,
    "certifications": ["..."] or null,
    "data_source": "extracted|inferred|missing",
    "confidence": "high|medium|low"
  }},
  "performance_metrics": {{
    "last_performance_rating": "..." or null,
    "key_achievements": ["..."] or null,
    "areas_for_improvement": ["..."] or null,
    "promotion_readiness": "ready|developing|not_ready" or null,
    "data_source": "extracted|inferred|missing",
    "confidence": "high|medium|low"
  }},
  "skills_assessment": {{
    "technical_skills": ["..."] or null,
    "leadership_skills": ["..."] or null,
    "communication_skills": ["..."] or null,
    "analytical_skills": ["..."] or null,
    "skill_gaps": ["..."] or null,
    "data_source": "extracted|inferred|missing",
    "confidence": "high|medium|low"
  }},
  "assessment_scores": {{
    "personality_scores": {{}} or null,
    "competency_ratings": {{}} or null,
    "360_feedback_summary": {{}} or null,
    "other_assessments": {{}} or null,
    "data_source": "extracted|missing",
    "confidence": "high|medium|low"
  }},
  "work_style": {{
    "collaboration_preference": "..." or null,
    "decision_making_style": "..." or null,
    "communication_style": "..." or null,
    "stress_response": "..." or null,
    "motivation_drivers": ["..."] or null,
    "data_source": "extracted|inferred|missing",
    "confidence": "high|medium|low"
  }},
  "career_development": {{
    "career_aspirations": "..." or null,
    "development_priorities": ["..."] or null,
    "mentoring_needs": ["..."] or null,
    "succession_planning": "..." or null,
    "mobility_preferences": "..." or null,
    "data_source": "extracted|inferred|missing",
    "confidence": "high|medium|low"
  }},
  "team_dynamics": {{
    "team_role_preference": "..." or null,
    "conflict_management": "..." or null,
    "influence_style": "..." or null,
    "cross_functional_ability": "..." or null,
    "cultural_fit": "..." or null,
    "data_source": "extracted|inferred|missing",
    "confidence": "high|medium|low"
  }}
}}

FORMATTING GUIDELINES:
- Use numbered lists for enumerated sections (1., 2., etc.) with double line breaks
- Include source citations in parentheses: (Hogan Assessment), (CV/Resume), etc.
- Mark confidence levels honestly: high=directly stated, medium=strong inference, low=weak inference
- Set null for categories without sufficient data - DO NOT fabricate information
- For data_source: "extracted"=directly from docs, "inferred"=AI interpretation, "missing"=insufficient data

Return only the JSON, no additional commentary."""

        # Generate the enhanced profile
        response = self.client.chat.completions.create(
            model="gpt-4.1-2025-04-14",
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,  # Lower temperature for more consistent structure
            max_tokens=4000
        )

        profile_content = response.choices[0].message.content
        
        # Clean up the JSON content
        profile_content = self._clean_profile_sources(profile_content)
        
        return profile_content

    def _identify_document_types(self, document_chunks: List[str]) -> List[str]:
        """Identify document types from content"""
        context = " ".join(document_chunks).lower()
        doc_types = []
        
        # Check for various document types
        if any(term in context for term in ["hogan", "hpi", "hds", "mvpi"]):
            doc_types.append("Hogan Assessment")
        if "360" in context:
            doc_types.append("360° Feedback")
        if any(term in context for term in ["cv", "resume", "curriculum vitae"]):
            doc_types.append("CV/Resume")
        if "intercultural development" in context:
            doc_types.append("IDI Assessment")
        if any(term in context for term in ["performance review", "annual review"]):
            doc_types.append("Performance Review")
        if "interview" in context:
            doc_types.append("Interview Notes")
            
        return doc_types

    def _clean_profile_sources(self, profile_content: str) -> str:
        """Clean up temporary filenames and improve source citations"""
        try:
            # Clean up temporary filenames
            temp_patterns = [
                r'tmp[a-zA-Z0-9]+\.[a-z]+',
                r'tmp[a-zA-Z0-9]+\.pdf',
                r'\(tmp[^)]*\)'
            ]
            
            for pattern in temp_patterns:
                profile_content = re.sub(pattern, '', profile_content)
            
            # Clean up multiple commas and whitespace
            profile_content = re.sub(r',\s*,', ',', profile_content)
            profile_content = re.sub(r',\s*}', '}', profile_content)
            profile_content = re.sub(r'\s+', ' ', profile_content)
            
            return profile_content
        except Exception as e:
            print(f"Error cleaning profile sources: {e}")
            return profile_content 