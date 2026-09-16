from unittest.mock import Mock
import pytest
from adapters.public_catalogue.router import ContentApiRouter
from adapters.public_catalogue.http import PublicSourceError


def test_content_is_local_and_has_no_server_extension():
    sources = Mock()
    sources.get.return_value = {"detail": {"id": 42}}
    router = ContentApiRouter(sources=sources, resolvers={}, transports={})
    assert router.get_rom_once(42) == {"id": 42}
    with pytest.raises(AttributeError):
        router.list_saves(42)
    sources.get.return_value = None
    with pytest.raises(PublicSourceError):
        router.get_rom(42)
