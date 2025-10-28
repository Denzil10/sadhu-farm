from __future__ import annotations

import csv
import json
import os
import tempfile
from base64 import b64encode
from io import BytesIO, StringIO
from pathlib import Path
from typing import Dict, Iterable

from PIL import Image, ImageDraw, ImageFont

import pdfkit
from flask import Flask, jsonify, render_template, request, send_file
from jinja2 import Environment, FileSystemLoader, select_autoescape
from markupsafe import Markup

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
TEMPLATE_NAME = "new_back.html"


def _load_template_env() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(ASSETS_DIR)),
        autoescape=select_autoescape(("html", "xml")),
    )


TEMPLATE_ENV = _load_template_env()
LABEL_TEMPLATE = TEMPLATE_ENV.get_template(TEMPLATE_NAME)

FONT_PATH = ASSETS_DIR / "Inter_18pt-SemiBold.ttf"
PRESET_FILE = ASSETS_DIR / "presets.json"

DEFAULT_DATA: Dict[str, str] = {
    "product_name": "Signature Cocoa",
    "desc": (
        "Indulge in the rich, decadent pleasure of our cocoa couverture — "
        "a delightful treat crafted with care on our family farm."
    ),
    "ing": "Cocoa nibs (65%), Cane sugar, Cocoa butter, Sunflower lecithin, Vanilla bean",
    "cont": "Milk, soy",
    "may": "Tree nuts, wheat",
    "energy_amt": "608",
    "energy_dv": "30%",
    "protein_amt": "6.2",
    "protein_dv": "12%",
    "fat_total_amt": "49.0",
    "fat_total_dv": "75%",
    "fat_sat_amt": "33.6",
    "fat_sat_dv": "168%",
    "fat_trans_amt": "0",
    "fat_trans_dv": "0%",
    "chol_amt": "0",
    "chol_dv": "0%",
    "carb_total_amt": "42.4",
    "carb_total_dv": "14%",
    "sugar_total_amt": "25.5",
    "sugar_total_dv": "51%",
    "sugar_added_amt": "25.5",
    "sugar_added_dv": "51%",
    "fiber_amt": "11.0",
    "fiber_dv": "44%",
    "sodium_amt": "46",
    "sodium_dv": "2%",
    "price": "520",
    "batch": "BC-2409-07",
    "mfg": "2024-09-15",
    "expiry": "2025-03-15",
    "maker": "Sadhu Farm Foods Pvt. Ltd.",
    "addr": "42 Bean Estate\nPollachi, Tamil Nadu 642001\nIndia",
}

MULTILINE_FIELDS = {"desc", "ing", "may", "addr"}

QUICK_FIELDS = (
    {"name": "batch", "label": "Batch Code", "type": "text"},
    {"name": "mfg", "label": "Manufacture Date", "type": "date"},
    {"name": "expiry", "label": "Expiry Date", "type": "date"},
)

FIELD_GROUPS = (
    (
        "Preset",
        (
            {"name": "product_name", "label": "Product Name", "type": "text"},
            {"name": "price", "label": "Unit Price (₹/kg)", "type": "text"},
        ),
    ),
    (
        "Product & Allergens",
        (
            {"name": "desc", "label": "Description", "type": "textarea", "rows": 3},
            {"name": "ing", "label": "Ingredients", "type": "textarea", "rows": 4},
            {"name": "cont", "label": "Contains", "type": "text"},
            {"name": "may", "label": "May Contain", "type": "textarea", "rows": 2},
        ),
    ),
    (
        "Nutrition (Amount per 100g)",
        (
            {"name": "energy_amt", "label": "Energy (kcal)", "type": "text"},
            {"name": "protein_amt", "label": "Protein (g)", "type": "text"},
            {"name": "fat_total_amt", "label": "Total Fat (g)", "type": "text"},
            {"name": "fat_sat_amt", "label": "Saturated Fat (g)", "type": "text"},
            {"name": "fat_trans_amt", "label": "Trans Fat (g)", "type": "text"},
            {"name": "chol_amt", "label": "Cholesterol (mg)", "type": "text"},
            {"name": "carb_total_amt", "label": "Total Carbs (g)", "type": "text"},
            {"name": "sugar_total_amt", "label": "Total Sugars (g)", "type": "text"},
            {"name": "sugar_added_amt", "label": "Added Sugars (g)", "type": "text"},
            {"name": "fiber_amt", "label": "Dietary Fiber (g)", "type": "text"},
            {"name": "sodium_amt", "label": "Sodium (mg)", "type": "text"},
        ),
    ),
    (
        "Nutrition (% Daily Value)",
        (
            {"name": "energy_dv", "label": "Energy %DV", "type": "text"},
            {"name": "protein_dv", "label": "Protein %DV", "type": "text"},
            {"name": "fat_total_dv", "label": "Total Fat %DV", "type": "text"},
            {"name": "fat_sat_dv", "label": "Saturated Fat %DV", "type": "text"},
            {"name": "fat_trans_dv", "label": "Trans Fat %DV", "type": "text"},
            {"name": "chol_dv", "label": "Cholesterol %DV", "type": "text"},
            {"name": "carb_total_dv", "label": "Total Carbs %DV", "type": "text"},
            {"name": "sugar_total_dv", "label": "Total Sugars %DV", "type": "text"},
            {"name": "sugar_added_dv", "label": "Added Sugars %DV", "type": "text"},
            {"name": "fiber_dv", "label": "Dietary Fiber %DV", "type": "text"},
            {"name": "sodium_dv", "label": "Sodium %DV", "type": "text"},
        ),
    ),
    (
        "Manufacturer",
        (
            {"name": "maker", "label": "Manufacturer", "type": "text"},
            {"name": "addr", "label": "Address", "type": "textarea", "rows": 3},
        ),
    ),
)

ALL_FIELD_NAMES = (
    *(field["name"] for field in QUICK_FIELDS),
    *(field["name"] for _, group in FIELD_GROUPS for field in group),
)

app = Flask(__name__)


def load_presets() -> Dict[str, Dict[str, str]]:
    if not PRESET_FILE.exists():
        return {}
    try:
        return json.loads(PRESET_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_presets(presets: Dict[str, Dict[str, str]]) -> None:
    PRESET_FILE.parent.mkdir(parents=True, exist_ok=True)
    PRESET_FILE.write_text(json.dumps(presets, indent=2, ensure_ascii=False), encoding="utf-8")


def _normalize_preset_row(row: Dict[str, str]) -> Dict[str, str]:
    trimmed = {name: row.get(name, "").strip() for name in ALL_FIELD_NAMES}
    merged = _merge_defaults(trimmed)
    if trimmed.get("product_name"):
        merged["product_name"] = trimmed["product_name"]
    return merged


@app.route("/assets/<path:filename>")
def serve_asset(filename):
    """Serve static assets from the assets directory."""
    return send_file(ASSETS_DIR / filename)

@app.route("/test")
def test_bg():
    """Test background image visibility."""
    return send_file("simple_test.html")

@app.route("/ultra")
def ultra_test():
    """Ultra simple background test."""
    return send_file("ultra_simple.html")


def _escape_multiline(value: str) -> Markup:
    """Escape user text and preserve line breaks."""
    if not value:
        return Markup("")
    escaped = Markup.escape(value)
    return Markup("<br>").join(escaped.splitlines())


def build_context(form_values: Dict[str, str], for_pdf: bool = False) -> Dict[str, str]:
    context: Dict[str, str] = {}
    for key, raw in form_values.items():
        stripped = raw.strip()
        if key in MULTILINE_FIELDS:
            context[key] = _escape_multiline(stripped)
        else:
            context[key] = stripped

    # Handle custom nutrition fields
    custom_nutrition = _process_custom_nutrition(form_values)
    if custom_nutrition:
        context["custom_nutrition"] = custom_nutrition

    bg_candidates = ("base.png", "base.png")
    bg_path = next(
        (ASSETS_DIR / candidate for candidate in bg_candidates if (ASSETS_DIR / candidate).exists()),
        None,
    )
    if bg_path is None:
        raise FileNotFoundError("Background frame not found in assets.")
    if for_pdf:
        # Use absolute path for wkhtmltopdf
        context["bg_url"] = str(bg_path.resolve())
    else:
        context["bg_url"] = f"/assets/{bg_path.name}"

    logo_candidates = ("logo.png", "fssai.png")
    logo_path = next(
        (ASSETS_DIR / candidate for candidate in logo_candidates if (ASSETS_DIR / candidate).exists()),
        None,
    )

    if logo_path:
        if for_pdf:
            # Use absolute path for wkhtmltopdf
            context["logo_url"] = str(logo_path.resolve())
        else:
            context["logo_url"] = f"/assets/{logo_path.name}"

    font_face = _build_font_face()
    if font_face:
        context["font_face"] = font_face
    return context


def render_label_html(context: Dict[str, str]) -> str:
    return LABEL_TEMPLATE.render(**context)


def create_sticker_sheet_with_images(single_sticker_html: str) -> bytes:
    """Create A4 PDF using image manipulation approach."""
    from PIL import Image, ImageDraw
    import pdfkit
    from io import BytesIO
    
    # A4 dimensions at 300 DPI
    A4_WIDTH_PX = 2480  # 210mm * 300 DPI / 25.4
    A4_HEIGHT_PX = 3508  # 297mm * 300 DPI / 25.4
    
    # Label dimensions (scaled down to fit 4 on A4)
    LABEL_WIDTH_PX = 600  # ~50mm
    LABEL_HEIGHT_PX = 750  # ~63mm
    
    # Create A4 canvas
    a4_image = Image.new('RGB', (A4_WIDTH_PX, A4_HEIGHT_PX), 'white')
    
    # Generate single label as image
    # First create a temporary HTML file for the single label
    temp_html = f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="utf-8">
        <style>
            @page {{ size: {LABEL_WIDTH_PX}px {LABEL_HEIGHT_PX}px; margin: 0; }}
            body {{ margin: 0; padding: 0; }}
        </style>
    </head>
    <body>
        {single_sticker_html}
    </body>
    </html>
    """
    
    # Generate PDF for single label
    single_label_pdf = pdfkit.from_string(temp_html, False, options={
        "page-size": "A4",
        "margin-top": "0mm",
        "margin-bottom": "0mm",
        "margin-left": "0mm",
        "margin-right": "0mm",
        "encoding": "UTF-8",
        "enable-local-file-access": "",
        "disable-smart-shrinking": "",
        "print-media-type": "",
        "dpi": "300",
    })
    
    # For now, let's use a simpler approach - create the A4 layout directly
    return create_simple_a4_layout(single_sticker_html)


def create_simple_a4_layout(single_sticker_html: str) -> str:
    """Create a simple A4 layout that works with the original single sticker logic."""
    # Extract just the article content from the HTML
    import re
    article_match = re.search(r"<article[^>]*>(?P<article>.*)</article>", single_sticker_html, flags=re.IGNORECASE | re.DOTALL)
    if article_match:
        sticker_content = article_match.group("article").strip()
    else:
        # Fallback: get body content
        body_match = re.search(r"<body[^>]*>(?P<body>.*)</body>", single_sticker_html, flags=re.IGNORECASE | re.DOTALL)
        if body_match:
            sticker_content = body_match.group("body").strip()
        else:
            sticker_content = single_sticker_html
    
    # Extract styles from the original HTML
    style_match = re.search(r"<style[^>]*>(?P<style>.*)</style>", single_sticker_html, flags=re.IGNORECASE | re.DOTALL)
    sticker_styles = style_match.group("style") if style_match else ""
    
    # Simply repeat the full sticker HTML 4 times with proper positioning
    # The content should be actual full-size stickers (120mm x 150mm) scaled to fit
    return f"""
<!DOCTYPE html>
<html>
<head>
    <meta charset="utf-8">
    <style>
        {sticker_styles}
        @page {{ size: A4; margin: 0; }}
        * {{ box-sizing: border-box; }}
        body {{ 
            margin: 0; 
            padding: 0; 
            background: white;
        }}
        .a4-sheet {{
            width: 210mm;
            height: 297mm;
            position: relative;
            background: white;
            margin: 0;
            padding: 0;
        }}
        .sticker-wrapper {{
            position: absolute;
            width: 100mm;
            height: 125mm;
            overflow: hidden;
        }}
        .sticker-wrapper .content {{
            width: 120mm;
            height: 150mm;
            transform: scale(0.75);
            transform-origin: top left;
        }}
        .pos1 {{ left: 5mm; top: 5mm; }}
        .pos2 {{ left: 105mm; top: 5mm; }}
        .pos3 {{ left: 5mm; top: 135mm; }}
        .pos4 {{ left: 105mm; top: 135mm; }}
    </style>
</head>
<body>
    <div class="a4-sheet">
        <div class="sticker-wrapper pos1">
            <div class="content">
                {sticker_content}
            </div>
        </div>
        <div class="sticker-wrapper pos2">
            <div class="content">
                {sticker_content}
            </div>
        </div>
        <div class="sticker-wrapper pos3">
            <div class="content">
                {sticker_content}
            </div>
        </div>
        <div class="sticker-wrapper pos4">
            <div class="content">
                {sticker_content}
            </div>
        </div>
    </div>
</body>
</html>
"""


def create_sticker_sheet_html(single_sticker_html: str) -> str:
    """Create an A4 sheet with 4 labels - main entry point."""
    return create_simple_a4_layout(single_sticker_html)


def generate_pdf_with_pillow(single_sticker_html: str) -> bytes:
    """Generate a 4-sticker A4 PDF using Pillow for precise layout control."""
    
    # Step 1: Generate single sticker as image using wkhtmltopdf
    def html_to_image(html_content: str, width_mm: int = 120, height_mm: int = 150, dpi: int = 300) -> Image.Image:
        """Convert HTML to image using wkhtmltoimage."""
        try:
            # Generate PNG image using wkhtmltoimage
            import subprocess
            with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as html_file:
                html_file.write(html_content)
                html_file.flush()
                
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as img_file:
                    cmd = [
                        'wkhtmltoimage',
                        '--crop-w', str(int(width_mm * dpi / 25.4)),
                        '--crop-h', str(int(height_mm * dpi / 25.4)),
                        '--quality', '95',
                        '--format', 'png',
                        '--disable-smart-width',
                        html_file.name,
                        img_file.name
                    ]
                    
                    result = subprocess.run(cmd, capture_output=True, text=True)
                    if result.returncode != 0:
                        raise Exception(f"wkhtmltoimage failed: {result.stderr}")
                    
                    # Load the generated image
                    image = Image.open(img_file.name)
                    
                    # Clean up temp files
                    os.unlink(html_file.name)
                    os.unlink(img_file.name)
                    
                    return image
                    
        except Exception as e:
            print(f"Error generating image: {e}")
            raise
    
    # Step 2: Create A4 canvas and arrange 4 stickers
    def create_a4_layout(sticker_image: Image.Image) -> Image.Image:
        """Create A4 layout with 4 sticker images."""
        # A4 dimensions at 300 DPI
        a4_width_px = int(210 * 300 / 25.4)  # ~2480px
        a4_height_px = int(297 * 300 / 25.4)  # ~3508px
        
        # Create white A4 canvas
        canvas = Image.new('RGB', (a4_width_px, a4_height_px), 'white')
        
        # Calculate sticker dimensions and positions
        sticker_width_mm = 100
        sticker_height_mm = 125
        sticker_width_px = int(sticker_width_mm * 300 / 25.4)
        sticker_height_px = int(sticker_height_mm * 300 / 25.4)
        
        # Resize sticker to fit in frame
        sticker_resized = sticker_image.resize((sticker_width_px, sticker_height_px), Image.Resampling.LANCZOS)
        
        # Calculate positions (5mm margins, 5mm gaps)
        margin_px = int(5 * 300 / 25.4)
        gap_px = int(5 * 300 / 25.4)
        
        positions = [
            (margin_px, margin_px),  # Top-left
            (margin_px + sticker_width_px + gap_px, margin_px),  # Top-right
            (margin_px, margin_px + sticker_height_px + gap_px),  # Bottom-left
            (margin_px + sticker_width_px + gap_px, margin_px + sticker_height_px + gap_px),  # Bottom-right
        ]
        
        # Paste 4 stickers
        for pos in positions:
            canvas.paste(sticker_resized, pos)
        
        return canvas
    
    # Step 3: Convert final image to PDF
    def image_to_pdf(image: Image.Image) -> bytes:
        """Convert PIL Image to PDF bytes."""
        pdf_buffer = BytesIO()
        # Convert to RGB if needed (for PDF compatibility)
        if image.mode != 'RGB':
            image = image.convert('RGB')
        image.save(pdf_buffer, format='PDF', quality=95)
        return pdf_buffer.getvalue()
    
    # Execute the pipeline
    try:
        # Generate single sticker image
        sticker_image = html_to_image(single_sticker_html)
        
        # Create A4 layout with 4 stickers
        a4_layout = create_a4_layout(sticker_image)
        
        # Convert to PDF
        pdf_bytes = image_to_pdf(a4_layout)
        
        return pdf_bytes
        
    except Exception as e:
        print(f"Error in Pillow PDF generation: {e}")
        # Fallback to original method
        return pdfkit.from_string(single_sticker_html, False, options={
            'page-size': 'A4',
            'margin-top': '0',
            'margin-right': '0',
            'margin-bottom': '0',
            'margin-left': '0',
            'disable-smart-shrinking': '',
            'print-media-type': '',
            'dpi': 300,
        })


def generate_pdf(html: str) -> bytes:
    # Use the new approach: 4 separate single PDFs combined into one A4
    return generate_4_combined_pdfs(html)


def generate_single_sticker_pdf(html: str) -> bytes:
    """Generate a single perfect sticker PDF using the original method."""
    config = None
    wkhtml_binary = os.environ.get("WKHTMLTOPDF_BINARY")
    if wkhtml_binary:
        config = pdfkit.configuration(wkhtmltopdf=wkhtml_binary)

    # Original single sticker options that gave perfect fitting
    options = {
        "page-size": "A4",
        "page-width": "120mm",
        "page-height": "150mm", 
        "margin-top": "0mm",
        "margin-bottom": "0mm", 
        "margin-left": "0mm",
        "margin-right": "0mm",
        "encoding": "UTF-8",
        "enable-local-file-access": "",
        "disable-smart-shrinking": "",
        "print-media-type": "",
        "dpi": "300",
    }

    return pdfkit.from_string(html, False, options=options, configuration=config)


def generate_single_sticker_png(html: str) -> bytes:
    """Generate a single perfect sticker PNG using wkhtmltoimage."""
    import subprocess
    import tempfile
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as html_file:
        html_file.write(html)
        html_file.flush()
        
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as img_file:
            # Convert 120mm x 150mm to pixels at 300 DPI
            width_px = int(120 * 300 / 25.4)  # ~1417px
            height_px = int(150 * 300 / 25.4)  # ~1772px
            
            # Use wkhtmltoimage to create perfect single sticker image
            cmd = [
                'wkhtmltoimage',
                '--width', str(width_px),
                '--height', str(height_px), 
                '--quality', '95',
                '--format', 'png',
                '--disable-smart-width',
                '--enable-local-file-access',
                '--load-error-handling', 'ignore',
                html_file.name,
                img_file.name
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"wkhtmltoimage failed: {result.stderr}")
            
            # Read the generated image
            with open(img_file.name, 'rb') as f:
                png_bytes = f.read()
            
            # Clean up temp files
            os.unlink(html_file.name)
            os.unlink(img_file.name)
            
            return png_bytes


def generate_single_sticker_jpg(html: str) -> bytes:
    """Generate a single perfect sticker JPG using wkhtmltoimage."""
    import subprocess
    import tempfile
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.html', delete=False) as html_file:
        html_file.write(html)
        html_file.flush()
        
        with tempfile.NamedTemporaryFile(suffix='.jpg', delete=False) as img_file:
            # Convert 120mm x 150mm to pixels at 300 DPI
            width_px = int(120 * 300 / 25.4)  # ~1417px
            height_px = int(150 * 300 / 25.4)  # ~1772px
            
            # Use wkhtmltoimage to create perfect single sticker image
            cmd = [
                'wkhtmltoimage',
                '--width', str(width_px),
                '--height', str(height_px), 
                '--quality', '95',
                '--format', 'jpg',
                '--disable-smart-width',
                '--enable-local-file-access',
                '--load-error-handling', 'ignore',
                html_file.name,
                img_file.name
            ]
            
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                raise Exception(f"wkhtmltoimage failed: {result.stderr}")
            
            # Read the generated image
            with open(img_file.name, 'rb') as f:
                jpg_bytes = f.read()
            
            # Clean up temp files
            os.unlink(html_file.name)
            os.unlink(img_file.name)
            
            return jpg_bytes


def _merge_defaults(overrides: Dict[str, str]) -> Dict[str, str]:
    merged = DEFAULT_DATA.copy()
    merged.update({k: v for k, v in overrides.items() if v})
    return merged


def _process_custom_nutrition(form_values: Dict[str, str]) -> str:
    """Process custom nutrition fields from form data."""
    custom_fields = []
    for key, value in form_values.items():
        if key.startswith("custom_nutrition[") and key.endswith("][name]"):
            # Extract the index
            index = key.split("[")[1].split("]")[0]
            name_key = f"custom_nutrition[{index}][name]"
            amount_key = f"custom_nutrition[{index}][amount]"
            
            name = form_values.get(name_key, "").strip()
            amount = form_values.get(amount_key, "").strip()
            
            if name and amount:
                custom_fields.append(f"{name}: {amount}")
    
    return "<br>".join(custom_fields) if custom_fields else ""


def _build_font_face() -> str:
    if not FONT_PATH.exists():
        return ""
    encoded = b64encode(FONT_PATH.read_bytes()).decode("ascii")
    return (
        "@font-face{font-family:'Inter Custom';font-style:normal;font-weight:400;"
        "src:url(data:font/truetype;base64," + encoded + ") format('truetype');}"
    )


@app.route("/", methods=["GET", "POST"])
def label_generator():
    error: str | None = None
    presets = load_presets()
    selected_preset = request.args.get("preset", "")
    if request.method == "POST":
        selected_preset = request.form.get("selected_preset", selected_preset)

    if request.method == "GET" and selected_preset in presets:
        form_values: Dict[str, str] = _merge_defaults(presets[selected_preset])
    else:
        form_values = _merge_defaults({})

    preview_html = render_label_html(build_context(form_values, for_pdf=False))
    return render_template(
        "label_generator.html",
        field_groups=FIELD_GROUPS,
        quick_fields=QUICK_FIELDS,
        values=form_values,
        error=error,
        preview_html=preview_html,
        presets=presets,
        selected_preset=selected_preset,
    )


@app.route("/generate_single_pdf", methods=["POST"])
def generate_single_pdf():
    """Generate a single perfect sticker PDF."""
    submitted = {name: request.form.get(name, "") for name in ALL_FIELD_NAMES}
    form_values = _merge_defaults(submitted)
    context = build_context(form_values, for_pdf=True)
    
    try:
        html = render_label_html(context)
        pdf_bytes = generate_single_sticker_pdf(html)
        pdf_io = BytesIO(pdf_bytes)
        return send_file(
            pdf_io,
            mimetype="application/pdf",
            as_attachment=True,
            download_name="label.pdf",
        )
    except Exception as exc:
        error = f"Unable to generate PDF: {exc}"
        presets = load_presets()
        preview_html = render_label_html(build_context(form_values, for_pdf=False))
        return render_template(
            "label_generator.html",
            field_groups=FIELD_GROUPS,
            quick_fields=QUICK_FIELDS,
            values=form_values,
            presets=presets,
            selected_preset="",
            preview_html=preview_html,
            error=error,
        )


@app.route("/generate_single_png", methods=["POST"])
def generate_single_png():
    """Generate a single perfect sticker PNG."""
    submitted = {name: request.form.get(name, "") for name in ALL_FIELD_NAMES}
    form_values = _merge_defaults(submitted)
    context = build_context(form_values, for_pdf=False)  # Use web URLs instead of file paths
    
    try:
        html = render_label_html(context)
        png_bytes = generate_single_sticker_png(html)
        png_io = BytesIO(png_bytes)
        return send_file(
            png_io,
            mimetype="image/png",
            as_attachment=True,
            download_name="label.png",
        )
    except Exception as exc:
        error = f"Unable to generate PNG: {exc}"
        presets = load_presets()
        preview_html = render_label_html(build_context(form_values, for_pdf=False))
        return render_template(
            "label_generator.html",
            field_groups=FIELD_GROUPS,
            quick_fields=QUICK_FIELDS,
            values=form_values,
            presets=presets,
            selected_preset="",
            preview_html=preview_html,
            error=error,
        )


@app.route("/generate_single_jpg", methods=["POST"])
def generate_single_jpg():
    """Generate a single perfect sticker JPG."""
    submitted = {name: request.form.get(name, "") for name in ALL_FIELD_NAMES}
    form_values = _merge_defaults(submitted)
    context = build_context(form_values, for_pdf=False)  # Use web URLs instead of file paths
    
    try:
        html = render_label_html(context)
        jpg_bytes = generate_single_sticker_jpg(html)
        jpg_io = BytesIO(jpg_bytes)
        return send_file(
            jpg_io,
            mimetype="image/jpeg",
            as_attachment=True,
            download_name="label.jpg",
        )
    except Exception as exc:
        error = f"Unable to generate JPG: {exc}"
        presets = load_presets()
        preview_html = render_label_html(build_context(form_values, for_pdf=False))
        return render_template(
            "label_generator.html",
            field_groups=FIELD_GROUPS,
            quick_fields=QUICK_FIELDS,
            values=form_values,
            presets=presets,
            selected_preset="",
            preview_html=preview_html,
            error=error,
        )


@app.route("/upload_presets", methods=["POST"])
def upload_presets():
    file = request.files.get("presets_file")
    if file is None or not file.filename:
        return jsonify(success=False, error="No file provided."), 400

    try:
        content = file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        return jsonify(success=False, error="Could not decode file. Use UTF-8 encoding."), 400

    reader = csv.DictReader(StringIO(content))
    if reader.fieldnames is None:
        return jsonify(success=False, error="CSV header row is required."), 400
    normalized_headers = [name.strip() for name in reader.fieldnames if name]
    reader.fieldnames = normalized_headers
    if "product_name" not in normalized_headers:
        return jsonify(success=False, error="CSV must include a 'product_name' column."), 400

    presets = load_presets()
    added = 0

    try:
        for row in reader:
            product_name = (row.get("product_name") or "").strip()
            if not product_name:
                continue
            normalized = _normalize_preset_row(row)
            normalized["product_name"] = product_name
            presets[product_name] = normalized
            added += 1
    except csv.Error as exc:
        return jsonify(success=False, error=f"Invalid CSV format: {exc}"), 400

    save_presets(presets)
    return jsonify(success=True, added=added, total=len(presets))


@app.route("/save_preset", methods=["POST"])
def save_preset():
    presets = load_presets()
    form_data = {name: request.form.get(name, "") for name in ALL_FIELD_NAMES}
    product_name = form_data.get("product_name", "").strip()
    if not product_name:
        return jsonify(success=False, error="Product name is required to save a preset."), 400
    if product_name in presets:
        return jsonify(
            success=False,
            error="A preset with this product name already exists. Choose a unique name.",
        ), 409

    normalized = _merge_defaults(form_data)
    normalized["product_name"] = product_name
    presets[product_name] = normalized
    save_presets(presets)
    return jsonify(success=True, product_name=product_name, total=len(presets))


def iter_field_names() -> Iterable[str]:
    return ALL_FIELD_NAMES


if __name__ == "__main__":
    app.run(debug=True, host='0.0.0.0', port=5001)

