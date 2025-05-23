import chromadb
from chromadb.config import Settings
import os
from typing import List, Dict, Any, Optional
import json

class VectorStore:
    def __init__(self):
        # Initialize ChromaDB with local persistence
        self.client = chromadb.Client(Settings(
            persist_directory="chroma_db",
            anonymized_telemetry=False
        ))
        
        # Create or get collections
        self.single_profile_collection = self.client.get_or_create_collection(
            name="leadership_documents",
            metadata={"hnsw:space": "cosine"}
        )
        
        # Collection for employee profiles (processed sections)
        self.employee_profiles_collection = self.client.get_or_create_collection(
            name="employee_profiles",
            metadata={"hnsw:space": "cosine"}
        )
        
        # Collection for employee raw documents (for detailed citations)
        self.employee_documents_collection = self.client.get_or_create_collection(
            name="employee_documents",
            metadata={"hnsw:space": "cosine"}
        )
    
    def store_documents(self, documents: List[str], metadata_list: List[dict] = None):
        """Store documents in the single profile vector database."""
        # Get all current IDs
        existing = self.single_profile_collection.get()
        if existing and 'ids' in existing and existing['ids']:
            self.single_profile_collection.delete(ids=existing['ids'])
        # Add new documents
        ids = [str(i) for i in range(len(documents))]
        
        # Add metadata if provided
        if metadata_list:
            self.single_profile_collection.add(
                documents=documents,
                metadatas=metadata_list,
                ids=ids
            )
        else:
            self.single_profile_collection.add(
                documents=documents,
                ids=ids
            )
    
    def get_relevant_chunks(self, query: str = None, n_results: int = 5, employee_id: str = None) -> List[str]:
        """
        Retrieve relevant document chunks based on a query.
        
        Args:
            query: The search query
            n_results: Maximum number of results to return
            employee_id: Optional employee ID to filter results
            
        Returns:
            List of relevant document chunks
        """
        if employee_id:
            # If employee_id is provided, first try to search in raw documents collection
            # for more detailed citations
            try:
                # Check if we have raw documents for this employee
                raw_docs = self.employee_documents_collection.get(
                    where={"employee_id": employee_id}
                )
                
                if raw_docs['documents'] and len(raw_docs['documents']) > 0:
                    if query is None:
                        # If no query, return all raw documents for this employee
                        return raw_docs['documents']
                    
                    # Search for relevant chunks within this employee's raw documents
                    results = self.employee_documents_collection.query(
                        query_texts=[query],
                        where={"employee_id": employee_id},
                        n_results=n_results
                    )
                    
                    if results['documents'] and len(results['documents'][0]) > 0:
                        return results['documents'][0]
                
                # If no raw documents found or no results from raw documents,
                # fall back to the processed profile sections
                employee_docs = self.employee_profiles_collection.get(
                    where={"employee_id": employee_id}
                )
                
                if not employee_docs['documents']:
                    return []
                
                if query is None:
                    # If no query, return all documents for this employee
                    return employee_docs['documents']
                
                # Search for relevant chunks within this employee's profile sections
                results = self.employee_profiles_collection.query(
                    query_texts=[query],
                    where={"employee_id": employee_id},
                    n_results=n_results
                )
                
                if results['documents'] and len(results['documents'][0]) > 0:
                    return results['documents'][0]
                return []
                
            except Exception as e:
                print(f"Error retrieving employee chunks: {str(e)}")
                return []
        else:
            # Original behavior for single profile
            if query is None:
                # If no query provided, return all documents
                results = self.single_profile_collection.get()
                return results['documents']
            
            # Search for relevant chunks
            results = self.single_profile_collection.query(
                query_texts=[query],
                n_results=n_results
            )
            return results['documents'][0]
    
    def clear(self):
        """Clear all documents from the single profile vector store."""
        self.single_profile_collection.delete(where={"id": {"$ne": None}})
    
    # New methods for employee database functionality
    
    def store_employee_profile(self, employee_id: str, profile_sections: List[Dict[str, Any]], 
                              metadata: Dict[str, Any] = None):
        """
        Store an employee's profile sections as separate chunks with metadata.
        
        Args:
            employee_id: Unique identifier for the employee
            profile_sections: List of profile section dictionaries
            metadata: Additional metadata about the employee
        """
        # Delete any existing entries for this employee
        self.employee_profiles_collection.delete(where={"employee_id": employee_id})
        
        # Store each section as a separate chunk
        documents = []
        metadatas = []
        ids = []
        
        for i, section in enumerate(profile_sections):
            # Convert section to JSON string if it's not already
            if isinstance(section, dict):
                section_text = json.dumps(section)
            else:
                section_text = section
                
            # Create a document from the section
            documents.append(section_text)
            
            # Create metadata for this section
            section_metadata = {
                "employee_id": employee_id,
                "section_id": i
            }
            
            # Add employee metadata if provided
            if metadata:
                for key, value in metadata.items():
                    # Handle list values by concatenating them
                    if isinstance(value, list):
                        section_metadata[key] = ", ".join(str(item) for item in value)
                    else:
                        section_metadata[key] = value
            
            metadatas.append(section_metadata)
            ids.append(f"{employee_id}_{i}")
        
        # Add to collection
        self.employee_profiles_collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
    
    def store_employee_documents(self, employee_id: str, documents: List[str], metadata: Dict[str, Any] = None):
        """
        Store an employee's raw document chunks for detailed citations.
        
        Args:
            employee_id: Unique identifier for the employee
            documents: List of raw document chunks
            metadata: Additional metadata about the employee
        """
        # Delete any existing document entries for this employee
        self.employee_documents_collection.delete(where={"employee_id": employee_id})
        
        if not documents:
            return
            
        # Prepare metadata and IDs for each document chunk
        metadatas = []
        ids = []
        
        for i, doc in enumerate(documents):
            # Create metadata for this document
            doc_metadata = {
                "employee_id": employee_id,
                "chunk_id": i
            }
            
            # Add employee metadata if provided
            if metadata:
                for key, value in metadata.items():
                    # Handle list values by concatenating them
                    if isinstance(value, list):
                        doc_metadata[key] = ", ".join(str(item) for item in value)
                    else:
                        doc_metadata[key] = value
            
            metadatas.append(doc_metadata)
            ids.append(f"{employee_id}_doc_{i}")
        
        # Add to collection
        self.employee_documents_collection.add(
            documents=documents,
            metadatas=metadatas,
            ids=ids
        )
    
    def delete_employee_profile(self, employee_id: str):
        """Delete all vector entries for an employee."""
        # Delete from profiles collection
        self.employee_profiles_collection.delete(
            where={"employee_id": employee_id}
        )
        
        # Also delete from raw documents collection
        self.employee_documents_collection.delete(
            where={"employee_id": employee_id}
        )
    
    def batch_store_employee_profiles(self, employee_data_list: List[Dict[str, Any]]):
        """
        Store multiple employee profiles in batch for much better performance.
        
        Args:
            employee_data_list: List of dictionaries containing employee data
                Each dict should have: id, profile, metadata
        """
        if not employee_data_list:
            return
            
        # Prepare batch data
        all_documents = []
        all_metadatas = []
        all_ids = []
        
        # Process all employees in a single pass
        for idx, employee_data in enumerate(employee_data_list):
            employee_id = employee_data.get('id')
            if not employee_id:
                continue
                
            try:
                # Parse profile data
                profile_data = json.loads(employee_data.get('profile', '[]'))
                metadata = employee_data.get('metadata', {})
                
                # Process each profile section
                for section_idx, section in enumerate(profile_data):
                    # Convert section to JSON string if it's not already
                    if isinstance(section, dict):
                        section_text = json.dumps(section)
                    else:
                        section_text = section
                        
                    # Create metadata for this section
                    section_metadata = {
                        "employee_id": employee_id,
                        "section_id": section_idx
                    }
                    
                    # Add employee metadata if provided
                    if metadata:
                        for key, value in metadata.items():
                            # Handle list values by concatenating them
                            if isinstance(value, list):
                                section_metadata[key] = ", ".join(str(item) for item in value)
                            else:
                                section_metadata[key] = value
                    
                    # Add to batch
                    all_documents.append(section_text)
                    all_metadatas.append(section_metadata)
                    all_ids.append(f"{employee_id}_{section_idx}")
            except Exception as e:
                print(f"Error processing employee {employee_id}: {str(e)}")
                continue
        
        # Delete existing entries first
        employee_ids = [data.get('id') for data in employee_data_list if data.get('id')]
        for employee_id in employee_ids:
            self.employee_profiles_collection.delete(where={"employee_id": employee_id})
        
        # Perform batch insertion (much faster than individual inserts)
        if all_documents:
            self.employee_profiles_collection.add(
                documents=all_documents,
                metadatas=all_metadatas,
                ids=all_ids
            )
    
    def search_employees(self, query: str, filters: Dict[str, Any] = None, 
                         n_results: int = 10) -> List[Dict[str, Any]]:
        """
        Search for employees based on a natural language query and optional filters.
        
        Args:
            query: Natural language query
            filters: Dictionary of metadata filters
            n_results: Maximum number of results to return
            
        Returns:
            List of results with employee_id and matched text
        """
        print(f"DEBUG: Searching with query: '{query}', filters: {filters}")
        
        try:
            # Check if employee collection exists and has data
            collection_info = self.employee_profiles_collection.get()
            print(f"DEBUG: Collection info - count: {len(collection_info.get('ids', []))}")
            
            # Execute search without filters first to get semantic matches
            results = self.employee_profiles_collection.query(
                query_texts=[query],
                n_results=n_results * 2  # Get more results initially to filter later
            )
            
            print(f"DEBUG: Initial search results - docs found: {len(results.get('documents', [[]])[0])}")
            
            # If we have filters, apply them manually to the results
            if filters and results['documents'] and len(results['documents'][0]) > 0:
                print(f"DEBUG: Applying filters: {filters}")
                # Filter the results based on the metadata
                filtered_docs = []
                filtered_metadata = []
                filtered_ids = []
                filtered_distances = []
                
                for i, doc in enumerate(results['documents'][0]):
                    metadata = results['metadatas'][0][i]
                    doc_id = results['ids'][0][i]
                    distance = results['distances'][0][i] if 'distances' in results else 0
                    
                    print(f"DEBUG: Checking result {i}, metadata: {metadata}")
                    
                    # Check if this result matches all filters
                    matches_all_filters = True
                    
                    for key, value in filters.items():
                        # Handle regex pattern filters
                        if isinstance(value, dict) and '$regex' in value:
                            pattern = value['$regex'].replace('.*', '')  # Extract the core pattern
                            metadata_value = str(metadata.get(key, ''))
                            print(f"DEBUG: Regex check - key: {key}, pattern: {pattern}, value: {metadata_value}")
                            if pattern.lower() not in metadata_value.lower():
                                matches_all_filters = False
                                print(f"DEBUG: Failed regex match for {key}")
                                break
                        # Handle exact match filters
                        elif str(metadata.get(key, '')) != str(value):
                            matches_all_filters = False
                            print(f"DEBUG: Failed exact match for {key}")
                            break
                    
                    if matches_all_filters:
                        print(f"DEBUG: Result {i} matches all filters")
                        filtered_docs.append(doc)
                        filtered_metadata.append(metadata)
                        filtered_ids.append(doc_id)
                        if 'distances' in results:
                            filtered_distances.append(distance)
                
                # Replace results with filtered results
                filtered_results = {
                    'documents': [filtered_docs],
                    'metadatas': [filtered_metadata],
                    'ids': [filtered_ids],
                }
                if 'distances' in results:
                    filtered_results['distances'] = [filtered_distances]
                
                results = filtered_results
                print(f"DEBUG: After filtering - docs found: {len(results.get('documents', [[]])[0])}")
            
            # Process results to group by employee
            employee_results = {}
            
            if results['documents'] and len(results['documents'][0]) > 0:
                for i, doc in enumerate(results['documents'][0]):
                    metadata = results['metadatas'][0][i]
                    employee_id = metadata.get('employee_id')
                    
                    if employee_id not in employee_results:
                        employee_results[employee_id] = {
                            'employee_id': employee_id,
                            'match_count': 0,
                            'matches': [],
                            'metadata': metadata
                        }
                    
                    # Add this match
                    employee_results[employee_id]['matches'].append(doc)
                    employee_results[employee_id]['match_count'] += 1
            
            # Convert to list and sort by match count
            result_list = list(employee_results.values())
            result_list.sort(key=lambda x: x['match_count'], reverse=True)
            
            print(f"DEBUG: Final result count: {len(result_list)}")
            return result_list
            
        except Exception as e:
            print(f"DEBUG: Error in search_employees: {str(e)}")
            import traceback
            traceback.print_exc()
            return [] 