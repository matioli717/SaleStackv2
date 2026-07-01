def _filter_leads_for_tenant(leads, tenant_id):
    return [l for l in leads if not l.get("tenant_id") or l.get("tenant_id") == tenant_id]


def test_tenant_sees_own_leads():
    leads = [
        {"id": "1", "tenant_id": "tenant_a"},
        {"id": "2", "tenant_id": "tenant_a"},
        {"id": "3", "tenant_id": "tenant_b"},
    ]
    result = _filter_leads_for_tenant(leads, "tenant_a")
    assert len(result) == 2
    assert all(l["tenant_id"] == "tenant_a" for l in result)


def test_tenant_does_not_see_other_tenant_leads():
    leads = [
        {"id": "1", "tenant_id": "tenant_a"},
        {"id": "2", "tenant_id": "tenant_b"},
    ]
    result = _filter_leads_for_tenant(leads, "tenant_a")
    assert len(result) == 1
    assert result[0]["tenant_id"] == "tenant_a"


def test_lead_without_tenant_id_is_visible_to_all():
    leads = [
        {"id": "1"},
        {"id": "2", "tenant_id": "tenant_a"},
    ]
    result_a = _filter_leads_for_tenant(leads, "tenant_a")
    result_b = _filter_leads_for_tenant(leads, "tenant_b")
    assert len(result_a) == 2
    assert len(result_b) == 1  # only the untagged lead


def test_empty_leads_list():
    assert _filter_leads_for_tenant([], "tenant_a") == []


def test_tenant_id_none():
    leads = [{"id": "1", "tenant_id": None}]
    result = _filter_leads_for_tenant(leads, "tenant_a")
    assert len(result) == 1


def test_multiple_tenants_isolation():
    leads = [
        {"id": "1", "tenant_id": "t1"},
        {"id": "2", "tenant_id": "t2"},
        {"id": "3", "tenant_id": "t3"},
        {"id": "4"},
    ]
    assert len(_filter_leads_for_tenant(leads, "t1")) == 2
    assert len(_filter_leads_for_tenant(leads, "t2")) == 2
    assert len(_filter_leads_for_tenant(leads, "t3")) == 2
    assert len(_filter_leads_for_tenant(leads, "t4")) == 1
