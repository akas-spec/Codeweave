# CodeWeave — AI-Powered Autonomous Code Engineering Platform

![Python](https://img.shields.io/badge/Python-3.11-blue.svg)
![TypeScript](https://img.shields.io/badge/TypeScript-5.0-blue.svg)
![FastAPI](https://img.shields.io/badge/FastAPI-0.115-green.svg)
![Next.js](https://img.shields.io/badge/Next.js-14-black.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-blue.svg)
![Redis](https://img.shields.io/badge/Redis-7-red.svg)

CodeWeave is an AI-powered code engineering platform that enables autonomous code reasoning, multi-repo analysis, and sophisticated embedding-based code navigation.

## Architecture

- **Backend**: FastAPI, SQLAlchemy (async), pgvector, Sentence Transformers
- **Frontend**: Next.js, Tailwind CSS, TypeScript
- **Database**: PostgreSQL with pgvector for embeddings
- **Cache/Queue**: Redis + ARQ
- **AI Integration**: OpenRouter API

## Quick Start

1. Clone the repository
2. Set up environment variables:
   ```bash
   cp .env.example .env
   # Edit .env with your credentials
   ```
3. Start the infrastructure (Database, Redis):
   ```bash
   docker-compose up -d
   ```
4. Start backend (requires Python 3.11+):
   ```bash
   cd backend
   python -m venv venv
   source venv/bin/activate  # or venv\Scripts\activate on Windows
   pip install -r requirements.txt
   uvicorn app.main:app --reload
   ```

## License

This project is licensed under the MIT License.
