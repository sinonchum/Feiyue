from feiyue_core.workflow.wave9_marker import wave9_marker


def test_wave9_marker_returns_verified():
    assert wave9_marker() == "verified"
