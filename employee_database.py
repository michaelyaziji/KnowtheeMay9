import os
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
import uuid

class EmployeeDatabase:
    def __init__(self, storage_dir="employee_data"):
        """Initialize employee database with storage directory."""
        self.storage_dir = storage_dir
        os.makedirs(storage_dir, exist_ok=True)
        self.index_file = os.path.join(storage_dir, "index.json")
        self.profile_index = self._load_index()
    
    def _load_index(self) -> Dict[str, Dict[str, Any]]:
        """Load the employee index or create a new one if it doesn't exist."""
        if os.path.exists(self.index_file):
            with open(self.index_file, 'r') as f:
                return json.load(f)
        else:
            # Create empty index
            return {}
    
    def _save_index(self):
        """Save the employee index to disk."""
        with open(self.index_file, 'w') as f:
            json.dump(self.profile_index, f, indent=2)
    
    def add_employee(self, name: str, profile_data: str, 
                    metadata: Dict[str, Any] = None) -> str:
        """
        Add a new employee profile to the database.
        
        Args:
            name: Employee name
            profile_data: The JSON string containing the profile
            metadata: Additional structured data about the employee
            
        Returns:
            employee_id: Unique ID for the employee
        """
        # Generate a unique ID for the employee
        employee_id = str(uuid.uuid4())
        
        # Extract traits and attributes from the profile data
        extracted_metadata = self._extract_metadata_from_profile(profile_data)
        
        # Merge with provided metadata
        if metadata:
            extracted_metadata.update(metadata)
        
        # Add name to metadata
        extracted_metadata['name'] = name
        extracted_metadata['added_date'] = datetime.now().isoformat()
        
        # Track document names if provided in metadata
        if metadata and 'document_names' in metadata:
            extracted_metadata['document_names'] = metadata['document_names']
        
        # Save the profile to a file
        profile_path = os.path.join(self.storage_dir, f"{employee_id}.json")
        with open(profile_path, 'w') as f:
            f.write(profile_data)
        
        # Add to index
        self.profile_index[employee_id] = {
            'name': name,
            'file_path': profile_path,
            'metadata': extracted_metadata,
            'added_date': extracted_metadata['added_date']
        }
        
        # Save updated index
        self._save_index()
        
        return employee_id
    
    def get_employee(self, employee_id: str) -> Optional[Dict[str, Any]]:
        """Retrieve an employee profile by ID."""
        if employee_id not in self.profile_index:
            return None
        
        # Get profile data
        profile_path = self.profile_index[employee_id]['file_path']
        with open(profile_path, 'r') as f:
            profile_data = f.read()
        
        # Return employee data with profile
        return {
            'id': employee_id,
            'name': self.profile_index[employee_id]['name'],
            'profile': profile_data,
            'metadata': self.profile_index[employee_id]['metadata']
        }
    
    def get_all_employees(self) -> List[Dict[str, Any]]:
        """Get a list of all employees with basic info (no profile content)."""
        return [
            {
                'id': emp_id,
                'name': data['name'],
                'metadata': data['metadata'],
                'added_date': data['added_date']
            }
            for emp_id, data in self.profile_index.items()
        ]
    
    def delete_employee(self, employee_id: str) -> bool:
        """Delete an employee profile."""
        if employee_id not in self.profile_index:
            return False
        
        # Remove the profile file
        profile_path = self.profile_index[employee_id]['file_path']
        if os.path.exists(profile_path):
            os.remove(profile_path)
        
        # Remove from index
        del self.profile_index[employee_id]
        self._save_index()
        
        return True
    
    def update_employee_profile(self, employee_id: str, profile_data: str) -> bool:
        """
        Update an existing employee's profile data.
        
        Args:
            employee_id: Unique ID for the employee
            profile_data: The new JSON string containing the updated profile
            
        Returns:
            bool: True if successful, False if employee not found
        """
        if employee_id not in self.profile_index:
            return False
        
        # Extract new metadata from the updated profile
        extracted_metadata = self._extract_metadata_from_profile(profile_data)
        
        # Preserve certain existing metadata (like name, added_date, document_names)
        existing_metadata = self.profile_index[employee_id]['metadata']
        
        # Merge metadata, keeping existing important fields
        updated_metadata = {
            **extracted_metadata,
            'name': existing_metadata.get('name'),
            'added_date': existing_metadata.get('added_date'),
            'last_updated': datetime.now().isoformat()
        }
        
        # Preserve document names if they exist
        if 'document_names' in existing_metadata:
            updated_metadata['document_names'] = existing_metadata['document_names']
        
        # Preserve department if it exists
        if 'department' in existing_metadata:
            updated_metadata['department'] = existing_metadata['department']
        
        # Save the updated profile to file
        profile_path = self.profile_index[employee_id]['file_path']
        with open(profile_path, 'w') as f:
            f.write(profile_data)
        
        # Update the index
        self.profile_index[employee_id]['metadata'] = updated_metadata
        
        # Save updated index
        self._save_index()
        
        return True
    
    def _extract_metadata_from_profile(self, profile_json: str) -> Dict[str, Any]:
        """
        Extract searchable attributes from profile JSON.
        This converts unstructured profile data into structured metadata.
        """
        metadata = {
            'traits': [],
            'strengths': [],
            'roles': [],
            'leadership_style': []
        }
        
        try:
            # Parse the profile JSON
            profile_data = json.loads(profile_json)
            
            # Process each section to extract relevant metadata
            for section in profile_data:
                section_name = section.get('section', '')
                content = section.get('content', '')
                
                # Extract traits from Profile Summary
                if section_name == 'Profile Summary':
                    # Look for traits mentioned in parentheses
                    traits = self._extract_traits(content)
                    metadata['traits'].extend(traits)
                
                # Extract strengths
                elif section_name == 'Key Strengths':
                    strengths = self._extract_list_items(content)
                    metadata['strengths'].extend(strengths)
                
                # Extract leadership style keywords
                elif section_name == 'Leadership Style':
                    style_keywords = self._extract_leadership_style(content)
                    metadata['leadership_style'].extend(style_keywords)
                
                # Extract roles that would fit
                elif section_name == 'Roles That Would Fit':
                    roles = self._extract_list_items(content)
                    metadata['roles'].extend(roles)
            
            # Remove duplicates
            for key in metadata:
                metadata[key] = list(set(metadata[key]))
            
        except Exception as e:
            print(f"Error extracting metadata: {e}")
        
        return metadata
    
    def _extract_traits(self, text: str) -> List[str]:
        """Extract personality traits from profile text."""
        common_traits = [
            "analytical", "creative", "detail-oriented", "strategic", 
            "collaborative", "independent", "extroverted", "introverted",
            "adaptable", "resilient", "innovative", "methodical",
            "persuasive", "communicative", "technical", "visionary"
        ]
        
        found_traits = []
        for trait in common_traits:
            if trait in text.lower():
                found_traits.append(trait)
        
        return found_traits
    
    def _extract_list_items(self, text: str) -> List[str]:
        """Extract numbered list items from text."""
        items = []
        # Split by numbered items (1., 2., etc.)
        import re
        list_items = re.split(r'\d+\.', text)
        
        # Skip the first item if it's empty (before the first number)
        if list_items and not list_items[0].strip():
            list_items = list_items[1:]
        
        for item in list_items:
            # Remove citations and clean up
            clean_item = re.sub(r'\([^)]*\)', '', item)
            clean_item = clean_item.strip()
            if clean_item:
                items.append(clean_item)
        
        return items
    
    def _extract_leadership_style(self, text: str) -> List[str]:
        """Extract leadership style keywords."""
        leadership_styles = [
            "directive", "participative", "transformational", "transactional",
            "servant", "democratic", "authoritative", "coaching", "delegative",
            "visionary", "pacesetting", "affiliative", "commanding"
        ]
        
        found_styles = []
        for style in leadership_styles:
            if style in text.lower():
                found_styles.append(style)
        
        return found_styles 