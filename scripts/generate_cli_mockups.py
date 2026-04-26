from pathlib import Path

from PIL import Image, ImageDraw, ImageFont


ROOT = Path(__file__).resolve().parents[1]
OUT_DIR = ROOT / "docs" / "superpowers" / "mockups"


def font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "/System/Library/Fonts/SFNSMono.ttf",
        "/System/Library/Fonts/Menlo.ttc",
        "/Library/Fonts/Arial Unicode.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def rounded(draw: ImageDraw.ImageDraw, box, radius, fill, outline=None, width=1):
    draw.rounded_rectangle(box, radius=radius, fill=fill, outline=outline, width=width)


def text(draw, xy, value, fill=(230, 230, 230), size=18):
    draw.text(xy, value, fill=fill, font=font(size))


def make_scrolling_log():
    img = Image.new("RGB", (1200, 820), (12, 15, 18))
    draw = ImageDraw.Draw(img)

    rounded(draw, (40, 40, 1160, 780), 22, (20, 24, 28), (68, 76, 86), 2)
    rounded(draw, (40, 40, 1160, 104), 22, (28, 35, 46), (68, 76, 86), 2)
    text(draw, (76, 62), "Lios-Agent", (126, 203, 255), 24)
    text(draw, (232, 66), "Active Mode", (170, 178, 189), 18)
    text(draw, (980, 66), "workspace: mobile-app", (122, 132, 145), 16)

    y = 142
    rows = [
        (">", "Analyzing request", "Parsing goal and workspace context", (94, 196, 255)),
        ("i", "Read", "cli.py", (126, 203, 255)),
        ("i", "Read", "agent/repl.py", (126, 203, 255)),
        ("✓", "Context loaded", "2 files inspected", (93, 214, 139)),
        ("", "", "", (0, 0, 0)),
        (">", "Planning next action", "Need CLI surface for active agent execution", (94, 196, 255)),
        ("•", "Todo", "Implement adaptive terminal renderer", (238, 198, 91)),
        ("•", "Todo", "Stream agent events to renderer", (238, 198, 91)),
        ("✓", "Plan ready", "3 execution steps", (93, 214, 139)),
        ("", "", "", (0, 0, 0)),
        ("⠋", "Executing step 1", "Update CLI command flow", (238, 198, 91)),
        ("  ", "Patch", "agent/repl.py", (170, 178, 189)),
        ("  ", "Patch", "cli.py", (170, 178, 189)),
        ("✓", "Step complete", "Renderer wired into execution loop", (93, 214, 139)),
        ("", "", "", (0, 0, 0)),
        ("⠙", "Running verification", "pytest tests/test_cli.py", (238, 198, 91)),
    ]

    for symbol, label, detail, color in rows:
        if not label:
            y += 22
            continue
        rounded(draw, (74, y - 8, 110, y + 28), 10, (30, 36, 42), None)
        text(draw, (86, y - 2), symbol, color, 18)
        text(draw, (134, y), label, (232, 235, 238), 19)
        text(draw, (430, y + 1), detail, (143, 153, 166), 17)
        y += 42

    rounded(draw, (72, 704, 1128, 738), 12, (14, 18, 22), (55, 64, 74), 1)
    text(draw, (94, 711), "You can still scroll back through every event after execution finishes.", (130, 140, 153), 16)

    img.save(OUT_DIR / "cli-scrolling-log.png")


def make_live_dashboard():
    img = Image.new("RGB", (1200, 820), (9, 12, 16))
    draw = ImageDraw.Draw(img)

    rounded(draw, (36, 34, 1164, 104), 22, (25, 32, 43), (71, 84, 101), 2)
    text(draw, (70, 58), "Lios-Agent", (126, 203, 255), 25)
    text(draw, (230, 62), "Active Execution Dashboard", (210, 217, 226), 19)
    rounded(draw, (944, 58, 1128, 86), 12, (48, 37, 18), (118, 89, 31), 1)
    text(draw, (964, 63), "Status: Executing", (238, 198, 91), 15)

    rounded(draw, (36, 126, 788, 700), 20, (18, 22, 27), (68, 76, 86), 2)
    rounded(draw, (812, 126, 1164, 700), 20, (18, 22, 27), (68, 76, 86), 2)

    text(draw, (70, 154), "Current Action", (232, 235, 238), 22)
    text(draw, (846, 154), "Plan", (232, 235, 238), 22)

    rounded(draw, (70, 202, 754, 354), 18, (27, 34, 42), (70, 89, 110), 1)
    text(draw, (100, 232), "Applying changes to `agent/repl.py`", (238, 198, 91), 21)
    text(draw, (100, 272), "Streaming agent state into an adaptive Rich layout.", (174, 184, 197), 18)
    text(draw, (100, 306), "Terminal size: 120 x 42  •  Renderer: dashboard", (126, 203, 255), 16)

    rounded(draw, (70, 386, 754, 646), 18, (14, 18, 22), (47, 57, 68), 1)
    text(draw, (100, 414), "Recent Events", (232, 235, 238), 19)
    events = [
        ("✓", "Loaded vault state", (93, 214, 139)),
        ("✓", "Generated execution plan", (93, 214, 139)),
        ("⠋", "Editing CLI renderer", (238, 198, 91)),
        ("•", "Queued verification", (143, 153, 166)),
    ]
    yy = 456
    for sym, body, color in events:
        text(draw, (104, yy), sym, color, 18)
        text(draw, (144, yy), body, (170, 178, 189), 18)
        yy += 42

    plan = [
        ("✓", "1. Analyze CLI flow", (93, 214, 139)),
        ("✓", "2. Choose renderer", (93, 214, 139)),
        ("⠋", "3. Edit active run UI", (238, 198, 91)),
        (" ", "4. Run tests", (143, 153, 166)),
        (" ", "5. Summarize results", (143, 153, 166)),
    ]
    yy = 210
    for sym, body, color in plan:
        rounded(draw, (846, yy - 8, 880, yy + 26), 9, (30, 36, 42), None)
        text(draw, (856, yy - 3), sym, color, 17)
        text(draw, (898, yy), body, color if sym.strip() else (143, 153, 166), 17)
        yy += 56

    rounded(draw, (846, 534, 1128, 642), 14, (27, 34, 42), (70, 89, 110), 1)
    text(draw, (870, 558), "Adaptive behavior", (232, 235, 238), 17)
    text(draw, (870, 590), "Wide: split dashboard", (143, 153, 166), 15)
    text(draw, (870, 614), "Narrow: compact log", (143, 153, 166), 15)

    rounded(draw, (36, 724, 1164, 774), 18, (16, 20, 25), (68, 76, 86), 1)
    text(draw, (70, 740), "Ctrl+C to interrupt  •  /status to inspect  •  /compact to switch layout", (130, 140, 153), 17)

    img.save(OUT_DIR / "cli-live-dashboard.png")


if __name__ == "__main__":
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    make_scrolling_log()
    make_live_dashboard()
    print(f"Generated {OUT_DIR / 'cli-scrolling-log.png'}")
    print(f"Generated {OUT_DIR / 'cli-live-dashboard.png'}")
