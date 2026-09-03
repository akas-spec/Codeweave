"""Initial baseline schema

Revision ID: 0001
Revises: 
Create Date: 2026-09-03

This is a baseline migration representing the existing CodeWeave schema.
Tables: users, repositories, documents (with pgvector), llm_usage.

Because the database already has these tables from Phase 0-3, this
migration uses batch operations with `IF NOT EXISTS` semantics where
possible, so it is safe to run against both fresh and existing databases.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from pgvector.sqlalchemy import Vector

# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Enable pgvector extension (idempotent)
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # --- users ---
    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("github_id", sa.Integer(), nullable=False, unique=True, index=True),
        sa.Column("username", sa.String(255), nullable=False, unique=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("avatar_url", sa.String(512), nullable=True),
        sa.Column("github_access_token", sa.String(512), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        if_not_exists=True,
    )

    # --- repositories ---
    op.create_table(
        "repositories",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("full_name", sa.String(512), nullable=False, unique=True),
        sa.Column("github_url", sa.String(1024), nullable=False),
        sa.Column("description", sa.String(2048), nullable=True),
        sa.Column("default_branch", sa.String(255), server_default="main"),
        sa.Column("language", sa.String(100), nullable=True),
        sa.Column(
            "ingestion_status",
            sa.Enum("pending", "cloning", "parsing", "embedding", "completed", "failed",
                    name="ingestionstatus"),
            server_default="pending",
        ),
        sa.Column("ingestion_progress", sa.Integer(), server_default=sa.text("0")),
        sa.Column("ingestion_error", sa.String(2048), nullable=True),
        sa.Column("total_chunks", sa.Integer(), server_default=sa.text("0")),
        sa.Column("owner_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        if_not_exists=True,
    )

    # --- documents (with pgvector embedding) ---
    op.create_table(
        "documents",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(1024), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("chunk_index", sa.Integer(), server_default=sa.text("0")),
        sa.Column("chunk_type", sa.String(50), nullable=True),
        sa.Column("language", sa.String(50), nullable=True),
        sa.Column("embedding", Vector(384)),
        sa.Column("repository_id", sa.Integer(), sa.ForeignKey("repositories.id"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        if_not_exists=True,
    )

    # --- llm_usage ---
    op.create_table(
        "llm_usage",
        sa.Column("id", sa.BigInteger(), primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"),
                  nullable=True, index=True),
        sa.Column("model", sa.String(255), nullable=False),
        sa.Column("endpoint", sa.String(512), nullable=True),
        sa.Column("input_tokens", sa.Integer(), server_default=sa.text("0")),
        sa.Column("output_tokens", sa.Integer(), server_default=sa.text("0")),
        sa.Column("cost_usd", sa.Numeric(10, 6), server_default=sa.text("0")),
        sa.Column("latency_ms", sa.Integer(), nullable=True),
        sa.Column("success", sa.Integer(), server_default=sa.text("1")),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        if_not_exists=True,
    )


def downgrade() -> None:
    op.drop_table("llm_usage")
    op.drop_table("documents")
    op.drop_table("repositories")
    op.drop_table("users")
    op.execute("DROP TYPE IF EXISTS ingestionstatus")
    op.execute("DROP EXTENSION IF EXISTS vector")
