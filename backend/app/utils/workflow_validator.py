"""
Workflow Validation Utilities
Validates workflow structure, node connections, and configuration
"""
from typing import List, Dict, Any
from fastapi import HTTPException


COMPATIBLE_API_RESPONSE_SOURCES = {
    "detection",
    "batch_detection",
    "video_detection",
    "export",
    "conditional",
    "input"  # In case input node passes data directly
}


def validate_api_response_node(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> None:
    """
    Validate API Response node configuration.
    
    Rules:
    1. Maximum one API Response node per workflow
    2. API Response node must have at least one incoming edge
    3. API Response can only receive connections from compatible node types
    
    Args:
        nodes: List of workflow nodes
        edges: List of workflow edges
    
    Raises:
        HTTPException: If validation fails
    """
    # Find all API Response nodes
    api_response_nodes = [n for n in nodes if n.get('type') == 'api_response']
    
    # Rule 1: Max one API Response node
    if len(api_response_nodes) > 1:
        raise HTTPException(
            status_code=400,
            detail="Workflow can only have ONE API Response node. Please remove extra API Response nodes."
        )
    
    if not api_response_nodes:
        return  # No API Response node, skip validation
    
    api_node = api_response_nodes[0]
    api_node_id = api_node.get('id')
    
    # Rule 2: Must have at least one incoming edge
    incoming_edges = [e for e in edges if e.get('target') == api_node_id]
    
    if not incoming_edges:
        raise HTTPException(
            status_code=400,
            detail=(
                "API Response node must be connected to at least one node. "
                "Connect detection or operation nodes to include their outputs in the API response."
            )
        )
    
    # Rule 3: Can only connect from compatible node types
    node_type_map = {n.get('id'): n.get('type') for n in nodes}
    
    for edge in incoming_edges:
        source_node_id = edge.get('source')
        source_node_type = node_type_map.get(source_node_id)
        
        if source_node_type not in COMPATIBLE_API_RESPONSE_SOURCES:
            raise HTTPException(
                status_code=400,
                detail=(
                    f"Cannot connect '{source_node_type}' node to API Response. "
                    f"Only detection, export, and operation nodes can connect to API Response. "
                    f"Allowed types: {', '.join(sorted(COMPATIBLE_API_RESPONSE_SOURCES))}"
                )
            )


def validate_api_trigger_node(nodes: List[Dict[str, Any]]) -> None:
    """
    Validate API Trigger node configuration.
    
    Rules:
    1. If workflow has API trigger, it should have fields defined
    2. Field names must be unique
    3. Field types must be valid
    
    Args:
        nodes: List of workflow nodes
    
    Raises:
        HTTPException: If validation fails
    """
    api_trigger_nodes = [n for n in nodes if n.get('type') == 'trigger_api']
    
    if not api_trigger_nodes:
        return
    
    for node in api_trigger_nodes:
        fields = node.get('data', {}).get('fields', [])
        
        # Check field uniqueness
        field_names = [f.get('name') for f in fields]
        if len(field_names) != len(set(field_names)):
            raise HTTPException(
                status_code=400,
                detail="API Trigger node has duplicate field names. Each field must have a unique name."
            )
        
        # Validate field types
        valid_types = ['string', 'number', 'boolean', 'array', 'object']
        for field in fields:
            if field.get('type') not in valid_types:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid field type '{field.get('type')}'. Allowed types: {', '.join(valid_types)}"
                )


def validate_workflow_structure(nodes: List[Dict[str, Any]], edges: List[Dict[str, Any]]) -> None:
    """
    Validate overall workflow structure.
    
    Args:
        nodes: List of workflow nodes
        edges: List of workflow edges
    
    Raises:
        HTTPException: If validation fails
    """
    # Validate API trigger
    validate_api_trigger_node(nodes)
    
    # Validate API response
    validate_api_response_node(nodes, edges)
    
    # Can add more validations here:
    # - Check for circular dependencies
    # - Validate trigger node exists
    # - Check required node configurations
