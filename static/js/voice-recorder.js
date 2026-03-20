/**
 * Voice recorder Alpine.js component.
 *
 * States: idle → recording → processing → idle
 * Max duration: 60s, visual warning at 45s, auto-stop at 60s.
 * Cancel discards audio, stop/send submits for transcription.
 */
function voiceRecorder() {
    return {
        canRecord: !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia),
        recording: false,
        processing: false,
        elapsed: 0,
        _mediaRecorder: null,
        _chunks: [],
        _timer: null,
        _stream: null,

        formatTime(seconds) {
            const m = Math.floor(seconds / 60);
            const s = seconds % 60;
            return `${m}:${String(s).padStart(2, '0')}`;
        },

        async startRecording() {
            if (this.recording || this.processing) return;

            try {
                this._stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            } catch (err) {
                this._showError('Microphone unavailable');
                return;
            }

            this._chunks = [];
            this.elapsed = 0;

            // Prefer webm, fall back to whatever is available
            const mimeType = MediaRecorder.isTypeSupported('audio/webm;codecs=opus')
                ? 'audio/webm;codecs=opus'
                : MediaRecorder.isTypeSupported('audio/webm')
                    ? 'audio/webm'
                    : '';

            try {
                this._mediaRecorder = new MediaRecorder(this._stream, mimeType ? { mimeType } : {});
            } catch (err) {
                this._cleanup();
                this._showError('Recording not supported');
                return;
            }

            this._mediaRecorder.ondataavailable = (e) => {
                if (e.data.size > 0) this._chunks.push(e.data);
            };

            this._mediaRecorder.onerror = () => {
                this._cleanup();
                this._showError('Recording failed');
            };

            this._mediaRecorder.onstop = () => {
                // Handled in stopAndSend / cancelRecording
            };

            this._mediaRecorder.start(250); // collect chunks every 250ms
            this.recording = true;

            // Timer
            this._timer = setInterval(() => {
                this.elapsed++;
                if (this.elapsed >= 60) {
                    this.stopAndSend();
                }
            }, 1000);

            // Warn before unload
            window.addEventListener('beforeunload', this._beforeUnload);
        },

        async stopAndSend() {
            if (!this.recording) return;

            this.recording = false;
            this.processing = true;
            clearInterval(this._timer);

            // Stop the recorder and wait for final data
            await new Promise((resolve) => {
                this._mediaRecorder.onstop = resolve;
                this._mediaRecorder.stop();
            });

            this._stopStream();
            window.removeEventListener('beforeunload', this._beforeUnload);

            if (this._chunks.length === 0) {
                this.processing = false;
                return;
            }

            const blob = new Blob(this._chunks, { type: this._mediaRecorder.mimeType || 'audio/webm' });
            const formData = new FormData();
            formData.append('audio', blob, 'recording.webm');

            // Set inflight on the parent chat form's Alpine data
            const chatForm = document.getElementById('chat-form');

            try {
                const response = await fetch(this._voiceSendUrl(), {
                    method: 'POST',
                    body: formData,
                    headers: {
                        'X-CSRFToken': this._getCsrf(),
                    },
                });

                if (response.ok) {
                    const html = await response.text();
                    const messagesContainer = document.getElementById('messages');
                    if (messagesContainer) {
                        messagesContainer.insertAdjacentHTML('beforeend', html);
                        messagesContainer.scrollTop = messagesContainer.scrollHeight;
                    }
                    // Re-render Lucide icons for new content
                    if (window.lucide) lucide.createIcons();
                } else {
                    this._showError("Couldn't process audio");
                }
            } catch (err) {
                this._showError("Couldn't process audio");
            }

            this.processing = false;
            this._chunks = [];
        },

        cancelRecording() {
            if (!this.recording) return;

            this.recording = false;
            clearInterval(this._timer);

            if (this._mediaRecorder && this._mediaRecorder.state !== 'inactive') {
                this._mediaRecorder.stop();
            }

            this._stopStream();
            this._chunks = [];
            this.elapsed = 0;
            window.removeEventListener('beforeunload', this._beforeUnload);
        },

        _cleanup() {
            this.recording = false;
            this.processing = false;
            clearInterval(this._timer);
            this._stopStream();
            this._chunks = [];
            this.elapsed = 0;
        },

        _stopStream() {
            if (this._stream) {
                this._stream.getTracks().forEach(t => t.stop());
                this._stream = null;
            }
        },

        _showError(msg) {
            // Use the existing toast system if available, otherwise console
            if (window.clintelaChat && window.clintelaChat.showToast) {
                window.clintelaChat.showToast(msg, 'error');
            } else {
                console.error('[VoiceRecorder]', msg);
            }
        },

        _voiceSendUrl() {
            // Derive from the chat send URL pattern
            const chatUrl = document.getElementById('chat-form')?.getAttribute('hx-post') || '';
            return chatUrl.replace('chat/send/', 'voice/send/');
        },

        _getCsrf() {
            const el = document.querySelector('[name=csrfmiddlewaretoken]');
            if (el) return el.value;
            const cookie = document.cookie.split(';').find(c => c.trim().startsWith('csrftoken='));
            return cookie ? cookie.split('=')[1] : '';
        },

        _beforeUnload(e) {
            e.preventDefault();
            e.returnValue = '';
        },
    };
}
