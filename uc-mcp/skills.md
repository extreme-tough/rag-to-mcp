skills:
  - name: query_policy_documents
    description: >
      Call the underlying CMC policy RAG server for questions about the City Municipal Corporation HR Leave Policy, IT Acceptable Use Policy, and Finance Reimbursement Policy only. The tool must remain within the described document scope and must never answer questions outside those three policy sources.
    input: >
      A question object with a required non-empty string field named question representing a staff policy inquiry about the CMC HR Leave Policy, IT Acceptable Use Policy, or Finance Reimbursement Policy.
    output: >
      A tool result containing the answer text and cited sources when the question is in scope, or a structured error payload when the question is out of scope or the underlying RAG server refuses the request.
    error_handling: >
      If the question is outside the three policy documents, return a refusal response with isError: true and explain that the question is outside scope. If the RAG server returns refused=True, return error content with isError: true and the refusal message rather than empty content. If the input is missing, blank, or not a string, reject the request before invoking the RAG layer. If the tool call fails internally, return a structured JSON-RPC error and never return an empty content array. Validate the tool description and input schema so the tool remains scoped to the CMC HR Leave Policy, IT Acceptable Use Policy, and Finance Reimbursement Policy only.

  - name: serve_mcp
    description: >
      Start a plain HTTP JSON-RPC MCP server on a configurable port, expose the tools/list and tools/call handlers, and return standards-compliant JSON-RPC responses for all calls including application errors.
    input: >
      A port number and incoming HTTP JSON-RPC request payloads for tools/list or tools/call. The tool must accept standard JSON-RPC requests and return valid JSON-RPC responses.
    output: >
      A JSON-RPC response containing either the list of available tools or the result of a tool invocation, plus structured error objects for unsupported methods or invalid requests.
    error_handling: >
      If an unknown method is requested, return JSON-RPC error -32601 Method not found. If a tool argument is invalid or missing, return an error object with isError: true instead of an empty or partial result. Ensure the server responds with HTTP 200 for all JSON-RPC responses including errors; transport-level failures should use HTTP 4xx/5xx only at the network layer. Never silently drop errors or return empty content arrays; every failure must be explicit and machine-readable.