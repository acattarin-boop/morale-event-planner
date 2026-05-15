import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import date, timedelta
import json
 
# ── Config ───────────────────────────────────────────────────────────────────
SHEET_ID = "18-q7ItMDfPkdvS7o01UzS4Xbyz6KmDDaTjcBTksoBlU"
 
BASE_NAMES = [
    "Ahmed", "Alec", "Brian", "Dave", "Farhad",
    "Kyle", "Leo", "Meng", "Peter", "Ranga", "Sesha", "Vivian"
]
 
def get_event_weekdays():
    """Return all weekdays in May and June 2026."""
    days = []
    for month in [5, 6]:
        d = date(2026, month, 1)
        while d.month == month:
            if d.weekday() < 5:
                days.append(d.strftime("%a %b %d"))
            d += timedelta(days=1)
    return days
 
ALL_DAYS = get_event_weekdays()
# Keep JUNE_DAYS as alias so rest of code still works if referenced
JUNE_DAYS = ALL_DAYS
 
# ── Google Sheets ─────────────────────────────────────────────────────────────
def get_sheet():
    creds_dict = json.loads(st.secrets["gcp_service_account"])
    scopes = [
        "https://www.googleapis.com/auth/spreadsheets",
        "https://www.googleapis.com/auth/drive",
    ]
    creds = Credentials.from_service_account_info(creds_dict, scopes=scopes)
    client = gspread.authorize(creds)
    return client.open_by_key(SHEET_ID)
 
@st.cache_data(ttl=300)
def read_sheet(tab):
    sh = get_sheet()
    ws = sh.worksheet(tab)
    all_values = ws.get_all_values()
    if not all_values or len(all_values) < 2:
        return pd.DataFrame()
    headers = [h.strip() for h in all_values[0]]
    rows = all_values[1:]
    padded = [r + [""] * (len(headers) - len(r)) for r in rows]
    return pd.DataFrame(padded, columns=headers)
 
@st.cache_data(ttl=300)
def read_all_sheets():
    """Load all tabs in a single connection — minimises API calls."""
    sh = get_sheet()
    result = {}
    for tab in ["availability", "events", "dining", "votes", "names"]:
        try:
            ws = sh.worksheet(tab)
            all_values = ws.get_all_values()
            if all_values and len(all_values) >= 2:
                headers = [h.strip() for h in all_values[0]]
                rows = all_values[1:]
                padded = [r + [""] * (len(headers) - len(r)) for r in rows]
                result[tab] = pd.DataFrame(padded, columns=headers)
            elif all_values and len(all_values) == 1:
                headers = [h.strip() for h in all_values[0]]
                result[tab] = pd.DataFrame(columns=headers)
            else:
                result[tab] = pd.DataFrame()
        except Exception:
            result[tab] = pd.DataFrame()
    return result
 
def get_data(tab):
    """Get sheet data from session state cache — no extra API calls."""
    return st.session_state.get("sheets_data", {}).get(tab, pd.DataFrame())
 
def refresh_data():
    """Force a fresh load from Google Sheets and cache in session state."""
    read_all_sheets.clear()
    st.session_state["sheets_data"] = read_all_sheets()
 
def init_availability_headers():
    """Ensure the availability sheet has the correct header row."""
    try:
        sh = get_sheet()
        ws = sh.worksheet("availability")
        existing = ws.row_values(1)
        expected = ["Name"] + JUNE_DAYS
        if existing != expected:
            # If sheet is empty or headers wrong, write correct headers
            if not existing:
                ws.append_row(expected)
            else:
                ws.update("A1", [expected])
    except Exception:
        pass  # Don't crash the app if this fails
 
def write_names_to_sheet(names: list):
    sh = get_sheet()
    ws = sh.worksheet("names")
    ws.clear()
    ws.append_row(["Name"])
    if names:
        ws.append_rows([[n] for n in sorted(names)], value_input_option="USER_ENTERED")
 
def append_row(tab, row: list):
    sh = get_sheet()
    ws = sh.worksheet(tab)
    ws.append_row(row, value_input_option="USER_ENTERED")
 
def col_letter(n):
    """Convert 1-based column number to A1 letter notation (handles AA, AB, etc.)."""
    result = ""
    while n > 0:
        n, rem = divmod(n - 1, 26)
        result = chr(65 + rem) + result
    return result
 
def update_row(tab, row_index: int, row: list):
    sh = get_sheet()
    ws = sh.worksheet(tab)
    end_col = col_letter(len(row))
    ws.update(f"A{row_index}:{end_col}{row_index}", [row])
 
# ── Page config ───────────────────────────────────────────────────────────────
st.set_page_config(page_title="Morale Event Planner", page_icon="🎉", layout="wide")
 
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Serif+Display&family=DM+Sans:wght@300;400;500;600&display=swap');
html, body, [class*="css"] { font-family: 'DM Sans', sans-serif; }
h1, h2, h3 { font-family: 'DM Serif Display', serif; }
.stTabs [data-baseweb="tab"] { font-size: 1rem; font-weight: 600; padding: 0.6rem 1.4rem; }
.stTabs [aria-selected="true"] { color: #e85d26; border-bottom: 3px solid #e85d26; }
.block-container { padding-top: 2rem; }
</style>
""", unsafe_allow_html=True)
 
st.title("🎉 Morale Event Planner")
st.caption("Coordinate availability, propose ideas, and vote — all in one place.")
 
# ── Load ALL sheet data once at startup ───────────────────────────────────────
if "sheets_data" not in st.session_state:
    st.session_state["sheets_data"] = read_all_sheets()
 
# ── Names ─────────────────────────────────────────────────────────────────────
def get_extra_names():
    """Get added names from cached sheets_data. Falls back gracefully."""
    names_df = st.session_state.get("sheets_data", {}).get("names", pd.DataFrame())
    if names_df.empty:
        return []
    # Accept 'Name' header or treat first column as names list
    col = next((c for c in names_df.columns if c.strip().lower() == "name"), None)
    if not col and len(names_df.columns) > 0:
        col = names_df.columns[0]
    if not col:
        return []
    return [v.strip() for v in names_df[col] if str(v).strip() and str(v).strip().lower() != "name"]
 
# ── Load names ────────────────────────────────────────────────────────────────
extra_names = get_extra_names()
ALL_NAMES = sorted(set(BASE_NAMES) | set(extra_names))
 
# ── Sidebar ───────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown("### 👋 Who are you?")
    user = st.selectbox("Select your name", ["— select —"] + ALL_NAMES, key="user_name")
    if user != "— select —":
        st.success(f"Hi, **{user}**!")
    else:
        st.warning("Please select your name to participate.")
 
    st.divider()
    st.markdown("**Don't see your name?**")
    new_name = st.text_input("Your name", placeholder="First Last",
                             key="new_name_input", label_visibility="collapsed")
    if st.button("➕ Add Name", use_container_width=True):
        name_clean = new_name.strip().title()
        if not name_clean:
            st.warning("Please enter a name.")
        elif name_clean in ALL_NAMES:
            st.info(f"{name_clean} is already in the list.")
        else:
            updated = sorted(set(extra_names) | {name_clean})
            write_names_to_sheet(updated)
            read_all_sheets.clear()
            st.session_state["sheets_data"] = read_all_sheets()
            st.success(f"✅ Added **{name_clean}**! Select your name above.")
            st.rerun()
 
    st.divider()
    st.caption("Morale Event Planner · June 2026")
    st.caption("*To remove a name, delete it from the **names** tab in Google Sheets.*")
 
identified = user != "— select —"
 
# ── Tabs ──────────────────────────────────────────────────────────────────────
tab1, tab2, tab3, tab4 = st.tabs(["📅 Availability", "🎯 Events", "🍽️ Dining", "🗳️ Votes"])
 
# ═════════════════════════════════════════════════════════════════════════════
# TAB 1 · AVAILABILITY
# ═════════════════════════════════════════════════════════════════════════════
with tab1:
    st.subheader("When are you available?")
 
    avail_df = get_data("availability")
    today = date.today()
 
    # Normalise column names
    if not avail_df.empty:
        avail_df.columns = [c.strip() for c in avail_df.columns]
        day_lookup = {d.lower().replace(" 0", " "): d for d in ALL_DAYS}
        rename_map = {}
        for col in avail_df.columns:
            norm = col.lower().replace(" 0", " ")
            if norm in day_lookup and col != day_lookup[norm]:
                rename_map[col] = day_lookup[norm]
        if rename_map:
            avail_df = avail_df.rename(columns=rename_map)
 
    # Load user's saved state
    existing_row = None
    existing_idx = None
    if not avail_df.empty and "Name" in avail_df.columns:
        match = avail_df[avail_df["Name"] == user]
        if not match.empty:
            existing_row = match.iloc[0]
            existing_idx = int(match.index[0]) + 2
 
    saved_state = {}
    for day in ALL_DAYS:
        val = ""
        if existing_row is not None and day in existing_row:
            v = str(existing_row[day]).strip()
            if v in ("✓", "✗"):
                val = v
        saved_state[day] = val
 
    # Per-day name lists
    day_avail_names   = {d: [] for d in ALL_DAYS}
    day_unavail_names = {d: [] for d in ALL_DAYS}
    if not avail_df.empty and "Name" in avail_df.columns:
        for _, arow in avail_df.iterrows():
            aname = str(arow.get("Name", "")).strip()
            if not aname:
                continue
            for day in ALL_DAYS:
                v = str(arow.get(day, "")).strip()
                if v == "✓":
                    day_avail_names[day].append(aname)
                elif v == "✗":
                    day_unavail_names[day].append(aname)
 
    # ── Calendar session state ────────────────────────────────────────────────
    ss_key = f"cal_state_{user}"
    if ss_key not in st.session_state:
        # First time this user loads — seed from sheet data
        st.session_state[ss_key] = dict(saved_state)
    else:
        # Already have local state — sync any sheet values that are newer
        # (e.g. saved on another device, or just after a save+rerun)
        for day, val in saved_state.items():
            if val and not st.session_state[ss_key].get(day):
                st.session_state[ss_key][day] = val
 
    # Month navigation: 0 = May 2026, 1 = June 2026
    if "cal_month_idx" not in st.session_state:
        # Default to current month if within range, else May
        st.session_state["cal_month_idx"] = 1 if today.month >= 6 else 0
 
    cal_state  = st.session_state[ss_key]
    month_idx  = st.session_state["cal_month_idx"]
    months     = [(2026, 5, "May 2026"), (2026, 6, "June 2026")]
    yr, mo, mo_label = months[month_idx]
 
    def set_day(day, val):
        cal_state[day] = "" if cal_state.get(day) == val else val
        st.session_state[ss_key] = cal_state
 
    # ── Save button + nav header ──────────────────────────────────────────────
    h1, h2, h3, h4, h5 = st.columns([2, 1, 2, 1, 3])
    with h1:
        if identified:
            if st.button("💾 Save Availability", type="primary", use_container_width=True):
                row = [user] + [cal_state.get(d, "") for d in ALL_DAYS]
                try:
                    if existing_idx:
                        update_row("availability", existing_idx, row)
                    else:
                        append_row("availability", row)
                    read_all_sheets.clear()
                    st.session_state["sheets_data"] = read_all_sheets()
                    # Re-seed this user's session state from freshly loaded sheet
                    fresh_avail = st.session_state["sheets_data"].get("availability", pd.DataFrame())
                    if not fresh_avail.empty and "Name" in fresh_avail.columns:
                        match2 = fresh_avail[fresh_avail["Name"] == user]
                        if not match2.empty:
                            fresh_row = match2.iloc[0]
                            for day in ALL_DAYS:
                                v = str(fresh_row.get(day, "")).strip()
                                if v in ("✓", "✗"):
                                    st.session_state[ss_key][day] = v
                    st.success("✅ Saved!")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")
    with h2:
        if st.button("◀", use_container_width=True, disabled=(month_idx == 0)):
            st.session_state["cal_month_idx"] = 0
            st.rerun()
    with h3:
        st.markdown(
            f"<div style='text-align:center;font-size:16px;font-weight:600;"
            f"padding:6px 0;color:#3c4043'>📅 {mo_label}</div>",
            unsafe_allow_html=True)
    with h4:
        if st.button("▶", use_container_width=True, disabled=(month_idx == 1)):
            st.session_state["cal_month_idx"] = 1
            st.rerun()
    with h5:
        st.caption("✅ = available · ❌ = not available · press again to clear · then 💾 Save")
 
    # ── Build calendar grid for current month ─────────────────────────────────
    all_month_days = []
    d = date(yr, mo, 1)
    while d.month == mo:
        all_month_days.append(d)
        d += timedelta(days=1)
 
    start_offset = date(yr, mo, 1).weekday()  # 0=Mon
    grid = [None] * start_offset + all_month_days
    while len(grid) % 7 != 0:
        grid.append(None)
 
    # ── Calendar header ───────────────────────────────────────────────────────
    st.markdown("""
    <style>
    .dow-hdr{display:grid;grid-template-columns:repeat(7,1fr);
             border:1px solid #e0e0e0;background:#f8f9fa;margin-top:4px}
    .dow-cell{text-align:center;padding:7px 0;font-size:10px;font-weight:600;
              text-transform:uppercase;letter-spacing:.08em;color:#70757a}
    .cal-day-btn button {
        padding: 1px 2px !important;
        min-height: 22px !important;
        height: 22px !important;
        font-size: 11px !important;
        line-height: 1 !important;
    }
    </style>
    <div class="dow-hdr">
      <div class="dow-cell">Mon</div><div class="dow-cell">Tue</div>
      <div class="dow-cell">Wed</div><div class="dow-cell">Thu</div>
      <div class="dow-cell">Fri</div>
      <div class="dow-cell" style="color:#ccc">Sat</div>
      <div class="dow-cell" style="color:#ccc">Sun</div>
    </div>
    """, unsafe_allow_html=True)
 
    rows_of_7 = [grid[i:i+7] for i in range(0, len(grid), 7)]
 
    for week_row in rows_of_7:
        cols = st.columns(7, gap="small")
        for ci, cell in enumerate(week_row):
            with cols[ci]:
                if cell is None or cell.weekday() >= 5:
                    day_label = str(cell.day) if cell else ""
                    st.markdown(
                        f"<div style='min-height:110px;background:#fafafa;"
                        f"border:1px solid #eee;padding:6px 4px;"
                        f"color:#ccc;font-size:11px;border-radius:4px'>{day_label}</div>",
                        unsafe_allow_html=True)
                else:
                    ds       = cell.strftime("%a %b %d")
                    s        = cal_state.get(ds, "")
                    is_past  = cell < today
                    in_range = ds in ALL_DAYS
 
                    if is_past or not in_range:
                        # Past or non-event day — greyed out, not clickable
                        st.markdown(
                            f"<div style='min-height:110px;background:#f5f5f5;"
                            f"border:1px solid #eee;padding:6px 4px;"
                            f"border-radius:4px;opacity:0.5'>"
                            f"<span style='font-size:11px;color:#bbb;font-weight:600'>{cell.day}</span>"
                            f"</div>",
                            unsafe_allow_html=True)
                    else:
                        if s == "✓":
                            bg = "#e6f4ea"; bdr = "#34a853"; num_bg = "#34a853"; num_col = "#fff"
                        elif s == "✗":
                            bg = "#fce8e6"; bdr = "#ea4335"; num_bg = "#ea4335"; num_col = "#fff"
                        else:
                            bg = "#fff"; bdr = "#e8eaed"; num_bg = "#f1f3f4"; num_col = "#3c4043"
 
                        chips = ""
                        if identified:
                            if s == "✓":
                                chips += f"<span style='display:block;font-size:8px;font-weight:600;padding:1px 3px;border-radius:4px;background:#34a853;color:#fff;margin-bottom:1px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap'>{user}</span>"
                            elif s == "✗":
                                chips += f"<span style='display:block;font-size:8px;font-weight:600;padding:1px 3px;border-radius:4px;background:#ea4335;color:#fff;margin-bottom:1px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap'>{user}</span>"
                        for n in day_avail_names.get(ds, []):
                            if n != user:
                                chips += f"<span style='display:block;font-size:8px;padding:1px 3px;border-radius:4px;background:#34a85320;color:#1a7a38;border:1px solid #34a85340;margin-bottom:1px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap'>{n}</span>"
                        for n in day_unavail_names.get(ds, []):
                            if n != user:
                                chips += f"<span style='display:block;font-size:8px;padding:1px 3px;border-radius:4px;background:#ea433520;color:#b71c1c;border:1px solid #ea433540;margin-bottom:1px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap'>{n}</span>"
 
                        st.markdown(
                            f"<div style='background:{bg};border:1px solid {bdr};"
                            f"border-radius:4px 4px 0 0;padding:5px 4px;min-height:80px'>"
                            f"<span style='display:inline-flex;align-items:center;justify-content:center;"
                            f"width:22px;height:22px;border-radius:50%;background:{num_bg};"
                            f"color:{num_col};font-size:11px;font-weight:600;margin-bottom:3px'>"
                            f"{cell.day}</span>"
                            f"<div>{chips}</div></div>",
                            unsafe_allow_html=True)
 
                        if identified:
                            st.markdown('<div class="cal-day-btn">', unsafe_allow_html=True)
                            b1, b2 = st.columns(2, gap="small")
                            with b1:
                                if st.button("✅", key=f"avail_{ds}", help="Mark available",
                                             use_container_width=True):
                                    set_day(ds, "✓")
                                    st.rerun()
                            with b2:
                                if st.button("❌", key=f"unavail_{ds}", help="Mark not available",
                                             use_container_width=True):
                                    set_day(ds, "✗")
                                    st.rerun()
                            st.markdown('</div>', unsafe_allow_html=True)
 
    st.markdown("<br>", unsafe_allow_html=True)
 
# ═════════════════════════════════════════════════════════════════════════════
# TAB 2 & 3 · EVENTS + DINING
# ═════════════════════════════════════════════════════════════════════════════
def get_col(row, *candidates):
    for c in candidates:
        val = row.get(c, "")
        if str(val).strip() not in ("", "nan", "None"):
            return str(val).strip()
    return ""
 
def ideas_tab(tab, sheet_tab, label):
    with tab:
        st.subheader(f"{label} Ideas")
        try:
            df = get_data(sheet_tab)
        except Exception as e:
            st.error(f"Could not load data: {e}")
            df = pd.DataFrame()
 
        if not df.empty:
            df.columns = [c.strip() for c in df.columns]
 
        col_list, col_form = st.columns([3, 2], gap="large")
 
        with col_list:
            st.markdown(f"#### 📋 Current {label} Suggestions")
            if df.empty or len(df) == 0:
                st.info(f"No {label.lower()} ideas yet — be the first to add one!")
            else:
                for i, row in df.iterrows():
                    title_val = get_col(row, "Title", "title")
                    by_val    = get_col(row, "Submitted By", "submitted by", "Name")
                    desc_val  = get_col(row, "Description", "description")
                    link_val  = get_col(row, "Link", "link", "Website", "URL")
                    price_val = get_col(row, "Est. Price/Person", "Est. Price", "Price", "price")
 
                    # Compact single-line tile
                    link_html = f' &nbsp;<a href="{link_val}" target="_blank" style="font-size:0.75rem">🔗</a>' if link_val and link_val.startswith("http") else ""
                    price_html = f'<span style="float:right;font-size:0.75rem;color:#555">💰${price_val}/pp</span>' if price_val else ""
                    desc_html = f'<div style="font-size:0.75rem;color:#777;margin-top:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">{desc_val}</div>' if desc_val else ""
                    st.markdown(
                        f'<div style="border:1px solid #e0e0e0;border-radius:6px;padding:5px 10px;margin-bottom:4px;background:#fff">'
                        f'{price_html}'
                        f'<span style="font-size:0.85rem;font-weight:600">{title_val or "Untitled"}</span>{link_html}'
                        f'<span style="font-size:0.72rem;color:#999;margin-left:6px">by {by_val or "Unknown"}</span>'
                        f'{desc_html}'
                        f'</div>',
                        unsafe_allow_html=True)
 
        with col_form:
            st.markdown(f"#### ➕ Add a {label} Idea")
            if not identified:
                st.info("Select your name in the sidebar to submit.")
            else:
                with st.form(key=f"form_{sheet_tab}", clear_on_submit=True):
                    title = st.text_input("Title *", placeholder="e.g. Bowling Night")
                    desc  = st.text_area("Description (optional)",
                                         placeholder="Tell the team more about this idea...",
                                         height=80)
                    link  = st.text_input("Link (optional)", placeholder="https://...")
                    price = st.text_input("Est. Price/Person (optional)", placeholder="e.g. 25")
                    if st.form_submit_button("Submit Idea", type="primary", use_container_width=True):
                        if not title.strip():
                            st.warning("Please enter a title.")
                        else:
                            try:
                                append_row(sheet_tab,
                                           [user, title.strip(), desc.strip(),
                                            link.strip(), price.strip()])
                                read_all_sheets.clear()
                                st.session_state["sheets_data"] = read_all_sheets()
                                st.success(f"✅ {label} idea submitted!")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error saving: {e}")
 
ideas_tab(tab2, "events", "Event")
ideas_tab(tab3, "dining", "Dining")
 
# ═════════════════════════════════════════════════════════════════════════════
# TAB 4 · VOTES
# ═════════════════════════════════════════════════════════════════════════════
with tab4:
    st.subheader("Cast Your Votes")
    st.caption("Rank your top 3 picks for events and dining. You can update anytime.")
 
    try:
        # Always read fresh so tally reflects latest votes immediately
        _sh = get_sheet()
        def _read_fresh(tab):
            ws = _sh.worksheet(tab)
            vals = ws.get_all_values()
            if not vals or len(vals) < 2:
                return pd.DataFrame()
            hdrs = [h.strip() for h in vals[0]]
            rows = [r + [""] * (len(hdrs) - len(r)) for r in vals[1:]]
            return pd.DataFrame(rows, columns=hdrs)
        events_df = _read_fresh("events")
        dining_df = _read_fresh("dining")
        votes_df  = _read_fresh("votes")
    except Exception as e:
        st.error(f"Could not load voting data: {e}")
        events_df = dining_df = votes_df = pd.DataFrame()
 
    for _df in [events_df, dining_df, votes_df]:
        if not _df.empty:
            _df.columns = [c.strip() for c in _df.columns]
 
    # ── Deduplicate votes sheet — keep last row per person, delete extras ─────
    if not votes_df.empty and "Name" in votes_df.columns:
        dupes = votes_df[votes_df.duplicated(subset=["Name"], keep="last")]
        if not dupes.empty:
            # Delete duplicate rows from sheet (highest row index first to avoid shifting)
            sh = get_sheet()
            ws = sh.worksheet("votes")
            for idx in sorted(dupes.index.tolist(), reverse=True):
                ws.delete_rows(idx + 2)  # +2: header row + 1-based
            refresh_data()
            votes_df = get_data("votes")
            if not votes_df.empty:
                votes_df.columns = [c.strip() for c in votes_df.columns]
 
    def get_titles(df):
        for col in ["Title", "title"]:
            if not df.empty and col in df.columns:
                return [str(v).strip() for v in df[col]
                        if str(v).strip() not in ("", "nan")]
        return []
 
    event_titles  = get_titles(events_df)
    dining_titles = get_titles(dining_df)
 
    def tally(df, col_prefix, titles):
        counts = {t: 0 for t in titles}
        weights = {"1st": 3, "2nd": 2, "3rd": 1}
        if df.empty:
            return counts
        for _, row in df.iterrows():
            for rank, w in weights.items():
                pick = str(row.get(f"{col_prefix} {rank}", "")).strip()
                if pick in counts:
                    counts[pick] += w
        return counts
 
    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 🎯 Event Vote Tally")
        if event_titles:
            tally_e = tally(votes_df, "Event", event_titles)
            st.dataframe(
                pd.DataFrame(list(tally_e.items()), columns=["Event", "Score"])
                  .sort_values("Score", ascending=False),
                use_container_width=True, hide_index=True)
        else:
            st.info("No events proposed yet.")
 
    with c2:
        st.markdown("#### 🍽️ Dining Vote Tally")
        if dining_titles:
            tally_d = tally(votes_df, "Dining", dining_titles)
            st.dataframe(
                pd.DataFrame(list(tally_d.items()), columns=["Dining", "Score"])
                  .sort_values("Score", ascending=False),
                use_container_width=True, hide_index=True)
        else:
            st.info("No dining ideas proposed yet.")
 
    st.divider()
 
    if not identified:
        st.info("Select your name in the sidebar to vote.")
    else:
        # Always read votes fresh so banner and pre-fill are accurate
        try:
            sh = get_sheet()
            ws_votes = sh.worksheet("votes")
            votes_live = ws_votes.get_all_values()
            existing_vote = None
            if len(votes_live) > 1:
                v_headers = [h.strip() for h in votes_live[0]]
                for vrow in votes_live[1:]:
                    if vrow and vrow[0].strip().lower() == user.lower():
                        padded = vrow + [""] * (len(v_headers) - len(vrow))
                        existing_vote = dict(zip(v_headers, padded))
                        break
        except Exception:
            existing_vote = None
 
        st.markdown(f"#### {user}'s Votes")
        none_opt = "— no pick —"
 
        if existing_vote is not None:
            st.info("You've already voted — your selections are pre-filled. Saving will overwrite your previous vote.")
 
        col1, col2 = st.columns(2)
 
        with col1:
            st.markdown("**🎯 Event Rankings**")
            if event_titles:
                e_opts = [none_opt] + event_titles
                def ev(key):
                    v = existing_vote.get(key, none_opt).strip() if existing_vote else none_opt
                    return e_opts.index(v) if v in e_opts else 0
                e1 = st.selectbox("🥇 1st Choice (3 pts)", e_opts, index=ev("Event 1st"), key="e1")
                e2_opts = [o for o in e_opts if o == none_opt or o != e1]
                e2_def = (existing_vote.get("Event 2nd", none_opt).strip() if existing_vote else none_opt)
                e2_def = e2_def if e2_def in e2_opts else none_opt
                e2 = st.selectbox("🥈 2nd Choice (2 pts)", e2_opts, index=e2_opts.index(e2_def), key="e2")
                e3_opts = [o for o in e_opts if o == none_opt or (o != e1 and o != e2)]
                e3_def = (existing_vote.get("Event 3rd", none_opt).strip() if existing_vote else none_opt)
                e3_def = e3_def if e3_def in e3_opts else none_opt
                e3 = st.selectbox("🥉 3rd Choice (1 pt)", e3_opts, index=e3_opts.index(e3_def), key="e3")
            else:
                st.info("Add event ideas first.")
                e1 = e2 = e3 = none_opt
 
        with col2:
            st.markdown("**🍽️ Dining Rankings**")
            if dining_titles:
                d_opts = [none_opt] + dining_titles
                def dv(key):
                    v = existing_vote.get(key, none_opt).strip() if existing_vote else none_opt
                    return d_opts.index(v) if v in d_opts else 0
                d1 = st.selectbox("🥇 1st Choice (3 pts)", d_opts, index=dv("Dining 1st"), key="d1")
                d2_opts = [o for o in d_opts if o == none_opt or o != d1]
                d2_def = (existing_vote.get("Dining 2nd", none_opt).strip() if existing_vote else none_opt)
                d2_def = d2_def if d2_def in d2_opts else none_opt
                d2 = st.selectbox("🥈 2nd Choice (2 pts)", d2_opts, index=d2_opts.index(d2_def), key="d2")
                d3_opts = [o for o in d_opts if o == none_opt or (o != d1 and o != d2)]
                d3_def = (existing_vote.get("Dining 3rd", none_opt).strip() if existing_vote else none_opt)
                d3_def = d3_def if d3_def in d3_opts else none_opt
                d3 = st.selectbox("🥉 3rd Choice (1 pt)", d3_opts, index=d3_opts.index(d3_def), key="d3")
            else:
                st.info("Add dining ideas first.")
                d1 = d2 = d3 = none_opt
 
        if st.button("💾 Save Votes", type="primary"):
            def clean(v): return "" if v == none_opt else v
            new_row = [user, clean(e1), clean(e2), clean(e3), clean(d1), clean(d2), clean(d3)]
            try:
                # Always read fresh from sheet to get true current state
                sh = get_sheet()
                ws = sh.worksheet("votes")
                all_vals = ws.get_all_values()
                # Find any existing rows for this user (case-insensitive)
                existing_rows = []
                for i, r in enumerate(all_vals[1:], start=2):  # start=2: 1-based + skip header
                    if r and r[0].strip().lower() == user.lower():
                        existing_rows.append(i)
 
                if existing_rows:
                    # Update the first match, delete any extras (reverse to avoid index shift)
                    update_row("votes", existing_rows[0], new_row)
                    for extra_idx in sorted(existing_rows[1:], reverse=True):
                        ws.delete_rows(extra_idx)
                else:
                    append_row("votes", new_row)
 
                read_all_sheets.clear()
                st.session_state["sheets_data"] = read_all_sheets()
                st.success("✅ Votes saved!")
                st.rerun()
            except Exception as e:
                st.error(f"Error saving votes: {e}")
