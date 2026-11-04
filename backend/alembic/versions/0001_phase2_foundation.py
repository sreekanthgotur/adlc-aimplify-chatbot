"""Create foundational intake schema tables.

Revision ID: 0001_phase2_foundation
Revises:
Create Date: 2026-11-04
"""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "0001_phase2_foundation"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "schema_versions",
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("field_count", sa.Integer(), nullable=False),
        sa.Column("section_count", sa.Integer(), nullable=False),
        sa.Column("mandatory_count", sa.Integer(), nullable=False),
        sa.CheckConstraint("field_count = 27", name="ck_schema_field_count"),
        sa.CheckConstraint("section_count = 6", name="ck_schema_section_count"),
        sa.CheckConstraint("mandatory_count = 18", name="ck_schema_mandatory_count"),
        sa.PrimaryKeyConstraint("schema_version"),
    )
    op.create_table(
        "intake_sections",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("section_key", sa.String(length=64), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("ordinal", sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(["schema_version"], ["schema_versions.schema_version"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("schema_version", "section_key", name="uq_section_key"),
    )
    op.create_table(
        "canonical_field_definitions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("field_key", sa.String(length=128), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("section_key", sa.String(length=64), nullable=False),
        sa.Column("value_type", sa.String(length=32), nullable=False),
        sa.Column("mandatory", sa.Boolean(), nullable=False),
        sa.Column("fill_mode", sa.String(length=64), nullable=False),
        sa.Column("ai_writable", sa.Boolean(), nullable=False),
        sa.Column("declaration_only", sa.Boolean(), nullable=False),
        sa.Column("clarification_prompt", sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(["schema_version"], ["schema_versions.schema_version"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("schema_version", "field_key", name="uq_field_key"),
    )
    op.create_table(
        "idea_submissions",
        sa.Column("submission_id", sa.String(length=64), nullable=False),
        sa.Column("schema_version", sa.String(length=64), nullable=False),
        sa.Column("subject_ref", sa.String(length=255), nullable=False),
        sa.Column("status", sa.String(length=64), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.ForeignKeyConstraint(["schema_version"], ["schema_versions.schema_version"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("submission_id"),
    )
    op.create_table(
        "field_values",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("submission_id", sa.String(length=64), nullable=False),
        sa.Column("field_key", sa.String(length=128), nullable=False),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column("origin", sa.String(length=32), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.CheckConstraint("origin IN ('ai_extracted','human_entered')", name="ck_field_origin"),
        sa.CheckConstraint(
            "(field_key NOT IN ('declaration_accepted','submitter_signature','date_of_submission','reviewer_notes')) "
            "OR origin = 'human_entered'",
            name="ck_human_only_field_origin",
        ),
        sa.ForeignKeyConstraint(["submission_id"], ["idea_submissions.submission_id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("submission_id", "field_key", name="uq_submission_field"),
    )


def downgrade() -> None:
    op.drop_table("field_values")
    op.drop_table("idea_submissions")
    op.drop_table("canonical_field_definitions")
    op.drop_table("intake_sections")
    op.drop_table("schema_versions")

