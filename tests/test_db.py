from engine.db import DB, ETAPAS


def test_ciclo_de_vida_do_video(tmp_path):
    db = DB(tmp_path / "engine.db")
    video_id = db.add_video("/tmp/live.mp4", title="live")
    assert db.add_video("/tmp/live.mp4") == video_id  # idempotente por path

    assert [db.stage_status(video_id, e) for e in ETAPAS] == ["pending"] * len(ETAPAS)
    db.set_stage(video_id, "ingest", "done")
    db.set_stage(video_id, "audio", "failed", "boom")
    assert db.stage_status(video_id, "ingest") == "done"
    falhas = [s for s in db.stages_do_video(video_id) if s["status"] == "failed"]
    assert falhas[0]["error"] == "boom"


def test_momentos_e_clips(tmp_path):
    db = DB(tmp_path / "engine.db")
    video_id = db.add_video("/tmp/live.mp4")
    mid = db.add_moment(video_id, 10.0, 55.0, 9.5, "rage épico", "chat explodiu")
    db.add_moment(video_id, 120.0, 150.0, 7.0, "explicação", "contexto")
    momentos = db.moments(video_id)
    assert [m["score"] for m in momentos] == [9.5, 7.0]  # ordenado por score

    db.set_moment_status(mid, "rendered")
    assert db.moments(video_id, status="pending")[0]["title"] == "explicação"

    clip_id = db.add_clip(mid, "/tmp/clip.mp4", "h264_amf")
    clips = db.clips(video_id)
    assert clips[0]["id"] == clip_id
    assert clips[0]["encoder"] == "h264_amf"
    assert clips[0]["title"] == "rage épico"

    db.clear_moments(video_id)
    assert db.moments(video_id) == []
    assert db.clips(video_id) == []
