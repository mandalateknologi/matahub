"""
API Response Executor
Handles API response workflow nodes.
"""
import logging
from typing import Dict, Any

from app.services.executors.base import NodeExecutorBase

logger = logging.getLogger(__name__)


class ApiResponseExecutor(NodeExecutorBase):
    """API Response Node Executor - collects outputs from connected nodes."""
    
    def __init__(self):
        super().__init__("api_response")
    
    def execute(
        self,
        node_id: str,
        config: Dict[str, Any],
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Collect outputs from connected nodes and build API response."""
        logger.info(f"Executing API Response node {node_id}")
        
        try:
            dependency_outputs = context.get('_dependency_outputs', {})
            
            if not dependency_outputs:
                return {
                    "status": "success",
                    "message": "No data sources connected to API Response node",
                    "results": []
                }
            
            response_mode = config.get('response_mode', 'array')
            image_output = config.get('image_output', {})
            max_images = image_output.get('max_images', 100)
            error_handling = config.get('error_handling', 'fail_on_any')
            
            results = []
            errors = []
            
            for source_node_id, output_data in dependency_outputs.items():
                if output_data.get('status') == 'failed':
                    error_msg = output_data.get('error', 'Unknown error')
                    errors.append({"source_node": source_node_id, "error": error_msg})
                    
                    if error_handling == 'fail_on_any':
                        raise Exception(f"Connected node {source_node_id} failed: {error_msg}")
                    elif error_handling == 'partial_results':
                        results.append({"source_node": source_node_id, "status": "failed", "error": error_msg})
                    continue
                
                node_result = {"source_node": source_node_id, "status": "success"}
                
                if 'results' in output_data:
                    predictions = output_data['results']
                    if isinstance(predictions, list) and max_images:
                        predictions = predictions[:max_images]
                    node_result['predictions'] = predictions
                    node_result['prediction_count'] = len(predictions) if isinstance(predictions, list) else 1
                
                if 'summary' in output_data:
                    node_result['summary'] = output_data['summary']
                
                if 'model_name' in output_data:
                    node_result['model'] = output_data['model_name']
                elif 'model_id' in output_data:
                    node_result['model_id'] = output_data['model_id']
                
                if 'image_urls' in output_data:
                    image_urls = output_data['image_urls']
                    if isinstance(image_urls, list) and max_images:
                        image_urls = image_urls[:max_images]
                    node_result['image_urls'] = image_urls
                
                if 'campaign_id' in output_data:
                    node_result['campaign_id'] = output_data['campaign_id']
                    if 'campaign_name' in output_data:
                        node_result['campaign_name'] = output_data['campaign_name']
                
                for key in ['confidence_avg', 'classes_detected', 'image_count']:
                    if key in output_data:
                        node_result[key] = output_data[key]
                
                results.append(node_result)
            
            if response_mode == 'array':
                response_data = {
                    "status": "success" if not errors else "partial_success",
                    "results": results,
                    "summary": {
                        "total_sources": len(dependency_outputs),
                        "successful_sources": len(results),
                        "failed_sources": len(errors)
                    }
                }
                if errors:
                    response_data["errors"] = errors
            
            elif response_mode == 'merged':
                all_predictions = []
                all_images = []
                
                for result in results:
                    if 'predictions' in result:
                        if isinstance(result['predictions'], list):
                            all_predictions.extend(result['predictions'])
                        else:
                            all_predictions.append(result['predictions'])
                    if 'image_urls' in result:
                        all_images.extend(result['image_urls'])
                
                response_data = {
                    "status": "success" if not errors else "partial_success",
                    "predictions": all_predictions,
                    "images": all_images,
                    "summary": {
                        "total_predictions": len(all_predictions),
                        "total_images": len(all_images)
                    }
                }
                if errors:
                    response_data["errors"] = errors
            
            else:
                response_data = {"status": "success", "results": results}
            
            logger.info(f"API Response node {node_id} completed with {len(results)} results")
            return response_data
            
        except Exception as e:
            logger.error(f"API Response node {node_id} failed: {str(e)}")
            raise
