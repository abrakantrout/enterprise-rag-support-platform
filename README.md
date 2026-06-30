# Enterprise AI Knowledge Platform with Intelligent Customer Support (RAG)

## Project Overview
This project is an enterprise-grade AI customer support platform powered by Retrieval-Augmented Generation (RAG). Organizations can upload their own knowledge bases (FAQs, manuals, policies, SOPs), and customers interact with an AI assistant that retrieves relevant information from these uploaded documents to generate accurate, context-grounded responses with verifiable citations.

The platform is designed around a clean, decoupled clean architecture, prioritizing security, metadata isolation, and scalability.

---

## Folder Overview

```
├── backend/                       # FastAPI application core
│   ├── app/
│   │   ├── core/                  # Configurations, logging settings
│   │   ├── database/              # PostgreSQL & ChromaDB clients
│   │   ├── middleware/            # Custom filters (placeholders)
│   │   ├── routers/               # API route definitions (health router)
│   │   ├── services/              # Core business services (placeholders)
│   │   ├── utilities/             # Helper tools (placeholders)
│   │   └── main.py                # FastAPI entry point
│   ├── Dockerfile                 # Backend container definition
│   └── requirements.txt           # Backend package dependencies
├── docs/                          # Architecture & design specifications
├── frontend/                      # Streamlit user interface client
│   ├── app.py                     # Frontend entry point
│   └── Dockerfile                 # Frontend container definition
├── docker-compose.yml             # Container orchestration config
├── requirements.txt               # Master package dependencies list
└── README.md                      # General documentation index
```

---

## Sprint 1 Status
*   **Status:** `🟢 Project Foundation Online`
*   **Completed:**
    *   Unified workspace directory layout.
    *   Stateless FastAPI backend shell with core package structures.
    *   Streamlit frontend shell initialized with custom CSS styling.
    *   Configuration management validated through Pydantic Settings.
    *   Standard logging setup with console output and rolling rotation file write.
    *   SQLAlchemy session-management and connection health-checks.
    *   ChromaDB HTTP client integration and heartbeat validations.
    *   Interactive diagnostics `/health` endpoint.
    *   Dev-ready Docker and Docker-compose orchestration.

## RAG Quality & API Keys

The platform operates in one of two embedding modes depending on your configuration:

*   **REAL Mode**:
    *   **Trigger**: Activated when a valid, real `GOOGLE_API_KEY` or `GEMINI_API_KEY` is provided in `.env` (not empty, not starting with `mock-`, and not a placeholder).
    *   **Behavior**: Generates vector representations using high-fidelity Gemini embedding APIs (`models/text-embedding-004`). Cosine similarity scores are calculated raw without scaling.
    *   **Production Readiness**: **Ready for Production**. This is the required configuration for real-world document search and customer support query resolution.
*   **MOCK Mode**:
    *   **Trigger**: Activated if no API key is specified, placeholders are used, or keys begin with `mock-` (e.g., `mock-key`).
    *   **Behavior**: Uses a simplified, local Bag-of-Words and character n-gram matching algorithm with synonym expansion. Retrieval similarity scores are scaled to fit system thresholds.
    *   **Production Readiness**: **NOT Production-Ready**. Mock mode exists solely for offline local development, demo workflows, and automated pipeline validation. It is not suitable for production deployment.

To configure real RAG quality, specify a valid Gemini key in your `.env` file:
```env
GOOGLE_API_KEY=your_real_gemini_api_key_here
```

---

## Local Setup & Run Instructions

### Prerequisites
*   Python 3.11+
*   Docker & Docker Compose (recommended)
*   PostgreSQL & ChromaDB (if running bare-metal)

### Option 1: Run with Docker Compose (Recommended)
1.  Verify Docker is running locally.
2.  Boot up the multi-container stack from the root directory:
    ```bash
    docker-compose up --build
    ```
3.  Access the applications:
    *   **Frontend UI:** [http://localhost:8501](http://localhost:8501)
    *   **Backend API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
    *   **Health Diagnostics:** [http://localhost:8000/health](http://localhost:8000/health)

### Option 2: Running Locally (Bare-metal)
If you want to run the services directly on your host machine:

#### 1. Databases Setup
Run PostgreSQL and ChromaDB containers only:
```bash
docker compose up db chroma -d
```
Note: Ensure your local `.env` variables point to `localhost:5432` for PostgreSQL and `localhost:8001` for ChromaDB.

#### 2. Running Backend FastAPI
1.  Navigate to the backend directory:
    ```bash
    cd backend
    ```
2.  Create and activate a virtual environment:
    ```bash
    python -m venv .venv
    # Windows
    .\.venv\Scripts\activate
    # macOS/Linux
    source .venv/bin/activate
    ```
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
4.  Start the FastAPI server:
    ```bash
    uvicorn app.main:app --reload
    ```

#### 3. Running Frontend Streamlit
1.  Open a new terminal tab and navigate to the frontend directory:
    ```bash
    cd frontend
    ```
2.  Create and activate a virtual environment:
    ```bash
    python -m venv .venv
    # Windows
    .\.venv\Scripts\activate
    # macOS/Linux
    source .venv/bin/activate
    ```
3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```
4.  Start the Streamlit client:
    ```bash
    streamlit run app.py
    ```
