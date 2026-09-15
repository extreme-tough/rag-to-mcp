skills:
  - name: chunk_documents
    description: >
      Load policy documents from the policy-documents directory, split them into
      sentence-aware chunks no larger than 400 tokens, and return each chunk with
      metadata for document name, chunk index, and text.
    input: >
      Path to the policy-documents directory containing the HR, IT, and Finance
      policy text files.
    output: >
      A list of chunk dictionaries, each containing doc_name, chunk_index, and
      text, with chunk boundaries preserved at sentence ends.
    error_handling: >
      If a policy file is missing, unreadable, or cannot be parsed, skip that file,
      log the issue, and continue processing the remaining documents. This prevents
      chunk boundary failures and ensures the pipeline does not silently split a
      clause across sentence boundaries or drop valid policy content, including the
      HR leave-without-pay approval sentence in section 5.2.

  - name: retrieve_and_answer
    description: >
      Embed the user query with sentence-transformers, retrieve the top three
      relevant chunks from ChromaDB, filter out low-scoring matches below 0.6,
      answer using retrieved context only, and return the answer with cited chunk
      sources.
    input: >
      A query string representing a city staff question about HR, IT, or Finance
      policy.
    output: >
      An answer string plus a list of cited chunk references, each including the
      source document name and chunk index.
    error_handling: >
      If no retrieved chunk scores above 0.6, return the refusal template exactly:
      'This question is not covered in the retrieved policy documents. Retrieved
      chunks: [list chunk sources]. Please contact the relevant department for
      guidance.' Never generate an answer from general knowledge. If the query
      spans multiple documents, retrieve from each separately and do not merge
      chunks from different documents into a single answer. Never add information
      not present in the retrieved chunks; this prevents wrong retrieval and answer
      grounding failures. For the leave-without-pay question, the retrieved context
      must include the HR policy sentence naming both Department Head and HR
      Director as required approvers.
