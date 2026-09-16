"""Public-catalogue composition root. No server account or synchronisation services."""

import asyncio
import functools
import logging
import os
from types import SimpleNamespace

from adapters.asyncio_sleeper import AsyncioSleeper
from adapters.atlas_catalogue import AtlasCatalogueAdapter
from adapters.download_file import DownloadFileAdapter
from adapters.emulator_installation import EmulatorInstallationAdapter, InstallationCatalogueAdapter
from adapters.es_find_rules import EsFindRulesAdapter
from adapters.persistence import PersistenceAdapter, PlatformCoreReaderAdapter
from adapters.public_catalogue.downloads import RomsdlDownloadAdapter, RomspediaDownloadAdapter
from adapters.public_catalogue.emuparadise import EmuparadiseCatalogueAdapter
from adapters.public_catalogue.http import PublicHttpAdapter
from adapters.public_catalogue.router import ContentApiRouter
from adapters.public_catalogue.sources import PublicSourceStore
from adapters.public_catalogue.vimm import VimmDownloadAdapter
from adapters.repositories.unit_of_work import SqliteUnitOfWork
from adapters.retrodeck_paths import RetroDeckPathsAdapter
from adapters.rom_files import RomFileAdapter
from adapters.sqlite_migrations import MIGRATIONS_DIR, apply_migrations
from adapters.steam_rom_manager import SteamRomManagerAdapter
from adapters.system_clock import SystemClock
from domain.user_data_location import config_root, data_root
from services.active_core_resolver import ActiveCoreResolver, ActiveCoreResolverConfig
from services.catalogue import CatalogueService, CatalogueServiceConfig
from services.disc_launch_resolver import DiscLaunchResolver, DiscLaunchResolverConfig
from services.downloads import DownloadService, DownloadServiceConfig
from services.rom_install_recorder import RomInstallRecorder, RomInstallRecorderConfig
from services.rom_removal import RomRemovalService, RomRemovalServiceConfig


def bootstrap(*, user_home, plugin_dir, emit, logger: logging.Logger):
    clock = SystemClock()
    settings_dir, data_dir = config_root(user_home), data_root(user_home)
    os.makedirs(settings_dir, exist_ok=True)
    os.makedirs(data_dir, exist_ok=True)
    persistence = PersistenceAdapter(settings_dir, data_dir, logger, clock=clock)
    settings = persistence.load_settings()
    # Preserve local install identities and paths across this fork's upgrade.
    db_path = os.path.join(data_dir, "romm_sync.db")
    apply_migrations(db_path, MIGRATIONS_DIR, logger=logger)
    uow = functools.partial(SqliteUnitOfWork, db_path)
    paths = EmulatorInstallationAdapter(
        user_home=user_home,
        preference=settings.get("emulator_installation", "auto"),
        retrodeck_paths=RetroDeckPathsAdapter(user_home=user_home, logger=logger),
    )
    rules = EsFindRulesAdapter(user_home=user_home, logger=logger)
    atlas = AtlasCatalogueAdapter(
        choose_installation=paths.choose, emulator_installed=rules.command_emulator_installed, log_debug=logger.debug
    )
    catalogue = InstallationCatalogueAdapter(catalogue=atlas, installation=paths)

    def resolve_system(slug, _fs_slug=None):
        system = slug
        if paths.kind == "emudeck":
            paths.validate_system(system)
        return system

    core = ActiveCoreResolver(
        config=ActiveCoreResolverConfig(
            uow_factory=uow,
            core_info=catalogue,
            sandbox_launcher=rules.resolve_sandbox_launcher,
            platform_core_reader=PlatformCoreReaderAdapter(settings),
            resolve_system=resolve_system,
            logger=logger,
        )
    )
    files = DownloadFileAdapter()
    discs = DiscLaunchResolver(
        config=DiscLaunchResolverConfig(
            list_files=files.list_files, system_extensions=catalogue.get_supported_extensions, logger=logger
        )
    )
    recorder = RomInstallRecorder(
        config=RomInstallRecorderConfig(
            logger=logger,
            clock=clock,
            uow_factory=uow,
            system_extensions=catalogue.get_supported_extensions,
            active_core=core,
            disc_resolver=discs,
            external_shortcuts=paths.kind == "emudeck",
        )
    )
    sources = PublicSourceStore(db_path=db_path)
    ep = EmuparadiseCatalogueAdapter(
        http=PublicHttpAdapter(hosts=EmuparadiseCatalogueAdapter.page_hosts, user_agent="Tender")
    )
    provider_types = {
        "romspedia": RomspediaDownloadAdapter,
        "romsdl": RomsdlDownloadAdapter,
        "vimm": VimmDownloadAdapter,
    }
    transports, resolvers = {}, {}
    for name, adapter in provider_types.items():
        file_hosts = adapter.file_hosts if name == "vimm" else {adapter.file_host}
        transports[name] = PublicHttpAdapter(hosts=frozenset(adapter.page_hosts | file_hosts), user_agent="Tender")
        resolvers[name] = adapter(http=transports[name])
    api = ContentApiRouter(sources=sources, resolvers=resolvers, transports=transports)
    loop = asyncio.get_running_loop()

    async def target_gate(detail, path, **_kwargs):
        def check():
            if not os.path.lexists(path):
                return None
            with uow() as unit:
                install = unit.rom_installs.get(detail["id"])
                if install and os.path.realpath(path) in {
                    os.path.realpath(install.file_path),
                    os.path.realpath(install.rom_dir or install.file_path),
                }:
                    return None
            return {
                "success": False,
                "reason": "target_occupied",
                "message": "An existing file occupies this location. Tender will not overwrite an untracked ROM.",
            }

        return await loop.run_in_executor(None, check)

    downloads = DownloadService(
        config=DownloadServiceConfig(
            catalogue=api,
            downloads=api,
            download_file_store=files,
            resolve_system=resolve_system,
            loop=loop,
            logger=logger,
            emit=emit,
            clock=clock,
            sleeper=AsyncioSleeper(),
            retrodeck_paths=paths,
            install_recorder=recorder,
            target_gate=target_gate,
            m3u_support=catalogue.system_supports_m3u,
            uow_factory=uow,
            rom_remover=lambda: removal.remove_rom,
        )
    )
    removal = RomRemovalService(
        config=RomRemovalServiceConfig(
            logger=logger,
            loop=loop,
            clock=clock,
            emit=emit,
            rom_file_store=RomFileAdapter(),
            retrodeck_paths=paths,
            download_queue_cleanup=downloads,
            uow_factory=uow,
        )
    )
    search = CatalogueService(
        config=CatalogueServiceConfig(
            catalogue=ep,
            resolve_system=resolve_system,
            sources=sources,
            resolvers=resolvers,
            uow_factory=uow,
            clock=clock,
            loop=loop,
            plugin_dir=plugin_dir,
            shortcut_owner="srm" if paths.kind == "emudeck" else "tender",
        )
    )
    return SimpleNamespace(
        settings=settings,
        persistence=persistence,
        paths=paths,
        srm=SteamRomManagerAdapter(installation=paths, user_home=user_home, data_dir=data_dir),
        downloads=downloads,
        removal=removal,
        search=search,
        ep=ep,
        api=api,
        uow=uow,
    )
