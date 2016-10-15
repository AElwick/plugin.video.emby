import sys
import os
import traceback
import requests
import logging
import clientinfo
import md5
import xbmc
import platform
from utils import window, settings, language as lang

log = logging.getLogger("EMBY."+__name__)

# for info on the metrics that can be sent to Google Analytics
# https://developers.google.com/analytics/devguides/collection/protocol/v1/parameters#events

class GoogleAnalytics():

    testing = False
    
    def __init__(self):
    
        client_info = clientinfo.ClientInfo()
        self.version = client_info.get_version()
        self.device_id = client_info.get_device_id()       
        self.userAgent = "Kodi (" + self.getUserAgentOS() + ")"
        
        # Use set user name
        self.user_name = settings('username') or settings('connectUsername') or 'None'
        
        # use md5 for client and user for analytics
        self.device_id = md5.new(self.device_id).hexdigest()
        self.user_name = md5.new(self.user_name).hexdigest()
    
    def getUserAgentOS(self):
    
        return platform.system()
    
        '''
        if xbmc.getCondVisibility('system.platform.osx'):
            return "OSX"
        elif xbmc.getCondVisibility('system.platform.ios'):
            return "iOS"
        elif xbmc.getCondVisibility('system.platform.windows'):
            return "Windows"
        elif xbmc.getCondVisibility('system.platform.android'):
            return "Android"
        elif xbmc.getCondVisibility('system.platform.linux.raspberrypi'):
            return "Linux"
        elif xbmc.getCondVisibility('system.platform.linux'):
            return "Linux"
        else:
            return platform.system()
        '''
        
    def formatException(self):
        exc_type, exc_obj, exc_tb = sys.exc_info()
		
        stackFrames = traceback.extract_tb(exc_tb)
        if(len(stackFrames) > 0):
            stackFrames = traceback.extract_tb(exc_tb)[-1]
        else:
            stackFrames = None
        log.error(str(stackFrames))
		
        errorType = "NA"
        errorFile = "NA"
		
        if(stackFrames != None):
            fileName = os.path.split(stackFrames[0])[1]

            errorFile = "%s:%s(%s)(%s)" % (fileName, stackFrames[1], exc_obj.message, stackFrames[3].strip())
            errorFile = errorFile[0:499]
            errorType = "%s" % (exc_type.__name__)
            del(exc_type, exc_obj, exc_tb)
            log.error(errorType + " - " + errorFile)
			
        return errorType, errorFile
	
    def sendEventData(self, eventCategory, eventAction, eventLabel=None):
       
        # all the data we can send to Google Analytics
        data = {}
        data['v'] = '1'
        data['tid'] = 'UA-85356267-1' # tracking id, this is the account ID
        
        data['ds'] = 'plugin' # data source
        
        data['an'] = 'Kodi4Emby' # App Name
        data['aid'] = '1' # App ID
        data['av'] = self.version # App Version
        #data['aiid'] = '1.1' # App installer ID

        data['cid'] = self.device_id # Client ID
        #data['uid'] = self.user_name # User ID

        data['ua'] = self.userAgent # user agent string
        
        data['t'] = 'event' # action type
        data['ec'] = eventCategory # Event Category
        data['ea'] = eventAction # Event Action

        if(eventLabel != None):
            data['el'] = eventLabel # Event Label
        
        self.sendData(data)
            
    def sendData(self, data):
    
        log.info("GA: " + str(data))

        if(settings('metricLogging') == "false"):
            return
        
        if(self.testing):
            url = "https://www.google-analytics.com/debug/collect" # test URL
        else:
            url = "https://www.google-analytics.com/collect" # prod URL
        
        try:
            r = requests.post(url, data)
        except Exception as error:
            log.error(error)
        
        if(self.testing):
            log.info("GA: " + r.text.encode('utf-8'))
            
    
            