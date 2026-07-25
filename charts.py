"""
charts.py  —  Universal CSV Analytics Platform
Generates all Plotly charts based on available columns.
Charts are returned as JSON strings for safe transfer over the API.
"""
import json
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import plotly.io as pio
from plotly.subplots import make_subplots


# ──────────────────────────────────────────────
#  Shared Theme Helpers
# ──────────────────────────────────────────────
PALETTE = px.colors.qualitative.Vivid
BLUE_SEQ = px.colors.sequential.Blues
TEAL_SEQ = px.colors.sequential.Teal

LAYOUT_BASE = dict(
    paper_bgcolor="rgba(0,0,0,0)",
    plot_bgcolor="rgba(0,0,0,0)",
    font=dict(family="Inter, system-ui, sans-serif", size=12, color="#94a3b8"),
    title_font=dict(size=16, color="#f8fafc", family="Outfit, sans-serif"),
    legend=dict(
        bgcolor="rgba(30,41,59,0.6)",
        bordercolor="rgba(255,255,255,0.1)",
        borderwidth=1,
        font=dict(color="#cbd5e1"),
    ),
    margin=dict(l=50, r=30, t=60, b=50),
    hoverlabel=dict(
        bgcolor="#1e293b",
        font_size=12,
        font_color="#f8fafc",
        bordercolor="rgba(59,130,246,0.6)",
    ),
    xaxis=dict(
        gridcolor="rgba(255,255,255,0.05)",
        showgrid=True,
        zeroline=False,
        linecolor="rgba(255,255,255,0.1)",
        tickfont=dict(color="#94a3b8"),
    ),
    yaxis=dict(
        gridcolor="rgba(255,255,255,0.05)",
        showgrid=True,
        zeroline=False,
        linecolor="rgba(255,255,255,0.1)",
        tickfont=dict(color="#94a3b8"),
    ),
)


def _styled(fig) -> go.Figure:
    """Apply shared dark layout to any figure."""
    fig.update_layout(**LAYOUT_BASE)
    return fig


def _to_json(fig) -> str:
    """Serialize figure to JSON string."""
    return pio.to_json(fig)


def _safe_chart(func, *args, **kwargs):
    """Wraps chart generation to prevent crashes — returns None on error."""
    try:
        return func(*args, **kwargs)
    except Exception:
        return None


# ──────────────────────────────────────────────
#  Sales Charts
# ──────────────────────────────────────────────
def chart_sales_by_category(df, sales_col, cat_col):
    data = df.groupby(cat_col)[sales_col].sum().reset_index().sort_values(
        sales_col, ascending=False).head(12)
    fig = px.bar(data, x=cat_col, y=sales_col,
                 title=f"Sales by {cat_col}",
                 color=sales_col, color_continuous_scale=BLUE_SEQ,
                 text_auto=".2s")
    fig.update_traces(textfont_size=11, textangle=0, textposition="outside",
                      cliponaxis=False, marker_line_width=0)
    fig.update_coloraxes(showscale=False)
    return _to_json(_styled(fig))


def chart_sales_donut(df, sales_col, cat_col):
    data = df.groupby(cat_col)[sales_col].sum().reset_index().sort_values(
        sales_col, ascending=False).head(8)
    fig = px.pie(data, names=cat_col, values=sales_col,
                 title=f"{sales_col} Share by {cat_col}",
                 color_discrete_sequence=PALETTE, hole=0.5)
    fig.update_traces(textposition="outside", textinfo="percent+label",
                      pull=[0.04] + [0] * (len(data) - 1))
    return _to_json(_styled(fig))


def chart_sales_histogram(df, sales_col):
    fig = px.histogram(df, x=sales_col, nbins=40,
                       title=f"Distribution of {sales_col}",
                       marginal="box", color_discrete_sequence=["#3b82f6"])
    fig.update_traces(marker_line_width=0.5, marker_line_color="#1e3a5f")
    return _to_json(_styled(fig))


def chart_sales_box(df, sales_col, cat_col=None):
    if cat_col and df[cat_col].nunique() <= 15:
        fig = px.box(df, x=cat_col, y=sales_col,
                     title=f"{sales_col} Distribution by {cat_col}",
                     color=cat_col, color_discrete_sequence=PALETTE,
                     points="outliers")
    else:
        fig = px.box(df, y=sales_col,
                     title=f"Box Plot: {sales_col}",
                     color_discrete_sequence=["#8b5cf6"], points="all")
    return _to_json(_styled(fig))


def chart_top_products(df, sales_col, prod_col, n=15):
    data = df.groupby(prod_col)[sales_col].sum().reset_index().sort_values(
        sales_col, ascending=False).head(n)
    fig = px.bar(data, x=sales_col, y=prod_col, orientation="h",
                 title=f"Top {n} Products by {sales_col}",
                 color=sales_col, color_continuous_scale=TEAL_SEQ,
                 text_auto=".2s")
    fig.update_layout(yaxis=dict(categoryorder="total ascending", tickfont=dict(color="#94a3b8")))
    fig.update_coloraxes(showscale=False)
    return _to_json(_styled(fig))


def chart_worst_products(df, sales_col, prod_col, n=10):
    data = df.groupby(prod_col)[sales_col].sum().reset_index().sort_values(
        sales_col).head(n)
    fig = px.bar(data, x=sales_col, y=prod_col, orientation="h",
                 title=f"Bottom {n} Products (Lowest Sales)",
                 color=sales_col,
                 color_continuous_scale=["#ef4444", "#f59e0b"],
                 text_auto=".2s")
    fig.update_layout(yaxis=dict(categoryorder="total descending", tickfont=dict(color="#94a3b8")))
    fig.update_coloraxes(showscale=False)
    return _to_json(_styled(fig))


# ──────────────────────────────────────────────
#  Time Series Charts
# ──────────────────────────────────────────────
def chart_monthly_trend(df, date_col, sales_col):
    monthly = df.groupby(df[date_col].dt.to_period("M"))[sales_col].sum().reset_index()
    monthly[date_col] = monthly[date_col].dt.to_timestamp()
    fig = px.area(monthly, x=date_col, y=sales_col,
                  title=f"Monthly {sales_col} Trend",
                  color_discrete_sequence=["#3b82f6"])
    fig.update_traces(line_shape="spline", line=dict(width=2.5),
                      fillcolor="rgba(59,130,246,0.15)")
    return _to_json(_styled(fig))


def chart_quarterly_sales(df, date_col, sales_col):
    df_q = df.copy()
    df_q["Quarter"] = df_q[date_col].dt.to_period("Q").astype(str)
    data = df_q.groupby("Quarter")[sales_col].sum().reset_index()
    fig = px.bar(data, x="Quarter", y=sales_col,
                 title=f"Quarterly {sales_col}",
                 color=sales_col, color_continuous_scale=BLUE_SEQ,
                 text_auto=".2s")
    fig.update_coloraxes(showscale=False)
    return _to_json(_styled(fig))


def chart_yearly_trend(df, date_col, sales_col):
    df["_Year"] = df[date_col].dt.year
    data = df.groupby("_Year")[sales_col].sum().reset_index()
    df.drop(columns=["_Year"], inplace=True, errors="ignore")
    fig = px.bar(data, x="_Year", y=sales_col,
                 title=f"Yearly {sales_col}",
                 color=sales_col, color_continuous_scale=TEAL_SEQ,
                 text_auto=".2s")
    fig.update_xaxes(type="category")
    fig.update_coloraxes(showscale=False)
    return _to_json(_styled(fig))


def chart_rolling_average(df, date_col, sales_col, window=3):
    monthly = df.groupby(df[date_col].dt.to_period("M"))[sales_col].sum().reset_index()
    monthly[date_col] = monthly[date_col].dt.to_timestamp()
    monthly["Rolling Avg"] = monthly[sales_col].rolling(window=window).mean()

    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=monthly[date_col], y=monthly[sales_col],
        mode="lines", name=sales_col,
        line=dict(color="#64748b", width=1.5, dash="dot"),
    ))
    fig.add_trace(go.Scatter(
        x=monthly[date_col], y=monthly["Rolling Avg"],
        mode="lines", name=f"{window}-Month Rolling Avg",
        line=dict(color="#f59e0b", width=2.5),
        fill="tozeroy", fillcolor="rgba(245,158,11,0.08)",
    ))
    fig.update_layout(title=f"{sales_col} with {window}-Month Rolling Average", **LAYOUT_BASE)
    return _to_json(fig)


# ──────────────────────────────────────────────
#  Profit Charts
# ──────────────────────────────────────────────
def chart_profit_by_category(df, profit_col, cat_col):
    data = df.groupby(cat_col)[profit_col].sum().reset_index().sort_values(profit_col)
    colors_list = ["#ef4444" if v < 0 else "#10b981" for v in data[profit_col]]
    fig = px.bar(data, x=cat_col, y=profit_col,
                 title=f"Profit by {cat_col}  (Red = Loss)",
                 text_auto=".2s")
    fig.update_traces(marker_color=colors_list, marker_line_width=0)
    fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
    return _to_json(_styled(fig))


def chart_profit_trend(df, date_col, profit_col):
    monthly = df.groupby(df[date_col].dt.to_period("M"))[profit_col].sum().reset_index()
    monthly[date_col] = monthly[date_col].dt.to_timestamp()
    monthly["color"] = monthly[profit_col].apply(lambda x: "#10b981" if x >= 0 else "#ef4444")
    fig = px.bar(monthly, x=date_col, y=profit_col,
                 title=f"Monthly {profit_col} Trend")
    fig.update_traces(marker_color=monthly["color"].tolist())
    fig.add_hline(y=0, line_dash="dash", line_color="rgba(255,255,255,0.3)")
    return _to_json(_styled(fig))


def chart_discount_vs_profit(df, discount_col, profit_col):
    fig = px.scatter(df.sample(min(len(df), 1000)), x=discount_col, y=profit_col,
                     title=f"Discount vs {profit_col}",
                     color=profit_col,
                     color_continuous_scale=["#ef4444", "#94a3b8", "#10b981"],
                     opacity=0.65, trendline="ols")
    fig.update_coloraxes(showscale=False)
    return _to_json(_styled(fig))


# ──────────────────────────────────────────────
#  Customer Charts
# ──────────────────────────────────────────────
def chart_top_customers(df, sales_col, cust_col, n=15):
    data = df.groupby(cust_col)[sales_col].sum().reset_index().sort_values(
        sales_col, ascending=False).head(n)
    fig = px.bar(data, x=sales_col, y=cust_col, orientation="h",
                 title=f"Top {n} Customers by Revenue",
                 color=sales_col, color_continuous_scale=BLUE_SEQ,
                 text_auto=".2s")
    fig.update_layout(yaxis=dict(categoryorder="total ascending", tickfont=dict(color="#94a3b8")))
    fig.update_coloraxes(showscale=False)
    return _to_json(_styled(fig))


def chart_customer_frequency(df, cust_col):
    freq = df[cust_col].value_counts().reset_index()
    freq.columns = [cust_col, "Order Count"]
    fig = px.histogram(freq, x="Order Count", nbins=30,
                       title="Customer Order Frequency Distribution",
                       color_discrete_sequence=["#8b5cf6"])
    return _to_json(_styled(fig))


# ──────────────────────────────────────────────
#  Regional Charts
# ──────────────────────────────────────────────
def chart_sales_by_region(df, sales_col, region_col):
    data = df.groupby(region_col)[sales_col].sum().reset_index().sort_values(
        sales_col, ascending=False).head(20)
    fig = px.bar(data, x=region_col, y=sales_col,
                 title=f"Sales by {region_col}",
                 color=sales_col, color_continuous_scale=TEAL_SEQ,
                 text_auto=".2s")
    fig.update_coloraxes(showscale=False)
    return _to_json(_styled(fig))


def chart_region_treemap(df, sales_col, region_col, cat_col=None):
    if cat_col:
        fig = px.treemap(df, path=[region_col, cat_col], values=sales_col,
                         title=f"Treemap: {sales_col} by {region_col} & {cat_col}",
                         color=sales_col, color_continuous_scale=BLUE_SEQ)
    else:
        fig = px.treemap(df, path=[region_col], values=sales_col,
                         title=f"Treemap: {sales_col} by {region_col}",
                         color=sales_col, color_continuous_scale=BLUE_SEQ)
    fig.update_traces(textinfo="label+value+percent root")
    return _to_json(_styled(fig))


# ──────────────────────────────────────────────
#  Generic Statistical Charts
# ──────────────────────────────────────────────
def chart_correlation_matrix(df, numeric_cols):
    corr = df[numeric_cols].corr()
    fig = px.imshow(corr, text_auto=".2f",
                    title="Feature Correlation Matrix",
                    color_continuous_scale="RdBu_r",
                    zmin=-1, zmax=1)
    fig.update_layout(title_font=dict(size=15, color="#f8fafc"), **{k: v for k, v in LAYOUT_BASE.items() if k != "title_font"})
    return _to_json(fig)


def chart_scatter_matrix(df, numeric_cols, color_col=None):
    cols = numeric_cols[:5]  # Limit for readability
    fig = px.scatter_matrix(df.sample(min(len(df), 500)),
                            dimensions=cols,
                            color=color_col if color_col else None,
                            title="Scatter Matrix (Pair Plot)",
                            color_discrete_sequence=PALETTE,
                            opacity=0.5)
    fig.update_traces(diagonal_visible=False, marker=dict(size=3))
    return _to_json(_styled(fig))


def chart_distribution_subplots(df, numeric_cols):
    """Creates a 2-column grid of histograms for the top 6 numeric columns."""
    cols = numeric_cols[:6]
    n = len(cols)
    rows = (n + 1) // 2
    fig = make_subplots(rows=rows, cols=2,
                        subplot_titles=[f"Distribution: {c}" for c in cols])

    palette = ["#3b82f6", "#8b5cf6", "#10b981", "#f59e0b", "#ef4444", "#06b6d4"]
    for i, col in enumerate(cols):
        r, c = divmod(i, 2)
        fig.add_trace(
            go.Histogram(x=df[col], name=col, nbinsx=30,
                         marker_color=palette[i % len(palette)],
                         marker_line_width=0, showlegend=False),
            row=r + 1, col=c + 1
        )

    fig.update_layout(
        title_text="Numeric Feature Distributions",
        height=max(300, rows * 280),
        **LAYOUT_BASE
    )
    for axis in fig.layout:
        if "xaxis" in axis or "yaxis" in axis:
            fig.layout[axis]["gridcolor"] = "rgba(255,255,255,0.05)"
            fig.layout[axis]["tickfont"] = dict(color="#94a3b8")

    return _to_json(fig)


def chart_box_subplots(df, numeric_cols):
    """Multi-column box plot for outlier detection."""
    cols = numeric_cols[:8]
    fig = go.Figure()
    palette = ["#3b82f6", "#8b5cf6", "#10b981", "#f59e0b",
               "#ef4444", "#06b6d4", "#f97316", "#84cc16"]
    for i, col in enumerate(cols):
        fig.add_trace(go.Box(
            y=df[col], name=col,
            marker_color=palette[i % len(palette)],
            line_color=palette[i % len(palette)],
            boxpoints="outliers"
        ))
    fig.update_layout(title="Box Plots — Outlier Detection", **LAYOUT_BASE)
    return _to_json(fig)


def chart_missing_values(df):
    """Bar chart of missing value counts."""
    missing = df.isnull().sum()
    missing = missing[missing > 0].sort_values(ascending=False)
    if missing.empty:
        return None
    fig = px.bar(x=missing.index, y=missing.values,
                 title="Missing Values by Column",
                 labels={"x": "Column", "y": "Missing Count"},
                 color=missing.values,
                 color_continuous_scale=["#10b981", "#f59e0b", "#ef4444"])
    fig.update_coloraxes(showscale=False)
    return _to_json(_styled(fig))


def chart_categorical_frequency(df, cat_col, limit=20):
    """Horizontal bar chart for a categorical column's top values."""
    counts = df[cat_col].value_counts().head(limit).reset_index()
    counts.columns = [cat_col, "Count"]
    fig = px.bar(counts, x="Count", y=cat_col, orientation="h",
                 title=f"Value Frequency: {cat_col}",
                 color="Count", color_continuous_scale=BLUE_SEQ,
                 text_auto=True)
    fig.update_layout(yaxis=dict(categoryorder="total ascending", tickfont=dict(color="#94a3b8")))
    fig.update_coloraxes(showscale=False)
    return _to_json(_styled(fig))


# ──────────────────────────────────────────────
#  ABC Analysis (Product segmentation)
# ──────────────────────────────────────────────
def chart_abc_analysis(df, sales_col, prod_col):
    prod_sales = df.groupby(prod_col)[sales_col].sum().sort_values(ascending=False).reset_index()
    prod_sales["Cumulative %"] = prod_sales[sales_col].cumsum() / prod_sales[sales_col].sum() * 100
    prod_sales["ABC"] = prod_sales["Cumulative %"].apply(
        lambda x: "A (Top 80%)" if x <= 80 else ("B (80-95%)" if x <= 95 else "C (Tail 5%)")
    )
    abc_summary = prod_sales.groupby("ABC").agg(
        Products=(prod_col, "count"),
        Total_Sales=(sales_col, "sum")
    ).reset_index()
    fig = px.bar(abc_summary, x="ABC", y="Total_Sales",
                 title="ABC Product Segmentation",
                 color="ABC", text_auto=".2s",
                 color_discrete_map={
                     "A (Top 80%)": "#10b981",
                     "B (80-95%)": "#f59e0b",
                     "C (Tail 5%)": "#ef4444"
                 })
    return _to_json(_styled(fig))


# ──────────────────────────────────────────────
#  Master Chart Dispatcher
# ──────────────────────────────────────────────
def generate_all_charts(df: pd.DataFrame, mapped_cols: dict) -> dict:
    """
    Calls chart functions based on available columns.
    Returns a dict of {chart_key: plotly_json_string | None}.
    """
    charts = {}
    sc = mapped_cols.get("Sales")
    pc = mapped_cols.get("Profit")
    dc = mapped_cols.get("Date")
    cc = mapped_cols.get("Customer")
    prc = mapped_cols.get("Product")
    catc = mapped_cols.get("Category")
    rc = mapped_cols.get("Region")
    disc = mapped_cols.get("Discount")

    numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_cols = df.select_dtypes(include=["object", "category"]).columns.tolist()

    # ── Sales Charts ──
    if sc and catc:
        charts["sales_by_category"] = _safe_chart(chart_sales_by_category, df, sc, catc)
        charts["sales_donut"] = _safe_chart(chart_sales_donut, df, sc, catc)
        charts["sales_box"] = _safe_chart(chart_sales_box, df, sc, catc)
    elif sc:
        charts["sales_histogram"] = _safe_chart(chart_sales_histogram, df, sc)
        charts["sales_box"] = _safe_chart(chart_sales_box, df, sc)

    if sc and prc:
        charts["top_products"] = _safe_chart(chart_top_products, df, sc, prc)
        charts["worst_products"] = _safe_chart(chart_worst_products, df, sc, prc)
        charts["abc_analysis"] = _safe_chart(chart_abc_analysis, df, sc, prc)

    # ── Time Series Charts ──
    if dc and sc and pd.api.types.is_datetime64_any_dtype(df[dc]):
        charts["monthly_trend"] = _safe_chart(chart_monthly_trend, df, dc, sc)
        charts["quarterly_sales"] = _safe_chart(chart_quarterly_sales, df, dc, sc)
        charts["yearly_trend"] = _safe_chart(chart_yearly_trend, df, dc, sc)
        charts["rolling_average"] = _safe_chart(chart_rolling_average, df, dc, sc)

    # ── Profit Charts ──
    if pc and catc:
        charts["profit_by_category"] = _safe_chart(chart_profit_by_category, df, pc, catc)
    if pc and dc and pd.api.types.is_datetime64_any_dtype(df[dc]):
        charts["profit_trend"] = _safe_chart(chart_profit_trend, df, dc, pc)
    if pc and disc:
        charts["discount_vs_profit"] = _safe_chart(chart_discount_vs_profit, df, disc, pc)

    # ── Customer Charts ──
    if cc and sc:
        charts["top_customers"] = _safe_chart(chart_top_customers, df, sc, cc)
    if cc:
        charts["customer_frequency"] = _safe_chart(chart_customer_frequency, df, cc)

    # ── Regional Charts ──
    if rc and sc:
        charts["sales_by_region"] = _safe_chart(chart_sales_by_region, df, sc, rc)
        charts["region_treemap"] = _safe_chart(chart_region_treemap, df, sc, rc, catc)

    # ── Generic Statistical Charts (always generated if numeric cols exist) ──
    if len(numeric_cols) >= 2:
        charts["correlation_matrix"] = _safe_chart(chart_correlation_matrix, df, numeric_cols[:10])
        charts["scatter_matrix"] = _safe_chart(chart_scatter_matrix, df, numeric_cols,
                                               catc if catc and df[catc].nunique() <= 8 else None)

    if len(numeric_cols) >= 1:
        charts["distributions"] = _safe_chart(chart_distribution_subplots, df, numeric_cols)
        charts["box_plots"] = _safe_chart(chart_box_subplots, df, numeric_cols)

    charts["missing_values"] = _safe_chart(chart_missing_values, df)

    # Frequency chart for the first categorical column (if not already handled)
    if categorical_cols:
        first_cat = categorical_cols[0]
        if first_cat not in [catc, rc, cc, prc]:
            charts["categorical_frequency"] = _safe_chart(chart_categorical_frequency, df, first_cat)

    return charts
