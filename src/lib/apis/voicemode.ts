import { WEBUI_BASE_URL } from '$lib/constants';

export interface LiveKitTokenRequest {
	identity: string;
	room: string;
}

export interface LiveKitTokenResponse {
	token: string;
	url: string;
}

export interface VoiceModeConfig {
	enabled: boolean;
	livekit_url: string;
}

/**
 * Get LiveKit token for joining a voice session
 */
export const getLiveKitToken = async (
	token: string,
	identity: string,
	room: string
): Promise<LiveKitTokenResponse> => {
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/api/v1/voicemode/token`, {
		method: 'POST',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		},
		body: JSON.stringify({
			identity,
			room
		})
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error('Failed to get LiveKit token:', err);
			error = err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};

/**
 * Get VoiceMode configuration
 */
export const getVoiceModeConfig = async (token: string): Promise<VoiceModeConfig> => {
	let error = null;

	const res = await fetch(`${WEBUI_BASE_URL}/api/v1/voicemode/config`, {
		method: 'GET',
		headers: {
			Accept: 'application/json',
			'Content-Type': 'application/json',
			Authorization: `Bearer ${token}`
		}
	})
		.then(async (res) => {
			if (!res.ok) throw await res.json();
			return res.json();
		})
		.catch((err) => {
			console.error('Failed to get VoiceMode config:', err);
			error = err;
			return null;
		});

	if (error) {
		throw error;
	}

	return res;
};