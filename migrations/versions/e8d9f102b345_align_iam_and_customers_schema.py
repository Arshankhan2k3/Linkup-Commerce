"""align_iam_and_customers_schema

Revision ID: e8d9f102b345
Revises: d7c72d34a266
Create Date: 2026-09-16 02:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'e8d9f102b345'
down_revision: Union[str, Sequence[str], None] = 'd7c72d34a266'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------------------------------------------------------------------------
    # IAM schema updates
    # ---------------------------------------------------------------------------
    # users: add phone, status, email_verified_at; adjust constraints
    op.add_column('users', sa.Column('phone', sa.String(length=32), nullable=True))
    op.add_column('users', sa.Column('status', sa.String(length=24), server_default='ACTIVE', nullable=False))
    op.add_column('users', sa.Column('email_verified_at', sa.DateTime(timezone=True), nullable=True))

    # permissions: add module, created_at, adjust code length
    op.add_column('permissions', sa.Column('module', sa.String(length=50), server_default='General', nullable=False))
    op.add_column('permissions', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.alter_column('permissions', 'code', type_=sa.String(length=100))

    # role_permissions: add created_at
    op.add_column('role_permissions', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))

    # roles: adjust name length & description type
    op.alter_column('roles', 'name', type_=sa.String(length=80))
    op.alter_column('roles', 'description', type_=sa.Text())

    # staff_members: add is_owner, allow display_name nullable, add index on status
    op.add_column('staff_members', sa.Column('is_owner', sa.Boolean(), server_default='false', nullable=False))
    op.alter_column('staff_members', 'display_name', nullable=True, type_=sa.String(length=140))
    op.create_index('ix_staff_members_status', 'staff_members', ['status'])

    # staff_member_roles: add created_at
    op.add_column('staff_member_roles', sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))

    # refresh_tokens: add parent_token_id, replaced_by_token_id, device_info (JSONB), revoked_at
    op.add_column('refresh_tokens', sa.Column('parent_token_id', sa.UUID(), sa.ForeignKey('refresh_tokens.token_id', ondelete='SET NULL'), nullable=True))
    op.add_column('refresh_tokens', sa.Column('replaced_by_token_id', sa.UUID(), sa.ForeignKey('refresh_tokens.token_id', ondelete='SET NULL'), nullable=True))
    op.add_column('refresh_tokens', sa.Column('device_info', postgresql.JSONB(), server_default='{}', nullable=False))
    op.add_column('refresh_tokens', sa.Column('revoked_at', sa.DateTime(timezone=True), nullable=True))
    op.create_index('ix_refresh_tokens_expires_at', 'refresh_tokens', ['expires_at'])
    op.create_index('ix_refresh_tokens_revoked_at', 'refresh_tokens', ['revoked_at'])

    # ---------------------------------------------------------------------------
    # Customer schema updates
    # ---------------------------------------------------------------------------
    # customers: allow first_name, last_name nullable
    op.alter_column('customers', 'first_name', nullable=True)
    op.alter_column('customers', 'last_name', nullable=True)
    op.create_index('ix_customers_email', 'customers', ['email'])
    op.create_index('ix_customers_phone', 'customers', ['phone'])
    op.create_index('ix_customers_created_at', 'customers', ['created_at'])

    # customer_addresses: add label, line1, line2, state, updated_at
    op.add_column('customer_addresses', sa.Column('label', sa.String(length=50), nullable=True))
    op.add_column('customer_addresses', sa.Column('line1', sa.String(length=255), server_default='', nullable=False))
    op.add_column('customer_addresses', sa.Column('line2', sa.String(length=255), nullable=True))
    op.add_column('customer_addresses', sa.Column('state', sa.String(length=120), server_default='', nullable=False))
    op.add_column('customer_addresses', sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.alter_column('customer_addresses', 'first_name', nullable=True)
    op.alter_column('customer_addresses', 'last_name', nullable=True)
    op.create_index('ix_customer_addresses_postal_code', 'customer_addresses', ['postal_code'])

    # customer_consents: channel, purpose, state, source, occurred_at, metadata
    op.add_column('customer_consents', sa.Column('channel', sa.String(length=24), server_default='EMAIL', nullable=False))
    op.add_column('customer_consents', sa.Column('purpose', sa.String(length=40), server_default='MARKETING', nullable=False))
    op.add_column('customer_consents', sa.Column('state', sa.String(length=24), server_default='SUBSCRIBED', nullable=False))
    op.add_column('customer_consents', sa.Column('source', sa.String(length=50), nullable=True))
    op.add_column('customer_consents', sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False))
    op.add_column('customer_consents', sa.Column('metadata', postgresql.JSONB(), server_default='{}', nullable=False))
    op.create_index('ix_customer_consents_channel', 'customer_consents', ['channel'])
    op.create_index('ix_customer_consents_occurred_at', 'customer_consents', ['occurred_at'])

    # customer_notes: customer_note_id, actor_staff_member_id
    op.add_column('customer_notes', sa.Column('actor_staff_member_id', sa.UUID(), sa.ForeignKey('staff_members.staff_member_id', ondelete='SET NULL'), nullable=True))
    op.create_index('ix_customer_notes_created_at', 'customer_notes', ['created_at'])


def downgrade() -> None:
    pass
