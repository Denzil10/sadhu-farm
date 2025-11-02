# -*- coding: utf-8 -*-
import base64
import json
from importlib import resources
from io import BytesIO
from pathlib import Path
from typing import Dict

from flask import Flask, jsonify, render_template, request, send_file
from weasyprint import HTML

BASE_DIR = Path(__file__).resolve().parent
ASSETS_DIR = BASE_DIR / "assets"
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
    "weight": "250",
    "batch": "BC-2409-07",
    "mfg": "2024-09-15",
    "expiry": "2025-03-15",
    "maker": "42 Bean Estate, Pollachi, Tamil Nadu, India",
    "fssai": "11224312000494",
    "country": "India",
}

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
            {"name": "price", "label": "Unit Price", "type": "text"},
            {"name": "weight", "label": "Weight (g)", "type": "text"},
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
            {"name": "fssai", "label": "FSSAI License", "type": "text"},
            {"name": "country", "label": "Country of Origin", "type": "text"},
        ),
    ),
)

ALL_FIELD_NAMES = (
    *(field["name"] for field in QUICK_FIELDS),
    *(field["name"] for _, group in FIELD_GROUPS for field in group),
)

app = Flask(__name__)


def asset_uri(filename: str, use_relative: bool = True) -> str:
    """Return a URI for an asset, usable by WeasyPrint.
    
    Args:
        filename: Name of the asset file
        use_relative: If True, returns relative path (for local dev with base_url)
                     If False, returns absolute path (most reliable for server environments)
    """
    local_path = ASSETS_DIR / filename
    if local_path.exists():
        if use_relative:
            # Use relative path from BASE_DIR - WeasyPrint will resolve via base_url
            rel_path = str(local_path.relative_to(BASE_DIR))
            app.logger.debug(f"Asset URI (relative): {rel_path}, base_dir: {BASE_DIR.resolve()}")
            return rel_path
        else:
            # Use absolute path string (works best on servers)
            abs_path = str(local_path.resolve())
            app.logger.debug(f"Asset URI (absolute): {abs_path}")
            return abs_path
    
    # Try resources fallback
    try:
        resource = resources.files("assets").joinpath(filename)
        with resources.as_file(resource) as resource_path:
            if use_relative:
                # Try to get relative path if possible
                try:
                    rel_path = str(Path(resource_path).relative_to(BASE_DIR))
                    app.logger.debug(f"Asset URI (resource relative): {rel_path}")
                    return rel_path
                except ValueError:
                    # If not relative, use absolute path
                    abs_path = str(Path(resource_path).resolve())
                    app.logger.debug(f"Asset URI (resource absolute): {abs_path}")
                    return abs_path
            else:
                # Use absolute path string for server environments
                abs_path = str(Path(resource_path).resolve())
                app.logger.debug(f"Asset URI (resource absolute): {abs_path}")
                return abs_path
    except (FileNotFoundError, ModuleNotFoundError, AttributeError) as e:
        app.logger.warning("Asset missing: %s (%s)", filename, e)
        return ""


def asset_to_base64(filename: str) -> str:
    """Return base64 encoded asset. Tries multiple methods to find the file.
    
    Returns empty string if file cannot be found or read.
    """
    # Method 1: Try local ASSETS_DIR path
    local_path = ASSETS_DIR / filename
    if local_path.exists() and local_path.is_file():
        try:
            data = local_path.read_bytes()
            if data:
                encoded = base64.b64encode(data).decode("ascii")
                app.logger.debug("Successfully loaded %s from local path", filename)
                return encoded
        except (OSError, IOError, PermissionError) as e:
            app.logger.warning("Failed to read asset %s from local path: %s", filename, e)
    
    # Method 2: Try importlib.resources (for packaged deployments)
    try:
        resource = resources.files("assets").joinpath(filename)
        if resource.is_file():
            with resources.as_file(resource) as resource_path:
                data = Path(resource_path).read_bytes()
                if data:
                    encoded = base64.b64encode(data).decode("ascii")
                    app.logger.debug("Successfully loaded %s from resources", filename)
                    return encoded
    except (FileNotFoundError, ModuleNotFoundError, AttributeError, ValueError, OSError) as e:
        app.logger.debug("Asset %s not found in resources: %s", filename, e)
    
    # Method 3: Try relative to BASE_DIR
    try:
        alt_path = BASE_DIR / filename
        if alt_path.exists() and alt_path.is_file():
            data = alt_path.read_bytes()
            if data:
                encoded = base64.b64encode(data).decode("ascii")
                app.logger.debug("Successfully loaded %s from BASE_DIR", filename)
                return encoded
    except (OSError, IOError) as e:
        app.logger.debug("Asset %s not found in BASE_DIR: %s", filename, e)
    
    # All methods failed
    app.logger.error("Could not find or read asset: %s (tried: %s, resources, %s)", 
                     filename, local_path, BASE_DIR / filename)
    return ""


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


def _merge_defaults(overrides: Dict[str, str]) -> Dict[str, str]:
    merged = DEFAULT_DATA.copy()
    merged.update({k: v for k, v in overrides.items() if v})
    return merged


def _normalize_preset_row(row: Dict[str, str]) -> Dict[str, str]:
    trimmed = {name: row.get(name, "").strip() for name in ALL_FIELD_NAMES}
    merged = _merge_defaults(trimmed)
    if trimmed.get("product_name"):
        merged["product_name"] = trimmed["product_name"]
    return merged


def generate_label_html(data: Dict[str, str]) -> str:
    """Generate HTML for a single label with the given data."""
    # Use base64 encoding - most reliable method that works everywhere
    # File paths often fail on server environments like Render.com
    base_frame_b64 = asset_to_base64("base.png")
    fssai_logo_b64 = asset_to_base64("fssai.png")
    
    # Build URIs - use base64 data URI if available, otherwise empty string
    base_frame_uri = f"data:image/png;base64,{base_frame_b64}" if base_frame_b64 else ""
    fssai_logo_uri = f"data:image/png;base64,{fssai_logo_b64}" if fssai_logo_b64 else ""
    
    # Log warnings if images are missing (but continue rendering)
    if not base_frame_b64:
        app.logger.warning("Base frame image (base.png) not found - label will render without background frame")
    else:
        app.logger.debug("Base frame image loaded successfully")
        
    if not fssai_logo_b64:
        app.logger.warning("FSSAI logo (fssai.png) not found - label will render without logo")
    else:
        app.logger.debug("FSSAI logo loaded successfully")
    
    # Only include image tag if logo URI is available
    fssai_img_tag = (
        f'<img class="fssai-logo" src="{fssai_logo_uri}" alt="FSSAI" />' if fssai_logo_uri else ""
    )

    # Format nutrition table rows
    nutrition_rows = []
    nutrition_fields = [
        ("Energy", "energy_amt", "energy_dv", "kcal"),
        ("Protein", "protein_amt", "protein_dv", "g"),
        ("Total Fat", "fat_total_amt", "fat_total_dv", "g"),
        ("Saturated Fat", "fat_sat_amt", "fat_sat_dv", "g"),
        ("Cholesterol", "chol_amt", "chol_dv", "mg"),
        ("Total Carbs", "carb_total_amt", "carb_total_dv", "g"),
        ("Total Sugars", "sugar_total_amt", "sugar_total_dv", "g"),
        ("Added Sugars", "sugar_added_amt", "sugar_added_dv", "g"),
        ("Dietary Fiber", "fiber_amt", "fiber_dv", "g"),
        ("Sodium", "sodium_amt", "sodium_dv", "mg"),
    ]

    for name, amt_key, dv_key, unit in nutrition_fields:
        amt = data.get(amt_key, "")
        dv = data.get(dv_key, "")
        if amt or dv:
            nutrition_rows.append(
                f'<tr><td>{name}</td><td>{amt} {unit}</td><td>{dv}</td></tr>'
            )

    nutrition_table = "\n".join(nutrition_rows)

    return f"""
        <article class="label">
          <div class="label-inner">
            <section class="desc">
              {data.get("desc", "").replace(chr(10), "<br>")}
            </section>
            <table class="ingredients-nutrition-container">
              <tr>
                <td class="ingredients">
                  <div class="section-title">Ingredients</div>
                  <p>{data.get("ing", "").replace(chr(10), "<br>")}</p>
                  <div><strong>CONTAINS:</strong> {data.get("cont", "")}</div>
                  <div><strong>MAY CONTAIN:</strong> {data.get("may", "").replace(chr(10), "<br>")}</div>
                </td>
                <td class="facts">
                  <table>
                    <thead>
                      <tr>
                        <th>Nutrition Facts<br><span>Per 100g</span></th>
                        <th>Amount</th>
                        <th>% Daily Value</th>
                      </tr>
                    </thead>
                    <tbody>
                      {nutrition_table}
                    </tbody>
                  </table>
                </td>
              </tr>
            </table>
            <section class="grid">
              <div class="grid-row">
                <div class="grid-cell"><span><strong>Manufactured:</strong></span> {data.get("mfg", "")}</div>
                <div class="grid-cell"><span><strong>Price:</strong></span> ₹ {data.get("price", "")}</div>
              </div>
              <div class="grid-row">
                <div class="grid-cell"><span><strong>Expiry:</strong></span> {data.get("expiry", "")}</div>
                <div class="grid-cell"><span><strong>Weight:</strong></span> {data.get("weight", "")} g</div>
              </div>
              <div class="grid-row">
                <div class="grid-cell"></div>
                <div class="grid-cell"><span><strong>Batch Code:</strong></span> {data.get("batch", "")}</div>
              </div>
            </section>
            <footer class="foot">
              <div class="foot-content">
                <div class="foot-left">
                  <div><strong>Manufactured By:</strong></div>
                  <div>{data.get("maker", "").replace(chr(10), "<br>")}</div>
                </div>
                <div class="foot-right">
                  <div class="fssai-block">{fssai_img_tag} <strong>LIC:</strong> {data.get("fssai", "")}</div>
                  <div><strong>Country of Origin:</strong> {data.get("country", "")}</div>
                </div>
              </div>
            </footer>
          </div>
        </article>
    """


def generate_test_png_html(data: Dict[str, str]) -> str:
    """Generate HTML for testing multiple image embedding methods."""
    # Get URIs for file-based methods - use relative paths for server compatibility
    base_frame_uri = asset_uri("base.png", use_relative=True)
    fssai_logo_uri = asset_uri("fssai.png", use_relative=True)
    
    # Also get file:// URI versions for testing
    base_frame_file_uri = asset_uri("base.png", use_relative=False)
    fssai_logo_file_uri = asset_uri("fssai.png", use_relative=False)
    
    # Get base64 for methods that need base64 encoding
    base_frame_path = ASSETS_DIR / "base.png"
    fssai_logo_path = ASSETS_DIR / "fssai.png"
    base_frame_b64 = ""
    fssai_logo_b64 = ""
    
    if base_frame_path.exists():
        base_frame_b64 = base64.b64encode(base_frame_path.read_bytes()).decode("ascii")
    if fssai_logo_path.exists():
        fssai_logo_b64 = base64.b64encode(fssai_logo_path.read_bytes()).decode("ascii")
    
    # Get absolute paths for file:// URLs
    base_frame_abs = str(base_frame_path.resolve()) if base_frame_path.exists() else ""
    fssai_logo_abs = str(fssai_logo_path.resolve()) if fssai_logo_path.exists() else ""
    base_frame_relative = str(base_frame_path.relative_to(BASE_DIR)) if base_frame_path.exists() else ""
    fssai_logo_relative = str(fssai_logo_path.relative_to(BASE_DIR)) if fssai_logo_path.exists() else ""
    
    # Create test label content (simplified)
    label_content = f"""
            <section class="desc">
              {data.get("desc", "")[:50]}...
            </section>
            <div class="test-info">
              <div><strong>Product:</strong> {data.get("product_name", "")}</div>
              <div><strong>Batch:</strong> {data.get("batch", "")}</div>
            </div>
            <footer class="foot">
              <div class="fssai-block">
                <img class="fssai-logo" src="{fssai_logo_uri}" alt="FSSAI" />
                <strong>LIC:</strong> {data.get("fssai", "")}
              </div>
            </footer>
    """
    
    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="utf-8" />
    <style>
      @page {{
        size: A4 landscape;
        margin: 5mm;
      }}
      
      body {{
        font-family: system-ui, sans-serif;
        margin: 0;
        padding: 0;
        width: 100%;
        height: 100%;
      }}
      
      .test-container {{
        display: grid;
        grid-template-columns: 1fr 1fr;
        gap: 12px;
        padding: 10px;
      }}
      
      .test-label {{
        position: relative;
        width: 100%;
        min-height: 150px;
        padding: 10px;
        border: 2px solid #ddd;
        border-radius: 6px;
        background: #fff;
        font-size: 9px;
        color: #000;
        overflow: hidden;
        box-sizing: border-box;
      }}
      
      .test-label.full-width {{
        grid-column: 1 / -1;
      }}
      
      .test-label h3 {{
        margin: 0 0 8px;
        font-size: 12px;
        color: #333;
        border-bottom: 1px solid #ddd;
        padding-bottom: 5px;
        line-height: 1.3;
      }}
      
      .label-inner {{
        position: relative;
        z-index: 1;
      }}
      
      /* Method 1: Base64 data URI in CSS background */
      .method1 {{
        background-image: url("data:image/png;base64,{base_frame_b64}");
        background-size: 100% 100%;
        background-repeat: no-repeat;
        background-position: center;
      }}
      
      /* Method 2: Base64 data URI in img tag */
      .method2 {{
        background-color: #f5f5f5;
      }}
      .method2 .frame-img {{
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        object-fit: cover;
        z-index: 0;
        opacity: 0.3;
      }}
      
      /* Method 3: File URL with absolute path */
      .method3 {{
        background-image: url("file://{base_frame_abs}");
        background-size: 100% 100%;
        background-repeat: no-repeat;
      }}
      
      /* Method 4: Relative path (should work with base_url) */
      .method4 {{
        background-image: url("{base_frame_relative}");
        background-size: 100% 100%;
        background-repeat: no-repeat;
      }}
      
      /* Method 7: asset_uri() relative path (Current Implementation) */
      .method7 {{
        background-image: url("{base_frame_uri}");
        background-size: 100% 100%;
        background-repeat: no-repeat;
      }}
      
      /* Method 8: asset_uri() file:// URI (for comparison) */
      .method8 {{
        background-image: url("{base_frame_file_uri}");
        background-size: 100% 100%;
        background-repeat: no-repeat;
      }}
      
      /* Method 5: Base64 in img tag positioned absolutely */
      .method5 {{
        position: relative;
      }}
      .method5 .frame-img {{
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        z-index: 0;
      }}
      
      /* Method 6: Multiple base64 images stacked */
      .method6 {{
        background-image: 
          url("data:image/png;base64,{base_frame_b64}"),
          url("data:image/png;base64,{fssai_logo_b64}");
        background-size: 100% 100%, 50px 50px;
        background-repeat: no-repeat, no-repeat;
        background-position: center, top right;
      }}
      
      .desc {{
        text-align: center;
        font-size: 9px;
        margin-bottom: 6px;
        line-height: 1.3;
      }}
      
      .test-info {{
        font-size: 8px;
        margin: 6px 0;
        line-height: 1.4;
      }}
      
      .foot {{
        margin-top: 8px;
        font-size: 8px;
        line-height: 1.4;
      }}
      
      .fssai-block {{
        display: flex;
        align-items: center;
        gap: 4px;
      }}
      
      .fssai-logo {{
        height: 12px;
        width: auto;
      }}
      
      .label-inner {{
        display: flex;
        flex-direction: column;
        height: 100%;
      }}
    </style>
    </head>
    <body>
      <div class="test-container">
        <div class="test-label method1">
          <h3>Method 1: Base64 CSS Background</h3>
          <div class="label-inner">
            {label_content}
          </div>
        </div>
        
        <div class="test-label method2">
          <h3>Method 2: Base64 img tag (absolute)</h3>
          <img src="data:image/png;base64,{base_frame_b64}" class="frame-img" alt="frame" />
          <div class="label-inner">
            {label_content}
          </div>
        </div>
        
        <div class="test-label method3">
          <h3>Method 3: File URL (absolute)</h3>
          <div class="label-inner">
            {label_content}
          </div>
        </div>
        
        <div class="test-label method4">
          <h3>Method 4: File URL (relative)</h3>
          <div class="label-inner">
            {label_content}
          </div>
        </div>
        
        <div class="test-label method5">
          <h3>Method 5: Base64 img (relative z-index)</h3>
          <img src="data:image/png;base64,{base_frame_b64}" class="frame-img" alt="frame" />
          <div class="label-inner">
            {label_content}
          </div>
        </div>
        
        <div class="test-label method6">
          <h3>Method 6: Multiple Base64 Backgrounds</h3>
          <div class="label-inner">
            {label_content}
          </div>
        </div>
        
        <div class="test-label method7">
          <h3>Method 7: asset_uri() relative path</h3>
          <div class="label-inner">
            {label_content}
          </div>
        </div>
        
        <div class="test-label method8 full-width">
          <h3>Method 8: asset_uri() file:// URI (for comparison)</h3>
          <div class="label-inner">
            {label_content}
          </div>
        </div>
      </div>
    </body>
    </html>
    """


def generate_pdf_html(data: Dict[str, str], labels_per_page: int = 4) -> str:
    """Generate full HTML document for PDF generation with multiple labels."""
    label_markup = generate_label_html(data)
    labels = "\n".join(label_markup for _ in range(labels_per_page))

    # Load base frame - use base64 encoding (most reliable on all platforms)
    base_frame_b64 = asset_to_base64("base.png")
    base_frame_uri = f"data:image/png;base64,{base_frame_b64}" if base_frame_b64 else ""
    
    if not base_frame_b64:
        app.logger.warning("Base frame image (base.png) not found - labels will render without background frame")
    else:
        app.logger.debug("Base frame image loaded successfully for PDF generation")

    return f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=800, initial-scale=1" />
    <style>
      @page {{
        size: A4;
        margin: 0;
      }}

      * {{ box-sizing:border-box; }}
      html, body {{ margin: 0; padding: 0; background: #fff; }}

      .sheet {{
        width: 210mm;
        height: 297mm;
        padding: 0;
        display: grid;
        grid-template-columns: repeat(2, 1fr);
        grid-template-rows: repeat(2, 1fr);
        gap: 0;
      }}

      .label {{
        position: relative;
        width: 100%;
        height: 100%;
        color: #000;
        font: 11px/1.45 "Inter", system-ui, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial, sans-serif;
        padding: 10mm 8mm 10mm;
        overflow: hidden;
        {('background-image: url("' + base_frame_uri + '");') if base_frame_uri else ''}
        background-position: left top;
        background-size: 100% 100%;
        background-repeat: no-repeat;
      }}

      .label-inner{{
        display:flex;
        flex-direction:column;
        position:relative;
        z-index:1;
        width: 100%;
        height: 100%;
        gap:10px;
        justify-content:center;
        padding-top: 2px;
      }}

      h1,h2,h3,p {{ margin:0; }}

      .desc{{
        text-align:center;
        font-size:10px;
        line-height:1.5;
        color:#333;
        white-space:pre-line;
        margin-bottom:8px;
      }}

      .section-title{{
        font-weight:800;
        text-transform:uppercase;
        margin-bottom:6px;
        font-size:10px;
      }}

      .ingredients-nutrition-container{{
        width:100%;
        border-collapse:collapse;
        margin:0;
        padding:0;
      }}

      .ingredients{{
        width:45%;
        vertical-align:top;
        padding-right:10px;
      }}
      .ingredients p{{ margin:0; white-space:pre-line; }}

      .ingredients div{{
        font-size:10px;
        margin-bottom:1px;
      }}

      .facts{{
        width:55%;
        vertical-align:top;
        padding-left:10px;
        padding:4px 6px 6px;
        background:transparent;
      }}
      .facts table{{
        width:100%;
        border-collapse:collapse;
        table-layout:fixed;
        font-size:6.5px;
      }}
      .facts th,
      .facts td{{
        border:1px solid #c9c9c9;
        padding:2px 3px;
        text-align:left;
        vertical-align:middle;
      }}
      .facts thead th{{
        background:#f2f2f2;
        font-weight:700;
        text-transform:uppercase;
        font-size:7px;
        letter-spacing:0.3px;
      }}
      .facts tbody td:nth-child(2){{
        text-align:center;
      }}
      .facts tbody td:last-child{{
        text-align:right;
      }}

      .grid{{
        display:table;
        width:100%;
        font-size:10px;
        margin-top: 4px;
        margin-bottom: 4px;
      }}
      .grid-row{{
        display:table-row;
      }}
      .grid-cell{{
        display:table-cell;
        width:50%;
        padding:3px 10px;
        vertical-align:top;
      }}

      .foot{{
        padding-top:6px;
        font-size:10.5px;
        margin-top:auto;
        margin-bottom: 0;
        padding-bottom: 0;
      }}

      .foot-content{{
        display:table;
        width:100%;
      }}

      .foot-left{{
        display:table-cell;
        width:50%;
        vertical-align:top;
        padding:3px 12px;
      }}

      .foot-right{{
        display:table-cell;
        width:50%;
        vertical-align:top;
        padding:3px 12px;
      }}
      .fssai-block{{ display:flex; align-items:center; gap:6px; margin-bottom:2px; }}
      .fssai-logo{{ height:12px; width:auto; display:inline-block; vertical-align:middle; }}
    </style>
    </head>
    <body>
      <div class="sheet">
        {labels}
      </div>
    </body>
    </html>
    """


@app.route("/", methods=["GET", "POST"])
def label_generator():
    presets = load_presets()
    selected_preset = request.args.get("preset", "")
    if request.method == "POST":
        selected_preset = request.form.get("selected_preset", selected_preset)

    if request.method == "GET" and selected_preset in presets:
        form_values: Dict[str, str] = _merge_defaults(presets[selected_preset])
    else:
        form_values = _merge_defaults({})

    return render_template(
        "label_generator.html",
        field_groups=FIELD_GROUPS,
        quick_fields=QUICK_FIELDS,
        values=form_values,
        error=None,
        presets=presets,
        selected_preset=selected_preset,
    )


@app.route("/generate_test_png", methods=["POST"])
def generate_test_png():
    """Generate a test PNG with multiple image embedding methods."""
    submitted = {name: request.form.get(name, "") for name in ALL_FIELD_NAMES}
    form_values = _merge_defaults(submitted)
    
    try:
        html = generate_test_png_html(form_values)
        # WeasyPrint: render HTML to document, then write as PNG
        document = HTML(string=html, base_url=str(BASE_DIR.resolve())).render()
        png_bytes = document.write_png()
        png_io = BytesIO(png_bytes)
        return send_file(
            png_io,
            mimetype="image/png",
            as_attachment=True,
            download_name="image_test.png",
        )
    except Exception as exc:
        # Fallback: try PDF and convert, or return error
        try:
            html = generate_test_png_html(form_values)
            pdf_bytes = HTML(string=html, base_url=str(BASE_DIR.resolve())).write_pdf()
            # For now, return PDF if PNG fails (so user can see the test)
            pdf_io = BytesIO(pdf_bytes)
            return send_file(
                pdf_io,
                mimetype="application/pdf",
                as_attachment=True,
                download_name="image_test.pdf",
            )
        except Exception as e:
            return jsonify(success=False, error=f"Unable to generate test image: {exc} - {e}"), 500


@app.route("/generate_single_pdf", methods=["POST"])
def generate_single_pdf():
    """Generate an A4 PDF with 4 labels."""
    submitted = {name: request.form.get(name, "") for name in ALL_FIELD_NAMES}
    form_values = _merge_defaults(submitted)
    
    try:
        html = generate_pdf_html(form_values, labels_per_page=4)
        pdf_bytes = HTML(string=html, base_url=str(BASE_DIR.resolve())).write_pdf()
        pdf_io = BytesIO(pdf_bytes)
        return send_file(
            pdf_io,
            mimetype="application/pdf",
            as_attachment=True,
            download_name="sadhu_farm_labels.pdf",
        )
    except Exception as exc:
        error = f"Unable to generate PDF: {exc}"
        presets = load_presets()
        return render_template(
            "label_generator.html",
            field_groups=FIELD_GROUPS,
            quick_fields=QUICK_FIELDS,
            values=form_values,
            presets=presets,
            selected_preset="",
            error=error,
        )


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


# For Vercel deployment
handler = app

if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5001)
