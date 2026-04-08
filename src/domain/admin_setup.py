"""
Admin User Setup & Claim System
Erster Start Admin Claim Prozess
"""
from __future__ import annotations

import os
import secrets
import logging
from datetime import datetime, timedelta, timezone

from src.infrastructure.db import db
from src.infrastructure.auth import create_user, hash_password, insert_user_with_cursor, verify_password

logger = logging.getLogger(__name__)


ADMIN_CLAIM_OTP_ENV = "AGENT_ADMIN_CLAIM_OTP"


def generate_admin_claim_otp() -> str:
    """
    Generiere einmaligen OTP für ersten Admin Claim
    Wird beim ersten Start in Log und optional in ENV ausgegeben
    """
    otp = secrets.token_urlsafe(24)

    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            # Lösche alte Claim OTPs
            cur.execute("DELETE FROM admin_claim_otp")

            # Speichere neuen OTP gültig für 24h
            cur.execute("""
                INSERT INTO admin_claim_otp (otp_hash, expires_at)
                VALUES (%s, %s)
            """, (
                hash_password(otp),
                datetime.now(timezone.utc) + timedelta(hours=24)
            ))
            conn.commit()

    # Gib OTP im Terminal Log aus
    logger.info("")
    logger.info("=" * 80)
    logger.info("  🎯 ERSTER START ADMIN CLAIM")
    logger.info("")
    logger.info(f"  Admin Claim OTP: {otp}")
    logger.info("")
    logger.info("  Öffne /control/claim.html und trage OTP + E-Mail + Passwort ein")
    logger.info("  Dieser OTP ist 24 Stunden gültig")
    logger.info("=" * 80)
    logger.info("")

    # Optional: Setze als Env Variable für Docker Logs
    os.environ[ADMIN_CLAIM_OTP_ENV] = otp

    return otp


def claim_admin_user(email: str, password: str, otp: str) -> bool:
    """
    Claim ersten Admin User mit OTP.
    Uses one DB transaction + advisory lock so parallel claims cannot create two admins.
    """
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT pg_advisory_xact_lock(872814001)")
            cur.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
            if cur.fetchone()[0] > 0:
                conn.rollback()
                return False

            cur.execute(
                """
                SELECT otp_hash, expires_at
                FROM admin_claim_otp
                WHERE used_at IS NULL
                ORDER BY created_at DESC
                LIMIT 1
                FOR UPDATE
                """
            )
            row = cur.fetchone()

            if not row:
                conn.rollback()
                return False

            otp_hash, expires_at = row

            if not verify_password(otp, otp_hash):
                conn.rollback()
                return False

            now_utc = datetime.now(timezone.utc)
            if now_utc > expires_at:
                conn.rollback()
                return False

            user = insert_user_with_cursor(cur, email, password, role="admin")

            cur.execute(
                """
                UPDATE admin_claim_otp
                SET used_at = NOW(), claimed_by_user_id = %s
                WHERE otp_hash = %s
                """,
                (user.id, otp_hash),
            )
        conn.commit()

    logger.info("✅ Admin User erfolgreich erstellt: %s", email)
    return True


def is_first_start() -> bool:
    """
    Prüfe ob es der erste Start ist und kein Admin User existiert
    """
    with db.pool().connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM users WHERE role = 'admin'")
            admin_count = cur.fetchone()[0]
            return admin_count == 0


def setup_admin_claim_if_needed() -> None:
    """
    Wenn noch kein Admin existiert generiere Claim OTP
    Wird automatisch bei Startup aufgerufen
    """
    if is_first_start():
        generate_admin_claim_otp()


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 3:
        print("Benutzung: PYTHONPATH=/app python -m src.domain.admin_setup <email> <passwort>")
        print("Erstellt oder aktualisiert Admin User direkt über Kommandozeile (Container-DB).")
        sys.exit(1)

    email = sys.argv[1]
    password = sys.argv[2]

    db.init_pool()

    from src.infrastructure.auth import get_user_by_email, update_user_password

    existing = get_user_by_email(email)

    if existing:
        update_user_password(existing.id, password)
        print(f"ℹ️  User existiert bereits: {email}")
        print("ℹ️  Passwort wurde aktualisiert")
    else:
        create_user(email, password, role="admin")
        print(f"✅ Admin User erfolgreich erstellt: {email}")

    print("✅ Anmeldung: /control/login.html")
