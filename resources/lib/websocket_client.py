# -*- coding: utf-8 -*-

#################################################################################################

import json
import logging
import threading
import websocket

import xbmc

import clientinfo
import downloadutils
import librarysync
import playlist
import userclient
from utils import window, settings, dialog, language as lang, JSONRPC

##################################################################################################

log = logging.getLogger("EMBY."+__name__)

##################################################################################################


class WebSocket_Client(threading.Thread):

    _shared_state = {}

    _client = None
    _stop_websocket = False


    def __init__(self):

        self.__dict__ = self._shared_state
        self.monitor = xbmc.Monitor()
        
        self.doutils = downloadutils.DownloadUtils()
        self.client_info = clientinfo.ClientInfo()
        self.device_id = self.client_info.get_device_id()
        self.library_sync = librarysync.LibrarySync()
        
        threading.Thread.__init__(self)


    def send_progress_update(self, data):

        log.debug("sendProgressUpdate")
        try:
            message = {

                'MessageType': "ReportPlaybackProgress",
                'Data': data
            }
            message_str = json.dumps(message)
            self._client.send(message_str)
            log.debug("Message data: %s", message_str)

        except Exception as error:
            log.exception(error)

    def on_message(self, ws, message):

        result = json.loads(message)
        message_type = result['MessageType']
        data = result['Data']

        if message_type not in ('SessionEnded'):
            # Mute certain events
            log.info("Message: %s" % message)

        if message_type == "Play":
            # A remote control play command has been sent from the server.
            self._play_(data)

        elif message_type == "Playstate":
            # A remote control update playstate command has been sent from the server.
            self._playstate_(data)

        elif message_type == "UserDataChanged":
            # A user changed their personal rating for an item, or their playstate was updated
            userdata_list = data['UserDataList']
            self.library_sync.triage_items("userdata", userdata_list)

        elif message_type == "LibraryChanged":
            
            librarySync = self.library_sync
            processlist = {

                'added': data['ItemsAdded'],
                'update': data['ItemsUpdated'],
                'remove': data['ItemsRemoved']
            }
            for action in processlist:
                librarySync.triage_items(action, processlist[action])

        elif message_type == "GeneralCommand":
            self._general_commands(data)

        elif message_type == "ServerRestarting":
            self._server_restarting()

        elif message_type == "UserConfigurationUpdated":
            # Update user data set in userclient
            userclient.UserClient().get_user(data)
            self.library_sync.refresh_views = True

        elif message_type == "ServerShuttingDown":
            # Server went offline
            window('emby_online', value="false")

    @classmethod
    def _play_(cls, data):

        item_ids = data['ItemIds']
        command = data['PlayCommand']

        playlist_ = playlist.Playlist()

        if command == "PlayNow":
            startat = data.get('StartPositionTicks', 0)
            playlist_.playAll(item_ids, startat)
            dialog(type_="notification",
                   heading=lang(29999),
                   message="%s %s" % (len(item_ids), lang(33004)),
                   icon="{emby}",
                   sound=False)

        elif command == "PlayNext":
            newplaylist = playlist_.modifyPlaylist(item_ids)
            dialog(type_="notification",
                   heading=lang(29999),
                   message="%s %s" % (len(item_ids), lang(33005)),
                   icon="{emby}",
                   sound=False)
            player = xbmc.Player()
            if not player.isPlaying():
                # Only start the playlist if nothing is playing
                player.play(newplaylist)

    @classmethod
    def _playstate_(cls, data):

        command = data['Command']
        player = xbmc.Player()

        actions = {

            'Stop': player.stop,
            'Unpause': player.pause,
            'Pause': player.pause,
            'NextTrack': player.playnext,
            'PreviousTrack': player.playprevious,
            'Seek': player.seekTime
        }
        action = actions[command]
        if command == "Seek":
            seekto = data['SeekPositionTicks']
            seektime = seekto / 10000000.0
            action(seektime)
            log.info("Seek to %s", seektime)
        else:
            action()
            log.info("Command: %s completed", command)

        window('emby_command', value="true")

    @classmethod
    def _general_commands(cls, data):

        command = data['Name']
        arguments = data['Arguments']

        if command in ('Mute', 'Unmute', 'SetVolume',
                       'SetSubtitleStreamIndex', 'SetAudioStreamIndex'):

            player = xbmc.Player()
            # These commands need to be reported back
            if command == "Mute":
                xbmc.executebuiltin('Mute')
            elif command == "Unmute":
                xbmc.executebuiltin('Mute')
            elif command == "SetVolume":
                volume = arguments['Volume']
                xbmc.executebuiltin('SetVolume(%s[,showvolumebar])' % volume)
            elif command == "SetAudioStreamIndex":
                index = int(arguments['Index'])
                player.setAudioStream(index - 1)
            elif command == "SetSubtitleStreamIndex":
                embyindex = int(arguments['Index'])
                currentFile = player.getPlayingFile()

                mapping = window('emby_%s.indexMapping' % currentFile)
                if mapping:
                    externalIndex = json.loads(mapping)
                    # If there's external subtitles added via playbackutils
                    for index in externalIndex:
                        if externalIndex[index] == embyindex:
                            player.setSubtitleStream(int(index))
                            break
                    else:
                        # User selected internal subtitles
                        external = len(externalIndex)
                        audioTracks = len(player.getAvailableAudioStreams())
                        player.setSubtitleStream(external + embyindex - audioTracks - 1)
                else:
                    # Emby merges audio and subtitle index together
                    audioTracks = len(player.getAvailableAudioStreams())
                    player.setSubtitleStream(index - audioTracks - 1)

            # Let service know
            window('emby_command', value="true")

        elif command == "DisplayMessage":

            header = arguments['Header']
            text = arguments['Text']
            dialog(type_="notification",
                   heading=header,
                   message=text,
                   icon="{emby}",
                   time=4000)

        elif command == "SendString":

            params = {
                'text': arguments['String'],
                'done': False
            }
            result = JSONRPC("Input.SendText").execute(params)

        elif command in ("MoveUp", "MoveDown", "MoveRight", "MoveLeft"):
            # Commands that should wake up display
            actions = {
                'MoveUp': "Input.Up",
                'MoveDown': "Input.Down",
                'MoveRight': "Input.Right",
                'MoveLeft': "Input.Left"
            }
            result = JSONRPC(actions[command]).execute()

        elif command == "GoHome":
            result = JSONRPC("GUI.ActivateWindow").execute({"window":"home"})

        else:
            builtin = {

                'ToggleFullscreen': 'Action(FullScreen)',
                'ToggleOsdMenu': 'Action(OSD)',
                'ToggleContextMenu': 'Action(ContextMenu)',
                'Select': 'Action(Select)',
                'Back': 'Action(back)',
                'PageUp': 'Action(PageUp)',
                'NextLetter': 'Action(NextLetter)',
                'GoToSearch': 'VideoLibrary.Search',
                'GoToSettings': 'ActivateWindow(Settings)',
                'PageDown': 'Action(PageDown)',
                'PreviousLetter': 'Action(PrevLetter)',
                'TakeScreenshot': 'TakeScreenshot',
                'ToggleMute': 'Mute',
                'VolumeUp': 'Action(VolumeUp)',
                'VolumeDown': 'Action(VolumeDown)',
            }
            action = builtin.get(command)
            if action:
                xbmc.executebuiltin(action)
    
    @classmethod
    def _server_restarting(cls):

        if settings('supressRestartMsg') == "true":
            dialog(type_="notification",
                   heading=lang(29999),
                   message=lang(33006),
                   icon="{emby}")

    def on_close(self, ws):
        log.debug("closed")

    def on_open(self, ws):
        self.doutils.postCapabilities(self.device_id)

    def on_error(self, ws, error):
        if "10061" in str(error):
            # Server is offline
            pass
        else:
            log.debug("Error: %s", error)

    def run(self):

        # websocket.enableTrace(True)

        user_id = window('emby_currUser')
        server = window('emby_server%s' % user_id)
        token = window('emby_accessToken%s' % user_id)
        # Get the appropriate prefix for the websocket
        if "https" in server:
            server = server.replace('https', "wss")
        else:
            server = server.replace('http', "ws")

        websocket_url = "%s?api_key=%s&deviceId=%s" % (server, token, self.device_id)
        log.info("websocket url: %s", websocket_url)

        self._client = websocket.WebSocketApp(websocket_url,
                                             on_message=self.on_message,
                                             on_error=self.on_error,
                                             on_close=self.on_close)
        self._client.on_open = self.on_open
        log.warn("----===## Starting WebSocketClient ##===----")

        while not self.monitor.abortRequested():

            self._client.run_forever(ping_interval=10)
            if self._stop_websocket:
                break

            if self.monitor.waitForAbort(5):
                # Abort was requested, exit
                break

        log.warn("##===---- WebSocketClient Stopped ----===##")

    def stop_client(self):

        self._stop_websocket = True
        self._client.close()
        log.info("Stopping thread")
