"""
Data Input Executor
Handles data input workflow nodes.
"""
import logging
from typing import Dict, Any
from pathlib import Path

from app.services.executors.base import NodeExecutorBase
from app.services.executors.utils import resolve_fm_path_to_absolute
from app.config import settings

logger = logging.getLogger(__name__)


class InputExecutor(NodeExecutorBase):
    """Executor for input nodes."""
    
    def __init__(self):
        super().__init__("data_input")
    
    def execute(
        self, 
        node_id: str,
        config: Dict[str, Any], 
        context: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Prepare input sources for prediction."""
        validated = self.validate_config(config)
        
        try:
            sources = []
            actual_context = context.get('_context', context)
            creator_id = actual_context.get('creator_id')
            
            if not creator_id:
                raise ValueError("creator_id not found in workflow context")
            
            if validated.mode.value == "single":
                if validated.file_paths and len(validated.file_paths) > 0:
                    file_path = validated.file_paths[0]
                    resolved_path = resolve_fm_path_to_absolute(file_path, creator_id)
                    sources.append(str(resolved_path))
                else:
                    file_path = context.get('trigger_data', {}).get('file_path')
                    if file_path:
                        resolved_path = resolve_fm_path_to_absolute(file_path, creator_id)
                        sources.append(str(resolved_path))
            
            elif validated.mode.value == "batch":
                for file_path in (validated.file_paths or []):
                    resolved_path = resolve_fm_path_to_absolute(file_path, creator_id)
                    sources.append(str(resolved_path))
            
            elif validated.mode.value in ["folder_images", "folder_videos"]:
                folder = resolve_fm_path_to_absolute(validated.folder_path, creator_id)
                
                if not folder.exists():
                    raise ValueError(f"Folder not found: {validated.folder_path}")
                
                # Validate folder location
                try:
                    relative_to_user = folder.relative_to(Path(settings.uploads_dir) / str(creator_id))
                    if not (str(relative_to_user).startswith("shared") or str(relative_to_user).startswith("workflows")):
                        raise ValueError(f"Folder scan only allowed in 'shared' or 'workflows' folders")
                except ValueError:
                    pass
                
                extensions = ['.jpg', '.jpeg', '.png', '.bmp'] if validated.mode.value == "folder_images" else ['.mp4', '.avi', '.mov', '.mkv']
                
                if validated.recursive:
                    for ext in extensions:
                        sources.extend([str(p) for p in folder.rglob(f"*{ext}")])
                else:
                    for ext in extensions:
                        sources.extend([str(p) for p in folder.glob(f"*{ext}")])
            
            elif validated.mode.value == "rtsp":
                sources.append(validated.rtsp_url)
            
            elif validated.mode.value == "webcam":
                sources.append(f"webcam:{validated.camera_index}")
            
            logger.info(f"Input node {node_id} prepared {len(sources)} sources")
            
            return {
                "input_sources": sources,
                "input_mode": validated.mode.value,
                "source_count": len(sources),
                "post_process_action": validated.post_process_action,
                "output_folder": validated.output_folder
            }
            
        except Exception as e:
            logger.error(f"Input node {node_id} failed: {str(e)}")
            raise
