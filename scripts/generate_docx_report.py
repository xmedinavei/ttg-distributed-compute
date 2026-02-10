#!/usr/bin/env python3
"""
Generate TTG Project Status Report DOCX (M1 + M2 + M3).

Produces a clean, formal document matching the existing supervisor
report style: centered underlined section headings, justified body
text, and clean grid tables.

Usage:
    python3 scripts/generate_docx_report.py
"""

import os
import sys

try:
    from docx import Document
    from docx.shared import Pt, Inches, RGBColor
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.enum.table import WD_TABLE_ALIGNMENT
    from docx.oxml.ns import qn
except ImportError:
    print("ERROR: python-docx not installed. Run: pip3 install python-docx")
    sys.exit(1)

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUTPUT_PATH = os.path.join(
    PROJECT_DIR, "docs", "tracking",
    "TTG_Project_Status_Report_M1_M2_M3.docx",
)


# ═══════════════════════════════════════════════════════════════════════════
# STYLE HELPERS
# ═══════════════════════════════════════════════════════════════════════════

def set_font(run, name="Times New Roman", size=12, bold=False,
             underline=False, color=None):
    """Configure font properties on a run."""
    run.font.name = name
    run.font.size = Pt(size)
    run.bold = bold
    run.underline = underline
    if color:
        run.font.color.rgb = RGBColor(*color)


def add_centered_heading(doc, text, size=13, bold=True, underline=True):
    """Add a centered, bold, underlined heading (matching the image style)."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_before = Pt(12)
    p.paragraph_format.space_after = Pt(6)
    run = p.add_run(text)
    set_font(run, size=size, bold=bold, underline=underline)
    return p


def add_body_text(doc, text, size=11):
    """Add a justified body paragraph."""
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    p.paragraph_format.space_before = Pt(4)
    p.paragraph_format.space_after = Pt(4)
    run = p.add_run(text)
    set_font(run, size=size)
    return p


def add_spacer(doc):
    """Add an empty paragraph spacer."""
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    return p


def make_table(doc, headers, rows, col_widths=None):
    """
    Create a formatted table with bold header row.

    Args:
        doc: Document instance
        headers: list of header strings
        rows: list of lists of cell strings
        col_widths: optional list of Inches for each column
    """
    table = doc.add_table(rows=1 + len(rows), cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.style = "Table Grid"

    # Header row
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = ""
        p = cell.paragraphs[0]
        run = p.add_run(h)
        set_font(run, size=10, bold=True)

    # Data rows
    for r_idx, row_data in enumerate(rows):
        for c_idx, cell_text in enumerate(row_data):
            cell = table.rows[r_idx + 1].cells[c_idx]
            cell.text = ""
            p = cell.paragraphs[0]
            run = p.add_run(str(cell_text))
            # Bold the first column (milestone / metric name)
            is_bold = (c_idx == 0)
            set_font(run, size=10, bold=is_bold)

    # Column widths
    if col_widths:
        for i, w in enumerate(col_widths):
            for row in table.rows:
                row.cells[i].width = Inches(w)

    return table


def add_page_break(doc):
    """Insert a page break."""
    doc.add_page_break()


# ═══════════════════════════════════════════════════════════════════════════
# PAGE 1: PLANNING OVERVIEW
# ═══════════════════════════════════════════════════════════════════════════

def build_page_1(doc):
    """Build the planning overview page (milestones + next steps)."""

    # ── Title ──
    add_centered_heading(doc, "Planning", size=14)

    add_body_text(doc,
        "The TTG Distributed Computation System processes large parameter sets "
        "across multiple Kubernetes worker nodes. The project has successfully "
        "completed three milestones and supports dual queue backends (Redis Streams "
        "and RabbitMQ) with verified fault tolerance, automatic retry/dead-letter "
        "handling, and visual monitoring."
    )

    # ── Milestone 1 ──
    add_centered_heading(doc,
        "Milestone 1: Basic Setup (Complete - January 27, 2026)")

    add_body_text(doc,
        "The foundational infrastructure was established with a local Kubernetes "
        "cluster running 4 nodes (1 control-plane + 3 workers). The system "
        "successfully processed 10,000 parameters in approximately 8 seconds "
        "using 3 parallel workers with static range partitioning. All workers "
        "completed successfully with a 100% success rate, computing a grand sum "
        "of 5,000,354."
    )

    # ── Milestone 2 ──
    add_centered_heading(doc,
        "Milestone 2: Message Queue (Complete - February 4, 2026)")

    add_body_text(doc,
        "The system was enhanced with Redis Streams for dynamic task distribution "
        "and fault tolerance. The key achievement is verified fault tolerance: when "
        "a worker was forcefully terminated at 30% progress, the remaining workers "
        "continued processing without interruption, and all 100 task chunks "
        "completed successfully with zero data loss. This proves the queue-based "
        "architecture can recover from failures automatically. Additional "
        "deliverables include a demo script with fault injection, safe cleanup "
        "utilities, and comprehensive documentation."
    )

    # ── Milestone 3 ──
    add_centered_heading(doc,
        "Milestone 3: Production Queue (Complete - February 9, 2026)")

    add_body_text(doc,
        "RabbitMQ was added as a production-grade queue backend while preserving "
        "Redis Streams as a rollback-safe fallback. The worker selects the backend "
        "via the QUEUE_BACKEND environment variable. RabbitMQ provides retry queues "
        "with configurable TTL and a Dead Letter Queue (DLQ) for exhausted retries. "
        "Both backends achieve 100% task completion with zero data loss under fault "
        "injection. A unified one-command demo script supports both backends with "
        "live progress bars, fault injection, and strict TTG-only cleanup. "
        "Monitoring is available via RabbitMQ Management UI and CLI tools."
    )

    # ── Next Steps ──
    add_centered_heading(doc,
        "Next Steps: Milestone 4 (Target: ??)")

    add_body_text(doc,
        "Future work includes adding Prometheus and Grafana monitoring dashboards "
        "in Kind, planning a full RabbitMQ cutover (deprecating the Redis path), "
        "scale testing with 100K+ parameters, and deploying to Azure Kubernetes "
        "Service (AKS) for production. A CI/CD pipeline for automated deployment "
        "is also planned."
    )


# ═══════════════════════════════════════════════════════════════════════════
# PAGE 2: TABLES
# ═══════════════════════════════════════════════════════════════════════════

def build_page_2(doc):
    """Build the milestone status and metrics comparison page."""

    add_page_break(doc)

    # ── Milestone Status Table ──
    add_centered_heading(doc, "Milestone Status", size=13)

    make_table(doc,
        headers=["Milestone", "Deliverables", "Status", "Date", "Key Result"],
        rows=[
            [
                "M1: Basic Setup",
                "K8s cluster, workers,\nparallel jobs",
                "✅ Complete",
                "Jan 27",
                "10K params in 8s",
            ],
            [
                "M2: Message Queue",
                "Redis Streams, fault\ntolerance",
                "✅ Complete",
                "Feb 4",
                "100% despite failure",
            ],
            [
                "M3: Production\nQueue",
                "RabbitMQ backend,\nretry/DLQ, dual-mode",
                "✅ Complete",
                "Feb 9",
                "25 p/s RabbitMQ,\n27 p/s Redis",
            ],
        ],
        col_widths=[1.3, 1.5, 0.9, 0.7, 1.5],
    )

    add_spacer(doc)
    add_spacer(doc)

    # ── Key Metrics Comparison Table ──
    add_centered_heading(doc, "Key Metrics Comparison", size=13)

    make_table(doc,
        headers=["Metric", "Milestone 1", "Milestone 2", "Milestone 3"],
        rows=[
            ["Architecture", "Static partitioning", "Redis Streams queue", "RabbitMQ AMQP queue"],
            ["Fault Tolerance", "❌ None", "✅ Verified (100/100\nat 30% kill)", "✅ Verified (100/100\nauto-requeue)"],
            ["Task Distribution", "Pre-calculated", "Dynamic (consumer\ngroups)", "Dynamic (basic_get\nprefetch=1)"],
            ["Parameters Processed", "10,000", "10,000", "1,000 (demo)"],
            ["Workers", "3 parallel", "3 queue-based", "3 queue-based"],
            ["Execution Time", "~8 seconds", "~8s (44s with fault\ndemo)", "39s (49s with fault\ndemo)"],
            ["Throughput", "1,250 params/sec", "1,276 params/sec", "25 params/sec (demo\nscale)"],
            ["Success Rate", "100%", "100%", "100%"],
            ["Retry / DLQ", "N/A", "XCLAIM recovery", "Retry queue + DLQ"],
        ],
        col_widths=[1.3, 1.4, 1.5, 1.5],
    )


# ═══════════════════════════════════════════════════════════════════════════
# PAGE 3: TEST RESULTS SUMMARY
# ═══════════════════════════════════════════════════════════════════════════

def build_page_3(doc):
    """Build the complete test results summary page."""

    add_page_break(doc)

    # ── Heading ──
    add_centered_heading(doc, "Test Results Summary", size=14)

    add_body_text(doc,
        "The table below consolidates every verified demo run across all three "
        "milestones. All runs achieved 100% task completion with zero data loss, "
        "including runs where a worker was forcefully killed mid-processing."
    )

    add_spacer(doc)

    # ── Full Results Table ──
    make_table(doc,
        headers=[
            "Run",
            "Milestone",
            "Backend",
            "Fault\nInjection",
            "Workers",
            "Params",
            "Chunks",
            "Time",
            "Throughput",
            "Data\nLoss",
        ],
        rows=[
            [
                "1",
                "M1",
                "Static\npartition",
                "No",
                "3",
                "10,000",
                "N/A",
                "~8s",
                "1,250 p/s",
                "ZERO",
            ],
            [
                "2",
                "M2",
                "Redis\nStreams",
                "No",
                "3",
                "10,000",
                "100/100",
                "~8s",
                "1,276 p/s",
                "ZERO",
            ],
            [
                "3",
                "M2",
                "Redis\nStreams",
                "Yes\n(kill at 30%)",
                "3→2",
                "10,000",
                "100/100",
                "44s",
                "227 p/s",
                "ZERO",
            ],
            [
                "4",
                "M3",
                "Redis\nStreams",
                "No",
                "3",
                "1,000",
                "100/100",
                "36s",
                "27 p/s",
                "ZERO",
            ],
            [
                "5",
                "M3",
                "Redis\nStreams",
                "Yes\n(kill at 33%)",
                "3→2",
                "1,000",
                "100/100",
                "48s",
                "20 p/s",
                "ZERO",
            ],
            [
                "6",
                "M3",
                "RabbitMQ",
                "No",
                "3",
                "1,000",
                "100/100",
                "39s",
                "25 p/s",
                "ZERO",
            ],
            [
                "7",
                "M3",
                "RabbitMQ",
                "Yes\n(kill at 36%)",
                "3→2",
                "1,000",
                "100/100",
                "49s",
                "20 p/s",
                "ZERO",
            ],
        ],
        col_widths=[0.35, 0.55, 0.7, 0.75, 0.55, 0.6, 0.6, 0.45, 0.7, 0.45],
    )

    add_spacer(doc)

    # ── Key Takeaways ──
    add_centered_heading(doc, "Key Takeaways", size=13)

    takeaways = [
        "100% success rate across all 7 verified demo runs — no task was ever lost.",
        "Fault tolerance works on both backends: Redis recovers via XCLAIM; "
        "RabbitMQ auto-requeues unacked messages on worker disconnect.",
        "Throughput drops ~20-25% under fault (2 vs 3 workers) — expected and proportional.",
        "RabbitMQ adds retry queues and Dead Letter Queue (DLQ) for operational "
        "visibility not available with Redis alone.",
        "Both backends can be demoed with a single command: "
        "./scripts/run-demo.sh --backend redis|rabbitmq",
    ]
    for t in takeaways:
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.space_before = Pt(2)
        p.paragraph_format.space_after = Pt(2)
        # Bullet prefix
        run = p.add_run("•  " + t)
        set_font(run, size=10)


# ═══════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════

def main():
    doc = Document()

    # Set default font for the document
    style = doc.styles["Normal"]
    font = style.font
    font.name = "Times New Roman"
    font.size = Pt(11)

    # Set narrow margins (matching the image)
    for section in doc.sections:
        section.top_margin = Inches(0.8)
        section.bottom_margin = Inches(0.8)
        section.left_margin = Inches(1.0)
        section.right_margin = Inches(1.0)

    print("Building page 1: Planning overview...")
    build_page_1(doc)

    print("Building page 2: Milestone Status + Key Metrics...")
    build_page_2(doc)

    print("Building page 3: Test Results Summary...")
    build_page_3(doc)

    # Save
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    doc.save(OUTPUT_PATH)
    print(f"\n✅ Report saved: {OUTPUT_PATH}")
    print(f"   File size: {os.path.getsize(OUTPUT_PATH):,} bytes")


if __name__ == "__main__":
    main()
