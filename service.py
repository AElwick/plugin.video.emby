# -*- coding: utf-8 -*-

#################################################################################################

import logging
import os
import sys

import xbmc
import xbmcaddon

#################################################################################################

_ADDON = xbmcaddon.Addon(id='plugin.video.emby')
_CWD = _ADDON.getAddonInfo('path').decode('utf-8')
_BASE_LIB = xbmc.translatePath(os.path.join(_CWD, 'resources', 'lib')).decode('utf-8')
sys.path.append(_BASE_LIB)

#################################################################################################

import loghandler
from service_entry import Service
from utils import settings

#################################################################################################

loghandler.config()
log = logging.getLogger("EMBY.service")
DELAY = settings('startupDelay') or 0

#################################################################################################

if __name__ == "__main__":

    log.warn("Delaying emby startup by: %s sec...", DELAY)

    try:
        if int(DELAY) and xbmc.Monitor().waitForAbort(int(DELAY)):
            raise RuntimeError("Abort event while waiting to start Emby for kodi")
        # Start the service
        Service().service_entry_point()
    except Exception as error:
        log.exception(error)
