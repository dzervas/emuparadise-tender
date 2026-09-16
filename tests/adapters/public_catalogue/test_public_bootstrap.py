import asyncio
import logging
from unittest.mock import AsyncMock

from bootstrap import bootstrap


def test_public_bootstrap_without_romm_or_native_save_sync(tmp_path):
    async def run():
        runtime = bootstrap(
            user_home=str(tmp_path), plugin_dir=str(tmp_path), emit=AsyncMock(), logger=logging.getLogger("test")
        )
        assert runtime.downloads.get_download_queue() == {"downloads": []}
        assert await runtime.search.list_entries() == {"success": True, "items": []}
        assert not hasattr(runtime.api, "list_saves")
        await runtime.downloads.shutdown()

    asyncio.run(run())
