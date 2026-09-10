from unittest.mock import Mock

import pytest

from adapters.public_catalogue.http import PublicSourceError
from adapters.public_catalogue.router import ContentApiRouter
from domain.provider_identity import PUBLIC_ID_START


class Romm:
    def __init__(self):
        self.calls = []

    def list_saves(self, rom_id):
        self.calls.append(rom_id)
        return []

    def ingest_play_sessions(self, device_id, sessions):
        self.calls.append(sessions)
        return {"results": []}

    def get_rom(self, rom_id):
        self.calls.append(rom_id)
        return {"id": rom_id}


def test_foreign_ids_cannot_reach_romm_extensions_or_batch_requests():
    romm = Romm()
    router = ContentApiRouter(romm=romm, sources=Mock(), resolvers={}, transports={})
    with pytest.raises(PublicSourceError):
        router.list_saves(PUBLIC_ID_START)
    with pytest.raises(PublicSourceError):
        router.ingest_play_sessions("device", [{"rom_id": 42}, {"rom_id": PUBLIC_ID_START}])
    assert romm.calls == []
    assert router.list_saves(42) == []
    assert router.get_rom(42) == {"id": 42}
    assert romm.calls == [42, 42]


def test_public_liveness_is_local_and_missing_source_is_not_deletion_authority():
    romm = Romm()
    sources = Mock()
    sources.get.return_value = {"detail": {"id": PUBLIC_ID_START}}
    router = ContentApiRouter(romm=romm, sources=sources, resolvers={}, transports={})
    assert router.get_rom_once(PUBLIC_ID_START) == {"id": PUBLIC_ID_START}
    sources.get.return_value = None
    with pytest.raises(PublicSourceError):
        router.get_rom_once(PUBLIC_ID_START)
    assert romm.calls == []
