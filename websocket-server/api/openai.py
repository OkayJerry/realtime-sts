from enum import Enum
from typing import List, Optional, Union, Literal, Any, Dict, Annotated
from pydantic import BaseModel, Field # conint and confloat are effectively replaced by Annotated + Field

# --- Enumerations ---
class InputAudioFormatEnum(str, Enum):
    """Supported formats for input audio."""
    PCM16 = "pcm16"
    G711_ULAW = "g711_ulaw"
    G711_ALAW = "g711_alaw"

class OutputAudioFormatEnum(str, Enum):
    """Supported formats for output audio."""
    PCM16 = "pcm16"
    G711_ULAW = "g711_ulaw"
    G711_ALAW = "g711_alaw"

class ToolChoiceOptionsEnum(str, Enum):
    """Options for how the model chooses tools."""
    AUTO = "auto"
    NONE = "none"
    REQUIRED = "required"

class VoiceEnum(str, Enum):
    """Available voices for the model's response."""
    ALLOY = "alloy"
    ASH = "ash"
    BALLAD = "ballad"
    CORAL = "coral"
    ECHO = "echo"
    SAGE = "sage"
    SHIMMER = "shimmer"

class NoiseReductionTypeEnum(str, Enum):
    """Type of noise reduction."""
    NEAR_FIELD = "near_field" # For close-talking microphones
    FAR_FIELD = "far_field"   # For far-field microphones

class TranscriptionModelEnum(str, Enum):
    """Models available for input audio transcription."""
    GPT_4O_TRANSCRIBE = "gpt-4o-transcribe"
    GPT_4O_MINI_TRANSCRIBE = "gpt-4o-mini-transcribe"
    WHISPER_1 = "whisper-1"

class TurnDetectionEagernessEnum(str, Enum):
    """Eagerness levels for Semantic VAD in turn detection."""
    LOW = "low"
    MEDIUM = "medium" # auto is equivalent to medium
    HIGH = "high"
    AUTO = "auto"

class TurnDetectionTypeEnum(str, Enum):
    """Type of turn detection."""
    SERVER_VAD = "server_vad"
    SEMANTIC_VAD = "semantic_vad"


# --- Nested Configuration Models ---
class ExpiresAtConfig(BaseModel):
    """Configuration for the ephemeral token expiration."""
    anchor: Literal["created_at"] = Field(..., description="The anchor point for expiration, currently only 'created_at'.")
    seconds: Annotated[int, Field(ge=10, le=7200)] = Field(..., description="Seconds from anchor to expiration (10-7200).")

class ClientSecretConfig(BaseModel):
    """Configuration options for the generated client secret."""
    expires_at: Optional[ExpiresAtConfig] = Field(None, description="Configuration for the ephemeral token expiration.")

class InputAudioNoiseReductionConfig(BaseModel):
    """
    Configuration for input audio noise reduction.
    Can be set to null to turn off.
    """
    type: Optional[NoiseReductionTypeEnum] = Field(None, description="Type of noise reduction: 'near_field' or 'far_field'.")

class InputAudioTranscriptionConfig(BaseModel):
    """
    Configuration for input audio transcription.
    Defaults to off and can be set to null to turn off once on.
    """
    language: Optional[str] = Field(None, description="Language of input audio in ISO-639-1 format (e.g., 'en') to improve accuracy.")
    model: Optional[TranscriptionModelEnum] = Field(None, description="Transcription model to use.")
    prompt: Optional[str] = Field(None, description="Optional text to guide the model's style or continue a previous audio segment.")

class ToolFunctionDefinition(BaseModel):
    """Defines the structure of a function tool."""
    name: str = Field(..., description="The name of the function to be called.")
    description: Optional[str] = Field(None, description="Description of what the function does, guidance on when/how to call it.")
    parameters: Dict[str, Any] = Field(..., description="Parameters the function accepts, in JSON Schema format.")

class ToolConfig(BaseModel):
    """Configuration for a single tool (function) available to the model."""
    type: Literal["function"] = Field("function", description="The type of the tool, must be 'function'.")
    function: ToolFunctionDefinition

class TurnDetectionConfig(BaseModel):
    """
    Configuration for turn detection.
    Can be set to null to turn off.
    """
    create_response: Optional[bool] = Field(None, description="Whether to automatically generate a response on VAD stop.")
    eagerness: Optional[TurnDetectionEagernessEnum] = Field(None, description="Eagerness for Semantic VAD: 'low', 'medium', 'high', or 'auto'.")
    interrupt_response: Optional[bool] = Field(None, description="Whether to automatically interrupt ongoing response on VAD start.")
    prefix_padding_ms: Optional[int] = Field(None, description="Audio to include before VAD detected speech (ms). Server VAD only. Defaults to 300ms.")
    silence_duration_ms: Optional[int] = Field(None, description="Duration of silence to detect speech stop (ms). Server VAD only. Defaults to 500ms.")
    threshold: Optional[Annotated[float, Field(ge=0.0, le=1.0)]] = Field(None, description="Activation threshold for VAD (0.0-1.0). Server VAD only. Defaults to 0.5.")
    type: Optional[TurnDetectionTypeEnum] = Field(None, description="Type of turn detection (e.g., 'server_vad', 'semantic_vad').")


# --- Session Configuration ---
class SessionConfig(BaseModel):
    """
    Realtime session object configuration.

    Parameters
    ----------
    - `client_secret` : `Optional[ClientSecretConfig]`
        Configuration options for the generated client secret.
    - `input_audio_format` : `Optional[InputAudioFormatEnum]`
        The format of input audio (e.g., `pcm16`).
    - `input_audio_noise_reduction` : `Optional[Union[InputAudioNoiseReductionConfig, None]]`
        Configuration for input audio noise reduction. Set to `None` (null) to disable.
    - `input_audio_transcription` : `Optional[Union[InputAudioTranscriptionConfig, None]]`
        Configuration for input audio transcription. Set to `None` (null) to disable.
    - `instructions` : `Optional[str]`
        Default system instructions for the model. Pass an empty string to clear.
    - `max_response_output_tokens` : `Optional[Union[Annotated[int, Field(ge=1, le=4096)], Literal["inf"]]]`
        Maximum number of output tokens. Defaults to "inf".
    - `modalities` : `Optional[List[str]]`
        Set of modalities for model response (e.g., `["text"]` to disable audio).
    - `model` : `Optional[str]`
        The Realtime model. Cannot be changed via update once a session is initialized with a model.
    - `output_audio_format` : `Optional[OutputAudioFormatEnum]`
        Format of output audio (e.g., `pcm16`).
    - `temperature` : `Optional[Annotated[float, Field(ge=0.6, le=1.2)]]`
        Sampling temperature for the model ([0.6, 1.2]). Recommended 0.8 for audio.
    - `tool_choice` : `Optional[Union[ToolChoiceOptionsEnum, str]]`
        How the model chooses tools (`auto`, `none`, `required`, or a specific function name).
    - `tools` : `Optional[List[ToolConfig]]`
        Tools (functions) available to the model.
    - `turn_detection` : `Optional[Union[TurnDetectionConfig, None]]`
        Configuration for turn detection. Set to `None` (null) to disable.
    - `voice` : `Optional[VoiceEnum]`
        The voice the model uses. Cannot be changed via update after the model has responded with audio.

    Description
    -----------
    This model defines the fields that can be updated within a session's
    configuration. Only the fields provided in the request are updated.
    """
    client_secret: Optional[ClientSecretConfig] = Field(None, description="Configuration options for the generated client secret.")
    input_audio_format: Optional[InputAudioFormatEnum] = Field(None, description="The format of input audio (e.g., pcm16, g711_ulaw).")
    input_audio_noise_reduction: Optional[Union[InputAudioNoiseReductionConfig, None]] = Field(None, description="Configuration for input audio noise reduction. Set to None to disable.")
    input_audio_transcription: Optional[Union[InputAudioTranscriptionConfig, None]] = Field(None, description="Configuration for input audio transcription. Set to None to disable.")
    instructions: Optional[str] = Field(None, description="Default system instructions. Pass an empty string to clear.")
    max_response_output_tokens: Optional[Union[Annotated[int, Field(ge=1, le=4096)], Literal["inf"]]] = Field("inf", description="Maximum number of output tokens for a single assistant response (1-4096 or 'inf').")
    modalities: Optional[List[str]] = Field(None, description="The set of modalities the model can respond with (e.g., ['text'] to disable audio).")
    model: Optional[str] = Field(None, description="The Realtime model used for this session. Cannot be changed via update after initialization.")
    output_audio_format: Optional[OutputAudioFormatEnum] = Field(None, description="The format of output audio (e.g., pcm16, g711_ulaw).")
    temperature: Optional[Annotated[float, Field(ge=0.6, le=1.2)]] = Field(None, description="Sampling temperature for the model ([0.6, 1.2]). Recommended 0.8 for audio models.")
    tool_choice: Optional[Union[ToolChoiceOptionsEnum, str]] = Field(None, description="How the model chooses tools ('auto', 'none', 'required', or a function name).")
    tools: Optional[List[ToolConfig]] = Field(None, description="Tools (functions) available to the model.")
    turn_detection: Optional[Union[TurnDetectionConfig, None]] = Field(None, description="Configuration for turn detection. Set to None to disable.")
    voice: Optional[VoiceEnum] = Field(None, description="The voice the model uses to respond. Cannot be changed via update after the model has first responded with audio.")


# --- Main Event Model: session.update ---
class SessionUpdateEvent(BaseModel):
    """
    Event to update the session’s default configuration.

    Parameters
    ----------
    - `event_id` : `Optional[str]`
        Optional client-generated ID for this event.
    - `session` : `SessionConfig`
        The session configuration object. Only present fields are updated.
    - `type` : `Literal["session.update"]`
        The event type, must be the string "session.update".

    Description
    -----------
    The client sends this event to update session fields. Restrictions apply
    to updating `voice` and `model` under certain conditions. The server
    responds with a `session.updated` event showing the full configuration.
    To clear a field like `instructions`, pass an empty string.
    """
    event_id: Optional[str] = Field(None, description="Optional client-generated ID used to identify this event.")
    session: SessionConfig = Field(..., description="Realtime session object configuration to update.")
    type: Literal["session.update"] = Field("session.update", description="The event type, must be 'session.update'.")

