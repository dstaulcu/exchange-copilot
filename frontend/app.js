/**
 * Exchange Assistant - Frontend Application
 */

class ExchangeAssistant {
    constructor() {
        this.apiBase = window.location.origin;
        this.ws = null;
        this.isConnected = false;
        this.sessionId = this.generateSessionId();
        this.lastInteractionId = null;
        
        this.init();
    }
    
    generateSessionId() {
        return 'sess_' + Math.random().toString(36).substring(2, 10);
    }
    
    async init() {
        // Get DOM elements
        this.elements = {
            messagesContainer: document.getElementById('messages'),
            messageInput: document.getElementById('message-input'),
            sendButton: document.getElementById('send-button'),
            syncButton: document.getElementById('sync-button'),
            userName: document.getElementById('user-name'),
            userEmail: document.getElementById('user-email'),
            userAvatar: document.getElementById('user-avatar'),
            unreadCount: document.getElementById('unread-count'),
            meetingsToday: document.getElementById('meetings-today'),
            syncText: document.getElementById('sync-text'),
            modelName: document.getElementById('model-name')
        };
        
        // Setup event listeners
        this.setupEventListeners();
        
        // Load initial status
        await this.loadStatus();
        
        // Connect WebSocket
        this.connectWebSocket();
        
        // Auto-resize textarea
        this.setupTextareaResize();
    }
    
    setupEventListeners() {
        // Send button
        this.elements.sendButton.addEventListener('click', () => this.sendMessage());
        
        // Enter to send (Shift+Enter for new line)
        this.elements.messageInput.addEventListener('keydown', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
        
        // Enable/disable send button based on input
        this.elements.messageInput.addEventListener('input', () => {
            this.elements.sendButton.disabled = !this.elements.messageInput.value.trim();
        });
        
        // Sync button
        this.elements.syncButton.addEventListener('click', () => this.triggerSync());
        
        // Quick actions
        document.querySelectorAll('.quick-action').forEach(btn => {
            btn.addEventListener('click', () => {
                const query = btn.dataset.query;
                if (query) {
                    this.elements.messageInput.value = query;
                    this.sendMessage();
                }
            });
        });
        
        // Status cards - click to query
        document.getElementById('email-status').addEventListener('click', () => {
            this.elements.messageInput.value = "Show me my unread emails";
            this.sendMessage();
        });
        
        document.getElementById('meeting-status').addEventListener('click', () => {
            this.elements.messageInput.value = "What meetings do I have today?";
            this.sendMessage();
        });
    }
    
    setupTextareaResize() {
        const textarea = this.elements.messageInput;
        textarea.addEventListener('input', () => {
            textarea.style.height = 'auto';
            textarea.style.height = Math.min(textarea.scrollHeight, 150) + 'px';
        });
    }
    
    async loadStatus() {
        try {
            const response = await fetch(`${this.apiBase}/api/status`);
            const data = await response.json();
            
            // Update user info
            if (data.user) {
                this.elements.userName.textContent = data.user.name || 'Unknown';
                this.elements.userEmail.textContent = data.user.email || '';
                this.elements.userAvatar.textContent = (data.user.name || '?').charAt(0).toUpperCase();
            }
            
            // Update stats
            if (data.stats) {
                this.elements.unreadCount.textContent = data.stats.unread_emails || 0;
                this.elements.meetingsToday.textContent = data.stats.meetings_today || 0;
            }
            
            // Update sync status
            if (data.sync) {
                const lastSync = data.sync.last_sync 
                    ? new Date(data.sync.last_sync).toLocaleTimeString()
                    : 'Never';
                this.elements.syncText.textContent = `Last sync: ${lastSync}`;
            }
            
            // Update model name
            if (data.model) {
                this.elements.modelName.textContent = data.model;
            }
            
        } catch (error) {
            console.error('Failed to load status:', error);
        }
    }
    
    connectWebSocket() {
        const wsProtocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
        const wsUrl = `${wsProtocol}//${window.location.host}/ws/chat`;
        
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onopen = () => {
            console.log('WebSocket connected');
            this.isConnected = true;
        };
        
        this.ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            this.handleWebSocketMessage(data);
        };
        
        this.ws.onclose = () => {
            console.log('WebSocket disconnected');
            this.isConnected = false;
            // Attempt to reconnect after 3 seconds
            setTimeout(() => this.connectWebSocket(), 3000);
        };
        
        this.ws.onerror = (error) => {
            console.error('WebSocket error:', error);
        };
    }
    
    handleWebSocketMessage(data) {
        switch (data.type) {
            case 'status':
                if (data.content === 'thinking') {
                    this.showThinking();
                }
                break;
                
            case 'response':
                this.hideThinking();
                this.lastInteractionId = data.interaction_id || null;
                this.addMessage('assistant', data.content, data.tools_used, this.lastInteractionId);
                this.loadStatus(); // Refresh status after response
                break;
                
            case 'error':
                this.hideThinking();
                this.addMessage('assistant', `Error: ${data.content}`);
                break;
                
            case 'pong':
                // Keepalive response
                break;
        }
    }
    
    async sendMessage() {
        const message = this.elements.messageInput.value.trim();
        if (!message) return;
        
        // Clear input
        this.elements.messageInput.value = '';
        this.elements.messageInput.style.height = 'auto';
        this.elements.sendButton.disabled = true;
        
        // Clear welcome message if present
        const welcome = this.elements.messagesContainer.querySelector('.welcome-message');
        if (welcome) {
            welcome.remove();
        }
        
        // Add user message
        this.addMessage('user', message);
        
        // Send via WebSocket if connected, otherwise use REST API
        if (this.isConnected && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify({ 
                type: 'chat', 
                content: message,
                session_id: this.sessionId
            }));
        } else {
            await this.sendMessageREST(message);
        }
    }
    
    async sendMessageREST(message) {
        this.showThinking();
        
        try {
            const response = await fetch(`${this.apiBase}/api/chat`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message, session_id: this.sessionId })
            });
            
            const data = await response.json();
            this.hideThinking();
            
            if (response.ok) {
                this.lastInteractionId = data.interaction_id || null;
                this.addMessage('assistant', data.response, data.tools_used, this.lastInteractionId);
            } else {
                this.addMessage('assistant', `Error: ${data.detail || 'Unknown error'}`);
            }
            
            this.loadStatus();
            
        } catch (error) {
            this.hideThinking();
            this.addMessage('assistant', `Connection error: ${error.message}`);
        }
    }
    
    addMessage(role, content, toolsUsed = [], interactionId = null) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}`;
        if (interactionId) {
            messageDiv.dataset.interactionId = interactionId;
        }
        
        const avatar = document.createElement('div');
        avatar.className = 'message-avatar';
        avatar.innerHTML = role === 'assistant' 
            ? '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>'
            : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>';
        
        const contentDiv = document.createElement('div');
        contentDiv.className = 'message-content';
        contentDiv.innerHTML = this.formatMessage(content);
        
        // Add tools used indicator
        if (toolsUsed && toolsUsed.length > 0) {
            const toolsDiv = document.createElement('div');
            toolsDiv.className = 'message-tools';
            toolsDiv.innerHTML = 'Tools used: ' + toolsUsed.map(t => `<span class="tool-tag">${t}</span>`).join('');
            contentDiv.appendChild(toolsDiv);
        }
        
        // Add feedback buttons for assistant messages
        if (role === 'assistant' && interactionId) {
            const feedbackDiv = document.createElement('div');
            feedbackDiv.className = 'message-feedback';
            feedbackDiv.innerHTML = `
                <span class="feedback-label">Was this helpful?</span>
                <button class="feedback-btn thumbs-up" data-rating="1" title="Thumbs up">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path>
                    </svg>
                </button>
                <button class="feedback-btn thumbs-down" data-rating="-1" title="Thumbs down">
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"></path>
                    </svg>
                </button>
            `;
            
            // Add click handlers
            feedbackDiv.querySelectorAll('.feedback-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    e.preventDefault();
                    const rating = parseInt(btn.dataset.rating);
                    this.showFeedbackForm(interactionId, rating, feedbackDiv);
                });
            });
            
            contentDiv.appendChild(feedbackDiv);
        }
        
        messageDiv.appendChild(avatar);
        messageDiv.appendChild(contentDiv);
        
        this.elements.messagesContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }
    
    showFeedbackForm(interactionId, rating, feedbackDiv) {
        // Show expandable feedback form after initial thumbs click
        const ratingEmoji = rating === 1 ? '👍' : '👎';
        feedbackDiv.innerHTML = `
            <div class="feedback-expanded">
                <span class="feedback-initial">${ratingEmoji}</span>
                <a href="#" class="feedback-expand-link">Tell us more (optional)</a>
                <div class="feedback-details" style="display: none;">
                    <div class="feedback-categories">
                        <label class="category-checkbox">
                            <input type="checkbox" value="speed"> Speed
                        </label>
                        <label class="category-checkbox">
                            <input type="checkbox" value="quality"> Quality
                        </label>
                        <label class="category-checkbox">
                            <input type="checkbox" value="accuracy"> Accuracy
                        </label>
                    </div>
                    <textarea class="feedback-comment" placeholder="Any additional comments..." rows="2"></textarea>
                    <div class="feedback-actions">
                        <button class="feedback-submit-btn">Submit</button>
                        <button class="feedback-skip-btn">Skip</button>
                    </div>
                </div>
            </div>
        `;
        feedbackDiv.classList.add('feedback-has-form');

        const expandLink = feedbackDiv.querySelector('.feedback-expand-link');
        const detailsDiv = feedbackDiv.querySelector('.feedback-details');
        const submitBtn = feedbackDiv.querySelector('.feedback-submit-btn');
        const skipBtn = feedbackDiv.querySelector('.feedback-skip-btn');

        // Expand/collapse toggle
        expandLink.addEventListener('click', (e) => {
            e.preventDefault();
            const isHidden = detailsDiv.style.display === 'none';
            detailsDiv.style.display = isHidden ? 'block' : 'none';
            expandLink.textContent = isHidden ? 'Hide details' : 'Tell us more (optional)';
        });

        // Skip - submit without details
        skipBtn.addEventListener('click', () => {
            this.submitFeedback(interactionId, rating, null, null, feedbackDiv);
        });

        // Submit with details
        submitBtn.addEventListener('click', () => {
            const categories = Array.from(feedbackDiv.querySelectorAll('.category-checkbox input:checked'))
                .map(cb => cb.value);
            const comment = feedbackDiv.querySelector('.feedback-comment').value.trim();
            this.submitFeedback(interactionId, rating, categories, comment || null, feedbackDiv);
        });

        // Auto-submit after 5 seconds if user doesn't interact
        setTimeout(() => {
            if (!feedbackDiv.classList.contains('feedback-submitted')) {
                this.submitFeedback(interactionId, rating, null, null, feedbackDiv);
            }
        }, 5000);
    }

    async submitFeedback(interactionId, rating, categories = null, comment = null, feedbackDiv) {
        if (feedbackDiv && feedbackDiv.classList.contains('feedback-submitted')) {
            return; // Already submitted
        }

        try {
            const body = { interaction_id: interactionId, rating };
            if (categories && categories.length > 0) {
                body.categories = categories;
            }
            if (comment) {
                body.comment = comment;
            }

            const response = await fetch(`${this.apiBase}/api/feedback`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(body)
            });
            
            if (response.ok && feedbackDiv) {
                // Show confirmation
                const categoryText = categories && categories.length > 0 
                    ? ` (${categories.join(', ')})` 
                    : '';
                feedbackDiv.innerHTML = `
                    <span class="feedback-thanks">
                        ${rating === 1 ? '👍' : '👎'} Thanks for your feedback!${categoryText}
                    </span>
                `;
                feedbackDiv.classList.add('feedback-submitted');
            } else if (!response.ok) {
                console.error('Failed to submit feedback');
            }
        } catch (error) {
            console.error('Feedback error:', error);
        }
    }
    
    formatMessage(content) {
        // Simple markdown-like formatting
        let formatted = content
            // Escape HTML
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            // Bold
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
            // Italic
            .replace(/\*(.*?)\*/g, '<em>$1</em>')
            // Code
            .replace(/`(.*?)`/g, '<code>$1</code>')
            // Line breaks
            .replace(/\n/g, '<br>');
        
        // Convert numbered lists
        formatted = formatted.replace(/^(\d+)\.\s+(.*)$/gm, '<li>$2</li>');
        formatted = formatted.replace(/(<li>.*<\/li>)+/g, '<ol>$&</ol>');
        
        // Convert bullet lists
        formatted = formatted.replace(/^[-*]\s+(.*)$/gm, '<li>$1</li>');
        
        return formatted;
    }
    
    showThinking() {
        // Remove any existing thinking indicator
        this.hideThinking();
        
        const thinkingDiv = document.createElement('div');
        thinkingDiv.className = 'message assistant';
        thinkingDiv.id = 'thinking-indicator';
        thinkingDiv.innerHTML = `
            <div class="message-avatar">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                    <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path>
                </svg>
            </div>
            <div class="message-content">
                <div class="thinking">
                    <div class="thinking-dot"></div>
                    <div class="thinking-dot"></div>
                    <div class="thinking-dot"></div>
                </div>
            </div>
        `;
        
        this.elements.messagesContainer.appendChild(thinkingDiv);
        this.scrollToBottom();
    }
    
    hideThinking() {
        const thinking = document.getElementById('thinking-indicator');
        if (thinking) {
            thinking.remove();
        }
    }
    
    scrollToBottom() {
        this.elements.messagesContainer.scrollTop = this.elements.messagesContainer.scrollHeight;
    }
    
    async triggerSync() {
        const btn = this.elements.syncButton;
        btn.classList.add('syncing');
        btn.disabled = true;
        
        try {
            const response = await fetch(`${this.apiBase}/api/sync`, { method: 'POST' });
            const data = await response.json();
            
            if (data.error) {
                console.error('Sync error:', data.error);
            } else {
                console.log('Sync complete:', data);
                await this.loadStatus();
            }
            
        } catch (error) {
            console.error('Sync failed:', error);
        } finally {
            btn.classList.remove('syncing');
            btn.disabled = false;
        }
    }
}

// Initialize the app when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    window.app = new ExchangeAssistant();
});
