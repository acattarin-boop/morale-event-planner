import streamlit as st
import pandas as pd
import gspread
from google.oauth2.service_account import Credentials
from datetime import date, timedelta
import json
import streamlit.components.v1 as components
 
# ── Config ───────────────────────────────────────────────────────────────────
SHEET_ID = "18-q7ItMDfPkdvS7o01UzS4Xbyz6KmDDaTjcBTksoBlU"
 
BASE_NAMES = [
    "Ahmed", "Alec", "Brian", "Dave", "Farhad",
    "Kyle", "Leo", "Meng", "Peter", "Ranga", "Sesha", "Vivian"
]
 
def get_june_weekdays():
    days = []
    d = date(2026, 6, 1)
    while d.month == 6:
        if d.weekday() < 5:
            days.append(d.strftime("%a %b %d"))
        d += timedelta(days=1)
    return days
 
JUNE_DAYS = get_june_weekdays()
 
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
 
@st.cache_data(ttl=30)
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
 
@st.cache_data(ttl=30)
def read_names_from_sheet():
    """Read extra names persisted in the 'names' Google Sheet tab."""
    try:
        sh = get_sheet()
        ws = sh.worksheet("names")
        vals = ws.col_values(1)
        return [v.strip() for v in vals if v.strip() and v.strip().lower() != "name"]
    except Exception:
        return []
 
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
 
def update_row(tab, row_index: int, row: list):
    sh = get_sheet()
    ws = sh.worksheet(tab)
    ws.update(f"A{row_index}:{chr(64+len(row))}{row_index}", [row])
 
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
 
# Ensure availability sheet has correct headers (fixes column mismatch)
init_availability_headers()
 
# ── Load names (persists across sessions via Google Sheet) ────────────────────
extra_names = read_names_from_sheet()
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
            read_names_from_sheet.clear()
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
    st.subheader("When are you available in June?")
    st.caption("Click a date: **green** = available · **red** = not available · click again to clear")
 
    try:
        avail_df = read_sheet("availability")
    except Exception as e:
        st.error(f"Could not load availability data: {e}")
        avail_df = pd.DataFrame()
 
    # Normalise avail_df column names to match JUNE_DAYS format exactly
    # Build a mapping from normalised sheet header -> JUNE_DAYS key
    if not avail_df.empty:
        avail_df.columns = [c.strip() for c in avail_df.columns]
        # Build a lookup: normalised-lowercase -> actual JUNE_DAY string
        june_day_lookup = {d.lower().replace(" 0", " "): d for d in JUNE_DAYS}
        # Rename sheet columns to match JUNE_DAYS if they differ only by zero-padding
        rename_map = {}
        for col in avail_df.columns:
            normalised = col.lower().replace(" 0", " ")
            if normalised in june_day_lookup and col != june_day_lookup[normalised]:
                rename_map[col] = june_day_lookup[normalised]
        if rename_map:
            avail_df = avail_df.rename(columns=rename_map)
 
    # Per-day availability counts
    day_counts = {}
    total_users = len(avail_df) if not avail_df.empty else 0
    for day in JUNE_DAYS:
        if not avail_df.empty and day in avail_df.columns:
            day_counts[day] = int(avail_df[day].apply(
                lambda v: 1 if str(v).strip() == "✓" else 0).sum())
        else:
            day_counts[day] = 0
 
    # Load this user's saved state
    existing_row = None
    existing_idx = None
    if not avail_df.empty and "Name" in avail_df.columns:
        match = avail_df[avail_df["Name"] == user]
        if not match.empty:
            existing_row = match.iloc[0]
            existing_idx = int(match.index[0]) + 2
 
    saved_state = {}
    for day in JUNE_DAYS:
        val = ""
        if existing_row is not None and day in existing_row:
            v = str(existing_row[day]).strip()
            if v in ("✓", "✗"):
                val = v
        saved_state[day] = val
 
    # Per-day name lists (all users)
    day_avail_names   = {d: [] for d in JUNE_DAYS}
    day_unavail_names = {d: [] for d in JUNE_DAYS}
    if not avail_df.empty and "Name" in avail_df.columns:
        for _, arow in avail_df.iterrows():
            aname = str(arow.get("Name", "")).strip()
            if not aname:
                continue
            for day in JUNE_DAYS:
                v = str(arow.get(day, "")).strip()
                if v == "✓":
                    day_avail_names[day].append(aname)
                elif v == "✗":
                    day_unavail_names[day].append(aname)
 
    # Build June 2026 calendar grid (starts Monday = offset 0)
    all_june = []
    d = date(2026, 6, 1)
    while d.month == 6:
        all_june.append(d)
        d += timedelta(days=1)
    start_offset = date(2026, 6, 1).weekday()
    grid = [None] * start_offset + all_june
    while len(grid) % 7 != 0:
        grid.append(None)
 
    grid_data = []
    for cell in grid:
        if cell is None:
            grid_data.append({"day_num": None, "day_str": None, "is_weekday": False})
        else:
            ds = cell.strftime("%a %b %d")
            iw = cell.weekday() < 5
            grid_data.append({"day_num": cell.day, "day_str": ds if iw else None, "is_weekday": iw})
 
    identified_js          = "true" if identified else "false"
    user_js                = json.dumps(user)
    grid_data_json         = json.dumps(grid_data)
    june_days_json         = json.dumps(JUNE_DAYS)
    saved_state_json       = json.dumps(saved_state)
    day_avail_names_json   = json.dumps(day_avail_names)
    day_unavail_names_json = json.dumps(day_unavail_names)
 
    calendar_html = f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
  @import url('https://fonts.googleapis.com/css2?family=Google+Sans:wght@400;500;600&family=Roboto:wght@300;400;500&display=swap');
  *{{box-sizing:border-box;margin:0;padding:0}}
  body{{font-family:'Roboto',sans-serif;background:transparent}}
  .cal-wrap{{background:#fff;border-radius:16px;border:1px solid #e0e0e0;overflow:hidden;box-shadow:0 2px 12px rgba(0,0,0,.08)}}
  .cal-header{{padding:18px 24px 10px;display:flex;align-items:center;gap:12px}}
  .cal-title{{font-family:'Google Sans',sans-serif;font-size:20px;font-weight:400;color:#3c4043}}
  .cal-legend{{display:flex;gap:14px;margin-left:auto;align-items:center;flex-wrap:wrap}}
  .leg-item{{display:flex;align-items:center;gap:5px;font-size:11px;color:#5f6368}}
  .leg-dot{{width:10px;height:10px;border-radius:50%}}
  .lg{{background:#34a853}}.lr{{background:#ea4335}}.lgr{{background:#e0e0e0;border:1px solid #ccc}}
  .dow-row{{display:grid;grid-template-columns:repeat(7,1fr);border-bottom:1px solid #e0e0e0}}
  .dow-cell{{text-align:center;padding:7px 0;font-size:10px;font-weight:500;text-transform:uppercase;letter-spacing:.08em;color:#70757a}}
  .cal-grid{{display:grid;grid-template-columns:repeat(7,1fr)}}
  .cal-cell{{min-height:115px;border-right:1px solid #e8eaed;border-bottom:1px solid #e8eaed;padding:6px 4px;background:#fff;transition:background .12s;overflow:hidden}}
  .cal-cell:nth-child(7n){{border-right:none}}
  .empty{{background:#fafafa}}
  .weekend{{background:#fafafa;cursor:default}}
  .weekend .dn{{color:#bbb}}
  .available{{background:#e6f4ea;cursor:pointer}}
  .unavailable{{background:#fce8e6;cursor:pointer}}
  .workday{{cursor:pointer}}
  .workday:hover{{background:#f1f3f4}}
  .available:hover{{background:#ceead6}}
  .unavailable:hover{{background:#f5c6c3}}
  .dn{{font-family:'Google Sans',sans-serif;font-size:12px;font-weight:500;color:#3c4043;
       display:inline-flex;align-items:center;justify-content:center;
       width:24px;height:24px;border-radius:50%;margin-bottom:2px}}
  .available .dn{{background:#34a853;color:#fff}}
  .unavailable .dn{{background:#ea4335;color:#fff}}
  .nl{{display:flex;flex-direction:column;gap:2px;margin-top:2px}}
  .nc{{font-size:9px;font-weight:500;padding:1px 4px;border-radius:6px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:100%}}
  .ncg{{background:#34a85322;color:#1a7a38;border:1px solid #34a85344}}
  .ncr{{background:#ea433522;color:#b71c1c;border:1px solid #ea433544}}
  .ncmg{{background:#34a853;color:#fff}}
  .ncmr{{background:#ea4335;color:#fff}}
  .save-row{{padding:14px 20px;border-top:1px solid #e0e0e0;display:flex;align-items:center;gap:14px;background:#fff;flex-wrap:wrap}}
  .save-btn{{background:#1a73e8;color:#fff;border:none;border-radius:8px;padding:9px 24px;font-size:13px;font-weight:500;cursor:pointer;font-family:'Google Sans',sans-serif;transition:background .2s}}
  .save-btn:hover{{background:#1557b0}}
  .save-btn:disabled{{background:#ccc;cursor:default}}
  .save-hint{{font-size:11px;color:#70757a}}
  .save-msg{{font-size:12px;font-weight:500}}
  .ok{{color:#34a853}}.err{{color:#ea4335}}
  .no-id{{padding:16px 20px;color:#70757a;font-size:13px}}
</style></head><body>
<div class="cal-wrap">
  <div class="cal-header">
    <span class="cal-title">📅 June 2026</span>
    <div class="cal-legend">
      <div class="leg-item"><div class="leg-dot lg"></div>Available</div>
      <div class="leg-item"><div class="leg-dot lr"></div>Not available</div>
      <div class="leg-item"><div class="leg-dot lgr"></div>No response</div>
    </div>
  </div>
  <div class="dow-row">
    <div class="dow-cell">Mon</div><div class="dow-cell">Tue</div>
    <div class="dow-cell">Wed</div><div class="dow-cell">Thu</div>
    <div class="dow-cell">Fri</div>
    <div class="dow-cell" style="color:#bbb">Sat</div>
    <div class="dow-cell" style="color:#bbb">Sun</div>
  </div>
  <div class="cal-grid" id="calGrid"></div>
  <div class="save-row" id="saveRow">
    <button class="save-btn" id="saveBtn" onclick="saveData()">💾 Save Availability</button>
    <span class="save-hint">Click once = available · again = not available · again = clear</span>
    <span class="save-msg" id="saveMsg"></span>
  </div>
</div>
<script>
const IDENTIFIED={identified_js};
const USER={user_js};
const GRID_DATA={grid_data_json};
const JUNE_DAYS={june_days_json};
const AVAIL_NAMES={day_avail_names_json};
const UNAVAIL_NAMES={day_unavail_names_json};
let state={saved_state_json};
 
function cycle(s){{ return s===""?"✓":s==="✓"?"✗":""; }}
function cellCls(ds){{
  if(!IDENTIFIED) return "cal-cell workday";
  const s=state[ds]||"";
  if(s==="✓") return "cal-cell available";
  if(s==="✗") return "cal-cell unavailable";
  return "cal-cell workday";
}}
function render(){{
  const g=document.getElementById("calGrid");
  g.innerHTML="";
  GRID_DATA.forEach(cell=>{{
    const div=document.createElement("div");
    if(cell.day_num===null){{ div.className="cal-cell empty"; g.appendChild(div); return; }}
    if(!cell.is_weekday){{ div.className="cal-cell weekend"; div.innerHTML=`<span class="dn">${{cell.day_num}}</span>`; g.appendChild(div); return; }}
    const ds=cell.day_str; const s=state[ds]||"";
    div.className=cellCls(ds);
    if(IDENTIFIED) div.onclick=()=>{{ state[ds]=cycle(state[ds]||""); render(); }};
    const av=(AVAIL_NAMES[ds]||[]).filter(n=>n!==USER);
    const un=(UNAVAIL_NAMES[ds]||[]).filter(n=>n!==USER);
    let chips='<div class="nl">';
    if(s==="✓") chips+=`<span class="nc ncmg">✓ ${{USER}}</span>`;
    if(s==="✗") chips+=`<span class="nc ncmr">✗ ${{USER}}</span>`;
    av.forEach(n=>{{ chips+=`<span class="nc ncg">${{n}}</span>`; }});
    un.forEach(n=>{{ chips+=`<span class="nc ncr">${{n}}</span>`; }});
    chips+='</div>';
    div.innerHTML=`<span class="dn">${{cell.day_num}}</span>${{chips}}`;
    g.appendChild(div);
  }});
}}
function saveData(){{
  if(!IDENTIFIED) return;
  const btn=document.getElementById("saveBtn");
  const msg=document.getElementById("saveMsg");
  btn.disabled=true; btn.textContent="Saving..."; msg.textContent="";
  const avail=JUNE_DAYS.filter(d=>state[d]==="✓").map(d=>encodeURIComponent(d)).join("|");
  const unavail=JUNE_DAYS.filter(d=>state[d]==="✗").map(d=>encodeURIComponent(d)).join("|");
  const url=new URL(window.parent.location.href);
  url.searchParams.set("cal_avail",avail);
  url.searchParams.set("cal_unavail",unavail);
  url.searchParams.set("cal_user",USER);
  url.searchParams.set("cal_save","1");
  window.parent.history.replaceState({{}},"",url.toString());
  setTimeout(()=>{{
    btn.disabled=false; btn.textContent="💾 Save Availability";
    msg.className="save-msg ok"; msg.textContent="✅ Saved!";
  }},400);
}}
if(!IDENTIFIED) document.getElementById("saveRow").innerHTML='<div class="no-id">👈 Select your name in the sidebar first.</div>';
render();
</script></body></html>"""
 
    components.html(calendar_html, height=780, scrolling=False)
 
    # Auto-commit when JS save was triggered via URL params
    if identified:
        qp = st.query_params
        if qp.get("cal_save") == "1" and qp.get("cal_user") == user:
            avail_raw   = qp.get("cal_avail", "")
            unavail_raw = qp.get("cal_unavail", "")
            avail_days   = set(avail_raw.split("|"))   if avail_raw   else set()
            unavail_days = set(unavail_raw.split("|")) if unavail_raw else set()
            current_state = {}
            for d in JUNE_DAYS:
                if d in avail_days:     current_state[d] = "✓"
                elif d in unavail_days: current_state[d] = "✗"
                else:                   current_state[d] = ""
            row = [user] + [current_state.get(d, "") for d in JUNE_DAYS]
            try:
                if existing_idx:
                    update_row("availability", existing_idx, row)
                else:
                    append_row("availability", row)
                read_sheet.clear()
                st.query_params.clear()
                st.rerun()
            except Exception as e:
                st.error(f"Error saving availability: {e}")
 
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
            df = read_sheet(sheet_tab)
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
 
                    with st.container(border=True):
                        st.markdown(f"**{title_val or 'Untitled'}**")
                        st.caption(f"Suggested by {by_val or 'Unknown'}")
                        if desc_val:
                            st.markdown(
                                f"<span style='font-size:0.85rem;color:#555'>{desc_val}</span>",
                                unsafe_allow_html=True)
                        mc = st.columns([2, 1])
                        if link_val and link_val.startswith("http"):
                            mc[0].markdown(f"[🔗 More Info]({link_val})")
                        if price_val:
                            mc[1].markdown(f"💰 **${price_val}/pp**")
 
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
                                read_sheet.clear()
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
        events_df = read_sheet("events")
        dining_df = read_sheet("dining")
        votes_df  = read_sheet("votes")
    except Exception as e:
        st.error(f"Could not load voting data: {e}")
        events_df = dining_df = votes_df = pd.DataFrame()
 
    for _df in [events_df, dining_df, votes_df]:
        if not _df.empty:
            _df.columns = [c.strip() for c in _df.columns]
 
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
        existing_vote     = None
        existing_vote_idx = None
        if not votes_df.empty and "Name" in votes_df.columns:
            match = votes_df[votes_df["Name"] == user]
            if not match.empty:
                existing_vote     = match.iloc[0]
                existing_vote_idx = int(match.index[0]) + 2
 
        st.markdown(f"#### {user}'s Votes")
        none_opt = "— no pick —"
 
        col1, col2 = st.columns(2)
 
        with col1:
            st.markdown("**🎯 Event Rankings**")
            if event_titles:
                e_opts = [none_opt] + event_titles
                def ei(key):
                    v = str(existing_vote.get(key, none_opt)).strip() if existing_vote is not None else none_opt
                    return e_opts.index(v) if v in e_opts else 0
                e1 = st.selectbox("🥇 1st Choice (3 pts)", e_opts, index=ei("Event 1st"), key="e1")
                e2 = st.selectbox("🥈 2nd Choice (2 pts)", e_opts, index=ei("Event 2nd"), key="e2")
                e3 = st.selectbox("🥉 3rd Choice (1 pt)",  e_opts, index=ei("Event 3rd"), key="e3")
            else:
                st.info("Add event ideas first.")
                e1 = e2 = e3 = none_opt
 
        with col2:
            st.markdown("**🍽️ Dining Rankings**")
            if dining_titles:
                d_opts = [none_opt] + dining_titles
                def di(key):
                    v = str(existing_vote.get(key, none_opt)).strip() if existing_vote is not None else none_opt
                    return d_opts.index(v) if v in d_opts else 0
                d1 = st.selectbox("🥇 1st Choice (3 pts)", d_opts, index=di("Dining 1st"), key="d1")
                d2 = st.selectbox("🥈 2nd Choice (2 pts)", d_opts, index=di("Dining 2nd"), key="d2")
                d3 = st.selectbox("🥉 3rd Choice (1 pt)",  d_opts, index=di("Dining 3rd"), key="d3")
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
                read_sheet.clear()
                st.success("✅ Votes saved!")
                st.rerun()
            except Exception as e:
                st.error(f"Error saving votes: {e}")
