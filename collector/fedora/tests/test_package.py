import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "tools/m3"))
from build_collector import build
from install_collector import install
from prepare_config import prepare


def test_reproducible_package_and_isolated_execution(tmp_path):
    first, second = tmp_path / "first.pyz", tmp_path / "second.pyz"
    assert build(first) == build(second)
    assert first.read_bytes() == second.read_bytes()
    result = subprocess.run(
        [sys.executable, "-I", str(first), "--help"], text=True, capture_output=True
    )
    assert result.returncode == 0 and "--sample" in result.stdout


def test_staged_install_never_enables_or_overwrites(tmp_path):
    home = tmp_path / "home"
    home.mkdir(mode=0o700)
    targets = install(home)
    assert all(path.is_file() for path in targets)
    assert (home / ".local/state/infrabadge-collector").stat().st_mode & 0o077 == 0
    assert not (home / ".config/systemd/user/timers.target.wants").exists()
    assert not (home / ".config/infrabadge/collector.token").exists()
    import pytest

    with pytest.raises(ValueError, match="existing_installation_preserved"):
        install(home)


def test_private_config_preparation_preserves_m2_and_separates_roles(tmp_path):
    import hashlib
    import json

    import pytest

    source = tmp_path / "original.json"
    source.write_text(
        json.dumps(
            {
                "devices": {"badge-lab": {"token_sha256": ["a" * 64], "scenario": "WARNING"}},
                "enable_faults": True,
            }
        )
    )
    source.chmod(0o600)
    original = source.read_bytes()
    ca = tmp_path / "ca.pem"
    ca.write_text("-----BEGIN CERTIFICATE-----\nSYNTHETIC PUBLIC TEST\n-----END CERTIFICATE-----")
    output = tmp_path / "new"
    prepare(output, source, ca, "https://localhost:8443", "badge-lab")
    assert source.read_bytes() == original
    config = json.loads((output / "gateway.json").read_text())
    assert not config["enable_faults"]
    assert config["devices"]["badge-lab"]["token_sha256"] == ["a" * 64]
    token = (output / "collector.token").read_text()
    assert config["collectors"]["workstation"]["token_sha256"] == [
        hashlib.sha256(token.encode()).hexdigest()
    ]
    assert all(path.stat().st_mode & 0o077 == 0 for path in output.iterdir())
    with pytest.raises(ValueError):
        prepare(output, source, ca, "https://localhost:8443", "badge-lab")
