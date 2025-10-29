# -*- coding: utf-8 -*-
import base64
import json
import os
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


def image_to_base64(image_path: Path) -> str:
    """Return the image at image_path encoded as base64 for data URIs."""
    if not image_path.exists():
        return ""
    data = image_path.read_bytes()
    return base64.b64encode(data).decode("ascii")


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
    # Load base frame and FSSAI logo
    base_frame = image_to_base64(ASSETS_DIR / "base.png")
    fssai_logo_b64 = image_to_base64(ASSETS_DIR / "fssai.png")
    fssai_img_tag = (
        f'<img class="fssai-logo" src="data:image/png;base64,{fssai_logo_b64}" alt="FSSAI" />'
        if fssai_logo_b64 else ""
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


def generate_pdf_html(data: Dict[str, str], labels_per_page: int = 4) -> str:
    """Generate full HTML document for PDF generation with multiple labels."""
    label_markup = generate_label_html(data)
    labels = "\n".join(label_markup for _ in range(labels_per_page))

    # Load base frame
    base_frame = image_to_base64(ASSETS_DIR / "base.png")

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
        padding: 5mm;
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
        padding: 12mm 10mm 12mm;
        overflow: hidden;
        background-image: url("data:image/png;base64,{base_frame}");
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
        gap:14px;
        justify-content:center;
        padding-top: 5px;
      }}

      h1,h2,h3,p {{ margin:0; }}

      .desc{{
        text-align:center;
        font-size:10px;
        line-height:1.5;
        color:#333;
        white-space:pre-line;
        margin-bottom:12px;
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
        margin-top: 8px;
        margin-bottom: 8px;
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


@app.route("/generate_single_pdf", methods=["POST"])
def generate_single_pdf():
    """Generate an A4 PDF with 4 labels."""
    submitted = {name: request.form.get(name, "") for name in ALL_FIELD_NAMES}
    form_values = _merge_defaults(submitted)
    
    try:
        html = generate_pdf_html(form_values, labels_per_page=4)
        pdf_bytes = HTML(string=html).write_pdf()
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
