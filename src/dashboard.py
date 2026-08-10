import math
import sys
from pathlib import Path

# Streamlit runs this file as a script, so project root must be on sys.path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import streamlit as st
import pandas as pd
import plotly.graph_objects as go
import plotly.express as px
import networkx as nx

from src.database import SessionLocal, init_db
from src.seed import seed_database
from src.models import User, Transaction, Connection
from src.score_service import (
    get_user_score_details,
    process_transaction,
    advance_simulated_time,
    get_risk_tier,
)
from src.graph_engine import (
    build_network_graph,
    detect_fraud_rings,
    get_fraud_penalty_for_user,
)
from src.decay_engine import calculate_decayed_score
from src.simulator import generate_synthetic_stream, inject_fraud_ring_attack

# Page Configuration
st.set_page_config(
    page_title="Trust Scoring & Fraud Ring Engine",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom Styling
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #3B82F6, #8B5CF6, #EC4899);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        color: #9CA3AF;
        font-size: 1.0rem;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #1F2937;
        border-radius: 8px;
        padding: 1rem;
        border: 1px solid #374151;
        text-align: center;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def get_db():
    init_db()
    return SessionLocal()


# Top Navigation / Title
st.markdown('<div class="main-title">🛡️ Dynamic Trust Score & Fraud-Ring Engine</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Exponential Time Decay • Graph Penalty Propagation • Real-time Risk Scoring</div>', unsafe_allow_html=True)

db = get_db()

# Sidebar Controls
st.sidebar.header("⚡ Quick Controls")
if st.sidebar.button("🔄 Reseed Database", use_container_width=True):
    seed_database()
    st.sidebar.success("Database reseeded!")
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("⏩ Fast-Forward Time")
col_t1, col_t2 = st.sidebar.columns(2)
if col_t1.button("+12 Hours"):
    advance_simulated_time(db, 12.0)
    st.rerun()
if col_t2.button("+7 Days"):
    advance_simulated_time(db, 168.0)
    st.rerun()

st.sidebar.markdown("---")
st.sidebar.subheader("🚨 Fraud Attack Simulator")
if st.sidebar.button("💥 Inject Fraud Ring Attack", use_container_width=True):
    res = inject_fraud_ring_attack(db)
    st.sidebar.warning(f"Injected synthetic bot: {res['created_user_id']}")
    st.rerun()


# Overview Metrics Bar
users = db.query(User).all()
txns = db.query(Transaction).all()
rings = detect_fraud_rings(db)
avg_score = sum(u.trust_score for u in users) / max(1, len(users))

m1, m2, m3, m4 = st.columns(4)
m1.metric("Total Users", len(users))
m2.metric("Avg System Trust", f"{avg_score:.1f} / 100")
m3.metric("Detected Fraud Rings", len(rings), delta=f"{len(rings)} Active" if rings else "0 Clean", delta_color="inverse")
m4.metric("Processed Transactions", len(txns))

st.markdown("---")

# Main Tabs
tab_overview, tab_decay, tab_graph, tab_simulator = st.tabs([
    "📊 System Overview & Risk Table",
    "📈 Time Decay Curve Inspector",
    "🕸️ Fraud-Ring Graph Visualizer",
    "⚙️ Transaction & Attack Simulator",
])

# ---------------------------------------------------------
# TAB 1: OVERVIEW & RISK TABLE
# ---------------------------------------------------------
with tab_overview:
    st.subheader("👥 Live User Risk Directory")

    user_rows = []
    for u in users:
        live_details = get_user_score_details(db, u.id)
        user_rows.append({
            "User ID": u.id,
            "Name": u.name,
            "Live Trust Score": live_details["current_live_score"],
            "Risk Tier": live_details["risk_tier"],
            "Graph Penalty": live_details["graph_penalty"],
            "Device ID": u.device_id or "N/A",
            "IP Address": u.ip_address or "N/A",
            "Last Updated": u.last_updated_at.strftime("%Y-%m-%d %H:%M:%S") if u.last_updated_at else "N/A",
        })

    df_users = pd.DataFrame(user_rows)
    
    st.dataframe(
        df_users,
        column_config={
            "Live Trust Score": st.column_config.ProgressColumn(
                "Live Trust Score",
                help="Current score recalculated with exponential decay and graph penalty",
                format="%.1f",
                min_value=0,
                max_value=100,
            ),
        },
        use_container_width=True,
        hide_index=True,
    )

    st.markdown("### 📜 Recent Transaction Activity Stream")
    recent_txns = db.query(Transaction).order_by(Transaction.timestamp.desc()).limit(10).all()
    if recent_txns:
        txn_data = []
        for t in recent_txns:
            u_name = next((u.name for u in users if u.id == t.user_id), t.user_id)
            txn_data.append({
                "Timestamp": t.timestamp.strftime("%Y-%m-%d %H:%M:%S"),
                "User": u_name,
                "Amount ($)": f"${t.amount:,.2f}",
                "Status": t.status,
                "Outcome Delta": f"{t.outcome_delta:+.1f}",
                "Post-Txn Score": t.applied_score,
            })
        st.dataframe(pd.DataFrame(txn_data), use_container_width=True, hide_index=True)
    else:
        st.info("No transaction history yet.")


# ---------------------------------------------------------
# TAB 2: DECAY CURVE INSPECTOR
# ---------------------------------------------------------
with tab_decay:
    st.subheader("📈 Exponential Time Decay Logic Inspector")
    st.write("Trust scores exponentially decay towards a baseline ($S_{baseline} = 50.0$) over time when inactive.")

    col_ctrl, col_chart = st.columns([1, 2])

    with col_ctrl:
        initial_score = st.slider("Initial Score ($S_0$)", 0.0, 100.0, 90.0, 1.0)
        baseline_score = st.slider("Baseline Score ($S_{baseline}$)", 0.0, 100.0, 50.0, 1.0)
        half_life = st.slider("Half-life (Hours)", 12.0, 168.0, 72.0, 6.0)
        penalty = st.slider("Graph Risk Penalty", 0.0, 40.0, 0.0, 1.0)

        st.latex(r"S(t) = S_{baseline} + (S_0 - S_{baseline}) \cdot e^{-\frac{\ln(2)}{t_{half}} \cdot t} - P_{graph}")

    with col_chart:
        hours = list(range(0, 337, 3))  # 0 to 14 days
        curve_scores = []
        for h in hours:
            score = calculate_decayed_score(
                current_score=initial_score,
                elapsed_hours=h,
                baseline_score=baseline_score,
                half_life_hours=half_life,
            )
            final_s = max(0.0, min(100.0, score - penalty))
            curve_scores.append(final_s)

        df_curve = pd.DataFrame({"Elapsed Hours": hours, "Elapsed Days": [h / 24.0 for h in hours], "Trust Score": curve_scores})

        fig = px.line(
            df_curve,
            x="Elapsed Days",
            y="Trust Score",
            title=f"Theoretical Trust Score Decay Curve over 14 Days",
            labels={"Elapsed Days": "Elapsed Time (Days)", "Trust Score": "Calculated Score"},
            markers=False,
        )
        fig.add_hline(y=baseline_score, line_dash="dash", line_color="gray", annotation_text="Baseline (50.0)")
        fig.update_yaxes(range=[0, 105])
        fig.update_layout(template="plotly_dark")
        st.plotly_chart(fig, use_container_width=True)


# ---------------------------------------------------------
# TAB 3: FRAUD-RING GRAPH VISUALIZER
# ---------------------------------------------------------
with tab_graph:
    st.subheader("🕸️ Network Topology & Fraud-Ring Detection")
    st.write("Accounts connected via **Shared Device**, **Shared IP**, or **Direct Transfers** propagate risk penalties.")

    G = build_network_graph(db)

    if G.number_of_nodes() > 0:
        pos = nx.spring_layout(G, seed=42, k=0.8)

        edge_x, edge_y = [], []
        edge_text = []

        for edge in G.edges(data=True):
            x0, y0 = pos[edge[0]]
            x1, y1 = pos[edge[1]]
            edge_x.extend([x0, x1, None])
            edge_y.extend([y0, y1, None])

        edge_trace = go.Scatter(
            x=edge_x, y=edge_y,
            line=dict(width=2, color='#6B7280'),
            hoverinfo='none',
            mode='lines'
        )

        node_x, node_y, node_color, node_text, node_size = [], [], [], [], []

        for node, attr in G.nodes(data=True):
            x, y = pos[node]
            node_x.append(x)
            node_y.append(y)
            score = attr["trust_score"]

            # Color coding
            if attr["is_fraud"]:
                color = '#EF4444'  # Red
                size = 35
            elif score >= 70:
                color = '#10B981'  # Green
                size = 25
            else:
                color = '#F59E0B'  # Yellow/Orange
                size = 25

            node_color.append(color)
            node_size.append(size)
            node_text.append(f"<b>{attr['name']}</b><br>ID: {node}<br>Score: {score}<br>Fraud: {attr['is_fraud']}")

        node_trace = go.Scatter(
            x=node_x, y=node_y,
            mode='markers+text',
            hoverinfo='text',
            text=[G.nodes[n]['name'].split()[0] for n in G.nodes()],
            textposition="top center",
            textfont=dict(color='white', size=12),
            hovertext=node_text,
            marker=dict(
                color=node_color,
                size=node_size,
                line_width=2,
                line_color='white',
            )
        )

        fig_g = go.Figure(
            data=[edge_trace, node_trace],
            layout=go.Layout(
                title="Interactive Connection Graph (Red = Flagged Fraud Node, Green = Trusted)",
                showlegend=False,
                hovermode='closest',
                margin=dict(b=20, l=5, r=5, t=40),
                xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                yaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
                template="plotly_dark",
            )
        )
        st.plotly_chart(fig_g, use_container_width=True)

    # Detected Rings Summary
    st.markdown("### 🚨 Detected Fraud Rings Detail")
    if rings:
        for r in rings:
            with st.expander(f"🔴 {r['ring_id']} — Risk Level: {r['risk_level']} ({r['size']} Connected Accounts)"):
                st.write(f"**Flagged Fraud Nodes:** {', '.join(r['fraud_nodes'])}")
                st.write(f"**Shared Devices:** {', '.join(r['shared_devices']) if r['shared_devices'] else 'None'}")
                st.write(f"**Shared IP Addresses:** {', '.join(r['shared_ips']) if r['shared_ips'] else 'None'}")
                st.dataframe(pd.DataFrame(r["nodes_detail"]), use_container_width=True, hide_index=True)
    else:
        st.success("No active fraud rings detected in current network graph.")


# ---------------------------------------------------------
# TAB 4: SIMULATOR & CONTROL PANEL
# ---------------------------------------------------------
with tab_simulator:
    st.subheader("⚙️ Execute Custom Transactions & Simulation Stream")

    col_form, col_sim = st.columns([1, 1])

    with col_form:
        st.markdown("### 💳 Submit Transaction")
        user_list = [u.id for u in users]
        sel_user = st.selectbox("Select User", user_list)
        txn_amount = st.number_input("Amount ($)", min_value=1.0, value=250.0, step=50.0)
        txn_status = st.selectbox("Transaction Status", ["SUCCESS", "SUSPICIOUS", "CHARGEBACK", "FAILED"])
        txn_device = st.text_input("Device ID (Optional)", value="")
        txn_ip = st.text_input("IP Address (Optional)", value="")

        if st.button("🚀 Process Transaction Event", use_container_width=True):
            res = process_transaction(
                db=db,
                user_id=sel_user,
                amount=txn_amount,
                status=txn_status,
                device_id=txn_device if txn_device else None,
                ip_address=txn_ip if txn_ip else None,
            )
            st.success(f"Processed! Verdict: **{res['verdict']}** | New Score: **{res['new_trust_score']}**")
            st.rerun()

    with col_sim:
        st.markdown("### 🎲 Batch Synthetic Generator")
        num_sim_txns = st.slider("Number of Random Transactions", 1, 20, 5)
        inject_fraud_flag = st.checkbox("Include Fraud/Chargebacks", value=True)

        if st.button("▶️ Run Synthetic Transaction Stream", use_container_width=True):
            logs = generate_synthetic_stream(db, num_events=num_sim_txns, inject_fraud=inject_fraud_flag)
            st.success(f"Generated and processed {len(logs)} synthetic transaction events!")
            st.json(logs[:3])
            st.rerun()

db.close()
