import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import date, timedelta
import json
 
# ── Config ──────────────────────────────────────────────────────────────────
SHEET_ID = "18-q7ItMDfPkdvS7o01UzS4Xbyz6KmDDaTjcBTksoBlU"
 
NAMES = [
    "Ahmed", "Alec", "Brian", "Dave", "Farhad",
    "Kyle", "Leo", "Meng", "Peter", "Ranga", "Sesha", "Vivian"
]
 
# Generate all weekdays in June 2025
def get_june_weekdays():
    days = []
    d = date(2025, 6, 2)  # First Monday of June 2025
    while d.month == 6:
        if d.weekday() < 5:  # Mon-Fri
            days.append(d.strftime("%a %b %d"))
        d += timedelta(days=1)
    return days
 
JUNE_DAYS = get_june_weekdays()
 
# ── Google Sheets connection ─────────────────────────────────────────────────
def get_sheet():
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)
 
def read_sheet(tab):
    sh = get_sheet()
    ws = sh.worksheet(tab)
    data = ws.get_all_records()
    return pd.DataFrame(data) if data else pd.DataFrame()
 
def append_row(tab, row: list):
    sh = get_sheet()
    ws = sh.worksheet(tab)
    ws.append_row(row, value_input_option="USER_ENTERED")
 
def update_row(tab, row_index: int, row: list):
    """row_index is 1-based sheet row (header=1, data starts at 2)"""
    sh = get_sheet()
    ws = sh.worksheet(tab)
    ws.update(f"A{row_index}:{chr(64+len(row))}{row_index}", [row])
 
def delete_row(tab, row_index: int):
    sh = get_sheet()
    ws = sh.worksheet(tab)
    ws.delete_rows(row_index)
 
def ensure_headers():
    sh = get_sheet()
    headers = {
        "availability": ["Name"] + JUNE_DAYS,
        "events":       ["Submitted By", "Title", "Link", "Est. Price/Person"],
        "dining":       ["Submitted By", "Title", "Link", "Est. Price/Person"],
        "votes":        ["Name", "Event 1st", "Event 2nd", "Event 3rd",
                         "Dining 1st", "Dining 2nd", "Dining 3rd"],
    }
    for tab, hdrs in headers.items():
        ws = sh.worksheet(tab)
        existing = ws.row_values(1)
        if existing != hdrs:
            ws.clear()
            ws.append_row(hdrs)
 
# ── Streamlit UI ─────────────────────────────────────────────────────────────
st.set_page_config(page_title="Morale Event Planner", page_icon="🎉", layout="wide")
 
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500;600&display=swap');
 
html, body, [class*="css"] {
    font-family: 'DM Sans', sans-serif;
}
h1, h2, h3 {
    font-family: 'DM Serif Display', serif;
}
.stTabs [data-baseweb="tab"] {
    font-size: 1rem;
    font-weight: 600;
    padding: 0.6rem 1.4rem;
}
.stTabs [aria-selected="true"] {
    color: #e85d26;
    border-bottom: 3px solid #e85d26;
}
.block-container { padding-top: 2rem; }
div[data-testid="stCheckbox"] label { font-size: 0.85rem; }
.section-label {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.1em;
    color: #888;
    margin-bottom: 0.25rem;
}
</style>
""", unsafe_allow_html=True)
 
st.title("🎉 Morale Event Planner")
st.caption("Coordinate availability, propose ideas, and vote — all in one place.")
 
# ── Name selector (persisted in session) ────────────────────────────────────
with st.sidebar:
    st.markdown("### 👋 Who are you?")
    user = st.selectbox("Select your name", ["— select —"] + NAMES, key="user_name")
    if user != "— select —":
        st.success(f"Hi, **{user}**!")
    else:
        st.warning("Please select your name to participate.")
    st.divider()
    st.caption("Morale Event Planner · June 2025")
 
identified = user != "— select —"
 
# ── Tabs ────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["📅 Availability", "🎯 Events", "🍽️ Dining", "🗳️ Votes"])
 
# ══════════════════════════════════════════════════════════════════════════════
# TAB 1 · AVAILABILITY
# ══════════════════════════════════════════════════════════════════════════════
with tab1:
    import streamlit.components.v1 as components
 
    st.subheader("When are you available in June?")
    st.caption("Click a date to cycle: **green** = available · **red** = not available · **grey** = no response")
 
    try:
        avail_df = read_sheet("availability")
    except Exception as e:
        st.error(f"Could not load availability data: {e}")
        avail_df = pd.DataFrame()
 
    # ── Team heatmap counts ──────────────────────────────────────────────────
    day_counts = {}
    total_users = len(avail_df) if not avail_df.empty else 0
    for day in JUNE_DAYS:
        if not avail_df.empty and day in avail_df.columns:
            day_counts[day] = avail_df[day].apply(lambda v: 1 if str(v).strip() == "✓" else 0).sum()
        else:
            day_counts[day] = 0
 
    # ── Load user's existing selections ─────────────────────────────────────
    existing_row = None
    existing_idx = None
    if not avail_df.empty and "Name" in avail_df.columns:
        match = avail_df[avail_df["Name"] == user]
        if not match.empty:
            existing_row = match.iloc[0]
            existing_idx = match.index[0] + 2
 
    # Build saved state per day
    saved_state = {}
    for day in JUNE_DAYS:
        val = ""
        if existing_row is not None and day in existing_row:
            v = str(existing_row[day]).strip()
            if v in ("✓", "✗"):
                val = v
        saved_state[day] = val
 
    # ── Build full June calendar grid (Sun offset) ───────────────────────────
    # June 2025 starts on Sunday. Grid = 7 cols, Sun–Sat
    # We only show Mon–Fri (weekdays), weekends are greyed out placeholder cells
    import calendar as cal_mod
    june_days_set = set(JUNE_DAYS)
 
    # Build a list of all days in a Mon-Sun grid for June 2025
    # June 1 2025 = Sunday, so Mon offset = 6 (we skip Sun col)
    # Use a 7-col grid: Mon Tue Wed Thu Fri Sat Sun
    all_june = []
    d = date(2025, 6, 1)
    while d.month == 6:
        all_june.append(d)
        d += timedelta(days=1)
 
    # Grid offset: Monday=0. June 1 is Sunday = weekday 6
    start_offset = date(2025, 6, 1).weekday()  # 6 = Sunday
 
    # Build grid cells: None = empty padding, date obj = actual day
    grid = [None] * start_offset + all_june
    while len(grid) % 7 != 0:
        grid.append(None)
 
    # ── Encode data to pass into HTML ────────────────────────────────────────
    june_days_json = json.dumps(JUNE_DAYS)
    saved_state_json = json.dumps(saved_state)
    day_counts_json = json.dumps({k: int(v) for k, v in day_counts.items()})
 
    # Build grid_data for JS: list of {day_num, day_str, is_weekday}
    grid_data = []
    for cell in grid:
        if cell is None:
            grid_data.append({"day_num": None, "day_str": None, "is_weekday": False})
        else:
            day_str = cell.strftime("%a %b %d")
            is_weekday = cell.weekday() < 5
            grid_data.append({"day_num": cell.day, "day_str": day_str if is_weekday else None, "is_weekday": is_weekday})
 
    grid_data_json = json.dumps(grid_data)
    identified_js = "true" if identified else "false"
    user_js = json.dumps(user)
    total_users_js = int(total_users)
 
    calendar_html = f"""
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;600&family=Roboto:wght@300;400;500&display=swap');
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  body {{ font-family: 'Roboto', sans-serif; background: transparent; padding: 0; }}
 
  .cal-wrap {{ max-width: 860px; background: #fff; border-radius: 16px;
               border: 1px solid #e0e0e0; overflow: hidden;
               box-shadow: 0 2px 12px rgba(0,0,0,0.08); }}
 
  .cal-header {{ background: #fff; padding: 20px 24px 12px;
                 display: flex; align-items: center; gap: 16px; }}
  .cal-title {{ font-family: 'Google Sans', sans-serif; font-size: 22px;
                font-weight: 400; color: #3c4043; }}
  .cal-legend {{ display: flex; gap: 16px; margin-left: auto; align-items: center; }}
  .leg-item {{ display: flex; align-items: center; gap: 6px; font-size: 12px; color: #5f6368; }}
  .leg-dot {{ width: 12px; height: 12px; border-radius: 50%; }}
  .leg-green {{ background: #34a853; }}
  .leg-red   {{ background: #ea4335; }}
  .leg-grey  {{ background: #e0e0e0; border: 1px solid #ccc; }}
 
  .dow-row {{ display: grid; grid-template-columns: repeat(7, 1fr);
              border-bottom: 1px solid #e0e0e0; background: #fff; }}
  .dow-cell {{ text-align: center; padding: 8px 0; font-size: 11px; font-weight: 500;
               text-transform: uppercase; letter-spacing: 0.08em; color: #70757a; }}
 
  .cal-grid {{ display: grid; grid-template-columns: repeat(7, 1fr); }}
 
  .cal-cell {{ min-height: 90px; border-right: 1px solid #e8eaed;
               border-bottom: 1px solid #e8eaed; padding: 8px 6px;
               position: relative; background: #fff; transition: background 0.15s; }}
  .cal-cell:nth-child(7n) {{ border-right: none; }}
  .cal-cell.empty {{ background: #fafafa; }}
  .cal-cell.weekend {{ background: #fafafa; cursor: default; }}
  .cal-cell.weekend .day-num {{ color: #bbb; }}
 
  .cal-cell.available   {{ background: #e6f4ea; cursor: pointer; }}
  .cal-cell.unavailable {{ background: #fce8e6; cursor: pointer; }}
  .cal-cell.workday     {{ cursor: pointer; }}
  .cal-cell.workday:hover {{ background: #f1f3f4; }}
  .cal-cell.available:hover   {{ background: #ceead6; }}
  .cal-cell.unavailable:hover {{ background: #f5c6c3; }}
 
  .day-num {{ font-family: 'Google Sans', sans-serif; font-size: 13px;
              font-weight: 500; color: #3c4043; display: inline-flex;
              align-items: center; justify-content: center;
              width: 28px; height: 28px; border-radius: 50%; }}
  .cal-cell.available .day-num   {{ background: #34a853; color: #fff; }}
  .cal-cell.unavailable .day-num {{ background: #ea4335; color: #fff; }}
 
  .status-badge {{ font-size: 10px; font-weight: 500; margin-top: 4px;
                   padding: 2px 6px; border-radius: 10px; display: inline-block; }}
  .badge-avail   {{ background: #34a85322; color: #1e7e34; }}
  .badge-unavail {{ background: #ea433522; color: #c62828; }}
 
  .team-bar {{ margin-top: 6px; height: 4px; border-radius: 2px; background: #e0e0e0; overflow: hidden; }}
  .team-fill {{ height: 100%; border-radius: 2px; background: #4285f4; transition: width 0.3s; }}
  .team-count {{ font-size: 9px; color: #70757a; margin-top: 2px; }}
 
  .save-row {{ padding: 16px 24px; border-top: 1px solid #e0e0e0;
               display: flex; align-items: center; gap: 16px; background: #fff; }}
  .save-btn {{ background: #1a73e8; color: white; border: none; border-radius: 8px;
               padding: 10px 28px; font-size: 14px; font-weight: 500;
               cursor: pointer; font-family: 'Google Sans', sans-serif;
               transition: background 0.2s; }}
  .save-btn:hover {{ background: #1557b0; }}
  .save-btn:disabled {{ background: #ccc; cursor: default; }}
  .save-hint {{ font-size: 12px; color: #70757a; }}
  .save-msg {{ font-size: 13px; font-weight: 500; }}
  .save-msg.ok  {{ color: #34a853; }}
  .save-msg.err {{ color: #ea4335; }}
 
  .not-identified {{ padding: 20px 24px; color: #70757a; font-size: 14px; }}
</style>
</head>
<body>
 
<div class="cal-wrap">
  <div class="cal-header">
    <span class="cal-title">📅 June 2025</span>
    <div class="cal-legend">
      <div class="leg-item"><div class="leg-dot leg-green"></div> Available</div>
      <div class="leg-item"><div class="leg-dot leg-red"></div> Not available</div>
      <div class="leg-item"><div class="leg-dot leg-grey"></div> No response</div>
    </div>
  </div>
 
  <div class="dow-row">
    <div class="dow-cell">Mon</div>
    <div class="dow-cell">Tue</div>
    <div class="dow-cell">Wed</div>
    <div class="dow-cell">Thu</div>
    <div class="dow-cell">Fri</div>
    <div class="dow-cell" style="color:#bbb">Sat</div>
    <div class="dow-cell" style="color:#bbb">Sun</div>
  </div>
 
  <div class="cal-grid" id="calGrid"></div>
 
  <div class="save-row" id="saveRow">
    <button class="save-btn" id="saveBtn" onclick="saveData()">💾 Save Availability</button>
    <span class="save-hint">Click once = available · Click again = not available · Click again = clear</span>
    <span class="save-msg" id="saveMsg"></span>
  </div>
</div>
 
<script>
const IDENTIFIED = {identified_js};
const USER = {user_js};
const GRID_DATA = {grid_data_json};
const DAY_COUNTS = {day_counts_json};
const TOTAL_USERS = {total_users_js};
const JUNE_DAYS = {june_days_json};
 
let state = {saved_state_json};
 
function cycle(current) {{
  if (current === "") return "✓";
  if (current === "✓") return "✗";
  return "";
}}
 
function cellClass(day_str, is_weekday) {{
  if (!is_weekday) return "cal-cell weekend";
  if (!IDENTIFIED) return "cal-cell workday";
  const s = state[day_str] || "";
  if (s === "✓") return "cal-cell available";
  if (s === "✗") return "cal-cell unavailable";
  return "cal-cell workday";
}}
 
function renderGrid() {{
  const grid = document.getElementById("calGrid");
  grid.innerHTML = "";
 
  GRID_DATA.forEach(cell => {{
    const div = document.createElement("div");
 
    if (cell.day_num === null) {{
      div.className = "cal-cell empty";
      grid.appendChild(div);
      return;
    }}
 
    if (!cell.is_weekday) {{
      div.className = "cal-cell weekend";
      div.innerHTML = `<span class="day-num">${{cell.day_num}}</span>`;
      grid.appendChild(div);
      return;
    }}
 
    const day_str = cell.day_str;
    const s = state[day_str] || "";
    div.className = cellClass(day_str, true);
 
    if (IDENTIFIED) {{
      div.onclick = () => {{
        state[day_str] = cycle(state[day_str] || "");
        renderGrid();
      }};
    }}
 
    const cnt = DAY_COUNTS[day_str] || 0;
    const pct = TOTAL_USERS > 0 ? Math.round((cnt / TOTAL_USERS) * 100) : 0;
 
    let badge = "";
    if (s === "✓") badge = `<div class="status-badge badge-avail">Available</div>`;
    if (s === "✗") badge = `<div class="status-badge badge-unavail">Not available</div>`;
 
    let teamBar = "";
    if (TOTAL_USERS > 0) {{
      teamBar = `
        <div class="team-bar"><div class="team-fill" style="width:${{pct}}%"></div></div>
        <div class="team-count">${{cnt}}/${{TOTAL_USERS}} available</div>`;
    }}
 
    div.innerHTML = `
      <span class="day-num">${{cell.day_num}}</span>
      ${{badge}}
      ${{teamBar}}
    `;
 
    grid.appendChild(div);
  }});
}}
 
function saveData() {{
  if (!IDENTIFIED) return;
  const btn = document.getElementById("saveBtn");
  const msg = document.getElementById("saveMsg");
  btn.disabled = true;
  btn.textContent = "Saving...";
  msg.textContent = "";
 
  // Encode state as compact string: days marked ✓ or ✗ joined by pipe
  const available = JUNE_DAYS.filter(d => state[d] === "✓").map(d => encodeURIComponent(d)).join("|");
  const unavailable = JUNE_DAYS.filter(d => state[d] === "✗").map(d => encodeURIComponent(d)).join("|");
 
  // Write to parent URL query params so Streamlit can read them
  const url = new URL(window.parent.location.href);
  url.searchParams.set("cal_avail", available);
  url.searchParams.set("cal_unavail", unavailable);
  url.searchParams.set("cal_user", USER);
  url.searchParams.set("cal_save", "1");
  window.parent.history.replaceState({{}}, "", url.toString());
 
  setTimeout(() => {{
    btn.disabled = false;
    btn.textContent = "💾 Save Availability";
    msg.className = "save-msg ok";
    msg.textContent = "✅ Selections recorded — click 'Confirm & Save' above!";
  }}, 400);
}}
 
if (!IDENTIFIED) {{
  document.getElementById("saveRow").innerHTML =
    '<div class="not-identified">👈 Select your name in the sidebar to mark your availability.</div>';
}}
 
renderGrid();
</script>
</body>
</html>
"""
 
    # Render the calendar component
    components.html(calendar_html, height=620, scrolling=False)
 
    # ── Read state from query params set by the calendar JS ─────────────────
    qp = st.query_params
    cal_save_triggered = qp.get("cal_save") == "1" and qp.get("cal_user") == user
 
    # Build state from query params if available, otherwise fall back to sheet data
    if cal_save_triggered:
        avail_raw = qp.get("cal_avail", "")
        unavail_raw = qp.get("cal_unavail", "")
        avail_days   = set(avail_raw.split("|")) if avail_raw else set()
        unavail_days = set(unavail_raw.split("|")) if unavail_raw else set()
        current_state = {}
        for d in JUNE_DAYS:
            if d in avail_days:     current_state[d] = "✓"
            elif d in unavail_days: current_state[d] = "✗"
            else:                   current_state[d] = saved_state.get(d, "")
    else:
        current_state = saved_state
 
    if identified:
        st.markdown("")
        if st.button("💾 Confirm & Save to Google Sheets", type="primary"):
            row = [user] + [current_state.get(d, "") for d in JUNE_DAYS]
            try:
                if existing_idx:
                    update_row("availability", existing_idx, row)
                else:
                    append_row("availability", row)
                # Clear query params after saving
                st.query_params.clear()
                st.success("✅ Availability saved to Google Sheets!")
                st.rerun()
            except Exception as e:
                st.error(f"Error saving: {e}")
        if cal_save_triggered:
            st.info("📋 Calendar selections loaded — click **Confirm & Save** to write to Google Sheets.")
        else:
            st.caption("👆 Click dates in the calendar above, then click this button to save.")
 
    # ── Team overview heatmap below ──────────────────────────────────────────
    if not avail_df.empty:
        with st.expander("👥 View full team availability table"):
            display_df = avail_df.set_index("Name") if "Name" in avail_df.columns else avail_df
            def fmt(val):
                v = str(val).strip()
                if v == "✓": return "✅"
                if v == "✗": return "❌"
                return ""
            st.dataframe(display_df.applymap(fmt), use_container_width=True)
 
# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 · EVENTS
# ══════════════════════════════════════════════════════════════════════════════
def get_col(row, *candidates):
    """Try multiple column name variants, return first match or empty string."""
    for c in candidates:
        if c in row and str(row[c]).strip() not in ("", "nan"):
            return str(row[c]).strip()
    return ""
 
def ideas_tab(tab, sheet_tab, label):
    with tab:
        st.subheader(f"{label} Ideas")
 
        try:
            df = read_sheet(sheet_tab)
        except Exception as e:
            st.error(f"Could not load data: {e}")
            df = pd.DataFrame()
 
        # Normalise column names — strip whitespace, case-insensitive lookup
        if not df.empty:
            df.columns = [c.strip() for c in df.columns]
 
        # Side-by-side layout: list on left, form on right
        col_list, col_form = st.columns([3, 2], gap="large")
 
        with col_list:
            st.markdown(f"#### 📋 Current {label} Suggestions")
            if df.empty or len(df) == 0:
                st.info(f"No {label.lower()} ideas yet — be the first to add one!")
            else:
                for i, row in df.iterrows():
                    title_val = get_col(row, "Title", "title", "TITLE")
                    by_val    = get_col(row, "Submitted By", "submitted by", "submitted_by", "Name")
                    link_val  = get_col(row, "Link", "link", "LINK", "Website", "URL")
                    price_val = get_col(row, "Est. Price/Person", "Est. Price", "Price", "price", "est. price/person")
 
                    with st.container(border=True):
                        # Title + submitter
                        title_display = title_val if title_val else "Untitled"
                        by_display    = by_val    if by_val    else "Unknown"
                        st.markdown(f"**{title_display}**")
                        st.caption(f"Suggested by {by_display}")
                        # Link + price on same row
                        meta_cols = st.columns([2, 1])
                        if link_val and link_val.startswith("http"):
                            meta_cols[0].markdown(f"[🔗 More Info]({link_val})")
                        if price_val:
                            meta_cols[1].markdown(f"💰 **${price_val}/pp**")
 
        with col_form:
            st.markdown(f"#### ➕ Add a {label} Idea")
            if not identified:
                st.info("Select your name in the sidebar to submit.")
            else:
                with st.form(key=f"form_{sheet_tab}", clear_on_submit=True):
                    title = st.text_input("Title *", placeholder="e.g. Bowling Night")
                    link  = st.text_input("Link (optional)", placeholder="https://...")
                    price = st.text_input("Est. Price/Person (optional)", placeholder="e.g. 25")
                    submitted = st.form_submit_button("Submit Idea", type="primary", use_container_width=True)
                    if submitted:
                        if not title.strip():
                            st.warning("Please enter a title.")
                        else:
                            try:
                                append_row(sheet_tab, [user, title.strip(), link.strip(), price.strip()])
                                st.success(f"✅ {label} idea submitted!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error saving: {e}")
 
ideas_tab(tab2, "events", "Event")
ideas_tab(tab3, "dining", "Dining")
 
# ══════════════════════════════════════════════════════════════════════════════
# TAB 4 · VOTES
# ══════════════════════════════════════════════════════════════════════════════
with tab4:
    st.subheader("Cast Your Votes")
    st.caption("Rank your top 3 picks for events and dining. You can update anytime.")
 
    try:
        events_df = read_sheet("events")
        dining_df = read_sheet("dining")
        votes_df  = read_sheet("votes")
    except Exception as e:
        st.error(f"Could not load voting data: {e}")
        events_df = dining_df = votes_df = pd.DataFrame()
 
    # Normalise column names
    for _df in [events_df, dining_df, votes_df]:
        if not _df.empty:
            _df.columns = [c.strip() for c in _df.columns]
 
    def get_titles(df):
        for col in ["Title", "title", "TITLE"]:
            if not df.empty and col in df.columns:
                return [str(v).strip() for v in df[col] if str(v).strip() not in ("", "nan")]
        return []
 
    event_titles  = get_titles(events_df)
    dining_titles = get_titles(dining_df)
 
    # Tally votes
    def tally(df, col_prefix, titles):
        counts = {t: 0 for t in titles}
        weights = {"1st": 3, "2nd": 2, "3rd": 1}
        if df.empty:
            return counts
        for _, row in df.iterrows():
            for rank, w in weights.items():
                pick = row.get(f"{col_prefix} {rank}", "")
                if pick in counts:
                    counts[pick] += w
        return counts
 
    c1, c2 = st.columns(2)
 
    with c1:
        st.markdown("#### 🎯 Event Vote Tally")
        if event_titles:
            tally_e = tally(votes_df, "Event", event_titles)
            tally_df_e = pd.DataFrame(list(tally_e.items()), columns=["Event", "Score"]).sort_values("Score", ascending=False)
            st.dataframe(tally_df_e, use_container_width=True, hide_index=True)
        else:
            st.info("No events proposed yet.")
 
    with c2:
        st.markdown("#### 🍽️ Dining Vote Tally")
        if dining_titles:
            tally_d = tally(votes_df, "Dining", dining_titles)
            tally_df_d = pd.DataFrame(list(tally_d.items()), columns=["Dining", "Score"]).sort_values("Score", ascending=False)
            st.dataframe(tally_df_d, use_container_width=True, hide_index=True)
        else:
            st.info("No dining ideas proposed yet.")
 
    st.divider()
 
    if not identified:
        st.info("Select your name in the sidebar to vote.")
    else:
        # Pre-fill existing votes
        existing_vote = None
        existing_vote_idx = None
        if not votes_df.empty and "Name" in votes_df.columns:
            match = votes_df[votes_df["Name"] == user]
            if not match.empty:
                existing_vote = match.iloc[0]
                existing_vote_idx = match.index[0] + 2
 
        st.markdown(f"#### {user}'s Votes")
 
        none_opt = "— no pick —"
 
        col1, col2 = st.columns(2)
 
        with col1:
            st.markdown("**🎯 Event Rankings**")
            if event_titles:
                e_opts = [none_opt] + event_titles
                e1_def = existing_vote.get("Event 1st", none_opt) if existing_vote is not None else none_opt
                e2_def = existing_vote.get("Event 2nd", none_opt) if existing_vote is not None else none_opt
                e3_def = existing_vote.get("Event 3rd", none_opt) if existing_vote is not None else none_opt
                e1 = st.selectbox("🥇 1st Choice", e_opts, index=e_opts.index(e1_def) if e1_def in e_opts else 0, key="e1")
                e2 = st.selectbox("🥈 2nd Choice", e_opts, index=e_opts.index(e2_def) if e2_def in e_opts else 0, key="e2")
                e3 = st.selectbox("🥉 3rd Choice", e_opts, index=e_opts.index(e3_def) if e3_def in e_opts else 0, key="e3")
            else:
                st.info("Add event ideas first.")
                e1 = e2 = e3 = none_opt
 
        with col2:
            st.markdown("**🍽️ Dining Rankings**")
            if dining_titles:
                d_opts = [none_opt] + dining_titles
                d1_def = existing_vote.get("Dining 1st", none_opt) if existing_vote is not None else none_opt
                d2_def = existing_vote.get("Dining 2nd", none_opt) if existing_vote is not None else none_opt
                d3_def = existing_vote.get("Dining 3rd", none_opt) if existing_vote is not None else none_opt
                d1 = st.selectbox("🥇 1st Choice", d_opts, index=d_opts.index(d1_def) if d1_def in d_opts else 0, key="d1")
                d2 = st.selectbox("🥈 2nd Choice", d_opts, index=d_opts.index(d2_def) if d2_def in d_opts else 0, key="d2")
                d3 = st.selectbox("🥉 3rd Choice", d_opts, index=d_opts.index(d3_def) if d3_def in d_opts else 0, key="d3")
            else:
                st.info("Add dining ideas first.")
                d1 = d2 = d3 = none_opt
 
        if st.button("💾 Save Votes", type="primary"):
            def clean(v): return "" if v == none_opt else v
            row = [user, clean(e1), clean(e2), clean(e3), clean(d1), clean(d2), clean(d3)]
            try:
                if existing_vote_idx:
                    update_row("votes", existing_vote_idx, row)
                else:
                    append_row("votes", row)
                st.success("Votes saved!")
                st.rerun()
            except Exception as e:
                st.error(f"Error saving votes: {e}")
