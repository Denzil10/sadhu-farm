from __future__ import annotations

import os
from io import BytesIO
from pathlib import Path
from typing import Dict, Iterable

import pdfkit
from flask import Flask, render_template, request, send_file
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

DEFAULT_DATA: Dict[str, str] = {
    "ing": "Cocoa nibs (65%)\nCane sugar\nCocoa butter\nSunflower lecithin\nVanilla bean",
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

MULTILINE_FIELDS = {"ing", "may", "addr"}

FIELD_GROUPS = (
    (
        "Product & Allergens",
        (
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
        "Pricing & Batch",
        (
            {"name": "price", "label": "Unit Price (₹/kg)", "type": "text"},
            {"name": "batch", "label": "Batch Code", "type": "text"},
            {"name": "mfg", "label": "Manufacture Date", "type": "text"},
            {"name": "expiry", "label": "Expiry Date", "type": "text"},
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

ALL_FIELD_NAMES = tuple(field["name"] for _, group in FIELD_GROUPS for field in group)

app = Flask(__name__)


def _escape_multiline(value: str) -> Markup:
    """Escape user text and preserve line breaks."""
    if not value:
        return Markup("")
    escaped = Markup.escape(value)
    return Markup("<br>").join(escaped.splitlines())


def build_context(form_values: Dict[str, str]) -> Dict[str, str]:
    context: Dict[str, str] = {}
    for key, raw in form_values.items():
        stripped = raw.strip()
        if key in MULTILINE_FIELDS:
            context[key] = _escape_multiline(stripped)
        else:
            context[key] = stripped

    bg_path = (ASSETS_DIR / "base.svg").resolve()
    logo_candidates = ("logo.png", "fssai.png")
    logo_path = next(
        (ASSETS_DIR / candidate for candidate in logo_candidates if (ASSETS_DIR / candidate).exists()),
        None,
    )

    context["bg_url"] = bg_path.as_uri()
    if logo_path:
        context["logo_url"] = logo_path.resolve().as_uri()
    return context


def render_label_html(context: Dict[str, str]) -> str:
    return LABEL_TEMPLATE.render(**context)


def generate_pdf(html: str) -> bytes:
    config = None
    wkhtml_binary = os.environ.get("WKHTMLTOPDF_BINARY")
    if wkhtml_binary:
        config = pdfkit.configuration(wkhtmltopdf=wkhtml_binary)

    options = {
        "page-width": "120mm",
        "page-height": "150mm",
        "margin-top": "0mm",
        "margin-bottom": "0mm",
        "margin-left": "0mm",
        "margin-right": "0mm",
        "encoding": "UTF-8",
        "enable-local-file-access": None,
    }

    return pdfkit.from_string(html, False, options=options, configuration=config)


def _merge_defaults(overrides: Dict[str, str]) -> Dict[str, str]:
    merged = DEFAULT_DATA.copy()
    merged.update({k: v for k, v in overrides.items() if v})
    return merged


@app.route("/", methods=["GET", "POST"])
def label_generator():
    error: str | None = None
    form_values: Dict[str, str] = _merge_defaults({})

    if request.method == "POST":
        submitted = {name: request.form.get(name, "") for name in ALL_FIELD_NAMES}
        form_values = _merge_defaults(submitted)
        context = build_context(form_values)
        try:
            html = render_label_html(context)
            pdf_bytes = generate_pdf(html)
        except Exception as exc:  # noqa: BLE001
            error = (
                "Unable to generate the PDF. "
                "Ensure wkhtmltopdf is installed and reachable. "
                f"Details: {exc}"
            )
        else:
            pdf_io = BytesIO(pdf_bytes)
            return send_file(
                pdf_io,
                mimetype="application/pdf",
                as_attachment=True,
                download_name="sadhu-farm-label.pdf",
            )

    return render_template(
        "label_generator.html",
        field_groups=FIELD_GROUPS,
        values=form_values,
        error=error,
    )


def iter_field_names() -> Iterable[str]:
    return ALL_FIELD_NAMES


if __name__ == "__main__":
    app.run(debug=True, port=5001)
