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
    st.subheader("When are you available in June?")
    st.caption("Check every day that works for you. Your selections save automatically.")

    try:
        avail_df = read_sheet("availability")
    except Exception as e:
        st.error(f"Could not load availability data: {e}")
        avail_df = pd.DataFrame()

    # Show summary grid (all users)
    if not avail_df.empty:
        st.markdown("#### Team Availability Overview")
        display_df = avail_df.set_index("Name") if "Name" in avail_df.columns else avail_df
        # Replace 1/0 or TRUE/FALSE with emoji
        def fmt(val):
            if str(val).upper() in ("TRUE", "1", "YES", "✓"):
                return "✅"
            return ""
        styled = display_df.applymap(fmt)
        st.dataframe(styled, use_container_width=True)

    st.divider()

    if not identified:
        st.info("Select your name in the sidebar to mark your availability.")
    else:
        st.markdown(f"#### {user}'s Availability")

        # Pre-fill existing selections
        existing_row = None
        existing_idx = None
        if not avail_df.empty and "Name" in avail_df.columns:
            match = avail_df[avail_df["Name"] == user]
            if not match.empty:
                existing_row = match.iloc[0]
                existing_idx = match.index[0] + 2  # +2 for header row + 1-based

        # Build week-grouped checkboxes
        weeks = {}
        for day_str in JUNE_DAYS:
            d = pd.to_datetime(day_str, format="%a %b %d")
            week_num = d.isocalendar()[1]
            weeks.setdefault(week_num, []).append(day_str)

        selections = {}
        for wk, days in weeks.items():
            cols = st.columns(len(days))
            for col, day in zip(cols, days):
                default = False
                if existing_row is not None and day in existing_row:
                    val = str(existing_row[day]).upper()
                    default = val in ("TRUE", "1", "YES", "✓")
                selections[day] = col.checkbox(day, value=default, key=f"avail_{user}_{day}")

        if st.button("💾 Save Availability", type="primary"):
            row = [user] + [("✓" if selections[d] else "") for d in JUNE_DAYS]
            try:
                if existing_idx:
                    update_row("availability", existing_idx, row)
                else:
                    append_row("availability", row)
                st.success("Availability saved!")
                st.rerun()
            except Exception as e:
                st.error(f"Error saving: {e}")

# ══════════════════════════════════════════════════════════════════════════════
# TAB 2 · EVENTS
# ══════════════════════════════════════════════════════════════════════════════
def ideas_tab(tab, sheet_tab, label):
    with tab:
        st.subheader(f"{label} Ideas")

        try:
            df = read_sheet(sheet_tab)
        except Exception as e:
            st.error(f"Could not load data: {e}")
            df = pd.DataFrame()

        # Show existing ideas
        if not df.empty:
            st.markdown(f"#### Current {label} Suggestions")
            for i, row in df.iterrows():
                with st.container(border=True):
                    c1, c2, c3 = st.columns([3, 2, 1])
                    c1.markdown(f"**{row.get('Title','—')}**  \n*Suggested by {row.get('Submitted By','—')}*")
                    link = row.get("Link", "")
                    if link and str(link).startswith("http"):
                        c2.markdown(f"[🔗 More Info]({link})")
                    price = row.get("Est. Price/Person", "")
                    if price:
                        c3.markdown(f"💰 **${price}**")
        else:
            st.info(f"No {label.lower()} ideas yet — be the first to add one!")

        st.divider()

        if not identified:
            st.info("Select your name in the sidebar to submit an idea.")
        else:
            st.markdown(f"#### ➕ Add a {label} Idea")
            with st.form(key=f"form_{sheet_tab}"):
                title = st.text_input("Title *", placeholder=f"e.g. Bowling Night")
                link  = st.text_input("Website / Link (optional)", placeholder="https://...")
                price = st.text_input("Estimated Price Per Person (optional)", placeholder="e.g. 25")
                submitted = st.form_submit_button("Submit Idea", type="primary")
                if submitted:
                    if not title:
                        st.warning("Please enter a title.")
                    else:
                        try:
                            append_row(sheet_tab, [user, title, link, price])
                            st.success(f"{label} idea submitted!")
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

    event_titles  = list(events_df["Title"]) if not events_df.empty and "Title" in events_df.columns else []
    dining_titles = list(dining_df["Title"]) if not dining_df.empty and "Title" in dining_df.columns else []

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
