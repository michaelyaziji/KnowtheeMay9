import os
from openai import OpenAI
import re
from typing import Dict, Any, List, Tuple
import json

class QueryProcessor:
    def __init__(self):
        """Initialize the query processor with OpenAI client."""
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ValueError("OPENAI_API_KEY environment variable is not set.")
        self.client = OpenAI(api_key=api_key)
        
        # Define system prompt for parsing queries
        self.system_prompt = """You are an expert system designed to parse natural language queries about employees.
Your task is to extract structured information from the user's query to help search a database of employee profiles.
Follow these guidelines:
1. Identify key attributes mentioned in the query (traits, skills, roles, etc.)
2. Determine if the query is looking for specific traits like "extroverted", "creative", etc.
3. Extract any role/position requirements like "engineer", "manager", etc.
4. Identify any other search filters like department, experience level, etc.
5. Format the output as JSON with clear attribute-value pairs

Example queries and expected outputs:
Query: "Find creative engineers with leadership experience"
Output: {
  "traits": ["creative", "leadership"],
  "roles": ["engineer"],
  "explanation": "Looking for engineers who are creative and have leadership experience"
}

Query: "Show me extroverted people who are good at communication"
Output: {
  "traits": ["extroverted", "communicative"],
  "explanation": "Searching for extroverted employees with good communication skills"
}

Query: "Who are the most analytical team members on the marketing team?"
Output: {
  "traits": ["analytical"],
  "departments": ["marketing"],
  "explanation": "Looking for analytical people in the marketing department"
}
"""
    
    def parse_query(self, query: str) -> Dict[str, Any]:
        """
        Parse a natural language query into structured search parameters.
        
        Args:
            query: Natural language query from the user
            
        Returns:
            Dictionary of extracted search parameters
        """
        prompt = f"Parse the following query about employees and extract structured search parameters:\n\n{query}"
        
        response = self.client.chat.completions.create(
            model="gpt-4.1-2025-04-14",
            messages=[
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": prompt}
            ],
            temperature=0.2,
            max_tokens=500
        )
        
        parsed_text = response.choices[0].message.content
        
        # Extract JSON from the response
        try:
            # Look for JSON pattern in the response
            json_match = re.search(r'({[\s\S]*})', parsed_text)
            if json_match:
                parsed_json = json.loads(json_match.group(1))
                return parsed_json
            else:
                # If no JSON format is found, return empty dict with error
                return {
                    "error": "Failed to parse query into structured format",
                    "raw_query": query
                }
        except Exception as e:
            return {
                "error": f"Error parsing query: {str(e)}",
                "raw_query": query
            }
    
    def convert_to_filters(self, parsed_query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Convert parsed query parameters to vector store filters.
        
        Args:
            parsed_query: Dictionary of parsed query parameters
            
        Returns:
            Filters dictionary for vector store query
        """
        filters = {}
        
        # Process traits
        if "traits" in parsed_query and parsed_query["traits"]:
            traits = parsed_query["traits"]
            # For simplicity, just use the first trait as a filter
            # Our custom filtering in vector_store will handle multiple traits
            if traits:
                trait_filter = f".*{traits[0]}.*"
                filters["traits"] = {"$regex": trait_filter}
        
        # Process roles
        if "roles" in parsed_query and parsed_query["roles"]:
            roles = parsed_query["roles"]
            # For simplicity, just use the first role as a filter
            # Our custom filtering in vector_store will handle multiple roles
            if roles:
                role_filter = f".*{roles[0]}.*"
                filters["roles"] = {"$regex": role_filter}
        
        # Process departments
        if "departments" in parsed_query and parsed_query["departments"]:
            departments = parsed_query["departments"]
            if len(departments) > 0:
                filters["department"] = departments[0]
        
        return filters
    
    def generate_explanation(self, results: List[Dict[str, Any]], 
                            original_query: str, 
                            parsed_query: Dict[str, Any]) -> str:
        """
        Generate a natural language explanation of the search results.
        
        Args:
            results: List of search results
            original_query: The original user query
            parsed_query: The parsed query parameters
            
        Returns:
            Natural language explanation
        """
        # Prepare context for the explanation
        result_count = len(results)
        
        # Extract result information
        result_names = [r["metadata"].get("name", "Unknown") for r in results[:5]]
        names_text = ", ".join(result_names) if result_names else "no employees"
        
        # Explanation of query parsing
        traits = parsed_query.get("traits", [])
        traits_text = ", ".join(traits) if traits else "no specific traits"
        
        roles = parsed_query.get("roles", [])
        roles_text = ", ".join(roles) if roles else "no specific roles"
        
        context = f"""Original query: "{original_query}"
The search found {result_count} employee(s).
Top matches: {names_text}
Traits identified in query: {traits_text}
Roles identified in query: {roles_text}

Generate a brief, natural-sounding explanation of the search results that addresses the original query.
Keep it concise (1-2 sentences). Don't list all employees by name unless there are 3 or fewer results.
"""
        
        prompt = f"Generate a concise explanation of these employee search results:\n\n{context}"
        
        response = self.client.chat.completions.create(
            model="gpt-4.1-2025-04-14",
            messages=[
                {"role": "system", "content": "You generate brief, natural language explanations of employee search results. Keep responses under 50 words."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.7,
            max_tokens=200
        )
        
        return response.choices[0].message.content
    
    def process_search_results(self, results: List[Dict[str, Any]], 
                              original_query: str, 
                              parsed_query: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process and format search results with explanations.
        
        Args:
            results: Raw search results from vector store
            original_query: Original natural language query
            parsed_query: Parsed query parameters
            
        Returns:
            Processed search results with explanation
        """
        # Generate explanation of results
        explanation = self.generate_explanation(results, original_query, parsed_query)
        
        # Format the results
        formatted_results = {
            "original_query": original_query,
            "parsed_query": parsed_query,
            "explanation": explanation,
            "count": len(results),
            "employees": []
        }
        
        # Format each employee result
        for result in results:
            employee_data = {
                "id": result["employee_id"],
                "name": result["metadata"].get("name", "Unknown"),
                "traits": result["metadata"].get("traits", "").split(", ") if "traits" in result["metadata"] else [],
                "match_count": result["match_count"]
            }
            formatted_results["employees"].append(employee_data)
        
        return formatted_results 