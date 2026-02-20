# employee_retention_dashboard.py
# Streamlit dashboard for Employee Retention Advisor (ERA)
# You will update DATA_PATH to your dataset file.

import os
import re
import math
import pandas as pd
import numpy as np
import streamlit as st
import plotly.express as px

# ----------------------------
# Config
# ----------------------------
st.set_page_config(page_title="Employee Retention Advisor", layout="wide")

DATA_PATH = "employee_retention_sample.xlsx"  # <-- CHANGE ME (xlsx or csv)
LOGO_PATH = "Screenshot 2026-02-13 at 9.17.27 AM copy 2.png"
SHEET_NAME = None  # set to a sheet name if needed, else None

# Columns expected (based on the synthetic dataset we generated). If your real data differs,
# update these mappings in one place.
COLS = {
    "id": "employee_id",
    "role": "role",
    "dept": "department",
    "loc": "location",
    "tenure": "tenure_months",
    "time_in_role": "time_in_role_months",
    "promotions": "promotions_last_24m",
    "salary_vs_market": "salary_vs_market_pct",
    "mgr_changes": "manager_changes_24m",
    "overtime": "overtime_hours_last_30d",
    "after_hours": "after_hours_work_freq",
    "pto": "pto_utilization_pct",
    "on_call": "on_call_burden",
    "engagement": "engagement_score",
    "enps": "enps",
    "one_on_one": "one_on_one_freq_per_month",
    "learning": "learning_hours_last_90d",
    "internal_apps": "internal_job_apps_6m",
    "perf_trend": "performance_trend",
    "missed_promos": "missed_promotions",
    "peer_feedback": "peer_feedback_score",
    "sentiment": "sentiment_summary",
    "risk_score": "flight_risk_score",
    "risk_cat": "risk_category",
    "risk_driver": "primary_risk_driver",
    "action": "recommended_action",
}

RISK_ORDER = ["Low", "Medium", "High"]
THRESHOLDS = {
    "burnout_high": 70,
    "mobility_pressure_high": 70,
    "engagement_low": 55,
    "enps_low": 0,
    "mgr_changes_high": 2,
}

ACTION_PLAYBOOK = {
    "High": {
        "Compensation Gap": "Comp review and adjustment proposal within 2 weeks.",
        "Burnout / Workload": "Reduce load, rebalance on-call, and mandate PTO recovery.",
        "Mobility Pressure": "Career pathing session; identify next role or stretch assignment.",
        "Low Engagement": "Manager 1:1 reset plan; re-align scope and recognition.",
        "Low eNPS": "Engagement follow-up and team health check.",
        "Performance Decline": "Coaching plan with clear goals and support.",
        "Missed Promotions": "Transparent promo criteria and timeline; interim recognition.",
        "Manager Instability": "Stabilize reporting line; clarify priorities.",
        "Other / Unspecified": "Manager review and stay interview within 2 weeks.",
    },
    "Medium": {
        "Compensation Gap": "Validate market data; plan for next comp cycle.",
        "Burnout / Workload": "Short-term workload relief and PTO encouragement.",
        "Mobility Pressure": "Discuss internal opportunities and development plan.",
        "Low Engagement": "Revisit role alignment and recognition cadence.",
        "Low eNPS": "Pulse feedback and localized team interventions.",
        "Performance Decline": "Lightweight coaching and remove blockers.",
        "Missed Promotions": "Clarify criteria; set near-term milestones.",
        "Manager Instability": "Increase touchpoints; reinforce goals.",
        "Other / Unspecified": "Manager check-in and data review.",
    },
    "Low": {
        "Compensation Gap": "Monitor; address in next review cycle if persistent.",
        "Burnout / Workload": "Encourage PTO and monitor workload.",
        "Mobility Pressure": "Support development and internal mobility.",
        "Low Engagement": "Maintain feedback cadence.",
        "Low eNPS": "Monitor sentiment; gather feedback.",
        "Performance Decline": "Regular check-ins and support.",
        "Missed Promotions": "Communicate growth path.",
        "Manager Instability": "Maintain clarity on goals.",
        "Other / Unspecified": "No immediate action; keep engaged.",
    },
}

px.defaults.template = "plotly_white"
px.defaults.color_discrete_sequence = [
    "#1E2EEA",
    "#1B74FF",
    "#1BA4FF",
    "#18C9D9",
    "#18E3B2",
]
px.defaults.color_continuous_scale = [
    [0.0, "#1E2EEA"],
    [0.5, "#1B74FF"],
    [1.0, "#18E3B2"],
]

st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@400;500;600;700&family=DM+Sans:wght@400;500;600&display=swap');
    :root{
        --c-blue-900:#0B1F5B;
        --c-blue-700:#1E2EEA;
        --c-blue-500:#1B74FF;
        --c-cyan-400:#18C9D9;
        --c-green-400:#18E3B2;
        --c-ink:#0D1B3A;
        --c-panel:#FFFFFF;
        --c-panel-soft:#F3F7FF;
    }
    html, body, [data-testid="stAppViewContainer"]{
        background: linear-gradient(140deg, #F6F8FF 0%, #F0F6FF 35%, #ECFBF7 100%);
        color: var(--c-ink);
        font-family: "DM Sans", "Segoe UI", sans-serif;
    }
    h1, h2, h3, h4, h5, h6, [data-testid="stMetricLabel"]{
        font-family: "Space Grotesk", "Segoe UI", sans-serif;
        color: var(--c-blue-900);
    }
    [data-testid="stSidebar"]{
        background: linear-gradient(180deg, #F7FAFF 0%, #F1F8FF 100%);
        border-right: 1px solid #E4ECFF;
    }
    [data-testid="stMetric"]{
        background: var(--c-panel);
        border: 1px solid #E8EEFF;
        border-radius: 12px;
        padding: 12px 14px;
        box-shadow: 0 6px 16px rgba(24, 201, 217, 0.08);
    }
    .stPlotlyChart, .stDataFrame, .stTable{
        background: var(--c-panel);
        border-radius: 12px;
        border: 1px solid #E8EEFF;
        padding: 6px;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ----------------------------
# Helpers
# ----------------------------
@st.cache_data(show_spinner=False)
def load_data(path: str) -> pd.DataFrame:
    if path.lower().endswith(".csv"):
        df = pd.read_csv(path)
    elif path.lower().endswith(".xlsx") or path.lower().endswith(".xls"):
        if SHEET_NAME is None:
            df = pd.read_excel(path)
        else:
            df = pd.read_excel(path, sheet_name=SHEET_NAME)
    else:
        raise ValueError("Unsupported file type. Use .csv or .xlsx/.xls")
    return df


def safe_col(df: pd.DataFrame, col: str) -> bool:
    return col in df.columns


def to_numeric_safe(s: pd.Series) -> pd.Series:
    return pd.to_numeric(s, errors="coerce")


def ensure_risk_category(df: pd.DataFrame) -> pd.DataFrame:
    """
    If risk_category isn't present, derive it from flight_risk_score.
    """
    cat_col = COLS["risk_cat"]
    score_col = COLS["risk_score"]
    if safe_col(df, cat_col):
        return df
    if safe_col(df, score_col):
        scores = to_numeric_safe(df[score_col])
        df[cat_col] = np.select(
            [scores < 35, (scores >= 35) & (scores < 65), scores >= 65],
            ["Low", "Medium", "High"],
            default="Unknown",
        )
    else:
        df[cat_col] = "Unknown"
    return df


def normalize_categoricals(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize common text fields to reduce filter noise.
    """
    for k in ["after_hours", "on_call", "perf_trend", "risk_cat"]:
        c = COLS[k]
        if safe_col(df, c):
            df[c] = df[c].astype(str).str.strip()
    return df


def compute_composites(df: pd.DataFrame) -> pd.DataFrame:
    """
    Optional: Add a few computed indices for dashboarding.
    These don't imply a production scoring model—just helpful visuals.
    """
    # Burnout Index (0-100) from overtime, PTO utilization (inverse), after-hours, on-call
    overtime = to_numeric_safe(df.get(COLS["overtime"], pd.Series([np.nan] * len(df))))
    pto = to_numeric_safe(df.get(COLS["pto"], pd.Series([np.nan] * len(df))))
    after_hours = df.get(COLS["after_hours"], pd.Series([""] * len(df))).astype(str).str.lower()
    on_call = df.get(COLS["on_call"], pd.Series([""] * len(df))).astype(str).str.lower()

    def map_level(x: str) -> float:
        if "none" in x:
            return 0.0
        if "low" in x:
            return 25.0
        if "medium" in x:
            return 60.0
        if "high" in x:
            return 90.0
        return np.nan

    after_score = after_hours.map(map_level)
    on_call_score = on_call.map(map_level)

    # Scale overtime: assume 0-60 hours maps to 0-100
    overtime_score = (overtime.clip(lower=0, upper=60) / 60.0) * 100.0

    # PTO utilization: low PTO use can be a burnout signal (inverse, 0-100)
    pto_score = (100.0 - pto.clip(lower=0, upper=100))

    burnout_index = np.nanmean(
        np.vstack([overtime_score.values, pto_score.values, after_score.values, on_call_score.values]),
        axis=0,
    )
    df["burnout_index"] = np.round(burnout_index, 1)

    # Growth Index (0-100): learning hours + internal mobility attempts (interpretable)
    learning = to_numeric_safe(df.get(COLS["learning"], pd.Series([np.nan] * len(df))))
    internal_apps = to_numeric_safe(df.get(COLS["internal_apps"], pd.Series([np.nan] * len(df))))

    # learning: 0-20 hours => 0-100
    learning_score = (learning.clip(lower=0, upper=20) / 20.0) * 100.0
    # internal apps: 0-3 => 0-100 (more apps can be sign of mobility/exit—here we use as "movement pressure")
    mobility_pressure = (internal_apps.clip(lower=0, upper=3) / 3.0) * 100.0

    df["learning_index"] = np.round(learning_score, 1)
    df["mobility_pressure"] = np.round(mobility_pressure, 1)

    # Comp gap flag
    sal = to_numeric_safe(df.get(COLS["salary_vs_market"], pd.Series([np.nan] * len(df))))
    df["comp_gap_flag"] = np.where(sal <= -8, "Yes", "No")

    return df


def ensure_primary_risk_driver(df: pd.DataFrame) -> pd.DataFrame:
    """
    Fill primary_risk_driver when missing or Unknown using rule-based signals.
    """
    driver_col = COLS["risk_driver"]

    if driver_col not in df.columns:
        df[driver_col] = ""

    base = df[driver_col].astype(str).str.strip()
    needs_fill = base.eq("") | base.str.lower().isin(["unknown", "nan", "none"])

    burnout = to_numeric_safe(df.get("burnout_index", pd.Series([np.nan] * len(df))))
    mobility = to_numeric_safe(df.get("mobility_pressure", pd.Series([np.nan] * len(df))))
    engagement = to_numeric_safe(df.get(COLS["engagement"], pd.Series([np.nan] * len(df))))
    enps = to_numeric_safe(df.get(COLS["enps"], pd.Series([np.nan] * len(df))))
    mgr_changes = to_numeric_safe(df.get(COLS["mgr_changes"], pd.Series([np.nan] * len(df))))

    perf = df.get(COLS["perf_trend"], pd.Series([""] * len(df))).astype(str).str.lower()
    missed_promos = df.get(COLS["missed_promos"], pd.Series([""] * len(df))).astype(str).str.lower()
    comp_gap = df.get("comp_gap_flag", pd.Series([""] * len(df))).astype(str).str.lower()

    derived = np.select(
        [
            comp_gap.eq("yes"),
            burnout >= THRESHOLDS["burnout_high"],
            mobility >= THRESHOLDS["mobility_pressure_high"],
            engagement <= THRESHOLDS["engagement_low"],
            enps <= THRESHOLDS["enps_low"],
            perf.str.contains("declin|down|poor|low", regex=True),
            missed_promos.isin(["yes", "true", "1", "y"]),
            mgr_changes >= THRESHOLDS["mgr_changes_high"],
        ],
        [
            "Compensation Gap",
            "Burnout / Workload",
            "Mobility Pressure",
            "Low Engagement",
            "Low eNPS",
            "Performance Decline",
            "Missed Promotions",
            "Manager Instability",
        ],
        default="Other / Unspecified",
    )

    df.loc[needs_fill, driver_col] = derived[needs_fill]
    return df


def derive_action(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure recommended_action is populated using risk category + primary driver.
    """
    action_col = COLS["action"]
    driver_col = COLS["risk_driver"]
    cat_col = COLS["risk_cat"]

    if action_col not in df.columns:
        df[action_col] = ""

    base = df[action_col].astype(str).str.strip()
    needs_fill = base.eq("") | base.str.lower().isin(["unknown", "nan", "none"])

    risk = df.get(cat_col, pd.Series(["Unknown"] * len(df))).astype(str)
    driver = df.get(driver_col, pd.Series(["Other / Unspecified"] * len(df))).astype(str)

    def pick_action(r, d):
        if r not in ACTION_PLAYBOOK:
            r = "Medium"
        return ACTION_PLAYBOOK.get(r, {}).get(d, ACTION_PLAYBOOK[r]["Other / Unspecified"])

    df.loc[needs_fill, action_col] = [
        pick_action(r, d) for r, d in zip(risk[needs_fill], driver[needs_fill])
    ]
    return df


def top_n_risk(df: pd.DataFrame, n: int = 10) -> pd.DataFrame:
    score_col = COLS["risk_score"]
    if safe_col(df, score_col):
        tmp = df.copy()
        tmp[score_col] = to_numeric_safe(tmp[score_col])
        return tmp.sort_values(score_col, ascending=False).head(n)
    return df.head(n)


def kpi_card(label: str, value: str, help_text: str = ""):
    st.metric(label, value, help=help_text if help_text else None)


# ----------------------------
# Load & prepare data
# ----------------------------
header_left, header_right = st.columns([1, 5])
with header_left:
    if os.path.exists(LOGO_PATH):
        st.image(LOGO_PATH, width=120)
    else:
        st.caption("Logo not found.")
with header_right:
    st.title("Employee Retention Advisor (ERA)")
    st.caption("Executive view of retention risk, key drivers, and prioritized actions.")

with st.sidebar:
    st.header("Data")
    st.caption("Update DATA_PATH in the script. You can also paste a path here for quick testing.")
    override_path = st.text_input("Override DATA_PATH (optional)", value="")
    data_path = override_path.strip() if override_path.strip() else DATA_PATH

    st.divider()
    st.header("Filters")

try:
    df = load_data(data_path)
except Exception as e:
    st.error(f"Failed to load data from: {data_path}\n\nError: {e}")
    st.stop()

df = normalize_categoricals(df)
df = ensure_risk_category(df)
df = compute_composites(df)
df = ensure_primary_risk_driver(df)
df = derive_action(df)

# Validate essentials
missing = [COLS["id"], COLS["dept"], COLS["role"], COLS["risk_cat"]]
missing = [c for c in missing if c not in df.columns]
if missing:
    st.warning(f"Missing expected columns: {missing}. Dashboard will still run, but some views may be limited.")

# ----------------------------
# Sidebar filters
# ----------------------------
def uniq(col_key, fallback_label):
    col = COLS[col_key]
    if safe_col(df, col):
        vals = sorted([v for v in df[col].dropna().unique().tolist()])
        return vals
    return [fallback_label]

with st.sidebar:
    risk_vals = uniq("risk_cat", "Unknown")
    dept_vals = uniq("dept", "Unknown")
    loc_vals = uniq("loc", "Unknown")
    role_vals = uniq("role", "Unknown")

    selected_risk = st.multiselect("Risk Category", options=risk_vals, default=risk_vals)
    selected_dept = st.multiselect("Department", options=dept_vals, default=dept_vals)
    selected_loc = st.multiselect("Location", options=loc_vals, default=loc_vals)
    selected_role = st.multiselect("Role", options=role_vals, default=role_vals)

    search = st.text_input("Search (ID / Role / Dept / Location)", value="").strip()

# Apply filters
fdf = df.copy()
if safe_col(fdf, COLS["risk_cat"]):
    fdf = fdf[fdf[COLS["risk_cat"]].isin(selected_risk)]
if safe_col(fdf, COLS["dept"]):
    fdf = fdf[fdf[COLS["dept"]].isin(selected_dept)]
if safe_col(fdf, COLS["loc"]):
    fdf = fdf[fdf[COLS["loc"]].isin(selected_loc)]
if safe_col(fdf, COLS["role"]):
    fdf = fdf[fdf[COLS["role"]].isin(selected_role)]

if search:
    hay = (
        fdf.get(COLS["id"], "").astype(str)
        + " | " + fdf.get(COLS["role"], "").astype(str)
        + " | " + fdf.get(COLS["dept"], "").astype(str)
        + " | " + fdf.get(COLS["loc"], "").astype(str)
    ).str.lower()
    fdf = fdf[hay.str.contains(re.escape(search.lower()), na=False)]

# ----------------------------
# KPI Row
# ----------------------------
k1, k2, k3, k4, k5 = st.columns(5)

total = len(fdf)
low = int((fdf[COLS["risk_cat"]] == "Low").sum()) if safe_col(fdf, COLS["risk_cat"]) else 0
med = int((fdf[COLS["risk_cat"]] == "Medium").sum()) if safe_col(fdf, COLS["risk_cat"]) else 0
high = int((fdf[COLS["risk_cat"]] == "High").sum()) if safe_col(fdf, COLS["risk_cat"]) else 0

avg_risk = float(np.nanmean(to_numeric_safe(fdf[COLS["risk_score"]])) if safe_col(fdf, COLS["risk_score"]) else np.nan)
avg_burnout = float(np.nanmean(to_numeric_safe(fdf["burnout_index"])) if "burnout_index" in fdf.columns else np.nan)

with k1:
    kpi_card("Employees", f"{total}", "Filtered population")
with k2:
    kpi_card("High Risk", f"{high}", "Risk category = High")
with k3:
    kpi_card("Concerning", f"{med}", "Risk category = Medium")
with k4:
    kpi_card("Low Risk", f"{low}", "Risk category = Low")
with k5:
    kpi_card("Avg Risk Score", f"{avg_risk:.1f}" if not math.isnan(avg_risk) else "—", "Average flight risk score")

st.caption(
    f"Avg Burnout Index (derived): {avg_burnout:.1f}"
    if not math.isnan(avg_burnout)
    else "Avg Burnout Index (derived): —"
)

with st.expander("Definitions (KPIs and Charts)"):
    st.markdown(
        "- Employees: filtered headcount in the current view.\n"
        "- High/Concerning/Low Risk: employee counts by risk_category.\n"
        "- Avg Risk Score: mean of flight_risk_score (0-100).\n"
        "- Avg Burnout Index: composite of overtime, PTO utilization (inverse), after-hours, and on-call burden (0-100).\n"
        "- Risk Distribution: count of employees by risk_category.\n"
        "- Risk Heatmap: average flight_risk_score by department and location.\n"
        "- Top Risk Drivers: most common primary_risk_driver (filled from rule-based signals if missing).\n"
        "- Risk vs Burnout: relationship between burnout_index and flight_risk_score.\n"
        "- Employee Drill-Down: individual profile with risk metrics and recommended action.\n"
        "- Indices: burnout_index, learning_index, and mobility_pressure (0-100, derived).\n"
        "- Action Playbook: recommended_action derived from risk_category + primary_risk_driver.\n"
    )

st.divider()

# ----------------------------
# Row 1: Risk Distribution + Heatmap
# ----------------------------
c1, c2 = st.columns([1, 1])

with c1:
    st.subheader("Risk Distribution")
    st.caption("Counts of employees by risk category (Low / Medium / High).")
    if safe_col(fdf, COLS["risk_cat"]):
        risk_counts = (
            fdf[COLS["risk_cat"]]
            .value_counts()
            .reindex(RISK_ORDER, fill_value=0)
            .reset_index()
        )
        risk_counts.columns = ["risk_category", "count"]
        fig = px.bar(risk_counts, x="risk_category", y="count")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("risk_category column not found.")

with c2:
    st.subheader("Risk Heatmap (Department × Location)")
    st.caption("Average flight risk score by department and location.")
    if safe_col(fdf, COLS["dept"]) and safe_col(fdf, COLS["loc"]) and safe_col(fdf, COLS["risk_score"]):
        tmp = fdf.copy()
        tmp[COLS["risk_score"]] = to_numeric_safe(tmp[COLS["risk_score"]])
        pivot = tmp.pivot_table(
            index=COLS["dept"],
            columns=COLS["loc"],
            values=COLS["risk_score"],
            aggfunc="mean",
        )
        fig = px.imshow(pivot, aspect="auto")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Need department, location, and flight_risk_score columns for heatmap.")

st.divider()

# ----------------------------
# Row 2: Drivers + Scatter
# ----------------------------
c3, c4 = st.columns([1, 1])

with c3:
    st.subheader("Top Risk Drivers")
    st.caption("Most frequent primary risk drivers in the filtered population.")
    if safe_col(fdf, COLS["risk_driver"]):
        drivers = (
            fdf[COLS["risk_driver"]]
            .fillna("Unknown")
            .value_counts()
            .reset_index()
        )
        drivers.columns = ["driver", "count"]
        fig = px.bar(drivers.head(10), x="driver", y="count")
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("primary_risk_driver column not found.")

with c4:
    st.subheader("Risk vs Burnout (Derived)")
    st.caption("Burnout index vs flight risk score. Use hover to inspect employees.")
    if safe_col(fdf, COLS["risk_score"]) and "burnout_index" in fdf.columns:
        tmp = fdf.copy()
        tmp[COLS["risk_score"]] = to_numeric_safe(tmp[COLS["risk_score"]])
        tmp["burnout_index"] = to_numeric_safe(tmp["burnout_index"])
        hover_cols = [c for c in [COLS["id"], COLS["role"], COLS["dept"], COLS["risk_cat"]] if c in tmp.columns]
        fig = px.scatter(
            tmp,
            x="burnout_index",
            y=COLS["risk_score"],
            hover_data=hover_cols,
        )
        st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Need flight_risk_score and derived burnout_index.")

st.divider()

# ----------------------------
# Row 3: Employee Drill-Down
# ----------------------------
st.subheader("Employee Drill-Down")
st.caption("Select an employee to review risk context and recommended action.")

left, right = st.columns([1, 2])

with left:
    if safe_col(fdf, COLS["id"]):
        emp_ids = fdf[COLS["id"]].astype(str).tolist()
        selected_emp = st.selectbox("Select Employee", options=emp_ids)
    else:
        selected_emp = None
        st.info("employee_id column not found; showing table only.")

    st.caption("Tip: use filters in the sidebar to narrow the population first.")

with right:
    if selected_emp and safe_col(fdf, COLS["id"]):
        row = fdf[fdf[COLS["id"]].astype(str) == str(selected_emp)].iloc[0]

        r1, r2, r3, r4 = st.columns(4)
        with r1:
            st.metric("Risk Score", f"{row.get(COLS['risk_score'], '—')}")
        with r2:
            st.metric("Risk Category", f"{row.get(COLS['risk_cat'], '—')}")
        with r3:
            st.metric("Burnout Index", f"{row.get('burnout_index', '—')}")
        with r4:
            st.metric("Comp Gap Flag", f"{row.get('comp_gap_flag', '—')}")

        st.write("**Primary Risk Driver**:", row.get(COLS["risk_driver"], "—"))
        st.write("**Recommended Action**:", row.get(COLS["action"], "—"))

        st.markdown("#### Action Plan")
        st.caption("Use these next steps to create a manager follow-up plan.")
        action_text = row.get(COLS["action"], "")
        if action_text and str(action_text).strip():
            st.checkbox("Schedule stay interview / 1:1", key=f"act_1_{selected_emp}")
            st.checkbox("Document agreed actions and owner", key=f"act_2_{selected_emp}")
            st.checkbox("Set a 30-day follow-up", key=f"act_3_{selected_emp}")
            st.write(f"**Suggested action:** {action_text}")
        else:
            st.info("No recommended action available for this employee.")

        # Profile view
        profile_cols = [
            COLS["role"], COLS["dept"], COLS["loc"],
            COLS["tenure"], COLS["time_in_role"],
            COLS["promotions"], COLS["missed_promos"],
            COLS["salary_vs_market"], COLS["mgr_changes"],
            COLS["overtime"], COLS["after_hours"], COLS["pto"], COLS["on_call"],
            COLS["engagement"], COLS["enps"], COLS["one_on_one"],
            COLS["learning"], COLS["internal_apps"],
            COLS["perf_trend"], COLS["peer_feedback"], COLS["sentiment"],
        ]
        profile_cols = [c for c in profile_cols if c in fdf.columns]

        profile = pd.DataFrame({
            "Metric": profile_cols,
            "Value": [row.get(c, np.nan) for c in profile_cols]
        })

        st.markdown("#### Employee Profile")
        st.dataframe(profile, use_container_width=True, hide_index=True)

        # Mini radar-like bar chart (simple)
        st.markdown("#### Indices")
        st.caption("Derived 0-100 indicators: burnout, learning engagement, and mobility pressure.")
        idx_df = pd.DataFrame([
            {"index": "Burnout", "value": row.get("burnout_index", np.nan)},
            {"index": "Learning", "value": row.get("learning_index", np.nan)},
            {"index": "Mobility Pressure", "value": row.get("mobility_pressure", np.nan)},
        ])
        idx_df["value"] = to_numeric_safe(idx_df["value"])
        fig = px.bar(idx_df, x="index", y="value")
        st.plotly_chart(fig, use_container_width=True)

# ----------------------------
# Table + Export
# ----------------------------
st.subheader("Employee Table (Filtered)")
st.caption("Detailed records for the filtered population.")

# Choose a clean set of table columns
table_cols = [
    COLS["id"], COLS["dept"], COLS["role"], COLS["loc"],
    COLS["risk_cat"], COLS["risk_score"], COLS["risk_driver"], COLS["action"],
    "burnout_index", "comp_gap_flag",
    COLS["engagement"], COLS["enps"], COLS["overtime"], COLS["pto"],
]
table_cols = [c for c in table_cols if c in fdf.columns]

st.dataframe(fdf[table_cols].sort_values(by=[COLS["risk_cat"], COLS["risk_score"]] if safe_col(fdf, COLS["risk_score"]) else [COLS["risk_cat"]], ascending=[True, False] if safe_col(fdf, COLS["risk_score"]) else [True]),
             use_container_width=True)

st.download_button(
    "Download filtered data as CSV",
    data=fdf.to_csv(index=False).encode("utf-8"),
    file_name="employee_retention_filtered.csv",
    mime="text/csv",
)

# ----------------------------
# Run instructions (for you)
# ----------------------------
#with st.expander("How to run"):
    #st.code(
    #    "pip install streamlit pandas plotly openpyxl\n"
   #     "streamlit run employee_retention_dashboard.py\n",
  #      language="bash",
 #   )
#
