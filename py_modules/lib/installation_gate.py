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
