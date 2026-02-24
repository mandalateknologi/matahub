"""
Prediction Worker - Background prediction job Execution
"""
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List
import cv2

from app.db import SessionLocal
from app.models.prediction_job import PredictionJob, PredictionStatus
from app.models.prediction_result import PredictionResult
from app.services.yolo_service import yolo_service
from app.services.sam3_service import sam3_service
from app.config import settings
import time

class PredictionWorker:
    """Worker for running prediction jobs in background threads."""
    
    def __init__(self):
        self._active_jobs: dict = {}
    
    def start_single_prediction(
        self,
        job_id: int,
        model_path: str,
        image_path: str,
        task_type: str = "detect",
        confidence: float = 0.25,
        iou_threshold: Optional[float] = 0.5,
        imgsz: Optional[int] = 1024,
        class_filter: Optional[List[str]] = None
    ) -> None:
        """
        Start a single image prediction job in a background thread.
        
        Args:
            job_id: prediction job ID
            model_path: Path to the model weights
            image_path: Path to the image file
            task_type: Task type (detect, classify, segment)
            confidence: Confidence threshold
            class_filter: Optional list of class names to filter
        """
        thread = threading.Thread(
            target=self._run_single_prediction,
            args=(job_id, model_path, image_path, task_type, confidence, class_filter),
            daemon=True
        )
        self._active_jobs[job_id] = thread
        thread.start()
    
    def start_batch_prediction(
        self,
        job_id: int,
        model_path: str,
        image_paths: List[str],
        task_type: str = "detect",
        confidence: float = 0.25,
        iou_threshold: Optional[float] = 0.5,
        imgsz: Optional[int] = 1024,
        class_filter: Optional[List[str]] = None
    ) -> None:
        """
        Start a batch prediction job in a background thread.
        
        Args:
            job_id: prediction job ID
            model_path: Path to the model weights
            image_paths: List of image file paths
            task_type: Task type (detect, classify, segment)
            confidence: Confidence threshold
            class_filter: Optional list of class names to filter
        """
        thread = threading.Thread(
            target=self._run_batch_prediction,
            args=(
                    job_id, model_path, image_paths, task_type, confidence, iou_threshold, imgsz, class_filter
                ),
            daemon=True
        )
        self._active_jobs[job_id] = thread
        thread.start()
    
    def start_video_prediction(
        self,
        job_id: int,
        model_path: str,
        video_path: str,
        task_type: str = "detect",
        confidence: float = 0.25,
        skip_frames: int = 5,
        iou_threshold: Optional[float] = 0.5,
        imgsz: Optional[int] = 1024,
        limit_frames:  Optional[int] = None,
        class_filter: Optional[List[str]] = None
    ) -> None:
        """
        Start a video prediction job in a background thread.
        
        Args:
            job_id: prediction job ID
            model_path: Path to the model weights
            video_path: Path to the video file
            task_type: Task type (detect, classify, segment)
            confidence: Confidence threshold
            skip_frames: Process every Nth frame
            
            class_filter: Optional list of class names to filter
        """
        thread = threading.Thread(
            target=self._run_video_prediction,
            args=(job_id, model_path, video_path, task_type, confidence, skip_frames, limit_frames, class_filter),
            daemon=True
        )
        self._active_jobs[job_id] = thread
        thread.start()
    
    def _run_single_prediction(
        self,
        job_id: int,
        model_path: str,
        image_path: str,
        task_type: str,
        confidence: float,
        iou_threshold: Optional[float] = 0.5,
        imgsz: Optional[int] = 1024,
        class_filter: Optional[List[str]] = None
    ) -> None:
        """Execute single image prediction job in background."""
        db = SessionLocal()
        
        try:
            # Update job status to running
            job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
            if not job:
                return
            
            job.status = PredictionStatus.RUNNING.value
            db.commit()
            
            # Run single image detection/classification
            result = yolo_service.detect_image(
                model_path=model_path,
                image_path=image_path,
                task_type=task_type,
                confidence=confidence,
                class_filter=class_filter
            )
            
            # Extract filename from path
            filename = Path(image_path).name
            
            # Build result config
            from app.schemas.prediction import ResultConfig
            result_config = ResultConfig(
                confidence=confidence,
                iou_threshold=iou_threshold,
                imgsz=imgsz,
                class_filter=class_filter,
                prompts=None,
                inference_type="yolo"
            ).model_dump()
            
            # Store result
            prediction_result = PredictionResult(
                prediction_job_id=job_id,
                file_name=filename,
                task_type=result.task_type,
                boxes_json=result.boxes or [],
                scores_json=result.scores or [],
                classes_json=result.classes or [],
                class_names_json=result.class_names or [],
                masks_json=result.masks or [],
                top_class=result.top_class,
                top_confidence=result.top_confidence,
                top_classes_json=result.top_classes or None,
                probabilities_json=result.probabilities or None,
                config_json=result_config
            )
            db.add(prediction_result)
            
            # Calculate stats
            total_detections = len(result.boxes) if result.boxes else 0
            class_counts = {}
            if result.class_names:
                for class_name in result.class_names:
                    class_counts[class_name] = class_counts.get(class_name, 0) + 1
            
            total_confidence = sum(result.scores) if result.scores else 0
            confidence_count = len(result.scores) if result.scores else 0
            avg_confidence = total_confidence / confidence_count if confidence_count > 0 else 0
            
            # Update job as completed with task-specific stats
            db.refresh(job)
            job.status = PredictionStatus.COMPLETED.value
            job.completed_at = datetime.now(timezone.utc)
            job.progress = 100
            
            # Use update_stats instead of direct dictionary assignment
            try:
                if task_type == "classify":
                    job.update_stats(
                        replace=True,
                        total_classifications=1,
                        top_class_distribution={result.top_class: 1} if result.top_class else {},
                        average_top_confidence=result.top_confidence or 0.0,
                        top_classes_summary=[{"class": result.top_class, "confidence": result.top_confidence or 0.0}] if result.top_class else [],
                        inference_time_ms=result.inference_time_ms or 0.0,
                        processing_time_ms=0.0
                    )
                elif task_type == "segment":
                    job.update_stats(
                        replace=True,
                        total_masks=total_detections,
                        mask_count_per_class=class_counts,
                        average_confidence=avg_confidence,
                        inference_time_ms=result.inference_time_ms or 0.0,
                        processing_time_ms=0.0
                    )
                else:  # detect
                    job.update_stats(
                        replace=True,
                        total_detections=total_detections,
                        class_counts=class_counts,
                        average_confidence=avg_confidence,
                        inference_time_ms=result.inference_time_ms or 0.0,
                        processing_time_ms=0.0
                    )
            except Exception as stats_err:
                print(f"Failed to update stats, using fallback: {stats_err}")
                # Fallback to basic stats if update_stats fails
                job.update_stats(
                    replace=True,
                    total_detections=total_detections,
                    class_counts=class_counts,
                    average_confidence=avg_confidence
                )
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            
            try:
                job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
                if job:
                    job.status = PredictionStatus.FAILED.value
                    job.error_message = str(e)[:1000]
                    job.completed_at = datetime.now(timezone.utc)
                db.commit()
            except Exception:
                db.rollback()
            
            print(f"Single prediction job {job_id} failed: {str(e)}")
            traceback.print_exc()
            
        finally:
            db.close()
            if job_id in self._active_jobs:
                del self._active_jobs[job_id]
    
    def _run_batch_prediction(
        self,
        job_id: int,
        model_path: str,
        image_paths: List[str],
        task_type: str,
        confidence: float,
        iou_threshold: Optional[float] = 0.5,
        imgsz: Optional[int] = 1024,
        class_filter: Optional[List[str]] = None
    ) -> None:
        """Execute batch prediction job in background."""
        db = SessionLocal()
        
        try:
            # Update job status to running
            job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
            if not job:
                return
            
            job.status = PredictionStatus.RUNNING.value
            db.commit()
            
            # Run batch detection/classification
            results = yolo_service.detect_batch(
                model_path=model_path,
                image_paths=image_paths,
                task_type=task_type,
                confidence=confidence,
                class_filter=class_filter
            )
            
            # Store results
            processed_count = 0
            total_images = len(image_paths)
            results_list: List[PredictionResult] = []

            for filename, result in results:
                processed_count += 1
                
                # Build result config
                from app.schemas.prediction import ResultConfig
                result_config = ResultConfig(
                    confidence=confidence,
                    iou_threshold=iou_threshold,
                    imgsz=imgsz,
                    class_filter=class_filter,
                    prompts=None,
                    inference_type="yolo"
                ).model_dump()
                
                prediction_result = PredictionResult(
                    prediction_job_id=job_id,
                    file_name=filename,
                    task_type=result.task_type,
                    boxes_json=result.boxes or [],
                    scores_json=result.scores or [],
                    classes_json=result.classes or [],
                    class_names_json=result.class_names or [],
                    masks_json=result.masks or [],  # Add segmentation masks
                    top_class=result.top_class,
                    top_confidence=result.top_confidence,
                    top_classes_json=result.top_classes or None,
                    probabilities_json=result.probabilities or None,
                    config_json=result_config
                )
                db.add(prediction_result)
                results_list.append(prediction_result)
                
                # Update progress every 5 images
                if processed_count % 5 == 0 or processed_count == total_images:
                    db.refresh(job)
                    job.progress = int((processed_count / total_images) * 100)
                    job.update_metadata(frames_processed=processed_count)
                    db.commit()
            
            # Update job as completed with task-specific stats
            db.refresh(job)
            job.status = PredictionStatus.COMPLETED.value
            job.completed_at = datetime.now(timezone.utc)
            job.progress = 100
            
            # Use update_stats instead of direct dictionary assignment
            try:
                job.finalize_stats(task_type=task_type, results=results_list)
            except Exception as stats_err:
                print(f"Failed to update stats, using fallback: {stats_err}")

            db.commit()

        except Exception as e:
            db.rollback()
            
            try:
                job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
                if job:
                    job.status = PredictionStatus.FAILED.value
                    job.error_message = str(e)[:1000]
                    job.completed_at = datetime.now(timezone.utc)
                db.commit()
            except Exception:
                db.rollback()
            
            print(f"Batch prediction job {job_id} failed: {str(e)}")
            traceback.print_exc()
            
        finally:
            db.close()
            if job_id in self._active_jobs:
                del self._active_jobs[job_id]
    
    def _run_video_prediction(
        self,
        job_id: int,
        model_path: str,
        video_path: str,
        task_type: str,
        confidence: float,
        skip_frames: int,
        iou_threshold: Optional[float] = 0.5,
        imgsz: Optional[int] = 1024,
        limit_frames: Optional[List[str]] = None,
        class_filter: Optional[List[str]] = None
    ) -> None:
        """Execute video detection/classification job in background."""
        db = SessionLocal()
        
        try:
            # Update job status to running
            job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
            if not job:
                return
            
            job.status = PredictionStatus.RUNNING.value
            
            # Create detection output directory
            prediction_dir = Path(settings.predictions_dir) / str(job_id)
            prediction_dir.mkdir(parents=True, exist_ok=True)
            
            # Get total frames and FPS for progress calculation
            cap = cv2.VideoCapture(video_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            video_fps = cap.get(cv2.CAP_PROP_FPS)
            if not video_fps or video_fps == 0:
                video_fps = 30  # Fallback to 30 FPS if unable to detect
            cap.release()
            
            # Initialize video metadata (config already set by API)
            try:
                job.update_metadata(
                    frames_processed=0,
                    total_frames=total_frames,
                    video_duration=total_frames / video_fps if video_fps > 0 else None,
                    fps=video_fps
                )
                db.commit()
            except Exception as meta_err:
                print(f"Failed to initialize metadata: {meta_err}")
            
            # Run video detection (generator)
            # Store results (sample frames to avoid too many results)
            total_detections = 0
            class_counts = {}
            total_confidence = 0.0
            confidence_count = 0
            frames_processed = 0
            
            # Store every 10th result to reduce database load
            for frame_number, result, frame in yolo_service.detect_video(
                model_path=model_path,
                video_path=video_path,
                task_type=task_type,
                confidence=confidence,
                skip_frames=skip_frames,
                return_frame=True,
                class_filter=class_filter
            ):
                # Store every 10th frame to reduce database load
                if result:
                    if frames_processed % 10 == 0:
                        # Save frame to disk
                        frame_filename = f"frame_{frame_number}.jpg"
                        frame_path = prediction_dir / frame_filename
                        cv2.imwrite(str(frame_path), frame)
                        
                        # Build result config
                        from app.schemas.prediction import ResultConfig
                        result_config = ResultConfig(
                            confidence=confidence,
                            iou_threshold=None,
                            imgsz=None,
                            class_filter=class_filter,
                            prompts=None,
                            inference_type="yolo"
                        ).model_dump()
                        
                        prediction_result = PredictionResult(
                            prediction_job_id=job_id,
                            file_name=frame_filename,
                            frame_number=frame_number,
                            task_type=result.task_type,
                            boxes_json=result.boxes,
                            scores_json=result.scores,
                            classes_json=result.classes,
                            class_names_json=result.class_names,
                            top_class=result.top_class,
                            top_confidence=result.top_confidence,
                            top_classes_json=result.top_classes or None,
                            probabilities_json=result.probabilities or None,
                            masks_json=result.masks or [],
                            config_json=result_config
                        )
                        db.add(prediction_result)
                    
                    # Aggregate stats for all frames
                    total_detections += len(result.boxes)
                    for class_name in result.class_names:
                        class_counts[class_name] = class_counts.get(class_name, 0) + 1
                    for score in result.scores:
                        total_confidence += score
                        confidence_count += 1
                        
                frames_processed += 1
                if limit_frames and limit_frames > 0:
                    # Check if we've reached the frame limit
                    if frames_processed >= limit_frames:
                        print(f"Video job {job_id}: Reached frame limit ({limit_frames}), stopping processing")
                        break
                
                # Update progress every 10 frames
                if frames_processed % 10 == 0:
                    db.refresh(job)
                    job.progress = int((frames_processed / total_frames) * 100) if total_frames > 0 else 0
                    
                    # Update stats and metadata incrementally (don't replace config)
                    try:
                        avg_conf = total_confidence / confidence_count if confidence_count > 0 else 0
                        job.update_stats(
                            replace=True,
                            total_detections=total_detections,
                            class_counts=class_counts,
                            average_confidence=avg_conf,
                            inference_time_ms=0.0,
                            processing_time_ms=0.0
                        )
                        job.update_metadata(
                            frames_processed=frames_processed,
                            total_frames=total_frames
                        )
                    except Exception as update_err:
                        print(f"Failed to update progress stats/metadata: {update_err}")
                    
                    db.commit()
            
            # Update job as completed with task-specific stats and metadata
            db.refresh(job)
            job.status = PredictionStatus.COMPLETED.value
            job.completed_at = datetime.now(timezone.utc)
            job.progress = 100
            
            avg_confidence = total_confidence / confidence_count if confidence_count > 0 else 0
            
            # Use update_stats and update_metadata instead of direct dictionary assignment
            try:
                job.update_stats(
                    replace=True,
                    total_detections=total_detections,
                    class_counts=class_counts,
                    average_confidence=avg_confidence,
                    inference_time_ms=0.0,
                    processing_time_ms=0.0
                )
                job.update_metadata(
                    frames_processed=frames_processed
                )
            except Exception as stats_err:
                print(f"Failed to update stats/metadata, using fallback: {stats_err}")
                job.update_stats(
                    replace=True,
                    total_detections=total_detections,
                    class_counts=class_counts,
                    average_confidence=avg_confidence
                )
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            
            try:
                job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
                if job:
                    job.status = PredictionStatus.FAILED.value
                    job.error_message = str(e)[:1000]
                    job.completed_at = datetime.now(timezone.utc)
                db.commit()
            except Exception:
                db.rollback()
            
            print(f"Video prediction job {job_id} failed: {str(e)}")
            traceback.print_exc()
            
        finally:
            db.close()
            if job_id in self._active_jobs:
                del self._active_jobs[job_id]
    
    def start_rtsp_prediction(
        self,
        job_id: int,
        model_path: str,
        rtsp_url: str,
        task_type: str = "detect",
        confidence: float = 0.25,
        skip_frames: int = 5,
        capture_mode: str = "continuous",
        iou_threshold: Optional[float] = 0.5,
        imgsz: Optional[int] = 1024,
        class_filter: Optional[List[str]] = None
    ) -> None:
        """
        Start RTSP stream detection in a background thread.
        
        Args:
            job_id: prediction job ID
            model_path: Path to the model weights
            rtsp_url: RTSP stream URL
            task_type: Task type (detect, classify, segment)
            confidence: Confidence threshold
            skip_frames: Process every Nth frame
            capture_mode: "continuous" (auto-save all frames) or "manual" (preview only)
            class_filter: Optional list of class names to filter
        """
        thread = threading.Thread(
            target=self._run_rtsp_prediction,
            args=(job_id, model_path, rtsp_url, task_type, confidence, skip_frames, capture_mode, class_filter),
            daemon=True
        )
        self._active_jobs[job_id] = {
            'thread': thread,
            'stop_flag': threading.Event(),
            'latest_frame': None,
            'latest_results': None
        }
        thread.start()
    
    def stop_job(self, job_id: int) -> None:
        """
        Stop a running inference job.
        
        Args:
            job_id: inference job ID
        """
        if job_id in self._active_jobs:
            self._active_jobs[job_id]['stop_flag'].set()
    
    def _run_rtsp_prediction(
        self,
        job_id: int,
        model_path: str,
        rtsp_url: str,
        task_type: str,
        confidence: float,
        skip_frames: int,
        capture_mode: str = "continuous",
        iou_threshold: Optional[float] = 0.5,
        imgsz: Optional[int] = 1024,
        class_filter: Optional[List[str]] = None
    ) -> None:
        """
        Run RTSP stream detection/classification.
        
        Args:
            job_id: prediction job ID
            model_path: Path to the model weights
            rtsp_url: RTSP stream URL
            task_type: Task type (detect, classify, segment)
            confidence: Confidence threshold
            skip_frames: Process every Nth frame
            capture_mode: "continuous" (auto-save all frames) or "manual" (preview only)
            class_filter: Optional list of class names to filter
        """
        db = SessionLocal()
        
        try:
            # Update job status to running
            job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
            if not job:
                return
            
            job.status = PredictionStatus.RUNNING.value
            db.commit()
            
            # Create detection output directory
            prediction_dir = Path(settings.predictions_dir) / str(job_id)
            prediction_dir.mkdir(parents=True, exist_ok=True)
            
            # Initialize detection counters
            total_detections = 0
            frames_processed = 0
            class_counts = {}
            total_confidence = 0.0
            confidence_count = 0
            
            # Get stop flag
            stop_flag = self._active_jobs[job_id]['stop_flag']
            
            # Process RTSP stream (using video detection with RTSP URL)
            print(f"Starting RTSP detection for job {job_id}, confidence={confidence}, skip_frames={skip_frames}")
            
            for frame_number, result, frame in yolo_service.detect_video(
                    model_path=model_path,
                    task_type=task_type,
                    video_path=rtsp_url,  # RTSP URL works as video source
                    confidence=confidence,
                    skip_frames=skip_frames,
                    return_frame=True,  # Get frame for streaming
                    class_filter=class_filter
                ):

                # Check if stop requested
                if stop_flag.is_set():
                    print(f"RTSP prediction job {job_id} stopped by user")
                    break
                
                # Store latest frame and results for MJPEG streaming
                if job_id in self._active_jobs:
                    self._active_jobs[job_id]['latest_frame'] = frame.copy()
                    if result:
                        self._active_jobs[job_id]['latest_results'] = {
                            'boxes': result.boxes if result.boxes else [],
                            'scores': result.scores if result.scores else [],
                            'classes': result.classes if result.classes else [],
                            'class_names': result.class_names if result.class_names else [],
                            'masks': result.masks if result.masks else []
                        }
                    else:
                        self._active_jobs[job_id]['latest_results'] = {
                            'boxes': [],
                            'scores': [],
                            'classes': [],
                            'class_names': [],
                            'masks': []
                        }
                
                # Only save to disk and database in continuous mode
                # Manual mode only stores in memory for preview
                if capture_mode == "continuous":
                    if result:
                        # Save result frame and data, if there are detections
                        frame_filename = f"frame_{frame_number}.jpg"
                        frame_path = prediction_dir / frame_filename
                        cv2.imwrite(str(frame_path), frame)
                        
                        # Build result config
                        from app.schemas.prediction import ResultConfig
                        result_config = ResultConfig(
                            confidence=confidence,
                            iou_threshold=None,
                            imgsz=None,
                            class_filter=class_filter,
                            prompts=None,
                            inference_type="yolo"
                        ).model_dump()
                        
                        # Save detection result to database (even if no detections)
                        prediction_result = PredictionResult(
                            prediction_job_id=job_id,
                            file_name=frame_filename,
                            frame_number=frame_number,
                            task_type=result.task_type,
                            boxes_json=result.boxes if result.boxes else [],
                            scores_json=result.scores if result.scores else [],
                            classes_json=result.classes if result.classes else [],
                            class_names_json=result.class_names if result.class_names else [],
                            masks_json=result.masks if result.masks else [],
                            top_class=result.top_class,
                            top_confidence=result.top_confidence,
                            top_classes_json=result.top_classes or None,
                            probabilities_json=result.probabilities or None,
                            config_json=result_config
                        )
                        db.add(prediction_result)
                
                # Update stats
                if result:
                    total_detections += len(result.boxes) if result.boxes else 0
                    if result.class_names:
                        for class_name in result.class_names:
                            class_counts[class_name] = class_counts.get(class_name, 0) + 1
                    if result.scores:
                        for score in result.scores:
                            total_confidence += score
                            confidence_count += 1

                frames_processed += 1
                
                # Log progress
                if frames_processed % 5 == 0:
                    print(f"RTSP job {job_id}: Processed {frames_processed} frames, {total_detections} detections")
                
                # Commit frequently for RTSP (every 5 frames for faster UI updates)
                if frames_processed % 5 == 0:
                    db.refresh(job)
                    job.progress = frames_processed  # Store frame count for RTSP
                    
                    # Update stats and metadata incrementally (don't replace config)
                    try:
                        avg_conf = total_confidence / confidence_count if confidence_count > 0 else 0
                        job.update_stats(
                            replace=True,
                            total_detections=total_detections,
                            class_counts=class_counts,
                            average_confidence=avg_conf,
                            inference_time_ms=0.0,
                            processing_time_ms=0.0
                        )
                        job.update_metadata(
                            frames_processed=frames_processed
                        )
                    except Exception as update_err:
                        print(f"Failed to update RTSP progress stats/metadata: {update_err}")
                    
                    db.commit()
            
            # Update job as completed
            print(f"RTSP job {job_id} finishing: {frames_processed} frames, {total_detections} detections")
            
            db.refresh(job)
            job.status = PredictionStatus.COMPLETED.value
            job.completed_at = datetime.now(timezone.utc)
            job.progress = frames_processed  # Final frame count
            
            avg_confidence = total_confidence / confidence_count if confidence_count > 0 else 0
            
            # Use update_stats and update_metadata instead of direct dictionary assignment
            try:
                job.update_stats(
                    replace=True,
                    total_detections=total_detections,
                    class_counts=class_counts,
                    average_confidence=avg_confidence,
                    inference_time_ms=0.0,
                    processing_time_ms=0.0
                )
                job.update_metadata(
                    frames_processed=frames_processed
                )
            except Exception as stats_err:
                print(f"Failed to update stats/metadata, using fallback: {stats_err}")
                job.update_stats(
                    replace=True,
                    total_detections=total_detections,
                    class_counts=class_counts,
                    average_confidence=avg_confidence
                )
            
            # Commit all remaining results before marking as complete
            db.commit()
            print(f"RTSP job {job_id} completed successfully")
            
        except Exception as e:
            print(f"Error in RTSP prediction job {job_id}: {str(e)}")
            import traceback
            traceback.print_exc()
            
            db.rollback()
            
            try:
                job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
                if job:
                    job.status = PredictionStatus.FAILED.value
                    job.error_message = str(e)[:1000]
                    job.completed_at = datetime.now(timezone.utc)
                db.commit()
            except Exception:
                db.rollback()
            
            print(f"RTSP prediction job {job_id} failed: {str(e)}")
            traceback.print_exc()
            
        finally:
            db.close()
            if job_id in self._active_jobs:
                del self._active_jobs[job_id]
    
    def is_job_running(self, job_id: int) -> bool:
        """Check if a prediction job is currently running."""
        if job_id not in self._active_jobs:
            return False
        job_info = self._active_jobs[job_id]
        if isinstance(job_info, dict):
            return job_info['thread'].is_alive()
        return job_info.is_alive()
    
    def get_active_jobs(self) -> list:
        """Get list of active job IDs."""
        active = []
        for jid, job_info in self._active_jobs.items():
            if isinstance(job_info, dict):
                if job_info['thread'].is_alive():
                    active.append(jid)
            elif job_info.is_alive():
                active.append(jid)
        return active
    
    def start_sam3_batch_detection(
        self,
        job_id: int,
        model_path: str,
        image_paths: List[str],
        file_names: List[str],
        prompts: List[dict],
        confidence: Optional[float] = 0.25,
        iou_threshold: Optional[float] = 0.5,
        imgsz: Optional[int] = 1024,
        class_filter: Optional[List[str]] = None,
        bpe_path: Optional[str] = None
    ) -> None:
        """
        Start a SAM3 batch detection job in a background thread.
        
        Args:
            job_id: Detection job ID
            model_path: Path to the SAM3 model
            image_paths: List of image file paths
            file_names: List of original file names
            prompts: List of SAM3 prompts (same prompts applied to all images)
            bpe_path: Optional path to BPE tokenizer file
        """
        thread = threading.Thread(
            target=self._run_sam3_batch_detection,
            args=(job_id, model_path, image_paths, file_names, prompts, bpe_path),
            daemon=True
        )
        self._active_jobs[job_id] = thread
        thread.start()
    
    def start_sam3_video_segmentation(
        self,
        job_id: int,
        model_path: str,
        video_path: str,
        prompts: List[dict],
        skip_frames: int = 5,
        iou_threshold: Optional[float] = 0.5,
        imgsz: Optional[int] = 1024,
        limit_frames:  Optional[int] = None,
        bpe_path: Optional[str] = None
    ) -> None:
        """
        Start a SAM3 video segmentation job in a background thread.
        
        Args:
            job_id: Detection job ID
            model_path: Path to the SAM3 model
            video_path: Path to the video file
            prompts: List of SAM3 prompts (same prompts applied to all frames)
            skip_frames: Process every Nth frame (default 5)
            limit_frames: Limit the number of frames to process (default 1000)
        """
        thread = threading.Thread(
            target=self._run_sam3_video_segmentation,
            args=(job_id, model_path, video_path, prompts, skip_frames, limit_frames, bpe_path),
            daemon=True
        )
        self._active_jobs[job_id] = thread
        thread.start()
    
    def start_rtsp_sam3_detection(
        self,
        job_id: int,
        model_path: str,
        bpe_path: str,
        rtsp_url: str,
        prompts: list,
        skip_frames: int = 10,
        capture_mode: str = "manual",
        class_filter: list = None,
        confidence: Optional[float] = 0.25,
        iou_threshold: Optional[float] = 0.5,
        imgsz: Optional[int] = 1024
    ) -> None:
        """
        Start SAM3 RTSP stream segmentation in background thread.
        
        Args:
            job_id: Detection job ID
            model_path: Path to SAM3 model weights
            bpe_path: Path to BPE vocabulary file
            rtsp_url: RTSP stream URL
            prompts: List of SAM3 prompt dicts
            skip_frames: Process every Nth frame (default 10 for SAM3)
            capture_mode: "continuous" (auto-save) or "manual" (preview only)
            class_filter: Optional list of class names to filter
        """
        thread = threading.Thread(
            target=self._run_rtsp_sam3_detection,
            args=(job_id, model_path, bpe_path, rtsp_url, prompts, skip_frames, capture_mode, class_filter),
            daemon=True
        )
        self._active_jobs[job_id] = {
            'thread': thread,
            'stop_flag': threading.Event(),
            'latest_frame': None,
            'latest_masks': [],
            'last_cleanup': time.time()
        }
        thread.start()
    
    def _run_sam3_batch_detection(
        self,
        job_id: int,
        model_path: str,
        image_paths: List[str],
        file_names: List[str],
        prompts: List[dict],
        confidence: Optional[float] = 0.25,
        iou_threshold: Optional[float] = 0.5,
        imgsz: Optional[int] = 1024,
        bpe_path: Optional[str] = None
    ) -> None:
        """Execute SAM3 batch detection job in background."""
        db = SessionLocal()
        
        try:
            job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
            if not job:
                return
            
            job.status = PredictionStatus.RUNNING.value
            db.commit()
            
            total_masks = 0
            processed_count = 0
            total_images = len(image_paths)
            
            for image_path, file_name in zip(image_paths, file_names):
                processed_count += 1
                
                try:
                    result = sam3_service.segment_image(
                        model_path=model_path,
                        image_path=image_path,
                        prompts=prompts,
                        bpe_path=bpe_path
                    )
                    
                    # Build result config
                    from app.schemas.prediction import ResultConfig
                    result_config = ResultConfig(
                        confidence=0.0,  # SAM3 doesn't use confidence
                        iou_threshold=None,
                        imgsz=1024,
                        class_filter=None,
                        prompts=prompts,
                        inference_type="sam3"
                    ).model_dump()
                    
                    prediction_result = PredictionResult(
                        prediction_job_id=job_id,
                        file_name=file_name,
                        task_type="segment",
                        boxes_json=result.boxes or [],
                        scores_json=result.scores or [],
                        classes_json=result.classes or [],
                        class_names_json=result.class_names or [],
                        masks_json=result.masks or [],
                        config_json=result_config
                    )
                    db.add(prediction_result)
                    
                    total_masks += len(result.masks) if result.masks else 0
                    
                except Exception as e:
                    print(f"SAM3 batch: Error processing {file_name}: {str(e)}")
                    traceback.print_exc()
                
                if processed_count % 5 == 0 or processed_count == total_images:
                    job.progress = int((processed_count / total_images) * 100)
                    job.update_metadata(frames_processed=processed_count)
                    db.commit()
            
            db.refresh(job)
            job.status = PredictionStatus.COMPLETED.value
            job.completed_at = datetime.now(timezone.utc)
            job.progress = 100
            
            # Use update_stats for segmentation instead of direct dictionary assignment
            try:
                job.update_stats(
                    replace=True,
                    total_masks=total_masks,
                    mask_count_per_class={},
                    average_confidence=0.0,
                    inference_time_ms=0.0,
                    processing_time_ms=0.0
                )
            except Exception as stats_err:
                print(f"Failed to update stats, using fallback: {stats_err}")
                job.update_stats(
                    replace=True,
                    total_masks=total_masks
                )
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            try:
                job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
                if job:
                    job.status = PredictionStatus.FAILED.value
                    job.error_message = str(e)
                db.commit()
            except Exception:
                db.rollback()
            print(f"SAM3 batch job {job_id} failed: {str(e)}")
            traceback.print_exc()
        finally:
            db.close()
            if job_id in self._active_jobs:
                del self._active_jobs[job_id]
    
    def _run_sam3_video_segmentation(
        self,
        job_id: int,
        model_path: str,
        video_path: str,
        prompts: List[dict],
        skip_frames: int,
        confindence: Optional[float] = 0.25,
        iou_threshold: Optional[float] = 0.5,
        imgsz: Optional[int] = 1024,
        limit_frames:  Optional[int] = None,
        bpe_path: Optional[str] = None
    ) -> None:
        """Execute SAM3 video segmentation job in background."""
        db = SessionLocal()
        
        try:
            job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
            if not job:
                return
            
            job.status = PredictionStatus.RUNNING.value
            
            cap = cv2.VideoCapture(video_path)
            total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
            video_fps = cap.get(cv2.CAP_PROP_FPS)
            if not video_fps or video_fps == 0:
                video_fps = 30  # Fallback to 30 FPS if unable to detect
            cap.release()
            
            # Initialize video metadata (config already set by API)
            try:
                job.update_metadata(
                    frames_processed=0,
                    total_frames=total_frames,
                    video_duration=total_frames / video_fps if video_fps > 0 else None,
                    fps=video_fps
                )
                db.commit()
            except Exception as meta_err:
                print(f"Failed to initialize SAM3 video metadata: {meta_err}")
            
            total_masks = 0
            frames_processed = 0
            frame_count = 0
            
            cap = cv2.VideoCapture(video_path)
            
            while cap.isOpened():
                ret, frame = cap.read()
                if not ret:
                    break
                
                if frame_count % skip_frames == 0:
                    temp_path = Path(settings.predictions_dir) / str(job_id) / f"frame_{frame_count}.jpg"
                    temp_path.parent.mkdir(parents=True, exist_ok=True)
                    cv2.imwrite(str(temp_path), frame)
                    
                    try:
                        result = sam3_service.segment_image(
                            model_path=model_path,
                            image_path=str(temp_path),
                            prompts=prompts,
                            bpe_path=bpe_path
                        )
                        
                        if result.masks and len(result.masks) > 0:
                            # Build result config
                            from app.schemas.prediction import ResultConfig
                            result_config = ResultConfig(
                                confidence=0.0,
                                iou_threshold=None,
                                imgsz=1024,
                                class_filter=None,
                                prompts=prompts,
                                inference_type="sam3"
                            ).model_dump()
                            
                            prediction_result = PredictionResult(
                                prediction_job_id=job_id,
                                file_name=f"frame_{frame_count}.jpg",
                                task_type="segment",
                                frame_number=frame_count,
                                boxes_json=result.boxes or [],
                                scores_json=result.scores or [],
                                classes_json=result.classes or [],
                                class_names_json=result.class_names or [],
                                masks_json=result.masks or [],
                                config_json=result_config
                            )
                            db.add(prediction_result)
                            total_masks += len(result.masks)
                        
                    except Exception as e:
                        print(f"SAM3 video: Error processing frame {frame_count}: {str(e)}")
                    
                    frames_processed += 1
                    
                    # Check if we've reached the frame limit
                    if limit_frames and limit_frames > 0:
                        if frames_processed >= limit_frames:
                            print(f"SAM3 video job {job_id}: Reached frame limit ({limit_frames}), stopping processing")
                            break
                    
                    if frames_processed % 5 == 0:
                        job.progress = int((frame_count / total_frames) * 100)
                        
                        # Update stats and metadata incrementally (don't replace config)
                        try:
                            job.update_stats(
                                replace=True,
                                total_masks=total_masks,
                                mask_count_per_class={},
                                average_confidence=0.0,
                                inference_time_ms=0.0,
                                processing_time_ms=0.0
                            )
                            job.update_metadata(
                                frames_processed=frames_processed,
                                total_frames=total_frames
                            )
                        except Exception as update_err:
                            print(f"Failed to update SAM3 video progress: {update_err}")
                        
                        db.commit()
                
                frame_count += 1
            
            cap.release()
            
            db.refresh(job)
            job.status = PredictionStatus.COMPLETED.value
            job.completed_at = datetime.now(timezone.utc)
            job.progress = 100
            
            # Use update_stats and update_metadata instead of direct dictionary assignment
            try:
                job.update_stats(
                    replace=True,
                    total_masks=total_masks,
                    mask_count_per_class={},
                    average_confidence=0.0,
                    inference_time_ms=0.0,
                    processing_time_ms=0.0
                )
                job.update_metadata(
                    frames_processed=frames_processed
                )
            except Exception as stats_err:
                print(f"Failed to update stats/metadata, using fallback: {stats_err}")
                job.update_stats(
                    replace=True,
                    total_masks=total_masks
                )
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            try:
                job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
                if job:
                    job.status = PredictionStatus.FAILED.value
                    job.error_message = str(e)
                db.commit()
            except Exception:
                db.rollback()
            print(f"SAM3 video job {job_id} failed: {str(e)}")
            traceback.print_exc()
        finally:
            db.close()
            if job_id in self._active_jobs:
                del self._active_jobs[job_id]
    
    def _run_rtsp_sam3_detection(
        self,
        job_id: int,
        model_path: str,
        bpe_path: str,
        rtsp_url: str,
        prompts: list,
        skip_frames: int,
        capture_mode: str,
        class_filter: list = None,
        confidence: Optional[float] = 0.25,
        iou_threshold: Optional[float] = 0.5,
        imgsz: Optional[int] = 1024,
    ) -> None:
        """Run SAM3 RTSP stream segmentation worker."""
        db = SessionLocal()
        
        try:
            job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
            if not job:
                return
            
            job.status = PredictionStatus.RUNNING.value
            db.commit()
            
            cap = cv2.VideoCapture(rtsp_url)
            if not cap.isOpened():
                raise Exception(f"Failed to open RTSP stream: {rtsp_url}")
            
            frame_count = 0
            frames_processed = 0
            total_masks = 0
            stop_flag = self._active_jobs[job_id]['stop_flag']
            last_cleanup = time.time()
            
            while cap.isOpened():
                if stop_flag.is_set():
                    print(f"SAM3 RTSP job {job_id} stopped by user")
                    break
                
                ret, frame = cap.read()
                if not ret:
                    print(f"SAM3 RTSP: Failed to read frame, reconnecting...")
                    time.sleep(1)
                    cap.release()
                    cap = cv2.VideoCapture(rtsp_url)
                    continue
                
                if frame_count % skip_frames == 0:
                    # In manual mode, only store frame in memory (no processing)
                    # In continuous mode, process and save to DB
                    if capture_mode == "manual":
                        # Just update latest frame for preview
                        self._active_jobs[job_id]['latest_frame'] = frame.copy()
                        self._active_jobs[job_id]['latest_masks'] = []
                    else:
                        # Continuous mode: process frame
                        temp_path = Path(settings.predictions_dir) / str(job_id) / f"rtsp_frame_{frames_processed}.jpg"
                        temp_path.parent.mkdir(parents=True, exist_ok=True)
                        cv2.imwrite(str(temp_path), frame)
                        
                        try:
                            result = sam3_service.segment_image(
                                model_path=model_path,
                                image_path=str(temp_path),
                                prompts=prompts,
                                bpe_path=bpe_path
                            )
                            
                            self._active_jobs[job_id]['latest_frame'] = frame.copy()
                            self._active_jobs[job_id]['latest_masks'] = result.masks or []
                            
                            if result.masks and len(result.masks) > 0:
                                # Build result config
                                from app.schemas.prediction import ResultConfig
                                result_config = ResultConfig(
                                    confidence=0.0,
                                    iou_threshold=None,
                                    imgsz=1024,
                                    class_filter=None,
                                    prompts=prompts,
                                    inference_type="sam3"
                                ).model_dump()
                                
                                prediction_result = PredictionResult(
                                    prediction_job_id=job_id,
                                    file_name=f"rtsp_frame_{frames_processed}.jpg",
                                    task_type="segment",
                                    frame_number=frames_processed,
                                    boxes_json=result.boxes or [],
                                    scores_json=result.scores or [],
                                    classes_json=result.classes or [],
                                    class_names_json=result.class_names or [],
                                    masks_json=result.masks or [],
                                    config_json=result_config
                                )
                                db.add(prediction_result)
                                total_masks += len(result.masks)
                            
                        except Exception as e:
                            print(f"SAM3 RTSP: Error processing frame: {str(e)}")
                    
                    frames_processed += 1
                    
                    if frames_processed % 10 == 0:
                        # Update stats and metadata incrementally (don't replace config)
                        try:
                            job.update_stats(
                                replace=True,
                                total_masks=total_masks,
                                mask_count_per_class={},
                                average_confidence=0.0,
                                inference_time_ms=0.0,
                                processing_time_ms=0.0
                            )
                            job.update_metadata(
                                frames_processed=frames_processed
                            )
                        except Exception as update_err:
                            print(f"Failed to update SAM3 RTSP progress: {update_err}")
                        
                        db.commit()
                
                frame_count += 1
                
                if time.time() - last_cleanup > 300:
                    self._cleanup_stale_jobs()
                    last_cleanup = time.time()
            
            cap.release()
            
            db.refresh(job)
            job.status = PredictionStatus.COMPLETED.value
            job.completed_at = datetime.now(timezone.utc)
            
            # Use update_stats and update_metadata instead of direct dictionary assignment
            try:
                job.update_stats(
                    replace=True,
                    total_masks=total_masks,
                    mask_count_per_class={},
                    average_confidence=0.0,
                    inference_time_ms=0.0,
                    processing_time_ms=0.0
                )
                job.update_metadata(
                    frames_processed=frames_processed
                )
            except Exception as stats_err:
                print(f"Failed to update stats/metadata, using fallback: {stats_err}")
                job.update_stats(
                    replace=True,
                    total_masks=total_masks
                )
            
            db.commit()
            
        except Exception as e:
            db.rollback()
            try:
                job = db.query(PredictionJob).filter(PredictionJob.id == job_id).first()
                if job:
                    job.status = PredictionStatus.FAILED.value
                    job.error_message = str(e)
                db.commit()
            except Exception:
                db.rollback()
            print(f"SAM3 RTSP job {job_id} failed: {str(e)}")
            traceback.print_exc()
        finally:
            db.close()
            if job_id in self._active_jobs:
                del self._active_jobs[job_id]
    
    def _cleanup_stale_jobs(self):
        """Remove stopped/completed jobs from memory cache."""
        stale_job_ids = []
        for job_id, job_data in self._active_jobs.items():
            if isinstance(job_data, dict):
                if not job_data['thread'].is_alive():
                    stale_job_ids.append(job_id)
            elif not job_data.is_alive():
                stale_job_ids.append(job_id)
        
        for job_id in stale_job_ids:
            del self._active_jobs[job_id]


# Global worker instance
prediction_worker = PredictionWorker()



