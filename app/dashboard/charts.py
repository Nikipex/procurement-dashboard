import pandas as pd
import plotly.graph_objects as go
from loguru import logger

def build_abc_distribution_chart(df: pd.DataFrame) -> str:
    """
    Build ABC distribution vertical bar chart.
    Simple, stable visualization.
    """
    if df.empty or "abc_class" not in df.columns:
        return "<div>Нет данных ABC</div>"
    
    abc_counts = df["abc_class"].value_counts().sort_index()
    
    # Ensure all classes are represented
    for cls in ["A", "B", "C"]:
        if cls not in abc_counts.index:
            abc_counts[cls] = 0
    abc_counts = abc_counts.sort_index()
    
    colors = {
        "A": "#EF5350",  # Red
        "B": "#FFA726",  # Orange
        "C": "#66BB6A"   # Green
    }
    
    fig = go.Figure(data=[go.Bar(
        x=abc_counts.index,
        y=abc_counts.values,
        marker_color=[colors.get(cls, "#90A4AE") for cls in abc_counts.index],
        text=abc_counts.values,
        textposition="outside",
        textfont_size=14,
        textfont_weight="bold",
        width=0.6
    )])
    
    fig.update_layout(
        title="Распределение ABC",
        xaxis_title="Класс",
        yaxis_title="Количество позиций",
        height=350,
        showlegend=False,
        margin=dict(l=50, r=20, t=50, b=50),
        xaxis=dict(tickfont_size=14),
        yaxis=dict(tickfont_size=12)
    )
    
    return fig.to_html(full_html=False, include_plotlyjs='cdn')

def build_velocity_distribution_chart(df: pd.DataFrame) -> str:
    """
    Build velocity distribution vertical bar chart.
    Simple, stable visualization.
    """
    if df.empty or "velocity_segment" not in df.columns:
        return "<div>Нет данных по оборачиваемости</div>"
    
    velocity_counts = df["velocity_segment"].value_counts()
    
    # Ensure consistent ordering
    order = ["FAST", "MEDIUM", "SLOW"]
    velocity_counts = velocity_counts.reindex([v for v in order if v in velocity_counts.index])
    
    # Fill missing with 0
    for seg in order:
        if seg not in velocity_counts.index:
            velocity_counts[seg] = 0
    velocity_counts = velocity_counts.reindex(order)
    
    colors = {
        "FAST": "#EF5350",    # Red
        "MEDIUM": "#FFA726",  # Orange
        "SLOW": "#66BB6A"     # Green
    }
    
    # Russian labels for x-axis
    x_labels = {
        "FAST": "Быстрая",
        "MEDIUM": "Средняя",
        "SLOW": "Медленная"
    }
    
    x_display = [x_labels.get(v, v) for v in velocity_counts.index]
    
    fig = go.Figure(data=[go.Bar(
        x=x_display,
        y=velocity_counts.values,
        marker_color=[colors.get(v, "#90A4AE") for v in velocity_counts.index],
        text=velocity_counts.values,
        textposition="outside",
        textfont_size=14,
        textfont_weight="bold",
        width=0.6
    )])
    
    fig.update_layout(
        title="Распределение по оборачиваемости",
        xaxis_title="Сегмент",
        yaxis_title="Количество позиций",
        height=350,
        showlegend=False,
        margin=dict(l=50, r=20, t=50, b=50),
        xaxis=dict(tickfont_size=14),
        yaxis=dict(tickfont_size=12)
    )
    
    return fig.to_html(full_html=False, include_plotlyjs='cdn')

def build_top_risk_chart(df: pd.DataFrame, top_n: int = 10) -> str:
    """
    Build top risk items horizontal bar chart.
    Shows critical items sorted by priority.
    """
    if df.empty or "critical_flag" not in df.columns:
        return "<div>Нет данных по рискам</div>"

    # Filter critical items
    critical_df = df[df["critical_flag"] == True].copy()

    if critical_df.empty:
        return "<div>Нет критичных позиций</div>"

    # Sort by priority: ABC (A>B>C), days_of_cover, recommended_order_qty
    abc_priority = {"A": 0, "B": 1, "C": 2}
    critical_df["abc_priority"] = critical_df["abc_class"].map(abc_priority).fillna(3)

    sort_columns = ["abc_priority"]
    ascending = [True]

    if "days_of_cover" in critical_df.columns:
        sort_columns.append("days_of_cover")
        ascending.append(True)

    if "recommended_order_qty_display" in critical_df.columns:
        sort_columns.append("recommended_order_qty_display")
        ascending.append(False)
    else:
        critical_df["recommended_order_qty_display"] = 0

    critical_df = critical_df.sort_values(by=sort_columns, ascending=ascending)

    top_risk = critical_df.head(top_n).copy()

    if top_risk.empty:
        return "<div>Нет данных для отображения</div>"

    # Reverse for prettier horizontal bar ordering
    top_risk = top_risk.iloc[::-1]

    fig = go.Figure(
        data=[
            go.Bar(
                y=top_risk["product_name"].astype(str).str[:55],
                x=top_risk["recommended_order_qty_display"].fillna(0).astype(int),
                orientation="h",
                marker_color="#EF5350",
                text=top_risk["recommended_order_qty_display"].fillna(0).astype(int),
                textposition="inside",
                textfont_size=10,
            )
        ]
    )

    fig.update_layout(
        title=f"Топ-{top_n} критичных позиций",
        xaxis_title="Рекомендованное количество",
        yaxis_title="Наименование",
        height=max(360, len(top_risk) * 38),
        autosize=True,
        showlegend=False,
        margin=dict(l=360, r=20, t=60, b=50),
        xaxis=dict(tickfont_size=11),
        yaxis=dict(tickfont_size=10),
        paper_bgcolor="white",
        plot_bgcolor="white",
    )

    fig.update_traces(
        hovertemplate="Наименование: %{y}<br>Рекомендовано: %{x}<extra></extra>"
    )

    return fig.to_html(full_html=False, include_plotlyjs=False)