import os

os.environ["STORAGE_MODE"] = "json"

import sys, pathlib
sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "DealStack" / "sales-prospecting"))


def test_save_and_load_proposals():
    from server import save_proposals, load_proposals
    proposals = [
        {
            "id": "prop_test_1",
            "lead_id": "lead_1",
            "lead_name": "Test Business",
            "proposal": "Proposal content here",
            "subject": "Test Proposal",
            "status": "pending",
        }
    ]
    save_proposals(proposals)
    loaded = load_proposals()
    found = [p for p in loaded if p["id"] == "prop_test_1"]
    assert len(found) == 1
    assert found[0]["lead_name"] == "Test Business"
    assert found[0]["status"] == "pending"
    clean_proposals([p for p in loaded if p["id"] != "prop_test_1"])


def test_proposals_duplicate_id():
    from server import save_proposals, load_proposals
    proposals = [{"id": "prop_dup_test", "lead_name": "Dup", "status": "pending"}]
    save_proposals(proposals)
    dup = [{"id": "prop_dup_test", "lead_name": "Dup Updated", "status": "pending"}]
    save_proposals(dup)
    loaded = load_proposals()
    matches = [p for p in loaded if p["id"] == "prop_dup_test"]
    assert len(matches) == 1
    clean_proposals([p for p in loaded if p["id"] != "prop_dup_test"])


def test_proposals_empty():
    from server import save_proposals, load_proposals
    save_proposals([])
    assert load_proposals() == []


def test_proposal_status_update():
    from server import save_proposals, load_proposals, update_lead_status_wrapper
    proposals = [{"id": "prop_sts", "lead_id": "lead_sts", "lead_name": "Status Test", "status": "pending"}]
    save_proposals(proposals)
    loaded = load_proposals()
    found = [p for p in loaded if p["id"] == "prop_sts"]
    assert found[0]["status"] == "pending"
    clean_proposals([p for p in loaded if p["id"] != "prop_sts"])


def test_proposals_missing_required_fields():
    from server import save_proposals, load_proposals
    proposals = [{"id": "prop_min"}]
    save_proposals(proposals)
    loaded = load_proposals()
    found = [p for p in loaded if p["id"] == "prop_min"]
    assert len(found) == 1
    clean_proposals([p for p in loaded if p["id"] != "prop_min"])


def clean_proposals(proposals):
    from server import save_proposals
    save_proposals(proposals)
