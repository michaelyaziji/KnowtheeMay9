import os
import json
import tiktoken
from typing import List, Dict, Any, Optional
from openai import OpenAI
from vector_store import VectorStore
from employee_database import EmployeeDatabase

class RAGQuerySystem:
    def __init__(self):
        """Initialize the RAG query system with intelligent context management"""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")
        self.client = OpenAI(api_key=api_key)
        self.vector_store = VectorStore()
        self.employee_db = EmployeeDatabase()
        
        # Initialize token encoder for GPT-4
        self.encoding = tiktoken.encoding_for_model("gpt-4")
        
        # Intelligent conversation management settings
        self.max_context_tokens = 6000  # Leave room for response tokens in 8K context
        self.max_conversation_tokens = 2000  # Max tokens for conversation history
        self.min_conversation_exchanges = 2  # Always keep at least 2 exchanges
        
        # Dynamic employee limits based on query type
        self.employee_limits = {
            "individual_profile": {"max": 5, "priority": 3},
            "cross_comparison": {"max": 8, "priority": 5}, 
            "team_analysis": {"max": 15, "priority": 10},
            "succession_planning": {"max": 20, "priority": 15},
            "department_analysis": {"max": 25, "priority": 20},
            "organization_wide": {"max": 50, "priority": 30},
            "general_guidance": {"max": 10, "priority": 5}
        }
        
        # User-configurable settings
        self.conversation_settings = {
            "enable_context_tracking": True,
            "max_conversation_memory": "adaptive",  # "adaptive", "short", "medium", "long"
            "employee_focus_mode": "adaptive",  # "narrow", "adaptive", "broad"
            "include_conversation_hints": True
        }
        
        # Load interpretation guidelines
        self.interpretation_docs = self._load_interpretation_docs()
        
        # Enhanced conversation tracking
        self.conversation_history = []
        self.context_employees = []  # Current context employees with scores
        self.conversation_metadata = {
            "total_tokens_used": 0,
            "peak_employee_count": 0,
            "conversation_theme": None
        }
        
        self.system_prompt = """You are an advanced HR Analytics AI with deep expertise in leadership psychology, organizational behavior, and talent management. You have access to a comprehensive database of employee profiles, assessment results, and interpretation guidelines.

Your capabilities include:
1. Intelligent cross-employee analysis and comparisons
2. Pattern recognition across teams and departments
3. Sophisticated interpretation of assessment data
4. Strategic recommendations for talent development and placement
5. Risk assessment and succession planning insights
6. CONTEXTUAL CONVERSATION - You maintain conversation context intelligently

Always provide evidence-based responses with specific citations. When making recommendations, consider both individual data and organizational context. You adapt your analysis scope based on the complexity and type of query."""

    def _count_tokens(self, text: str) -> int:
        """Count tokens in text using GPT-4 tokenizer"""
        try:
            return len(self.encoding.encode(text))
        except:
            # Fallback estimation: ~4 characters per token
            return len(text) // 4

    def _get_conversation_token_limit(self) -> int:
        """Get adaptive conversation token limit based on settings"""
        if self.conversation_settings["max_conversation_memory"] == "short":
            return 800
        elif self.conversation_settings["max_conversation_memory"] == "medium":
            return 1500
        elif self.conversation_settings["max_conversation_memory"] == "long":
            return 2500
        else:  # adaptive
            # Adjust based on conversation complexity
            if len(self.context_employees) > 10:
                return 1200  # Reduce history for complex employee contexts
            elif len(self.context_employees) > 5:
                return 1800
            else:
                return 2000

    def _get_employee_limit_for_query(self, query_type: str, scope: str) -> Dict[str, int]:
        """Get intelligent employee limits based on query type and scope"""
        base_limits = self.employee_limits.get(query_type, self.employee_limits["general_guidance"])
        
        # Adjust based on user settings
        if self.conversation_settings["employee_focus_mode"] == "narrow":
            return {"max": min(base_limits["max"], 8), "priority": min(base_limits["priority"], 5)}
        elif self.conversation_settings["employee_focus_mode"] == "broad":
            return {"max": base_limits["max"] + 10, "priority": base_limits["priority"] + 5}
        else:  # adaptive
            # Adjust based on scope
            if scope == "single_employee":
                return {"max": 5, "priority": 3}
            elif scope == "multiple_employees":
                return {"max": 12, "priority": 8}
            elif scope == "department":
                return {"max": 20, "priority": 15}
            else:
                return base_limits

    def update_conversation_settings(self, settings: Dict[str, Any]):
        """Update user-configurable conversation settings"""
        for key, value in settings.items():
            if key in self.conversation_settings:
                self.conversation_settings[key] = value

    def get_conversation_status(self) -> Dict[str, Any]:
        """Get current conversation status and statistics"""
        return {
            "conversation_length": len(self.conversation_history),
            "context_employees_count": len(self.context_employees),
            "total_tokens_used": self.conversation_metadata["total_tokens_used"],
            "conversation_theme": self.conversation_metadata["conversation_theme"],
            "settings": self.conversation_settings.copy(),
            "memory_status": self._get_memory_status()
        }

    def _get_memory_status(self) -> Dict[str, Any]:
        """Get current memory usage status"""
        total_conversation_tokens = sum(
            self._count_tokens(entry["original_query"] + entry["response"]) 
            for entry in self.conversation_history
        )
        
        limit = self._get_conversation_token_limit()
        
        return {
            "conversation_tokens": total_conversation_tokens,
            "token_limit": limit,
            "usage_percentage": (total_conversation_tokens / limit) * 100,
            "context_employees": [emp["name"] for emp in self.context_employees]
        }

    def _load_interpretation_docs(self) -> List[str]:
        """Load interpretation documentation"""
        interpretation_docs = []
        
        # Check for HowToInterpret directory
        interpret_dir = "HowToInterpret"
        if os.path.exists(interpret_dir):
            for filename in os.listdir(interpret_dir):
                if filename.endswith(('.txt', '.md', '.pdf', '.docx')):
                    file_path = os.path.join(interpret_dir, filename)
                    try:
                        # For now, assume text files. We can expand this later
                        if filename.endswith('.txt'):
                            with open(file_path, 'r', encoding='utf-8') as f:
                                content = f.read()
                                interpretation_docs.append(f"=== {filename} ===\n{content}")
                    except Exception as e:
                        print(f"Warning: Could not load {filename}: {e}")
        
        return interpretation_docs

    def process_complex_query(self, query: str, context_type: str = "general", 
                             conversation_id: str = "default") -> Dict[str, Any]:
        """
        Process complex queries with intelligent conversation context management
        
        Args:
            query: The user's question
            context_type: Type of analysis ("individual", "team", "comparison", "general")
            conversation_id: Unique identifier for this conversation thread
        """
        
        # Step 1: Resolve contextual references in the query
        resolved_query, context_employees = self._resolve_contextual_query(query)
        
        # Step 2: Analyze the resolved query to understand what type of response is needed
        query_analysis = self._analyze_query_intent(resolved_query, context_employees)
        
        # Step 3: Get intelligent limits for this query type
        employee_limits = self._get_employee_limit_for_query(
            query_analysis.get("query_type", "general_guidance"),
            query_analysis.get("scope", "single_employee")
        )
        
        # Step 4: Gather relevant context with intelligent limits
        context_chunks = self._gather_relevant_context(
            resolved_query, query_analysis, context_employees, employee_limits
        )
        
        # Step 5: Generate intelligent response with conversation awareness
        response = self._generate_intelligent_response(
            resolved_query, context_chunks, query_analysis, query
        )
        
        # Step 6: Update conversation tracking with token management
        self._update_conversation_history(query, resolved_query, response, context_employees, query_analysis)
        
        # Step 7: Update context employees with intelligent scoring
        self._update_context_employees(response, context_employees, query_analysis)
        
        # Step 8: Manage memory based on token limits
        self._manage_conversation_memory()
        
        return {
            "query": query,
            "resolved_query": resolved_query,
            "analysis": query_analysis,
            "response": response,
            "context_sources": len(context_chunks),
            "context_employees": [emp["name"] if isinstance(emp, dict) else emp for emp in self.context_employees],
            "employee_limits": employee_limits,
            "conversation_status": self.get_conversation_status(),
            "conversation_id": conversation_id
        }

    def _update_conversation_history(self, original_query: str, resolved_query: str, 
                                   response: str, context_employees: List[str], 
                                   query_analysis: Dict[str, Any]):
        """Update conversation history with metadata"""
        tokens_used = self._count_tokens(original_query + resolved_query + response)
        
        conversation_entry = {
            "original_query": original_query,
            "resolved_query": resolved_query,
            "response": response,
            "context_employees": context_employees,
            "query_type": query_analysis.get("query_type", "general"),
            "tokens_used": tokens_used,
            "timestamp": self._get_timestamp()
        }
        
        self.conversation_history.append(conversation_entry)
        self.conversation_metadata["total_tokens_used"] += tokens_used
        
        # Update conversation theme if not set
        if not self.conversation_metadata["conversation_theme"]:
            self.conversation_metadata["conversation_theme"] = query_analysis.get("query_type", "general")

    def _update_context_employees(self, response: str, context_employees: List[str], 
                                query_analysis: Dict[str, Any]):
        """Update context employees with intelligent scoring and relevance tracking"""
        
        # Extract employees mentioned in response
        response_employees = self._extract_employee_names_from_response(response)
        
        # Create new context employee entries with scores
        new_context_employees = []
        
        # Add context employees from query (highest priority)
        for emp_name in context_employees:
            employee_entry = {
                "name": emp_name,
                "relevance_score": 1.0,  # Highest relevance
                "source": "query_context",
                "first_mentioned": self._get_timestamp(),
                "query_types": [query_analysis.get("query_type", "general")]
            }
            new_context_employees.append(employee_entry)
        
        # Add employees from response (medium priority)
        for emp_name in response_employees:
            if not any(emp["name"] == emp_name for emp in new_context_employees):
                employee_entry = {
                    "name": emp_name,
                    "relevance_score": 0.8,
                    "source": "response_mention",
                    "first_mentioned": self._get_timestamp(),
                    "query_types": [query_analysis.get("query_type", "general")]
                }
                new_context_employees.append(employee_entry)
        
        # Merge with existing context employees, updating scores
        for new_emp in new_context_employees:
            existing_emp = next((emp for emp in self.context_employees 
                               if emp.get("name") == new_emp["name"]), None)
            
            if existing_emp:
                # Update existing employee - boost score and add query type
                existing_emp["relevance_score"] = min(1.0, existing_emp["relevance_score"] + 0.2)
                if new_emp["query_types"][0] not in existing_emp["query_types"]:
                    existing_emp["query_types"].append(new_emp["query_types"][0])
            else:
                # Add new employee
                self.context_employees.append(new_emp)
        
        # Sort by relevance score and limit based on settings
        self.context_employees.sort(key=lambda x: x["relevance_score"], reverse=True)
        
        # Apply intelligent limits
        max_employees = self._get_max_context_employees()
        if len(self.context_employees) > max_employees:
            self.context_employees = self.context_employees[:max_employees]
        
        # Update peak count
        self.conversation_metadata["peak_employee_count"] = max(
            self.conversation_metadata["peak_employee_count"],
            len(self.context_employees)
        )

    def _get_max_context_employees(self) -> int:
        """Get maximum context employees based on conversation complexity and settings"""
        base_limit = 15  # Default
        
        if self.conversation_settings["employee_focus_mode"] == "narrow":
            base_limit = 8
        elif self.conversation_settings["employee_focus_mode"] == "broad":
            base_limit = 25
        
        # Adjust based on conversation theme
        theme = self.conversation_metadata.get("conversation_theme", "general")
        if theme in ["succession_planning", "department_analysis"]:
            base_limit = min(base_limit + 10, 30)
        elif theme == "individual_profile":
            base_limit = min(base_limit, 10)
        
        return base_limit

    def _manage_conversation_memory(self):
        """Intelligent conversation memory management based on token limits"""
        if not self.conversation_history:
            return
        
        # Calculate total conversation tokens
        total_tokens = sum(entry["tokens_used"] for entry in self.conversation_history)
        token_limit = self._get_conversation_token_limit()
        
        # If we're under the limit, no need to prune
        if total_tokens <= token_limit:
            return
        
        # Keep minimum exchanges regardless of token count
        if len(self.conversation_history) <= self.min_conversation_exchanges:
            return
        
        # Prune oldest conversations while staying above minimum
        while (len(self.conversation_history) > self.min_conversation_exchanges and 
               sum(entry["tokens_used"] for entry in self.conversation_history) > token_limit):
            
            removed_entry = self.conversation_history.pop(0)
            
            # Update employee relevance scores when removing old context
            self._decay_employee_relevance_scores(removed_entry)

    def _decay_employee_relevance_scores(self, removed_entry: Dict[str, Any]):
        """Decay relevance scores for employees from removed conversation entries"""
        removed_employees = removed_entry.get("context_employees", [])
        
        for emp_name in removed_employees:
            emp_entry = next((emp for emp in self.context_employees 
                            if emp.get("name") == emp_name), None)
            if emp_entry:
                emp_entry["relevance_score"] = max(0.1, emp_entry["relevance_score"] - 0.3)
        
        # Remove employees with very low relevance scores
        self.context_employees = [emp for emp in self.context_employees 
                                 if emp["relevance_score"] > 0.15]

    def _resolve_contextual_query(self, query: str) -> tuple[str, List[str]]:
        """
        Resolve contextual references in queries with intelligent employee context
        
        Returns:
            tuple: (resolved_query, list_of_employee_names)
        """
        context_employees = []
        resolved_query = query
        
        # Check for contextual references
        contextual_indicators = [
            "between them", "among them", "between the two", "among the two",
            "which of them", "who among them", "these employees", "those employees",
            "the two", "both of them", "either of them", "these people",
            "them", "they", "the candidates", "the employees", "the team members",
            "the individuals", "the people mentioned", "those people"
        ]
        
        query_lower = query.lower()
        has_contextual_reference = any(indicator in query_lower for indicator in contextual_indicators)
        
        if has_contextual_reference and self.context_employees:
            # Get employee names from context, prioritizing by relevance score
            employee_names = [emp["name"] if isinstance(emp, dict) else emp 
                            for emp in self.context_employees[:8]]  # Top 8 most relevant
            context_employees = employee_names.copy()
            
            # Create a more specific query
            if len(employee_names) == 2:
                names_text = f"{employee_names[0]} and {employee_names[1]}"
            elif len(employee_names) <= 5:
                names_text = ", ".join(employee_names[:-1]) + f", and {employee_names[-1]}"
            else:
                # For larger groups, use more general reference
                names_text = f"{employee_names[0]}, {employee_names[1]}, and {len(employee_names)-2} other employees"
            
            # Replace common contextual terms with intelligent context
            replacements = {
                "between them": f"between {names_text}",
                "among them": f"among {names_text}",
                "between the two": f"between {names_text}",
                "among the two": f"among {names_text}",
                "which of them": f"which of {names_text}",
                "who among them": f"who among {names_text}",
                "these employees": names_text,
                "those employees": names_text,
                "the two": names_text,
                "both of them": f"both {names_text}",
                "either of them": f"either {names_text}",
                "these people": names_text,
                "the candidates": names_text,
                "the employees": names_text,
                "the team members": names_text,
                "the individuals": names_text,
                "the people mentioned": names_text,
                "those people": names_text
            }
            
            for old_text, new_text in replacements.items():
                if old_text in query_lower:
                    # Case-insensitive replacement
                    import re
                    pattern = re.compile(re.escape(old_text), re.IGNORECASE)
                    resolved_query = pattern.sub(new_text, resolved_query)
                    break
        
        return resolved_query, context_employees

    def _get_timestamp(self) -> str:
        """Get current timestamp for conversation tracking"""
        import time
        return time.strftime('%Y-%m-%d %H:%M:%S')
    
    def clear_conversation_history(self):
        """Clear conversation history and reset all tracking variables for a fresh start"""
        self.conversation_history = []
        self.context_employees = []
        self.conversation_metadata = {
            "total_tokens_used": 0,
            "peak_employee_count": 0,
            "conversation_theme": None
        }
        print("Conversation history cleared. Starting fresh conversation context.")

    def _analyze_query_intent(self, query: str, context_employees: List[str] = []) -> Dict[str, Any]:
        """Analyze what type of query this is and what information is needed"""
        
        analysis_prompt = f"""Analyze this HR/talent management query to understand the intent and required information:

Query: "{query}"

Determine:
1. Query type: individual_profile, team_analysis, cross_comparison, succession_planning, risk_assessment, general_guidance
2. Scope: single_employee, multiple_employees, department, organization-wide
3. Required data: personality_scores, performance_data, career_history, skills_assessment, leadership_style, team_dynamics
4. Analysis depth: surface_level, detailed_analysis, strategic_recommendations
5. Key entities: Extract any specific names, departments, roles mentioned

Return as JSON:
{{
  "query_type": "...",
  "scope": "...",
  "required_data": ["...", "..."],
  "analysis_depth": "...",
  "key_entities": ["...", "..."],
  "specific_request": "brief description of what user wants"
}}"""

        response = self.client.chat.completions.create(
            model="gpt-4.1-2025-04-14",
            messages=[
                {"role": "user", "content": analysis_prompt}
            ],
            temperature=0.2,
            max_tokens=500
        )
        
        try:
            analysis = json.loads(response.choices[0].message.content)
            analysis["key_entities"] = context_employees
            return analysis
        except:
            # Fallback if JSON parsing fails
            return {
                "query_type": "general_guidance",
                "scope": "single_employee",
                "required_data": ["general"],
                "analysis_depth": "detailed_analysis",
                "key_entities": [],
                "specific_request": query
            }

    def _gather_relevant_context(self, query: str, analysis: Dict[str, Any], 
                               context_employees: List[str] = [], 
                               employee_limits: Dict[str, int] = None) -> List[str]:
        """Gather relevant context with intelligent employee limits and prioritization"""
        context_chunks = []
        
        # Set default limits if not provided
        if employee_limits is None:
            employee_limits = {"max": 10, "priority": 5}
        
        max_employees = employee_limits["max"]
        priority_employees = employee_limits["priority"]
        
        # Add interpretation guidelines if relevant
        if analysis.get("query_type") in ["individual_profile", "succession_planning", "risk_assessment"]:
            context_chunks.extend(self.interpretation_docs[:2])  # Top 2 interpretation docs
        
        # PRIORITY 1: Context employees from conversation (highest priority)
        employees_added = 0
        if context_employees:
            print(f"DEBUG: Using context employees: {context_employees}")
            employees = self.employee_db.get_all_employees()
            for target_name in context_employees:
                if employees_added >= priority_employees:
                    break
                for emp in employees:
                    if target_name.lower() in emp['name'].lower() or emp['name'].lower() in target_name.lower():
                        employee_context = self._get_employee_context(emp['id'], analysis)
                        context_chunks.extend(employee_context)
                        employees_added += 1
                        print(f"DEBUG: Added priority context for {emp['name']}")
                        break
        
        # PRIORITY 2: High-relevance employees from conversation history
        if employees_added < priority_employees:
            high_relevance_employees = [
                emp for emp in self.context_employees 
                if isinstance(emp, dict) and emp.get("relevance_score", 0) > 0.7
            ][:priority_employees - employees_added]
            
            employees = self.employee_db.get_all_employees()
            for context_emp in high_relevance_employees:
                emp_name = context_emp["name"]
                for emp in employees:
                    if emp_name.lower() in emp['name'].lower() or emp['name'].lower() in emp_name.lower():
                        employee_context = self._get_employee_context(emp['id'], analysis)
                        context_chunks.extend(employee_context)
                        employees_added += 1
                        print(f"DEBUG: Added high-relevance context for {emp['name']}")
                        break
        
        # PRIORITY 3: Semantic search for additional employees up to max limit
        remaining_slots = max_employees - employees_added
        if remaining_slots > 0:
            scope = analysis.get("scope", "single_employee")
            
            if scope == "single_employee":
                # Try to find specific employee mentioned
                entities = analysis.get("key_entities", [])
                employees = self.employee_db.get_all_employees()
                
                for entity in entities:
                    if employees_added >= max_employees:
                        break
                    # Search for employee by name
                    for emp in employees:
                        if entity.lower() in emp['name'].lower():
                            # Skip if already added
                            if not any(emp['name'] in chunk for chunk in context_chunks):
                                employee_context = self._get_employee_context(emp['id'], analysis)
                                context_chunks.extend(employee_context)
                                employees_added += 1
                                break
                
                # If no specific employee found or need more, do semantic search
                if employees_added < max_employees:
                    search_results = self.vector_store.search_employees(query, n_results=remaining_slots + 5)
                    for result in search_results:
                        if employees_added >= max_employees:
                            break
                        # Skip if already added
                        emp_data = self.employee_db.get_employee(result['employee_id'])
                        if emp_data and not any(emp_data['name'] in chunk for chunk in context_chunks):
                            employee_context = self._get_employee_context(result['employee_id'], analysis)
                            context_chunks.extend(employee_context)
                            employees_added += 1
            
            elif scope in ["multiple_employees", "department", "team_analysis"]:
                # Get broader context - search for relevant employees
                search_results = self.vector_store.search_employees(query, n_results=remaining_slots + 10)
                added_employees = set()
                
                for result in search_results:
                    if employees_added >= max_employees:
                        break
                    
                    emp_data = self.employee_db.get_employee(result['employee_id'])
                    if emp_data and emp_data['name'] not in added_employees:
                        # Limit context per employee for broader analysis
                        employee_context = self._get_employee_context(result['employee_id'], analysis)
                        context_chunks.extend(employee_context[:2])  # Max 2 chunks per employee for broad analysis
                        employees_added += 1
                        added_employees.add(emp_data['name'])
        
        # If no specific context found, do general semantic search
        if not context_chunks or len(context_chunks) < 3:
            general_chunks = self.vector_store.get_relevant_chunks(query, n_results=8)
            context_chunks.extend(general_chunks)
        
        # Intelligent context limiting based on token constraints
        total_context_tokens = sum(self._count_tokens(chunk) for chunk in context_chunks)
        max_context_tokens = self.max_context_tokens - self._get_conversation_token_limit()
        
        if total_context_tokens > max_context_tokens:
            # Prioritize chunks - keep first chunks (usually most relevant)
            cumulative_tokens = 0
            trimmed_chunks = []
            for chunk in context_chunks:
                chunk_tokens = self._count_tokens(chunk)
                if cumulative_tokens + chunk_tokens <= max_context_tokens:
                    trimmed_chunks.append(chunk)
                    cumulative_tokens += chunk_tokens
                else:
                    break
            context_chunks = trimmed_chunks
        
        print(f"DEBUG: Final context - {employees_added} employees, {len(context_chunks)} chunks, ~{total_context_tokens} tokens")
        return context_chunks

    def _get_employee_context(self, employee_id: str, analysis: Dict[str, Any]) -> List[str]:
        """Get specific context for an employee based on what's needed"""
        context = []
        
        # Get employee data
        employee_data = self.employee_db.get_employee(employee_id)
        if not employee_data:
            return context
        
        # Parse profile to get relevant sections
        try:
            if isinstance(employee_data['profile'], str):
                profile_data = json.loads(employee_data['profile'])
            else:
                profile_data = employee_data['profile']
            
            # Check if this is an enhanced profile
            if isinstance(profile_data, dict) and 'traditional_sections' in profile_data:
                # Enhanced profile structure
                required_data = analysis.get("required_data", [])
                
                # Always include traditional sections
                for section in profile_data.get('traditional_sections', []):
                    section_text = f"{employee_data['name']} - {section.get('section', '')}: {section.get('content', '')}"
                    context.append(section_text)
                
                # Add enhanced sections based on requirements
                if "skills_assessment" in required_data and profile_data.get('skills_assessment'):
                    skills_data = profile_data['skills_assessment']
                    context.append(f"{employee_data['name']} - Skills Assessment: {json.dumps(skills_data)}")
                
                if "performance_data" in required_data and profile_data.get('performance_metrics'):
                    perf_data = profile_data['performance_metrics']
                    context.append(f"{employee_data['name']} - Performance Metrics: {json.dumps(perf_data)}")
                    
                if "team_dynamics" in required_data and profile_data.get('team_dynamics'):
                    team_data = profile_data['team_dynamics']
                    context.append(f"{employee_data['name']} - Team Dynamics: {json.dumps(team_data)}")
                    
            else:
                # Traditional profile structure
                for section in profile_data:
                    section_text = f"{employee_data['name']} - {section.get('section', '')}: {section.get('content', '')}"
                    context.append(section_text)
            
            # Add metadata context
            metadata_text = f"{employee_data['name']} - Metadata: {json.dumps(employee_data['metadata'])}"
            context.append(metadata_text)
            
        except Exception as e:
            print(f"Error processing employee context for {employee_id}: {e}")
        
        return context

    def _generate_intelligent_response(self, query: str, context_chunks: List[str], 
                                     analysis: Dict[str, Any], original_query: str) -> str:
        """Generate an intelligent response using the gathered context with token management"""
        
        # Combine context
        context = "\n\n".join(context_chunks)
        
        # Build conversation history context with intelligent token management
        conversation_context = ""
        if self.conversation_history:
            available_tokens = self._get_conversation_token_limit()
            conversation_context = "\n\nCONVERSATION HISTORY:\n"
            
            # Add conversation entries starting from most recent, within token limit
            conversation_tokens = 0
            entries_to_include = []
            
            for entry in reversed(self.conversation_history):
                entry_text = f"Q: {entry['original_query']}\nA: {entry['response'][:300]}...\n\n"
                entry_tokens = self._count_tokens(entry_text)
                
                if conversation_tokens + entry_tokens <= available_tokens:
                    entries_to_include.insert(0, entry)  # Insert at beginning to maintain order
                    conversation_tokens += entry_tokens
                else:
                    break
            
            # Build the conversation context from selected entries
            for i, entry in enumerate(entries_to_include, 1):
                conversation_context += f"Q{i}: {entry['original_query']}\n"
                # Include response summary to save tokens
                prev_response = entry['response'][:200] + "..." if len(entry['response']) > 200 else entry['response']
                conversation_context += f"A{i}: {prev_response}\n\n"
            
            # Add context employees summary if available
            if self.context_employees:
                context_emp_names = [emp["name"] if isinstance(emp, dict) else emp 
                                   for emp in self.context_employees[:5]]
                conversation_context += f"Current context employees: {', '.join(context_emp_names)}\n\n"
        
        # Create specialized prompt based on query type with dynamic analysis depth
        query_type = analysis.get("query_type", "general_guidance")
        analysis_depth = analysis.get("analysis_depth", "detailed_analysis")
        
        if query_type == "succession_planning":
            specialized_prompt = """You are providing succession planning analysis. Focus on:
- Leadership readiness and potential assessments
- Development needs, timelines, and specific action plans
- Risk factors, derailers, and comprehensive mitigation strategies
- Detailed comparison of candidates with specific strengths/weaknesses
- Strategic recommendations with clear rationale and implementation steps
- Consideration of organizational culture and future needs"""
            
        elif query_type == "team_analysis":
            specialized_prompt = """You are analyzing team dynamics and composition. Focus on:
- Complementary strengths, skills, and working style compatibility
- Potential conflict areas, communication gaps, and collaboration challenges
- Team effectiveness patterns and performance optimization
- Role optimization and talent deployment recommendations
- Leadership dynamics and influence patterns within the team
- Specific recommendations for team development and conflict resolution"""
            
        elif query_type == "risk_assessment":
            specialized_prompt = """You are conducting comprehensive talent risk assessment. Focus on:
- Flight risk indicators, retention strategies, and engagement factors
- Performance concerns, improvement plans, and capability gaps
- Leadership derailers, behavioral risks, and mitigation approaches
- Succession vulnerabilities and critical role coverage
- Market competitiveness and external threats to talent retention
- Actionable risk mitigation with timelines and success metrics"""
            
        elif query_type == "cross_comparison":
            specialized_prompt = """You are providing detailed employee comparison analysis. Focus on:
- Side-by-side capability assessment across multiple dimensions
- Strengths and development areas with specific examples
- Cultural fit and values alignment comparison
- Performance trajectory and potential analysis
- Specific recommendations for role assignments or development
- Objective scoring or ranking with clear criteria"""
            
        else:
            specialized_prompt = """You are providing comprehensive talent management insights. Focus on:
- Evidence-based analysis using available assessment and performance data
- Practical recommendations with clear rationale and implementation guidance
- Pattern identification across individuals, teams, or organizational levels
- Strategic implications for talent development and organizational effectiveness
- Data-driven insights that support decision-making"""

        # Enhance prompt based on analysis depth
        if analysis_depth == "strategic_recommendations":
            depth_guidance = "\nProvide strategic-level insights with long-term implications and organizational impact."
        elif analysis_depth == "detailed_analysis":
            depth_guidance = "\nProvide detailed analysis with specific examples and actionable recommendations."
        else:
            depth_guidance = "\nProvide clear, concise insights that directly address the question."

        prompt = f"""{specialized_prompt}{depth_guidance}

IMPORTANT: You are having an ongoing conversation with intelligent context management. Reference previous discussions naturally when relevant.

Employee Data and Assessment Context:
{context}{conversation_context}

CURRENT USER QUESTION: {original_query}
RESOLVED QUESTION (with context): {query}

Analysis Context:
- Query Type: {query_type}
- Scope: {analysis.get("scope", "not specified")}
- Required Data: {", ".join(analysis.get("required_data", ["general"]))}

Response Instructions:
1. Directly address the current question with specific, actionable insights
2. Reference conversation history naturally (e.g., "Building on our previous discussion about...")
3. Cite specific evidence from profiles, assessments, and data (use format: Source - Employee Name)
4. For comparisons, provide structured analysis with clear criteria
5. Identify patterns, trends, or concerning signals in the data
6. Offer practical recommendations with implementation guidance
7. Note any data limitations or areas requiring additional information
8. Maintain professional HR analytics perspective throughout

Ensure your response is comprehensive yet focused, providing value that justifies the conversation context."""

        response = self.client.chat.completions.create(
            model="gpt-4.1-2025-04-14",
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.4,
            max_tokens=2000
        )
        
        return response.choices[0].message.content

    def _extract_employee_names_from_response(self, response: str) -> List[str]:
        """Extract employee names mentioned in a response with intelligent scoring"""
        import re
        employee_names = []
        
        # Get all employee names from database
        all_employees = self.employee_db.get_all_employees()
        
        # Look for employee names mentioned in the response
        for emp in all_employees:
            name = emp['name']
            # Check for full name mentions (highest confidence)
            if name in response:
                if name not in employee_names:
                    employee_names.append(name)
            else:
                # Check for first name or last name mentions (lower confidence)
                parts = name.split()
                for part in parts:
                    if len(part) > 2 and part in response:  # Avoid matching short words
                        # Additional validation - ensure it's not a common word
                        common_words = {'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'her', 'was', 'one', 'our', 'out', 'day', 'get', 'use', 'man', 'new', 'now', 'way', 'may', 'say'}
                        if part.lower() not in common_words:
                            if name not in employee_names:
                                employee_names.append(name)
                                break
        
        # Limit to reasonable number and prioritize by frequency of mention
        name_counts = {}
        for name in employee_names:
            name_counts[name] = response.count(name) + response.count(name.split()[0])
        
        # Sort by mention frequency and limit
        sorted_names = sorted(employee_names, key=lambda x: name_counts.get(x, 0), reverse=True)
        return sorted_names[:8]  # Increased from 5 to 8 for better context tracking

    def get_conversation_insights(self) -> Dict[str, Any]:
        """Get insights about the current conversation for UI display"""
        if not self.conversation_history:
            return {"status": "no_conversation"}
        
        # Analyze conversation patterns
        query_types = [entry.get("query_type", "general") for entry in self.conversation_history]
        most_common_type = max(set(query_types), key=query_types.count) if query_types else "general"
        
        # Get employee focus
        all_mentioned_employees = []
        for entry in self.conversation_history:
            all_mentioned_employees.extend(entry.get("context_employees", []))
        
        employee_frequency = {}
        for emp in all_mentioned_employees:
            employee_frequency[emp] = employee_frequency.get(emp, 0) + 1
        
        top_employees = sorted(employee_frequency.items(), key=lambda x: x[1], reverse=True)[:5]
        
        memory_status = self._get_memory_status()
        
        return {
            "conversation_length": len(self.conversation_history),
            "conversation_theme": most_common_type,
            "top_employees": top_employees,
            "memory_usage": memory_status["usage_percentage"],
            "current_context_employees": len(self.context_employees),
            "total_tokens_used": self.conversation_metadata["total_tokens_used"],
            "settings_summary": {
                "memory_mode": self.conversation_settings["max_conversation_memory"],
                "focus_mode": self.conversation_settings["employee_focus_mode"],
                "context_tracking": self.conversation_settings["enable_context_tracking"]
            }
        }

# Initialize the system (will be imported by app.py)
rag_system = RAGQuerySystem() 