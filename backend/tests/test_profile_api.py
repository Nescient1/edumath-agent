from fastapi.testclient import TestClient

from app.main import app


def _cleanup_student(student_id: str) -> None:
    try:
        from app.repositories.profile_repository import _connect_pg

        with _connect_pg() as conn:
            with conn.cursor() as cur:
                cur.execute("DELETE FROM students WHERE id = %s", (student_id,))
    except Exception:
        pass


def test_profile_can_be_edited_and_wrong_record_status_can_update():
    client = TestClient(app)
    student_id = "PROFILE_API_TEST"
    _cleanup_student(student_id)
    try:
        profile_resp = client.put(
            f"/api/profile/{student_id}",
            json={
                "name": "测试学生",
                "grade": "高三",
                "target_score": 130,
                "current_score": 105,
                "textbook_version": "人教A版",
                "current_topic": "导数",
                "learning_goal": "补齐导数单调性",
            },
        )
        assert profile_resp.status_code == 200
        profile = profile_resp.json()
        assert profile["target_score"] == 130
        assert profile["current_topic"] == "导数"

        diagnose_resp = client.post(
            "/api/diagnose",
            json={
                "student_id": student_id,
                "question_text": "已知函数 f(x)=x^3-3x，求单调区间。",
                "student_answer": "只会求导，不会判断区间。",
            },
        )
        assert diagnose_resp.status_code == 200

        records_resp = client.get(f"/api/profile/{student_id}/records")
        assert records_resp.status_code == 200
        records = records_resp.json()
        assert records

        record_id = records[0]["id"]
        patch_resp = client.patch(
            f"/api/profile/{student_id}/records/{record_id}",
            json={"review_status": "已复习", "is_mastered": True},
        )
        assert patch_resp.status_code == 200
        patched = patch_resp.json()
        assert patched["review_status"] == "已复习"
        assert patched["is_mastered"] is True

        paged_resp = client.get(f"/api/profile/{student_id}/records?limit=1&offset=0")
        assert paged_resp.status_code == 200
        assert len(paged_resp.json()) <= 1

        advice_resp = client.post(f"/api/profile/{student_id}/advice")
        assert advice_resp.status_code == 200
        advice = advice_resp.json()
        assert "summary" in advice
        assert isinstance(advice["priority_points"], list)

        cached_profile_resp = client.get(f"/api/profile/{student_id}")
        assert cached_profile_resp.status_code == 200
        cached_profile = cached_profile_resp.json()
        assert cached_profile["advice"]["summary"] == advice["summary"]
    finally:
        _cleanup_student(student_id)


def test_profile_read_does_not_call_llm(monkeypatch):
    client = TestClient(app)
    student_id = "PROFILE_FAST_READ_TEST"
    _cleanup_student(student_id)
    try:
        import app.services.profile_service as profile_service
        from app.core.config import settings

        monkeypatch.setattr(settings, "enable_llm_profile_advice", "1")
        monkeypatch.setattr(settings, "openai_api_key", "fake-key")
        monkeypatch.setattr(profile_service, "is_llm_enabled", lambda: True)

        def fail_if_called(*args, **kwargs):
            raise AssertionError("GET /profile should not call LLM")

        monkeypatch.setattr(profile_service, "safe_generate_text", fail_if_called)

        resp = client.get(f"/api/profile/{student_id}")
        assert resp.status_code == 200
        assert resp.json()["student_id"] == student_id
    finally:
        _cleanup_student(student_id)
