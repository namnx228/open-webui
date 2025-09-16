import logging
import requests
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from open_webui.utils.auth import get_verified_user
from open_webui.env import (
    VOICEMODE_ENABLED,
    VOICEMODE_TOKEN_SERVER_URL,
    LIVEKIT_URL,
    SRC_LOG_LEVELS,
)

router = APIRouter()

log = logging.getLogger(__name__)
log.setLevel(SRC_LOG_LEVELS.get("VOICEMODE", "INFO"))


class LiveKitTokenRequest(BaseModel):
    identity: str
    room: str


class LiveKitTokenResponse(BaseModel):
    token: str
    url: str


@router.post("/token", response_model=LiveKitTokenResponse)
async def get_livekit_token(
    request_data: LiveKitTokenRequest,
    user=Depends(get_verified_user)
):
    """
    Proxy endpoint to get LiveKit token from voicemode token server
    """
    if not VOICEMODE_ENABLED:
        raise HTTPException(
            status_code=503,
            detail="VoiceMode is not enabled. Please configure VOICEMODE_ENABLED=true"
        )

    try:
        # Forward request to voicemode token server
        response = requests.post(
            VOICEMODE_TOKEN_SERVER_URL,
            json={
                "identity": request_data.identity,
                "room": request_data.room
            },
            timeout=10
        )
        response.raise_for_status()

        token_data = response.json()

        # Return token and URL
        return LiveKitTokenResponse(
            token=token_data["token"],
            url=token_data.get("url", LIVEKIT_URL)
        )

    except requests.RequestException as e:
        log.error(f"Failed to get LiveKit token: {e}")
        raise HTTPException(
            status_code=503,
            detail=f"Failed to connect to voicemode token server: {str(e)}"
        )
    except KeyError as e:
        log.error(f"Invalid response from token server: {e}")
        raise HTTPException(
            status_code=502,
            detail="Invalid response from voicemode token server"
        )


@router.get("/config")
async def get_voicemode_config(user=Depends(get_verified_user)):
    """
    Get VoiceMode configuration
    """
    return {
        "enabled": VOICEMODE_ENABLED,
        "livekit_url": LIVEKIT_URL,
    }