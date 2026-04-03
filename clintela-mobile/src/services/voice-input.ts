/**
 * Voice input service — native speech recognition with Whisper fallback.
 *
 * State machine:
 *   Idle → Listening → Processing → Transcription → Idle
 *                  └→ Error → Idle
 *
 * Strategy:
 *   1. Use iOS Speech / Android SpeechRecognizer (on-device, zero latency)
 *   2. If on-device confidence < 0.7, silently fall back to server-side Whisper
 *   3. No user-visible indicator of which engine produced the transcription
 *
 * The state machine drives the UI: pulsing teal ring (listening),
 * spinner (processing), typewriter effect (transcription), red flash (error).
 */

export type VoiceState = "idle" | "listening" | "processing" | "transcription" | "error";

export interface VoiceInputConfig {
  baseUrl: string;
  onStateChange: (state: VoiceState) => void;
  onTranscription: (text: string) => void;
  onError: (message: string) => void;
  maxDuration?: number; // seconds, default 30
  whisperConfidenceThreshold?: number; // default 0.7
}

const DEFAULT_MAX_DURATION = 30;
const DEFAULT_CONFIDENCE_THRESHOLD = 0.7;
const WHISPER_ENDPOINT = "/api/v1/voice/transcribe/";

let currentState: VoiceState = "idle";
let mediaRecorder: MediaRecorder | null = null;
let audioChunks: Blob[] = [];
let silenceTimer: ReturnType<typeof setTimeout> | null = null;

/**
 * Start voice recording.
 * Uses the Web Audio API for recording, with SpeechRecognition for on-device
 * transcription when available.
 */
export async function startListening(config: VoiceInputConfig): Promise<void> {
  if (currentState !== "idle") {
    console.warn("[Voice] Cannot start: already in state", currentState);
    return;
  }

  const maxDuration = config.maxDuration ?? DEFAULT_MAX_DURATION;

  try {
    setState("listening", config);

    // Request microphone access
    const stream = await navigator.mediaDevices.getUserMedia({
      audio: {
        echoCancellation: true,
        noiseSuppression: true,
        sampleRate: 16000,
      },
    });

    audioChunks = [];
    mediaRecorder = new MediaRecorder(stream, {
      mimeType: getSupportedMimeType(),
    });

    mediaRecorder.ondataavailable = (event) => {
      if (event.data.size > 0) {
        audioChunks.push(event.data);
      }
    };

    mediaRecorder.onstop = async () => {
      stream.getTracks().forEach((track) => track.stop());
      await processAudio(config);
    };

    mediaRecorder.start(250); // Collect in 250ms chunks

    // Auto-stop after max duration
    silenceTimer = setTimeout(() => {
      stopListening(config);
    }, maxDuration * 1000);

    // Try on-device speech recognition in parallel
    tryOnDeviceRecognition(config);
  } catch (error) {
    setState("error", config);
    config.onError("Couldn't access microphone. Check permissions.");
    setTimeout(() => setState("idle", config), 3000);
  }
}

/**
 * Stop voice recording and process the audio.
 */
export function stopListening(config: VoiceInputConfig): void {
  if (silenceTimer) {
    clearTimeout(silenceTimer);
    silenceTimer = null;
  }

  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
  }
}

/**
 * Get the current voice input state.
 */
export function getVoiceState(): VoiceState {
  return currentState;
}

/**
 * Process recorded audio — on-device first, Whisper fallback if low confidence.
 */
async function processAudio(config: VoiceInputConfig): Promise<void> {
  setState("processing", config);

  const threshold = config.whisperConfidenceThreshold ?? DEFAULT_CONFIDENCE_THRESHOLD;

  // If on-device recognition already produced a result, use it
  if (onDeviceResult && onDeviceConfidence >= threshold) {
    setState("transcription", config);
    config.onTranscription(onDeviceResult);
    resetOnDeviceState();
    setTimeout(() => setState("idle", config), 100);
    return;
  }

  // Fall back to server-side Whisper
  try {
    const audioBlob = new Blob(audioChunks, { type: getSupportedMimeType() });
    const text = await sendToWhisper(config.baseUrl, audioBlob);

    if (text) {
      setState("transcription", config);
      config.onTranscription(text);
    } else {
      setState("error", config);
      config.onError("Couldn't hear that. Tap to try again.");
    }
  } catch {
    setState("error", config);
    config.onError("Couldn't hear that. Tap to try again.");
  }

  resetOnDeviceState();
  setTimeout(() => setState("idle", config), 3000);
}

/**
 * Send audio to server-side Whisper for transcription.
 */
async function sendToWhisper(baseUrl: string, audioBlob: Blob): Promise<string | null> {
  const formData = new FormData();
  formData.append("audio", audioBlob, "recording.webm");

  const response = await fetch(`${baseUrl}${WHISPER_ENDPOINT}`, {
    method: "POST",
    credentials: "include",
    body: formData,
  });

  if (response.ok) {
    const data = await response.json();
    return data.text || null;
  }

  return null;
}

// ─── On-device Speech Recognition ──────────────────────────────────

let onDeviceResult: string | null = null;
let onDeviceConfidence = 0;
let recognition: SpeechRecognition | null = null;

function tryOnDeviceRecognition(config: VoiceInputConfig): void {
  const SpeechRecognitionAPI =
    (window as unknown as Record<string, unknown>).SpeechRecognition ||
    (window as unknown as Record<string, unknown>).webkitSpeechRecognition;

  if (!SpeechRecognitionAPI) return;

  recognition = new (SpeechRecognitionAPI as new () => SpeechRecognition)();
  recognition.continuous = false;
  recognition.interimResults = false;
  recognition.lang = "en-US";

  recognition.onresult = (event: SpeechRecognitionEvent) => {
    const result = event.results[0];
    if (result) {
      onDeviceResult = result[0].transcript;
      onDeviceConfidence = result[0].confidence;
    }
  };

  recognition.onerror = () => {
    // Silently fall through to Whisper
    onDeviceResult = null;
    onDeviceConfidence = 0;
  };

  recognition.start();
}

function resetOnDeviceState(): void {
  onDeviceResult = null;
  onDeviceConfidence = 0;
  if (recognition) {
    try {
      recognition.stop();
    } catch {
      // Already stopped
    }
    recognition = null;
  }
}

// ─── Helpers ──────────────────────────────────────────────────────

function setState(state: VoiceState, config: VoiceInputConfig): void {
  currentState = state;
  config.onStateChange(state);
}

function getSupportedMimeType(): string {
  if (MediaRecorder.isTypeSupported("audio/webm;codecs=opus")) {
    return "audio/webm;codecs=opus";
  }
  if (MediaRecorder.isTypeSupported("audio/mp4")) {
    return "audio/mp4";
  }
  return "audio/webm";
}
