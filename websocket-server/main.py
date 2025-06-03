# main.py
import os
import asyncio
import json
from pathlib import Path
from fastapi import FastAPI, WebSocket, HTTPException, WebSocketDisconnect
from fastapi.responses import PlainTextResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from urllib.parse import urlparse
import uvicorn
from starlette.websockets import WebSocketState

from logger import log, LogLevel

import sessions
from sessions import WebSocketRole


load_dotenv(override=True)

PORT = int(os.getenv('PORT', '8081'))
PUBLIC_URL = os.getenv('PUBLIC_URL', '')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY', '')
TWIML_FILE_PATH = Path(__file__).parent / 'twiml.xml'

if not OPENAI_API_KEY:
    log(LogLevel.CRITICAL, 'OPENAI_API_KEY environment variable is not set.')
    exit(1)
if not os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH'):
    log(LogLevel.CRITICAL, 'FIREBASE_SERVICE_ACCOUNT_KEY_PATH for Firebase Admin SDK must be set.')
    exit(1)

try:
    with open(TWIML_FILE_PATH, 'r') as f: TWIML_TEMPLATE = f.read()
except FileNotFoundError:
    log(LogLevel.CRITICAL, f'TwiML file not found at {TWIML_FILE_PATH}')
    exit(1)

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=['*'], allow_credentials=True, allow_methods=['*'], allow_headers=['*'],
)

@app.get('/public-url')
async def get_public_url_endpoint(): return JSONResponse({'publicUrl': PUBLIC_URL})

@app.post('/twiml')
@app.get('/twiml')
async def get_twiml_endpoint():
    # Assert requirements
    if not PUBLIC_URL: raise HTTPException(status_code=500, detail='PUBLIC_URL is not configured.')
    if not TWIML_TEMPLATE: raise HTTPException(status_code=500, detail='TwiML template not loaded.')
    
    # Convert HyperText Transfer Protocol Secure (https) to WebSocket Secure (wss)...
    # ... or convert HyperText Transfer Protocol (http) to WebSocket (ws)
    ws_parsed_url = urlparse(PUBLIC_URL)
    scheme = 'wss' if ws_parsed_url.scheme == 'https' else 'ws'
    ws_full_url = f'{scheme}://{ws_parsed_url.netloc}{ws_parsed_url.path.rstrip('/')}/call'

    # Inject new URL into Twilio Markup Language (TwiML)
    twiml_content = TWIML_TEMPLATE.replace('{{WS_URL}}', ws_full_url)

    return PlainTextResponse(twiml_content, media_type='application/xml')

@app.get('/tools')
async def get_tools_endpoint():
    pass


@app.websocket('/call')
async def websocket_call_endpoint(ws: WebSocket):
    print('calls')
    # Perform WebSocket 'handshake'
    await ws.accept()

    session = None

    # Inspect the first `N` messages from Twilio
    N = 10
    for i in range(N):  
        msg = await asyncio.wait_for(ws.receive_text(), timeout=10)
        payload = json.loads(msg)  # { 'event': 'connected' | 'start' | 'media', ... }
        log(LogLevel.INFO, payload)
        match payload.get('event'):
            case 'connected':  # Initial Twilio message
                '''
                # {'event': 'connected', 'protocol': 'Call', 'version': '1.0.0'}
                '''
                pass
            case 'start':  # Ready to connect to AI assistant
                '''
                { 'event': 'start',
                  'sequenceNumber': '1',
                  'start': { 'accountSid': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',

                             'callSid': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                             'customParameters': {},
                             'mediaFormat': { 'channels': 1,
                                              'encoding': 'audio/x-mulaw',
                                              'sampleRate': 8000},
                             'streamSid': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx',
                             'tracks': ['inbound']},
                  'streamSid': 'xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx'}
                '''
                start_payload = payload.get('start', {})
                stream_sid = start_payload.get('streamSid')
                
                session = await sessions.get(stream_sid)

                if not session:
                    session = await sessions.create(stream_sid, OPENAI_API_KEY)

                if session:
                    await session.set_websocket(sessions.WebSocketRole.TWILIO, ws)
                    break
    
    try:
        while True:
            msg = await ws.receive_text()
            payload = json.loads(msg)
            # log(LogLevel.INFO, payload)
            
            match payload.get('event'):
                case 'media':
                    media_payload = payload.get('media', {}).get('payload')

                    if session.ws_model and media_payload:
                        await session.send_to_websocket(WebSocketRole.MODEL, {
                            "type": "input_audio_buffer.append",
                            "audio": media_payload,
                        })
                case 'stop':
                    await sessions.remove(session.stream_sid, reason='Twilio call ended.')
    except WebSocketDisconnect:
        await sessions.remove(session.stream_sid, 'Twilio WebSocket disconnected.')
    except Exception as e:
        await sessions.remove(session.stream_sid, f'Error: {e}')
        if ws.client_state != WebSocketState.DISCONNECTED:
            try: await ws.close(code=1011)
            except Exception: pass

@app.websocket('/logs')
async def websocket_logs_endpoint(ws: WebSocket):
    pass
#     await websocket.accept()
#     query_params = parse_qs(str(websocket.query_params))
#     stream_sid_from_frontend = query_params.get('streamSid', [None])[0]
#     if not stream_sid_from_frontend:
#         # print('[Logs WS] Connection attempt without streamSid. Closing.')
#         await websocket.close(code=1008, reason='streamSid is required'); return
#     session = session_manager.get_session(stream_sid_from_frontend)
#     if not session:
#         print(f'[Logs WS] No active call session for streamSid: {stream_sid_from_frontend}. Closing.')
#         await websocket.close(code=1011, reason='No active call session found.'); return
#     await session.set_frontend_ws(websocket)
#     try:
#         while True:
#             data = await websocket.receive_text()
#             await session_manager.handle_frontend_message(session, data)
#     except WebSocketDisconnect: print(f'[Logs WS] Frontend WebSocket disconnected for {stream_sid_from_frontend}.')
#     except Exception as e: print(f'[Logs WS] Error for {stream_sid_from_frontend}: {e}')
#     finally:
#         if session: session.remove_frontend_ws()

if __name__ == '__main__':
    print(f'Starting Server on http://localhost:{PORT}')
    if not Path(TWIML_FILE_PATH).exists(): print(f"Warning: TwiML file '{TWIML_FILE_PATH}' not found.")
    if not os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH'): print('Warning: Firebase credentials not set.')
    uvicorn.run('main:app', host='0.0.0.0', port=PORT, reload=True)