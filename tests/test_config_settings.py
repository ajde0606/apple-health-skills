import importlib


def test_load_settings_reads_dotenv_each_call(tmp_path, monkeypatch):
    from mac.collector import config

    env_file = tmp_path / ".env"
    env_file.write_text("AHB_INGEST_TOKEN=first\nAHB_HOSTNAME=first.ts.net:8443\n")

    monkeypatch.setattr(config, "DOTENV_PATH", env_file)
    monkeypatch.delenv("AHB_INGEST_TOKEN", raising=False)
    monkeypatch.delenv("AHB_HOSTNAME", raising=False)

    s1 = config.load_settings()
    assert s1.ingest_token == "first"
    assert s1.hostname == "first.ts.net:8443"

    env_file.write_text("AHB_INGEST_TOKEN=second\nAHB_HOSTNAME=second.ts.net:8443\n")
    s2 = config.load_settings()
    assert s2.ingest_token == "second"
    assert s2.hostname == "second.ts.net:8443"


def test_tailscale_hostname_retries_after_failure(monkeypatch):
    from mac.collector import config

    importlib.reload(config)
    config._tailscale_hostname_cache = None

    calls = {"n": 0}

    def fake_check_output(*_args, **_kwargs):
        calls["n"] += 1
        if calls["n"] == 1:
            raise RuntimeError("temporary failure")
        return b'{"Self":{"DNSName":"my-mac.example.ts.net."}}'

    monkeypatch.setattr(config.subprocess, "check_output", fake_check_output)

    assert config._tailscale_hostname() == ""
    assert config._tailscale_hostname() == "my-mac.example.ts.net:8443"
    assert calls["n"] == 2
