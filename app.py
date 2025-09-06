import streamlit as st
from serpapi import GoogleSearch
import statistics

# =========================
# CONFIG
# =========================
API_KEY = "5d0343ae28be99b0554fb2ba9870a3aaa0cdbd356729cbba9577b5b87a45ac22"


# =========================
# PRICE LOOKUP (Google Shopping, US)
# =========================
def fetch_market_prices_us(part_name: str):
    """
    Returns a list of numeric prices from Google Shopping (US) for a given part.
    Low-ball outliers are softened by averaging.
    """
    search = GoogleSearch({
        "q": part_name,
        "tbm": "shop",
        "hl": "en",
        "gl": "us",
        "api_key": API_KEY
    })
    results = search.get_dict()
    items = results.get("shopping_results", [])
    prices = []
    links = []
    for it in items:
        price_str = (it.get("price") or "").replace("$", "").replace(",", "").strip()
        link = it.get("link")
        try:
            price = float(price_str)
            prices.append(price)
            if link:
                links.append(link)
        except:
            continue
    return prices, links


def market_stats(prices):
    """
    From a list of prices, return average.
    """
    if not prices:
        return None
    avg = statistics.mean(prices)
    return avg


# =========================
# EVALUATION LOGIC
# =========================
def evaluate_items(bill_items, avg_margin_pct: float):
    """
    bill_items: [{ part: str, qty: int, cost: float }]
    avg_margin_pct: e.g. 0.10 for +10% over average allowed
    """
    rows = []
    total_bill = 0.0
    total_market_avg = 0.0
    approved = 0
    caution = 0
    rejected = 0


    # --- Category 1: Duplicate entries check ---
    part_seen = {}
    duplicate_flags = set()
    for it in bill_items:
        part_key = (it["Description"].strip().lower(), it["Type"].strip().lower(), it["ATA Code"].strip())
        if part_key in part_seen:
            duplicate_flags.add(part_key)
        part_seen[part_key] = part_seen.get(part_key, 0) + 1

    # Only flag as duplicate if both Description, Type, and ATA Code match (not just ATA Code)
    # --- Category 1: Description clarity check ---
    vague_keywords = ["misc", "other", "unknown", "part", "item"]

    # --- Category 1: Quantity sanity check ---
    excessive_qty_threshold = 20  # Example: flag if qty > 20

    for it in bill_items:
        qty = int(it["Quantity"])
        unit_cost = float(it["Cost"])
        desc = it["Description"].strip()
        type_ = it["Type"].strip()
        ata_code = it["ATA Code"].strip()
        correction = it["Correction"].strip()
        cause = it["Cause"].strip()
        Items_total = unit_cost * qty
        total_bill += Items_total

        # Items completeness
        if not desc or unit_cost <= 0 or qty <= 0:
            status = "Rejected ❌"
            reason = "Missing or zero values for description, quantity, or unit cost."
            avg = None
            market_total = None
            allowed_unit_max = None
            ref_links = []
            rejected += 1
            rows.append({
                "Quantity": qty,
                "Cost": f"${unit_cost:,.2f}",
                "Description": desc,
                "Type": type_,
                "ATA Code": ata_code,
                "Correction": correction,
                "Cause": cause,
                "Items Total ($)": f"${Items_total:,.2f}",
                "Market Avg ($)": "N/A",
                "Allowed Unit Max ($)": "N/A",
                "Market Avg Total ($)": "N/A",
                "Reference Links": "",
                "Status": status,
                "Reason": reason
            })
            continue

        # Only flag as duplicate if both Description, Type, and ATA Code match
        part_key = (desc.lower(), type_.lower(), ata_code)
        if part_key in duplicate_flags:
            status = "Caution ⚠️"
            reason = "Duplicate line detected (same Description, Type, and ATA Code). Please review or merge items."
            avg = None
            market_total = None
            allowed_unit_max = None
            ref_links = []
            caution += 1
            rows.append({
                "Quantity": qty,
                "Cost": f"${unit_cost:,.2f}",
                "Description": desc,
                "Type": type_,
                "ATA Code": ata_code,
                "Correction": correction,
                "Cause": cause,
                "Items Total ($)": f"${Items_total:,.2f}",
                "Market Avg ($)": "N/A",
                "Allowed Unit Max ($)": "N/A",
                "Market Avg Total ($)": "N/A",
                "Reference Links": "",
                "Status": status,
                "Reason": reason
            })
            continue

        # Description clarity check
        if any(kw in desc.lower() for kw in vague_keywords):
            status = "Caution ⚠️"
            reason = "Description is unclear or vague. Please provide a standard part name."
            avg = None
            market_total = None
            allowed_unit_max = None
            ref_links = []
            caution += 1
            rows.append({
                "Quantity": qty,
                "Cost": f"${unit_cost:,.2f}",
                "Description": desc,
                "Type": type_,
                "ATA Code": ata_code,
                "Correction": correction,
                "Cause": cause,
                "Items Total ($)": f"${Items_total:,.2f}",
                "Market Avg ($)": "N/A",
                "Allowed Unit Max ($)": "N/A",
                "Market Avg Total ($)": "N/A",
                "Reference Links": "",
                "Status": status,
                "Reason": reason
            })
            continue

        # Quantity sanity check
        if qty > excessive_qty_threshold:
            status = "Caution ⚠️"
            reason = f"Quantity {qty} is unusually high for a single invoice. Please verify fleet needs."
            avg = None
            market_total = None
            allowed_unit_max = None
            ref_links = []
            caution += 1
            rows.append({
                "Quantity": qty,
                "Cost": f"${unit_cost:,.2f}",
                "Description": desc,
                "Type": type_,
                "ATA Code": ata_code,
                "Correction": correction,
                "Cause": cause,
                "Items Total ($)": f"${Items_total:,.2f}",
                "Market Avg ($)": "N/A",
                "Allowed Unit Max ($)": "N/A",
                "Market Avg Total ($)": "N/A",
                "Reference Links": "",
                "Status": status,
                "Reason": reason
            })
            continue

        # Google search query logic
        if type_.lower() == "part":
            search_query = f"{desc} {ata_code} part"
        elif type_.lower() == "labor":
            search_query = f"{desc} {ata_code} labor {correction} {cause}"
        else:
            search_query = f"{desc} {type_} {ata_code}"
        prices, ref_links = fetch_market_prices_us(search_query)
        avg = market_stats(prices)

        if avg is None:
            status = "Rejected ❌"
            reason = (
                "No market price data found for this item. "
                "Please check the description or try a more common term."
            )
            market_total = None
            allowed_unit_max = None
            rejected += 1
        else:
            market_total = avg * qty
            total_market_avg += market_total
            allowed_unit_max = avg * (1 + avg_margin_pct)

            if unit_cost <= avg:
                status = "Approved ✅"
                reason = (
                    f"Unit cost (${unit_cost:,.2f}) is at or below the market average (${avg:,.2f})."
                )
                approved += 1
            elif unit_cost <= allowed_unit_max:
                status = "Caution ⚠️"
                reason = (
                    f"Unit cost (${unit_cost:,.2f}) is above the market average (${avg:,.2f}) "
                    f"but within the allowed threshold (${allowed_unit_max:,.2f})."
                )
                caution += 1
            else:
                status = "Rejected ❌"
                reason = (
                    f"Unit cost (${unit_cost:,.2f}) exceeds the allowed maximum (${allowed_unit_max:,.2f}) "
                    f"based on market average (${avg:,.2f})."
                )
                rejected += 1

        # Items total validation
        if abs(Items_total - (unit_cost * qty)) > 0.01:
            status = "Caution ⚠️"
            reason = "Items total does not match Qty × Unit Cost. Please check for errors or inflation."
            caution += 1

        # Reference links HTML
        ref_html = ""
        if ref_links:
            ref_html = "<br>".join([f"<a href='{l}' target='_blank'>Link {i+1}</a>" for i, l in enumerate(ref_links[:3])])
        # Add Google Shopping search URL for proof
        google_search_url = f"https://www.google.com/search?tbm=shop&q={search_query.replace(' ', '+')}"
        ref_html += f"<br><a href='{google_search_url}' target='_blank'>Google Shopping Search</a>"

        rows.append({
            "Quantity": qty,
            "Cost": f"${unit_cost:,.2f}",
            "Description": desc,
            "Type": type_,
            "ATA Code": ata_code,
            "Correction": correction,
            "Cause": cause,
            "Items Total ($)": f"${Items_total:,.2f}",
            "Market Avg ($)": "N/A" if avg is None else f"${avg:,.2f}",
            "Allowed Unit Max ($)": "N/A" if avg is None else f"${allowed_unit_max:,.2f}",
            "Market Avg Total ($)": "N/A" if avg is None else f"${market_total:,.2f}",
            "Reference Links": ref_html,
            "Status": status,
            "Reason": reason
        })

    # --- Category 3: Grand total vs market check ---
    grand_total_flag = None
    if total_market_avg > 0:
        variance = total_bill - total_market_avg
        pct = (variance / total_market_avg) * 100
        if pct > 20:
            grand_total_flag = "Rejected ❌: Invoice total exceeds market average by more than 20%."
        elif pct > 10:
            grand_total_flag = "Caution ⚠️: Invoice total is 10–20% higher than market average. Please review."

    return rows, total_bill, total_market_avg, approved, caution, rejected, grand_total_flag

    return rows, total_bill, total_market_avg, approved, caution, rejected


# =========================
# STREAMLIT UI
# =========================
st.set_page_config(page_title="Fleet Repair Bill Verification (USA)", layout="wide")
st.title("🚚 Fleet Repair Bill Verification (USA)")

with st.expander("⚙️ Threshold Settings", expanded=True):
    avg_margin_pct = st.slider(
        "Allowed over Average (%)",
        min_value=0, max_value=50, value=10, step=1,
        help="Extra % allowed above the average market price."
    ) / 100.0
    st.caption(f"Effective **Allowed Unit Max** = Avg × (1 + {avg_margin_pct*100:.0f}%)")

st.subheader("🧾 Repair Invoice Entry")

st.markdown("""
#### Enter line items as per PO format:
""")

# Demo data for the Fill Demo Data button
DEMO_DATA = [
    {"Quantity": 2, "Cost": 93.12, "Description": "A/C RECIEVER - DRYER", "Type": "PART", "ATA Code": "01001065", "Correction": "REPLACE", "Cause": "DOES NOT OPERATE PROPERLY"},
    {"Quantity": 3, "Cost": 397.50, "Description": "A/C RECIEVER - DRYER", "Type": "LABOR", "ATA Code": "01001065", "Correction": "REPLACE", "Cause": "DOES NOT OPERATE PROPERLY"},
    {"Quantity": 2, "Cost": 265.00, "Description": "A/C REFRIGERANT, (PER LB)", "Type": "LABOR", "ATA Code": "01001273", "Correction": "REPLACE", "Cause": "MAINTENANCE"},
    {"Quantity": 1, "Cost": 100.00, "Description": "M.O.S.P.  MOBILE ONSITE SERVICE PREMIUM", "Type": "PM", "ATA Code": "1B008001", "Correction": "PREVENTIVE MAINT.", "Cause": "NOT SUPPLIED"},
    {"Quantity": 4, "Cost": 530.00, "Description": "REEFER COMPRESSOR", "Type": "LABOR", "ATA Code": "82002001", "Correction": "REPLACE", "Cause": "NOT SUPPLIED"},
    {"Quantity": 1, "Cost": 674.98, "Description": "REEFER COMPRESSOR", "Type": "PART", "ATA Code": "82002001", "Correction": "REPLACE", "Cause": "NOT SUPPLIED"},
    {"Quantity": 7, "Cost": 267.68, "Description": "A/C REFRIGERANT, (PER LB)", "Type": "PART", "ATA Code": "01001273", "Correction": "REPLACE", "Cause": "MAINTENANCE"}
]

num_parts = st.number_input("Number of Line Items", min_value=1, max_value=20, value=5, key="num_parts")

fill_demo = st.button("Fill Demo Data")
if fill_demo:
    for i, item in enumerate(DEMO_DATA):
        st.session_state[f"qty_{i}"] = item["Quantity"]
        st.session_state[f"cost_{i}"] = item["Cost"]
        st.session_state[f"desc_{i}"] = item["Description"]
        st.session_state[f"type_{i}"] = item["Type"]
        st.session_state[f"ata_{i}"] = item["ATA Code"]
        st.session_state[f"correction_{i}"] = item["Correction"]
        st.session_state[f"cause_{i}"] = item["Cause"]

num_parts = max(st.session_state.get("num_parts", 5), len(DEMO_DATA) if fill_demo else 5)

parts_input = []
header = st.columns([1, 1, 3, 1, 1, 2, 2])
header[0].markdown("**Quantity**")
header[1].markdown("**Cost ($)**")
header[2].markdown("**Description**")
header[3].markdown("**Type**")
header[4].markdown("**ATA Code**")
header[5].markdown("**Correction**")
header[6].markdown("**Cause**")

grand_total = 0.0
for i in range(st.session_state.get("num_parts", num_parts)):
    c1, c2, c3, c4, c5, c6, c7 = st.columns([1, 1, 3, 1, 1, 2, 2])
    qty = c1.number_input(f"Qty {i+1}", min_value=1, value=st.session_state.get(f"qty_{i}", 1), key=f"qty_{i}")
    cost = c2.number_input(f"Cost {i+1}", min_value=0.0, value=st.session_state.get(f"cost_{i}", 0.0), step=1.0, key=f"cost_{i}")
    desc = c3.text_input(f"Description {i+1}", value=st.session_state.get(f"desc_{i}", ""), key=f"desc_{i}")
    type_ = c4.text_input(f"Type {i+1}", value=st.session_state.get(f"type_{i}", ""), key=f"type_{i}")
    ata_code = c5.text_input(f"ATA Code {i+1}", value=st.session_state.get(f"ata_{i}", ""), key=f"ata_{i}")
    correction = c6.text_input(f"Correction {i+1}", value=st.session_state.get(f"correction_{i}", ""), key=f"correction_{i}")
    cause = c7.text_input(f"Cause {i+1}", value=st.session_state.get(f"cause_{i}", ""), key=f"cause_{i}")

    Items_total = qty * cost
    grand_total += Items_total

    if desc and cost > 0:
        parts_input.append({
            "Quantity": qty,
            "Cost": cost,
            "Description": desc,
            "Type": type_,
            "ATA Code": ata_code,
            "Correction": correction,
            "Cause": cause
        })

st.markdown(f"### 🧮 Grand Total: **${grand_total:,.2f}**")

submitted = st.button("🔍 Verify Bill")

if submitted and parts_input:
    rows, total_bill, total_market_avg, approved, caution, rejected, grand_total_flag = evaluate_items(
        parts_input, avg_margin_pct=avg_margin_pct
    )

    st.subheader("📊 Verification Results")
    default_columns = [
        "Quantity", "Cost", "Description", "Type", "ATA Code", "Correction", "Cause",
        "Items Total ($)", "Allowed Unit Max ($)", "Market Avg Total ($)", "Reference Links", "Status", "Reason"
    ]
    st.dataframe(
        [{**row, "Reference Links": row["Reference Links"]} for row in rows],
        use_container_width=True
    )

    for i, row in enumerate(rows):
        if row["Reference Links"]:
            st.markdown(f"**Line {i+1} Reference Links:**<br>{row['Reference Links']}", unsafe_allow_html=True)

    col1, col2, col3, col4, col5 = st.columns(5)
    col1.metric("Invoice Total ($)", f"{total_bill:,.2f}")

    if total_market_avg > 0:
        variance = total_bill - total_market_avg
        pct = (variance / total_market_avg) * 100
        if variance > 0:
            col2.metric(
                "Market Avg Total ($)",
                f"{total_market_avg:,.2f}",
                delta=f"{pct:+.1f}% vs market",
                delta_color="inverse"
            )
        else:
            col2.metric(
                "Market Avg Total ($)",
                f"{total_market_avg:,.2f}",
                delta=f"{pct:+.1f}% vs market",
                delta_color="normal"
            )
    else:
        col2.metric("Market Avg Total ($)", "N/A")

    col3.metric("Approved ✅", approved)
    col4.metric("Caution ⚠️", caution)
    col5.metric("Rejected ❌", rejected)

    if grand_total_flag:
        st.warning(grand_total_flag)

elif submitted:
    st.warning("Please fill at least one item with a valid Description and Cost.")
