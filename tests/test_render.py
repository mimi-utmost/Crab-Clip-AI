from pathlib import Path

from engine.config import Config
from engine.stages.render import _args_encoder, _filtro_video, montar_comando


def _cfg(tmp_path: Path) -> Config:
    return Config(ffmpeg=tmp_path / "ffmpeg.exe", whisper_cli=tmp_path / "w.exe",
                  llama_server=tmp_path / "s.exe", whisper_model=tmp_path / "m.bin",
                  llm_model=tmp_path / "l.gguf")


def test_filtro_vertical_1080p():
    vf = _filtro_video(1920, 1080, "captions-1.ass")
    assert vf == ("crop=608:1080:656:0,scale=1080:1920,setsar=1,"
                  "subtitles='captions-1.ass'")


def test_filtro_vertical_outras_resolucoes():
    assert _filtro_video(1280, 720, "a.ass").startswith("crop=404:720:438:0")
    assert _filtro_video(2560, 1440, "a.ass").startswith("crop=810:1440:875:0")


def test_encoders():
    amf = _args_encoder("h264_amf")
    x264 = _args_encoder("libx264")
    assert "h264_amf" in amf
    assert "libx264" in x264


def test_montar_comando(tmp_path):
    cfg = _cfg(tmp_path)
    cmd = [str(a) for a in montar_comando(cfg, "video.mp4", 10.0, 70.0, 1920, 1080,
                                          "captions-1.ass", "clip-001.mp4", "h264_amf")]
    assert cmd[0].endswith("ffmpeg.exe")
    i_ss, i_to = cmd.index("-ss"), cmd.index("-to")
    assert cmd[i_ss + 1] == "10.00"
    assert cmd[i_to + 1] == "70.00"
    assert "clip-001.mp4" == cmd[-1]
    assert "aac" in cmd
