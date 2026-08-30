import os
import re
import ast
import logging
from pathlib import Path
from typing import Optional
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from app.config import settings
from app.models.document import Document
from app.models.repository import Repository, IngestionStatus
from app.services.embeddings import EmbeddingService
from app.services.github_service import GitHubService

logger = logging.getLogger(__name__)

# File extensions to process
CODE_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go",
    ".rs", ".cpp", ".c", ".h", ".hpp", ".cs", ".rb", ".php",
    ".swift", ".kt", ".scala", ".vue", ".svelte", ".html", ".css",
}
DOC_EXTENSIONS = {".md", ".mdx", ".txt", ".rst", ".adoc"}
CONFIG_EXTENSIONS = {".json", ".yaml", ".yml", ".toml", ".ini", ".cfg"}
PDF_EXTENSIONS = {".pdf"}

IGNORE_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv",
    "dist", "build", ".next", ".nuxt", "target", "bin", "obj",
    ".idea", ".vscode", "coverage", ".tox", "env",
    "vendor", "bower_components", ".cache",
}

IGNORE_FILES = {
    ".DS_Store", "Thumbs.db", ".gitignore", ".env",
    "package-lock.json", "yarn.lock", "pnpm-lock.yaml",
    "poetry.lock", "Pipfile.lock", "Cargo.lock",
}


@dataclass
class Chunk:
    """Represents a chunk of code or text."""
    content: str
    source: str  # File path relative to repo root
    chunk_index: int
    chunk_type: str  # 'function', 'class', 'markdown_section', 'text', 'config'
    language: Optional[str] = None


class IngestionService:
    """Service for ingesting repository content into the vector database."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.embedding_service = EmbeddingService.get_instance()

    async def ingest_repository(
        self,
        repository: Repository,
        access_token: Optional[str] = None,
    ) -> None:
        """Full ingestion pipeline: clone -> crawl -> chunk -> embed -> store."""
        try:
            # Update status
            repository.ingestion_status = IngestionStatus.CLONING
            repository.ingestion_progress = 0
            await self.db.commit()

            # Clone repo
            github_service = GitHubService(access_token=access_token)
            repo_path = github_service.clone_repo(
                repository.github_url, repository.full_name
            )
            # repo_path = Path(settings.REPOS_DIR) / repository.full_name.replace("/", "_")

            # Update status
            repository.ingestion_status = IngestionStatus.PARSING
            repository.ingestion_progress = 20
            await self.db.commit()

            # Delete existing documents for this repo (re-ingestion)
            await self.db.execute(
                delete(Document).where(Document.repository_id == repository.id)
            )

            # Crawl and chunk files
            all_chunks = self._crawl_and_chunk(repo_path)
            total_chunks = len(all_chunks)
            logger.info(f"Found {total_chunks} chunks in {repository.full_name}")

            if total_chunks == 0:
                repository.ingestion_status = IngestionStatus.COMPLETED
                repository.ingestion_progress = 100
                repository.total_chunks = 0
                await self.db.commit()
                return

            # Update status
            repository.ingestion_status = IngestionStatus.EMBEDDING
            repository.ingestion_progress = 40
            await self.db.commit()

            # Generate embeddings in batches
            batch_size = 32
            for i in range(0, total_chunks, batch_size):
                batch = all_chunks[i:i + batch_size]
                texts = [chunk.content for chunk in batch]
                embeddings = await self.embedding_service.aencode_batch(texts, batch_size=batch_size)

                # Store in database
                for chunk, embedding in zip(batch, embeddings):
                    doc = Document(
                        source=chunk.source,
                        content=chunk.content,
                        chunk_index=chunk.chunk_index,
                        chunk_type=chunk.chunk_type,
                        language=chunk.language,
                        embedding=embedding,
                        repository_id=repository.id,
                    )
                    self.db.add(doc)

                # Update progress
                progress = 40 + int((i + len(batch)) / total_chunks * 55)
                repository.ingestion_progress = min(progress, 95)
                await self.db.commit()

            # Finalize
            repository.ingestion_status = IngestionStatus.COMPLETED
            repository.ingestion_progress = 100
            repository.total_chunks = total_chunks
            await self.db.commit()

            logger.info(f"Ingestion complete for {repository.full_name}: {total_chunks} chunks")

        except Exception as e:
            logger.error(f"Ingestion failed for {repository.full_name}: {e}")
            repository.ingestion_status = IngestionStatus.FAILED
            repository.ingestion_error = str(e)[:2000]
            await self.db.commit()
            raise

    def _crawl_and_chunk(self, repo_path: Path) -> list[Chunk]:
        """Crawl repository and create chunks from all supported files."""
        all_chunks = []

        for root, dirs, files in os.walk(repo_path):
            # Skip ignored directories
            dirs[:] = [d for d in dirs if d not in IGNORE_DIRS]

            for filename in files:
                if filename in IGNORE_FILES:
                    continue

                file_path = Path(root) / filename
                ext = file_path.suffix.lower()
                relative_path = str(file_path.relative_to(repo_path))

                try:
                    if ext in CODE_EXTENSIONS:
                        chunks = self._chunk_code_file(file_path, relative_path, ext)
                    elif ext in DOC_EXTENSIONS:
                        chunks = self._chunk_markdown_file(file_path, relative_path)
                    elif ext in CONFIG_EXTENSIONS:
                        chunks = self._chunk_text_file(file_path, relative_path, "config")
                    elif ext in PDF_EXTENSIONS:
                        chunks = self._chunk_pdf_file(file_path, relative_path)
                    else:
                        continue

                    all_chunks.extend(chunks)
                except Exception as e:
                    logger.warning(f"Failed to process {relative_path}: {e}")
                    continue

        return all_chunks

    def _chunk_code_file(self, file_path: Path, relative_path: str, ext: str) -> list[Chunk]:
        """Chunk a code file. Use AST parsing for Python, regex for others."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []

        if not content.strip():
            return []

        language = self._ext_to_language(ext)

        # For Python, use AST-based chunking
        if ext == ".py":
            return self._chunk_python_ast(content, relative_path)

        # For other languages, use regex-based chunking
        return self._chunk_code_regex(content, relative_path, language)

    def _chunk_python_ast(self, code: str, relative_path: str) -> list[Chunk]:
        """Chunk Python code using AST to extract functions and classes."""
        try:
            tree = ast.parse(code)
        except SyntaxError:
            return self._chunk_text(code, relative_path, "python")

        chunks = []
        chunk_index = 0
        covered_lines = set()
        lines = code.split("\n")

        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                source_segment = ast.get_source_segment(code, node)
                if not source_segment:
                    continue
                    
                if hasattr(node, "lineno") and hasattr(node, "end_lineno"):
                    for i in range(node.lineno - 1, node.end_lineno):
                        covered_lines.add(i)

                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    chunks.append(Chunk(
                        content=f"# File: {relative_path}\n\n{source_segment}",
                        source=relative_path,
                        chunk_index=chunk_index,
                        chunk_type="function",
                        language="python",
                    ))
                    chunk_index += 1
                elif isinstance(node, ast.ClassDef):
                    if len(source_segment.split()) > self.embedding_service.CHUNK_SIZE * 4 if hasattr(self.embedding_service, 'CHUNK_SIZE') else 2000:
                        class_header = self._get_class_header(source_segment)
                        chunks.append(Chunk(
                            content=f"# File: {relative_path}\n\n{class_header}",
                            source=relative_path,
                            chunk_index=chunk_index,
                            chunk_type="class",
                            language="python",
                        ))
                        chunk_index += 1
                    else:
                        chunks.append(Chunk(
                            content=f"# File: {relative_path}\n\n{source_segment}",
                            source=relative_path,
                            chunk_index=chunk_index,
                            chunk_type="class",
                            language="python",
                        ))
                        chunk_index += 1

        uncovered_blocks = []
        current_block = []
        
        for i, line in enumerate(lines):
            if i not in covered_lines:
                current_block.append(line)
            else:
                if current_block:
                    uncovered_blocks.append("\n".join(current_block))
                    current_block = []
        if current_block:
            uncovered_blocks.append("\n".join(current_block))
            
        uncovered_code = "\n\n".join(b for b in uncovered_blocks if b.strip())
        if uncovered_code.strip():
            module_chunks = self._chunk_text(uncovered_code, relative_path, "python", chunk_type="module_level")
            for c in module_chunks:
                c.chunk_index = chunk_index
                chunk_index += 1
                chunks.append(c)

        if not chunks:
            return self._chunk_text(code, relative_path, "python")

        return chunks

    def _get_class_header(self, class_source: str) -> str:
        """Extract class definition line and docstring."""
        lines = class_source.split("\n")
        header_lines = []
        in_docstring = False
        docstring_done = False

        for line in lines:
            if not docstring_done:
                header_lines.append(line)
                if '"""' in line or "'''" in line:
                    if in_docstring:
                        docstring_done = True
                    else:
                        in_docstring = True
                        # Single-line docstring
                        if line.count('"""') >= 2 or line.count("'''") >= 2:
                            docstring_done = True
            else:
                break

        return "\n".join(header_lines)

    def _chunk_code_regex(self, code: str, relative_path: str, language: str) -> list[Chunk]:
        """Chunk code using regex-based function/class detection."""
        # Pattern to match function and class definitions in common languages
        patterns = [
            r'(?:^|\n)((?:export\s+)?(?:async\s+)?function\s+\w+[^{]*\{)',  # JS/TS functions
            r'(?:^|\n)((?:export\s+)?class\s+\w+[^{]*\{)',  # JS/TS classes
            r'(?:^|\n)((?:pub\s+)?(?:async\s+)?fn\s+\w+)',  # Rust functions
            r'(?:^|\n)((?:public|private|protected)?\s*(?:static\s+)?\w+\s+\w+\s*\([^)]*\)\s*\{)',  # Java/C# methods
            r'(?:^|\n)(func\s+(?:\([^)]*\)\s+)?\w+)',  # Go functions
        ]

        # Try to find function boundaries; if none found, fall back to text chunking
        chunks = self._chunk_text(code, relative_path, language)
        return chunks

    def _chunk_markdown_file(self, file_path: Path, relative_path: str) -> list[Chunk]:
        """Chunk markdown files by heading sections."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []

        if not content.strip():
            return []

        # Split by headings (##, ###, etc.)
        sections = re.split(r'(?=^#{1,3}\s)', content, flags=re.MULTILINE)
        chunks = []

        for i, section in enumerate(sections):
            section = section.strip()
            if len(section) < 20:  # Skip very short sections
                continue

            # If section is too long, split further
            if len(section.split()) > settings.CHUNK_SIZE:
                sub_chunks = self._split_by_length(section, settings.CHUNK_SIZE)
                for j, sub in enumerate(sub_chunks):
                    chunks.append(Chunk(
                        content=f"# Source: {relative_path}\n\n{sub}",
                        source=relative_path,
                        chunk_index=len(chunks),
                        chunk_type="markdown_section",
                        language="markdown",
                    ))
            else:
                chunks.append(Chunk(
                    content=f"# Source: {relative_path}\n\n{section}",
                    source=relative_path,
                    chunk_index=i,
                    chunk_type="markdown_section",
                    language="markdown",
                ))

        return chunks

    def _chunk_pdf_file(self, file_path: Path, relative_path: str) -> list[Chunk]:
        """Extract text from PDF and chunk it."""
        try:
            import fitz  # PyMuPDF
            doc = fitz.open(str(file_path))
            text = ""
            for page in doc:
                text += page.get_text() + "\n"
            doc.close()
        except ImportError:
            logger.warning("PyMuPDF not installed. Skipping PDF: %s", relative_path)
            return []
        except Exception as e:
            logger.warning(f"Failed to read PDF {relative_path}: {e}")
            return []

        if not text.strip():
            return []

        return self._chunk_text(text, relative_path, "pdf", chunk_type="pdf_text")

    def _chunk_text_file(self, file_path: Path, relative_path: str, chunk_type: str = "text") -> list[Chunk]:
        """Chunk a plain text or config file."""
        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            return []

        if not content.strip():
            return []

        # Small config files: treat as single chunk
        if len(content.split()) <= settings.CHUNK_SIZE:
            return [Chunk(
                content=f"# File: {relative_path}\n\n{content}",
                source=relative_path,
                chunk_index=0,
                chunk_type=chunk_type,
                language=None,
            )]

        return self._chunk_text(content, relative_path, None, chunk_type)

    def _chunk_text(self, text: str, source: str, language: Optional[str], chunk_type: str = "text") -> list[Chunk]:
        """Generic text chunking with overlap."""
        words = text.split()
        chunks = []
        chunk_size = settings.CHUNK_SIZE
        overlap = settings.CHUNK_OVERLAP

        i = 0
        chunk_index = 0
        while i < len(words):
            end = min(i + chunk_size, len(words))
            chunk_text = " ".join(words[i:end])

            if len(chunk_text.strip()) > 20:
                chunks.append(Chunk(
                    content=f"# File: {source}\n\n{chunk_text}",
                    source=source,
                    chunk_index=chunk_index,
                    chunk_type=chunk_type,
                    language=language,
                ))
                chunk_index += 1

            i += chunk_size - overlap

        return chunks

    def _split_by_length(self, text: str, max_words: int) -> list[str]:
        """Split text into parts of roughly max_words each."""
        words = text.split()
        parts = []
        for i in range(0, len(words), max_words):
            parts.append(" ".join(words[i:i + max_words]))
        return parts

    @staticmethod
    def _ext_to_language(ext: str) -> str:
        """Map file extension to language name."""
        mapping = {
            ".py": "python", ".js": "javascript", ".ts": "typescript",
            ".jsx": "javascript", ".tsx": "typescript",
            ".java": "java", ".go": "go", ".rs": "rust",
            ".cpp": "cpp", ".c": "c", ".h": "c",
            ".hpp": "cpp", ".cs": "csharp", ".rb": "ruby",
            ".php": "php", ".swift": "swift", ".kt": "kotlin",
            ".scala": "scala", ".vue": "vue", ".svelte": "svelte",
        }
        return mapping.get(ext, "unknown")
