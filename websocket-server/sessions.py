import json
import datetime
from enum import Enum
from typing import Optional, Dict, Any

import asyncio
import websockets
from fastapi import WebSocket
from websockets import exceptions as ws_exceptions

from api import openai
from api import firestore

from logger import log, LogLevel



class WebSocketRole(Enum):
    '''Possible session WebSockets.'''
    TWILIO = 'twilio_ws'
    FRONTEND = 'frontend_ws'
    MODEL = 'model_ws'


class Session:
    def __init__(self, stream_sid: str, ai_api_key: str, config: Optional[openai.SessionConfig] = None):
        # WebSockets
        self.ws_twilio: Optional[WebSocket] = None
        self.ws_frontend: Optional[WebSocket] = None
        self.ws_model: Optional[WebSocket] = None
        
        # Session Configuration
        self.config: openai.SessionConfig = config if config else openai.SessionConfig()  # Consider pulling from Google Firestore

        # Metadata
        self.stream_sid: str = stream_sid
        self.ai_api_key: str = ai_api_key
        self.start_time: datetime.datetime = datetime.datetime.now(datetime.timezone.utc)
        self.is_model_connected: bool = False
        self._model_listener: Optional[asyncio.Task] = None

    async def set_websocket(self, role: WebSocketRole, ws: WebSocket):
        '''
        Asynchronously sets or updates a `WebSocket` connection for a specific role.

        Parameters
        ----------
        - `role` : `WebSocketRole`
            An enumeration indicating the type of service this `WebSocket`
            connection is for (e.g., TWILIO, FRONTEND, MODEL).
        - `ws` : `WebSocket`
            The new `WebSocket` object to be assigned to the specified role.

        Description
        -----------
        This function manages `WebSocket` connections for different services (Twilio,
        Frontend, Model). When a new `WebSocket` is provided for a role that already
        has an active connection, this function will attempt to gracefully close
        the existing `WebSocket` before assigning the new one. If closing the old
        `WebSocket` fails, the error is silently ignored, and the new `WebSocket`
        is assigned regardless.
        '''
        match role:
            case WebSocketRole.TWILIO:
                if self.ws_twilio and self.ws_twilio != ws:
                    try: await self.ws_twilio.close(code=1000)
                    except Exception: pass
                self.ws_twilio = ws
                asyncio.create_task(self.connect_model())
            case WebSocketRole.FRONTEND:
                if self.ws_frontend and self.ws_frontend != ws:
                    self.ws_frontend = ws
                    try: await self.ws_frontend.close(code=1000)
                    except Exception: pass
            case WebSocketRole.MODEL:
                if self.ws_model and self.ws_model != ws:
                    self.ws_model = ws
                    try: await self.ws_model.close(code=1000)
                    except Exception: pass

    async def remove_websocket(self, role: WebSocketRole):
        '''
        Asynchronously removes and closes a `WebSocket` connection for a specific role.

        Parameters
        ----------
        - `role` : `WebSocketRole`
            An enumeration indicating the type of service whose `WebSocket`
            connection is to be removed (e.g., TWILIO, FRONTEND, MODEL).

        Description
        -----------
        This function attempts to gracefully close the `WebSocket` connection
        associated with the given role. If the `WebSocket` exists, it will be
        closed with a standard code (1000). Any exceptions during the closure
        are silently ignored. After attempting to close, the `WebSocket`
        reference for that role is set to `None`.
        '''
        match role:
            case WebSocketRole.TWILIO:
                if self.ws_twilio:
                    try: await self.ws_twilio.close(code=1000)
                    except Exception: pass
                self.ws_twilio = None
            case WebSocketRole.FRONTEND:
                if self.ws_frontend:
                    try: await self.ws_frontend.close(code=1000)
                    except Exception: pass
                self.ws_frontend = None
            case WebSocketRole.MODEL:
                if self.ws_model:
                    try: await self.ws_model.close(code=1000)
                    except Exception: pass
                self.ws_model = None

    async def send_to_websocket(self, role: WebSocketRole, data: Any):
        '''
        Asynchronously sends data to a `WebSocket` connection for a specific role.

        Parameters
        ----------
        - `role` : `WebSocketRole`
            An enumeration indicating the type of service to which the data
            should be sent (e.g., TWILIO, FRONTEND, MODEL).
        - `data` : `Any`
            The data to be sent over the `WebSocket`. For TWILIO and FRONTEND,
            it's expected to be sent as JSON. For MODEL, it's converted to a
            JSON string.

        Description
        -----------
        This function attempts to send the provided data to the `WebSocket`
        associated with the given role.
        For TWILIO and FRONTEND roles, it uses `send_json`.
        For the MODEL role, it converts the data to a JSON string and uses `send`.
        It includes error handling for `ConnectionClosed` exceptions specifically
        for the MODEL `WebSocket`, updating `is_model_connected` status, and
        logs warnings for other exceptions during sending. Any exceptions for
        TWILIO and FRONTEND roles are silently ignored.
        '''
        match role:
            case WebSocketRole.TWILIO:
                if self.ws_twilio:
                    try: await self.ws_twilio.send_json(data)
                    except Exception: pass
            case WebSocketRole.FRONTEND:
                if self.ws_frontend:
                    try: await self.ws_frontend.send_json(data)
                    except Exception: pass
            case WebSocketRole.MODEL:
                if self.ws_model and self.is_model_connected:
                    msg = ''
                    try:
                        msg = json.dumps(data)
                        await self.ws_model.send(msg)
                    except ws_exceptions.ConnectionClosed as e:
                        log(LogLevel.WARNING, f'LLM connection closed while sending {e}')
                        self.is_model_connected = False
                    except Exception as e:
                        log(LogLevel.WARNING, f'Error sending to LLM {e}')

    async def connect_model(self):
        firestore.create_call_document(self.stream_sid, self.config)

    async def close_connections(self, reason: str = 'Session ended'):
        log(LogLevel.INFO, f'Closing connections. Reason: {reason}')
        pass


class OpenAISession(Session):
    def __init__(self, stream_sid: str, ai_api_key: str, config: Optional[openai.SessionConfig] = None):
        super().__init__(stream_sid, ai_api_key, config)

    async def connect_model(self):
        await super().connect_model()

        openai_ws_url = 'wss://api.openai.com/v1/realtime?model=gpt-4o-realtime-preview' 
        headers = [
            ('Authorization', f'Bearer {self.ai_api_key}'),
            ('OpenAI-Beta', 'realtime=v1'),
        ]
        print(openai_ws_url + '\n' + str(headers))
        try:
            self.ws_model = await websockets.connect(openai_ws_url, additional_headers=headers)
            print(f'ws_model: {self.ws_model}')
            self.is_model_connected = True  

            await self.configure_model()
            if not self.is_model_connected:
                if self.ws_model:
                    try: await self.ws_model.close()
                    except: pass
                self.ws_model = None
                return
            
            if self._model_listener: self._model_listener.cancel()
            self._model_listener = asyncio.create_task(self._run_model_listener())

        except Exception as e:
            log(LogLevel.WARNING, f'Failed to connect to OpenAI model: {e}')
            self.ws_model = None; self.is_model_connected = False

    async def configure_model(self):
        # https://platform.openai.com/docs/api-reference/realtime-client-events/session/update
        update_event = openai.SessionUpdateEvent(session=self.config)
        await self.send_to_websocket(WebSocketRole.MODEL, update_event.model_dump(exclude_none=True))

    async def _run_model_listener(self):
        try:
            async for msg in self.ws_model:
                log(LogLevel.INFO, 'Received Event:')
                log(LogLevel.INFO, msg)
                try:
                    event = json.loads(msg)
                    match event.get('type'):

                        # https://platform.openai.com/docs/api-reference/realtime-server-events/response/audio/delta
                        case 'response.audio.delta':

                            # https://www.twilio.com/docs/voice/media-streams/websocket-messages#send-a-media-message
                            await self.send_to_websocket(WebSocketRole.TWILIO, {
                                'event': 'media',
                                'streamSid': self.stream_sid,
                                'media': {'payload': event.get('delta')}
                            })
                            # https://www.twilio.com/docs/voice/media-streams/websocket-messages#send-a-mark-message
                            await self.send_to_websocket(WebSocketRole.TWILIO, {
                                'event': 'mark',
                                'streamSid': self.stream_sid,
                                'name': 'response_audio_chunk_sent' 
                            })

                        # https://platform.openai.com/docs/api-reference/realtime-server-events/response/done
                        # https://platform.openai.com/docs/api-reference/realtime-server-events/conversation/item/input_audio_transcription/completed
                        case 'response.done' | 'conversation.item.input_audio_transcription.completed':
                            event['timestamp'] = datetime.datetime.now(datetime.timezone.utc)
                            firestore.add_event_to_call_document(self.stream_sid, event)

                        # TODO: Implement text streaming to firestore (not working)
                        # https://platform.openai.com/docs/api-reference/realtime-server-events/response/text/delta
                        # https://platform.openai.com/docs/api-reference/realtime-server-events/response/text/done
                        # case 'response.text.delta' | 'response.text.done':
                        #     event['timestamp'] = datetime.datetime.now(datetime.timezone.utc)
                        #     firestore.add_event_to_call_document(self.stream_sid, event)

                except Exception as e:
                    log(LogLevel.WARNING, f'Model listener: Error processing event: {e}')
        except ws_exceptions.ConnectionClosed as e:
            log(LogLevel.WARNING, f'Model listener: Connection closed - {e}')
        except Exception as e:
            log(LogLevel.WARNING, f'Unhandled error: {e}')
        finally:
            log(LogLevel.INFO, 'Model listener stopped.')
            self.is_model_connected = False
            if self.ws_model and not self.ws_model.closed:
                try: await self.ws_model.close()
                except: pass
            self.ws_model = None

    async def _run_twilio_listener():
        pass

    async def close_connections(self, reason: str = 'Session ended'):
        await super().close_connections(reason=reason)
        
        if self._model_listener and not self._model_listener.done():
            self._model_listener.cancel()
            try: await self._model_listener
            except asyncio.CancelledError: log(LogLevel.INFO, 'Model listener cancelled.')

        for ws in [self.ws_frontend, self.ws_twilio, self.ws_model]:
            if ws:
                try:
                    if hasattr(ws, 'close'): await ws.close(code=1000, reason=reason)
                except Exception: pass
                finally: ws = None
        self.is_model_connected = False
        log(LogLevel.INFO, 'All connections successfully closed.')


_active_sessions: Dict[str, Session] = {}  # (k, v) = (Stream SID, Session)


async def get(stream_sid: str):
    return _active_sessions.get(stream_sid)

async def create(stream_sid: str, ai_api_key: str) -> OpenAISession:
    if stream_sid in _active_sessions:
        existing_session = await get(stream_sid)
        if existing_session: # Should always be true
             return existing_session
    
    # Initial configuration for the AI to speak first and handle audio correctly
    init_config = openai.SessionConfig(
        instructions='You are a helpful AI assistant!',
        output_audio_format=openai.OutputAudioFormatEnum.G711_ULAW,   # Twilio expects mu-law (audio/x-mulaw)
        voice=openai.VoiceEnum.ALLOY,
        input_audio_format=openai.InputAudioFormatEnum.G711_ULAW,  # Twilio sends mu-law (audio/x-mulaw)
        input_audio_transcription=openai.InputAudioTranscriptionConfig(
            model=openai.TranscriptionModelEnum.WHISPER_1
        ),
        turn_detection=openai.TurnDetectionConfig(
            type=openai.TurnDetectionTypeEnum.SERVER_VAD,
            create_response=True
        )
    )
    session = OpenAISession(stream_sid, ai_api_key, config=init_config)
    _active_sessions[stream_sid] = session
    # log(LogLevel.INFO, f'OpenAISession created and stored for {stream_sid}.')
    return session

async def remove(stream_sid: str, reason = 'Session ended.'):
    session = _active_sessions.pop(stream_sid, None)
    if session:
        await session.close_connections(reason=reason)