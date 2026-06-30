# Enterprise AI Knowledge Platform with Intelligent Customer Support (RAG)

An enterprise-grade AI customer support platform powered by Retrieval-Augmented Generation (RAG). Organizations can ingest their own knowledge bases (FAQs, manuals, policies, SOPs), and support agents interact with an AI assistant that retrieves relevant information from these uploaded documents to generate accurate, context-grounded responses with verifiable citations.

The platform is designed around a decoupled, clean architecture, prioritizing security, metadata isolation, and scalability.

---

## Features

- **JWT Authentication & RBAC**: Secure user authentication with Role-Based Access Control (restricted management views for Administrator and Support Agent roles).
- **Multi-Tenant Ingestion Isolation**: Document metadata, text chunks, and vector embeddings are strictly partitioned by organization ID.
- **Granular Ingestion Pipeline**: Safe uploads supporting PDF, TXT, and DOCX formats with step-by-step control (Extract Text, Parse Chunks, Generate Embeddings, Index Vectors).
- **Text Extraction & Semantic Chunking**: Text parser handles layouts, and a semantic chunker preserves contextual sentence boundaries.
- **Gemini Embeddings**: High-fidelity vector representations generated via Google Gemini Embedding APIs (`models/text-embedding-004`).
- **ChromaDB Vector Store**: Fast vector similarity search with cosine distance thresholds.
- **Grounded Answer Generator**: Combines retrieved knowledge segments to synthesize verified answers via Gemini.
- **Citations & Verification Scores**: Underlines grounding by mapping source attribution tags, vector similarity metrics, and confidence metrics.
- **React Admin Console Dashboard**: Displays telemetry metrics (total/processed documents, active sessions, negative review logs) alongside recent inquiries.
- **Chat Session Management**: Generates readable titles derived from the first user question, saves session history, and supports chat deletions.
- **Dockerized Ingestion**: Fully containerized stack for simple local deployment.

---

## Technology Stack

### Frontend
- **Framework**: React 19 (TypeScript, SPA architecture)
- **Tooling**: Vite (fast builds and dev server)
- **Styling**: Tailwind CSS v4, PostCSS, Autoprefixer ( premium SaaS dashboard look)
- **Router**: React Router DOM (v7)
- **HTTP Client**: Axios (with authorization request interceptors)
- **Icons**: Lucide React

### Backend
- **Framework**: FastAPI (high-performance async Python APIs)
- **ORM**: SQLAlchemy (database modeling and connection pool)
- **Database**: PostgreSQL (relational metadata store)
- **Vector DB**: ChromaDB (dense embedding index)
- **LLM Provider**: Google Gemini APIs
- **Migration Engine**: Alembic (database schema migrations)
- **Containerization**: Docker & Docker Compose

---

## Project Structure

```
├── backend/                       # FastAPI application core
│   ├── app/
│   │   ├── core/                  # Configurations, logging settings
│   │   ├── database/              # PostgreSQL & ChromaDB clients, models
│   │   ├── middleware/            # Custom filter middlewares
│   │   ├── routers/               # API route definitions (auth, documents, sessions)
│   │   ├── services/              # Extraction, chunking, embeddings, grounding services
│   │   └── main.py                # FastAPI entry point
│   ├── Dockerfile                 # Backend container definition
│   └── requirements.txt           # Backend package dependencies
├── docs/                          # Architecture & design specifications
├── frontend/                      # React TypeScript user interface client
│   ├── src/                       # React source files (components, pages, api)
│   │   ├── api/                   # Typed Axios API Client
│   │   ├── components/            # Layout shell, Sidebar, Header
│   │   └── pages/                 # Login, Dashboard, Documents, Chat pages
│   ├── index.html                 # Root HTML template
│   ├── package.json               # Node dependencies and scripts
│   └── Dockerfile                 # React frontend container definition
├── docker-compose.yml             # Container orchestration config
├── requirements.txt               # Master package dependencies list
└── README.md                      # General documentation index
```

---

## Environment Variables

To run the platform, create a `.env` file in the root directory. Below is the list of required variables:

```env
# Database Credentials
DATABASE_URL=postgresql://postgres:postgres@db:5432/rag_support

# ChromaDB Coordinates
CHROMA_HOST=chroma
CHROMA_PORT=8000

# Google Gemini API Keys (For REAL RAG Mode)
GOOGLE_API_KEY=your_real_gemini_api_key_here

# JWT Secret Key
JWT_SECRET_KEY=your_jwt_secret_signing_key_here
```

---

## Setup & Run Instructions

### Option 1: Run with Docker Compose (Recommended)

1. Verify Docker is running locally.
2. Build and boot the multi-container stack from the root directory:
   ```bash
   docker compose up --build
   ```
3. Access the applications:
   * **Frontend SPA Console:** [http://localhost:3000](http://localhost:3000)
   * **Backend API Docs:** [http://localhost:8000/docs](http://localhost:8000/docs)
   * **Health Diagnostics:** [http://localhost:8000/health](http://localhost:8000/health)

### Option 2: Running Locally (Bare-metal)

#### 1. Databases Setup
Start PostgreSQL and ChromaDB containers:
```bash
docker compose up db chroma -d
```
*Note: Update host settings in your `.env` variables to `localhost:5432` for PostgreSQL and `localhost:8001` for ChromaDB.*

#### 2. Running Backend FastAPI
1. Navigate to the backend directory:
   ```bash
   cd backend
   ```
2. Set up virtual environment and install packages:
   ```bash
   python -m venv .venv
   # Windows
   .\.venv\Scripts\activate
   # macOS/Linux
   source .venv/bin/activate
   
   pip install -r requirements.txt
   ```
3. Start the FastAPI server:
   ```bash
   uvicorn app.main:app --reload
   ```

#### 3. Running Frontend React Client
1. Navigate to the frontend directory:
   ```bash
   cd frontend
   ```
2. Install packages and launch the Vite development server:
   ```bash
   npm install
   npm run dev
   ```
3. Open your browser to [http://localhost:3000](http://localhost:3000).

---

## Current Capabilities

- **Secure Workspace Ingestion**: Admins upload documents, and stages are executed sequentially (Extract → Chunk → Embed → Index). Stage steps show green checkmarks and disabled styles once successfully completed and persisted.
- **Intelligent Telemetry**: Dashboard lists completed/failed documents count, chat statistics, and tracks low-rated logs so admins can identify gaps in knowledge coverage.
- **Conversational Grounding**: Support agents enter questions, the system retrieves local text snippets from ChromaDB, verifies references, calculates confidence scores, and produces citations with accordions.
- **Session Deletion**: Chat sidebar records session histories with readable titles, allowing agents to clear inactive conversations.

---

## Future Improvements

- **Background Job Queue**: Offload text extraction, embeddings calculations, and vector indexing tasks to background workers (Celery/Redis) to prevent request blocking.
- **PDF OCR Improvements**: Enhance scanner pipelines to OCR text from scanned document images using Tesseract or Google Cloud Vision APIs.
- **Admin Analytics Charts**: Integrate visual telemetry dashboards (line graphs, pie charts) for feedback scores and query categories.
- **Multi-Model Support**: Expose configurations to choose alternative LLM foundation models (Claude, GPT-4o, Llama).
