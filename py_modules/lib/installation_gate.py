"""Prevent new installations between selecting another setup and restarting Decky."""

import functools


def installation_restart_blocked(method):
    @functools.wraps(method)
    async def wrapper(self, *args, **kwargs):
        if self._installation_restart_required:
            return {
                "success": False,
                "reason": "restart_required",
                "message": "Restart Decky before installing into the newly selected emulator setup",
            }
        return await method(self, *args, **kwargs)

    return wrapper


def srm_update_blocked(method):
    @functools.wraps(method)
    async def wrapper(self, *args, **kwargs):
        import asyncio

        srm = getattr(self, "_srm", None)
        if (
            srm is not None
            and srm.enabled
            and (
                getattr(self, "_srm_starting", False)
                or await asyncio.get_running_loop().run_in_executor(None, srm.busy)
                or getattr(self, "_srm_starting", False)
            )
        ):
            return {"success": False, "reason": "srm_busy", "message": "Wait for the Steam library update to finish"}
        # This counter also serializes source rebinding against download admission.
        if getattr(self, "_catalogue_import_in_progress", False):
            return {
                "success": False,
                "reason": "source_change_active",
                "message": "Wait for download source selection to finish",
            }
        self._srm_mutations = getattr(self, "_srm_mutations", 0) + 1
        try:
            return await method(self, *args, **kwargs)
        finally:
            self._srm_mutations -= 1

    return wrapper
