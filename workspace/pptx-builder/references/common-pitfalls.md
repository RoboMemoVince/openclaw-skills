# Common Pitfalls in PPTX Building

Detailed examples with coordinate calculations for the most frequent layout bugs.

---

## 1. Caption Overlaps Footer

**Symptom**: Figure caption text ("图: ...") overlaps with page number, "Confidential" mark, or logo at the bottom of the slide.

**Root cause**: Image region extends too close to the page bottom. When the image fills the region's height, the caption (placed below the image) lands in the footer area.

**Example calculation** (13.34" x 7.50" slide):
```
Footer area starts at:     ~7.05" (page number + confidential mark)
Caption height:             0.35"
Gap image→caption:          0.10"
→ Image bottom must be:    < 7.05 - 0.35 - 0.10 = 6.60"

If image region top = 3.05:
→ Max image region height = 6.60 - 3.05 = 3.55"

WRONG:  height = SH - top - 0.7  = 3.75"  → caption at 6.90" (overlaps!)
RIGHT:  height = SH - top - 1.2  = 3.25"  → caption at 6.40" (safe)
```

**Fix pattern**:
```python
FOOTER_RESERVE = 0.8   # footer + logo area
CAPTION_SPACE = 0.5    # caption height + gap
IMAGE = SlideRegion(
    left, top, width,
    SH - top - FOOTER_RESERVE - CAPTION_SPACE
)
```

---

## 2. Placeholder Overflow Overlap

**Symptom**: Text on the title slide appears garbled — characters from two text elements rendered on top of each other.

**Root cause**: Template placeholders have fixed heights. If you put more text than fits (e.g., 48pt title + 24pt subtitle = 1.3" needed, but placeholder is 0.75" tall), the text overflows the placeholder boundary. If another placeholder is positioned right below, the overflowed text renders on top of the second placeholder's content.

**Example**:
```
Placeholder "Title":    y=0.99, height=0.75 → bottom at 1.74
Placeholder "Subtitle": y=2.13
Content in Title: "ProjectX" (48pt = 0.67") + 2 lines (24pt = 0.67") = 1.34"
→ Text extends from 0.99 to 0.99+1.34 = 2.33" → overlaps Subtitle at 2.13!
```

**Fix**: Don't use template placeholders for content that might overflow. Remove them and create explicit text boxes:
```python
# Remove the problematic placeholders
for shape in slide.shapes:
    if shape.has_text_frame and shape.name in ('Title', 'Subtitle'):
        shape._element.getparent().remove(shape._element)

# Create separate text boxes with adequate height
tb1 = slide.shapes.add_textbox(Inches(1.0), Inches(0.8), Inches(7.0), Inches(0.9))
# ... title content ...
tb2 = slide.shapes.add_textbox(Inches(1.0), Inches(1.8), Inches(7.0), Inches(1.2))
# ... subtitle content ...
```

---

## 3. Content Text Box Overlaps Footer

**Symptom**: On text-heavy pages (TOC, bullet lists), the last lines of text overlap with the footer area.

**Root cause**: Text box height set too large — the box extends into the footer area even if the text doesn't visually fill it. In some renderers, the text box boundary causes rendering conflicts.

**Example**:
```
Text box: y=1.3, height=5.8 → bottom at 7.1
Footer:   y=7.05
→ Box extends 0.05" into footer area
```

**Fix**: Calculate max height to stay above footer:
```python
max_height = SH - FOOTER_RESERVE - text_top  # e.g., 7.5 - 0.8 - 1.3 = 5.4
```

Also consider reducing font size or removing spacing if content is tight.

---

## 4. Evidence Page: Caption Spans Full Width

**Symptom**: On a two-column layout (text left, image right), the caption below the image spans the full page width, overlapping with the left-side text column.

**Root cause**: Caption uses `left=MARGIN, width=SW-2*MARGIN` (full width) instead of being scoped to the image column.

**Fix**: Scope caption to the image column:
```python
# WRONG
add_caption(slide, text, left=MARGIN, top=cap_top, width=SW - 2*MARGIN)

# RIGHT
add_caption(slide, text, left=IMAGE_REGION.left, top=cap_top, width=IMAGE_REGION.width)
```

---

## 5. Two-Image Stack: Second Image Overlaps First URL

**Symptom**: On evidence pages with two stacked screenshots, the second image overlaps with the URL box below the first image.

**Root cause**: Second image region uses a fixed y position instead of being calculated dynamically from the first image's actual position + URL height.

**Fix**: Chain positions dynamically:
```python
# Image 1
al1, at1, aw1, ah1 = add_real_image(slide, img1, REGION_1)
url1_top = at1 + ah1 + 0.05
add_url_box(slide, url1, left=REGION_1.left, top=url1_top, width=REGION_1.width)

# Image 2 region starts AFTER url1
img2_top = url1_top + 0.35 + 0.1  # URL height + gap
img2_region = SlideRegion(
    REGION_1.left, img2_top,
    REGION_1.width, SH - img2_top - FOOTER_RESERVE
)
al2, at2, aw2, ah2 = add_real_image(slide, img2, img2_region)
```

---

## 6. Image Not Centered in Region

**Symptom**: Image is flush-left or flush-top in its region instead of being centered.

**Root cause**: Using `region.left` and `region.top` directly without centering calculation.

**Fix**: Always center horizontally, and use `valign` parameter for vertical:
```python
actual_left = region.left + (region.width - w_in) / 2   # H-center
if valign == "top":
    actual_top = region.top                                # V-top
else:
    actual_top = region.top + (region.height - h_in) / 2  # V-center
```

**When to use which valign:**
- `"top"` — When image is below text (Layout C). Keeps image close to the text above.
- `"center"` — When image is beside text (Layout D). Looks balanced in the column.

---

## 7. EMU vs Inches Type Confusion

**Symptom**: Image placed at wrong position or with wrong size — numbers are off by a factor of 914400.

**Root cause**: python-pptx uses EMU (English Metric Units) internally. 1 inch = 914400 EMU. If you mix EMU values with inch calculations, results are wildly wrong.

**Fix**: Always convert to inches immediately when reading positions:
```python
# Reading positions FROM a shape
left_inches = shape.left / 914400

# Setting positions ON a shape — always use Inches()
slide.shapes.add_picture(path, Inches(left), Inches(top), Inches(w), Inches(h))
```

---

## 8. LibreOffice vs PowerPoint Rendering Differences

**Symptom**: PPT looks different in LibreOffice (used for PNG export) vs PowerPoint (final delivery).

**Known differences**:
- Font metrics vary slightly → line breaks may differ
- Some gradient/shadow effects render differently
- CJK fonts may fall back to different fonts

**Mitigation**:
- Use common fonts (Arial, Calibri, Noto Sans CJK)
- Don't rely on pixel-perfect text wrapping
- Leave 10-15% margin in text boxes for font variation
- Final verification should be in PowerPoint if possible

---

## Debugging Workflow

When a layout bug is found:

1. **Identify** the exact problem: What overlaps what? What's in the wrong position?
2. **Calculate** the actual coordinates:
   ```python
   for shape in slide.shapes:
       l, t = shape.left/914400, shape.top/914400
       w, h = shape.width/914400, shape.height/914400
       print(f"{shape.name}: ({l:.2f}, {t:.2f}) size ({w:.2f}, {h:.2f}) bottom={t+h:.2f}")
   ```
3. **Trace** back to the code that created the shape — which region/constant is wrong?
4. **Fix** the region constant or placement logic with explicit coordinate math
5. **Rebuild → Export → Verify** the fix visually
