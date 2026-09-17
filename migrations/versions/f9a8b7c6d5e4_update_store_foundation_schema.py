"""update_store_foundation_schema

Revision ID: f9a8b7c6d5e4
Revises: 9681f69c7a43
Create Date: 2026-09-17 00:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = 'f9a8b7c6d5e4'
down_revision: Union[str, Sequence[str], None] = '9681f69c7a43'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------------------------------------------------------------------------
    # stores updates — exact 10 attributes
    # store_id, name, legal_name, default_currency, country_code, timezone, status, version, created_at, updated_at
    # ---------------------------------------------------------------------------
    op.execute("""
    DO $$ 
    BEGIN 
        -- Rename currency to default_currency if needed
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='stores' AND column_name='currency') 
           AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='stores' AND column_name='default_currency') THEN
            ALTER TABLE stores RENAME COLUMN currency TO default_currency;
        END IF;

        -- Drop legacy/extra columns if present
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='stores' AND column_name='slug') THEN
            ALTER TABLE stores DROP COLUMN slug CASCADE;
        END IF;
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='stores' AND column_name='email') THEN
            ALTER TABLE stores DROP COLUMN email CASCADE;
        END IF;
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='stores' AND column_name='phone') THEN
            ALTER TABLE stores DROP COLUMN phone CASCADE;
        END IF;

        -- Adjust column types/lengths
        ALTER TABLE stores ALTER COLUMN name TYPE VARCHAR(160);
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='stores' AND column_name='legal_name') THEN
            ALTER TABLE stores ALTER COLUMN legal_name TYPE VARCHAR(200);
        END IF;
        ALTER TABLE stores ALTER COLUMN timezone TYPE VARCHAR(64);
        ALTER TABLE stores ALTER COLUMN default_currency TYPE CHAR(3);
        ALTER TABLE stores ALTER COLUMN status TYPE VARCHAR(24);
        ALTER TABLE stores ALTER COLUMN status SET DEFAULT 'ACTIVE';
        ALTER TABLE stores ALTER COLUMN version SET DEFAULT 1;
    END $$;
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_stores_status ON stores (status);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_stores_created_at ON stores (created_at);")

    # ---------------------------------------------------------------------------
    # store_settings updates — exact 12 attributes
    # settings_id, store_id, order_prefix, weight_unit, dimension_unit, tax_inclusive, allow_guest_checkout, inventory_policy, checkout_expiry_minutes, version, config, updated_at
    # ---------------------------------------------------------------------------
    op.execute("""
    DO $$ 
    BEGIN 
        -- Rename setting_id to settings_id if needed
        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='store_settings' AND column_name='setting_id') 
           AND NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='store_settings' AND column_name='settings_id') THEN
            ALTER TABLE store_settings RENAME COLUMN setting_id TO settings_id;
        END IF;

        -- Add missing columns
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='store_settings' AND column_name='dimension_unit') THEN
            ALTER TABLE store_settings ADD COLUMN dimension_unit VARCHAR(8) DEFAULT 'cm' NOT NULL;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='store_settings' AND column_name='version') THEN
            ALTER TABLE store_settings ADD COLUMN version BIGINT DEFAULT 1 NOT NULL;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='store_settings' AND column_name='config') THEN
            ALTER TABLE store_settings ADD COLUMN config JSONB DEFAULT '{}' NOT NULL;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='store_settings' AND column_name='updated_at') THEN
            ALTER TABLE store_settings ADD COLUMN updated_at TIMESTAMPTZ DEFAULT now() NOT NULL;
        END IF;

        ALTER TABLE store_settings ALTER COLUMN order_prefix SET DEFAULT 'ORD';
        ALTER TABLE store_settings ALTER COLUMN inventory_policy SET DEFAULT 'DENY';
    END $$;
    """)

    # ---------------------------------------------------------------------------
    # sales_channels updates — exact 8 attributes
    # channel_id, store_id, name, channel_type, status, config, version, created_at
    # ---------------------------------------------------------------------------
    op.execute("""
    DO $$ 
    BEGIN 
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='sales_channels' AND column_name='status') THEN
            ALTER TABLE sales_channels ADD COLUMN status VARCHAR(24) DEFAULT 'ACTIVE' NOT NULL;
        END IF;

        IF EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='sales_channels' AND column_name='is_active') THEN
            ALTER TABLE sales_channels DROP COLUMN is_active CASCADE;
        END IF;

        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='sales_channels' AND column_name='config') THEN
            ALTER TABLE sales_channels ADD COLUMN config JSONB DEFAULT '{}' NOT NULL;
        END IF;
        IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_name='sales_channels' AND column_name='version') THEN
            ALTER TABLE sales_channels ADD COLUMN version BIGINT DEFAULT 1 NOT NULL;
        END IF;

        ALTER TABLE sales_channels ALTER COLUMN channel_type TYPE VARCHAR(32);
        ALTER TABLE sales_channels ALTER COLUMN name TYPE VARCHAR(100);
    END $$;
    """)

    op.execute("""
    DO $$ 
    BEGIN 
        IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='uq_sales_channels_store_name') THEN
            ALTER TABLE sales_channels ADD CONSTRAINT uq_sales_channels_store_name UNIQUE (store_id, name);
        END IF;
    END $$;
    """)

    op.execute("CREATE INDEX IF NOT EXISTS ix_sales_channels_store_id ON sales_channels (store_id);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sales_channels_channel_type ON sales_channels (channel_type);")
    op.execute("CREATE INDEX IF NOT EXISTS ix_sales_channels_status ON sales_channels (status);")


def downgrade() -> None:
    pass
