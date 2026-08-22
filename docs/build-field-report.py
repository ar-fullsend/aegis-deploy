#!/usr/bin/env python3
"""Accessible, linearized field report for 100monkeys.ai engineering leadership."""
from __future__ import annotations

from pathlib import Path
from xml.sax.saxutils import escape

from reportlab.lib import colors
from reportlab.lib.enums import TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.pdfmetrics import registerFontFamily
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import (
    CondPageBreak,
    Flowable,
    KeepTogether,
    ListFlowable,
    ListItem,
    PageBreak,
    Paragraph,
    Preformatted,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

OUT = Path(__file__).with_name("AEGIS-Local-SLM-Field-Report-2026-08-21.pdf")
PATCH = Path(__file__).with_name("aegis-operator-2026-08-21.patch")

NAVY = colors.HexColor("#0B1F33")
INK = colors.HexColor("#1A1A1A")
RULE = colors.HexColor("#4A5560")
PALE = colors.HexColor("#F4F6F8")
WHITE = colors.white
ACCENT = colors.HexColor("#0B1F33")


class Bookmark(Flowable):
    def __init__(self, key: str, title: str, level: int = 0):
        super().__init__()
        self.key = key
        self.title = title
        self.level = level
        self.width = 0
        self.height = 0

    def draw(self):
        self.canv.bookmarkPage(self.key)
        self.canv.addOutlineEntry(self.title, self.key, self.level, closed=0)


def styles():
    base = getSampleStyleSheet()
    s = {
        "cover_kicker": ParagraphStyle(
            "cover_kicker",
            fontName="Times-Bold",
            fontSize=11,
            leading=14,
            textColor=WHITE,
            spaceAfter=6,
        ),
        "cover_title": ParagraphStyle(
            "cover_title",
            fontName="Times-Bold",
            fontSize=26,
            leading=32,
            textColor=WHITE,
            spaceAfter=10,
        ),
        "cover_sub": ParagraphStyle(
            "cover_sub",
            fontName="Times-Roman",
            fontSize=12,
            leading=16,
            textColor=WHITE,
        ),
        "h1": ParagraphStyle(
            "h1",
            fontName="Times-Bold",
            fontSize=16,
            leading=20,
            textColor=NAVY,
            spaceBefore=16,
            spaceAfter=8,
            keepWithNext=True,
        ),
        "h2": ParagraphStyle(
            "h2",
            fontName="Times-Bold",
            fontSize=13,
            leading=17,
            textColor=NAVY,
            spaceBefore=12,
            spaceAfter=6,
            keepWithNext=True,
        ),
        "body": ParagraphStyle(
            "body",
            fontName="Times-Roman",
            fontSize=11,
            leading=15,
            textColor=INK,
            alignment=TA_LEFT,
            spaceAfter=8,
        ),
        "bullet": ParagraphStyle(
            "bullet",
            fontName="Times-Roman",
            fontSize=11,
            leading=15,
            textColor=INK,
            leftIndent=12,
            spaceAfter=3,
        ),
        "cell": ParagraphStyle(
            "cell",
            fontName="Times-Roman",
            fontSize=9.5,
            leading=12.5,
            textColor=INK,
        ),
        "cell_h": ParagraphStyle(
            "cell_h",
            fontName="Times-Bold",
            fontSize=9.5,
            leading=12.5,
            textColor=WHITE,
        ),
        "code": ParagraphStyle(
            "code",
            fontName="Courier",
            fontSize=8.5,
            leading=11,
            textColor=INK,
            backColor=PALE,
            leftIndent=6,
            rightIndent=6,
            spaceBefore=4,
            spaceAfter=8,
        ),
        "caption": ParagraphStyle(
            "caption",
            fontName="Times-Italic",
            fontSize=9,
            leading=12,
            textColor=INK,
            spaceAfter=10,
        ),
        "footer": ParagraphStyle(
            "footer",
            fontName="Times-Roman",
            fontSize=8,
            leading=10,
            textColor=INK,
        ),
        "diff_file": ParagraphStyle(
            "diff_file",
            fontName="Times-Bold",
            fontSize=11,
            leading=14,
            textColor=NAVY,
            spaceBefore=10,
            spaceAfter=4,
            keepWithNext=True,
        ),
        "diff_meta": ParagraphStyle(
            "diff_meta",
            fontName="Courier",
            fontSize=8,
            leading=10.5,
            textColor=NAVY,
            spaceBefore=1,
            spaceAfter=1,
        ),
        "diff_ctx": ParagraphStyle(
            "diff_ctx",
            fontName="Courier",
            fontSize=8,
            leading=10.5,
            textColor=INK,
            spaceBefore=0,
            spaceAfter=0,
        ),
        "diff_plus": ParagraphStyle(
            "diff_plus",
            fontName="Courier",
            fontSize=8,
            leading=10.5,
            textColor=colors.HexColor("#0A5C2A"),
            spaceBefore=0,
            spaceAfter=0,
        ),
        "diff_minus": ParagraphStyle(
            "diff_minus",
            fontName="Courier",
            fontSize=8,
            leading=10.5,
            textColor=colors.HexColor("#8F1D1D"),
            spaceBefore=0,
            spaceAfter=0,
        ),
    }
    return s


def P(text, style):
    return Paragraph(text, style)


def table(headers, rows, col_widths):
    cell, head = styles()["cell"], styles()["cell_h"]
    data = [[P(f"<b>{h}</b>", head) for h in headers]]
    for row in rows:
        data.append([P(c, cell) for c in row])
    t = Table(data, colWidths=col_widths, repeatRows=1)
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), NAVY),
                ("TEXTCOLOR", (0, 0), (-1, 0), WHITE),
                ("BACKGROUND", (0, 1), (-1, -1), WHITE),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("RIGHTPADDING", (0, 0), (-1, -1), 6),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("GRID", (0, 0), (-1, -1), 0.6, RULE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [WHITE, PALE]),
            ]
        )
    )
    return t


def flow_diff(story, s) -> None:
    """Append the unified operator patch. Prefix +/– is the meaning; color is extra."""
    raw = PATCH.read_text(encoding="utf-8", errors="replace")
    files = []
    current = None
    plus = minus = 0
    for line in raw.splitlines():
        if line.startswith("diff --git "):
            if current:
                files.append(current)
            parts = line.split()
            path = parts[-1][2:] if len(parts) >= 4 else line
            current = {"path": path, "plus": 0, "minus": 0}
        elif current is not None:
            if line.startswith("+") and not line.startswith("+++"):
                current["plus"] += 1
            elif line.startswith("-") and not line.startswith("---"):
                current["minus"] += 1
    if current:
        files.append(current)

    story.append(PageBreak())
    story.append(Bookmark("s10", "Appendix — unified diff of the deploy fork", 0))
    story.append(P("Appendix — unified diff of the deploy fork", s["h1"]))
    story.append(
        P(
            "Offered with thanks, as a patch you can read or apply. This is "
            "<font face='Courier'>git diff HEAD</font> of <font face='Courier'>ar-fullsend/aegis-deploy</font> "
            "against the tree we started from today, plus three new scripts. Excluded: this PDF, "
            "its generator, and an unrelated <font face='Courier'>pc-tuning/</font> folder. "
            "Added lines are prefixed with <b>+</b> (dark green). Removed lines are prefixed with "
            "<b>−</b> (dark red). Color is not the only cue.",
            s["body"],
        )
    )
    rows = [[f["path"], str(f["plus"]), str(f["minus"])] for f in files]
    story.append(
        table(
            ["Path", "Added", "Removed"],
            rows,
            [5.2 * inch, 0.9 * inch, 0.9 * inch],
        )
    )
    story.append(
        P(
            f"Table 6. {len(files)} paths, {sum(f['plus'] for f in files)} insertions, "
            f"{sum(f['minus'] for f in files)} deletions. Full unified diff follows.",
            s["caption"],
        )
    )

    file_i = 0
    for line in raw.splitlines():
        if line.startswith("diff --git "):
            file_i += 1
            path = line.split()[-1][2:] if len(line.split()) >= 4 else line
            story.append(CondPageBreak(1.4 * inch))
            story.append(Bookmark(f"diff-{file_i}", path, 1))
            story.append(P(escape(path), s["diff_file"]))
            story.append(P(escape(line), s["diff_meta"]))
            continue
        if line.startswith("index ") or line.startswith("new file mode") or line.startswith("deleted file mode"):
            story.append(P(escape(line), s["diff_meta"]))
            continue
        if line.startswith("--- ") or line.startswith("+++ ") or line.startswith("@@"):
            story.append(P(escape(line), s["diff_meta"]))
            continue
        if line.startswith("+"):
            story.append(P(escape(line), s["diff_plus"]))
            continue
        if line.startswith("-"):
            story.append(P(escape(line), s["diff_minus"]))
            continue
        if line.startswith("#"):
            continue
        if not line.strip():
            story.append(Spacer(1, 4))
            continue
        story.append(P(escape(line) if line else " ", s["diff_ctx"]))


def header_footer(canvas: Canvas, doc):
    canvas.saveState()
    w, h = letter
    if doc.page > 1:
        canvas.setFillColor(NAVY)
        canvas.rect(0, h - 36, w, 36, fill=1, stroke=0)
        canvas.setFillColor(WHITE)
        canvas.setFont("Times-Roman", 9)
        canvas.drawString(
            0.75 * inch,
            h - 22,
            "AEGIS local-SLM field report  ·  100monkeys.ai  ·  2026-08-21",
        )
        canvas.setFillColor(INK)
        canvas.setFont("Times-Roman", 9)
        canvas.drawRightString(w - 0.75 * inch, 0.45 * inch, f"Page {doc.page}")
        canvas.setStrokeColor(RULE)
        canvas.setLineWidth(0.5)
        canvas.line(0.75 * inch, 0.58 * inch, w - 0.75 * inch, 0.58 * inch)
    canvas.restoreState()


def cover(canvas: Canvas, doc):
    canvas.saveState()
    w, h = letter
    canvas.setFillColor(NAVY)
    canvas.rect(0, 0, w, h, fill=1, stroke=0)
    canvas.setFillColor(WHITE)
    canvas.rect(0, h - 0.35 * inch, w, 0.35 * inch, fill=1, stroke=0)
    canvas.setFillColor(NAVY)
    canvas.setFont("Times-Bold", 9)
    canvas.drawString(0.75 * inch, h - 0.23 * inch, "WITH APPRECIATION  ·  ENGINEERING FIELD REPORT")
    canvas.setFillColor(WHITE)
    canvas.setFont("Times-Roman", 11)
    canvas.drawString(0.75 * inch, h - 1.4 * inch, "TO")
    canvas.setFont("Times-Bold", 14)
    canvas.drawString(0.75 * inch, h - 1.65 * inch, "Founder, 100monkeys.ai")
    canvas.setFont("Times-Roman", 11)
    canvas.drawString(0.75 * inch, h - 2.05 * inch, "FROM")
    canvas.setFont("Times-Bold", 14)
    canvas.drawString(0.75 * inch, h - 2.3 * inch, "A grateful operator  ·  ar-fullsend/aegis-deploy")
    canvas.setStrokeColor(WHITE)
    canvas.setLineWidth(1.2)
    canvas.line(0.75 * inch, h - 2.7 * inch, 3.2 * inch, h - 2.7 * inch)
    canvas.setFont("Times-Bold", 26)
    canvas.drawString(0.75 * inch, h - 3.4 * inch, "Thank you for AEGIS.")
    y = h - 3.9 * inch
    for line in [
        "Your control plane ran a full intent-to-execution FSM on a",
        "GTX 1660 Ti, rootless Podman, Kali, and a local GGUF. This",
        "note is what we learned adapting it to a slow local SLM —",
        "and the improvements we made on top of your work.",
    ]:
        canvas.setFont("Times-Roman", 13)
        canvas.drawString(0.75 * inch, y, line)
        y -= 18
    canvas.setFont("Times-Roman", 11)
    canvas.drawString(0.75 * inch, 1.3 * inch, "Date  21 August 2026")
    canvas.drawString(0.75 * inch, 1.1 * inch, "Lab   Kali GNU/Linux  ·  rootless Podman  ·  LM Studio llama.cpp CUDA")
    canvas.drawString(0.75 * inch, 0.9 * inch, "Repo  github.com/ar-fullsend/aegis-deploy  (fork of 100monkeys-ai stack)")
    canvas.restoreState()


def build():
    s = styles()
    story = []
    usable = 7.0 * inch

    def h1(key, title):
        story.append(Bookmark(key, title, 0))
        story.append(P(title, s["h1"]))

    def h2(key, title):
        story.append(Bookmark(key, title, 1))
        story.append(P(title, s["h2"]))

    story.append(PageBreak())

    h1("s1", "1. With thanks — and a result")
    story.append(
        P(
            "First: thank you. AEGIS is an unusually complete piece of systems work — "
            "orchestrator, Temporal FSM, SEAL envelopes, Keycloak, SeaweedFS, FUSE/NFS "
            "workspaces, FSAL isolation, and Zaru MCP as a tool proxy. Standing that up "
            "on a laptop is already a gift to operators. We spent 21 August 2026 putting "
            "it on Kali with rootless Podman and a local GGUF, and it <b>did the thing "
            "you designed it to do</b>.",
            s["body"],
        )
    )
    story.append(
        P(
            "<font face='Courier'>builtin-intent-to-execution</font> completed and printed "
            "<font face='Courier'>[0, 1, 1, 2, 3, 5, 8, 13, 21, 34]</font> — the first ten "
            "Fibonacci numbers for <font face='Courier'>n=10</font>. Your isolated Python "
            "container finished in <b>588 ms</b>. That number is the compliment: the "
            "sandbox, volume, and ContainerRun path are tight. The ~65 minute wall clock "
            "was almost entirely the local 27B SLM and a few layers we tuned so a slow "
            "box can still finish the FSM you wrote.",
            s["body"],
        )
    )
    story.append(
        P(
            "This note is not a complaint. It is a field report from someone who wanted "
            "your stack to shine on hardware nobody would pick for 27B, and who then "
            "patched the deploy repo so it could. Everything below is offered as "
            "<b>improvements on your work</b>, with gratitude, and as candidates to "
            "take upstream if they are useful.",
            s["body"],
        )
    )

    h1("s2", "2. Lab")
    story.append(
        table(
            ["Layer", "What we actually ran"],
            [
                [
                    "Host",
                    "Kali Rolling, 6 CPU threads, 15 GiB RAM, NVIDIA GeForce GTX 1660 Ti 6 GB (CUDA llama.cpp via LM Studio 0.4.21).",
                ],
                [
                    "Runtime",
                    "Rootless Podman kube-play. Profile <font face='Courier'>development</font>: database, secrets, temporal, seal-gateway, iam, core, mcp, storage, observability.",
                ],
                [
                    "LLM #1",
                    "<font face='Courier'>prism-ml/bonsai-27b</font> GGUF Q1_0, 4.73 GB, 56 GPU layers, ctx 8192, parallel 4, KV f16, vision mmproj loaded. Thinking on, then off.",
                ],
                [
                    "LLM #2 (now live)",
                    "<font face='Courier'>qwen2.5-coder-7b-instruct</font> Q4_K_M from lmstudio-community/Qwen2.5-Coder-7B-Instruct-GGUF. Reloaded <font face='Courier'>--gpu max -c 4096 --parallel 1</font>. Smoke test: chat completion “pong” in <b>0.38 s</b>, 2 completion tokens, 0 reasoning tokens.",
                ],
                [
                    "Auth",
                    "Keycloak 24 realm <font face='Courier'>aegis-system</font>, client <font face='Courier'>aegis-runtime</font>, issuer <font face='Courier'>http://127.0.0.1:8180</font>. Local Admin UI is happiest at that URL; <font face='Courier'>auth.localhost</font> + <font face='Courier'>--proxy=edge</font> wants Caddy in front.",
                ],
            ],
            [1.5 * inch, 5.5 * inch],
        )
    )
    story.append(P("Table 1. Hardware and control-plane facts. Nothing here is hypothetical.", s["caption"]))

    h1("s3", "3. What the pipeline actually did")
    story.append(
        P(
            "Workload: “Write a Python function fib(n) that returns the first n Fibonacci numbers,” "
            "language python, <font face='Courier'>inputs.n=10</font>, image "
            "<font face='Courier'>python:3.11-slim</font>. Workflow "
            "<font face='Courier'>builtin-intent-to-execution</font>.",
            s["body"],
        )
    )
    story.append(
        table(
            ["Execution", "Version", "Outcome", "Wall clock (approx.)"],
            [
                [
                    "c2ac7aed… / WRITE 3372e7e9",
                    "workflow 1.0.0 (stock, in-flight at core boot)",
                    "WRITE completed; VALIDATE timed out at 300 s overall on first thinking generate. Never called fs.read.",
                    "WRITE ~4 min + VALIDATE 5 min fail",
                ],
                [
                    "f6463680-0e2b-4c9f-bdb8-e185bab6c5f1",
                    "1.0.2",
                    "LM Studio unreachable at pasta 169.254.1.2. WRITE/VALIDATE 502 then “Output is not valid JSON: EOF”.",
                    "~27 s fail",
                ],
                [
                    "ac5367c2-bed4-48cf-b4f5-4f2758381c26",
                    "1.0.2",
                    "WRITE+VALIDATE pass. Container exit 0 in 602 ms. Formatter 300 s × Temporal retries blew EXECUTE 15 min activity.",
                    "~22 min fail at EXECUTE",
                ],
                [
                    "9a9a8908-818d-41c7-804a-67e90bf2e94a",
                    "1.0.3 (formatter required:false)",
                    "completed. stdout was a single newline. Model wrote code that ran and printed nothing useful.",
                    "~20 min",
                ],
                [
                    "19939581-953f-4c43-92a5-97de0c2d958f",
                    "1.0.3, thinking off",
                    "<b>completed</b>. First EXECUTE exit 1, FSM looped, second EXECUTE stdout <font face='Courier'>[0, 1, 1, 2, 3, 5, 8, 13, 21, 34]</font>, 588 ms, exit 0.",
                    "~65 min",
                ],
            ],
            [1.55 * inch, 1.15 * inch, 2.7 * inch, 1.6 * inch],
        )
    )
    story.append(P("Table 2. Intent-to-execution attempts on this node. The successful payload is yours.", s["caption"]))
    story.append(
        P(
            "The 65-minute success is a story about the model, not the architecture. Your "
            "three-agent FSM and Temporal formatter are doing exactly what they were designed "
            "to do — they simply assumed cloud-class generate latency. Once thinking was off, "
            "WRITE/VALIDATE were still multi-minute because Q1_0 27B on 6 GB is a packing "
            "trick, not a latency trick. The sandbox you built was never the bottleneck, "
            "and that is high praise.",
            s["body"],
        )
    )

    h1("s4", "4. Problems we solved on the local-SLM path")
    story.append(
        P(
            "These are edge cases we hit while stretching AEGIS onto a 6 GB card and rootless "
            "netavark. We solved them in the deploy fork and would be glad to contribute the "
            "patches upstream. None of this diminishes the design — it is what operators do "
            "when they care about a system.",
            s["body"],
        )
    )
    h2("s4a", "4.1 Host gateway on rootless netavark")
    story.append(
        P(
            "The documented local-LLM path is "
            "<font face='Courier'>http://host.containers.internal:1234/v1</font>, which is the "
            "right abstraction. On this Kali + netavark bridge (<font face='Courier'>aegis-network</font> "
            "10.89.0.0/24), Podman injects <font face='Courier'>169.254.1.2</font>. From "
            "<font face='Courier'>aegis-core</font> that address timed out on every port. The "
            "host LAN IPv4 (<font face='Courier'>192.168.1.204</font> today) worked. Bridge "
            "gateway <font face='Courier'>10.89.0.1:1234</font> did not — 1234 is a host process, "
            "not a published container port, so rootlessport never maps it.",
            s["body"],
        )
    )
    story.append(
        P(
            "What we did: rewrite <font face='Courier'>/etc/hosts</font> in the core pod at "
            "deploy/redeploy (<font face='Courier'>scripts/patch-host-gateway.sh</font>). "
            "Kubernetes <font face='Courier'>hostAliases</font> alone is not enough because "
            "pasta’s 169.254.1.2 line wins first-match. If local LLM is a SKU you want to "
            "support first-class, we would love to help land a tested host-gateway story for "
            "rootless netavark. Happy to send the script.",
            s["body"],
        )
    )

    h2("s4b", "4.2 Naming the timeout layers")
    story.append(
        P(
            "Your timeout model is actually quite careful — there are separate knobs for a "
            "single generate, an iteration, the whole agent, the Temporal state, the formatter "
            "activity, and the HTTP client. We learned that the hard way, and then we used "
            "that design as intended. A uniform “5 minutes everywhere” does not work until "
            "each layer is named:",
            s["body"],
        )
    )
    story.append(
        table(
            ["Knob", "Where", "What it actually caps"],
            [
                [
                    "<font face='Courier'>llm_timeout_seconds</font>",
                    "Agent spec.execution",
                    "One generate (HTTP to the provider).",
                ],
                [
                    "<font face='Courier'>iteration_timeout</font>",
                    "Agent spec.execution",
                    "One supervisor iteration (generate + tools).",
                ],
                [
                    "<font face='Courier'>security.resources.timeout</font>",
                    "Agent spec",
                    "Whole agent run. This became <font face='Courier'>overall_timeout_secs</font>. VALIDATE died here at 300 s on iteration 1.",
                ],
                [
                    "<font face='Courier'>states.*.timeout</font>",
                    "Workflow FSM",
                    "Temporal activity StartToClose for that state.",
                ],
                [
                    "<font face='Courier'>output_handler.timeout_seconds</font>",
                    "ContainerRun",
                    "Formatter activity. Stock 60 s × 3 retries = “Activity task failed” at EXECUTE_CODE while the Python container already exited 0.",
                ],
                [
                    "<font face='Courier'>llm_overall_timeout_secs</font>",
                    "NodeConfig",
                    "Orchestrator HTTP client. Must be ≥ the largest agent llm timeout or the client wins.",
                ],
            ],
            [1.9 * inch, 1.5 * inch, 3.6 * inch],
        )
    )
    story.append(P("Table 3. Timeout fields in your manifests — we used each of them.", s["caption"]))
    story.append(
        P(
            "VALIDATE is a two-turn tool agent (mandatory <font face='Courier'>fs.read</font>, then JSON "
            "with <font face='Courier'>json_schema</font> min_score 1.0). That design is sound for a "
            "capable model. On a thinking 27B, setting "
            "<font face='Courier'>resources.timeout = llm_timeout</font> meant the second turn never "
            "started. We learned to set <b>overall ≥ N × per-call</b> for iterative agents. A "
            "deploy-time check that refuses a manifest which cannot mathematically finish would "
            "be a lovely addition to the engine you already have.",
            s["body"],
        )
    )

    h2("s4c", "4.3 Overlay versions above stock builtins")
    story.append(
        P(
            "Core start helpfully re-registers stock v1.0.0 agents and the builtin workflow "
            "(<font face='Courier'>content drift detected — overwriting</font>). That is a "
            "reasonable way to keep builtins fresh. To keep our local-SLM timeouts, we versioned "
            "overlays at 1.0.1 / 1.0.2 / 1.0.3 / now <b>1.0.4</b> so semver stays above stock. "
            "That works for new runs. It does not rewrite in-flight executions started at boot "
            "(our first VALIDATE timeout was 1.0.0, started at 15:48:03, overlay applied 15:48:38).",
            s["body"],
        )
    )
    story.append(
        P(
            "A small upstream improvement: treat overlay/latest as an explicit node config, or "
            "skip force-redeploy when an operator overlay is already newer. We would be happy "
            "to sketch a lock file if that fits the model.",
            s["body"],
        )
    )

    h2("s4d", "4.4 Formatter as best-effort on a slow SLM")
    story.append(
        P(
            "The output formatter is a nice consumer-facing idea. On this box, "
            "ContainerRunCompleted in 602 ms, exit 0, then "
            "<font face='Courier'>aegis-output-formatter-agent</font> sat on a 27B generate until "
            "<font face='Courier'>overall_timeout_secs=300</font>. Temporal retried, and the parent "
            "EXECUTE state (15 m) ended with <font face='Courier'>Activity task failed</font>. "
            "The structured result already lives on <font face='Courier'>EXECUTE_CODE.stdout</font> "
            "via your <font face='Courier'>output_template</font> — which is elegant. We simply "
            "needed the pretty-print step not to own the critical path.",
            s["body"],
        )
    )
    story.append(
        P(
            "Version 1.0.4 uses <font face='Courier'>timeout_seconds: 15</font>, "
            "<font face='Courier'>required: false</font>, EXECUTE state 5 m, "
            "<font face='Courier'>max_state_visits: 1</font>. If the formatter cannot return in "
            "15 s, we keep the raw stdout. For local SLM that feels like the right default; "
            "cloud SKUs can keep the formatter required. Your split of "
            "<font face='Courier'>required</font> already made that possible.",
            s["body"],
        )
    )

    h2("s4e", "4.5 Auth scopes for the CLI we love")
    story.append(
        P(
            "<font face='Courier'>aegis workflow run --follow</font> is a great operator "
            "experience. It 403’d without <font face='Courier'>workflow:logs</font>. Stock "
            "bootstrap listed <font face='Courier'>workflow:run/execute/deploy</font>. We added "
            "<font face='Courier'>workflow:logs</font>, <font face='Courier'>workflow:cancel</font>, "
            "<font face='Courier'>workflow:status</font>, and <font face='Courier'>execution:list</font> "
            "to <font face='Courier'>scripts/bootstrap-keycloak.sh</font>. Issuer is the "
            "browser-reachable URL (<font face='Courier'>127.0.0.1:8180</font>); JWKS from inside "
            "the mesh is <font face='Courier'>aegis-iam:8180</font>. For local MCP we used "
            "<font face='Courier'>BYPASS_AUTH=true</font> (still requires a Bearer string) while "
            "that split is sorted. Offering this as a bootstrap completeness patch, not a "
            "security argument.",
            s["body"],
        )
    )

    h2("s4f", "4.6 VALIDATE on a small judge")
    story.append(
        P(
            "The validator’s contract is structural: <font face='Courier'>def solve(inputs)</font>, "
            "reads <font face='Courier'>INTENT_INPUTS</font>, prints JSON, stdlib only. That is a "
            "thoughtful gate. On a 7–27B local judge it is also a second generate plus a "
            "mandatory <font face='Courier'>fs.read</font>. On the successful run the judge wrote "
            "both “INTENT_INPUTS is empty/{} so this criterion is automatically satisfied” "
            "<i>and</i> “consumes inputs from environment” in the same object. The pipeline still "
            "passed because it emitted <font face='Courier'>valid: true</font>.",
            s["body"],
        )
    )
    story.append(
        P(
            "A deterministic AST/linter path for those six checks — with the LLM judge optional "
            "behind a flag, file bytes injected so you skip the tool-turn — would make your "
            "already-good gate cheaper on small models. We would use it immediately.",
            s["body"],
        )
    )

    h2("s4g", "4.7 Metrics so Grafana agrees with /health")
    story.append(
        P(
            "Grafana showed runtime, Keycloak, and OpenBao as down while "
            "<font face='Courier'>/health</font> was live. Scrapes hit loopback metrics on 9091 "
            "(the proxy is 9092); Keycloak needed <font face='Courier'>--metrics-enabled=true</font>; "
            "OpenBao needed an unauthenticated scrape listener. None of that is SLM-related. We "
            "fixed it locally so a first-time operator can trust the dashboards you already built. "
            "Those three flags belong in the default compose.",
            s["body"],
        )
    )

    h1("s5", "5. How we optimized the local model (no new GPU)")
    story.append(
        P(
            "AEGIS is model-agnostic — that is one of its strengths. We started with "
            "Bonsai 27B Q1_0 because it <i>fits</i> 6 GB. It is not fast there. VRAM sat at "
            "5880/6144 MiB. llama.cpp: 56 GPU layers, ctx 8192, parallel 4, KV cache f16, "
            "<font face='Courier'>--threads 2</font> on a 6-thread CPU, plus a BF16 mmproj for a "
            "coding task that never sees an image. NodeConfig had "
            "<font face='Courier'>context_window: 32768</font> and "
            "<font face='Courier'>max_output_tokens: 8192</font>, which is generous for cloud "
            "and expensive for a local generate. We tightened the aliases rather than fighting "
            "the orchestrator.",
            s["body"],
        )
    )
    story.append(
        table(
            ["Change", "Before", "After", "Why"],
            [
                [
                    "Weights",
                    "Bonsai-27B Q1_0 (extreme quant, thinking)",
                    "Qwen2.5-Coder-7B-Instruct Q4_K_M",
                    "7B coder is the honest SKU for 6 GB. 27B Q1 still fits; we keep it on disk as a stretch option.",
                ],
                [
                    "Thinking",
                    "On (first VALIDATE burned 300 s with no tool call)",
                    "Off",
                    "Reasoning tokens are not free on 6 GB. First success required this.",
                ],
                [
                    "Load flags",
                    "ctx 8192, parallel 4, n-gpu-layers 25 (UI default on Qwen)",
                    "<font face='Courier'>lms load --gpu max -c 4096 --parallel 1</font> → n-gpu-layers 999999",
                    "UI default only offloaded 25/28-ish Qwen layers. Max offload + parallel 1 is the 1660 Ti profile.",
                ],
                [
                    "Aliases",
                    "All aliases → Bonsai, max_output 8192/4096",
                    "All aliases → <font face='Courier'>qwen2.5-coder-7b-instruct</font>, 2048 / judge 1024, ctx 4096, temp 0.3/0.1",
                    "Builtins request alias <font face='Courier'>default</font>. One wrong alias silently goes back to 27B.",
                ],
                [
                    "Formatter",
                    "required, 300–600 s, Temporal ×3",
                    "required false, 15 s",
                    "Your output_template already has stdout. Formatter becomes best-effort locally.",
                ],
                [
                    "FSM visits",
                    "WRITE/VALIDATE/EXECUTE visits 3; EXECUTION_FAILED loops to WRITE",
                    "visits 1",
                    "Retry loops are perfect for cloud. Local SLM fails once so we can inspect."
                ],
            ],
            [1.15 * inch, 1.85 * inch, 2.15 * inch, 1.85 * inch],
        )
    )
    story.append(P("Table 4. Local-model changes we made so AEGIS could show off on a 1660 Ti.", s["caption"]))
    story.append(
        P(
            "Live check after reload, 21 August 2026 evening: LM Studio identifier "
            "<font face='Courier'>qwen2.5-coder-7b-instruct</font>, 4.36 GiB estimated, 5222 MiB "
            "VRAM used, ctx 4096, parallel 1, flash-attn on. Chat completions "
            "<font face='Courier'>pong</font> in 0.38 s. Core NodeConfig and overlay 1.0.4 are "
            "pointed at that id. Bonsai remains on disk as an optional stretch model.",
            s["body"],
        )
    )
    story.append(
        P(
            "Honest leftover knobs (LM Studio, not AEGIS): llama.cpp is still "
            "<font face='Courier'>--threads 2</font> because <font face='Courier'>lms load</font> "
            "has no threads flag; KV cache is still f16; the embedding model stays listed on "
            "<font face='Courier'>/v1/models</font>. The OpenAI proxy on 0.0.0.0:1234 is the "
            "correct target from pods once the host-gateway patch is applied.",
            s["body"],
        )
    )

    h1("s6", "6. What we added in the deploy fork")
    story.append(
        P(
            "Fork: <font face='Courier'>github.com/ar-fullsend/aegis-deploy</font>, built on your "
            "stack. MCP wiring is already pushed; the Qwen, timeout, and host-gateway work is in "
            "the working tree and will land as Conventional Commits. These are operator "
            "improvements on top of AEGIS, offered upstream if you want them:",
            s["body"],
        )
    )
    story.append(
        table(
            ["Area", "Change"],
            [
                [
                    "MCP",
                    "Pod <font face='Courier'>aegis-mcp</font>, image <font face='Courier'>ghcr.io/100monkeys-ai/zaru-mcp-server</font>, hostPort 8090, development+full profiles, Caddy <font face='Courier'>DOMAIN_MCP</font>, validate-stack health. initialize → zaru-mcp-server 0.15.0-pre-alpha; tools/list returns orchestrator tools.",
                ],
                [
                    "Overlays",
                    "<font face='Courier'>manifests/slow-slm/</font> now v1.0.4. Writer overall 15 m, validator 20 m / 10 m generate, formatter 10 m then 15 s required=false. <font face='Courier'>make overlays</font> after every core start.",
                ],
                [
                    "Host gateway",
                    "<font face='Courier'>scripts/patch-host-gateway.sh</font> + detect LAN src from default route. Wired into <font face='Courier'>deploy.sh</font> and <font face='Courier'>make redeploy POD=core</font>.",
                ],
                [
                    "Keycloak",
                    "hostname-url 127.0.0.1:8180, metrics enabled, extra workflow/execution scopes.",
                ],
                [
                    "Observability",
                    "Runtime metrics-proxy :9092, OpenBao unauthenticated metrics on listener, Grafana jobs use max(up{job=…}) where we touched dashboards.",
                ],
                [
                    "FUSE",
                    "User unit ExecStart=%h/.local/bin/aegis, StartLimitIntervalSec=0. Kali is not Ubuntu; setup.sh had to be allowed to proceed.",
                ],
            ],
            [1.4 * inch, 5.6 * inch],
        )
    )
    story.append(P("Table 5. Deploy-fork additions we would be glad to contribute back.", s["caption"]))

    h1("s7", "7. Ideas we would love to see upstream")
    story.append(
        P(
            "Your documentation is already ambitious and useful — we leaned on it all day. "
            "These are optional product enhancements, not a request for more prose. We would "
            "be honored if any of them fit the roadmap.",
            s["body"],
        )
    )
    story.append(
        P(
            "1. <b>A first-class local-SLM profile.</b> You already have profiles "
            "(minimal / development / full). A sibling that (a) maps host LLM via a tested "
            "gateway, (b) sets overall ≥ iterations × per-call, (c) best-efforts the formatter, "
            "(d) uses a cheap structural validator, (e) keeps operator overlays across core "
            "start would make AEGIS shine on the hardware people actually have.",
            s["body"],
        )
    )
    story.append(
        P(
            "2. <b>An optional deterministic VALIDATE.</b> Keep the LLM judge — it is a good "
            "idea — behind a flag, and inject file bytes so a small model does not pay a "
            "tool-turn. Today a 7B can claim INTENT_INPUTS is empty when the env is "
            "<font face='Courier'>{\"n\":10}</font>.",
            s["body"],
        )
    )
    story.append(
        P(
            "3. <b>Treat formatter as post-processing when ContainerRun exits 0.</b> Your "
            "<font face='Courier'>required</font> flag already supports this. Making "
            "best-effort the default on a local profile would spare operators a 15-minute "
            "<font face='Courier'>Activity task failed</font> after a 600 ms success.",
            s["body"],
        )
    )
    story.append(
        P(
            "4. <b>Bootstrap scopes that match the CLI.</b> Adding "
            "<font face='Courier'>workflow:logs</font> so <font face='Courier'>--follow</font> "
            "works out of the box. A short note on issuer vs JWKS for rootless pods would "
            "help everyone who copies the getting-started path.",
            s["body"],
        )
    )
    story.append(
        P(
            "5. <b>A recommended local model in getting started.</b> Qwen2.5-Coder-7B Q4_K_M "
            "is a kind default for 6–8 GB cards. 27B remains a great stretch goal when VRAM "
            "allows. AEGIS being model-agnostic is the point — a suggested SKU just shortens "
            "the first afternoon.",
            s["body"],
        )
    )
    story.append(
        P(
            "6. <b>MCP health that names optional pieces.</b> Zaru as a SEAL proxy is the "
            "right shape — we wired <font face='Courier'>ghcr.io/100monkeys-ai/zaru-mcp-server</font> "
            "and it listed orchestrator tools immediately. Missing "
            "<font face='Courier'>ZARU_CLIENT_URL</font> only affects User Memory; surfacing "
            "that in the health payload would be a polish item, not a redesign.",
            s["body"],
        )
    )

    h1("s8", "8. Scope and humility")
    story.append(
        P(
            "We have not yet load-tested Qwen through the full FSM; the 0.38 s pong is a "
            "provider smoke test, not a WRITE+VALIDATE+EXECUTE measurement. We have not "
            "enabled Gemini. We have not deployed edge TLS. We used "
            "<font face='Courier'>BYPASS_AUTH</font> on MCP as a local convenience while "
            "issuer and JWKS disagree — that is not a production posture. OpenBao root tokens "
            "live in <font face='Courier'>generated/</font>, gitignored, as your layout "
            "intended.",
            s["body"],
        )
    )
    story.append(
        P(
            "What we <b>are</b> glad to report: your control plane executed user-generated "
            "Python in an isolated container, with a workspace volume, a Temporal FSM, and a "
            "correct numeric result, on a GTX 1660 Ti. That is the system you built. We are "
            "grateful for it, and we hope the local-SLM work helps the next operator get there "
            "faster.",
            s["body"],
        )
    )

    h1("s9", "Appendix — knobs live on this node")
    story.append(
        P(
            "LM Studio load: <font face='Courier'>lms load qwen2.5-coder-7b-instruct --gpu max -c 4096 --parallel 1 -y</font>. "
            "AEGIS apply: <font face='Courier'>make overlays</font> after every "
            "<font face='Courier'>podman restart aegis-core-aegis-runtime</font>. "
            "Host gateway: <font face='Courier'>make redeploy POD=core</font> already calls "
            "<font face='Courier'>scripts/patch-host-gateway.sh</font>. "
            "Token: client_credentials <font face='Courier'>aegis-runtime</font> against realm "
            "<font face='Courier'>aegis-system</font>. "
            "Successful fib execution id: <font face='Courier'>19939581-953f-4c43-92a5-97de0c2d958f</font>.",
            s["body"],
        )
    )
    story.append(
        P(
            "UIs (all 127.0.0.1): runtime 8088, Keycloak 8180, Temporal 8233, SEAL 8089, MCP 8090, "
            "OpenBao 8200, Grafana 3300, Prometheus 9090, Jaeger 16686, Seaweed filer 8888 / master 9333, "
            "LM Studio 1234.",
            s["body"],
        )
    )
    story.append(Spacer(1, 16))
    story.append(
        P(
            "The complete unified diff is the next appendix — every overlay, config, script, "
            "and doc change from today, so you can read or apply it without cloning our fork.",
            s["body"],
        )
    )

    flow_diff(story, s)

    story.append(Spacer(1, 16))
    story.append(
        P(
            "With respect and thanks — we will take a Qwen-backed fib run next. This document "
            "covers the Bonsai era plus the cutover. Overlay YAMLs and the unified diff above "
            "are yours if you want them upstream. AEGIS is a remarkable piece of work.",
            s["body"],
        )
    )

    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=letter,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
        topMargin=0.85 * inch,
        bottomMargin=0.75 * inch,
        title="AEGIS local-SLM field report — 21 August 2026",
        author="Local AEGIS operator (ar-fullsend/aegis-deploy)",
        subject="With thanks: how we ran AEGIS locally on a 6 GB GPU and the improvements we made",
        creator="AEGIS field report generator",
        lang="en-US",
    )
    doc.build(story, onFirstPage=cover, onLaterPages=header_footer)
    return OUT


if __name__ == "__main__":
    path = build()
    print(path)
