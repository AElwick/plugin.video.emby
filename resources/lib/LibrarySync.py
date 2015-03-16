#################################################################################################
# LibrarySync
#################################################################################################

import xbmc
import xbmcgui
import xbmcaddon
import xbmcvfs
import json
import sqlite3
import threading
import urllib
from datetime import datetime, timedelta, time
import urllib2
import os

from xml.etree.ElementTree import Element, SubElement, Comment, tostring
from xml.etree import ElementTree
from xml.dom import minidom
import xml.etree.cElementTree as ET

from API import API
import Utils as utils
from DownloadUtils import DownloadUtils

addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
addondir = xbmc.translatePath(addon.getAddonInfo('profile'))
dataPath = os.path.join(addondir,"library")
movieLibrary = os.path.join(dataPath,'movies')
tvLibrary = os.path.join(dataPath,'tvshows')

sleepVal = 10
showProgress = True

class LibrarySync():   
        
    def syncDatabase(self):
        
        WINDOW = xbmcgui.Window( 10000 )
        WINDOW.setProperty("librarysync", "busy")
        pDialog = None
        
        try:
        
            if(showProgress):
                pDialog = xbmcgui.DialogProgressBG()
            if(pDialog != None):
                pDialog.create('Sync DB', 'Sync DB')
                
            updateNeeded = False    
            
            #process full movies sync
            allMovies = list()
            
            views = self.getCollections("movies")
            for view in views:
        
                movieData = self.getMovies(view.get('id'), True)
            
                if(self.ShouldStop()):
                    return True            
            
                if(movieData == None):
                    return False
            
                if(pDialog != None):
                    pDialog.update(0, "Sync DB : Processing " + view.get('title'))
                    total = len(movieData) + 1
                    count = 1
                
                for item in movieData:
                    if not item.get('IsFolder'):
                        kodiItem = self.getKodiMovie(item["Id"])
                        allMovies.append(item["Id"])
                        progMessage = "Processing"
                        item['Tag'] = view.get('title')
                        if kodiItem == None:
                            self.addMovieToKodiLibrary(item)
                            updateNeeded = True
                            progMessage = "Adding"
                        else:
                            self.updateMovieToKodiLibrary(item, kodiItem)
                            progMessage = "Updating"
                    
                        if(self.ShouldStop()):
                            return True
                    
                        # update progress bar
                        if(pDialog != None):
                            percentage = int(((float(count) / float(total)) * 100))
                            pDialog.update(percentage, message=progMessage + " Movie: " + str(count))
                            count += 1
                    
            #process full tv shows sync
            allTVShows = list()
            allEpisodes = list()
            tvShowData = self.getTVShows(True)
            
            if(self.ShouldStop()):
                return True            
            
            if (tvShowData == None):
                return
                
            if(pDialog != None):
                pDialog.update(0, "Sync DB : Processing TV Shows")
                total = len(tvShowData) + 1
                count = 0
                
            for item in tvShowData:
                if item.get('IsFolder'):
                    kodiItem = self.getKodiTVShow(item["Id"])
                    allTVShows.append(item["Id"])
                    progMessage = "Processing"
                    if kodiItem == None:
                        self.addTVShowToKodiLibrary(item)
                        updateNeeded = True
                        progMessage = "Adding"
                    else:
                        self.updateTVShowToKodiLibrary(item, kodiItem)
                        progMessage = "Updating"
                        
                    if(self.ShouldStop()):
                        return True
                        
                    # update progress bar
                    if(pDialog != None):
                        percentage = int(((float(count) / float(total)) * 100))
                        pDialog.update(percentage, message=progMessage + " Tv Show: " + str(count))
                        count += 1                        
                    
            
            #process episodes (will only be possible when tv show is scanned to library)   
            #TODO --> maybe pull full info only when needed ?
            allEpisodes = list()
            
            for tvshow in allTVShows:
                
                episodeData = self.getEpisodes(tvshow,True)
                kodiEpisodes = self.getKodiEpisodes(tvshow)
                
                if(self.ShouldStop()):
                    return True                
                
                if(pDialog != None):
                    pDialog.update(0, "Sync DB : Processing Episodes")
                    total = len(episodeData) + 1
                    count = 0         

                #we have to compare the lists somehow
                for item in episodeData:
                    comparestring1 = str(item.get("ParentIndexNumber")) + "-" + str(item.get("IndexNumber"))
                    matchFound = False
                    progMessage = "Processing"
                    if kodiEpisodes != None:
                        for KodiItem in kodiEpisodes:
                            
                            allEpisodes.append(KodiItem["episodeid"])
                            comparestring2 = str(KodiItem["season"]) + "-" + str(KodiItem["episode"])
                            if comparestring1 == comparestring2:
                                #match found - update episode
                                self.updateEpisodeToKodiLibrary(item,KodiItem,tvshow)
                                matchFound = True
                                progMessage = "Updating"

                    if not matchFound:
                        #no match so we have to create it
                        print "episode not found...creating it: "
                        self.addEpisodeToKodiLibrary(item,tvshow)
                        updateNeeded = True
                        progMessage = "Adding"
                        
                    if(self.ShouldStop()):
                        return True                        
                        
                    # update progress bar
                    if(pDialog != None):
                        percentage = int(((float(count) / float(total)) * 100))
                        pDialog.update(percentage, message=progMessage + " Episode: " + str(count))
                        count += 1    
                    
            # process deletes
            # TODO --> process deletes for episodes !!!
            if(pDialog != None):
                pDialog.update(0, message="Removing Deleted Items")
            
            if(self.ShouldStop()):
                return True            
            
            cleanNeeded = False
            allLocaldirs, filesMovies = xbmcvfs.listdir(movieLibrary)
            allMB3Movies = set(allMovies)
            for dir in allLocaldirs:
                if not dir in allMB3Movies:
                    self.deleteMovieFromKodiLibrary(dir)
                    cleanneeded = True
            
            if(self.ShouldStop()):
                return True            
            
            allLocaldirs, filesTVShows = xbmcvfs.listdir(tvLibrary)
            allMB3TVShows = set(allTVShows)
            for dir in allLocaldirs:
                if not dir in allMB3TVShows:
                    self.deleteTVShowFromKodiLibrary(dir)
                    cleanneeded = True
                    
            if(self.ShouldStop()):
                return True
                        
            if cleanNeeded:
                WINDOW.setProperty("cleanNeeded", "true")
            
            if updateNeeded:
                WINDOW.setProperty("updateNeeded", "true")
        
        finally:
            WINDOW.clearProperty("librarysync")
            if(pDialog != None):
                pDialog.close()
        
        return True
                              
    def updatePlayCounts(self):
        #update all playcounts from MB3 to Kodi library
        
        WINDOW = xbmcgui.Window( 10000 )
        WINDOW.setProperty("librarysync", "busy")
        pDialog = None
        
        try:
            if(showProgress):
                pDialog = xbmcgui.DialogProgressBG()
            if(pDialog != None):
                pDialog.create('Sync PlayCounts', 'Sync PlayCounts')        
        
            #process movies
            views = self.getCollections("movies")
            for view in views:
                movieData = self.getMovies(view.get('id'),False)
            
                if(self.ShouldStop()):
                    return True
                        
                if(movieData == None):
                    return False    
            
                if(pDialog != None):
                    pDialog.update(0, "Sync PlayCounts: Processing Movies")
                    totalCount = len(movieData) + 1
                    count = 1            
            
                for item in movieData:
                    if not item.get('IsFolder'):
                        kodiItem = self.getKodiMovie(item["Id"])
                        userData=API().getUserData(item)
                        timeInfo = API().getTimeInfo(item)
                        if kodiItem != None:
                            self.updateProperty(kodiItem,"playcount",int(userData.get("PlayCount")),"episode")
                  
                            kodiresume = int(round(kodiItem['resume'].get("position")))
                            resume = int(round(float(timeInfo.get("ResumeTime"))))*60
                            total = int(round(float(timeInfo.get("TotalTime"))))*60
                            if kodiresume != resume:
                                self.setKodiResumePoint(kodiItem['movieid'],resume,total,"movie")
                            
                        if(self.ShouldStop()):
                            return True
                        
                        # update progress bar
                        if(pDialog != None):
                            percentage = int(((float(count) / float(totalCount)) * 100))
                            pDialog.update(percentage, message="Updating Movie: " + str(count))
                            count += 1                              
                    
            #process Tv shows
            tvshowData = self.getTVShows(False)
            
            if(self.ShouldStop()):
                return True
                        
            if (tvshowData == None):
                return False    
            
            for item in tvshowData:
                episodeData = self.getEpisodes(item["Id"], False)
                
                if (episodeData != None):
                    if(pDialog != None):
                        pDialog.update(0, "Sync PlayCounts: Processing Episodes")
                        totalCount = len(episodeData) + 1
                        count = 1                  
                
                    for episode in episodeData:
                        kodiItem = self.getKodiEpisodeByMbItem(episode)
                        userData=API().getUserData(episode)
                        timeInfo = API().getTimeInfo(episode)
                        if kodiItem != None:
                            if kodiItem['playcount'] != int(userData.get("PlayCount")):
                                self.updateProperty(kodiItem,"playcount",int(userData.get("PlayCount")),"episode")
                            kodiresume = int(round(kodiItem['resume'].get("position")))
                            resume = int(round(float(timeInfo.get("ResumeTime"))))*60
                            total = int(round(float(timeInfo.get("TotalTime"))))*60
                            if kodiresume != resume:
                                self.setKodiResumePoint(kodiItem['episodeid'],resume,total,"episode")
                                
                        if(self.ShouldStop()):
                            return True
                        
                        # update progress bar
                        if(pDialog != None):
                            percentage = int(((float(count) / float(totalCount)) * 100))
                            pDialog.update(percentage, message="Updating Episode: " + str(count))
                            count += 1       

        finally:
            WINDOW.clearProperty("librarysync")
            if(pDialog != None):
                pDialog.close()            
        
        return True
    
    def getMovies(self, id, fullinfo = False):
        result = None
        
        addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
        port = addon.getSetting('port')
        host = addon.getSetting('ipaddress')
        server = host + ":" + port
        
        downloadUtils = DownloadUtils()
        userid = downloadUtils.getUserId()        
        
        if fullinfo:
            url = server + '/mediabrowser/Users/' + userid + '/items?ParentId=' + id + '&SortBy=SortName&Fields=Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview&Recursive=true&SortOrder=Ascending&IncludeItemTypes=Movie&format=json&ImageTypeLimit=1'
        else:
            url = server + '/mediabrowser/Users/' + userid + '/items?ParentId=' + id + '&SortBy=SortName&Fields=CumulativeRunTimeTicks&Recursive=true&SortOrder=Ascending&IncludeItemTypes=Movie&format=json&ImageTypeLimit=1'
        
        jsonData = downloadUtils.downloadUrl(url, suppress=True, popup=0)
        if jsonData != None and jsonData != "":
            result = json.loads(jsonData)
            if(result.has_key('Items')):
                result = result['Items']

        return result
    
    def getTVShows(self, fullinfo = False):
        result = None
        
        addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
        port = addon.getSetting('port')
        host = addon.getSetting('ipaddress')
        server = host + ":" + port
        
        downloadUtils = DownloadUtils()
        userid = downloadUtils.getUserId()   
        
        if fullinfo:
            url = server + '/mediabrowser/Users/' + userid + '/Items?&SortBy=SortName&Fields=Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview&Recursive=true&SortOrder=Ascending&IncludeItemTypes=Series&format=json&ImageTypeLimit=1'
        else:
            url = server + '/mediabrowser/Users/' + userid + '/Items?&SortBy=SortName&Fields=CumulativeRunTimeTicks&Recursive=true&SortOrder=Ascending&IncludeItemTypes=Series&format=json&ImageTypeLimit=1'
        
        jsonData = downloadUtils.downloadUrl(url, suppress=True, popup=0)
        if jsonData != None and jsonData != "":
            result = json.loads(jsonData)
            if(result.has_key('Items')):
                result = result['Items']

        return result
    
    def getEpisodes(self, showId, fullinfo = False):
        result = None
        
        addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
        port = addon.getSetting('port')
        host = addon.getSetting('ipaddress')
        server = host + ":" + port
        
        downloadUtils = DownloadUtils()
        userid = downloadUtils.getUserId()   
        
        if fullinfo:
            url = server + '/mediabrowser/Users/' + userid + '/Items?ParentId=' + showId + '&IsVirtualUnaired=false&IsMissing=False&SortBy=SortName&Fields=Path,Genres,SortName,Studios,Writer,ProductionYear,Taglines,CommunityRating,OfficialRating,CumulativeRunTimeTicks,Metascore,AirTime,DateCreated,MediaStreams,People,Overview&Recursive=true&SortOrder=Ascending&IncludeItemTypes=Episode&format=json&ImageTypeLimit=1'
        else:
            url = server + '/mediabrowser/Users/' + userid + '/Items?ParentId=' + showId + '&IsVirtualUnaired=false&IsMissing=False&SortBy=SortName&Fields=Name,SortName,CumulativeRunTimeTicks&Recursive=true&SortOrder=Ascending&IncludeItemTypes=Episode&format=json&ImageTypeLimit=1'
        
        jsonData = downloadUtils.downloadUrl(url, suppress=True, popup=0)
        
        if jsonData != None and jsonData != "":
            result = json.loads(jsonData)
            if(result.has_key('Items')):
                result = result['Items']
        return result
    
    def updatePlayCountFromKodi(self, id, playcount=0):
        #when user marks item watched from kodi interface update this to MB3
        
        addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
        port = addon.getSetting('port')
        host = addon.getSetting('ipaddress')
        server = host + ":" + port        
        downloadUtils = DownloadUtils()
        userid = downloadUtils.getUserId()           
        
        # TODO --> extend support for episodes
        json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovieDetails", "params": { "movieid": ' + str(id) + ', "properties" : ["playcount", "file"] }, "id": "1"}')
        if json_response != None:
            jsonobject = json.loads(json_response.decode('utf-8','replace'))  
            movie = None
            if(jsonobject.has_key('result')):
                result = jsonobject['result']
                if(result.has_key('moviedetails')):
                    moviedetails = result['moviedetails']
                    filename = moviedetails.get("file").rpartition('\\')[2]
                    mb3Id = filename.replace(".strm","")

                    watchedurl = 'http://' + server + '/mediabrowser/Users/' + userid + '/PlayedItems/' + mb3Id
                    utils.logMsg("watchedurl -->" + watchedurl)
                    if playcount != 0:
                        downloadUtils.downloadUrl(watchedurl, postBody="", type="POST")
                    else:
                        downloadUtils.downloadUrl(watchedurl, type="DELETE")
        
    def updateMovieToKodiLibrary( self, MBitem, KodiItem ):
        
        addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
        port = addon.getSetting('port')
        host = addon.getSetting('ipaddress')
        server = host + ":" + port        
        downloadUtils = DownloadUtils()
        userid = downloadUtils.getUserId()
        
        timeInfo = API().getTimeInfo(MBitem)
        userData=API().getUserData(MBitem)
        people = API().getPeople(MBitem)
        genre = API().getGenre(MBitem)
        studios = API().getStudios(MBitem)
        mediaStreams=API().getMediaStreams(MBitem)
        
        thumbPath = API().getArtwork(MBitem, "Primary")
        
        utils.logMsg("Updating item to Kodi Library", MBitem["Id"] + " - " + MBitem["Name"])
        
        #update artwork
        self.updateArtWork(KodiItem,"poster", API().getArtwork(MBitem, "poster"),"movie")
        self.updateArtWork(KodiItem,"clearlogo", API().getArtwork(MBitem, "Logo"),"movie")
        self.updateArtWork(KodiItem,"clearart", API().getArtwork(MBitem, "Art"),"movie")
        self.updateArtWork(KodiItem,"banner", API().getArtwork(MBitem, "Banner"),"movie")
        self.updateArtWork(KodiItem,"landscape", API().getArtwork(MBitem, "Thumb"),"movie")
        self.updateArtWork(KodiItem,"discart", API().getArtwork(MBitem, "Disc"),"movie")
        self.updateArtWork(KodiItem,"fanart", API().getArtwork(MBitem, "Backdrop"),"movie")
        
        #update common properties
        duration = (int(timeInfo.get('Duration'))*60)
        self.updateProperty(KodiItem,"runtime",duration,"movie")
        self.updateProperty(KodiItem,"year",MBitem.get("ProductionYear"),"movie")
        self.updateProperty(KodiItem,"mpaa",MBitem.get("OfficialRating"),"movie")
        self.updateProperty(KodiItem,"tag",MBitem.get("Tag"),"movie")
        
        if MBitem.get("CriticRating") != None:
            self.updateProperty(KodiItem,"rating",int(MBitem.get("CriticRating"))/10,"movie")
        
        self.updateProperty(KodiItem,"plotoutline",MBitem.get("ShortOverview"),"movie")
        self.updateProperty(KodiItem,"set",MBitem.get("TmdbCollectionName"),"movie")
        self.updateProperty(KodiItem,"sorttitle",MBitem.get("SortName"),"movie")
        
        if MBitem.get("ProviderIds") != None:
            if MBitem.get("ProviderIds").get("Imdb") != None:
                self.updateProperty(KodiItem,"imdbnumber",MBitem.get("ProviderIds").get("Imdb"),"movie")
        
        # FIXME --> Taglines not returned by MB3 server !?
        if MBitem.get("TagLines") != None:
            self.updateProperty(KodiItem,"tagline",MBitem.get("TagLines")[0],"movie")      
        
        self.updatePropertyArray(KodiItem,"writer",people.get("Writer"),"movie")
        self.updatePropertyArray(KodiItem,"director",people.get("Director"),"movie")
        self.updatePropertyArray(KodiItem,"genre",MBitem.get("Genres"),"movie")
        self.updatePropertyArray(KodiItem,"studio",studios,"movie")
        # FIXME --> ProductionLocations not returned by MB3 server !?
        self.updatePropertyArray(KodiItem,"country",MBitem.get("ProductionLocations"),"movie")
        
        #trailer link
        trailerUrl = None
        if MBitem.get("LocalTrailerCount") != None and MBitem.get("LocalTrailerCount") > 0:
            itemTrailerUrl = "http://" + server + "/mediabrowser/Users/" + userid + "/Items/" + MBitem.get("Id") + "/LocalTrailers?format=json"
            jsonData = downloadUtils.downloadUrl(itemTrailerUrl, suppress=True, popup=0 )
            if(jsonData != ""):
                trailerItem = json.loads(jsonData)
                trailerUrl = "plugin://plugin.video.mb3sync/?id=" + trailerItem[0].get("Id") + '&mode=play'
                self.updateProperty(KodiItem,"trailer",trailerUrl,"movie")
        
        #add actors
        self.AddActorsToMedia(KodiItem,MBitem.get("People"),"movie")
        
        self.createSTRM(MBitem)
        self.createNFO(MBitem)
        
    def updateTVShowToKodiLibrary( self, MBitem, KodiItem ):
        
        addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
        port = addon.getSetting('port')
        host = addon.getSetting('ipaddress')
        server = host + ":" + port        
        downloadUtils = DownloadUtils()
        
        timeInfo = API().getTimeInfo(MBitem)
        userData=API().getUserData(MBitem)
        people = API().getPeople(MBitem)
        genre = API().getGenre(MBitem)
        studios = API().getStudios(MBitem)
        mediaStreams=API().getMediaStreams(MBitem)
        
        thumbPath = API().getArtwork(MBitem, "Primary")
        
        utils.logMsg("Updating item to Kodi Library", MBitem["Id"] + " - " + MBitem["Name"])
        
        #update artwork
        self.updateArtWork(KodiItem,"poster", API().getArtwork(MBitem, "Primary"),"tvshow")
        self.updateArtWork(KodiItem,"clearlogo", API().getArtwork(MBitem, "Logo"),"tvshow")
        self.updateArtWork(KodiItem,"clearart", API().getArtwork(MBitem, "Art"),"tvshow")
        self.updateArtWork(KodiItem,"banner", API().getArtwork(MBitem, "Banner"),"tvshow")
        self.updateArtWork(KodiItem,"landscape", API().getArtwork(MBitem, "Thumb"),"tvshow")
        self.updateArtWork(KodiItem,"discart", API().getArtwork(MBitem, "Disc"),"tvshow")
        self.updateArtWork(KodiItem,"fanart", API().getArtwork(MBitem, "Backdrop"),"tvshow")
        
        #update common properties
        self.updateProperty(KodiItem,"year",MBitem.get("ProductionYear"),"tvshow")
        self.updateProperty(KodiItem,"mpaa",MBitem.get("OfficialRating"),"tvshow")
        
        if MBitem.get("CriticRating") != None:
            self.updateProperty(KodiItem,"rating",int(MBitem.get("CriticRating"))/10,"tvshow")
        
        self.updateProperty(KodiItem,"sorttitle",MBitem.get("SortName"),"tvshow")
        
        if MBitem.get("ProviderIds") != None:
            if MBitem.get("ProviderIds").get("Imdb") != None:
                self.updateProperty(KodiItem,"imdbnumber",MBitem.get("ProviderIds").get("Imdb"),"tvshow")
        

        self.updatePropertyArray(KodiItem,"genre",MBitem.get("Genres"),"tvshow")
        self.updatePropertyArray(KodiItem,"studio",studios,"tvshow")
        
        # FIXME --> ProductionLocations not returned by MB3 server !?
        self.updatePropertyArray(KodiItem,"country",MBitem.get("ProductionLocations"),"tvshow")
        
        #add actors
        self.AddActorsToMedia(KodiItem,MBitem.get("People"),"tvshow")

        self.createNFO(MBitem)
                    
    def updateEpisodeToKodiLibrary( self, MBitem, KodiItem, tvshowId ):
        
        addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
        port = addon.getSetting('port')
        host = addon.getSetting('ipaddress')
        server = host + ":" + port        
        downloadUtils = DownloadUtils()
        userid = downloadUtils.getUserId()
        
        timeInfo = API().getTimeInfo(MBitem)
        people = API().getPeople(MBitem)
        genre = API().getGenre(MBitem)
        studios = API().getStudios(MBitem)
        mediaStreams=API().getMediaStreams(MBitem)
        userData=API().getUserData(MBitem)
        
        thumbPath = API().getArtwork(MBitem, "Primary")
        
        utils.logMsg("Updating item to Kodi Library", MBitem["Id"] + " - " + MBitem["Name"])
        
        self.updateArtWork(KodiItem,"poster", API().getArtwork(MBitem, "Primary"),"episode")
        self.updateArtWork(KodiItem,"fanart", API().getArtwork(MBitem, "Backdrop"),"episode")
        #self.updateArtWork(KodiItem,"clearlogo", API().getArtwork(MBitem, "Logo"),"episode")
        #self.updateArtWork(KodiItem,"clearart", API().getArtwork(MBitem, "Art"),"episode")
        #self.updateArtWork(KodiItem,"banner", API().getArtwork(MBitem, "Banner"),"episode")
        #self.updateArtWork(KodiItem,"landscape", API().getArtwork(MBitem, "Thumb"),"episode")
        #self.updateArtWork(KodiItem,"discart", API().getArtwork(MBitem, "Disc"),"episode")
        
        
        #update common properties
        duration = (int(timeInfo.get('Duration'))*60)
        self.updateProperty(KodiItem,"runtime",duration,"episode")
        self.updateProperty(KodiItem,"firstaired",MBitem.get("ProductionYear"),"episode")
        
        if MBitem.get("CriticRating") != None:
            self.updateProperty(KodiItem,"rating",int(MBitem.get("CriticRating"))/10,"episode")
   
        
        self.updatePropertyArray(KodiItem,"writer",people.get("Writer"),"episode")

        #add actors
        self.AddActorsToMedia(KodiItem,MBitem.get("People"),"episode")
        
        self.createNFO(MBitem, tvshowId)
        self.createSTRM(MBitem, tvshowId)
    
    # adds or updates artwork to the given Kodi file in database
    def updateArtWork(self,KodiItem,artWorkName,artworkValue, fileType):
        if fileType == "tvshow":
            id = KodiItem['tvshowid']
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetTVShowDetails", "params": { "tvshowid": %i, "art": { "%s": "%s" }}, "id": 1 }'
        elif fileType == "episode":
            id = KodiItem['episodeid']
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetEpisodeDetails", "params": { "episodeid": %i, "art": { "%s": "%s" }}, "id": 1 }'
        elif fileType == "musicvideo":
            id = KodiItem['musicvideoid']
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMusicVideoDetails", "params": { musicvideoid": %i, "art": { "%s": "%s" }}, "id": 1 }'
        elif fileType == "movie":
            id = KodiItem['movieid']
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMovieDetails", "params": { "movieid": %i, "art": { "%s": "%s" }}, "id": 1 }'
        

        if KodiItem['art'].has_key(artWorkName):
            curValue = urllib.unquote(KodiItem['art'][artWorkName]).decode('utf8')
            if not artworkValue in curValue:
                xbmc.sleep(sleepVal)
                utils.logMsg("updating artwork..." + str(artworkValue) + " - " + str(curValue))
                xbmc.executeJSONRPC(jsoncommand %(id, artWorkName, artworkValue))
        elif artworkValue != None:
            xbmc.sleep(sleepVal)
            xbmc.executeJSONRPC(jsoncommand %(id, artWorkName, artworkValue))
    
    # adds or updates the given property on the videofile in Kodi database
    def updateProperty(self,KodiItem,propertyName,propertyValue,fileType):
        if fileType == "tvshow":
            id = KodiItem['tvshowid']
            jsoncommand_i = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetTVShowDetails", "params": { "tvshowid": %i, "%s": %i}, "id": 1 }'
            jsoncommand_s = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetTVShowDetails", "params": { "tvshowid": %i, "%s": "%s"}, "id": 1 }'
        elif fileType == "episode":
            id = KodiItem['episodeid']  
            jsoncommand_i = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetEpisodeDetails", "params": { "episodeid": %i, "%s": %i}, "id": 1 }'            
            jsoncommand_s = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetEpisodeDetails", "params": { "episodeid": %i, "%s": "%s"}, "id": 1 }'
        elif fileType == "musicvideo":
            id = KodiItem['musicvideoid']
            jsoncommand_i = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMusicVideoDetails", "params": { "musicvideoid": %i, "%s": %i}, "id": 1 }'
            jsoncommand_s = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMusicVideoDetails", "params": { "musicvideoid": %i, "%s": "%s"}, "id": 1 }'
        elif fileType == "movie":
            id = KodiItem['movieid']
            jsoncommand_i = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMovieDetails", "params": { "movieid": %i, "%s": %i}, "id": 1 }'
            jsoncommand_s = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMovieDetails", "params": { "movieid": %i, "%s": "%s"}, "id": 1 }'

        if propertyValue != KodiItem[propertyName]:
            if propertyValue != None:
                if type(propertyValue) is int:
                    xbmc.sleep(sleepVal)
                    utils.logMsg("updating property..." + str(propertyName) + ": " + str(propertyValue))
                    xbmc.executeJSONRPC(jsoncommand_i %(id, propertyName, propertyValue))
                else:
                    xbmc.sleep(sleepVal)
                    utils.logMsg("updating property..." + str(propertyName) + ": " + str(propertyValue))
                    xbmc.executeJSONRPC(jsoncommand_s %(id, propertyName, propertyValue.encode('utf-8')))

    # adds or updates the property-array on the videofile in Kodi database
    def updatePropertyArray(self,KodiItem,propertyName,propertyCollection,fileType):
        if fileType == "tvshow":
            id = KodiItem['tvshowid']   
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetTVShowDetails", "params": { "tvshowid": %i, "%s": %s}, "id": 1 }'
        elif fileType == "episode":
            id = KodiItem['episodeid']   
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetEpisodeDetails", "params": { "episodeid": %i, "%s": %s}, "id": 1 }'
        elif fileType == "musicvideo":
            id = KodiItem['musicvideoid']   
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMusicVideoDetails", "params": { "musicvideoid": %i, "%s": %s}, "id": 1 }'
        elif fileType == "movie":
            id = KodiItem['movieid']   
            jsoncommand = '{"jsonrpc": "2.0", "method": "VideoLibrary.SetMovieDetails", "params": { "movieid": %i, "%s": %s}, "id": 1 }'
        
        pendingChanges = False
        if propertyCollection != None:
            currentvalues = set(KodiItem[propertyName])
            genrestring = ""
            for item in propertyCollection:
                if not item in currentvalues:
                    pendingChanges = True
                    json_array = json.dumps(propertyCollection)
            
            if pendingChanges:
                xbmc.sleep(sleepVal)
                utils.logMsg("updating propertyarray..." + str(propertyName) + ": " + str(json_array))
                xbmc.executeJSONRPC(jsoncommand %(id,propertyName,json_array))    
    
    def CleanName(self, name):
        name = name.replace(":", "-")
        return name
        
    def createSTRM(self,item,parentId=None):
        
        item_type=str(item.get("Type")).encode('utf-8')
        if item_type == "Movie":
            itemPath = os.path.join(movieLibrary,item["Id"])
            strmFile = os.path.join(itemPath,item["Id"] + ".strm")

        if item_type == "MusicVideo":
            itemPath = os.path.join(musicVideoLibrary,item["Id"])
            strmFile = os.path.join(itemPath,item["Id"] + ".strm")

        if item_type == "Episode":
            itemPath = os.path.join(tvLibrary,parentId)
            if str(item.get("IndexNumber")) != None:
                filenamestr = self.CleanName(item.get("SeriesName")).encode('utf-8') + " S" + str(item.get("ParentIndexNumber")) + "E" + str(item.get("IndexNumber")) + ".strm"
            else:
                filenamestr = self.CleanName(item.get("SeriesName")).encode('utf-8') + " S0E0 " + item["Name"].decode('utf-8') + ".strm"
            strmFile = os.path.join(itemPath,filenamestr)
        
        if not xbmcvfs.exists(strmFile):
            xbmcvfs.mkdir(itemPath)
            text_file = open(strmFile, "w")
            
            playUrl = "plugin://plugin.video.mb3sync/?id=" + item["Id"] + '&mode=play'

            text_file.writelines(playUrl)
            text_file.close()

            
    def createNFO(self,item, parentId=None):
        downloadUtils = DownloadUtils()
        timeInfo = API().getTimeInfo(item)
        userData=API().getUserData(item)
        people = API().getPeople(item)
        mediaStreams=API().getMediaStreams(item)
        studios = API().getStudios(item)
        userid = downloadUtils.getUserId()
        port = addon.getSetting('port')
        host = addon.getSetting('ipaddress')
        server = host + ":" + port  
        item_type=str(item.get("Type"))
        
        if item_type == "Movie":
            itemPath = os.path.join(movieLibrary,item["Id"])
            nfoFile = os.path.join(itemPath,item["Id"] + ".nfo")
            rootelement = "movie"
        if item_type == "Series":
            itemPath = os.path.join(tvLibrary,item["Id"])
            nfoFile = os.path.join(itemPath,"tvshow.nfo")
            rootelement = "tvshow"
        if item_type == "Episode":
            itemPath = os.path.join(tvLibrary,parentId)
            if str(item.get("ParentIndexNumber")) != None:
                filenamestr = self.CleanName(item.get("SeriesName")).encode('utf-8') + " S" + str(item.get("ParentIndexNumber")) + "E" + str(item.get("IndexNumber")) + ".nfo"
            else:
                filenamestr = self.CleanName(item.get("SeriesName")).encode('utf-8') + " S0E0 " + item["Name"].decode('utf-8') + ".nfo"
            nfoFile = os.path.join(itemPath,filenamestr)
            rootelement = "episodedetails"
        
        if not xbmcvfs.exists(nfoFile):
            xbmcvfs.mkdir(itemPath)        
            root = Element(rootelement)
            SubElement(root, "id").text = item["Id"]
            if item.get("Tag") != None:
                SubElement(root, "tag").text = item.get("Tag")# TODO --> fix for TV etc
            
            SubElement(root, "thumb").text = API().getArtwork(item, "Primary")
            SubElement(root, "fanart").text = API().getArtwork(item, "Backdrop")
            SubElement(root, "title").text = utils.convertEncoding(item["Name"])
            SubElement(root, "originaltitle").text = utils.convertEncoding(item["Name"])
            SubElement(root, "sorttitle").text = utils.convertEncoding(item["SortName"])
            
            if item.has_key("OfficialRating"):
                SubElement(root, "mpaa").text = item["OfficialRating"]
            
            if item.get("CriticRating") != None:
                rating = int(item.get("CriticRating"))/10
                SubElement(root, "rating").text = str(rating)
            
            if item.get("DateCreated") != None:
                SubElement(root, "dateadded").text = item["DateCreated"]
            
            if userData.get("PlayCount") != None:
                SubElement(root, "playcount").text = userData.get("PlayCount")
                if int(userData.get("PlayCount")) > 0:
                    SubElement(root, "watched").text = "true"
            
            if timeInfo.get("ResumeTime") != None:
                resume_sec = int(round(float(timeInfo.get("ResumeTime"))))*60
                total_sec = int(round(float(timeInfo.get("TotalTime"))))*60
                resume = SubElement(root, "resume")
                SubElement(resume, "position").text = str(resume_sec)
                SubElement(resume, "total").text = str(total_sec)
            
            if item_type == "Episode":
                SubElement(root, "season").text = str(item.get("ParentIndexNumber"))
                SubElement(root, "episode").text = str(item.get("IndexNumber"))
                SubElement(root, "aired").text = str(item.get("ProductionYear"))
                
            SubElement(root, "year").text = str(item.get("ProductionYear"))
            SubElement(root, "runtime").text = str(timeInfo.get('Duration'))
            
            SubElement(root, "plot").text = utils.convertEncoding(API().getOverview(item))
            
            if item.get("ShortOverview") != None:
                SubElement(root, "plotoutline").text = utils.convertEncoding(item.get("ShortOverview"))
            
            if item.get("TmdbCollectionName") != None:
                SubElement(root, "set").text = item.get("TmdbCollectionName")
            
            if item.get("ProviderIds") != None:
                if item.get("ProviderIds").get("Imdb") != None:
                    SubElement(root, "imdbnumber").text = item
            
            if people.get("Writer") != None:
                for writer in people.get("Writer"):
                    SubElement(root, "writer").text = utils.convertEncoding(writer)
            
            if people.get("Director") != None:
                for director in people.get("Director"):
                    SubElement(root, "director").text = utils.convertEncoding(director)
            
            if item.get("Genres") != None:
                for genre in item.get("Genres"):
                    SubElement(root, "genre").text = utils.convertEncoding(genre)
            
            if studios != None:
                for studio in studios:
                    SubElement(root, "studio").text = utils.convertEncoding(studio)
                    
            if item.get("ProductionLocations") != None:
                for country in item.get("ProductionLocations"):
                    SubElement(root, "country").text = utils.convertEncoding(country)

            #trailer link
            trailerUrl = None
            if item.get("LocalTrailerCount") != None and item.get("LocalTrailerCount") > 0:
                itemTrailerUrl = "http://" + server + "/mediabrowser/Users/" + userid + "/Items/" + item.get("Id") + "/LocalTrailers?format=json"
                jsonData = downloadUtils.downloadUrl(itemTrailerUrl, suppress=True, popup=0 )
                if(jsonData != ""):
                    trailerItem = json.loads(jsonData)
                    trailerUrl = "plugin://plugin.video.mb3sync/?id=" + trailerItem[0].get("Id") + '&mode=play'
                    SubElement(root, "trailer").text = trailerUrl
            
            #add streamdetails
            fileinfo = SubElement(root, "fileinfo")
            streamdetails = SubElement(fileinfo, "streamdetails")
            video = SubElement(streamdetails, "video")
            SubElement(video, "duration").text = str(mediaStreams.get('totaltime'))
            SubElement(video, "aspect").text = mediaStreams.get('aspectratio')
            SubElement(video, "codec").text = mediaStreams.get('videocodec')
            SubElement(video, "width").text = str(mediaStreams.get('width'))
            SubElement(video, "height").text = str(mediaStreams.get('height'))
            SubElement(video, "duration").text = str(timeInfo.get('Duration'))
            
            audio = SubElement(streamdetails, "audio")
            SubElement(audio, "codec").text = mediaStreams.get('audiocodec')
            SubElement(audio, "channels").text = mediaStreams.get('channels')
            
            #add people
            if item.get("People") != None:
                for actor in item.get("People"):
                    if(actor.get("Type") == "Actor"):
                        actor_elem = SubElement(root, "actor")
                        SubElement(actor_elem, "name").text = utils.convertEncoding(actor.get("Name"))
                        SubElement(actor_elem, "type").text = utils.convertEncoding(actor.get("Role"))
                        SubElement(actor_elem, "thumb").text = downloadUtils.imageUrl(actor.get("Id"), "Primary", 0, 400, 400)
                            
                    
            
            ET.ElementTree(root).write(nfoFile, xml_declaration=True)
    
    
    def addMovieToKodiLibrary( self, item ):
        itemPath = os.path.join(movieLibrary,item["Id"])
        strmFile = os.path.join(itemPath,item["Id"] + ".strm")

        utils.logMsg("Adding item to Kodi Library",item["Id"] + " - " + item["Name"])
        
        #create path if not exists
        if not xbmcvfs.exists(itemPath + os.sep):
            xbmcvfs.mkdir(itemPath)
            
        #create nfo file
        self.createNFO(item)
        
        # create strm file
        self.createSTRM(item)
    
    def addEpisodeToKodiLibrary(self, item, tvshowId):

        utils.logMsg("Adding item to Kodi Library",item["Id"] + " - " + item["Name"])
            
        #create nfo file
        self.createNFO(item, tvshowId)
        
        # create strm file
        self.createSTRM(item, tvshowId)

    
    def deleteMovieFromKodiLibrary(self, id ):
        kodiItem = self.getKodiMovie(id)
        utils.logMsg("deleting movie from Kodi library",id)
        if kodiItem != None:
            xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.RemoveMovie", "params": { "movieid": %i}, "id": 1 }' %(kodiItem["movieid"]))
        
        path = os.path.join(movieLibrary,id)
        xbmcvfs.rmdir(path)
        
    def addTVShowToKodiLibrary( self, item ):
        itemPath = os.path.join(tvLibrary,item["Id"])
        utils.logMsg("Adding item to Kodi Library",item["Id"] + " - " + item["Name"])
        
        #create path if not exists
        if not xbmcvfs.exists(itemPath + os.sep):
            xbmcvfs.mkdir(itemPath)
            
        #create nfo file
        self.createNFO(item)
        
    def deleteTVShowFromKodiLibrary(self, id ):
        kodiItem = self.getKodiTVShow(id)
        utils.logMsg("deleting tvshow from Kodi library",id)
        if kodiItem != None:
            xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.RemoveTVShow", "params": { "tvshowid": %i}, "id": 1 }' %(kodiItem["tvshowid"]))
        path = os.path.join(tvLibrary,id)
        xbmcvfs.rmdir(path)
    
    def setKodiResumePoint(self, id, resume_seconds, total_seconds, fileType):
        #use sqlite to set the resume point while json api doesn't support this yet
        #todo --> submit PR to kodi team to get this added to the jsonrpc api
        dbPath = xbmc.translatePath("special://userdata/Database/MyVideos90.db")
        connection = sqlite3.connect(dbPath)
        cursor = connection.cursor( )
        
        if fileType == "episode":
            cursor.execute("SELECT idFile as fileidid FROM episode WHERE idEpisode = ?",(id,))
            result = cursor.fetchone()
            fileid = result[0]
        if fileType == "movie":
            cursor.execute("SELECT idFile as fileidid FROM movie WHERE idMovie = ?",(id,))
            result = cursor.fetchone()
            fileid = result[0]       
        
        cursor.execute("delete FROM bookmark WHERE idFile = ?", (fileid,))
        cursor.execute("select coalesce(max(idBookmark),0) as bookmarkId from bookmark")
        bookmarkId =  cursor.fetchone()[0]
        bookmarkId = bookmarkId + 1
        bookmarksql="insert into bookmark(idBookmark, idFile, timeInSeconds, totalTimeInSeconds, thumbNailImage, player, playerState, type) values(?, ?, ?, ?, ?, ?, ?, ?)"
        cursor.execute(bookmarksql, (bookmarkId,fileid,resume_seconds,total_seconds,None,"DVDPlayer",None,1))
        connection.commit()
        cursor.close()
    
    def AddActorsToMedia(self, KodiItem, people, mediatype):
        #use sqlite to set add the actors while json api doesn't support this yet
        #todo --> submit PR to kodi team to get this added to the jsonrpc api
        
        downloadUtils = DownloadUtils()
        if mediatype == "movie":
            id = KodiItem["movieid"]
        if mediatype == "tvshow":
            id = KodiItem["tvshowid"]
        if mediatype == "episode":
            id = KodiItem["episodeid"]

        
        dbPath = xbmc.translatePath("special://userdata/Database/MyVideos90.db")
        connection = sqlite3.connect(dbPath)
        cursor = connection.cursor()
        
        currentcast = list()
        if KodiItem["cast"] != None:
            for cast in KodiItem["cast"]:
                currentcast.append(cast["name"])

        if(people != None):
            for person in people:              
                if(person.get("Type") == "Actor"):
                    if person.get("Name") not in currentcast:
                        Name = person.get("Name")
                        Role = person.get("Role")
                        actorid = None
                        Thumb = downloadUtils.imageUrl(person.get("Id"), "Primary", 0, 400, 400)
                        cursor.execute("SELECT idActor as actorid FROM actors WHERE strActor = ?",(Name,))
                        result = cursor.fetchone()
                        if result != None:
                            actorid = result[0]
                        if actorid == None:
                            cursor.execute("select coalesce(max(idActor),0) as actorid from actors")
                            actorid = cursor.fetchone()[0]
                            actorid = actorid + 1
                            peoplesql="insert into actors(idActor, strActor, strThumb) values(?, ?, ?)"
                            cursor.execute(peoplesql, (actorid,Name,Thumb))
                        
                        if mediatype == "movie":
                            peoplesql="INSERT OR REPLACE into actorlinkmovie(idActor, idMovie, strRole, iOrder) values(?, ?, ?, ?)"
                        if mediatype == "tvshow":
                            peoplesql="INSERT OR REPLACE into actorlinktvshow(idActor, idShow, strRole, iOrder) values(?, ?, ?, ?)"
                        if mediatype == "episode":
                            peoplesql="INSERT OR REPLACE into actorlinkepisode(idActor, idEpisode, strRole, iOrder) values(?, ?, ?, ?)"
                        cursor.execute(peoplesql, (actorid,id,Role,None))
        
        connection.commit()
        cursor.close()
    
    
    def getKodiMovie(self, id):
        json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetMovies", "params": { "filter": {"operator": "contains", "field": "path", "value": "' + id + '"}, "properties" : ["art", "rating", "thumbnail", "resume", "runtime", "year", "genre", "cast", "trailer", "country", "studio", "set", "imdbnumber", "mpaa", "tagline", "plotoutline","plot", "sorttitle", "director", "writer", "playcount", "tag", "file"], "sort": { "order": "ascending", "method": "label", "ignorearticle": true } }, "id": "libMovies"}')
        jsonobject = json.loads(json_response.decode('utf-8','replace'))  
        movie = None
       
        if(jsonobject.has_key('result')):
            result = jsonobject['result']
            if(result.has_key('movies')):
                movies = result['movies']
                movie = movies[0]

        return movie
    
    def getKodiTVShow(self, id):
        json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetTVShows", "params": { "filter": {"operator": "contains", "field": "path", "value": "' + id + '"}, "properties": ["art", "genre", "plot", "mpaa", "cast", "studio", "sorttitle", "title", "originaltitle", "imdbnumber", "year", "rating", "thumbnail", "playcount", "file", "fanart"], "sort": { "order": "ascending", "method": "label", "ignorearticle": true } }, "id": "libTvShows"}')
        jsonobject = json.loads(json_response.decode('utf-8','replace'))  
        tvshow = None
        if(jsonobject.has_key('result')):
            result = jsonobject['result']
            if(result.has_key('tvshows')):
                tvshows = result['tvshows']
                tvshow = tvshows[0]
        return tvshow
    
    def getKodiEpisodes(self, id):
        episodes = None
        json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetTVShows", "params": { "filter": {"operator": "contains", "field": "path", "value": "' + id + '"}, "properties": ["art", "genre", "plot", "mpaa", "cast", "studio", "sorttitle", "title", "originaltitle", "imdbnumber", "year", "rating", "thumbnail", "playcount", "file", "fanart"], "sort": { "order": "ascending", "method": "label", "ignorearticle": true } }, "id": "libTvShows"}')
        jsonobject = json.loads(json_response.decode('utf-8','replace'))  
        tvshow = None
        if(jsonobject.has_key('result')):
            result = jsonobject['result']
            if(result.has_key('tvshows')):
                tvshows = result['tvshows']
                tvshow = tvshows[0]
                
                json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodes", "params": {"tvshowid": %d, "properties": ["title", "playcount", "plot", "season", "episode", "showtitle", "file", "lastplayed", "rating", "resume", "art", "streamdetails", "firstaired", "runtime", "writer", "cast", "dateadded"], "sort": {"method": "episode"}}, "id": 1}' %tvshow['tvshowid'])
                jsonobject = json.loads(json_response.decode('utf-8','replace'))  
                episodes = None
                if(jsonobject.has_key('result')):
                    result = jsonobject['result']
                    if(result.has_key('episodes')):
                        episodes = result['episodes']
        return episodes
        
    def getKodiEpisodeByMbItem(self, MBitem):
        json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetTVShows", "params": { "filter": {"operator": "is", "field": "title", "value": "' + MBitem.get("SeriesName").encode('utf-8') + '"} }, "id": "libTvShows"}')
        jsonobject = json.loads(json_response.decode('utf-8','replace'))  
        episode = None
        if(jsonobject.has_key('result')):
            result = jsonobject['result']
            if(result.has_key('tvshows')):
                tvshows = result['tvshows']
                tvshow = tvshows[0]

                # find the episode by combination of season and episode
                json_response = xbmc.executeJSONRPC('{"jsonrpc": "2.0", "method": "VideoLibrary.GetEpisodes", "params": {"tvshowid": %d, "properties": ["playcount","season", "resume", "episode"], "sort": {"method": "episode"}}, "id": 1}' %tvshow['tvshowid'])
                jsonobject = json.loads(json_response.decode('utf-8','replace'))  
                episodes = None
                if(jsonobject.has_key('result')):
                    result = jsonobject['result']
                    if(result.has_key('episodes')):
                        episodes = result['episodes']
                        
                        comparestring1 = str(MBitem.get("ParentIndexNumber")) + "-" + str(MBitem.get("IndexNumber"))
                        for item in episodes:
                            comparestring2 = str(item["season"]) + "-" + str(item["episode"])
                            if comparestring1 == comparestring2:
                                episode = item

        return episode

    
    def getCollections(self, type):
        #Build a list of the user views
        userid = DownloadUtils().getUserId()  
        addon = xbmcaddon.Addon(id='plugin.video.mb3sync')
        port = addon.getSetting('port')
        host = addon.getSetting('ipaddress')
        server = host + ":" + port
        
        viewsUrl = server + "/mediabrowser/Users/" + userid + "/Views?format=json&ImageTypeLimit=1"
        jsonData = DownloadUtils().downloadUrl(viewsUrl, suppress=True, popup=0 )
        
        if(jsonData != ""):
            views = json.loads(jsonData)
            views = views.get("Items")
            collections=[]
            for view in views:
                if(view.get("ChildCount") != 0):
                    Name =(view.get("Name")).encode('utf-8')
            
                total = str(view.get("ChildCount"))
                type = view.get("CollectionType")
                if type == None:
                    type = "None" # User may not have declared the type
                if type == type:
                    collections.append( {'title'      : Name,
                            'type'           : type,
                            'id'             : view.get("Id")})
        return collections
        
    def ShouldStop(self):
        if(xbmc.Player().isPlaying() or xbmc.abortRequested):
            return True
        else:
            return False
        
        
        
        