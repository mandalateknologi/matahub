"""
Export Worker - Background export job processing
"""
import threading
import zipfile
import json
import pandas as pd
from pathlib import Path
from datetime import datetime, timezone
from PIL import Image
from io import BytesIO
import cv2

from app.db import SessionLocal
from app.models.export_job import ExportJob, ExportStatus, ExportType
from app.models.prediction_job import PredictionJob
from app.models.prediction_result import PredictionResult
from app.config import settings


class ExportWorker:
    """Worker for processing export jobs in background."""
    
    def __init__(self):
        self.active_jobs = {}  # job_id -> thread
    
    def start_export(
        self,
        export_job_id: int,
        prediction_job_id: int,
        export_type: ExportType,
        options: dict
    ):
        """Start export job in background thread."""
        thread = threading.Thread(
            target=self._run_export,
            args=(export_job_id, prediction_job_id, export_type, options)
        )
        self.active_jobs[export_job_id] = thread
        thread.start()
    
    def _run_export(
        self,
        export_job_id: int,
        prediction_job_id: int,
        export_type: ExportType,
        options: dict
    ):
        """Run export job (executed in thread)."""
        db = SessionLocal()
        try:
            export_job = db.query(ExportJob).filter(ExportJob.id == export_job_id).first()
            if not export_job:
                return
            
            export_job.status = ExportStatus.PROCESSING
            export_job.progress = 0
            db.commit()
            
            # Route to appropriate export handler
            if export_type == ExportType.IMAGES_ZIP:
                self._export_images_zip(db, export_job, prediction_job_id, options)
            elif export_type == ExportType.DATA_JSON:
                self._export_data_json(db, export_job, prediction_job_id, options)
            elif export_type == ExportType.DATA_CSV:
                self._export_data_csv(db, export_job, prediction_job_id, options)
            elif export_type == ExportType.REPORT_PDF:
                # Check if single result export
                if options.get('single_result') and options.get('result_id'):
                    self._export_single_result_pdf(db, export_job, prediction_job_id, options)
                else:
                    self._export_report_pdf(db, export_job, prediction_job_id, options)
            
            export_job.status = ExportStatus.COMPLETED
            export_job.progress = 100
            export_job.completed_at = datetime.now(timezone.utc)
            db.commit()
            
        except Exception as e:
            export_job.status = ExportStatus.FAILED
            export_job.error_message = str(e)
            db.commit()
        finally:
            db.close()
            if export_job_id in self.active_jobs:
                del self.active_jobs[export_job_id]
    
    def _export_images_zip(self, db, export_job: ExportJob, prediction_job_id: int, options: dict):
        """Export images as ZIP file."""
        annotated = options.get('annotated', True)
        result_ids = options.get('result_ids')
        
        # Get results
        query = db.query(PredictionResult).filter(
            PredictionResult.prediction_job_id == prediction_job_id
        )
        if result_ids:
            query = query.filter(PredictionResult.id.in_(result_ids))
        results = query.all()
        
        if not results:
            raise ValueError("No results to export")
        
        # Create export directory
        export_dir = Path(settings.predictions_dir) / "exports"
        export_dir.mkdir(exist_ok=True)
        
        # Create ZIP file
        zip_filename = f"detection_{prediction_job_id}_images_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip"
        zip_path = export_dir / zip_filename
        
        with zipfile.ZipFile(zip_path, 'w') as zipf:
            total = len(results)
            for idx, result in enumerate(results):
                # Load original image
                image_path = Path(settings.predictions_dir) / str(prediction_job_id) / result.file_name
                
                if not image_path.exists():
                    continue
                
                if annotated:
                    # Draw bounding boxes
                    img = cv2.imread(str(image_path))
                    if img is not None:
                        self._draw_boxes_cv2(img, result)
                        
                        # Save to buffer
                        buffer = BytesIO()
                        is_success, buffer_img = cv2.imencode(".jpg", img)
                        if is_success:
                            zipf.writestr(f"annotated_{result.file_name}", buffer.getvalue())
                else:
                    # Add original image
                    zipf.write(image_path, arcname=result.file_name)
                
                # Update progress
                export_job.progress = (idx + 1) / total * 100
                db.commit()
        
        export_job.file_path = str(zip_path)
    
    def _export_data_json(self, db, export_job: ExportJob, prediction_job_id: int, options: dict):
        """Export detection data as JSON."""
        result_ids = options.get('result_ids')
        
        # Get detection job
        job = db.query(PredictionJob).filter(PredictionJob.id == prediction_job_id).first()
        if not job:
            raise ValueError("Detection job not found")
        
        # Get results
        query = db.query(PredictionResult).filter(
            PredictionResult.prediction_job_id == prediction_job_id
        )
        if result_ids:
            query = query.filter(PredictionResult.id.in_(result_ids))
        results = query.all()
        
        # Build JSON structure
        data = {
            "job_id": prediction_job_id,
            "mode": job.mode.value if hasattr(job.mode, 'value') else job.mode,
            "model_id": job.model_id,
            "campaign_id": job.campaign_id,
            "summary": job.summary_json,
            "created_at": job.created_at.isoformat(),
            "results": []
        }
        
        total = len(results)
        for idx, result in enumerate(results):
            data["results"].append({
                "id": result.id,
                "file_name": result.file_name,
                "frame_number": result.frame_number,
                "detections": [
                    {
                        "class": result.class_names_json[i],
                        "confidence": float(result.scores_json[i]),
                        "box": result.boxes_json[i]
                    }
                    for i in range(len(result.boxes_json))
                ]
            })
            
            # Update progress
            export_job.progress = (idx + 1) / total * 100
            db.commit()
        
        # Save JSON
        export_dir = Path(settings.predictions_dir) / "exports"
        export_dir.mkdir(exist_ok=True)
        json_filename = f"detection_{prediction_job_id}_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        json_path = export_dir / json_filename
        
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        export_job.file_path = str(json_path)
    
    def _export_data_csv(self, db, export_job: ExportJob, prediction_job_id: int, options: dict):
        """Export detection data as CSV."""
        result_ids = options.get('result_ids')
        
        # Get results
        query = db.query(PredictionResult).filter(
            PredictionResult.prediction_job_id == prediction_job_id
        )
        if result_ids:
            query = query.filter(PredictionResult.id.in_(result_ids))
        results = query.all()
        
        # Build flat structure for CSV
        rows = []
        total = len(results)
        
        for idx, result in enumerate(results):
            for i in range(len(result.boxes_json)):
                box = result.boxes_json[i]
                rows.append({
                    'result_id': result.id,
                    'file_name': result.file_name,
                    'frame_number': result.frame_number,
                    'class_name': result.class_names_json[i],
                    'confidence': result.scores_json[i],
                    'x1': box[0],
                    'y1': box[1],
                    'x2': box[2],
                    'y2': box[3]
                })
            
            # Update progress
            export_job.progress = (idx + 1) / total * 100
            db.commit()
        
        # Create DataFrame and save
        df = pd.DataFrame(rows)
        export_dir = Path(settings.predictions_dir) / "exports"
        export_dir.mkdir(exist_ok=True)
        csv_filename = f"detection_{prediction_job_id}_data_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        csv_path = export_dir / csv_filename
        
        df.to_csv(csv_path, index=False)
        export_job.file_path = str(csv_path)
    
    def _export_report_pdf(self, db, export_job: ExportJob, prediction_job_id: int, options: dict):
        """Export detection report as PDF."""
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.units import inch
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        import matplotlib.pyplot as plt
        
        result_ids = options.get('result_ids')
        
        # Get detection job
        job = db.query(PredictionJob).filter(PredictionJob.id == prediction_job_id).first()
        if not job:
            raise ValueError("Detection job not found")
        
        # Get results (limit to first 100 to avoid huge PDFs)
        query = db.query(PredictionResult).filter(
            PredictionResult.prediction_job_id == prediction_job_id
        )
        if result_ids:
            query = query.filter(PredictionResult.id.in_(result_ids))
        query = query.limit(100)
        results = query.all()
        
        # Create PDF
        export_dir = Path(settings.predictions_dir) / "exports"
        export_dir.mkdir(exist_ok=True)
        pdf_filename = f"detection_{prediction_job_id}_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = export_dir / pdf_filename
        
        doc = SimpleDocTemplate(str(pdf_path), pagesize=letter)
        story = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], fontSize=24, textColor=colors.HexColor('#1D2F43'), spaceAfter=12, alignment=TA_CENTER)
        story.append(Paragraph(f"Detection Report #{prediction_job_id}", title_style))
        story.append(Spacer(1, 0.3*inch))
        
        # Job metadata
        metadata = [
            ['Mode:', str(job.mode.value if hasattr(job.mode, 'value') else job.mode)],
            ['Status:', str(job.status.value if hasattr(job.status, 'value') else job.status)],
            ['Created:', job.created_at.strftime('%Y-%m-%d %H:%M:%S')],
            ['Total Results:', str(len(results))]
        ]
        
        t = Table(metadata, colWidths=[2*inch, 4*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E1E1E1')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1D2F43')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        story.append(t)
        story.append(Spacer(1, 0.3*inch))
        
        # Summary statistics
        if job.summary_json:
            story.append(Paragraph("Summary Statistics", styles['Heading2']))
            story.append(Spacer(1, 0.1*inch))
            
            summary_data = [
                ['Total Detections:', str(job.summary_json.get('total_detections', 0))],
                ['Average Confidence:', f"{job.summary_json.get('average_confidence', 0) * 100:.1f}%"]
            ]
            
            t = Table(summary_data, colWidths=[2*inch, 4*inch])
            t.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F5F5F5')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1D2F43')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
            ]))
            story.append(t)
            story.append(Spacer(1, 0.2*inch))
            
            # Class breakdown chart
            if 'class_counts' in job.summary_json:
                class_counts = job.summary_json['class_counts']
                if class_counts:
                    fig, ax = plt.subplots(figsize=(6, 4))
                    classes = list(class_counts.keys())
                    counts = list(class_counts.values())
                    ax.bar(classes, counts, color='#E1604C')
                    ax.set_xlabel('Class')
                    ax.set_ylabel('Count')
                    ax.set_title('Detection Class Breakdown')
                    plt.xticks(rotation=45, ha='right')
                    plt.tight_layout()
                    
                    # Save chart to buffer
                    chart_buffer = BytesIO()
                    plt.savefig(chart_buffer, format='png', dpi=100)
                    chart_buffer.seek(0)
                    plt.close()
                    
                    story.append(RLImage(chart_buffer, width=5*inch, height=3.3*inch))
                    story.append(Spacer(1, 0.3*inch))
        
        story.append(PageBreak())
        
        # Check if this is a manual video session (timeline format)
        is_manual_video = (
            job.mode.value == "video" and 
            job.summary_json and 
            job.summary_json.get('capture_mode') == 'manual'
        )
        
        if is_manual_video:
            # Sort results by frame_timestamp or frame_number for timeline view
            sorted_results = sorted(results, key=lambda r: r.frame_timestamp or r.frame_number or 0)
            
            # Timeline-based results
            story.append(Paragraph("Captured Frames Timeline", styles['Heading2']))
            story.append(Spacer(1, 0.2*inch))
            
            # Add session info if available
            if job.summary_json.get('video_filename'):
                story.append(Paragraph(f"<b>Video:</b> {job.summary_json['video_filename']}", styles['Normal']))
            if job.summary_json.get('video_duration'):
                duration = job.summary_json['video_duration']
                story.append(Paragraph(f"<b>Duration:</b> {duration:.2f} seconds", styles['Normal']))
            story.append(Spacer(1, 0.2*inch))
            
            total = len(sorted_results)
            for idx, result in enumerate(sorted_results):
                # Load and annotate image
                image_path = Path(settings.predictions_dir) / str(prediction_job_id) / result.file_name
                
                if image_path.exists():
                    try:
                        img = cv2.imread(str(image_path))
                        if img is not None:
                            # Draw boxes
                            self._draw_boxes_cv2(img, result)
                            
                            # Convert to RGB and save to buffer
                            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                            pil_img = Image.fromarray(img_rgb)
                            
                            # Resize for PDF (max 400px width)
                            max_width = 400
                            if pil_img.width > max_width:
                                ratio = max_width / pil_img.width
                                new_size = (max_width, int(pil_img.height * ratio))
                                pil_img = pil_img.resize(new_size, Image.Resampling.LANCZOS)
                            
                            img_buffer = BytesIO()
                            pil_img.save(img_buffer, format='JPEG', quality=85)
                            img_buffer.seek(0)
                            
                            # Format title with timestamp
                            timestamp_str = result.frame_timestamp if result.frame_timestamp else f"Frame {result.frame_number}"
                            detection_count = len(result.boxes_json)
                            
                            # Build detailed detection summary with confidence
                            detection_details = []
                            if detection_count > 0 and result.class_names_json and result.scores_json:
                                # Group by class and calculate average confidence
                                class_detections = {}
                                for class_name, score in zip(result.class_names_json, result.scores_json):
                                    if class_name not in class_detections:
                                        class_detections[class_name] = []
                                    class_detections[class_name].append(score)
                                
                                # Format as "class: count (avg_conf%)"
                                for class_name, scores in class_detections.items():
                                    avg_conf = sum(scores) / len(scores) * 100
                                    detection_details.append(f"{class_name}: {len(scores)} ({avg_conf:.1f}%)")
                            
                            # Add to PDF with timeline format
                            title_text = f"<b>Frame at {timestamp_str}</b> - {detection_count} detection(s)"
                            if detection_details:
                                title_text += f" [{', '.join(detection_details)}]"
                            
                            story.append(Paragraph(title_text, styles['Normal']))
                            story.append(Spacer(1, 0.1*inch))
                            story.append(RLImage(img_buffer, width=4*inch, height=4*inch * pil_img.height / pil_img.width))
                            story.append(Spacer(1, 0.2*inch))
                            
                            # Add page break every 2 images
                            if (idx + 1) % 2 == 0 and idx < total - 1:
                                story.append(PageBreak())
                    except Exception as e:
                        print(f"Error processing image {result.file_name}: {e}")
        else:
            # Standard results grid (for non-manual video modes)
            story.append(Paragraph("Detection Results", styles['Heading2']))
            story.append(Spacer(1, 0.2*inch))
            
            total = len(results)
            for idx, result in enumerate(results):
                # Load and annotate image
                image_path = Path(settings.predictions_dir) / str(prediction_job_id) / result.file_name
                
                if image_path.exists():
                    try:
                        img = cv2.imread(str(image_path))
                        if img is not None:
                            # Draw boxes
                            self._draw_boxes_cv2(img, result)
                            
                            # Convert to RGB and save to buffer
                            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                            pil_img = Image.fromarray(img_rgb)
                            
                            # Resize for PDF (max 400px width)
                            max_width = 400
                            if pil_img.width > max_width:
                                ratio = max_width / pil_img.width
                                new_size = (max_width, int(pil_img.height * ratio))
                                pil_img = pil_img.resize(new_size, Image.Resampling.LANCZOS)
                            
                            img_buffer = BytesIO()
                            pil_img.save(img_buffer, format='JPEG', quality=85)
                            img_buffer.seek(0)
                            
                            # Build detailed detection summary with confidence
                            detection_count = len(result.boxes_json)
                            detection_details = []
                            if detection_count > 0 and result.class_names_json and result.scores_json:
                                # Group by class and calculate average confidence
                                class_detections = {}
                                for class_name, score in zip(result.class_names_json, result.scores_json):
                                    if class_name not in class_detections:
                                        class_detections[class_name] = []
                                    class_detections[class_name].append(score)
                                
                                # Format as "class: count (avg_conf%)"
                                for class_name, scores in class_detections.items():
                                    avg_conf = sum(scores) / len(scores) * 100
                                    detection_details.append(f"{class_name}: {len(scores)} ({avg_conf:.1f}%)")
                            
                            # Add to PDF
                            title_text = f"<b>{result.file_name}</b> - {detection_count} detection(s)"
                            if detection_details:
                                title_text += f" [{', '.join(detection_details)}]"
                            
                            story.append(Paragraph(title_text, styles['Normal']))
                            story.append(Spacer(1, 0.1*inch))
                            story.append(RLImage(img_buffer, width=4*inch, height=4*inch * pil_img.height / pil_img.width))
                            story.append(Spacer(1, 0.2*inch))
                            
                            # Add page break every 2 images
                            if (idx + 1) % 2 == 0 and idx < total - 1:
                                story.append(PageBreak())
                    except Exception as e:
                        print(f"Error processing image {result.file_name}: {e}")
            
            # Update progress
            export_job.progress = (idx + 1) / total * 100
            db.commit()
        
        # Build PDF
        doc.build(story)
        export_job.file_path = str(pdf_path)
    
    def _export_single_result_pdf(self, db, export_job: ExportJob, prediction_job_id: int, options: dict):
        """Export single detection result as PDF with original and annotated images."""
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage, PageBreak
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        
        result_id = options.get('result_id')
        if not result_id:
            raise ValueError("result_id is required")
        
        # Get detection result
        result = db.query(PredictionResult).filter(
            PredictionResult.id == result_id
        ).first()
        
        if not result:
            raise ValueError("Detection result not found")
        
        # Get detection job
        job = db.query(PredictionJob).filter(PredictionJob.id == prediction_job_id).first()
        if not job:
            raise ValueError("Detection job not found")
        
        # Create PDF
        export_dir = Path(settings.predictions_dir) / "exports"
        export_dir.mkdir(exist_ok=True)
        pdf_filename = f"detection_result_{result_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = export_dir / pdf_filename
        
        doc = SimpleDocTemplate(str(pdf_path), pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
        story = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], 
                                    fontSize=20, textColor=colors.HexColor('#1D2F43'), 
                                    spaceAfter=12, alignment=TA_CENTER)
        story.append(Paragraph(f"Detection Result Report", title_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Metadata table
        metadata = [
            ['File Name:', result.file_name],
            ['Detection Job ID:', str(job.id)],
            ['Mode:', str(job.mode.value if hasattr(job.mode, 'value') else job.mode)],
            ['Total Detections:', str(len(result.boxes_json))],
            ['Created:', job.created_at.strftime('%Y-%m-%d %H:%M:%S')]
        ]
        
        if result.frame_number is not None:
            metadata.insert(1, ['Frame Number:', str(result.frame_number)])
        
        t = Table(metadata, colWidths=[2*inch, 4*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E1E1E1')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1D2F43')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        story.append(t)
        story.append(Spacer(1, 0.3*inch))
        
        # Original Image
        image_path = Path(settings.predictions_dir) / str(job.id) / result.file_name
        if image_path.exists():
            story.append(Paragraph("<b>Original Image</b>", styles['Heading2']))
            story.append(Spacer(1, 0.1*inch))
            
            img = cv2.imread(str(image_path))
            if img is not None:
                # Resize to fit page width
                max_width = 6 * inch
                height, width = img.shape[:2]
                aspect = height / width
                img_width = min(width, max_width)
                img_height = img_width * aspect
                
                # Convert to PIL
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(img_rgb)
                img_buffer = BytesIO()
                pil_img.save(img_buffer, format='PNG')
                img_buffer.seek(0)
                
                story.append(RLImage(img_buffer, width=img_width, height=img_height))
                story.append(Spacer(1, 0.3*inch))
        
        # Annotated Image
        if image_path.exists():
            story.append(Paragraph("<b>Annotated Image (with Detections)</b>", styles['Heading2']))
            story.append(Spacer(1, 0.1*inch))
            
            img = cv2.imread(str(image_path))
            if img is not None:
                # Draw boxes
                annotated_img = img.copy()
                self._draw_boxes_cv2(annotated_img, result)
                
                # Resize to fit page width
                max_width = 6 * inch
                height, width = annotated_img.shape[:2]
                aspect = height / width
                img_width = min(width, max_width)
                img_height = img_width * aspect
                
                # Convert to PIL
                img_rgb = cv2.cvtColor(annotated_img, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(img_rgb)
                img_buffer = BytesIO()
                pil_img.save(img_buffer, format='PNG')
                img_buffer.seek(0)
                
                story.append(RLImage(img_buffer, width=img_width, height=img_height))
                story.append(Spacer(1, 0.3*inch))
        
        # Detection Details Table
        if len(result.boxes_json) > 0:
            story.append(Paragraph("<b>Detection Details</b>", styles['Heading2']))
            story.append(Spacer(1, 0.1*inch))
            
            # Create detection table
            detection_data = [['#', 'Class', 'Confidence', 'Bounding Box (x1, y1, x2, y2)']]
            for i in range(len(result.boxes_json)):
                box = result.boxes_json[i]
                class_name = result.class_names_json[i]
                score = result.scores_json[i]
                box_str = f"({int(box[0])}, {int(box[1])}, {int(box[2])}, {int(box[3])})"
                detection_data.append([
                    str(i + 1),
                    class_name,
                    f"{score * 100:.1f}%",
                    box_str
                ])
            
            det_table = Table(detection_data, colWidths=[0.5*inch, 1.5*inch, 1*inch, 3*inch])
            det_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1D2F43')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
            ]))
            story.append(det_table)
            story.append(Spacer(1, 0.2*inch))
            
            # Summary statistics
            class_counts = {}
            for class_name in result.class_names_json:
                class_counts[class_name] = class_counts.get(class_name, 0) + 1
            
            avg_confidence = sum(result.scores_json) / len(result.scores_json) if result.scores_json else 0
            
            summary_data = [
                ['Total Detections:', str(len(result.boxes_json))],
                ['Average Confidence:', f"{avg_confidence * 100:.1f}%"],
                ['Unique Classes:', str(len(class_counts))]
            ]
            
            for class_name, count in sorted(class_counts.items(), key=lambda x: x[1], reverse=True):
                summary_data.append([f"  {class_name}:", str(count)])
            
            summary_table = Table(summary_data, colWidths=[2*inch, 2*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E1E1E1')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1D2F43')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, 2), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
            ]))
            story.append(Paragraph("<b>Summary</b>", styles['Heading2']))
            story.append(Spacer(1, 0.1*inch))
            story.append(summary_table)
        
        # Build PDF
        doc.build(story)
        export_job.file_path = str(pdf_path)
    
    def _export_single_result_pdf(self, db, export_job: ExportJob, prediction_job_id: int, options: dict):
        """Export single detection result as PDF with original and annotated images."""
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, Image as RLImage
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import inch
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER
        
        result_id = options.get('result_id')
        if not result_id:
            raise ValueError("result_id is required")
        
        # Get detection result
        result = db.query(PredictionResult).filter(
            PredictionResult.id == result_id
        ).first()
        
        if not result:
            raise ValueError("Detection result not found")
        
        # Get detection job
        job = db.query(PredictionJob).filter(PredictionJob.id == prediction_job_id).first()
        if not job:
            raise ValueError("Detection job not found")
        
        # Create PDF
        export_dir = Path(settings.predictions_dir) / "exports"
        export_dir.mkdir(exist_ok=True)
        pdf_filename = f"detection_result_{result_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.pdf"
        pdf_path = export_dir / pdf_filename
        
        doc = SimpleDocTemplate(str(pdf_path), pagesize=letter, topMargin=0.5*inch, bottomMargin=0.5*inch)
        story = []
        styles = getSampleStyleSheet()
        
        # Title
        title_style = ParagraphStyle('CustomTitle', parent=styles['Heading1'], 
                                    fontSize=20, textColor=colors.HexColor('#1D2F43'), 
                                    spaceAfter=12, alignment=TA_CENTER)
        story.append(Paragraph(f"Detection Result Report", title_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Metadata table
        metadata = [
            ['File Name:', result.file_name],
            ['Detection Job ID:', str(job.id)],
            ['Mode:', str(job.mode.value if hasattr(job.mode, 'value') else job.mode)],
            ['Total Detections:', str(len(result.boxes_json))],
            ['Created:', job.created_at.strftime('%Y-%m-%d %H:%M:%S')]
        ]
        
        if result.frame_number is not None:
            metadata.insert(1, ['Frame Number:', str(result.frame_number)])
        
        t = Table(metadata, colWidths=[2*inch, 4*inch])
        t.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E1E1E1')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1D2F43')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
            ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
        ]))
        story.append(t)
        story.append(Spacer(1, 0.3*inch))
        
        # Original Image
        image_path = Path(settings.predictions_dir) / str(job.id) / result.file_name
        if image_path.exists():
            story.append(Paragraph("<b>Original Image</b>", styles['Heading2']))
            story.append(Spacer(1, 0.1*inch))
            
            img = cv2.imread(str(image_path))
            if img is not None:
                # Resize to fit page width
                max_width = 6 * inch
                height, width = img.shape[:2]
                aspect = height / width
                img_width = min(width, max_width)
                img_height = img_width * aspect
                
                # Convert to PIL
                img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(img_rgb)
                img_buffer = BytesIO()
                pil_img.save(img_buffer, format='PNG')
                img_buffer.seek(0)
                
                story.append(RLImage(img_buffer, width=img_width, height=img_height))
                story.append(Spacer(1, 0.3*inch))
        
        # Annotated Image
        if image_path.exists():
            story.append(Paragraph("<b>Annotated Image (with Detections)</b>", styles['Heading2']))
            story.append(Spacer(1, 0.1*inch))
            
            img = cv2.imread(str(image_path))
            if img is not None:
                # Draw boxes
                annotated_img = img.copy()
                self._draw_boxes_cv2(annotated_img, result)
                
                # Resize to fit page width
                max_width = 6 * inch
                height, width = annotated_img.shape[:2]
                aspect = height / width
                img_width = min(width, max_width)
                img_height = img_width * aspect
                
                # Convert to PIL
                img_rgb = cv2.cvtColor(annotated_img, cv2.COLOR_BGR2RGB)
                pil_img = Image.fromarray(img_rgb)
                img_buffer = BytesIO()
                pil_img.save(img_buffer, format='PNG')
                img_buffer.seek(0)
                
                story.append(RLImage(img_buffer, width=img_width, height=img_height))
                story.append(Spacer(1, 0.3*inch))
        
        # Detection Details Table
        if len(result.boxes_json) > 0:
            story.append(Paragraph("<b>Detection Details</b>", styles['Heading2']))
            story.append(Spacer(1, 0.1*inch))
            
            # Create detection table
            detection_data = [['#', 'Class', 'Confidence', 'Bounding Box (x1, y1, x2, y2)']]
            for i in range(len(result.boxes_json)):
                box = result.boxes_json[i]
                class_name = result.class_names_json[i]
                score = result.scores_json[i]
                box_str = f"({int(box[0])}, {int(box[1])}, {int(box[2])}, {int(box[3])})"
                detection_data.append([
                    str(i + 1),
                    class_name,
                    f"{score * 100:.1f}%",
                    box_str
                ])
            
            det_table = Table(detection_data, colWidths=[0.5*inch, 1.5*inch, 1*inch, 3*inch])
            det_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#1D2F43')),
                ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, 0), 10),
                ('BOTTOMPADDING', (0, 0), (-1, 0), 8),
                ('BACKGROUND', (0, 1), (-1, -1), colors.beige),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
                ('FONTSIZE', (0, 1), (-1, -1), 8),
                ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.lightgrey])
            ]))
            story.append(det_table)
            story.append(Spacer(1, 0.2*inch))
            
            # Summary statistics
            class_counts = {}
            for class_name in result.class_names_json:
                class_counts[class_name] = class_counts.get(class_name, 0) + 1
            
            avg_confidence = sum(result.scores_json) / len(result.scores_json) if result.scores_json else 0
            
            summary_data = [
                ['Total Detections:', str(len(result.boxes_json))],
                ['Average Confidence:', f"{avg_confidence * 100:.1f}%"],
                ['Unique Classes:', str(len(class_counts))]
            ]
            
            for class_name, count in sorted(class_counts.items(), key=lambda x: x[1], reverse=True):
                summary_data.append([f"  {class_name}:", str(count)])
            
            summary_table = Table(summary_data, colWidths=[2*inch, 2*inch])
            summary_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#E1E1E1')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1D2F43')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, 2), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
                ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
            ]))
            story.append(Paragraph("<b>Summary</b>", styles['Heading2']))
            story.append(Spacer(1, 0.1*inch))
            story.append(summary_table)
        
        # Build PDF
        doc.build(story)
        export_job.file_path = str(pdf_path)
    
    def _draw_boxes_cv2(self, img, result: PredictionResult):
        """Draw bounding boxes on image using OpenCV."""
        for i in range(len(result.boxes_json)):
            box = result.boxes_json[i]
            class_name = result.class_names_json[i]
            score = result.scores_json[i]
            
            # Draw rectangle
            x1, y1, x2, y2 = [int(coord) for coord in box]
            cv2.rectangle(img, (x1, y1), (x2, y2), (225, 96, 76), 2)  # #E1604C in BGR
            
            # Draw label
            label = f"{class_name} {score:.2f}"
            label_size, _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 1)
            label_y = max(y1 - 10, label_size[1] + 10)
            
            cv2.rectangle(img, (x1, label_y - label_size[1] - 10), (x1 + label_size[0], label_y), (225, 96, 76), -1)
            cv2.putText(img, label, (x1, label_y - 5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)


# Singleton instance
export_worker = ExportWorker()
