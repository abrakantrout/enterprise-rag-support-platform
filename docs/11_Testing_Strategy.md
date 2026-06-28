# Testing Strategy Specification

| Attribute | Details |
| :--- | :--- |
| **Project Name** | Enterprise AI Knowledge Platform with Intelligent Customer Support (RAG) |
| **Document Name** | Testing Strategy Specification |
| **Version** | v1.0.0 (Baseline Approved) |
| **Document Status** | Approved |
| **Owner** | Senior QA Engineer & Software Test Architect |
| **Last Updated** | 2026-06-27 |

### Document Purpose
This Testing Strategy Specification defines the testing methods, evaluation criteria, failure scenarios, and validation checklists for the *Enterprise AI Knowledge Platform*. It establishes a practical, developer-focused testing framework for Version 1, detailing unit testing, integration checkpoints, API testing, UI validation, and RAG grounding evaluations that can be executed by a single developer.

---

## 1. Testing Philosophy

For a project built and maintained by a single developer, the testing philosophy must balance code quality with development velocity. Over-engineering test suites with complex automation frameworks can consume too much time, while neglecting testing leads to regressions, hallucinations, and system failures.

Our testing approach is built on a set of core principles:
*   **Test Early, Test Often:** Integrate testing into the daily development cycle. Catching logic bugs during code drafting is significantly faster than debugging them in production.
*   **Automate Where Practical:** Write automated unit tests for core backend functions (such as chunking logic, citation extraction, and access filters) where outcomes are predictable and repetitive.
*   **Manual Testing Where Appropriate:** Rely on manual testing for visual UI changes, responsive layout verifications, and complex user flows where coding automated tests would introduce excessive overhead.
*   **Practical RAG Evaluation:** Establish manual, query-based evaluation sets to verify that responses are grounded and citations are correct, rather than setting up complex, automated AI assessment models.

---

## 2. Testing Levels

The platform's testing framework is divided into five core levels:

```
┌────────────────────────────────────────────────────────┐
│                      Unit Testing                      │
│  - Validate text chunkers, role filters, and helpers.  │
├────────────────────────────────────────────────────────┤
│                   Integration Testing                  │
│  - Verify DB writes, vector searches, and API routes.  │
├────────────────────────────────────────────────────────┤
│                      System Testing                    │
│  - Test end-to-end user journeys in staging.           │
├────────────────────────────────────────────────────────┤
│                     Manual QA Checkups                 │
│  - Verify UI layouts, forms, and responsive elements.  │
├────────────────────────────────────────────────────────┤
│                     RAG Grounding Evaluator            │
│  - Test responses against grounding and citation sets. │
└────────────────────────────────────────────────────────┘
```

*   **Unit Testing:** Focuses on isolating and testing individual functions (e.g., verifying that the recursive character splitter breaks paragraphs at the correct separators).
*   **Integration Testing:** Verifies communication between modules and databases (e.g., confirming a successful document ingestion writes metadata to PostgreSQL and inserts vector indexes into ChromaDB).
*   **System Testing:** Tests complete, end-to-end user journeys (e.g. uploading a document, querying the assistant as a customer, and verifying that the answer matches the uploaded context).
*   **Manual Testing:** Visual and functional verification of user interfaces, input validation forms, responsive break-points, and error screens.
*   **RAG Evaluation:** Query-based validation tests to verify that generated answers are grounded, citations are accurate, and fallback behaviors function correctly.

---

## 3. Module-Wise Testing Specifications

This section specifies what to test, expected outcomes, and failure scenarios for each core application module.

| Module Name | What to Test | Expected Outcome | Failure Scenarios to Validate |
| :--- | :--- | :--- | :--- |
| **Authentication** | Login, JWT creation, token refresh, role authorization, and logout. | Credentials verify, JWTs issue and refresh, and roles restrict access. | * Invalid passwords return 401.<br>* Expired tokens are rejected.<br>* Support agents are blocked from admin routes. |
| **Document Upload** | Size validation, file type validation, and upload status changes. | Files under 25MB upload, database metadata logs, and progress indicators update. | * Files exceeding 25MB are blocked.<br>* Unsupported formats (e.g. .exe) return 400. |
| **PDF Processing** | Text extraction, layout parsing, and table formatting. | Raw text extracts cleanly and tables format into Markdown grids. | * Password-locked PDFs fail gracefully.<br>* Scanned PDFs return clear warnings. |
| **Chunking** | Splitting text with size limits and overlaps. | Text splits at separators (paragraphs, sentences) within target boundaries. | * Oversized chunks do not crash the pipeline.<br>* Structural layouts (like lists) are preserved. |
| **Embeddings** | Converting chunks to vectors using the embedding API. | Text translates into 768-dimensional numerical vector arrays. | * Upstream timeouts retry using backoff.<br>* Empty string chunks are skipped. |
| **Vector DB** | Writing embeddings to collections and performing searches. | Vectors insert, retrieve, and filter using metadata tags. | * ChromaDB connection losses handle gracefully.<br>* Deleted documents are purged from vector search. |
| **Chat API** | Query submissions, history tracking, and response streaming. | Sessions initialize, queries retrieve context, and text streams via SSE. | * Inactive sessions return 404.<br>* Similarity scores below threshold return fallbacks. |
| **Dashboard** | Metric calculations, data grids, and report exports. | Token costs calculate, deflection metrics update, and CSV files download. | * Missing query logs do not break metrics.<br>* Large history logs render without crashing. |
| **Feedback** | Log rating scores and review comment records. | Feedback links to messages and logs ratings and comments in PostgreSQL. | * Duplicate ratings are ignored.<br>* Invalid message IDs return validation errors. |
| **Frontend** | Renders components, captures inputs, and displays citations. | UI displays messages, opens citation cards, and scales layouts. | * Inputs are blocked during query streaming.<br>* Network timeouts display friendly alerts. |

---

## 4. RAG Evaluation Strategy

Evaluating a RAG engine requires assessing both the retrieval step (did the system find the right information?) and the generation step (did the LLM synthesize a correct, grounded response?).

To evaluate the RAG engine, the developer maintains a local **Gold Standard Evaluation Set** containing 20 to 30 test questions. This evaluation set is used to run query checks and evaluate responses against six core questions:

```
                  [ RAG Grounding Evaluation Checks ]
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
 [Correct Answer?]        [Correct Citation?]       [Zero Hallucination?]
(Verified by context)   (Links to exact page)      (No external facts)
         │                         │                         │
         ├─────────────────────────┼─────────────────────────┤
         ▼                         ▼                         ▼
[Correct Retrieval?]     [Reasonable Latency?]     [Safe Fallback?]
(Top-K holds details)   (Response under 5s-8s)   (Unknown query declined)
```

1.  **Correct Answer?** Does the generated response address the query based on the retrieved context?
2.  **Correct Citation?** Do the inline citation tags point directly to the source document and page containing the information?
3.  **Zero Hallucination?** Does the response exclude facts or assumptions not present in the retrieved context?
4.  **Correct Retrieval?** Did the vector search retrieve the actual documents and sections needed to answer the query in the top-K matches?
5.  **Reasonable Latency?** Did the time-to-first-token occur in under 1 second, and the complete response generate within 5-8 seconds?
6.  **Safe Fallback?** Did the system output the default fallback message and support escalation link when queried on topics outside the document library?

---

## 5. API Testing

API routes are tested using FastAPI's auto-generated Swagger UI or Postman to verify request-response structures and validation rules.

*   **Endpoint Specifications:** Verify that endpoints match the URL patterns, methods, request parameters, and JSON schemas specified in the [API Design Specification](file:///c:/Users/Abrakant/OneDrive/Documents/Projects/AI%20Customer%20Support%20using%20RAG/docs/07_API_Design_Specification.md).
*   **Response Envelopes:** Confirm that all responses return the standard envelope structure containing `success`, `data`, `warnings`, `error`, and `meta` fields.
*   **Edge Case Requests:** Test API inputs using invalid email addresses, empty queries, or unauthorized headers to confirm the endpoints return the appropriate HTTP error codes (`400`, `401`, `403`, `422`).

---

## 6. UI Testing

UI testing focuses on validating layout responsiveness, page transitions, and element accessibility:

*   **Navigation Links:** Click all sidebar links, menu buttons, and page redirects to verify that pages transition smoothly without routing loops or broken links.
*   **Form Validation:** Enter invalid inputs (such as incorrect email formats or short passwords) into registration forms to confirm validation rules block submissions.
*   **Responsive Layout Checks:** Resize the browser window to verify that sidebars collapse, margins adjust, text wraps, and tables compress to fit mobile screen dimensions (down to 375x812).
*   **Loading & Error UI:** Verify that loading indicators (pulsing typing dots, upload progress bars) appear during processing and that error alerts display clearly when connections timeout.

---

## 7. Performance Testing

The system must satisfy realistic performance targets under normal usage:
*   **Chat Query Latency:** The system must return the first token of the chat response in under 1 second, and the full generation must complete in under 5 seconds (with a maximum threshold of 8 seconds under heavy load).
*   **Document Ingestion Times:** Ingesting a standard 10-page document (approx. 3,000 words) must complete parsing, chunking, and indexing in under 30 seconds.
*   **Stability Validation:** The application and database containers must run continuously during normal query traffic without memory leaks, resource exhaustion, or system crashes.

---

## 8. Security Verification

The developer runs manual security checks to verify system isolation and data validation controls:

*   **Unauthorized Access Checks:** Attempt to access administrative routes (e.g. `/api/v1/documents/upload`) without authorization headers to confirm the system returns a `401 Unauthorized` error.
*   **JWT Validity Checks:** Test requests using malformed, expired, or modified JWT access tokens to verify they are rejected by middleware.
*   **File Extension Filtering:** Attempt to upload files with unapproved extensions (`.exe`, `.jpg`) to confirm the upload validator blocks the files.
*   **Size Filtering:** Verify that files larger than 25MB are rejected before ingestion begins.
*   **Access Isolation Checks:** Submit customer-role queries designed to retrieve content from files marked `Internal Use Only` to verify that no internal context is retrieved or cited.

---

## 9. Manual Testing Checklist

The developer uses the checklists below to verify system functionality before releasing updates.

### 9.1 Authentication & Profile Checklist
- [ ] User can register a new account (Administrator role only).
- [ ] User can log in with valid credentials, receiving JWT tokens.
- [ ] Invalid passwords block login attempts, showing inline warnings.
- [ ] Expirations log users out after 30 minutes of inactivity.
- [ ] User can log out, clearing tokens from local browser storage.
- [ ] User can update their profile information and password.

### 9.2 Document Management Checklist
- [ ] Administrator can drag-and-drop PDF, Markdown, and TXT files to upload.
- [ ] File size and extension validators block unapproved uploads.
- [ ] Document library displays file name, size, upload date, and processing status.
- [ ] Library status transitions from `Processing` to `Completed` or `Failed`.
- [ ] Document deletions cascade to remove files from disk and vectors from ChromaDB.

### 9.3 Conversational Q&A Checklist
- [ ] Chat window displays conversational bubbles for queries and responses.
- [ ] AI responses stream text tokens in real-time.
- [ ] System prompt grounding restricts answers to the provided context, preventing hallucinations.
- [ ] Citation badges display inline and open hover cards showing source filenames and sections.
- [ ] Clicking citation badges opens the source document reader.
- [ ] Queries on out-of-scope topics return the configured fallback message and escalation link.
- [ ] Users can submit ratings and comments using the thumbs-up/down feedback buttons.
- [ ] Users can clear their active conversation history.

---

## 10. Bug Tracking Strategy

To minimize management overhead for a single developer, the project avoids complex enterprise tracking tools like Jira. Instead, we use **GitHub Issues**:

```
[Issue Identified] ──► [Open GitHub Issue] ──► [Assign Label & Priority]
                              │
                              ▼
                       [Fix Code Locally]
                              │
                              ▼
         [Commit & Push using Commit Tag: 'fixes #ID']
                              │
                              ▼
                 [GitHub Issue Closes Automatically]
```

*   **Issue Creation:** Open a GitHub Issue for every identified bug or feature request, describing the bug, steps to reproduce it, and the expected behavior.
*   **Label Assignments:** Assign simple labels to organize issues (e.g. `bug`, `feature`, `documentation`, `high-priority`).
*   **Auto-Closure:** Include issue reference tags in git commit messages (e.g., `fix: resolve citation overflow on mobile, fixes #14`) to close the issue automatically when the code is merged to the main branch.

---

## 11. Regression Testing

Regression testing ensures that code updates or bug fixes do not introduce new issues in existing features.
*   **Execution Trigger:** Rerun the automated unit tests and check the manual testing checklist before merging updates from feature branches to the `develop` or `main` branches.
*   **RAG Validation:** Rerun the Gold Standard Evaluation Set after updating system prompts or chunking configurations to verify response quality.

---

## 12. Testing Tools

The testing framework uses standard, lightweight tools to manage tests:

*   **pytest:** The primary testing framework, managing unit, integration, and async endpoint tests.
*   **Swagger UI:** Exposed by FastAPI, used to test API endpoints directly in the browser.
*   **Postman:** Used to build and save API request collections to test complex endpoint sequences (e.g. login -> upload -> query).
*   **Browser DevTools:** Used to inspect HTML elements, verify responsive layouts, monitor network latency, and debug JavaScript errors.
*   **GitHub Issues:** The bug tracking system, managing features, issues, and release notes directly in the repository.

---

## 13. Future Testing Scope

As the platform scales to support high concurrent user traffic and multi-tenant SaaS models, the testing strategy can be expanded to include:
*   **Load Testing:** Using tools like Locust or JMeter to simulate hundreds of concurrent chat sessions, verifying system performance under load.
*   **Security Vulnerability Scanners:** Integrating dependency checkers (such as safety or pip-audit) into CI/CD pipelines to scan code for known vulnerabilities.
*   **Automated UI Testing:** Integrating headless browser testing tools (like Playwright or Cypress) to automate frontend visual checks.

---

## 14. Ready for Testing Checklist

*   [x] Automated unit testing scope and tools (pytest) defined.
*   [x] Module-wise test matrices (Authentication, Upload, Ingestion, Chat) established.
*   [x] Gold Standard Evaluation Set parameters for RAG grounding defined.
*   [x] API, UI, and performance test targets specified.
*   [x] Security verification and access isolation checks documented.
*   [x] Manual QA checklists and Bug tracking strategies (GitHub Issues) established.

---

## 15. Conclusion

This Testing Strategy Specification defines a practical framework to verify the quality, security, and performance of the Enterprise AI Knowledge Platform. By combining automated unit tests for core backend functions with manual QA checklists and RAG evaluation sets, the strategy provides the developer with a realistic testing plan. This framework ensures that updates can be developed, tested, and released with high confidence in the platform's reliability.
