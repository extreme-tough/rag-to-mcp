role: >
  MCP tool agent for the City Municipal Corporation policy assistant. It exposes a single tool that answers questions only from the CMC HR Leave Policy, IT Acceptable Use Policy, and Finance Reimbursement Policy.

intent: >
  Answer only questions that are in scope for the three CMC policy documents, enforce tool description and input constraints, and return refusal-style errors for questions outside that scope without wasting calls or inventing unsupported answers.

context: >
  The agent operates as a JSON-RPC MCP server over HTTP and must expose one tool named query_policy_documents. It receives a question string, calls the underlying RAG server, and returns structured tool results. The tool description is the enforcement boundary: the agent must stay within the CMC HR Leave Policy, IT Acceptable Use Policy, and Finance Reimbursement Policy, and must not answer questions outside those documents.

enforcement: >
  - "Tool description must state the exact document scope: CMC HR Leave Policy, IT Acceptable Use Policy, and Finance Reimbursement Policy."
  - "Tool description must state what it cannot answer: questions outside these three documents return the refusal template."
  - "inputSchema must require question as a non-empty string."
  - "Error responses must use isError: true — never return an empty content array on failure."
  - "The server must return HTTP 200 for all JSON-RPC responses including errors; transport errors use HTTP 4xx/5xx, application errors use JSON-RPC error objects."
  - "The server must expose only the query_policy_documents tool through tools/list and must handle unknown methods with JSON-RPC error -32601."
  - "If the tool is called with a question outside scope, it must refuse with an explicit error result rather than pretending to answer."
  - "If the underlying RAG server returns refused=True, the MCP tool must return error content with isError: true and the refusal message."
  - "Responses must remain grounded to the three in-scope policy documents and must not answer budget forecasts or other out-of-scope questions using general knowledge."
  - "Any JSON-RPC application error must be returned as a structured JSON-RPC error object, not as a silent empty payload."