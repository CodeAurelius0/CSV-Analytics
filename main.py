import os
import uuid
import json
import traceback

import numpy as np
import pandas as pd
from scipy import stats as scipy_stats
from flask import Flask, request, render_template, jsonify, send_file
from werkzeug.utils import secure_filename

from charts import generate_all_charts

import tempfile

# ──────────────────────────────────────────────
#  Flask App Configuration
# ──────────────────────────────────────────────
app = Flask(__name__)
app.config["UPLOAD_FOLDER"] = os.path.join(tempfile.gettempdir(), "csv_uploads")
app.config["REPORT_FOLDER"] = os.path.join(tempfile.gettempdir(), "csv_reports")
app.config["MAX_CONTENT_LENGTH"] = 50 * 1024 * 1024  # 50 MB

os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
os.makedirs(app.config["REPORT_FOLDER"], exist_ok=True)

# ──────────────────────────────────────────────
#  Helper
# ──────────────────────────────────────────────
def load_dataframe(filepath, nrows=None):
    if filepath.lower().endswith(".csv"):
        return pd.read_csv(filepath, nrows=nrows) if nrows else pd.read_csv(filepath)
    else:
        try:
            return pd.read_excel(filepath, nrows=nrows) if nrows else pd.read_excel(filepath)
        except ValueError as ve:
            if "format cannot be determined" in str(ve).lower():
                try:
                    return pd.read_csv(filepath, nrows=nrows) if nrows else pd.read_csv(filepath)
                except Exception:
                    pass
            raise ValueError("The uploaded file is not a valid Excel or CSV file.")

# ──────────────────────────────────────────────
#  Smart Column Synonym Mapping
# ──────────────────────────────────────────────
COLUMN_SYNONYMS = {
    "Sales": [
        "sales", "revenue", "income", "amount", "total sales", "sale amount",
        "total_sales", "sale_amount", "gross sales", "net sales", "turnover",
        "receipts", "price", "total_amount", "order_amount"
    ],
    "Profit": [
        "profit", "net profit", "gain", "margin", "net_profit", "earnings",
        "net income", "profit_margin", "net_income", "operating profit"
    ],
    "Discount": [
        "discount", "discount_rate", "discount_amount", "rebate", "deduction"
    ],
    "Quantity": [
        "quantity", "qty", "units", "count", "volume", "units_sold",
        "number of units", "pieces"
    ],
    "Customer": [
        "customer", "client", "buyer", "consumer", "customer name",
        "customer_name", "client_name", "account", "customer id", "customer_id"
    ],
    "Product": [
        "product", "item", "product name", "product_name", "item_name",
        "product id", "product_id", "sku", "article"
    ],
    "Category": [
        "category", "product category", "type", "department", "segment",
        "sub-category", "subcategory", "product_category", "product_type",
        "class", "group", "genre"
    ],
    "Region": [
        "region", "state", "city", "country", "location", "territory",
        "area", "zone", "province", "county", "district", "market"
    ],
    "Date": [
        "date", "order date", "order_date", "ship date", "ship_date",
        "timestamp", "created_at", "time", "period", "year_month",
        "purchase_date", "transaction_date", "invoice_date"
    ],
}


# ──────────────────────────────────────────────
#  Column Detection
# ──────────────────────────────────────────────
def detect_columns(df: pd.DataFrame) -> dict:
    """
    Maps DataFrame columns to standard metric names using synonym matching.
    Returns a dict like {'Sales': 'Revenue', 'Date': 'Order Date', ...}
    """
    mapped = {}
    df_cols_lower = {col.lower().strip(): col for col in df.columns}

    for standard_name, synonyms in COLUMN_SYNONYMS.items():
        for syn in synonyms:
            if syn in df_cols_lower:
                mapped[standard_name] = df_cols_lower[syn]
                break  # first match wins

    return mapped


def classify_columns(df: pd.DataFrame) -> dict:
    """Returns lists of column names by detected type."""
    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()
    bool_cols = df.select_dtypes(include=["bool"]).columns.tolist()
    datetime_cols = df.select_dtypes(include=["datetime64"]).columns.tolist()

    return {
        "numeric": numeric_cols,
        "categorical": categorical_cols,
        "boolean": bool_cols,
        "datetime": datetime_cols,
    }


# ──────────────────────────────────────────────
#  Data Cleaning Engine
# ──────────────────────────────────────────────
def clean_data(df: pd.DataFrame) -> tuple:
    """
    Cleans the DataFrame and returns (cleaned_df, cleaning_report_dict).
    Handles: missing values, duplicates, constant columns, empty columns.
    """
    report = {
        "original_rows": len(df),
        "original_cols": len(df.columns),
        "missing_before": int(df.isnull().sum().sum()),
        "duplicate_rows": int(df.duplicated().sum()),
        "constant_cols": [],
        "empty_cols": [],
        "outlier_cols": {},
        "actions_taken": [],
    }

    # 1. Drop fully empty columns
    empty_cols = df.columns[df.isnull().all()].tolist()
    if empty_cols:
        df = df.drop(columns=empty_cols)
        report["empty_cols"] = empty_cols
        report["actions_taken"].append(f"Dropped {len(empty_cols)} fully-empty column(s).")

    # 2. Drop constant columns (only one unique value, ignoring NaN)
    constant_cols = [col for col in df.columns if df[col].nunique(dropna=True) == 1]
    if constant_cols:
        df = df.drop(columns=constant_cols)
        report["constant_cols"] = constant_cols
        report["actions_taken"].append(f"Dropped {len(constant_cols)} constant column(s).")

    # 3. Drop exact duplicate rows
    before_dedup = len(df)
    df = df.drop_duplicates()
    removed_dups = before_dedup - len(df)
    if removed_dups > 0:
        report["actions_taken"].append(f"Removed {removed_dups} exact duplicate row(s).")

    # 4. Fill numeric nulls with median; categorical with mode
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    for col in numeric_cols:
        null_count = int(df[col].isnull().sum())
        if null_count > 0:
            df[col] = df[col].fillna(df[col].median())
            report["actions_taken"].append(f"Filled {null_count} missing value(s) in '{col}' with median.")

    categorical_cols = df.select_dtypes(include=["object", "category"]).columns
    for col in categorical_cols:
        null_count = int(df[col].isnull().sum())
        if null_count > 0:
            mode_val = df[col].mode()
            fill_val = mode_val[0] if not mode_val.empty else "Unknown"
            df[col] = df[col].fillna(fill_val)
            report["actions_taken"].append(f"Filled {null_count} missing value(s) in '{col}' with mode.")

    # 5. Detect outliers using IQR (informational, no automatic removal)
    for col in numeric_cols:
        if col in df.columns:
            q1 = df[col].quantile(0.25)
            q3 = df[col].quantile(0.75)
            iqr = q3 - q1
            outliers = ((df[col] < (q1 - 1.5 * iqr)) | (df[col] > (q3 + 1.5 * iqr))).sum()
            if outliers > 0:
                report["outlier_cols"][col] = int(outliers)

    report["final_rows"] = len(df)
    report["final_cols"] = len(df.columns)
    report["missing_after"] = int(df.isnull().sum().sum())
    report["rows_removed"] = report["original_rows"] - len(df)
    report["cols_removed"] = report["original_cols"] - len(df.columns)

    # 6. Calculate Data Health Score (0-100)
    missing_pct = report["missing_before"] / max(1, report["original_rows"] * report["original_cols"])
    dup_pct = report["duplicate_rows"] / max(1, report["original_rows"])
    outlier_ratio = sum(report["outlier_cols"].values()) / max(1, report["final_rows"])

    health_score = 100
    health_score -= min(30, missing_pct * 100)
    health_score -= min(20, dup_pct * 100)
    health_score -= min(10, outlier_ratio * 10)
    health_score -= len(empty_cols) * 2
    health_score -= len(constant_cols) * 2

    report["health_score"] = round(max(0, health_score), 1)

    return df, report


# ──────────────────────────────────────────────
#  Statistical Analysis
# ──────────────────────────────────────────────
def generate_statistics(df: pd.DataFrame) -> dict:
    """Generates comprehensive statistical summary for numeric columns."""
    numeric_df = df.select_dtypes(include=[np.number])
    if numeric_df.empty:
        return {}

    stats = {}
    for col in numeric_df.columns:
        series = numeric_df[col].dropna()
        if len(series) == 0:
            continue

        from scipy import stats as scipy_stats

        try:
            skewness = float(series.skew())
            kurt = float(series.kurtosis())
        except Exception:
            skewness, kurt = 0.0, 0.0

        try:
            mode_val = float(series.mode().iloc[0])
        except Exception:
            mode_val = float("nan")

        stats[col] = {
            "count": int(series.count()),
            "mean": round(float(series.mean()), 4),
            "median": round(float(series.median()), 4),
            "mode": round(mode_val, 4),
            "std": round(float(series.std()), 4),
            "variance": round(float(series.var()), 4),
            "min": round(float(series.min()), 4),
            "max": round(float(series.max()), 4),
            "range": round(float(series.max() - series.min()), 4),
            "q1": round(float(series.quantile(0.25)), 4),
            "q3": round(float(series.quantile(0.75)), 4),
            "iqr": round(float(series.quantile(0.75) - series.quantile(0.25)), 4),
            "p5": round(float(series.quantile(0.05)), 4),
            "p95": round(float(series.quantile(0.95)), 4),
            "skewness": round(skewness, 4),
            "kurtosis": round(kurt, 4),
        }

    return stats


# ──────────────────────────────────────────────
#  KPI Generation
# ──────────────────────────────────────────────
def generate_kpis(df: pd.DataFrame, mapped_cols: dict) -> list:
    """Returns a list of KPI dicts: {label, value, icon, color}"""
    kpis = []

    def add_kpi(label, value, icon, color):
        kpis.append({"label": label, "value": value, "icon": icon, "color": color})

    # Always available
    add_kpi("Total Rows", f"{len(df):,}", "bi-table", "#3b82f6")
    add_kpi("Total Columns", f"{len(df.columns):,}", "bi-layout-three-columns", "#8b5cf6")

    if "Sales" in mapped_cols:
        sc = mapped_cols["Sales"]
        total_sales = df[sc].sum()
        avg_sales = df[sc].mean()
        add_kpi("Total Sales", f"${total_sales:,.2f}", "bi-currency-dollar", "#10b981")
        add_kpi("Avg Sale", f"${avg_sales:,.2f}", "bi-graph-up", "#06b6d4")

    if "Profit" in mapped_cols:
        pc = mapped_cols["Profit"]
        total_profit = df[pc].sum()
        add_kpi("Total Profit", f"${total_profit:,.2f}", "bi-cash-stack", "#f59e0b")

        if "Sales" in mapped_cols:
            sc = mapped_cols["Sales"]
            margin = (total_profit / df[sc].sum()) * 100 if df[sc].sum() != 0 else 0
            add_kpi("Profit Margin", f"{margin:.1f}%", "bi-pie-chart", "#ec4899")

    if "Discount" in mapped_cols:
        dc = mapped_cols["Discount"]
        avg_discount = df[dc].mean() * 100 if df[dc].max() <= 1 else df[dc].mean()
        add_kpi("Avg Discount", f"{avg_discount:.1f}%", "bi-tag", "#f97316")

    if "Quantity" in mapped_cols:
        qc = mapped_cols["Quantity"]
        add_kpi("Total Units Sold", f"{int(df[qc].sum()):,}", "bi-box-seam", "#84cc16")

    if "Customer" in mapped_cols:
        cc = mapped_cols["Customer"]
        add_kpi("Unique Customers", f"{df[cc].nunique():,}", "bi-people", "#06b6d4")

    if "Product" in mapped_cols:
        prc = mapped_cols["Product"]
        add_kpi("Unique Products", f"{df[prc].nunique():,}", "bi-box", "#a855f7")

    if "Category" in mapped_cols:
        catc = mapped_cols["Category"]
        add_kpi("Categories", f"{df[catc].nunique():,}", "bi-grid", "#14b8a6")

    if "Region" in mapped_cols:
        rc = mapped_cols["Region"]
        add_kpi("Regions", f"{df[rc].nunique():,}", "bi-geo-alt", "#f43f5e")

    return kpis


# ──────────────────────────────────────────────
#  AI Business Insights Engine
# ──────────────────────────────────────────────
def generate_insights(df: pd.DataFrame, mapped_cols: dict) -> list:
    """Generates rule-based business insights for each detected section."""
    insights = []

    def add_insight(section, icon, observation, insight_text, recommendation, risk=""):
        insights.append({
            "section": section,
            "icon": icon,
            "observation": observation,
            "insight": insight_text,
            "recommendation": recommendation,
            "risk": risk,
        })

    # ── Sales + Category Insight ──
    if "Sales" in mapped_cols and "Category" in mapped_cols:
        sc, catc = mapped_cols["Sales"], mapped_cols["Category"]
        cat_sales = df.groupby(catc)[sc].sum().sort_values(ascending=False)
        if len(cat_sales) > 0:
            top = cat_sales.index[0]
            pct = (cat_sales.iloc[0] / cat_sales.sum()) * 100
            bottom = cat_sales.index[-1] if len(cat_sales) > 1 else top
            add_insight(
                "Sales by Category", "bi-bar-chart-fill",
                f"'{top}' generates {pct:.1f}% of total sales, the highest across all categories.",
                f"{top} is the dominant revenue driver in the dataset.",
                f"Increase marketing spend and inventory for {top}. Consider bundling {top} items with low-performing categories.",
                f"Over-reliance on '{top}' creates revenue concentration risk if demand drops."
            )

    # ── Profit Insight ──
    if "Profit" in mapped_cols and "Category" in mapped_cols:
        pc, catc = mapped_cols["Profit"], mapped_cols["Category"]
        cat_profit = df.groupby(catc)[pc].sum().sort_values()
        if not cat_profit.empty:
            worst = cat_profit.index[0]
            worst_val = cat_profit.iloc[0]
            best = cat_profit.index[-1]
            if worst_val < 0:
                add_insight(
                    "Profitability Alert", "bi-exclamation-triangle-fill",
                    f"'{worst}' is generating a net LOSS of ${abs(worst_val):,.2f}.",
                    f"This category is actively destroying company value.",
                    f"Review pricing strategy, cost structure, or consider discontinuing unprofitable SKUs in '{worst}'.",
                    f"Continuing operations in '{worst}' at a loss could erode overall profitability by {abs(worst_val / df[pc].sum() * 100):.1f}%."
                )
            else:
                add_insight(
                    "Profitability", "bi-cash-stack",
                    f"'{best}' is the most profitable category.",
                    f"High-margin categories like '{best}' represent strong business value.",
                    f"Prioritize cross-selling '{best}' items and replicate its pricing strategy in underperforming categories.",
                    "Margin compression in profitable categories could occur if competitor pricing drops."
                )

    # ── Customer Insight ──
    if "Customer" in mapped_cols and "Sales" in mapped_cols:
        cc, sc = mapped_cols["Customer"], mapped_cols["Sales"]
        cust_sales = df.groupby(cc)[sc].sum().sort_values(ascending=False)
        top_5_pct = (cust_sales.head(5).sum() / cust_sales.sum()) * 100 if not cust_sales.empty else 0
        add_insight(
            "Customer Concentration", "bi-people-fill",
            f"The top 5 customers account for {top_5_pct:.1f}% of total sales.",
            f"A {'high' if top_5_pct > 50 else 'moderate'} level of customer concentration exists.",
            "Invest in customer acquisition campaigns to diversify the revenue base and reduce dependency on top accounts.",
            f"Losing top customers could risk up to {top_5_pct:.1f}% of total revenue."
        )

    # ── Time Series Insight ──
    if "Date" in mapped_cols and "Sales" in mapped_cols:
        dc, sc = mapped_cols["Date"], mapped_cols["Sales"]
        if pd.api.types.is_datetime64_any_dtype(df[dc]):
            monthly = df.groupby(df[dc].dt.to_period("M"))[sc].sum()
            if len(monthly) >= 2:
                growth = ((monthly.iloc[-1] - monthly.iloc[-2]) / max(1e-9, abs(monthly.iloc[-2]))) * 100
                direction = "grew" if growth >= 0 else "declined"
                add_insight(
                    "Sales Trend", "bi-graph-up-arrow",
                    f"Sales {direction} by {abs(growth):.1f}% in the most recent period.",
                    f"The {'positive' if growth >= 0 else 'negative'} monthly trend suggests {'momentum' if growth >= 0 else 'a slowdown'} in business activity.",
                    f"{'Scale operations and marketing to sustain momentum.' if growth >= 0 else 'Investigate root causes of the decline and launch corrective promotions.'}",
                    f"{'Ensure supply chain can support sustained growth.' if growth >= 0 else 'Extended decline risks customer attrition and market share loss.'}"
                )

    # ── Product Insight ──
    if "Product" in mapped_cols and "Sales" in mapped_cols:
        prc, sc = mapped_cols["Product"], mapped_cols["Sales"]
        prod_sales = df.groupby(prc)[sc].sum().sort_values(ascending=False)
        if len(prod_sales) > 0:
            top_prod = prod_sales.index[0]
            bottom_prod = prod_sales.index[-1] if len(prod_sales) > 1 else top_prod
            add_insight(
                "Product Performance", "bi-box-seam",
                f"'{top_prod}' leads sales. '{bottom_prod}' is the lowest-performing product.",
                "A clear performance gap exists between the top and bottom products.",
                f"Run clearance promotions for '{bottom_prod}'. Increase availability and upselling for '{top_prod}'.",
                "Low-selling products tie up working capital and warehouse space."
            )

    # ── Regional Insight ──
    if "Region" in mapped_cols and "Sales" in mapped_cols:
        rc, sc = mapped_cols["Region"], mapped_cols["Sales"]
        region_sales = df.groupby(rc)[sc].sum().sort_values(ascending=False)
        if len(region_sales) > 0:
            top_region = region_sales.index[0]
            top_pct = (region_sales.iloc[0] / region_sales.sum()) * 100
            add_insight(
                "Regional Analysis", "bi-geo-alt-fill",
                f"'{top_region}' contributes {top_pct:.1f}% of total regional sales.",
                f"{top_region} is the highest-performing geographic market.",
                f"Replicate the go-to-market strategy from {top_region} in underperforming regions.",
                "Geographic concentration in one region increases exposure to regional economic risks."
            )

    # ── Generic fallback ──
    if not insights:
        numeric_cols = df.select_dtypes(include=[np.number]).columns
        if len(numeric_cols) > 0:
            top_col = numeric_cols[0]
            add_insight(
                "Dataset Overview", "bi-clipboard-data",
                f"Dataset contains {len(df):,} rows and {len(df.columns)} columns. '{top_col}' has a mean of {df[top_col].mean():.2f}.",
                "Statistical patterns and distributions have been identified across the numeric features.",
                "Explore the correlation matrix and distribution charts below to find relationships between variables.",
                "Insufficient business context columns were detected; insights are statistical rather than operational."
            )

    return insights


# ──────────────────────────────────────────────
#  PDF Report Generator
# ──────────────────────────────────────────────
def generate_pdf_report(df: pd.DataFrame, mapped_cols: dict, clean_report: dict,
                        kpis: list, insights: list, stats: dict, filepath: str):
    """Generates a professional multi-section PDF report using ReportLab."""
    from reportlab.lib.pagesizes import letter
    from reportlab.lib import colors
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import inch
    from reportlab.platypus import (
        SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle,
        HRFlowable, PageBreak
    )

    doc = SimpleDocTemplate(filepath, pagesize=letter,
                            topMargin=0.75 * inch, bottomMargin=0.75 * inch,
                            leftMargin=0.75 * inch, rightMargin=0.75 * inch)
    styles = getSampleStyleSheet()

    # Custom styles
    primary_color = colors.HexColor("#3b82f6")
    header_style = ParagraphStyle("header", parent=styles["Heading1"],
                                  textColor=primary_color, fontSize=20, spaceAfter=6)
    section_style = ParagraphStyle("section", parent=styles["Heading2"],
                                   textColor=colors.HexColor("#1e293b"), fontSize=14, spaceAfter=4)
    sub_style = ParagraphStyle("sub", parent=styles["Heading3"],
                               textColor=colors.HexColor("#475569"), fontSize=11)
    normal = styles["Normal"]
    normal.fontSize = 10

    elements = []

    def make_table(data, col_widths=None, header_bg=colors.HexColor("#3b82f6")):
        t = Table(data, colWidths=col_widths)
        row_colors = [
            ("BACKGROUND", (0, 0), (-1, 0), header_bg),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.whitesmoke, colors.white]),
            ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cbd5e1")),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ("TOPPADDING", (0, 0), (-1, -1), 6),
        ]
        t.setStyle(TableStyle(row_colors))
        return t

    def section_divider():
        elements.append(Spacer(1, 8))
        elements.append(HRFlowable(width="100%", thickness=1,
                                   color=colors.HexColor("#e2e8f0")))
        elements.append(Spacer(1, 8))

    # ── Cover Page ──
    elements.append(Spacer(1, 1 * inch))
    elements.append(Paragraph("Universal CSV Analytics Platform", header_style))
    elements.append(Paragraph("Automated Data Analysis Report", section_style))
    elements.append(Spacer(1, 0.25 * inch))
    elements.append(Paragraph(f"Dataset: {clean_report['original_rows']:,} rows × "
                               f"{clean_report['original_cols']} columns", normal))
    elements.append(Paragraph(f"Data Health Score: {clean_report['health_score']} / 100", normal))
    elements.append(Spacer(1, 0.5 * inch))
    elements.append(PageBreak())

    # ── Executive Summary ──
    elements.append(Paragraph("1. Executive Summary", header_style))
    section_divider()
    summary_text = (
        f"This report was automatically generated by the Universal CSV Analytics Platform. "
        f"The uploaded dataset contains <b>{clean_report['original_rows']:,} rows</b> and "
        f"<b>{clean_report['original_cols']} columns</b>. After cleaning, the final dataset "
        f"contains <b>{clean_report['final_rows']:,} rows</b> and "
        f"<b>{clean_report['final_cols']} columns</b>. "
        f"The Data Health Score is <b>{clean_report['health_score']}/100</b>."
    )
    elements.append(Paragraph(summary_text, normal))
    elements.append(Spacer(1, 0.25 * inch))

    # Detected mappings
    if mapped_cols:
        elements.append(Paragraph("Detected Business Columns", sub_style))
        map_data = [["Standard Metric", "Detected Column Name"]]
        for k, v in mapped_cols.items():
            map_data.append([k, v])
        elements.append(make_table(map_data, col_widths=[2.5 * inch, 4 * inch]))
    elements.append(Spacer(1, 0.25 * inch))

    # ── Data Cleaning Report ──
    elements.append(Paragraph("2. Data Cleaning Report", header_style))
    section_divider()
    cleaning_data = [
        ["Metric", "Value"],
        ["Original Rows", f"{clean_report['original_rows']:,}"],
        ["Original Columns", f"{clean_report['original_cols']}"],
        ["Duplicate Rows Removed", f"{clean_report['duplicate_rows']:,}"],
        ["Missing Values Before", f"{clean_report['missing_before']:,}"],
        ["Missing Values After", f"{clean_report['missing_after']:,}"],
        ["Final Rows", f"{clean_report['final_rows']:,}"],
        ["Final Columns", f"{clean_report['final_cols']}"],
        ["Health Score", f"{clean_report['health_score']} / 100"],
    ]
    elements.append(make_table(cleaning_data, col_widths=[3.5 * inch, 3 * inch]))
    elements.append(Spacer(1, 0.15 * inch))

    if clean_report.get("actions_taken"):
        elements.append(Paragraph("Cleaning Actions Taken:", sub_style))
        for action in clean_report["actions_taken"]:
            elements.append(Paragraph(f"• {action}", normal))

    elements.append(Spacer(1, 0.25 * inch))

    # ── KPI Summary ──
    elements.append(Paragraph("3. Key Performance Indicators", header_style))
    section_divider()
    kpi_data = [["KPI", "Value"]]
    for kpi in kpis:
        kpi_data.append([kpi["label"], kpi["value"]])
    elements.append(make_table(kpi_data, col_widths=[3.5 * inch, 3 * inch]))
    elements.append(Spacer(1, 0.25 * inch))

    # ── Statistical Analysis ──
    elements.append(Paragraph("4. Statistical Analysis", header_style))
    section_divider()
    if stats:
        stat_header = ["Column", "Mean", "Median", "Std Dev", "Min", "Max", "Skewness"]
        stat_rows = [stat_header]
        for col, s in list(stats.items())[:8]:  # Limit to 8 cols for PDF width
            stat_rows.append([
                col[:20],
                str(s["mean"]), str(s["median"]),
                str(s["std"]), str(s["min"]), str(s["max"]),
                str(s["skewness"])
            ])
        elements.append(make_table(stat_rows))
    else:
        elements.append(Paragraph("No numeric columns found for statistical analysis.", normal))
    elements.append(Spacer(1, 0.25 * inch))

    # ── Business Insights ──
    elements.append(Paragraph("5. AI Business Insights & Recommendations", header_style))
    section_divider()
    for ins in insights:
        elements.append(Paragraph(ins["section"], sub_style))
        elements.append(Paragraph(f"<b>Observation:</b> {ins['observation']}", normal))
        elements.append(Paragraph(f"<b>Insight:</b> {ins['insight']}", normal))
        elements.append(Paragraph(f"<b>Recommendation:</b> {ins['recommendation']}", normal))
        if ins.get("risk"):
            elements.append(Paragraph(f"<b>Risk:</b> {ins['risk']}", normal))
        elements.append(Spacer(1, 0.15 * inch))

    # ── Conclusion ──
    elements.append(PageBreak())
    elements.append(Paragraph("6. Conclusion", header_style))
    section_divider()
    conclusion = (
        "This automated analysis was produced by the Universal CSV Analytics Platform. "
        "The insights and recommendations above are generated from statistical patterns "
        "detected in the dataset. For critical business decisions, we recommend validating "
        "these findings with domain experts and incorporating additional data sources."
    )
    elements.append(Paragraph(conclusion, normal))

    doc.build(elements)


# ──────────────────────────────────────────────
#  Routes
# ──────────────────────────────────────────────
@app.route("/")
def index():
    return render_template("index.html")


@app.route("/upload", methods=["POST"])
def upload_file():
    if "file" not in request.files:
        return jsonify({"error": "No file part in request"}), 400

    file = request.files["file"]
    if not file or file.filename == "":
        return jsonify({"error": "No file selected"}), 400

    valid_ext = file.filename.lower().endswith((".csv", ".xlsx", ".xls"))
    if not valid_ext:
        return jsonify({"error": "Only CSV and Excel files are accepted"}), 400

    try:
        filename = secure_filename(file.filename)
        unique_name = f"{uuid.uuid4().hex}_{filename}"
        filepath = os.path.join(app.config["UPLOAD_FOLDER"], unique_name)
        file.save(filepath)

        # Quick read for preview
        df_preview = load_dataframe(filepath, nrows=200)

        # Memory usage estimation (full file)
        total_lines = sum(1 for _ in open(filepath, encoding="utf-8", errors="ignore")) - 1
        approx_mem = os.path.getsize(filepath) / (1024 * 1024)

        dtypes = df_preview.dtypes.astype(str).to_dict()
        missing = df_preview.isnull().sum().to_dict()

        return jsonify({
            "success": True,
            "filename": unique_name,
            "original_name": file.filename,
            "rows_estimate": total_lines,
            "columns": list(df_preview.columns),
            "dtypes": dtypes,
            "missing": {k: int(v) for k, v in missing.items()},
            "duplicates": int(df_preview.duplicated().sum()),
            "memory_mb": round(approx_mem, 2),
            "preview": df_preview.head(10).fillna("").to_dict(orient="records"),
        })
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": f"Upload failed: {exc}"}), 500


@app.route("/analyze/<filename>", methods=["GET"])
def analyze(filename):
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "File not found. Please re-upload."}), 404

    try:
        df = load_dataframe(filepath)
    except Exception as exc:
        return jsonify({"error": f"Could not read file: {exc}"}), 500

    try:
        # 1. Clean
        df, clean_report = clean_data(df)

        # 2. Detect columns
        mapped_cols = detect_columns(df)
        col_types = classify_columns(df)

        # 3. Parse dates
        if "Date" in mapped_cols:
            try:
                df[mapped_cols["Date"]] = pd.to_datetime(
                    df[mapped_cols["Date"]], infer_datetime_format=True, errors="coerce"
                )
                df = df.dropna(subset=[mapped_cols["Date"]])
            except Exception:
                del mapped_cols["Date"]

        # 4. KPIs
        kpis = generate_kpis(df, mapped_cols)

        # 5. Statistics
        stats = generate_statistics(df)

        # 6. Charts
        charts = generate_all_charts(df, mapped_cols)

        # 7. Insights
        insights = generate_insights(df, mapped_cols)

        return jsonify({
            "success": True,
            "clean_report": clean_report,
            "mapped_columns": mapped_cols,
            "col_types": col_types,
            "kpis": kpis,
            "statistics": stats,
            "charts": charts,
            "insights": insights,
        })

    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": f"Analysis failed: {exc}"}), 500


@app.route("/download/<fmt>/<filename>")
def download_report(fmt, filename):
    filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)
    if not os.path.exists(filepath):
        return jsonify({"error": "File not found"}), 404

    try:
        df = load_dataframe(filepath)
        df, clean_report = clean_data(df)
        mapped_cols = detect_columns(df)

        if "Date" in mapped_cols:
            try:
                df[mapped_cols["Date"]] = pd.to_datetime(
                    df[mapped_cols["Date"]], infer_datetime_format=True, errors="coerce"
                )
            except Exception:
                pass

        uid = uuid.uuid4().hex[:8]

        if fmt == "csv":
            out = os.path.join(app.config["REPORT_FOLDER"], f"cleaned_{uid}.csv")
            df.to_csv(out, index=False)
            return send_file(out, as_attachment=True, download_name="cleaned_data.csv",
                             mimetype="text/csv")

        elif fmt == "excel":
            out = os.path.join(app.config["REPORT_FOLDER"], f"report_{uid}.xlsx")
            with pd.ExcelWriter(out, engine="openpyxl") as writer:
                df.to_excel(writer, sheet_name="Cleaned Data", index=False)

                # Stats sheet
                stats = generate_statistics(df)
                if stats:
                    stats_df = pd.DataFrame(stats).T
                    stats_df.to_excel(writer, sheet_name="Statistics")

                # KPIs sheet
                kpis = generate_kpis(df, mapped_cols)
                kpi_df = pd.DataFrame([{"KPI": k["label"], "Value": k["value"]} for k in kpis])
                kpi_df.to_excel(writer, sheet_name="KPIs", index=False)

            return send_file(out, as_attachment=True, download_name="analytics_report.xlsx",
                             mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

        elif fmt == "pdf":
            out = os.path.join(app.config["REPORT_FOLDER"], f"report_{uid}.pdf")
            kpis = generate_kpis(df, mapped_cols)
            insights = generate_insights(df, mapped_cols)
            stats = generate_statistics(df)
            generate_pdf_report(df, mapped_cols, clean_report, kpis, insights, stats, out)
            return send_file(out, as_attachment=True, download_name="analytics_report.pdf",
                             mimetype="application/pdf")

        return jsonify({"error": "Invalid format. Use csv, excel, or pdf."}), 400

    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": f"Report generation failed: {exc}"}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
