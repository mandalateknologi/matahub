"""
Campaign Export Worker

Background worker for generating comprehensive campaign reports (mega-PDFs and data archives).
"""
import threading
import zipfile
import json
from datetime import datetime
from typing import Dict, List, Tuple
from pathlib import Path
from io import BytesIO
import cv2
from PIL import Image

from app.db import SessionLocal
from app.models.campaign import Campaign, CampaignExport, CampaignExportStatus, CampaignExportType
from app.models.prediction_job import PredictionJob as DetectionJob
from app.models.prediction_result import PredictionResult as DetectionResultModel
from app.services.campaign_stats import calculate_campaign_stats
from app.config import settings

# ReportLab imports for PDF generation
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER
from reportlab.lib import colors
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, PageBreak,
    Table, TableStyle, Image as RLImage
)

# Matplotlib for charts
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt


class CampaignExportWorker:
    """Worker for processing Campaign Export jobs in background threads."""
    
    def __init__(self):
        self.active_exports: Dict[int, threading.Thread] = {}
    
    def start_export(self, export_id: int) -> bool:
        """
        Start a Campaign Export job in a background thread.
        
        Args:
            export_id: CampaignExport ID to process
            
        Returns:
            True if export started successfully, False otherwise
        """
        if export_id in self.active_exports:
            return False
        
        thread = threading.Thread(
            target=self._process_export,
            args=(export_id,),
            daemon=True
        )
        self.active_exports[export_id] = thread
        thread.start()
        return True
    
    def _process_export(self, export_id: int):
        """
        Process a Campaign Export job (runs in background thread).
        
        Generates comprehensive campaign reports with all job results,
        aggregate statistics, and visualizations.
        
        Args:
            export_id: CampaignExport ID to process
        """
        db = SessionLocal()
        
        try:
            # Get export job
            export_job = db.query(CampaignExport).filter(CampaignExport.id == export_id).first()
            if not export_job:
                return
            
            # Update status to processing
            export_job.status = CampaignExportStatus.PROCESSING
            export_job.progress = 0
            db.commit()
            
            # Route to appropriate export handler
            if export_job.export_type == CampaignExportType.MEGA_REPORT_PDF:
                self._export_mega_pdf(db, export_job)
            elif export_job.export_type == CampaignExportType.MEGA_DATA_ZIP:
                self._export_mega_zip(db, export_job)
            
            # Mark as completed
            export_job.status = CampaignExportStatus.COMPLETED
            export_job.progress = 100
            export_job.completed_at = datetime.utcnow()
            db.commit()
            
        except Exception as e:
            # Mark as failed
            try:
                export_job.status = CampaignExportStatus.FAILED
                export_job.config_json = {
                    **export_job.config_json,
                    "error": str(e)
                }
                db.commit()
            except:
                pass
        
        finally:
            db.close()
            # Remove from active exports
            if export_id in self.active_exports:
                del self.active_exports[export_id]
    
    def _query_results_paginated(self, db, campaign_id: int, chunk_size: int = 100):
        """
        Query detection results in paginated chunks to avoid memory issues.
        
        Args:
            db: Database campaign
            campaign_id: campaign ID to query results for
            chunk_size: Number of results per chunk
            
        Yields:
            Tuples of (job, results_list)
        """
        # Get all jobs in campaign
        jobs = db.query(DetectionJob).filter(
            DetectionJob.campaign_id == campaign_id
        ).all()
        
        for job in jobs:
            # Query results for this job in chunks
            offset = 0
            while True:
                results = db.query(DetectionResultModel).filter(
                    DetectionResultModel.prediction_job_id == job.id
                ).offset(offset).limit(chunk_size).all()
                
                if not results:
                    break
                
                yield (job, results)
                offset += chunk_size
    
    def _sample_top_confidence(self, db, campaign_id: int, max_results: int = 500) -> List[Tuple[DetectionJob, List[DetectionResultModel]]]:
        """
        Sample top detection results by confidence across all jobs.
        
        Args:
            db: Database campaign
            campaign_id: campaign ID
            max_results: Maximum number of results to return
            
        Returns:
            List of (job, results) tuples with top confidence results
        """
        # Collect all results with their average confidence
        all_results = []
        
        jobs = db.query(DetectionJob).filter(
            DetectionJob.campaign_id == campaign_id
        ).all()
        
        for job in jobs:
            results = db.query(DetectionResultModel).filter(
                DetectionResultModel.prediction_job_id == job.id
            ).all()
            
            for result in results:
                # Calculate average confidence for this result
                if result.scores_json and len(result.scores_json) > 0:
                    avg_conf = sum(result.scores_json) / len(result.scores_json)
                    all_results.append((job, result, avg_conf))
        
        # Sort by confidence descending
        all_results.sort(key=lambda x: x[2], reverse=True)
        
        # Take top N results
        top_results = all_results[:max_results]
        
        # Group by job
        job_results_map = {}
        for job, result, conf in top_results:
            if job.id not in job_results_map:
                job_results_map[job.id] = (job, [])
            job_results_map[job.id][1].append(result)
        
        return list(job_results_map.values())
    
    def _draw_boxes_cv2(self, img, result: DetectionResultModel):
        """
        Draw bounding boxes on image using OpenCV.
        Reused from ExportWorker pattern.
        
        Args:
            img: OpenCV image (numpy array)
            result: DetectionResult with boxes, scores, classes
        """
        if not result.boxes_json or not result.class_names_json:
            return
        
        # Color palette (Navy and Accent)
        colors_palette = [
            (225, 96, 76),    # Accent color
            (29, 47, 67),     # Navy color
            (115, 122, 127),  # Grey
        ]
        
        for i, box in enumerate(result.boxes_json):
            if i >= len(result.class_names_json):
                break
            
            class_name = result.class_names_json[i]
            confidence = result.scores_json[i] if result.scores_json and i < len(result.scores_json) else 0.0
            
            # Draw box
            x1, y1, x2, y2 = map(int, box)
            color = colors_palette[i % len(colors_palette)]
            cv2.rectangle(img, (x1, y1), (x2, y2), color, 2)
            
            # Draw label background
            label = f"{class_name}: {confidence:.2f}"
            font_scale = 0.5
            thickness = 1
            (label_width, label_height), baseline = cv2.getTextSize(
                label, cv2.FONT_HERSHEY_SIMPLEX, font_scale, thickness
            )
            
            cv2.rectangle(
                img,
                (x1, y1 - label_height - baseline - 5),
                (x1 + label_width, y1),
                color,
                -1
            )
            
            # Draw label text
            cv2.putText(
                img,
                label,
                (x1, y1 - baseline - 2),
                cv2.FONT_HERSHEY_SIMPLEX,
                font_scale,
                (255, 255, 255),
                thickness
            )
    
    def _export_mega_pdf(self, db, export_job: CampaignExport):
        """
        Generate comprehensive PDF report for entire campaign.
        
        Args:
            db: Database campaign
            export_job: CampaignExport job
        """
        # Get campaign
        campaign = db.query(Campaign).filter(
            Campaign.id == export_job.campaign_id
        ).first()
        
        if not campaign:
            raise ValueError(f"campaign {export_job.campaign_id} not found")
        
        # Calculate campaign statistics
        stats = calculate_campaign_stats(campaign.id, db)
        
        # Update progress: 10% - stats calculated
        export_job.progress = 10
        db.commit()
        
        # Create export directory
        export_dir = Path(settings.predictions_dir) / "exports"
        export_dir.mkdir(exist_ok=True)
        
        # Create PDF file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        pdf_filename = f"campaign_{campaign.id}_report_{timestamp}.pdf"
        pdf_path = export_dir / pdf_filename
        
        doc = SimpleDocTemplate(
            str(pdf_path),
            pagesize=letter,
            rightMargin=0.75*inch,
            leftMargin=0.75*inch,
            topMargin=0.75*inch,
            bottomMargin=0.75*inch
        )
        
        story = []
        styles = getSampleStyleSheet()
        
        # Custom styles
        title_style = ParagraphStyle(
            'CustomTitle',
            parent=styles['Heading1'],
            fontSize=24,
            textColor=colors.HexColor('#1D2F43'),  # Navy
            spaceAfter=30,
            alignment=TA_CENTER
        )
        
        heading_style = ParagraphStyle(
            'CustomHeading',
            parent=styles['Heading2'],
            fontSize=16,
            textColor=colors.HexColor('#1D2F43'),
            spaceAfter=12
        )
        
        # Title Page
        story.append(Spacer(1, 1*inch))
        story.append(Paragraph("Campaign Report", title_style))
        story.append(Spacer(1, 0.3*inch))
        story.append(Paragraph(f"<b>{campaign.name}</b>", styles['Heading2']))
        
        if campaign.description:
            story.append(Spacer(1, 0.2*inch))
            story.append(Paragraph(campaign.description, styles['Normal']))
        
        story.append(Spacer(1, 0.5*inch))
        
        # campaign metadata table
        metadata = [
            ['Playbook:', campaign.playbook.name if campaign.playbook else 'N/A'],
            ['Creator:', campaign.creator.email if campaign.creator else 'N/A'],
            ['Created:', campaign.created_at.strftime('%Y-%m-%d %H:%M:%S')],
            ['Status:', campaign.status.value.upper()],
        ]
        
        if campaign.ended_at:
            metadata.append(['Ended:', campaign.ended_at.strftime('%Y-%m-%d %H:%M:%S')])
        
        metadata_table = Table(metadata, colWidths=[2*inch, 4*inch])
        metadata_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F0F0F0')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1D2F43')),
            ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTSIZE', (0, 0), (-1, -1), 10),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
            ('TOPPADDING', (0, 0), (-1, -1), 8),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#D0D0D0'))
        ]))
        story.append(metadata_table)
        
        # Custom fields if present
        if campaign.summary_json and 'custom_fields' in campaign.summary_json:
            custom_fields = campaign.summary_json['custom_fields']
            if custom_fields:
                story.append(Spacer(1, 0.3*inch))
                story.append(Paragraph("<b>Additional Information</b>", styles['Heading3']))
                
                custom_data = [[k, v] for k, v in custom_fields.items()]
                custom_table = Table(custom_data, colWidths=[2*inch, 4*inch])
                custom_table.setStyle(TableStyle([
                    ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F0F0F0')),
                    ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1D2F43')),
                    ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                    ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                    ('FONTSIZE', (0, 0), (-1, -1), 9),
                    ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                    ('TOPPADDING', (0, 0), (-1, -1), 6),
                    ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#D0D0D0'))
                ]))
                story.append(custom_table)
        
        story.append(PageBreak())
        
        # Update progress: 20% - title page complete
        export_job.progress = 20
        db.commit()
        
        # Executive Summary
        story.append(Paragraph("Executive Summary", heading_style))
        story.append(Spacer(1, 0.2*inch))
        
        summary_data = [
            ['Total Jobs', str(stats.get('total_jobs', 0))],
            ['Completed Jobs', str(stats.get('completed_jobs', 0))],
            ['Running Jobs', str(stats.get('running_jobs', 0))],
            ['Failed Jobs', str(stats.get('failed_jobs', 0))],
            ['Total Detections', str(stats.get('total_detections', 0))],
            ['Average Confidence', f"{stats.get('average_confidence', 0) * 100:.1f}%"],
        ]
        
        summary_table = Table(summary_data, colWidths=[3*inch, 2*inch])
        summary_table.setStyle(TableStyle([
            ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#F8F9FA')),
            ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1D2F43')),
            ('ALIGN', (0, 0), (0, -1), 'LEFT'),
            ('ALIGN', (1, 0), (1, -1), 'RIGHT'),
            ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
            ('FONTNAME', (1, 0), (1, -1), 'Helvetica'),
            ('FONTSIZE', (0, 0), (-1, -1), 11),
            ('BOTTOMPADDING', (0, 0), (-1, -1), 10),
            ('TOPPADDING', (0, 0), (-1, -1), 10),
            ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#D0D0D0'))
        ]))
        story.append(summary_table)
        story.append(Spacer(1, 0.3*inch))
        
        # Class Distribution Chart
        class_counts = stats.get('class_counts', {})
        if class_counts:
            story.append(Paragraph("Class Distribution", heading_style))
            story.append(Spacer(1, 0.2*inch))
            
            # Create matplotlib chart
            fig, ax = plt.subplots(figsize=(6, 4))
            classes = list(class_counts.keys())
            counts = list(class_counts.values())
            
            ax.bar(classes, counts, color='#E1604C')  # Accent color
            ax.set_xlabel('Class', fontsize=10)
            ax.set_ylabel('Count', fontsize=10)
            ax.set_title('Detections by Class', fontsize=12, fontweight='bold')
            plt.xticks(rotation=45, ha='right')
            plt.tight_layout()
            
            # Save to buffer
            chart_buffer = BytesIO()
            plt.savefig(chart_buffer, format='png', dpi=100)
            chart_buffer.seek(0)
            plt.close()
            
            story.append(RLImage(chart_buffer, width=5*inch, height=3.3*inch))
            story.append(Spacer(1, 0.3*inch))
        
        story.append(PageBreak())
        
        # Update progress: 30% - summary complete
        export_job.progress = 30
        db.commit()
        
        # Per-Job Sections with top results
        story.append(Paragraph("Job Details", heading_style))
        story.append(Spacer(1, 0.2*inch))
        
        # Sample top confidence results (max 500 across all jobs)
        config = export_job.config_json or {}
        max_images = config.get('max_images', 500)
        job_results = self._sample_top_confidence(db, campaign.id, max_images)
        
        page_count = 0
        max_pages = 200
        
        for idx, (job, results) in enumerate(job_results):
            if page_count >= max_pages:
                story.append(Paragraph(
                    f"<i>Report limited to {max_pages} pages. {len(job_results) - idx} more jobs not shown.</i>",
                    styles['Normal']
                ))
                break
            
            # Job header
            story.append(Paragraph(f"Job #{job.id} - {job.mode.value.upper()}", styles['Heading3']))
            
            # Job metadata
            job_meta = [
                ['Source:', job.source_ref or 'N/A'],
                ['Status:', job.status.value.upper()],
                ['Created:', job.created_at.strftime('%Y-%m-%d %H:%M:%S')],
            ]
            
            if job.summary_json:
                job_summary = job.summary_json
                if 'total_detections' in job_summary:
                    job_meta.append(['Total Detections:', str(job_summary['total_detections'])])
                if 'average_confidence' in job_summary:
                    job_meta.append(['Avg Confidence:', f"{job_summary['average_confidence'] * 100:.1f}%"])
            
            job_table = Table(job_meta, colWidths=[2*inch, 4*inch])
            job_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (0, -1), colors.HexColor('#F0F0F0')),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.HexColor('#1D2F43')),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 9),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 6),
                ('TOPPADDING', (0, 0), (-1, -1), 6),
                ('GRID', (0, 0), (-1, -1), 1, colors.HexColor('#D0D0D0'))
            ]))
            story.append(job_table)
            story.append(Spacer(1, 0.2*inch))
            
            # Add top 5 images for this job
            for i, result in enumerate(results[:5]):
                image_path = Path(settings.predictions_dir) / str(job.id) / result.file_name
                
                if image_path.exists():
                    try:
                        # Load and annotate image
                        img = cv2.imread(str(image_path))
                        if img is not None:
                            self._draw_boxes_cv2(img, result)
                            
                            # Convert to RGB
                            img_rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
                            pil_img = Image.fromarray(img_rgb)
                            
                            # Resize for PDF
                            max_width = 400
                            if pil_img.width > max_width:
                                ratio = max_width / pil_img.width
                                new_size = (max_width, int(pil_img.height * ratio))
                                pil_img = pil_img.resize(new_size, Image.Resampling.LANCZOS)
                            
                            img_buffer = BytesIO()
                            pil_img.save(img_buffer, format='JPEG', quality=85)
                            img_buffer.seek(0)
                            
                            # Add to PDF
                            detection_count = len(result.boxes_json) if result.boxes_json else 0
                            story.append(Paragraph(
                                f"<b>{result.file_name}</b> - {detection_count} detection(s)",
                                styles['Normal']
                            ))
                            story.append(Spacer(1, 0.1*inch))
                            story.append(RLImage(img_buffer, width=4*inch, height=4*inch * pil_img.height / pil_img.width))
                            story.append(Spacer(1, 0.2*inch))
                            page_count += 0.5  # Rough page count estimate
                    except Exception as e:
                        print(f"Error processing image {result.file_name}: {e}")
            
            if len(results) > 5:
                story.append(Paragraph(
                    f"<i>+{len(results) - 5} more result(s) for this job</i>",
                    styles['Normal']
                ))
            
            story.append(PageBreak())
            page_count += 1
            
            # Update progress: 30% + (idx / total * 60%)
            progress = 30 + int((idx + 1) / len(job_results) * 60)
            export_job.progress = min(progress, 90)
            db.commit()
        
        # Build PDF
        doc.build(story)
        
        export_job.file_path = str(pdf_path)
        export_job.progress = 95
        db.commit()
    
    def _export_mega_zip(self, db, export_job: CampaignExport):
        """
        Generate comprehensive ZIP archive with all campaign data.
        
        Args:
            db: Database campaign
            export_job: CampaignExport job
        """
        # Get campaign
        campaign = db.query(Campaign).filter(
            Campaign.id == export_job.campaign_id
        ).first()
        
        if not campaign:
            raise ValueError(f"campaign {export_job.campaign_id} not found")
        
        # Calculate campaign statistics
        stats = calculate_campaign_stats(campaign.id, db)
        
        # Update progress: 10%
        export_job.progress = 10
        db.commit()
        
        # Create export directory
        export_dir = Path(settings.predictions_dir) / "exports"
        export_dir.mkdir(exist_ok=True)
        
        # Create ZIP file
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        zip_filename = f"campaign_{campaign.id}_data_{timestamp}.zip"
        zip_path = export_dir / zip_filename
        
        total_size = 0
        max_size = 1 * 1024 * 1024 * 1024  # 1GB warning threshold
        
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
            # Add campaign summary JSON
            summary_json = {
                'campaign': {
                    'id': campaign.id,
                    'name': campaign.name,
                    'description': campaign.description,
                    'playbook_name': campaign.playbook.name if campaign.playbook else None,
                    'status': campaign.status.value,
                    'created_at': campaign.created_at.isoformat(),
                    'ended_at': campaign.ended_at.isoformat() if campaign.ended_at else None,
                },
                'statistics': stats,
                'custom_fields': campaign.summary_json.get('custom_fields', {}) if campaign.summary_json else {}
            }
            
            zipf.writestr(
                f"campaign_{campaign.id}/summary.json",
                json.dumps(summary_json, indent=2)
            )
            
            export_job.progress = 20
            db.commit()
            
            # Get all jobs
            jobs = db.query(DetectionJob).filter(
                DetectionJob.campaign_id == campaign.id
            ).all()
            
            for idx, job in enumerate(jobs):
                job_dir = f"campaign_{campaign.id}/job_{job.id}"
                
                # Get results for this job
                results = db.query(DetectionResultModel).filter(
                    DetectionResultModel.prediction_job_id == job.id
                ).all()
                
                # Export job data as JSON
                job_data = {
                    'job_id': job.id,
                    'mode': job.mode.value,
                    'source_ref': job.source_ref,
                    'status': job.status.value,
                    'created_at': job.created_at.isoformat(),
                    'summary': job.summary_json,
                    'results': []
                }
                
                # Add results data
                for result in results:
                    result_data = {
                        'id': result.id,
                        'file_name': result.file_name,
                        'frame_number': result.frame_number,
                        'frame_timestamp': result.frame_timestamp,
                        'task_type': result.task_type,
                        'detections': []
                    }
                    
                    if result.boxes_json and result.class_names_json and result.scores_json:
                        for i in range(len(result.boxes_json)):
                            result_data['detections'].append({
                                'class': result.class_names_json[i] if i < len(result.class_names_json) else None,
                                'confidence': result.scores_json[i] if i < len(result.scores_json) else None,
                                'box': result.boxes_json[i]
                            })
                    
                    job_data['results'].append(result_data)
                
                zipf.writestr(
                    f"{job_dir}/data.json",
                    json.dumps(job_data, indent=2)
                )
                
                # Add annotated images
                for result in results:
                    image_path = Path(settings.predictions_dir) / str(job.id) / result.file_name
                    
                    if image_path.exists():
                        try:
                            # Load and annotate
                            img = cv2.imread(str(image_path))
                            if img is not None:
                                self._draw_boxes_cv2(img, result)
                                
                                # Encode as JPEG
                                is_success, buffer = cv2.imencode('.jpg', img, [cv2.IMWRITE_JPEG_QUALITY, 85])
                                if is_success:
                                    zipf.writestr(
                                        f"{job_dir}/images/{result.file_name}",
                                        buffer.tobytes()
                                    )
                                    total_size += len(buffer.tobytes())
                        except Exception as e:
                            print(f"Error processing image {result.file_name}: {e}")
                
                # Update progress: 20% + (idx / total * 70%)
                progress = 20 + int((idx + 1) / len(jobs) * 70)
                export_job.progress = min(progress, 90)
                db.commit()
        
        # Check total size
        actual_size = zip_path.stat().st_size
        if actual_size > max_size:
            print(f"WARNING: Export ZIP size ({actual_size / 1024 / 1024:.1f}MB) exceeds 1GB threshold")
        
        export_job.file_path = str(zip_path)
        export_job.progress = 95
        db.commit()


# Global worker instance
campaign_export_worker = CampaignExportWorker()

