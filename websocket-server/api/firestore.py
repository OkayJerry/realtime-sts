import os
from typing import Any
import firebase_admin
from firebase_admin import credentials, firestore

from logger import log, LogLevel
from api.openai import SessionConfig

from dotenv import load_dotenv

load_dotenv(override=True)

FIRESTORE_CALLS_COLLECTION = 'calls'

firebase_service_account_key_path = os.getenv('FIREBASE_SERVICE_ACCOUNT_KEY_PATH')
_firestore_client = None

if firebase_service_account_key_path:
    try:
        if not firebase_admin._apps:
            print(firebase_service_account_key_path)
            cred = credentials.Certificate(firebase_service_account_key_path)
            firebase_admin.initialize_app(cred)
        _firestore_client = firestore.client()
    except Exception as e:
        log(LogLevel.CRITICAL, f'Firestore client initialization failed: {e}')
        exit(1)
else:
    log(LogLevel.CRITICAL, 'FIREBASE_SERVICE_ACCOUNT_KEY_PATH environment variable is not set.')
    exit(1)

def create_call_document(stream_sid: str, session_config: SessionConfig):
    call_document = {
        'stream_sid': stream_sid,
        'session_config': session_config.model_dump(),
        'events': [],
        'created_at': firestore.SERVER_TIMESTAMP
    }

    try:
        doc_ref = _firestore_client.collection(FIRESTORE_CALLS_COLLECTION).document(stream_sid)
        doc_ref.set(call_document)
    except Exception as e:
        log(LogLevel.WARNING, f'Failed to create call document: {e}')

def add_event_to_call_document(stream_sid: str, event_data: Any):
    try:
        doc_ref = _firestore_client.collection(FIRESTORE_CALLS_COLLECTION).document(stream_sid)
        doc_ref.update({'events': firestore.ArrayUnion([event_data])})
    except Exception as e:
        log(LogLevel.WARNING, f'Failed to add event to call document: {e}') 