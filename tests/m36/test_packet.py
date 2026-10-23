"""Only private offline packets; no serial library or device is involved."""

import json
import os
from pathlib import Path

import pytest
from fixtures import bundle
from prepare_packet import prepare

ROOT = Path(__file__).resolve().parents[2]
NATIVE = ROOT / "results/m36-native/policy"


@pytest.fixture
def packet_files(tmp_path):
    if not NATIVE.is_file():
        pytest.skip("Native production parser unavailable on this runner")
    tmp_path.chmod(0o700)
    source = tmp_path / "config.json"
    source.write_text(json.dumps(bundle()))
    source.chmod(0o600)
    return source, tmp_path / "packet.private"


def test_offline_packet_private_and_no_overwrite(packet_files):
    source, target = packet_files
    prepare(source, target, NATIVE)
    assert target.stat().st_mode & 0o777 == 0o600
    assert target.read_bytes().startswith(b"IBPROV36 {")
    before = target.read_bytes()
    with pytest.raises(FileExistsError):
        prepare(source, target, NATIVE)
    assert target.read_bytes() == before


def test_reject_world_readable_and_symlink(packet_files):
    source, target = packet_files
    source.chmod(0o644)
    with pytest.raises(ValueError):
        prepare(source, target, NATIVE)
    source.chmod(0o600)
    link = source.parent / "link"
    link.symlink_to(source)
    with pytest.raises(OSError):
        prepare(link, target, NATIVE)
    assert not target.exists()


def test_parser_error_not_exposed_and_no_output(packet_files, capsys):
    source, target = packet_files
    source.write_text('{"secret": "do not log"}')
    with pytest.raises(ValueError):
        prepare(source, target, NATIVE)
    assert not target.exists() and not capsys.readouterr().out
    assert os.getuid() == source.stat().st_uid
