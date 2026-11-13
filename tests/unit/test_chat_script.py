from scripts.chat import describe, new_session


def test_text_is_not_described():
    assert describe({"type": "text", "delta": "hi"}) is None
    assert describe({"type": "done"}) is None


def test_status_uses_a_friendly_label():
    assert describe({"type": "status", "tool": "search_dishes"}) == "  (searching dishes...)"
    assert describe({"type": "status", "tool": "new_tool"}) == "  (new_tool...)"


def test_quota_blocked_and_error():
    assert describe({"type": "quota", "left": 7}) == "  [7 messages left today]"
    assert "BLOCKED" in describe({"type": "blocked"})
    assert describe({"type": "error", "code": "quota_exceeded"}) == "  [error: quota_exceeded]"


def test_draft_shows_lines_and_total():
    out = describe(
        {
            "type": "draft",
            "restaurant": {"id": "r1", "name": "Nakhla Kitchen", "nameAr": "مطبخ النخلة"},
            "lines": [{"itemId": "i1", "name": "Kunafa", "nameAr": "كنافة", "priceHalalas": 1800, "qty": 2}],
            "totalHalalas": 3600,
        }
    )
    assert "Nakhla Kitchen: 2 x Kunafa = 36.00 SAR" in out


def test_session_id_is_long_enough_for_agentcore():
    assert len(new_session()) >= 33
    assert new_session() != new_session()
