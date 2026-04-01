---
name: pptx-builder
description: |
  Build presentation slides programmatically with python-pptx from any corporate/custom template.
  Use when user asks to create, modify, or automate PowerPoint presentations.
platform: [openclaw, claude-code]
---

# PPTX Builder

Build presentation slides programmatically with python-pptx from any corporate/custom template. Handles layout design, image placement, content fitting, validation, and iterative visual review.

## When to Use

- User asks to create or modify a PowerPoint presentation
- User provides a template (.pptx) and content (text, images, or a content document)
- User wants to automate PPT generation from structured data
- User wants to fix layout/overlap issues in an existing PPT

## Workflow Overview

The PPT building process has 5 phases. **Never skip the review phase** — layout bugs are invisible in code and only surface visually.

```
Phase 1: Analyze Template
Phase 2: Design Layout System
Phase 3: Build Content
Phase 4: Validate (automated)
Phase 5: Visual Review → Fix → Re-review (iterative)
```

---

## Phase 1: Analyze Template

Before writing any code, understand the template:

```python
from pptx import Presentation
from pptx.util import Inches, Emu

prs = Presentation("template.pptx")

# 1. Get slide dimensions
w = prs.slide_width / 914400   # EMU to inches
h = prs.slide_height / 914400
print(f"Slide: {w:.2f}\" x {h:.2f}\"")  # e.g. 13.34 x 7.50 (widescreen)

# 2. List all slide layouts
for master in prs.slide_masters:
    for layout in master.slide_layouts:
        print(f"  Layout: {layout.name!r}")

# 3. Inspect placeholders on each layout
for layout in prs.slide_masters[0].slide_layouts:
    print(f"\n--- {layout.name} ---")
    for ph in layout.placeholders:
        l = ph.left/914400; t = ph.top/914400
        w = ph.width/914400; h = ph.height/914400
        print(f"  {ph.name!r} idx={ph.placeholder_format.idx} "
              f"pos=({l:.2f}, {t:.2f}, {w:.2f}, {h:.2f})")

# 4. Check for footer/watermark elements on existing slides
for i, slide in enumerate(prs.slides):
    for shape in slide.shapes:
        if shape.has_text_frame:
            txt = shape.text_frame.text[:60]
            l = shape.left/914400; t = shape.top/914400
            print(f"  Slide {i}: {shape.name!r} text={txt!r} y={t:.2f}")
```

**Key things to identify:**
- Slide dimensions (standard 10x7.5 vs widescreen 13.33x7.5)
- Which layout to use for content slides (usually a "blank" or "text" layout)
- **Footer area**: Where page numbers, confidential marks, logos are (typically y > 6.8")
- **Safe content area**: The region between title and footer where content can go

---

## Phase 2: Design Layout System

### The SlideRegion Pattern

**Never hardcode coordinates scattered across your build script.** Define a coordinate system once, then reference it everywhere.

```python
from dataclasses import dataclass

@dataclass
class SlideRegion:
    left: float; top: float; width: float; height: float

    @property
    def right(self): return self.left + self.width
    @property
    def bottom(self): return self.top + self.height

    def below(self, gap=0.15):
        """Top coordinate for placing something below this region."""
        return self.bottom + gap
```

### Calculating Layout Constants

For each slide type, define regions with these rules:

1. **Title region**: Fixed at top (e.g., y=0.4, height=0.7)
2. **Content start**: Below title (e.g., y=1.3)
3. **Footer reserve**: Leave at least **0.8"** at the bottom for footers/page numbers/logos
4. **Caption reserve**: If images have captions, reserve **0.5"** below the image region
5. **Gap between elements**: 0.1-0.2" minimum

```python
SW, SH = 13.34, 7.50   # From template analysis
MARGIN = 0.8
FOOTER_RESERVE = 0.8    # Space for page number + confidential mark + logo
CAPTION_HEIGHT = 0.4    # Caption text box height

# Example: Points above + Image below
TITLE = SlideRegion(MARGIN, 0.4, SW - 2*MARGIN, 0.7)
POINTS = SlideRegion(MARGIN, 1.3, SW - 2*MARGIN, 1.6)
# Image region: between points and footer, minus caption space
img_top = POINTS.below(0.15)
img_max_bottom = SH - FOOTER_RESERVE - CAPTION_HEIGHT - 0.1
IMAGE = SlideRegion(1.5, img_top, SW - 3.0, img_max_bottom - img_top)
```

**Critical rule**: `IMAGE.bottom + caption_height + gap < SH - FOOTER_RESERVE`

### Common Layout Types

| Layout | Structure | Use For |
|--------|-----------|---------|
| A | Title only | Cover slide |
| B | Full-page text | TOC, text-heavy |
| C | Points (top) + Image (bottom) | Background, examples |
| D | Points (left) + Image (right) | Feature details |
| E | Two-column text | Comparison, protection points |
| F | Points (left) + Screenshot (right) + URL | Evidence pages |

---

## Phase 3: Build Content

### Safe Image Placement

**The #1 source of layout bugs is image placement.** Always use this pattern:

```python
from PIL import Image as PILImage
from pptx.util import Inches

def add_real_image(slide, img_path, region, valign="center"):
    """Place image in region, maintaining aspect ratio.
    Returns (actual_left, actual_top, actual_w, actual_h) in inches.

    valign="center": vertically center in region (good for side images)
    valign="top": flush to top of region (good for below-text images)
    """
    img = PILImage.open(img_path)
    iw, ih = img.size
    aspect = iw / ih
    container_aspect = region.width / region.height

    if aspect > container_aspect:  # Wide image → fill width
        w_in = region.width
        h_in = region.width / aspect
    else:                          # Tall image → fill height
        h_in = region.height
        w_in = region.height * aspect

    # Always horizontally center
    actual_left = region.left + (region.width - w_in) / 2
    # Vertical alignment
    if valign == "top":
        actual_top = region.top
    else:
        actual_top = region.top + (region.height - h_in) / 2

    slide.shapes.add_picture(
        img_path, Inches(actual_left), Inches(actual_top),
        Inches(w_in), Inches(h_in))
    return actual_left, actual_top, w_in, h_in
```

### Dynamic Caption Placement

**Captions MUST follow the image**, not be placed at a fixed position:

```python
al, at, aw, ah = add_real_image(slide, img_path, IMAGE_REGION, valign="top")
if caption:
    cap_top = at + ah + 0.1  # Right below actual image bottom
    add_caption(slide, caption, left=MARGIN, top=cap_top, width=SW - 2*MARGIN)
```

### Title Slide: Avoid Placeholder Overflow

**Never put too much text in a template placeholder.** If the placeholder is 0.75" tall but your content needs 1.5", the text overflows and overlaps with elements below.

**Safe approach**: Remove template placeholders, create your own text boxes at explicit positions:

```python
# Remove placeholders
shapes_to_remove = [s for s in slide.shapes
                     if s.has_text_frame and 'Security' not in s.text_frame.text]
for s in shapes_to_remove:
    s._element.getparent().remove(s._element)

# Add explicit text boxes
tb = slide.shapes.add_textbox(Inches(1.0), Inches(0.8), Inches(7.0), Inches(0.9))
# ... set text, font, color
```

### Content Slides: Clear Placeholders First

```python
slide = prs.slides.add_slide(layout)
for ph in list(slide.placeholders):
    sp = ph._element
    sp.getparent().remove(sp)
# Now add your own content with explicit positioning
```

---

## Phase 4: Automated Validation

Run these checks after building every slide AND after the full PPT:

```python
def check_slide_overlaps(slide, slide_w, slide_h):
    """Check all shapes for overlap and out-of-bounds issues."""
    issues = []
    shapes = []
    for shape in slide.shapes:
        l = shape.left / 914400
        t = shape.top / 914400
        w = shape.width / 914400
        h = shape.height / 914400
        shapes.append((shape.name, l, t, l+w, t+h))
        if l + w > slide_w + 0.1:
            issues.append(f"'{shape.name}' right overflow: {l+w:.2f} > {slide_w}")
        if t + h > slide_h + 0.1:
            issues.append(f"'{shape.name}' bottom overflow: {t+h:.2f} > {slide_h}")
    # Pairwise overlap check (ignore tiny overlaps < 0.2")
    for i, (n1, l1, t1, r1, b1) in enumerate(shapes):
        for j, (n2, l2, t2, r2, b2) in enumerate(shapes):
            if i >= j: continue
            if l1 < r2 and r1 > l2 and t1 < b2 and b1 > t2:
                ow = min(r1,r2) - max(l1,l2)
                oh = min(b1,b2) - max(t1,t2)
                if ow > 0.2 and oh > 0.2:
                    issues.append(f"Overlap: '{n1}' & '{n2}' ({ow:.1f}x{oh:.1f}\")")
    return issues
```

Call after each slide: `_check_slide(slide, "Slide N title")`
Call after full PPT: loop all slides, report all issues.

---

## Phase 5: Visual Review (CRITICAL)

**Automated validation catches overlaps but NOT visual problems.** You MUST visually review every page.

### Export to PNG

```bash
# Method: LibreOffice → PDF → per-page PNG
libreoffice --headless --convert-to pdf --outdir /tmp/review output.pptx
pdftoppm -png -r 200 /tmp/review/output.pdf /tmp/review/slide
```

Or use the helper script: `python3 ~/.claude/skills/pptx-builder/scripts/export_slides.py <pptx_path>`

### Review Checklist (per page)

For EVERY page, check these 7 items:

1. **Title**: Visible? Correct font/color? Not overlapping with content below?
2. **Text content**: All text visible? No truncation? No overflow beyond text box?
3. **Image**: Present? Correctly sized? Horizontally centered in its region?
4. **Caption/subtitle**: Below the image (not at page bottom)? Not overlapping footer?
5. **Footer area**: Page number, confidential mark, logo — none overlapped by content?
6. **Spacing**: Reasonable gaps between title→content→image→caption→footer?
7. **Alignment**: Left-side text aligned? Right-side images aligned across slides?

### The Review-Fix Loop

```
Build PPT → Export PNG → Review ALL pages → List issues → Fix code → Rebuild → Re-review
```

**Rules:**
- Review ALL pages in one pass, not just the ones you think might have issues
- When fixing, calculate the actual coordinates with numbers — don't guess
- After fixing, re-export and re-review the fixed pages
- Continue until zero issues found

---

## Common Pitfalls & Fixes

See `references/common-pitfalls.md` for detailed examples with coordinate calculations.

**Top 5 bugs (ranked by frequency):**

| # | Bug | Root Cause | Fix |
|---|-----|-----------|-----|
| 1 | Caption overlaps footer | Image region too tall, no footer reserve | Subtract `FOOTER_RESERVE + CAPTION_HEIGHT` from image region |
| 2 | Title slide text garbled | Too much text in small placeholder | Remove placeholder, use explicit text boxes |
| 3 | Image not centered | Using raw `region.left` without centering calc | Use `add_real_image()` with centering logic |
| 4 | Text overflow into next element | Text box height too large, overlapping with element below | Calculate max height = next_element_top - current_top - gap |
| 5 | Caption detached from image | Caption at fixed y instead of dynamic | Caption y = actual_image_bottom + small_gap |

---

## Working with Figures

When generating figures for slides (e.g., with tech-figure-gen):

1. **Constraint**: Max 12 elements, labels ≤ 8 CJK chars or 15 Latin chars
2. **Style**: Use `--style slide --size landscape` for consistency
3. **Verify after generation**: Use Read tool to view each image — check content, readability, style
4. **Check dimensions**: File > 50KB and resolution > 800x400

## Working with Screenshots

For evidence/reference screenshots:

1. **Capture** the actual page showing the specific content you want to reference
2. **Annotate** with red boxes using Pillow to highlight key elements:
   ```python
   from PIL import Image, ImageDraw
   img = Image.open("screenshot.png")
   draw = ImageDraw.Draw(img)
   for box in boxes:  # [(x1,y1,x2,y2), ...]
       for i in range(4):  # 4px thick
           draw.rectangle([box[0]-i, box[1]-i, box[2]+i, box[3]+i], outline='red')
   img.save("annotated.png")
   ```
3. **Verify annotations**: Read the annotated image to confirm red boxes are on the right elements
4. **Reference in text**: The slide text should say exactly what the red boxes highlight

---

## File Organization

```
project/
├── template.pptx            # Original template (never modify)
├── build_template.py        # Shared: SlideRegion, layout constants, validation, helpers
├── build_ppt.py             # Main build script: content + assembly
├── figures/                  # Generated diagrams
├── screenshots/              # Raw screenshots
│   └── annotated/            # Red-box annotated versions
└── output.pptx               # Generated PPT
```

**Separation principle**: `build_template.py` has zero content — only layout/validation/helpers.
`build_ppt.py` has all content and calls into template helpers.

---

## Quick Start Checklist

When starting a new PPT project:

- [ ] Analyze template: dimensions, layouts, footer positions
- [ ] Define SlideRegion constants with footer/caption reserves
- [ ] Write `add_real_image()` with aspect-ratio + centering
- [ ] Write `check_slide_overlaps()` validator
- [ ] Build slides, validate each one
- [ ] Export to PNG, visually review ALL pages
- [ ] Fix issues, re-export, re-review
- [ ] Repeat until zero issues
