from __future__ import annotations

from collections import Counter, defaultdict
from datetime import date
from textwrap import wrap

from .models import Task


DETAILED_TASK_LIMIT = 30
MARKDOWN_INVENTORY_LIMIT = 250
PDF_INVENTORY_LIMIT = 220
PDF_PAGE_LIMIT = 30


def build_markdown_report(tasks: list[Task]) -> str:
    if not tasks:
        return "# AI SEO Copilot Report\n\nNo SEO tasks have been generated yet."

    sorted_tasks = sorted(tasks, key=lambda task: task.priority_score, reverse=True)
    counts = Counter(task.issue for task in sorted_tasks)
    grouped: dict[str, list[Task]] = defaultdict(list)
    for task in sorted_tasks:
        grouped[task.issue].append(task)

    lines = [
        "# AI SEO Copilot Report",
        "",
        "## Executive Summary",
        "",
        f"- Total tasks found: {len(sorted_tasks)}",
        f"- Issue categories: {len(counts)}",
        f"- Average priority: {_average_priority(sorted_tasks)}",
        f"- Average confidence: {_average_confidence(sorted_tasks)}",
        "",
        "## Summarized Report",
        "",
        *_summarized_report(sorted_tasks, counts),
        "",
        "## Issue Breakdown",
        "",
    ]

    for issue, count in counts.most_common():
        lines.append(f"- {issue}: {count}")

    lines.extend(["", "## Action Playbook By Issue", ""])
    lines.extend(_action_playbook(grouped))

    lines.extend(["", "## Highest Priority Tasks", ""])
    for index, task in enumerate(sorted_tasks[:DETAILED_TASK_LIMIT], start=1):
        lines.extend(_task_block(index, task, compact=False))

    lines.extend(["", "## Execution Work Plan", ""])
    lines.extend(_execution_plan(sorted_tasks))

    lines.extend(["", "## Compact Task Inventory", ""])
    lines.extend(_compact_inventory(sorted_tasks, MARKDOWN_INVENTORY_LIMIT))

    return "\n".join(lines).strip() + "\n"


def build_pdf_report(tasks: list[Task]) -> bytes:
    return _build_formatted_pdf(tasks)


def _summarized_report(tasks: list[Task], counts: Counter[str]) -> list[str]:
    high_priority = [task for task in tasks if task.priority_score >= 80]
    top_issues = counts.most_common(5)
    top_tasks = tasks[:10]

    lines = [
        f"- Focus first on {len(high_priority)} high-priority task(s).",
        "- Biggest issue areas: "
        + (", ".join(f"{issue} ({count})" for issue, count in top_issues) if top_issues else "none"),
        "- Recommended first move: assign the top priority fixes, batch similar title/meta updates, then handle broken backlink or traffic-drop recovery.",
        "",
        "### Top 10 Tasks To Start With",
        "",
    ]

    if not top_tasks:
        lines.append("- No tasks available.")
        return lines

    for index, task in enumerate(top_tasks, start=1):
        page = task.page or "insufficient data"
        keyword = f" | {task.keyword}" if task.keyword else ""
        first_action = task.actions[0] if task.actions else "Review the supplied evidence and decide the next SEO action."
        lines.extend(
            [
                f"{index}. {task.issue} - Priority {task.priority_score}/100",
                f"   - Page: {page}{keyword}",
                f"   - Do first: {first_action}",
            ]
        )

    return lines


def _task_block(index: int, task: Task, compact: bool) -> list[str]:
    page = task.page or "insufficient data"
    keyword = f" | Keyword: {task.keyword}" if task.keyword else ""
    lines = [
        f"{index}. **{task.issue}**",
        f"   - Status: [ ] Not started",
        f"   - Page: {page}{keyword}",
        f"   - Priority: {task.priority_score}/100",
        f"   - Confidence: {task.confidence_score}",
        f"   - Evidence: {task.evidence}",
        f"   - Problem: {task.issue}",
    ]

    if task.ai_explanation:
        lines.append(f"   - Explanation: {task.ai_explanation}")

    if task.actions:
        lines.append("   - Recommended actions:")
        for action in task.actions:
            lines.append(f"     - [ ] {action}")

    generated = task.generated_content
    content_bits = []
    if generated.titles:
        content_bits.append("Titles: " + " | ".join(generated.titles[:3]))
    if generated.meta_descriptions:
        content_bits.append("Meta descriptions: " + " | ".join(generated.meta_descriptions[:3]))
    if generated.headings and not compact:
        content_bits.append("Headings: " + " | ".join(generated.headings[:4]))
    if generated.faqs and not compact:
        content_bits.append("FAQs: " + " | ".join(generated.faqs[:4]))

    if content_bits:
        lines.append(f"   - Generated content: {'; '.join(content_bits)}")

    lines.append("")
    return lines


def _execution_plan(tasks: list[Task]) -> list[str]:
    high = [task for task in tasks if task.priority_score >= 80]
    medium = [task for task in tasks if 60 <= task.priority_score < 80]
    low = [task for task in tasks if task.priority_score < 60]

    return [
        "### This Week",
        "",
        f"- Fix or assign the top {min(len(high), 25)} high-priority tasks.",
        "- Prioritize traffic drops, ranking opportunities close to page one, and broken backlink reclamation.",
        "",
        "### Next Sprint",
        "",
        f"- Work through {len(medium)} medium-priority improvements.",
        "- Batch similar CTR and title/meta updates together.",
        "",
        "### Backlog",
        "",
        f"- Keep {len(low)} lower-priority tasks for future content refreshes and cleanup.",
    ]


def _average_priority(tasks: list[Task]) -> float:
    return round(sum(task.priority_score for task in tasks) / len(tasks), 1)


def _average_confidence(tasks: list[Task]) -> float:
    return round(sum(task.confidence_score for task in tasks) / len(tasks), 2)


def _build_formatted_pdf(tasks: list[Task]) -> bytes:
    report = _PdfReport()
    if not tasks:
        report.title_page(0, 0, 0)
        report.section("Report Status")
        report.paragraph("No SEO tasks have been generated yet. Upload Ahrefs CSV files and run analysis to create the PDF report.")
        return report.to_bytes()

    sorted_tasks = sorted(tasks, key=lambda task: task.priority_score, reverse=True)
    counts = Counter(task.issue for task in sorted_tasks)
    grouped: dict[str, list[Task]] = defaultdict(list)
    for task in sorted_tasks:
        grouped[task.issue].append(task)

    high_priority = sum(1 for task in sorted_tasks if task.priority_score >= 80)
    report.title_page(len(sorted_tasks), len(counts), high_priority)
    report.kpi_grid(
        [
            ("Total Tasks", str(len(sorted_tasks))),
            ("Issue Types", str(len(counts))),
            ("Avg Priority", str(_average_priority(sorted_tasks))),
            ("Avg Confidence", str(_average_confidence(sorted_tasks))),
        ]
    )

    report.section("Summarized Report")
    report.bullets(
        [
            f"Focus first on {high_priority} high-priority task(s).",
            "Biggest issue areas: "
            + ", ".join(f"{issue} ({count})" for issue, count in counts.most_common(5)),
            "Recommended first move: assign the top priority fixes, batch similar title/meta updates, then handle broken backlink or traffic-drop recovery.",
        ]
    )

    report.subsection("Top 10 Tasks To Start With")
    for index, task in enumerate(sorted_tasks[:10], start=1):
        first_action = task.actions[0] if task.actions else "Review evidence and decide the next SEO action."
        report.task_card(index, task, first_action, compact=True)

    report.section("Issue Breakdown")
    report.issue_table(counts)

    report.section("Execution Work Plan")
    report.bullets(_execution_plan_plain(sorted_tasks))

    report.section("Action Playbook By Issue")
    for issue, issue_tasks in counts.most_common():
        report.subsection(issue)
        report.bullets(_unique_actions(grouped[issue], limit=5))

    report.section("Highest Priority Tasks")
    for index, task in enumerate(sorted_tasks[:DETAILED_TASK_LIMIT], start=1):
        report.task_card(index, task, compact=False)

    report.section("Compact Task Inventory")
    report.paragraph(
        "This section keeps the PDF concise by listing each highest-impact task as one compact row. "
        "Use JSON or CSV export for the complete raw table when a very large upload exceeds the PDF page budget."
    )
    report.compact_task_table(sorted_tasks[:PDF_INVENTORY_LIMIT], page_limit=PDF_PAGE_LIMIT)
    if len(sorted_tasks) > PDF_INVENTORY_LIMIT:
        remaining = len(sorted_tasks) - PDF_INVENTORY_LIMIT
        report.paragraph(
            f"{remaining} additional lower-priority task(s) are available in the JSON/CSV exports. "
            "They were omitted from this PDF to keep the report within 20-30 pages."
        )

    return report.to_bytes()


def _action_playbook(grouped: dict[str, list[Task]]) -> list[str]:
    lines: list[str] = []
    for issue, issue_tasks in grouped.items():
        lines.extend([f"### {issue}", ""])
        lines.append(f"- Tasks in this category: {len(issue_tasks)}")
        for action in _unique_actions(issue_tasks, limit=6):
            lines.append(f"- [ ] {action}")
        lines.append("")
    return lines


def _unique_actions(tasks: list[Task], limit: int) -> list[str]:
    seen = set()
    actions = []
    for task in tasks:
        for action in task.actions:
            normalized = action.strip().lower()
            if not normalized or normalized in seen:
                continue
            seen.add(normalized)
            actions.append(action.strip())
            if len(actions) >= limit:
                return actions
    return actions or ["Review the supplied evidence and decide the next SEO action."]


def _compact_inventory(tasks: list[Task], limit: int) -> list[str]:
    lines = [
        "| # | Issue | Page / Keyword | Priority | First action |",
        "|---:|---|---|---:|---|",
    ]
    for index, task in enumerate(tasks[:limit], start=1):
        page = task.page or "insufficient data"
        keyword = f" / {task.keyword}" if task.keyword else ""
        action = task.actions[0] if task.actions else "Review evidence."
        lines.append(
            f"| {index} | {_md_cell(task.issue)} | {_md_cell(page + keyword)} | "
            f"{task.priority_score} | {_md_cell(action)} |"
        )
    if len(tasks) > limit:
        lines.extend(
            [
                "",
                f"Note: {len(tasks) - limit} additional lower-priority task(s) are available in the JSON/CSV exports.",
            ]
        )
    return lines


def _execution_plan_plain(tasks: list[Task]) -> list[str]:
    high = [task for task in tasks if task.priority_score >= 80]
    medium = [task for task in tasks if 60 <= task.priority_score < 80]
    low = [task for task in tasks if task.priority_score < 60]
    return [
        f"This week: fix or assign the top {min(len(high), 25)} high-priority tasks.",
        "Prioritize traffic drops, ranking opportunities close to page one, and broken backlink reclamation.",
        f"Next sprint: work through {len(medium)} medium-priority improvements.",
        "Batch similar CTR and title/meta updates together.",
        f"Backlog: keep {len(low)} lower-priority tasks for future content refreshes and cleanup.",
    ]


class _PdfReport:
    page_width = 612
    page_height = 792
    margin = 44
    bottom = 56

    def __init__(self) -> None:
        self.pages: list[list[str]] = []
        self.commands: list[str] = []
        self.page_number = 0
        self.y = 0
        self._new_page()

    def title_page(self, total_tasks: int, issue_types: int, high_priority: int) -> None:
        self._rect(0, 0, self.page_width, self.page_height, fill=(0.05, 0.09, 0.13))
        self._rect(0, 0, self.page_width, 210, fill=(0.09, 0.17, 0.23))
        self._text("AI SEO Copilot", self.margin, 705, size=30, font="F2", color=(1, 1, 1))
        self._text("SEO Action Report", self.margin, 670, size=18, font="F1", color=(0.78, 0.92, 0.96))
        self._text(f"Generated {date.today().isoformat()}", self.margin, 642, size=10, color=(0.72, 0.78, 0.84))
        self._text("Ahrefs insight to prioritized action plan", self.margin, 590, size=12, color=(0.86, 0.91, 0.94))
        self._metric_tile(self.margin, 485, 150, "Total Tasks", str(total_tasks))
        self._metric_tile(self.margin + 170, 485, 150, "Issue Types", str(issue_types))
        self._metric_tile(self.margin + 340, 485, 150, "High Priority", str(high_priority))
        self.y = 430

    def kpi_grid(self, items: list[tuple[str, str]]) -> None:
        self._ensure_space(98)
        width = 122
        gap = 10
        start_x = self.margin
        for index, (label, value) in enumerate(items):
            self._metric_tile(start_x + index * (width + gap), self.y - 72, width, label, value, dark=False)
        self.y -= 96

    def section(self, title: str) -> None:
        self._ensure_space(54)
        self.y -= 10
        self._text(title, self.margin, self.y, size=17, font="F2", color=(0.05, 0.16, 0.22))
        self._line(self.margin, self.y - 8, self.page_width - self.margin, self.y - 8, color=(0.1, 0.54, 0.48), width=1.4)
        self.y -= 30

    def subsection(self, title: str) -> None:
        self._ensure_space(34)
        self._text(title, self.margin, self.y, size=12, font="F2", color=(0.08, 0.22, 0.30))
        self.y -= 22

    def paragraph(self, text: str) -> None:
        for line in self._wrap(text, 10, self.page_width - self.margin * 2):
            self._ensure_space(16)
            self._text(line, self.margin, self.y, size=10, color=(0.16, 0.20, 0.24))
            self.y -= 14
        self.y -= 6

    def bullets(self, items: list[str]) -> None:
        for item in items:
            lines = self._wrap(item, 10, self.page_width - self.margin * 2 - 14)
            self._ensure_space(16 * max(len(lines), 1) + 4)
            self._text("-", self.margin, self.y, size=10, font="F2", color=(0.1, 0.54, 0.48))
            for offset, line in enumerate(lines):
                self._text(line, self.margin + 14, self.y - offset * 14, size=10, color=(0.16, 0.20, 0.24))
            self.y -= 14 * len(lines) + 5

    def issue_table(self, counts: Counter[str]) -> None:
        self._ensure_space(36)
        self._rect(self.margin, self.y - 22, self.page_width - self.margin * 2, 24, fill=(0.91, 0.96, 0.95))
        self._text("Issue", self.margin + 10, self.y - 14, size=9, font="F2")
        self._text("Count", self.page_width - self.margin - 58, self.y - 14, size=9, font="F2")
        self.y -= 28
        for issue, count in counts.most_common():
            self._ensure_space(24)
            self._line(self.margin, self.y - 6, self.page_width - self.margin, self.y - 6, color=(0.84, 0.88, 0.90), width=0.5)
            self._text(issue, self.margin + 10, self.y, size=9, color=(0.15, 0.18, 0.21))
            self._text(str(count), self.page_width - self.margin - 58, self.y, size=9, color=(0.15, 0.18, 0.21))
            self.y -= 22
        self.y -= 8

    def compact_task_table(self, tasks: list[Task], page_limit: int) -> None:
        self._ensure_space(38)
        self._rect(self.margin, self.y - 22, self.page_width - self.margin * 2, 24, fill=(0.91, 0.96, 0.95))
        self._text("#", self.margin + 8, self.y - 14, size=8.3, font="F2")
        self._text("Issue / page / action", self.margin + 34, self.y - 14, size=8.3, font="F2")
        self._text("Priority", self.page_width - self.margin - 58, self.y - 14, size=8.3, font="F2")
        self.y -= 30

        for index, task in enumerate(tasks, start=1):
            if self.page_number >= page_limit and self.y < 150:
                remaining = len(tasks) - index + 1
                self.paragraph(
                    f"{remaining} additional compact task row(s) were omitted to keep this PDF within {page_limit} pages."
                )
                return

            page = task.page or "insufficient data"
            keyword = f" | {task.keyword}" if task.keyword else ""
            action = task.actions[0] if task.actions else "Review evidence and decide the next SEO action."
            detail = f"{task.issue}: {page}{keyword} | {action}"
            wrapped = self._wrap(detail, 7.5, self.page_width - self.margin * 2 - 96)
            row_height = max(22, 10 * min(len(wrapped), 2) + 10)
            self._ensure_space(row_height + 2)
            self._line(self.margin, self.y - 4, self.page_width - self.margin, self.y - 4, color=(0.86, 0.90, 0.92), width=0.4)
            self._text(str(index), self.margin + 8, self.y - 14, size=7.5, color=(0.18, 0.22, 0.26))
            for offset, line in enumerate(wrapped[:2]):
                self._text(line, self.margin + 34, self.y - 14 - offset * 10, size=7.5, color=(0.18, 0.22, 0.26))
            self._text(str(task.priority_score), self.page_width - self.margin - 48, self.y - 14, size=7.5, color=(0.18, 0.22, 0.26))
            self.y -= row_height
        self.y -= 8

    def task_card(self, index: int, task: Task, action: str | None = None, compact: bool = False) -> None:
        action_text = action or (task.actions[0] if task.actions else "Review evidence and decide the next SEO action.")
        lines = [
            f"Page: {task.page or 'insufficient data'}",
            f"Keyword: {task.keyword or 'insufficient data'}",
            f"Evidence: {task.evidence}",
            f"Do first: {action_text}",
        ]
        if not compact and task.ai_explanation:
            lines.append(f"Explanation: {task.ai_explanation}")
        if not compact and len(task.actions) > 1:
            lines.extend(f"Action: {item}" for item in task.actions[1:4])

        wrapped: list[str] = []
        for item in lines:
            wrapped.extend(self._wrap(item, 8.6, self.page_width - self.margin * 2 - 28))

        height = 52 + len(wrapped) * 11
        self._ensure_space(height + 10)
        top = self.y
        self._rect(self.margin, top - height, self.page_width - self.margin * 2, height, fill=(0.97, 0.985, 0.985), stroke=(0.79, 0.86, 0.86))
        self._text(f"{index}. {task.issue}", self.margin + 12, top - 20, size=10.5, font="F2", color=(0.04, 0.16, 0.21))
        self._pill(f"Priority {task.priority_score}/100", self.page_width - self.margin - 112, top - 28, 96)
        self._text(f"Confidence {task.confidence_score}", self.page_width - self.margin - 112, top - 42, size=7.8, color=(0.35, 0.40, 0.44))
        cursor = top - 42
        for line in wrapped:
            self._text(line, self.margin + 14, cursor, size=8.6, color=(0.19, 0.23, 0.26))
            cursor -= 11
        self.y = top - height - 10

    def to_bytes(self) -> bytes:
        self._finish_page()
        return _pdf_from_pages(["\n".join(page).encode("ascii") for page in self.pages])

    def _new_page(self) -> None:
        if self.commands:
            self._finish_page()
        self.page_number += 1
        self.commands = []
        self.y = self.page_height - self.margin
        self._rect(0, 0, self.page_width, self.page_height, fill=(1, 1, 1))

    def _finish_page(self) -> None:
        if not self.commands:
            return
        self._line(self.margin, 36, self.page_width - self.margin, 36, color=(0.82, 0.86, 0.88), width=0.5)
        self._text("AI SEO Copilot", self.margin, 22, size=8, color=(0.42, 0.48, 0.52))
        self._text(f"Page {self.page_number}", self.page_width - self.margin - 42, 22, size=8, color=(0.42, 0.48, 0.52))
        self.pages.append(self.commands)
        self.commands = []

    def _ensure_space(self, height: float) -> None:
        if self.y - height < self.bottom:
            self._new_page()

    def _metric_tile(self, x: float, y: float, width: float, label: str, value: str, dark: bool = True) -> None:
        fill = (0.12, 0.22, 0.29) if dark else (0.94, 0.98, 0.97)
        label_color = (0.75, 0.86, 0.90) if dark else (0.35, 0.42, 0.46)
        value_color = (1, 1, 1) if dark else (0.04, 0.16, 0.21)
        self._rect(x, y, width, 68, fill=fill, stroke=(0.18, 0.38, 0.42) if dark else (0.80, 0.88, 0.87))
        self._text(label.upper(), x + 12, y + 45, size=7.5, font="F2", color=label_color)
        self._text(value, x + 12, y + 19, size=18, font="F2", color=value_color)

    def _pill(self, text: str, x: float, y: float, width: float) -> None:
        self._rect(x, y, width, 16, fill=(0.10, 0.54, 0.48))
        self._text(text, x + 8, y + 5, size=7.5, font="F2", color=(1, 1, 1))

    def _wrap(self, text: str, font_size: float, width: float) -> list[str]:
        chars = max(int(width / (font_size * 0.50)), 18)
        return wrap(
            _ascii(text),
            width=chars,
            break_long_words=False,
            break_on_hyphens=False,
        ) or [""]

    def _text(self, text: str, x: float, y: float, size: float = 10, font: str = "F1", color: tuple[float, float, float] = (0, 0, 0)) -> None:
        self.commands.append(f"{color[0]:.3f} {color[1]:.3f} {color[2]:.3f} rg")
        self.commands.append(f"BT /{font} {size:.2f} Tf {x:.2f} {y:.2f} Td ({_pdf_escape(text)}) Tj ET")

    def _rect(self, x: float, y: float, width: float, height: float, fill: tuple[float, float, float] | None = None, stroke: tuple[float, float, float] | None = None) -> None:
        if fill:
            self.commands.append(f"{fill[0]:.3f} {fill[1]:.3f} {fill[2]:.3f} rg")
        if stroke:
            self.commands.append(f"{stroke[0]:.3f} {stroke[1]:.3f} {stroke[2]:.3f} RG")
        operator = "B" if fill and stroke else "f" if fill else "S"
        self.commands.append(f"{x:.2f} {y:.2f} {width:.2f} {height:.2f} re {operator}")

    def _line(self, x1: float, y1: float, x2: float, y2: float, color: tuple[float, float, float], width: float = 1) -> None:
        self.commands.append(f"{color[0]:.3f} {color[1]:.3f} {color[2]:.3f} RG")
        self.commands.append(f"{width:.2f} w {x1:.2f} {y1:.2f} m {x2:.2f} {y2:.2f} l S")


def _pdf_from_pages(page_streams: list[bytes]) -> bytes:
    objects: list[bytes] = []
    objects.append(b"<< /Type /Catalog /Pages 2 0 R >>")
    page_object_numbers = [3 + index * 2 for index in range(len(page_streams))]
    kids = " ".join(f"{number} 0 R" for number in page_object_numbers)
    objects.append(f"<< /Type /Pages /Kids [{kids}] /Count {len(page_streams)} >>".encode("ascii"))

    for page_index, content in enumerate(page_streams):
        page_object_number = page_object_numbers[page_index]
        content_object_number = page_object_number + 1
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {_PdfReport.page_width} {_PdfReport.page_height}] "
                "/Resources << /Font << "
                "/F1 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> "
                "/F2 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold >> "
                "/F3 << /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Oblique >> "
                f">> >> /Contents {content_object_number} 0 R >>"
            ).encode("ascii")
        )
        objects.append(
            b"<< /Length " + str(len(content)).encode("ascii") + b" >>\nstream\n" + content + b"\nendstream"
        )

    pdf = bytearray(b"%PDF-1.4\n")
    offsets = [0]
    for index, obj in enumerate(objects, start=1):
        offsets.append(len(pdf))
        pdf.extend(f"{index} 0 obj\n".encode("ascii"))
        pdf.extend(obj)
        pdf.extend(b"\nendobj\n")

    xref_offset = len(pdf)
    pdf.extend(f"xref\n0 {len(objects) + 1}\n".encode("ascii"))
    pdf.extend(b"0000000000 65535 f \n")
    for offset in offsets[1:]:
        pdf.extend(f"{offset:010d} 00000 n \n".encode("ascii"))
    pdf.extend(
        (
            f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
            f"startxref\n{xref_offset}\n%%EOF\n"
        ).encode("ascii")
    )
    return bytes(pdf)


def _ascii(value: str) -> str:
    return value.encode("ascii", "replace").decode("ascii")


def _md_cell(value: str) -> str:
    return _ascii(value).replace("|", "/").replace("\n", " ").strip()


def _pdf_escape(value: str) -> str:
    return _ascii(value).replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")
