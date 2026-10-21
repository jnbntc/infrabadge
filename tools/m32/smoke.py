"""Native container smoke appended after the synthetic fixture module in CI."""

import json
import platform
import tempfile
from pathlib import Path

from infrabadge_gateway.distributed.core import Core
from infrabadge_gateway.distributed.store import Store, restore
from infrabadge_gateway.models import Snapshot

with tempfile.TemporaryDirectory() as directory:
    folder = Path(directory)
    store = Store(folder / "core.db")
    core = Core(configuration(), store)
    core.ingest("a", sample(), NOW)
    assert Snapshot.model_validate_json(core.snapshot("display-a", NOW)).status == "HEALTHY"
    store.backup(folder / "backup.db")
    store.close()
    restore(folder / "backup.db", folder / "restored.db")
    store = Store(folder / "restored.db")
    assert (
        Core(configuration(), store).inventory("alpha", NOW + 1)["nodes"][0]["freshness"]
        == "restored"
    )
    store.close()
print(
    json.dumps(
        dict(
            native_machine=platform.machine(),
            sqlite_migrate_backup_restore=True,
            m2_contract=True,
            real_hosts_accessed=False,
        )
    )
)
