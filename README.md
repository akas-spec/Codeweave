# CodeWeave

An AI-powered autonomous code engineering platform that semantically indexes GitHub repositories and provides an interactive LLM chat interface for codebase navigation and automated debugging.

## Features

- **Semantic Code Search:** Intelligently chunks and indexes your codebase using Python AST parsing and SentenceTransformers.
- **Interactive Chat Interface:** Real-time streaming chat powered by OpenRouter LLMs, allowing you to ask architectural and debugging questions about your code.
- **Autonomous Agent:** ReAct-based background agent orchestration that can autonomously navigate repositories, diagnose issues, and propose fixes.
- **GitHub Integration:** Seamless GitHub OAuth login and 1-click repository cloning and indexing.

## Architecture

- **Backend**: FastAPI, SQLAlchemy (async), pgvector, Sentence Transformers
- **Frontend**: Next.js, Tailwind CSS, TypeScript
- **Database**: PostgreSQL with pgvector for embeddings
- **Cache/Queue**: Redis + ARQ
- **AI Integration**: OpenRouter API

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Python 3.11+
- Node.js 18+

### 1. Clone the repository
```bash
# Note: Replace the URL with your actual GitHub repository URL
git clone https://github.com/YOUR_USERNAME/CodeWeave.git
cd CodeWeave
```

### 2. Set up environment variables
```bash
cp .env.example .env
# Open .env and add your OpenRouter API key and GitHub OAuth credentials
```

### 3. Start the infrastructure (Database, Redis)
```bash
docker-compose up -d
```

### 4. Start the Backend API
```bash
cd backend
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Mac/Linux:
# source venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload
```

### 5. Start the Frontend
Open a new terminal window:
```bash
cd frontend
npm install
npm run dev
```

*The application will now be available at http://localhost:3000 and the backend API at http://localhost:8000.*

## License

This project is licensed under the MIT License.
