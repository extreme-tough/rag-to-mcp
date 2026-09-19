"""
UC-MCP — mcp_server.py
Plain HTTP MCP Server — Starter File

Build this using your AI coding tool:
1. Share agents.md, skills.md, and uc-mcp/README.md with your AI tool
2. Ask it to implement this file following the MCP protocol
   described in the README
3. Run with: python3 mcp_server.py --port 8765
4. Test with: python3 test_client.py --port 8765

Protocol: JSON-RPC 2.0 over HTTP POST
No external dependencies beyond Python stdlib.

Methods to implement:
  tools/list  — return the tool definition for query_policy_documents
  tools/call  — execute query_policy_documents, return JSON-RPC response
"""

import json
import argparse
import sys
import os
from http.server import HTTPServer, BaseHTTPRequestHandler

# Import RAG — uses stub by default, swap to rag_server once yours works
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "../uc-rag"))
try:
    # Try participant's rag_server first
    from rag_server import query as rag_query
    from rag_server import warmup as rag_warmup
    print("[mcp_server] Using participant rag_server.py")
except (ImportError, NotImplementedError):
    # Fall back to stub
    from stub_rag import query as rag_query
    rag_warmup = None
    print("[mcp_server] Using stub_rag.py (fallback)")

# Import LLM adapter
from llm_adapter import call_llm


# ── TOOL DEFINITION ──────────────────────────────────────────────────────────
# This is what the agent reads to decide when to call your tool.
# The description IS the enforcement — make it specific.
TOOL_DEFINITION = {
    "name": "query_policy_documents",
    "description": (
        "Answers questions about CMC HR Leave Policy, IT Acceptable Use Policy, "
        "and Finance Reimbursement Policy ONLY. Returns cited answers grounded in "
        "retrieved document chunks. Returns a refusal for questions outside these "
        "three documents. Do not send budget, procurement, or general policy "
        "questions to this tool."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "question": {
                "type": "string",
                "description": "The policy question to answer",
            }
        },
        "required": ["question"],
    },
}


# ── SKILL: query_policy_documents ────────────────────────────────────────────
def query_policy_documents(question: str) -> dict:
    """
    Call the RAG server with the question.
    Return MCP content format: {"content": [...], "isError": bool}

    Error handling:
    - If RAG refuses (no chunks above threshold) → isError: True
    - If RAG raises exception → isError: True with error message
    """
    if not isinstance(question, str) or not question.strip():
        return {
            "content": [{"type": "text", "text": "Question must be a non-empty string."}],
            "isError": True,
        }

    try:
        result = rag_query(question, llm_call=call_llm)
    except Exception as exc:
        return {
            "content": [{"type": "text", "text": f"Error: {exc}"}],
            "isError": True,
        }

    answer = result.get("answer", "") or "No answer available."
    return {
        "content": [{"type": "text", "text": answer}],
        "isError": bool(result.get("refused", False)),
    }


# ── SKILL: serve_mcp ─────────────────────────────────────────────────────────
class MCPHandler(BaseHTTPRequestHandler):
    """
    HTTP request handler implementing JSON-RPC 2.0.
    Handles POST requests to / with JSON-RPC body.

    Implement:
    - tools/list  → return TOOL_DEFINITION
    - tools/call  → call query_policy_documents, return result
    - unknown methods → JSON-RPC error -32601
    """

    def do_POST(self):
        try:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length) if length > 0 else b"{}"
            body = raw.decode("utf-8", errors="replace")
            try:
                request = json.loads(body)
            except json.JSONDecodeError:
                response = {
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {"code": -32700, "message": "Parse error"},
                }
                self._send_json(response)
                return

            request_id = request.get("id")
            method = request.get("method")

            if method == "tools/list":
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": {"tools": [TOOL_DEFINITION]},
                }
                self._send_json(response)
                return

            if method == "tools/call":
                params = request.get("params", {})
                if not isinstance(params, dict):
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32602, "message": "Invalid params"},
                    }
                    self._send_json(response)
                    return

                tool_name = params.get("name")
                arguments = params.get("arguments", {})
                if tool_name != "query_policy_documents" or not isinstance(arguments, dict):
                    response = {
                        "jsonrpc": "2.0",
                        "id": request_id,
                        "error": {"code": -32602, "message": "Invalid tool name or arguments"},
                    }
                    self._send_json(response)
                    return

                result = query_policy_documents(arguments.get("question", ""))
                response = {
                    "jsonrpc": "2.0",
                    "id": request_id,
                    "result": result,
                }
                self._send_json(response)
                return

            response = {
                "jsonrpc": "2.0",
                "id": request_id,
                "error": {"code": -32601, "message": "Method not found"},
            }
            self._send_json(response)
        except Exception as exc:  # pragma: no cover - defensive fallback
            response = {
                "jsonrpc": "2.0",
                "id": None,
                "error": {"code": -32603, "message": f"Internal error: {exc}"},
            }
            self._send_json(response)

    def _send_json(self, payload):
        body = json.dumps(payload).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format, *args):
        # Suppress default HTTP logging — use print for clarity
        print(f"[mcp_server] {args[0]} {args[1]}")


# ── MAIN ─────────────────────────────────────────────────────────────────────
def main():
    parser = argparse.ArgumentParser(description="UC-MCP Plain HTTP MCP Server")
    parser.add_argument("--port", type=int, default=8765,
                        help="Port to listen on (default: 8765)")
    args = parser.parse_args()

    # Verify RAG index exists
    db_path = os.path.join(os.path.dirname(__file__), "../uc-rag/stub_chroma_db")
    if not os.path.exists(db_path):
        print("[mcp_server] WARNING: RAG index not found.")
        print("[mcp_server] Run first: python3 ../uc-rag/stub_rag.py --build-index")
        print("[mcp_server] Starting anyway — queries will fail until index is built.")

    # Warm up RAG (loads embedder + collection once) so requests stay fast
    if rag_warmup is not None:
        try:
            print("[mcp_server] Warming up RAG (loads embedder once)...")
            rag_warmup()
        except Exception as exc:
            print(f"[mcp_server] WARNING: RAG warmup failed ({exc}). Queries may fail.")

    server = HTTPServer(("localhost", args.port), MCPHandler)
    print(f"[mcp_server] MCP server running on http://localhost:{args.port}")
    print(f"[mcp_server] Test with: python3 test_client.py --port {args.port}")
    print(f"[mcp_server] Press Ctrl+C to stop.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n[mcp_server] Stopped.")


if __name__ == "__main__":
    main()
