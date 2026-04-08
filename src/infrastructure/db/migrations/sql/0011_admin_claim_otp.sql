-- One-time bootstrap OTP for first admin (see src/domain/admin_setup.py)
CREATE TABLE IF NOT EXISTS admin_claim_otp (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  otp_hash TEXT NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ NOT NULL,
  used_at TIMESTAMPTZ,
  claimed_by_user_id UUID REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_admin_claim_otp_pending ON admin_claim_otp (created_at DESC)
  WHERE used_at IS NULL;
