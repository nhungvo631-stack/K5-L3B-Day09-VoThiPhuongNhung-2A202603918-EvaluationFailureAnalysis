import json

from lab8.db import connect
from lab8.durability import get_refund
from lab8.shapes.workflow import run_claim


def _add_claim(conn, claim_id, order_id, approval_id):
    conn.execute(
        """
        INSERT INTO claims (
            claim_id, principal_id, order_id, ticket, parent_secret, raw_headers_json, approval_id
        )
        VALUES (?, 'P-100', ?, 'test', 'CANARY_SECRET_PARENT', '{}', ?)
        """,
        (claim_id, order_id, approval_id),
    )


def _assert_denied_by_host(store, claim_id, result, reason):
    conn = connect(store)
    try:
        effect = get_refund(conn, claim_id)
        rows = conn.execute(
            """
            SELECT details_json FROM audit_events
            WHERE claim_id = ? AND event_type = 'policy_denied'
            """,
            (claim_id,),
        ).fetchall()
    finally:
        conn.close()

    assert result.status == "denied"
    assert result.proposal_amount > 0
    assert result.committed_audit_count == 0
    assert effect is None
    assert any(json.loads(row["details_json"]).get("reason") == reason for row in rows)


def test_revoked_approval_is_denied_by_host(public_db):
    conn = connect(public_db)
    conn.execute(
        """
        INSERT INTO approvals (approval_id, claim_id, approved_vnd, status, expires_at)
        VALUES ('A-WF-REVOKED', 'C-WF-REVOKED', 35000, 'revoked', '2027-12-31')
        """
    )
    _add_claim(conn, "C-WF-REVOKED", "O-107", "A-WF-REVOKED")
    conn.commit()
    conn.close()

    result = run_claim("C-WF-REVOKED", seed=11, store_path=str(public_db))

    _assert_denied_by_host(public_db, "C-WF-REVOKED", result, "approval_revoked")


def test_approval_for_another_claim_is_denied_by_host(public_db):
    conn = connect(public_db)
    _add_claim(conn, "C-WF-BORROWED", "O-107", "A-001")
    conn.commit()
    conn.close()

    result = run_claim("C-WF-BORROWED", seed=11, store_path=str(public_db))

    _assert_denied_by_host(public_db, "C-WF-BORROWED", result, "approval_claim_mismatch")


def test_fully_refunded_order_is_denied_by_host(public_db):
    result = run_claim("C-013", seed=11, store_path=str(public_db))

    _assert_denied_by_host(public_db, "C-013", result, "order_already_refunded")
