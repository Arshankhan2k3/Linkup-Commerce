"""recreate customer addresses table

Revision ID: 9681f69c7a43
Revises: 0607e3b2c72c
Create Date: 2026-09-16 11:38:13.070807

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = '9681f69c7a43'
down_revision: Union[str, Sequence[str], None] = '0607e3b2c72c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.execute("DROP TABLE IF EXISTS customer_addresses CASCADE")
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='customer_notes' AND column_name='note_id') THEN ALTER TABLE customer_notes RENAME COLUMN note_id TO customer_note_id; END IF; END $$;")
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='store_id') THEN ALTER TABLE users DROP COLUMN store_id; END IF; END $$;")
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='users' AND column_name='is_active') THEN ALTER TABLE users DROP COLUMN is_active; END IF; END $$;")
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='staff_members' AND column_name='updated_at') THEN ALTER TABLE staff_members DROP COLUMN updated_at; END IF; END $$;")
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='refresh_tokens' AND column_name='is_consumed') THEN ALTER TABLE refresh_tokens DROP COLUMN is_consumed; END IF; END $$;")
    op.execute("DO $$ BEGIN IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='refresh_tokens' AND column_name='user_agent') THEN ALTER TABLE refresh_tokens DROP COLUMN user_agent; END IF; END $$;")
    op.create_table(
        'customer_addresses',
        sa.Column('address_id', sa.UUID(), nullable=False),
        sa.Column('customer_id', sa.UUID(), sa.ForeignKey('customers.customer_id', ondelete='CASCADE'), nullable=False),
        sa.Column('label', sa.String(length=50), nullable=True),
        sa.Column('first_name', sa.String(length=100), nullable=True),
        sa.Column('last_name', sa.String(length=100), nullable=True),
        sa.Column('phone', sa.String(length=32), nullable=True),
        sa.Column('line1', sa.String(length=255), nullable=False),
        sa.Column('line2', sa.String(length=255), nullable=True),
        sa.Column('city', sa.String(length=120), nullable=False),
        sa.Column('state', sa.String(length=120), nullable=False),
        sa.Column('postal_code', sa.String(length=24), nullable=False),
        sa.Column('country_code', sa.CHAR(length=2), nullable=False),
        sa.Column('is_default', sa.Boolean(), server_default='false', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('address_id')
    )
    op.create_index(
        'ix_customer_addresses_default',
        'customer_addresses',
        ['customer_id'],
        unique=True,
        postgresql_where=sa.text('is_default = true')
    )
    op.create_index('ix_customer_addresses_customer_id', 'customer_addresses', ['customer_id'], unique=False)
    op.create_index('ix_customer_addresses_postal_code', 'customer_addresses', ['postal_code'], unique=False)

    # Recreate customer_consents table
    op.execute("DROP TABLE IF EXISTS customer_consents CASCADE")
    op.create_table(
        'customer_consents',
        sa.Column('consent_id', sa.UUID(), nullable=False),
        sa.Column('customer_id', sa.UUID(), sa.ForeignKey('customers.customer_id', ondelete='CASCADE'), nullable=False),
        sa.Column('channel', sa.String(length=24), nullable=False),
        sa.Column('purpose', sa.String(length=40), nullable=False),
        sa.Column('state', sa.String(length=24), nullable=False),
        sa.Column('source', sa.String(length=50), nullable=True),
        sa.Column('ip_address', postgresql.INET(), nullable=True),
        sa.Column('occurred_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('metadata', postgresql.JSONB(), server_default='{}', nullable=False),
        sa.PrimaryKeyConstraint('consent_id')
    )
    op.create_index('ix_customer_consents_customer_id', 'customer_consents', ['customer_id'], unique=False)
    op.create_index('ix_customer_consents_channel', 'customer_consents', ['channel'], unique=False)
    op.create_index('ix_customer_consents_occurred_at', 'customer_consents', ['occurred_at'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_customer_consents_occurred_at', table_name='customer_consents')
    op.drop_index('ix_customer_consents_channel', table_name='customer_consents')
    op.drop_index('ix_customer_consents_customer_id', table_name='customer_consents')
    op.drop_table('customer_consents')

    op.drop_index('ix_customer_addresses_postal_code', table_name='customer_addresses')
    op.drop_index('ix_customer_addresses_customer_id', table_name='customer_addresses')
    op.drop_index('ix_customer_addresses_default', table_name='customer_addresses', postgresql_where=sa.text('is_default = true'))
    op.drop_table('customer_addresses')
