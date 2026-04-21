import json
import logging
import sys
from fastapi.testclient import TestClient
from main import app
from db.manager import db_manager

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_phase_5")

from db.manager import migration_runner
from main import app

def verify_multi_user_auth():
    logger.info("--- Phase 5: Multi-User & RBAC Verification ---")
    
    # 0. Ensure schema is updated
    migration_runner.run_initial_migration("schema.sql")
    
    client = TestClient(app)
    
    # 0. Cleanup
    conn = db_manager.connect()
    with conn:
        conn.execute("DELETE FROM users")
        conn.execute("DELETE FROM assets")
    
    # 1. Verify First Registration (becomes ADMIN)
    logger.info("Test 1: First user registration (Admin check)...")
    res1 = client.post("/auth/register", json={
        "username": "admin_user",
        "password": "password123",
        "full_name": "System Administrator",
        "role": "USER" # Should be overridden to ADMIN
    })
    assert res1.status_code == 200
    assert res1.json()["role"] == "ADMIN"
    logger.info("[OK] First user successfully promoted to ADMIN")

    # 2. Verify Second Registration (remains USER)
    logger.info("Test 2: Second user registration...")
    res2 = client.post("/auth/register", json={
        "username": "staff_user",
        "password": "password456",
        "full_name": "Staff Member",
        "role": "USER"
    })
    assert res2.status_code == 200
    assert res2.json()["role"] == "USER"
    logger.info("[OK] Second user remains USER")

    # 3. Verify Login & JWT
    logger.info("Test 3: Login (Staff)...")
    login_res = client.post("/auth/login", data={"username": "staff_user", "password": "password456"})
    assert login_res.status_code == 200
    staff_token = login_res.json()["access_token"]
    logger.info("[OK] Staff login successful, token received")

    # 4. Verify RBAC (Staff cannot create asset)
    logger.info("Test 4: RBAC Restriction (Staff -> Create Asset)...")
    asset_res = client.post("/assets/", 
        json={
            "ba_number": "BA-1234",
            "commission_date": "2024-01-01",
            "total_kms": 1000
        },
        headers={"Authorization": f"Bearer {staff_token}"}
    )
    assert asset_res.status_code == 403
    logger.info("[OK] Staff correctly blocked from admin restricted resource")

    # 5. Verify RBAC (Admin can create asset)
    logger.info("Test 5: RBAC Success (Admin -> Create Asset)...")
    admin_login = client.post("/auth/login", data={"username": "admin_user", "password": "password123"})
    admin_token = admin_login.json()["access_token"]
    
    admin_asset_res = client.post("/assets/", 
        json={
            "ba_number": "BA-9999",
            "commission_date": "2024-01-01",
            "total_kms": 1000,
            "serial_number": "SN-9999",
            "asset_group": "Logistics",
            "asset_type": "Truck"
        },
        headers={"Authorization": f"Bearer {admin_token}"}
    )
    assert admin_asset_res.status_code == 200
    assert admin_asset_res.json()["ba_number"] == "BA-9999"
    logger.info("[OK] Admin successfully created asset")

    logger.info("--- All Verification Tests Passed! ---")

if __name__ == "__main__":
    try:
        verify_multi_user_auth()
    except Exception as e:
        logger.error(f"Verification failed: {e}")
        sys.exit(1)
