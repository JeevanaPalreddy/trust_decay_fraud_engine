from typing import Dict, Any, List
import networkx as nx
from sqlalchemy.orm import Session
from src.models import User, Connection


def build_network_graph(db: Session) -> nx.Graph:
    """
    Builds a NetworkX graph of users and connection edges from DB.
    """
    G = nx.Graph()

    # Add all users as nodes
    users = db.query(User).all()
    for u in users:
        is_fraud = u.trust_score < 30.0
        G.add_node(
            u.id,
            name=u.name,
            email=u.email,
            trust_score=round(u.trust_score, 2),
            device_id=u.device_id,
            ip_address=u.ip_address,
            is_fraud=is_fraud,
        )

    # Add explicit connection edges
    connections = db.query(Connection).all()
    for c in connections:
        if G.has_node(c.source_user_id) and G.has_node(c.target_user_id):
            G.add_edge(
                c.source_user_id,
                c.target_user_id,
                connection_type=c.connection_type,
                weight=c.weight,
            )

    return G


def get_fraud_penalty_for_user(db: Session, user_id: str, attenuation: float = 0.2) -> float:
    """
    Calculates negative trust penalty propagation based on graph distance to fraud nodes.
    Penalty = sum( (100 - fraud_score) * attenuation / (distance ^ 2) ) for all fraud nodes.
    """
    G = build_network_graph(db)

    if not G.has_node(user_id):
        return 0.0

    # If the user itself is already a fraud node, no external propagation penalty added
    if G.nodes[user_id].get("is_fraud", False):
        return 0.0

    fraud_nodes = [node for node, attr in G.nodes(data=True) if attr.get("is_fraud", False)]
    total_penalty = 0.0

    for f_node in fraud_nodes:
        if f_node == user_id:
            continue
        try:
            distance = nx.shortest_path_length(G, source=f_node, target=user_id)
            if distance > 0:
                f_score = G.nodes[f_node]["trust_score"]
                severity = max(10.0, 100.0 - f_score)
                penalty = (severity * attenuation) / (distance ** 2)
                total_penalty += penalty
        except nx.NetworkXNoPath:
            continue

    return round(min(50.0, total_penalty), 2)


def detect_fraud_rings(db: Session) -> List[Dict[str, Any]]:
    """
    Detects subgraphs (connected components) that contain at least one flagged fraud node.
    """
    G = build_network_graph(db)
    components = list(nx.connected_components(G))

    rings = []
    ring_counter = 1

    for comp in components:
        comp_nodes = list(comp)
        fraud_nodes = [n for n in comp_nodes if G.nodes[n].get("is_fraud", False)]

        if fraud_nodes:
            # We found a fraud ring!
            ring_nodes_detail = []
            shared_devices = set()
            shared_ips = set()

            for n in comp_nodes:
                n_data = G.nodes[n]
                ring_nodes_detail.append({
                    "id": n,
                    "name": n_data["name"],
                    "trust_score": n_data["trust_score"],
                    "is_fraud": n_data["is_fraud"],
                })
                if n_data.get("device_id"):
                    shared_devices.add(n_data["device_id"])
                if n_data.get("ip_address"):
                    shared_ips.add(n_data["ip_address"])

            risk_level = "CRITICAL" if len(fraud_nodes) > 1 or len(comp_nodes) >= 3 else "HIGH"

            rings.append({
                "ring_id": f"RING-{ring_counter:03d}",
                "size": len(comp_nodes),
                "fraud_node_count": len(fraud_nodes),
                "fraud_nodes": fraud_nodes,
                "member_nodes": comp_nodes,
                "nodes_detail": ring_nodes_detail,
                "risk_level": risk_level,
                "shared_devices": list(shared_devices),
                "shared_ips": list(shared_ips),
            })
            ring_counter += 1

    return rings


def get_fraud_ring_for_user(db: Session, user_id: str) -> Dict[str, Any]:
    """
    Gets detailed fraud ring & neighbor graph topology for a specific user.
    """
    G = build_network_graph(db)
    if not G.has_node(user_id):
        return {"user_id": user_id, "in_fraud_ring": False, "neighbors": []}

    neighbors = list(G.neighbors(user_id))
    neighbor_details = []
    for n in neighbors:
        edge_data = G.get_edge_data(user_id, n) or {}
        n_data = G.nodes[n]
        neighbor_details.append({
            "user_id": n,
            "name": n_data["name"],
            "trust_score": n_data["trust_score"],
            "is_fraud": n_data["is_fraud"],
            "connection_type": edge_data.get("connection_type", "UNKNOWN"),
        })

    penalty = get_fraud_penalty_for_user(db, user_id)
    rings = detect_fraud_rings(db)
    user_ring = next((r for r in rings if user_id in r["member_nodes"]), None)

    return {
        "user_id": user_id,
        "trust_score": G.nodes[user_id]["trust_score"],
        "in_fraud_ring": user_ring is not None,
        "ring_id": user_ring["ring_id"] if user_ring else None,
        "ring_risk_level": user_ring["risk_level"] if user_ring else "NORMAL",
        "propagated_penalty": penalty,
        "neighbors": neighbor_details,
    }
