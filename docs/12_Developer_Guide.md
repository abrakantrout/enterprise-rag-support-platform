# Developer Guide

| Attribute | Details |
| :--- | :--- |
| **Project Name** | Enterprise AI Knowledge Platform with Intelligent Customer Support (RAG) |
| **Document Name** | Developer Guide |
| **Version** | v1.0.0 (Baseline Approved) |
| **Document Status** | Approved |
| **Owner** | Principal Software Engineer & Technical Lead |
| **Last Updated** | 2026-06-27 |

### Document Purpose
This Developer Guide establishes the coding standards, design guidelines, configurations, and review checklists for the *Enterprise AI Knowledge Platform*. It serves as the engineering handbook for development, ensuring clean, maintainable, and consistent code quality across backend, frontend, and AI subsystems.

---

## 1. Engineering Philosophy

To build a production-ready application as a single developer, we prioritize code quality and maintainability over clever, over-engineered solutions.

Our development workflow is guided by these core principles:
*   **Simplicity:** Write direct, straightforward code. Avoid pre-emptive optimization or complex design patterns until they are explicitly required.
*   **Readability:** Code is read more often than it is written. Use clear variable names, logical page structures, and explicit typing so that other developers (and your future self) can easily understand the logic.
*   **Maintainability:** Design components and modules to be easily updated or replaced with minimal impact on the rest of the application.
*   **Small, Reusable Components:** Break down complex tasks into small, single-purpose functions and UI components, making them easier to test and reuse.
*   **Separation of Concerns (SoC):** Ensure that each layer of the application has a single, well-defined responsibility.
*   **Practical Clean Architecture:** Enforce logical boundaries between routing, database management, and RAG execution layers, avoiding academic over-complexity.
*   **Consistency over Cleverness:** Adhere to established coding standards and naming conventions throughout the repository. Consistency makes the codebase predictable and easier to debug.

---

## 2. Folder Organization Philosophy

The platform's folder organization separates concerns and isolates dependencies to support modular development:

*   **Frontend-Backend Separation:** The frontend UI and the backend API are housed in separate logical directories. This isolates client-side dependencies (e.g. Streamlit, React node packages) from backend Python runtimes and libraries.
*   **Decoupled Services and Routes:** FastAPI routes are kept thin, acting only as interface routers. Business logic is placed in dedicated Service classes, ensuring that core code can be reused and tested independently of API endpoints.
*   **Isolated Configuration:** Application variables, database credentials, and API keys are managed in a central configuration module, preventing settings from being scattered across the codebase.
*   **Reusable Utilities:** Shared logic (e.g., date formatting, file type detection, custom text cleansers) is isolated in a utilities folder, keeping core service components focused on their primary tasks.

> [!NOTE]
> The final directory structure will be initialized and detailed during the code implementation phase.

---

## 3. Naming Conventions

Consistent naming makes the codebase predictable and easier to search.

| Component Class | Naming Convention | Case Standard | Architectural Examples |
| :--- | :--- | :--- | :--- |
| **Python Files** | Snake case | `snake_case.py` | `document_service.py`, `auth_router.py` |
| **Classes** | Pascal case | `PascalCase` | `DocumentService`, `RAGEngine` |
| **Functions** | Snake case | `snake_case` | `get_active_session()`, `parse_pdf()` |
| **Variables** | Snake case | `snake_case` | `user_id`, `chunk_overlap` |
| **Constants** | Upper snake case | `UPPER_SNAKE_CASE` | `MAX_FILE_SIZE_BYTES`, `DEFAULT_PAGE_SIZE` |
| **Env Variables** | Upper snake case | `UPPER_SNAKE_CASE` | `DATABASE_URL`, `GEMINI_API_KEY` |
| **API Endpoints** | Lower kebab case | `/kebab-case/` | `/api/v1/auth/login`, `/api/v1/chat/sessions` |
| **DB Models** | Pascal case | `PascalCase` | `User`, `Document`, `ChatSession` |

---

## 4. Python Coding Standards

Backend code must adhere to modern Python styling standards to ensure clean and readable code:

### 4.1 Type Hints
All function signatures and class properties must include type hints. This makes the code self-documenting and enables static analysis tools to catch type-mismatch bugs before runtime.

```python
# Example: Type-hinted function
def retrieve_context_chunks(document_id: str, limit: int = 5) -> list[str]:
    # Logic goes here
    return []
```

### 4.2 Docstrings
Every class and public function must include a docstring (using PEP 257 standard double-quotes) explaining its purpose, parameters, and return types.

```python
def extract_pdf_text(file_path: str) -> str:
    """
    Extracts raw text content from a local PDF file using PyMuPDF.

    Args:
        file_path (str): The local path to the target PDF file.

    Returns:
        str: The extracted raw text string.
    """
    # Logic goes here
    return ""
```

### 4.3 Clean Imports
Group imports logically at the top of each file:
1.  Standard library imports (e.g. `os`, `sys`, `json`).
2.  Third-party package imports (e.g. `fastapi`, `sqlalchemy`, `pydantic`).
3.  Local application imports (e.g. `from app.services import document_service`).

### 4.4 Function and Class Responsibilities
*   **Function Length:** Keep functions focused on a single task. Functions should rarely exceed 50 lines of code.
*   **Class Cohesion:** Classes must have a single responsibility. For example, a `PDFParser` class should only parse PDFs, and should not contain logic for saving files or generating database records.

---

## 5. FastAPI Guidelines

FastAPI routers are designed to manage HTTP communication and payload validation, delegating business logic to service layers.

*   **Thin Routers:** Router handlers should focus on:
    *   Verifying user roles.
    *   Validating input payloads via Pydantic schemas.
    *   Calling the appropriate service method.
    *   Returning standard response envelopes.
*   **Dependency Injection:** Use FastAPI's dependency injection system (`Depends`) to inject database sessions and service instances, making it easier to mock dependencies in tests.
*   **Pydantic Data Validation:** Define clear input and output Pydantic schemas for all route parameters, ensuring that invalid data is rejected at the API boundary.

---

## 6. Database Guidelines

Ensure data operations are secure, efficient, and consistent by following these guidelines:

*   **Use the ORM:** Perform database queries using SQLAlchemy ORM syntax. Avoid writing raw SQL strings unless necessary for complex analytics or performance optimization.
*   **Transaction Scope:** Wrap write operations in database transactions. Ensure sessions are committed only when the entire operation succeeds, and rolled back if an error occurs.
*   **Keep Queries Simple:** Avoid complex JOIN chains. If a query becomes too complex, split it into simpler queries or build a dedicated database view.
*   **Avoid Logic Duplication:** Keep query queries inside repository or service classes. Do not repeat query filters (e.g., `is_deleted == False`) across routers.

---

## 7. AI Module Guidelines

To keep prompt engineering and AI execution clean and maintainable, follow these rules:

*   **Isolate Prompts:** Prompt templates must be kept separate from the Python logic. Save templates in external files (e.g., YAML or text files) or in system configuration parameters.
*   **Configurable Model Parameters:** Never hardcode model names, temperatures, or similarity thresholds in service logic. Read these parameters from settings configuration instances.
*   **Decouple AI Subsystems:** Separate document parsing from embedding generation, and vector search from prompt synthesis, allowing components to be tested and updated independently.
*   **Isolate AI Logic:** Keep LLM API and vector database operations inside the `RAGEngine` module. API router code should never directly execute vector searches or generate prompt completions.

---

## 8. Error Handling Standards

The application implements a consistent error handling strategy to protect system state and provide clear user feedback:

*   **User-Friendly Errors:** API errors returned to the client must use friendly, non-technical explanations (e.g. "We could not find the requested file") rather than raw database tracebacks.
*   **Structured Logging:** Capture the full stack trace and technical details of exceptions in application logs for debugging.
*   **Graceful Failures:** Ensure failures in secondary tasks (e.g., sending an upload notification) do not crash the primary task (e.g., completing the file ingestion).

---

## 9. Logging Standards

The platform logs events using specific log levels:

*   **INFO:** Used to log standard application milestones, such as successful logins, document uploads, and session completions.
*   **WARNING:** Used to log non-critical issues that do not block operations but require monitoring, such as API retry attempts or failed login attempts.
*   **ERROR:** Used to log system exceptions, database failures, and unhandled errors that block task execution. Error logs should always include stack traces.

---

## 10. Configuration Management

Configuration parameters are managed statelessly:
*   **Environment Variables:** System ports, DB URLs, and API keys are read from environment variables at runtime.
*   **Environment Checkpoints:** Pydantic Settings validates that all required configurations are present and correctly typed when the application starts up, blocking server execution if variables are missing.

---

## 11. Git Workflow

To coordinate codebase changes efficiently, the developer uses a simple Git workflow:

```
[Main Branch (Production)] ──► [Develop Branch (Staging)] ──► [Feature Branch (Local Dev)]
                                                                      │
                                     ┌────────────────────────────────┴────────────────────────────────┐
                                     ▼                                                                 ▼
                               [Small Commit]                                                    [Small Commit]
                         "feat: add chunk validator"                                       "test: add parsing tests"
                                     │                                                                 │
                                     └────────────────────────────────┬────────────────────────────────┘
                                                                      ▼
                                                       [Merge Pull Request to Develop]
```

*   **Main Branch:** Production branch, representing the stable state of the application.
*   **Develop Branch:** Staging branch, containing completed features waiting for deployment.
*   **Feature Branches:** Dedicated branch for each feature or bug fix (e.g., `feat/document-chunking`, `fix/login-latency`).
*   **Small Commits:** Make small, logical commits to track code changes clearly.
*   **Commit Messages:** Write clear, concise commit messages that explain *what* changes were made (e.g. `feat: add file type validation to ingestion pipeline`).

---

## 12. Documentation Standards

*   **Inline Comments:** Write comments to explain *why* complex or non-obvious logic is necessary, rather than explaining *what* the code does.
*   **README Maintenance:** Keep the root `README.md` updated with setup guides, prerequisites, database configurations, and testing commands.
*   **API Schema Updates:** Document API modifications using FastAPI's Pydantic model schemas to ensure auto-generated Swagger documentation stays accurate.

---

## 13. Code Review Checklist

Before merging feature branches to `develop` or `main`, review the code against the checklist below:

- [ ] **Readability:** Are variable and function names self-descriptive? Is the logic simple and easy to follow?
- [ ] **Type Safety:** Do all functions and class definitions include type hints?
- [ ] **Error Handling:** Are exceptions caught and logged? Does the API return user-friendly messages?
- [ ] **Logging:** Are log levels (`INFO`, `WARNING`, `ERROR`) used correctly? Are stack traces captured for exceptions?
- [ ] **Security:** Are database queries protected against SQL injection? Do secure routes enforce JWT checks and role constraints?
- [ ] **Testing:** Do new features include unit and integration tests? Does the test suite run successfully?
- [ ] **Documentation:** Are docstrings present on public classes and functions? Have configurations and README files been updated?

---

## 14. Common Mistakes to Avoid

*   **Oversized Functions:** Functions that perform multiple, unrelated tasks. Split large functions into smaller, single-purpose utilities.
*   **Hardcoded Configuration:** Hardcoding API keys, ports, or model names. Always read settings from environment variables.
*   **Business Logic in Routers:** Writing SQL queries or prompt templates inside router files. Routers must remain thin, delegating tasks to services.
*   **Ignoring Exceptions:** Catching exceptions using blank handlers (e.g. `except: pass`) without logging the issue.
*   **Duplicate Code:** Repeating identical logic or validations across services. Extract shared patterns into common utility files.

---

## 15. AI Engineering Best Practices

*   **Context Grounding:** Prompts must explicitly instruct the LLM to restrict its answers to the provided context, preventing hallucinations.
*   **Model Agility:** Configure model selections using environment settings to allow swapping providers without code changes.
*   **Evaluation Checks:** Run test questions against the Gold Standard Evaluation Set periodically to evaluate response quality.
*   **Token Optimization:** Optimize retrieval chunk size and prompt context length to control API usage costs.

---

## 16. Ready for Development Checklist

*   [x] Engineering philosophy and modular principles defined.
*   [x] Naming conventions and coding standards established.
*   [x] Thin-router design and service layers specified.
*   [x] Prompt isolation and configuration guidelines documented.
*   [x] Error handling, log levels, and configuration variables defined.
*   [x] Git branching workflows and code review checklists established.

---

## 17. Conclusion

This Developer Guide defines the coding standards, architecture boundaries, and git workflows for the Enterprise AI Knowledge Platform. By maintaining small functions, separating routes from business services, isolating prompt templates, and running regression tests, this guide provides a framework to write clean, secure, and production-ready code. Following these guidelines ensures that the application remains maintainable and scalable as it transitions from development to production.
