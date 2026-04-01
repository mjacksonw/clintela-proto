/**
 * Support Group WebSocket client.
 *
 * Full bidirectional: patient sends messages via WS, receives persona
 * responses, reactions, and typing indicators via WS.
 *
 * Used as an Alpine.js component: x-data="supportGroupChat()"
 */

function supportGroupChat() {
  return {
    // Tab state
    activeTab: 'care_team',
    careTeamUnread: 0,
    supportGroupUnread: 0,

    // Support group state
    sgMessages: [],
    sgConnected: false,
    sgConnecting: false,
    sgOnboarded: false,
    sgTyping: null, // { persona_id, persona_name } or null

    // Internal
    _ws: null,
    _reconnectDelay: 1000,
    _reconnectTimer: null,
    _patientId: null,

    init() {
      this._patientId = window.__sgPatientId || document.body.dataset.patientId;
      if (!this._patientId) return;

      // Check onboarding state (server-side is authoritative, localStorage is fast-path cache)
      this.sgOnboarded = window.__sgOnboarded || localStorage.getItem('sg_onboarded') === 'true';

      // Load initial messages if any are rendered server-side
      const initialMessages = document.getElementById('sg-initial-messages');
      if (initialMessages) {
        try {
          this.sgMessages = JSON.parse(initialMessages.textContent || '[]');
          if (this.sgMessages.length > 0) {
            this.sgOnboarded = true;
          }
        } catch (e) { /* ignore */ }
      }

      // Connect WebSocket
      this._connect();
    },

    // -- Tab management --

    switchTab(tab) {
      this.activeTab = tab;
      if (tab === 'support_group') {
        this.supportGroupUnread = 0;
        this.$nextTick(() => this._scrollToBottom());
      } else {
        this.careTeamUnread = 0;
      }
    },

    // -- WebSocket connection --

    _connect() {
      if (this._ws) return;
      this.sgConnecting = true;

      const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
      const url = `${protocol}//${window.location.host}/ws/support-group/${this._patientId}/`;

      this._ws = new WebSocket(url);

      this._ws.onopen = () => {
        this.sgConnected = true;
        this.sgConnecting = false;
        this._reconnectDelay = 1000;
      };

      this._ws.onclose = () => {
        this.sgConnected = false;
        this.sgConnecting = false;
        this._ws = null;
        this._scheduleReconnect();
      };

      this._ws.onerror = () => {
        // onclose will fire after this
      };

      this._ws.onmessage = (event) => {
        this._handleMessage(JSON.parse(event.data));
      };
    },

    _scheduleReconnect() {
      if (this._reconnectTimer) return;
      this._reconnectTimer = setTimeout(() => {
        this._reconnectTimer = null;
        this._reconnectDelay = Math.min(this._reconnectDelay * 2, 30000);
        this._connect();
      }, this._reconnectDelay);
    },

    // -- Send message --

    sendMessage(text) {
      if (!text || !text.trim() || !this._ws || !this.sgConnected) return;

      const message = text.trim();

      // Optimistic UI: add patient message immediately
      this.sgMessages.push({
        type: 'user',
        content: message,
        timestamp: new Date().toISOString(),
      });
      this.$nextTick(() => this._scrollToBottom());

      // Send via WebSocket
      this._ws.send(JSON.stringify({ message }));
    },

    sendVoiceMessage(text, audioUrl) {
      if (!text || !text.trim() || !this._ws || !this.sgConnected) return;

      this.sgMessages.push({
        type: 'user',
        content: text.trim(),
        channel: 'voice',
        audio_url: audioUrl,
        timestamp: new Date().toISOString(),
      });
      this.$nextTick(() => this._scrollToBottom());

      this._ws.send(JSON.stringify({
        message: text.trim(),
        channel: 'voice',
        audio_url: audioUrl,
      }));
    },

    // -- Handle incoming messages --

    _handleMessage(data) {
      switch (data.type) {
        case 'support_group_message':
          this._addPersonaMessage(data);
          break;
        case 'support_group_reaction':
          this._addReaction(data);
          break;
        case 'support_group_typing':
          this._showTyping(data);
          break;
        case 'crisis_detected':
          this._showEscalation(data);
          break;
        case 'error':
          console.warn('Support group error:', data.message);
          break;
      }
    },

    _addPersonaMessage(data) {
      this.sgTyping = null;
      this.sgMessages.push({
        type: 'persona',
        message_id: data.message_id,
        persona_id: data.persona_id,
        persona_name: data.persona_name,
        content: data.content,
        avatar_color: data.avatar_color,
        avatar_color_dark: data.avatar_color_dark,
        avatar_initials: data.avatar_initials,
        reactions: [],
        timestamp: new Date().toISOString(),
      });

      if (this.activeTab !== 'support_group') {
        this.supportGroupUnread++;
      }
      this.$nextTick(() => this._scrollToBottom());
    },

    _addReaction(data) {
      const msg = this.sgMessages.find(m => m.message_id === data.message_id);
      if (msg && msg.reactions) {
        msg.reactions.push({
          persona_id: data.persona_id,
          emoji: data.emoji,
        });
      }
    },

    _showTyping(data) {
      if (data.persona_id) {
        this.sgTyping = {
          persona_id: data.persona_id,
          persona_name: data.persona_name,
        };
      } else {
        // Generic typing (before router picks persona)
        this.sgTyping = { persona_id: '', persona_name: '' };
      }
      // Auto-clear typing after 15s
      setTimeout(() => {
        if (this.sgTyping && this.sgTyping.persona_id === data.persona_id) {
          this.sgTyping = null;
        }
      }, 15000);
    },

    _showEscalation(data) {
      this.sgMessages.push({
        type: 'escalation',
        content: data.message,
        timestamp: new Date().toISOString(),
      });
      this.$nextTick(() => this._scrollToBottom());
    },

    // -- Onboarding --

    startChatting() {
      this.sgOnboarded = true;
      localStorage.setItem('sg_onboarded', 'true');
      // Server-side conversation created on first message send
    },

    // -- Profile card --

    showProfileCard: false,
    profileCardPersona: null,

    openProfileCard(personaId) {
      // Persona data passed as data attributes or from registry
      const personas = window.__sgPersonas || {};
      this.profileCardPersona = personas[personaId] || null;
      if (this.profileCardPersona) {
        this.showProfileCard = true;
      }
    },

    closeProfileCard() {
      this.showProfileCard = false;
      this.profileCardPersona = null;
    },

    // -- Helpers --

    _scrollToBottom() {
      const container = document.getElementById('sg-messages');
      if (container) {
        container.scrollTop = container.scrollHeight;
      }
    },

    // Emoji display mapping
    emojiMap: {
      'thumbs_up': '\uD83D\uDC4D',
      'heart': '\u2764\uFE0F',
      'hug': '\uD83E\uDD17',
      'celebrate': '\uD83C\uDF89',
      'muscle': '\uD83D\uDCAA',
    },

    getEmoji(name) {
      return this.emojiMap[name] || name;
    },
  };
}
