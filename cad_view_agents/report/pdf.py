"""
PDF renderer for engineering reports using reportlab.
"""
import os
from typing import List
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.enums import TA_CENTER, TA_LEFT, TA_JUSTIFY
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.pdfgen import canvas

from .models import Report, Insight, BOMItem


def render_pdf(report: Report, output_path: str) -> str:
    """
    Generate PDF report.
    
    Args:
        report: Report object
        output_path: Path to output PDF file
        
    Returns:
        Path to generated PDF file
    """
    # Ensure output directory exists
    os.makedirs(os.path.dirname(output_path) if os.path.dirname(output_path) else ".", exist_ok=True)
    
    # Create PDF document
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        rightMargin=20*mm,
        leftMargin=20*mm,
        topMargin=20*mm,
        bottomMargin=20*mm,
    )
    
    # Build story (content)
    story = []
    styles = getSampleStyleSheet()
    
    # Custom styles
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#1a1a1a'),
        spaceAfter=12,
        alignment=TA_CENTER,
    )
    
    heading_style = ParagraphStyle(
        'CustomHeading',
        parent=styles['Heading2'],
        fontSize=16,
        textColor=colors.HexColor('#2c3e50'),
        spaceAfter=8,
        spaceBefore=12,
    )
    
    # Cover page
    story.append(Spacer(1, 30*mm))
    story.append(Paragraph("Engineering Report", title_style))
    story.append(Spacer(1, 10*mm))
    
    if report.meta.file_name:
        story.append(Paragraph(f"<b>File:</b> {report.meta.file_name}", styles['Normal']))
    story.append(Paragraph(f"<b>Assembly ID:</b> {report.meta.assembly_id}", styles['Normal']))
    story.append(Paragraph(f"<b>Generated:</b> {report.meta.generated_at_iso[:19]}", styles['Normal']))
    story.append(Spacer(1, 15*mm))
    
    # Key metrics box
    metrics_data = [
        ['Total Parts', str(report.overview.total_parts)],
        ['Unique Parts', str(report.overview.unique_parts)],
        ['Complexity Score', f"{report.overview.complexity_score_0_100}/100"],
        ['Health Score', f"{report.health_check.score_0_100}/100"],
    ]
    metrics_table = Table(metrics_data, colWidths=[80*mm, 80*mm])
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor('#f8f9fa')),
        ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
    ]))
    story.append(metrics_table)
    
    story.append(PageBreak())
    
    # Overview section
    story.append(Paragraph("Overview", heading_style))
    overview_data = [
        ['Metric', 'Value'],
        ['Total Parts', str(report.overview.total_parts)],
        ['Unique Parts', str(report.overview.unique_parts)],
        ['Repeated Parts', str(report.overview.repeated_parts)],
        ['Complexity Score', f"{report.overview.complexity_score_0_100}/100"],
    ]
    
    if report.overview.bbox_mm:
        overview_data.append(['Bounding Box (mm)', 
                            f"X: {report.overview.bbox_mm.x:.1f}, "
                            f"Y: {report.overview.bbox_mm.y:.1f}, "
                            f"Z: {report.overview.bbox_mm.z:.1f}"])
    
    overview_table = Table(overview_data, colWidths=[100*mm, 60*mm])
    overview_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ]))
    story.append(overview_table)
    story.append(Spacer(1, 10*mm))
    
    # BOM section
    if report.bom:
        story.append(Paragraph("Bill of Materials", heading_style))
        bom_data = [['Item', 'Part Name', 'Qty', 'Material', 'Volume (mm³)']]
        
        for item in report.bom:
            volume_str = f"{item.volume_mm3:.1f}" if item.volume_mm3 else "N/A"
            material_str = item.material or "N/A"
            bom_data.append([
                str(item.item_no),
                item.part_name[:40],  # Truncate long names
                str(item.qty),
                material_str[:20],  # Truncate long materials
                volume_str,
            ])
        
        # Paginate BOM if too long
        max_rows_per_page = 25
        if len(bom_data) > max_rows_per_page + 1:  # +1 for header
            # Split into multiple tables
            for i in range(1, len(bom_data), max_rows_per_page):
                page_bom_data = [bom_data[0]] + bom_data[i:i+max_rows_per_page]
                bom_table = Table(page_bom_data, colWidths=[15*mm, 60*mm, 15*mm, 30*mm, 30*mm])
                bom_table.setStyle(_get_bom_table_style())
                story.append(bom_table)
                if i + max_rows_per_page < len(bom_data):
                    story.append(PageBreak())
        else:
            bom_table = Table(bom_data, colWidths=[15*mm, 60*mm, 15*mm, 30*mm, 30*mm])
            bom_table.setStyle(_get_bom_table_style())
            story.append(bom_table)
        
        story.append(Spacer(1, 10*mm))
    
    # Insights section
    if report.insights:
        story.append(Paragraph("Insights", heading_style))
        for insight in report.insights:
            # Color based on severity
            if insight.severity == "risk":
                bg_color = colors.HexColor('#fee')
                border_color = colors.HexColor('#c33')
            elif insight.severity == "warn":
                bg_color = colors.HexColor('#ffeaa7')
                border_color = colors.HexColor('#fdcb6e')
            else:
                bg_color = colors.HexColor('#e8f4f8')
                border_color = colors.HexColor('#74b9ff')
            
            insight_data = [
                [f"<b>{insight.title}</b> ({insight.severity.upper()})"],
                [insight.details],
            ]
            insight_table = Table(insight_data, colWidths=[150*mm])
            insight_table.setStyle(TableStyle([
                ('BACKGROUND', (0, 0), (-1, -1), bg_color),
                ('TEXTCOLOR', (0, 0), (-1, -1), colors.black),
                ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
                ('FONTNAME', (0, 0), (0, 0), 'Helvetica-Bold'),
                ('FONTSIZE', (0, 0), (-1, -1), 10),
                ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
                ('TOPPADDING', (0, 0), (-1, -1), 8),
                ('LEFTPADDING', (0, 0), (-1, -1), 8),
                ('RIGHTPADDING', (0, 0), (-1, -1), 8),
                ('GRID', (0, 0), (-1, -1), 1, border_color),
            ]))
            story.append(insight_table)
            story.append(Spacer(1, 5*mm))
        
        story.append(Spacer(1, 5*mm))
    
    # Health check section
    story.append(Paragraph("Health Check", heading_style))
    health_color = colors.green
    if report.health_check.score_0_100 < 50:
        health_color = colors.red
    elif report.health_check.score_0_100 < 70:
        health_color = colors.orange
    
    health_data = [
        ['Health Score', f"{report.health_check.score_0_100}/100"],
    ]
    if report.health_check.warnings:
        health_data.append(['Warnings', '; '.join(report.health_check.warnings[:5])])
    
    health_table = Table(health_data, colWidths=[50*mm, 100*mm])
    health_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (0, 0), health_color),
        ('TEXTCOLOR', (0, 0), (0, 0), colors.white),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('GRID', (0, 0), (-1, -1), 1, colors.grey),
    ]))
    story.append(health_table)
    story.append(Spacer(1, 10*mm))
    
    # Largest parts section
    if report.largest_parts:
        story.append(Paragraph("Largest Parts", heading_style))
        largest_data = [['Part Name', 'Volume (mm³)', 'Quantity']]
        for part in report.largest_parts:
            largest_data.append([
                part.get('part_name', 'Unknown')[:40],
                f"{part.get('volume_mm3', 0):.1f}" if part.get('volume_mm3') else "N/A",
                str(part.get('qty', 1)),
            ])
        
        largest_table = Table(largest_data, colWidths=[80*mm, 40*mm, 30*mm])
        largest_table.setStyle(_get_bom_table_style())
        story.append(largest_table)
        story.append(Spacer(1, 10*mm))
    
    # Repetition section
    if report.repetition.top_repeated:
        story.append(Paragraph("Repetition Analysis", heading_style))
        story.append(Paragraph(
            f"Repeated parts account for {report.repetition.repeated_share_pct:.1f}% of total parts.",
            styles['Normal']
        ))
        story.append(Spacer(1, 5*mm))
        
        rep_data = [['Part Name', 'Quantity']]
        for part in report.repetition.top_repeated[:10]:
            rep_data.append([
                part.get('part_name', 'Unknown')[:50],
                str(part.get('qty', 1)),
            ])
        
        rep_table = Table(rep_data, colWidths=[100*mm, 50*mm])
        rep_table.setStyle(_get_bom_table_style())
        story.append(rep_table)
        story.append(Spacer(1, 10*mm))
    
    # Manufacturing hints
    if report.manufacturing_hints:
        story.append(Paragraph("Manufacturing Hints", heading_style))
        for hint in report.manufacturing_hints:
            story.append(Paragraph(f"<b>{hint.title}</b>", styles['Normal']))
            story.append(Paragraph(hint.details, styles['Normal']))
            story.append(Spacer(1, 5*mm))
        story.append(Spacer(1, 5*mm))
    
    # Next steps
    if report.next_steps:
        story.append(Paragraph("Next Steps", heading_style))
        for i, step in enumerate(report.next_steps, 1):
            story.append(Paragraph(f"{i}. {step}", styles['Normal']))
        story.append(Spacer(1, 5*mm))
    
    # Reference geometry section
    if report.reference_geometry:
        story.append(Paragraph("Reference Geometry (Excluded from Manufacturing Analysis)", heading_style))
        story.append(Paragraph(
            f"The following {len(report.reference_geometry)} item(s) were identified as reference geometry "
            "and excluded from volume calculations, largest parts analysis, manufacturing hints, and complexity scoring.",
            styles['Normal']
        ))
        story.append(Spacer(1, 5*mm))
        
        ref_data = [['Part Name', 'Reason']]
        for item in report.reference_geometry:
            ref_data.append([
                item.part_name[:50],  # Truncate long names
                item.reason[:60],  # Truncate long reasons
            ])
        
        ref_table = Table(ref_data, colWidths=[80*mm, 70*mm])
        ref_table.setStyle(_get_bom_table_style())
        story.append(ref_table)
    
    # Build PDF
    doc.build(story)
    
    return output_path


def _get_bom_table_style() -> TableStyle:
    """Get table style for BOM and similar tables."""
    return TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495e')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 10),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('TEXTCOLOR', (0, 1), (-1, -1), colors.black),
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 9),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#f8f9fa')]),
    ])
