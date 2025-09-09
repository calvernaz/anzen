// Anzen Chat Application
const { createApp } = Vue;

createApp({
    data() {
        return {
            messages: [],
            inputMessage: '',
            isLoading: false,
            selectedRoute: 'public:chat',
            messageIdCounter: 0
        }
    },
    methods: {
        async sendMessage() {
            if (!this.inputMessage.trim() || this.isLoading) return;

            const userMessage = this.inputMessage.trim();
            this.addMessage('user', userMessage);
            this.inputMessage = '';
            this.isLoading = true;

            try {
                // Step 1: Check input with gateway
                console.log('🛡️ Checking input with gateway...');
                const inputSafetyResponse = await this.checkInputSafety(userMessage);
                
                if (inputSafetyResponse.decision === 'BLOCK') {
                    this.addMessage('system', '🚫 Message blocked due to sensitive content');
                    return;
                }

                const safeText = inputSafetyResponse.safe_text || userMessage;
                
                if (inputSafetyResponse.decision === 'REDACT') {
                    this.addMessage('system', '⚠️ Sensitive information detected and redacted');
                }

                // Step 2: Send to agent
                console.log('🤖 Sending to agent...');
                const agentResponse = await this.callAgent(safeText);
                
                // Step 3: Check output safety
                console.log('🛡️ Checking output safety...');
                const outputSafetyResponse = await this.checkOutputSafety(agentResponse.response);
                
                // Add assistant message with safety info
                this.addMessage('assistant', outputSafetyResponse.safe_text || agentResponse.response, {
                    decision: outputSafetyResponse.decision,
                    entities: outputSafetyResponse.entities || [],
                    trace_id: agentResponse.trace_id,
                    plan: agentResponse.plan
                });

            } catch (error) {
                console.error('❌ Error:', error);
                this.addMessage('system', '❌ Sorry, something went wrong. Please try again.');
            } finally {
                this.isLoading = false;
                this.$nextTick(() => {
                    this.scrollToBottom();
                });
            }
        },

        async checkInputSafety(text) {
            const response = await fetch('http://localhost:8000/v1/anzen/check/input', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    text: text,
                    route: this.selectedRoute,
                    language: 'en'
                })
            });

            if (!response.ok) {
                throw new Error(`Gateway input check failed: ${response.status}`);
            }

            return await response.json();
        },

        async callAgent(text) {
            const controller = new AbortController();
            const timeoutId = setTimeout(() => controller.abort(), 30000);

            try {
                const response = await fetch('http://localhost:8001/v1/agents/secure', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify({
                        prompt: text,
                        user_id: 'demo-user'
                    }),
                    signal: controller.signal
                });

                clearTimeout(timeoutId);

                if (!response.ok) {
                    throw new Error(`Agent call failed: ${response.status}`);
                }

                return await response.json();
            } catch (error) {
                clearTimeout(timeoutId);
                throw error;
            }
        },

        async checkOutputSafety(text) {
            const response = await fetch('http://localhost:8000/v1/anzen/check/output', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    text: text,
                    route: this.selectedRoute,
                    language: 'en'
                })
            });

            if (!response.ok) {
                throw new Error(`Gateway output check failed: ${response.status}`);
            }

            return await response.json();
        },

        addMessage(type, content, safetyInfo = null) {
            this.messages.push({
                id: ++this.messageIdCounter,
                type,
                content,
                safetyInfo,
                timestamp: new Date()
            });
        },

        handleEnter(event) {
            if (!event.shiftKey) {
                this.sendMessage();
            }
        },

        scrollToBottom() {
            const container = this.$refs.messagesContainer;
            if (container) {
                container.scrollTop = container.scrollHeight;
            }
        },

        getSafetyBadgeClass(decision) {
            const classes = {
                'ALLOW': 'bg-green-100 text-green-800',
                'REDACT': 'bg-yellow-100 text-yellow-800',
                'BLOCK': 'bg-red-100 text-red-800'
            };
            return classes[decision] || 'bg-gray-100 text-gray-800';
        },

        getEntityClass(entityType) {
            const sensitiveTypes = ['CREDIT_CARD', 'US_SSN', 'US_PASSPORT', 'IBAN_CODE'];
            if (sensitiveTypes.includes(entityType)) {
                return 'entity-redacted';
            }
            return 'entity-highlight';
        },

        loadExample(type) {
            const examples = {
                weather: "What's the weather like in Paris? My email is john.doe@company.com if you need to contact me.",
                email: "Can you help me draft an email? My contact is jane.smith@example.org and my phone is 555-123-4567.",
                sensitive: "I need help with my account. My SSN is 123-45-6789 and my credit card number is 4532-1234-5678-9012."
            };

            this.inputMessage = examples[type] || examples.weather;
        },

        clearChat() {
            this.messages = [];
            this.inputMessage = '';
        }
    },

    mounted() {
        console.log('🚀 Anzen Chat initialized');
        
        // Auto-resize textarea
        this.$nextTick(() => {
            const textarea = document.querySelector('textarea');
            if (textarea) {
                textarea.addEventListener('input', function() {
                    this.style.height = 'auto';
                    this.style.height = Math.min(this.scrollHeight, 120) + 'px';
                });
            }
        });
    }
}).mount('#app');
