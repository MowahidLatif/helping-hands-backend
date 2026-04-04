"""fee policy fields + settlements/payout ledger

Revision ID: 0024_fee_policy_settlements
Revises: 0023_ai_site_recipe
"""

from alembic import op

revision = "0024_fee_policy_settlements"
down_revision = "0023_ai_site_recipe"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        ALTER TABLE campaigns
        ADD COLUMN IF NOT EXISTS fee_option TEXT NOT NULL DEFAULT 'donor_pays',
        ADD COLUMN IF NOT EXISTS fee_policy_version TEXT NOT NULL DEFAULT 'v1';
        """
    )
    op.execute(
        """
        ALTER TABLE organizations
        ADD COLUMN IF NOT EXISTS stripe_connect_account_id TEXT NULL,
        ADD COLUMN IF NOT EXISTS payout_account_ready BOOLEAN NOT NULL DEFAULT FALSE,
        ADD COLUMN IF NOT EXISTS payout_onboarding_status TEXT NOT NULL DEFAULT 'not_started',
        ADD COLUMN IF NOT EXISTS payouts_enabled BOOLEAN NOT NULL DEFAULT FALSE;
        """
    )
    op.execute(
        """
        ALTER TABLE donations
        ADD COLUMN IF NOT EXISTS fee_option TEXT NULL,
        ADD COLUMN IF NOT EXISTS fee_policy_version TEXT NULL,
        ADD COLUMN IF NOT EXISTS stripe_balance_transaction_id TEXT NULL,
        ADD COLUMN IF NOT EXISTS stripe_processing_fee_cents INTEGER NULL,
        ADD COLUMN IF NOT EXISTS platform_fee_percent NUMERIC(5,2) NULL,
        ADD COLUMN IF NOT EXISTS platform_fee_cents INTEGER NULL,
        ADD COLUMN IF NOT EXISTS donor_fee_cents INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS platform_absorbed_fee_cents INTEGER NOT NULL DEFAULT 0,
        ADD COLUMN IF NOT EXISTS net_to_org_cents INTEGER NULL;
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS campaign_settlements (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          campaign_id UUID NOT NULL UNIQUE REFERENCES campaigns(id) ON DELETE CASCADE,
          org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
          fee_option TEXT NOT NULL,
          fee_policy_version TEXT NOT NULL DEFAULT 'v1',
          gross_raised_cents INTEGER NOT NULL DEFAULT 0,
          stripe_fee_cents INTEGER NOT NULL DEFAULT 0,
          platform_fee_cents INTEGER NOT NULL DEFAULT 0,
          donor_covered_fee_cents INTEGER NOT NULL DEFAULT 0,
          platform_absorbed_fee_cents INTEGER NOT NULL DEFAULT 0,
          refunded_cents INTEGER NOT NULL DEFAULT 0,
          disputed_cents INTEGER NOT NULL DEFAULT 0,
          net_payout_cents INTEGER NOT NULL DEFAULT 0,
          status TEXT NOT NULL DEFAULT 'pending',
          payout_attempts INTEGER NOT NULL DEFAULT 0,
          last_error TEXT NULL,
          settled_at TIMESTAMPTZ NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        """
        CREATE TABLE IF NOT EXISTS campaign_payouts (
          id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
          settlement_id UUID NOT NULL REFERENCES campaign_settlements(id) ON DELETE CASCADE,
          campaign_id UUID NOT NULL REFERENCES campaigns(id) ON DELETE CASCADE,
          org_id UUID NOT NULL REFERENCES organizations(id) ON DELETE CASCADE,
          amount_cents INTEGER NOT NULL,
          currency TEXT NOT NULL DEFAULT 'usd',
          idempotency_key TEXT NOT NULL UNIQUE,
          stripe_transfer_id TEXT NULL UNIQUE,
          stripe_payout_id TEXT NULL,
          status TEXT NOT NULL DEFAULT 'initiated',
          failure_reason TEXT NULL,
          raw JSONB NULL,
          created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
          updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
        );
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_campaign_settlements_org_id
        ON campaign_settlements(org_id, created_at DESC);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_campaign_payouts_campaign_id
        ON campaign_payouts(campaign_id, created_at DESC);
        """
    )
    op.execute(
        """
        CREATE INDEX IF NOT EXISTS ix_campaign_payouts_settlement_id
        ON campaign_payouts(settlement_id, created_at DESC);
        """
    )


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_campaign_payouts_settlement_id;")
    op.execute("DROP INDEX IF EXISTS ix_campaign_payouts_campaign_id;")
    op.execute("DROP INDEX IF EXISTS ix_campaign_settlements_org_id;")
    op.execute("DROP TABLE IF EXISTS campaign_payouts;")
    op.execute("DROP TABLE IF EXISTS campaign_settlements;")
    op.execute(
        """
        ALTER TABLE donations
        DROP COLUMN IF EXISTS net_to_org_cents,
        DROP COLUMN IF EXISTS platform_absorbed_fee_cents,
        DROP COLUMN IF EXISTS donor_fee_cents,
        DROP COLUMN IF EXISTS platform_fee_cents,
        DROP COLUMN IF EXISTS platform_fee_percent,
        DROP COLUMN IF EXISTS stripe_processing_fee_cents,
        DROP COLUMN IF EXISTS stripe_balance_transaction_id,
        DROP COLUMN IF EXISTS fee_policy_version,
        DROP COLUMN IF EXISTS fee_option;
        """
    )
    op.execute(
        """
        ALTER TABLE organizations
        DROP COLUMN IF EXISTS payouts_enabled,
        DROP COLUMN IF EXISTS payout_onboarding_status,
        DROP COLUMN IF EXISTS payout_account_ready,
        DROP COLUMN IF EXISTS stripe_connect_account_id;
        """
    )
    op.execute(
        """
        ALTER TABLE campaigns
        DROP COLUMN IF EXISTS fee_policy_version,
        DROP COLUMN IF EXISTS fee_option;
        """
    )
