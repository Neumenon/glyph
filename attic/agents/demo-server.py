#!/usr/bin/env python3
"""
GLYPH Demo Server - showcase UI backed by real demo execution.

Serves:
- the new agent control room showcase
- the legacy oracle demo
- JSON APIs for both surfaces
"""

import json
import hashlib
from http.server import HTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlparse, parse_qs
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
PY_DIR = ROOT / "py"
if str(PY_DIR) not in sys.path:
    sys.path.insert(0, str(PY_DIR))

# Import demo components
from glyph.loose import json_to_glyph, fingerprint_loose, from_json_loose
from agent_showcase import build_showcase_payload

# ============================================================================
# DEMO DATA GENERATION
# ============================================================================

def generate_turn_1():
    """Turn 1: Knowledge Base Search"""
    kb_articles = [
        {"id": "kb_001", "title": "Refund Policy 2025", "relevance": 0.98, "snippet": "30-day full refunds"},
        {"id": "kb_002", "title": "Defective Item Replacement", "relevance": 0.95, "snippet": "Free shipping both ways"},
        {"id": "kb_003", "title": "Shipping Delays", "relevance": 0.92, "snippet": "If delayed >5 days, full refund"},
    ]
    
    # JSON format
    json_data = {
        "query": "refund policy damaged item",
        "results": kb_articles
    }
    json_str = json.dumps(json_data)
    
    # GLYPH format
    glyph_str = json_to_glyph(json_data)
    
    # State data
    state_data = {
        "conversation_id": "conv_2025_001",
        "customer_id": "cust_789",
        "issue": "Damaged item received - electronics",
        "turns": [
            {
                "num": 1,
                "user": "My TV arrived damaged. What's your refund policy?",
                "thought": "User has damaged item. Need to search refund policy.",
                "tools": ["search_knowledge_base"],
                "results": kb_articles,
                "time": "2025-01-20T10:30:00Z"
            }
        ],
        "step": 1,
        "refund_ok": False,
        "amount": 0
    }
    
    json_state = json.dumps(state_data)
    glyph_state = json_to_glyph(state_data)
    
    return {
        "turn": 1,
        "title": "Research Policy",
        "user_input": "My TV arrived damaged. What's your refund policy?",
        "agent_thought": "User has damaged item. Need to search refund policy and assess eligibility.",
        "kb_json": json_str,
        "kb_glyph": glyph_str,
        "kb_json_chars": len(json_str),
        "kb_glyph_chars": len(glyph_str),
        "kb_savings": 100 * (1 - len(glyph_str) / len(json_str)),
        "state_json": json_state,
        "state_glyph": glyph_state,
        "state_json_chars": len(json_state),
        "state_glyph_chars": len(glyph_state),
        "state_savings": 100 * (1 - len(glyph_state) / len(json_state)),
        "state_hash": hashlib.sha256(glyph_state.encode()).hexdigest()[:16],
    }

def generate_turn_2():
    """Turn 2: Fetch History & Validate"""
    orders = [
        {"order_id": "ORD_2025_001", "date": "2025-01-15", "amount_cents": 5999, "status": "delivered", "issue": "item_damaged"},
        {"order_id": "ORD_2025_002", "date": "2024-12-20", "amount_cents": 2499, "status": "delivered", "issue": "none"},
    ]
    
    history_data = {
        "customer_id": "cust_789",
        "lifetime_value_cents": 84980,
        "account_age_days": 487,
        "orders": orders
    }
    
    json_history = json.dumps(history_data)
    glyph_history = json_to_glyph(history_data)
    
    # Full state
    state_data = {
        "conversation_id": "conv_2025_001",
        "customer_id": "cust_789",
        "issue": "Damaged item received - electronics",
        "turns": [
            {
                "num": 1,
                "user": "My TV arrived damaged. What's your refund policy?",
                "thought": "User has damaged item. Need to search refund policy.",
                "tools": ["search_knowledge_base"],
                "results": ["kb_001", "kb_002", "kb_003"],
                "time": "2025-01-20T10:30:00Z"
            },
            {
                "num": 2,
                "user": "Please look up my account and process the refund.",
                "thought": "Customer is eligible. Fetch history to confirm order exists.",
                "tools": ["fetch_customer_history", "process_refund"],
                "results": ["history_fetched", "refund_processed"],
                "time": "2025-01-20T10:35:00Z"
            }
        ],
        "step": 2,
        "refund_ok": True,
        "amount": 5999
    }
    
    json_state = json.dumps(state_data)
    glyph_state = json_to_glyph(state_data)
    
    return {
        "turn": 2,
        "title": "Fetch & Validate",
        "user_input": "Please look up my account and process the refund.",
        "agent_thought": "Customer is eligible. Fetch history to confirm order exists.",
        "history_json": json_history,
        "history_glyph": glyph_history,
        "history_json_chars": len(json_history),
        "history_glyph_chars": len(glyph_history),
        "validation_result": "✓ Tool detected at token 15, Valid tool 'process_refund'",
        "state_json": json_state,
        "state_glyph": glyph_state,
        "state_json_chars": len(json_state),
        "state_glyph_chars": len(glyph_state),
        "state_savings": 100 * (1 - len(glyph_state) / len(json_state)),
        "state_hash": hashlib.sha256(glyph_state.encode()).hexdigest()[:16],
        "streaming_detection": {
            "tool_name": "process_refund",
            "detected_at_token": 15,
            "tokens_to_reject_unknown": 3,
            "savings_percent": 94
        }
    }

def generate_turn_3():
    """Turn 3: Incremental Patching"""
    state_data = {
        "conversation_id": "conv_2025_001",
        "customer_id": "cust_789",
        "issue": "Damaged item received - electronics",
        "turns": [
            {
                "num": 1,
                "user": "My TV arrived damaged. What's your refund policy?",
                "thought": "User has damaged item.",
                "tools": ["search_knowledge_base"],
                "results": ["kb_001"],
                "time": "2025-01-20T10:30:00Z"
            },
            {
                "num": 2,
                "user": "Please look up my account and process the refund.",
                "thought": "Customer is eligible.",
                "tools": ["fetch_customer_history", "process_refund"],
                "results": ["history_fetched", "refund_processed"],
                "time": "2025-01-20T10:35:00Z"
            },
            {
                "num": 3,
                "user": "Thank you! When will I get my refund?",
                "thought": "Customer asking about timeline. Check refund status.",
                "tools": ["get_refund_status"],
                "results": ["status_retrieved"],
                "time": "2025-01-20T10:40:00Z"
            }
        ],
        "step": 3,
        "refund_ok": True,
        "amount": 5999,
        "refund_sent": True
    }
    
    json_full = json.dumps(state_data)
    glyph_full = json_to_glyph(state_data)
    
    patch_data = """@patch base=78bc1460e64bcff5
turns+{num=3 user="Thank you..." tools=[get_refund_status] results=[status_retrieved]}
current_step~1
refund_sent=t"""
    
    return {
        "turn": 3,
        "title": "Incremental Patching",
        "patch_format": patch_data,
        "full_resync_json": json_full,
        "full_resync_glyph": glyph_full,
        "full_json_chars": len(json_full),
        "full_glyph_chars": len(glyph_full),
        "patch_chars": len(patch_data),
        "patch_savings": 100 * (1 - len(patch_data) / len(json_full)),
        "state_hash_turn2": "78bc1460e64bcff5",
        "state_hash_turn3": hashlib.sha256(glyph_full.encode()).hexdigest()[:16],
        "verification": "Hash mismatch → automatic resync triggered"
    }

# ============================================================================
# HTTP HANDLERS
# ============================================================================

class DemoHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        parsed = urlparse(self.path)
        
        # API endpoint for demo data
        if parsed.path == "/api/demo":
            query = parse_qs(parsed.query)
            turn = int(query.get('turn', ['1'])[0])
            
            if turn == 1:
                data = generate_turn_1()
            elif turn == 2:
                data = generate_turn_2()
            elif turn == 3:
                data = generate_turn_3()
            else:
                data = {"error": "Invalid turn"}
            
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.end_headers()
            self.wfile.write(json.dumps(data).encode())
            return

        if parsed.path == "/api/agent-showcase":
            query = parse_qs(parsed.query)
            config = _config_from_query(query)
            data = build_showcase_payload(config)
            self._write_json(200, data)
            return
        
        # Serve static files
        if parsed.path == '/' or parsed.path == '':
            self.path = '/agent-showcase.html'
        elif parsed.path == '/legacy':
            self.path = '/demo-ui.html'
        
        try:
            return super().do_GET()
        except Exception:
            self.send_response(404)
            self.end_headers()

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path != "/api/agent-showcase":
            self.send_response(404)
            self.end_headers()
            return

        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError as exc:
            self._write_json(400, {"error": f"Invalid JSON body: {exc}"})
            return

        payload = build_showcase_payload(data if isinstance(data, dict) else {})
        self._write_json(200, payload)
    
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def log_message(self, format, *args):
        """Suppress default logging"""
        pass

    def _write_json(self, status: int, payload: dict):
        self.send_response(status)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(payload).encode())


def _config_from_query(query: dict[str, list[str]]) -> dict:
    def first(name: str, default: str) -> str:
        return query.get(name, [default])[0]

    return {
        "task": first("task", ""),
        "max_rounds": first("max_rounds", "1"),
        "arbitration_mode": first("arbitration_mode", "majority"),
        "require_consensus": first("require_consensus", "false").lower() == "true",
        "min_confidence": first("min_confidence", "0.6"),
        "enable_tools": first("enable_tools", "true").lower() == "true",
        "include_arbiter": first("include_arbiter", "true").lower() == "true",
    }

# ============================================================================
# SERVER
# ============================================================================

if __name__ == '__main__':
    port = 9999
    server = HTTPServer(('localhost', port), DemoHandler)
    
    print()
    print("█" * 80)
    print("  GLYPH Demo Server")
    print("█" * 80)
    print()
    print(f"  ✓ Server running at: http://localhost:{port}")
    print(f"  ✓ Open in browser:   http://localhost:{port}/")
    print(f"  ✓ Legacy demo:       http://localhost:{port}/legacy")
    print()
    print(f"  API Endpoints:")
    print(f"    • http://localhost:{port}/api/agent-showcase")
    print(f"    • http://localhost:{port}/api/demo?turn=1")
    print(f"    • http://localhost:{port}/api/demo?turn=2")
    print(f"    • http://localhost:{port}/api/demo?turn=3")
    print()
    print("  Press Ctrl+C to stop server")
    print()
    print("█" * 80)
    print()
    
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n  Server stopped.")
        sys.exit(0)
