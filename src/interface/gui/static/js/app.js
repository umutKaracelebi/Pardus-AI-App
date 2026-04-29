/* ═══════════════════════════════════════════════════════
   Pardus AI Assistant – Frontend Logic
   ═══════════════════════════════════════════════════════ */

document.addEventListener('DOMContentLoaded', () => {
    // ─── DOM Elements ───
    const chatArea       = document.getElementById('chat-area');
    const messagesEl     = document.getElementById('messages');
    const welcomeScreen  = document.getElementById('welcome-screen');
    const input          = document.getElementById('message-input');
    const sendBtn        = document.getElementById('send-btn');
    const screenshotBtn  = document.getElementById('screenshot-btn');
    const attachBtn      = document.getElementById('attach-btn');
    const attachMenuBtn  = document.getElementById('attach-menu-btn');
    const attachPopover  = document.getElementById('attachment-popover');
    const newChatBtn     = document.getElementById('new-chat-btn');
    const sidebarToggle  = document.getElementById('sidebar-toggle');
    const quickBtns      = document.querySelectorAll('.quick-btn');
    const chatHistory    = document.getElementById('chat-history');
    
    // Image Modal Elements
    const imgModalOverlay = document.getElementById('image-modal-overlay');
    const imgPromptInput  = document.getElementById('image-prompt-input');
    const imgModalCancel  = document.getElementById('image-modal-cancel');
    const imgModalConfirm = document.getElementById('image-modal-confirm');

    let isWaiting = false;
    let currentChatId = null;
    let chats = {};
    let pendingImageFile = null; // Holds the attached image file
    let pendingVideoFile = null; // Holds the attached video file
    let pendingAudioFile = null; // Holds the attached audio file

    // Preview strip elements
    const previewStrip = document.getElementById('image-preview-strip');
    const previewThumb = document.getElementById('preview-thumb');
    const previewRemoveBtn = document.getElementById('preview-remove-btn');

    // Safe localStorage wrappers for PyWebView/WebKit
    const safeGetItem = function(key) {
        try {
            if (typeof window !== 'undefined' && window.localStorage !== null) {
                return window.localStorage.getItem(key);
            }
        } catch(e) {}
        return null;
    };

    const safeSetItem = function(key, value) {
        try {
            if (typeof window !== 'undefined' && window.localStorage !== null) {
                window.localStorage.setItem(key, value);
            }
        } catch(e) {}
    };

    let aiModel = 'cloud';

    // ─── Settings Panel ───
    const settingsOverlay = document.getElementById('settings-overlay');
    const settingsBtn     = document.getElementById('settings-btn');
    const settingsClose   = document.getElementById('settings-close');
    const modelRadios     = document.querySelectorAll('input[name="ai-model"]');

    // Restore saved model selection
    modelRadios.forEach(function(r) { if (r.value === aiModel) r.checked = true; });

    if (settingsBtn && settingsOverlay) {
        settingsBtn.addEventListener('click', function() { settingsOverlay.classList.remove('hidden'); });
    }
    if (settingsClose && settingsOverlay) {
        settingsClose.addEventListener('click', function() { settingsOverlay.classList.add('hidden'); });
    }
    if (settingsOverlay) {
        settingsOverlay.addEventListener('click', function(e) {
            if (e.target === settingsOverlay) settingsOverlay.classList.add('hidden');
        });
    }

    modelRadios.forEach(function(r) {
        r.addEventListener('change', function() {
            aiModel = r.value;
            safeSetItem('pardus_ai_model', aiModel);
        });
    });

    // ─── Load Chat History from Backend ───
    const loadChats = async () => {
        try {
            const res = await fetch('/api/chats');
            const data = await res.json();
            if (data.success && data.chats) {
                chats = data.chats;
            } else {
                chats = {};
            }
        } catch(e) {
            console.error('[Pardus AI] Failed to load chats:', e);
            chats = {};
        }
    };

    const saveChats = async () => {
        try {
            // Only persist chats that have messages
            const nonEmptyChats = {};
            for (const id of Object.keys(chats)) {
                if (chats[id].messages && chats[id].messages.length > 0) {
                    nonEmptyChats[id] = chats[id];
                }
            }
            await fetch('/api/chats', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ chats: nonEmptyChats })
            });
        } catch(e) {
            console.error('[Pardus AI] Failed to save chats:', e);
        }
    };

    const renderChatHistory = () => {
        // Remove old items (keep the label)
        const items = chatHistory.querySelectorAll('.history-item');
        items.forEach(i => i.remove());

        const ids = Object.keys(chats)
            .filter(id => chats[id].messages && chats[id].messages.length > 0)
            .sort((a, b) => parseInt(b) - parseInt(a));
        ids.forEach(id => {
            const item = document.createElement('div');
            item.className = 'history-item' + (id === currentChatId ? ' active' : '');
            item.textContent = chats[id].title || 'Yeni Sohbet';
            item.addEventListener('click', () => loadChat(id));
            chatHistory.appendChild(item);
        });
    };

    const createNewChat = () => {
        currentChatId = Date.now().toString();
        chats[currentChatId] = { title: '', messages: [] };
        messagesEl.innerHTML = '';
        messagesEl.style.display = 'none';
        welcomeScreen.classList.remove('hidden');
        input.value = '';
        sendBtn.disabled = true;
        renderChatHistory();
        input.focus();
    };

    const loadChat = (id) => {
        if (!chats[id]) return;
        currentChatId = id;
        messagesEl.innerHTML = '';

        if (chats[id].messages.length > 0) {
            welcomeScreen.classList.add('hidden');
            messagesEl.style.display = 'flex';
            chats[id].messages.forEach(m => {
                // Detect generated image/video messages and render with proper preview
                const imgMatch = m.text.match(/^🎨 \[Üretilen Görsel\]\((.+)\)$/);
                const vidMatch = m.text.match(/^🎬 \[Üretilen Video\]\((.+)\)$/);
                if (m.sender === 'assistant' && imgMatch) {
                    addGeneratedImageMessage(imgMatch[1], '', false);
                } else if (m.sender === 'assistant' && vidMatch) {
                    addGeneratedVideoMessage(vidMatch[1], '', false);
                } else {
                    addMessage(m.text, m.sender, false, m.imageDataUrl || null);
                }
            });
            setTimeout(scrollToBottom, 50);
        } else {
            messagesEl.style.display = 'none';
            welcomeScreen.classList.remove('hidden');
        }
        renderChatHistory();
        input.focus();
    };

    const saveMessage = (text, sender, imageDataUrl = null) => {
        if (!currentChatId) createNewChat();
        const msg = { text, sender };
        if (imageDataUrl) msg.imageDataUrl = imageDataUrl;
        chats[currentChatId].messages.push(msg);
        saveChats();
    };

    const generateChatTitle = async (userMsg, assistantMsg) => {
        try {
            const res = await fetch('/api/generate-title', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ user_message: userMsg, assistant_message: assistantMsg })
            });
            const data = await res.json();
            if (data.success && data.title && currentChatId && chats[currentChatId]) {
                chats[currentChatId].title = data.title;
                saveChats();
                renderChatHistory();
            }
        } catch(e) {
            // Fallback: use first words of user message
            if (currentChatId && chats[currentChatId] && !chats[currentChatId].title) {
                chats[currentChatId].title = userMsg.substring(0, 35) + (userMsg.length > 35 ? '...' : '');
                saveChats();
                renderChatHistory();
            }
        }
    };

    // ─── Sidebar Toggle ───
    sidebarToggle.addEventListener('click', () => {
        sidebar.classList.toggle('collapsed');
    });

    // ─── Auto-resize textarea ───
    input.addEventListener('input', () => {
        input.style.height = 'auto';
        input.style.height = Math.min(input.scrollHeight, 150) + 'px';
        sendBtn.disabled = input.value.trim() === '' && !pendingImageFile;
    });

    // ─── Send Message ───
    const sendMessage = async (text) => {
        // Intercept for generation mode (image/video)
        if (typeof currentGenMode !== 'undefined' && currentGenMode !== 'chat') {
            const handled = await handleGenSend();
            if (handled) return;
        }

        text = text || input.value.trim();
        if ((!text && !pendingImageFile && !pendingFile) || isWaiting) return;

        // Hide welcome, show messages
        welcomeScreen.classList.add('hidden');
        messagesEl.style.display = 'flex';

        // Check if there's an attached image
        if (pendingImageFile) {
            const file = pendingImageFile;
            const prompt = text || 'Bu görseli açıkla.';
            const imgDataUrl = previewThumb.src; // grab data URL before clearing
            clearImagePreview();
            input.value = '';
            input.style.height = 'auto';
            sendBtn.disabled = true;

            addMessage(prompt, 'user', true, imgDataUrl);
            const typingEl = showTyping();
            isWaiting = true;

            try {
                const formData = new FormData();
                formData.append('image', file);
                formData.append('prompt', prompt);
                const res = await fetch('/api/analyze-image', { method: 'POST', body: formData });
                const data = await res.json();
                removeTyping(typingEl);

                if (data.success) {
                    addMessage(data.response, 'assistant');
                    if (currentChatId && chats[currentChatId] && !chats[currentChatId].title) {
                        chats[currentChatId].title = '📷 ' + prompt.substring(0, 30) + (prompt.length > 30 ? '...' : '');
                        saveChats();
                        renderChatHistory();
                    }
                } else {
                    addMessage('⚠️ ' + data.error, 'assistant');
                }
            } catch (err) {
                removeTyping(typingEl);
                addMessage('⚠️ Bağlantı hatası: ' + err.message, 'assistant');
            }
            isWaiting = false;
            input.focus();
            return;
        }

        // Check if there's an attached video
        if (pendingVideoFile) {
            const file = pendingVideoFile;
            const prompt = text || 'Bu videoyu analiz et ve açıkla.';
            clearVideoPreview();
            input.value = '';
            input.style.height = 'auto';
            sendBtn.disabled = true;

            addMessage('🎬 ' + file.name + ': ' + prompt, 'user');
            const typingEl = showTyping();
            isWaiting = true;

            try {
                const formData = new FormData();
                formData.append('video', file);
                formData.append('prompt', prompt);
                const res = await fetch('/api/analyze-video', { method: 'POST', body: formData });
                const data = await res.json();
                removeTyping(typingEl);

                if (data.success) {
                    addMessage(data.response, 'assistant');
                    if (currentChatId && chats[currentChatId] && !chats[currentChatId].title) {
                        chats[currentChatId].title = '🎬 ' + file.name;
                        saveChats();
                        renderChatHistory();
                    }
                } else {
                    addMessage('⚠️ ' + data.error, 'assistant');
                }
            } catch (err) {
                removeTyping(typingEl);
                addMessage('⚠️ Bağlantı hatası: ' + err.message, 'assistant');
            }
            isWaiting = false;
            input.focus();
            return;
        }

        // Check if there's an attached audio file
        if (pendingAudioFile) {
            const file = pendingAudioFile;
            const prompt = text || 'Bu ses dosyasını analiz et ve açıkla.';
            clearAudioPreview();
            input.value = '';
            input.style.height = 'auto';
            sendBtn.disabled = true;

            addMessage('🎵 ' + file.name + ': ' + prompt, 'user');
            const typingEl = showTyping();
            isWaiting = true;

            try {
                const formData = new FormData();
                formData.append('audio', file);
                formData.append('prompt', prompt);
                const res = await fetch('/api/analyze-audio', { method: 'POST', body: formData });
                const data = await res.json();
                removeTyping(typingEl);

                if (data.success) {
                    addMessage(data.response, 'assistant');
                    if (currentChatId && chats[currentChatId] && !chats[currentChatId].title) {
                        chats[currentChatId].title = '🎵 ' + file.name;
                        saveChats();
                        renderChatHistory();
                    }
                } else {
                    addMessage('⚠️ ' + data.error, 'assistant');
                }
            } catch (err) {
                removeTyping(typingEl);
                addMessage('⚠️ Bağlantı hatası: ' + err.message, 'assistant');
            }
            isWaiting = false;
            input.focus();
            return;
        }

        // Check if there's an attached document file
        if (pendingFile) {
            const file = pendingFile;
            const prompt = text || 'Bu dosyayı özetle.';
            clearImagePreview();
            input.value = '';
            input.style.height = 'auto';
            sendBtn.disabled = true;

            addMessage(`📄 ${file.name}: ${prompt}`, 'user');
            const typingEl = showTyping();
            isWaiting = true;

            try {
                const formData = new FormData();
                formData.append('file', file);
                formData.append('prompt', prompt);
                const res = await fetch('/api/analyze-file', { method: 'POST', body: formData });
                const data = await res.json();
                removeTyping(typingEl);

                if (data.success) {
                    addMessage(data.response, 'assistant');
                    if (currentChatId && chats[currentChatId] && !chats[currentChatId].title) {
                        chats[currentChatId].title = '📄 ' + file.name;
                        saveChats();
                        renderChatHistory();
                    }
                } else {
                    addMessage('⚠️ ' + data.error, 'assistant');
                }
            } catch (err) {
                removeTyping(typingEl);
                addMessage('⚠️ Bağlantı hatası: ' + err.message, 'assistant');
            }
            isWaiting = false;
            input.focus();
            return;
        }

        // Normal text message
        addMessage(text, 'user');
        input.value = '';
        input.style.height = 'auto';
        sendBtn.disabled = true;

        // Show typing
        const typingEl = showTyping();

        isWaiting = true;
        const needsTitle = currentChatId && chats[currentChatId] && !chats[currentChatId].title;
        try {
            const res = await fetch('/api/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message: text, needs_title: needsTitle, model: aiModel })
            });
            const data = await res.json();
            removeTyping(typingEl);

            if (data.success) {
                addMessage(data.response, 'assistant');
                if (data.title && currentChatId && chats[currentChatId]) {
                    chats[currentChatId].title = data.title;
                    saveChats();
                    renderChatHistory();
                }
            } else {
                addMessage('⚠️ Hata: ' + data.error, 'assistant');
            }
        } catch (err) {
            removeTyping(typingEl);
            addMessage('⚠️ Bağlantı hatası: ' + err.message, 'assistant');
        }
        isWaiting = false;
        input.focus();
    };

    // ─── Send Events ───
    sendBtn.addEventListener('click', () => sendMessage());
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });

    // ─── Document Click (Close Popover) ───
    document.addEventListener('click', (e) => {
        if (attachMenuBtn && attachPopover) {
            if (!attachMenuBtn.contains(e.target) && !attachPopover.contains(e.target)) {
                attachPopover.classList.add('hidden');
                attachMenuBtn.classList.remove('active');
            }
        }
        
        const quickBtn = e.target.closest('.quick-btn');
        if (quickBtn) {
            e.preventDefault();
            e.stopPropagation();
            const prompt = quickBtn.getAttribute('data-prompt');
            console.log('[Pardus AI] Quick button clicked:', prompt);
            if (prompt && !isWaiting) {
                sendMessage(prompt);
            }
        }
    });

    // ─── Attachment Menu ───
    if (attachMenuBtn && attachPopover) {
        attachMenuBtn.addEventListener('click', (e) => {
            e.preventDefault();
            e.stopPropagation();
            attachPopover.classList.toggle('hidden');
            attachMenuBtn.classList.toggle('active');
        });
    }

    // ─── New Chat ───
    newChatBtn.addEventListener('click', () => createNewChat());

    // ─── Screenshot ───
    if (screenshotBtn) {
        screenshotBtn.addEventListener('click', async () => {
        if (isWaiting) return;
        
        if (attachPopover) attachPopover.classList.add('hidden');
        if (attachMenuBtn) attachMenuBtn.classList.remove('active');

        welcomeScreen.classList.add('hidden');
        messagesEl.style.display = 'flex';
        addMessage('📸 Ekran görüntüsü alınıyor ve analiz ediliyor...', 'user');

        const typingEl = showTyping();
        isWaiting = true;

        try {
            const res = await fetch('/api/screenshot', { method: 'POST' });
            const data = await res.json();
            removeTyping(typingEl);

            if (data.success) {
                addMessage(data.response, 'assistant');
            } else {
                addMessage('⚠️ ' + data.error, 'assistant');
            }
        } catch (err) {
            removeTyping(typingEl);
            addMessage('⚠️ Bağlantı hatası: ' + err.message, 'assistant');
        }
        isWaiting = false;
    });
    } // end screenshotBtn

    // ─── Image Upload (Inline Preview) ───
    if (attachBtn) {
        attachBtn.addEventListener('click', () => {
            if (isWaiting) return;

            if (attachPopover) attachPopover.classList.add('hidden');
            if (attachMenuBtn) attachMenuBtn.classList.remove('active');

            const fileInput = document.createElement('input');
            fileInput.type = 'file';
            fileInput.accept = 'image/*';
            fileInput.onchange = (e) => {
                const file = e.target.files[0];
                if (!file) return;

                // Store file and show preview
                pendingImageFile = file;
                pendingFile = null; // clear any pending doc file
                const reader = new FileReader();
                reader.onload = (ev) => {
                    previewThumb.src = ev.target.result;
                    previewStrip.classList.remove('hidden');
                    input.placeholder = 'Bu görsel hakkında sorunuzu yazın...';
                    sendBtn.disabled = false;
                    input.focus();
                };
                reader.readAsDataURL(file);
            };
            fileInput.click();
        });
    }

    // ─── Video Upload ───
    const videoUploadBtn = document.getElementById('video-upload-btn');
    const videoPreviewStrip = document.getElementById('video-preview-strip');
    const videoPreviewName = document.getElementById('video-preview-name');
    const videoRemoveBtn = document.getElementById('video-remove-btn');

    const clearVideoPreview = () => {
        pendingVideoFile = null;
        if (videoPreviewStrip) videoPreviewStrip.classList.add('hidden');
        input.placeholder = 'Mesajınızı yazın...';
    };

    if (videoRemoveBtn) {
        videoRemoveBtn.addEventListener('click', clearVideoPreview);
    }

    if (videoUploadBtn) {
        videoUploadBtn.addEventListener('click', () => {
            if (isWaiting) return;

            if (attachPopover) attachPopover.classList.add('hidden');
            if (attachMenuBtn) attachMenuBtn.classList.remove('active');

            const fileInput = document.createElement('input');
            fileInput.type = 'file';
            fileInput.accept = 'video/mp4,video/webm,video/avi,video/mkv,video/mov,video/*';
            fileInput.onchange = (e) => {
                const file = e.target.files[0];
                if (!file) return;

                pendingVideoFile = file;
                pendingImageFile = null;
                pendingFile = null;
                clearImagePreview();

                if (videoPreviewName) videoPreviewName.textContent = file.name;
                if (videoPreviewStrip) videoPreviewStrip.classList.remove('hidden');
                input.placeholder = 'Bu video hakkında sorunuzu yazın...';
                sendBtn.disabled = false;
                input.focus();
            };
            fileInput.click();
        });
    }

    // ─── Audio Upload ───
    const audioUploadBtn = document.getElementById('audio-upload-btn');
    const audioPreviewStrip = document.getElementById('audio-preview-strip');
    const audioPreviewName = document.getElementById('audio-preview-name');
    const audioRemoveBtn = document.getElementById('audio-remove-btn');

    const clearAudioPreview = () => {
        pendingAudioFile = null;
        if (audioPreviewStrip) audioPreviewStrip.classList.add('hidden');
        input.placeholder = 'Mesajınızı yazın...';
    };

    if (audioRemoveBtn) {
        audioRemoveBtn.addEventListener('click', clearAudioPreview);
    }

    if (audioUploadBtn) {
        audioUploadBtn.addEventListener('click', () => {
            if (isWaiting) return;

            if (attachPopover) attachPopover.classList.add('hidden');
            if (attachMenuBtn) attachMenuBtn.classList.remove('active');

            const fileInput = document.createElement('input');
            fileInput.type = 'file';
            fileInput.accept = 'audio/mp3,audio/wav,audio/ogg,audio/flac,audio/aac,audio/m4a,audio/*';
            fileInput.onchange = (e) => {
                const file = e.target.files[0];
                if (!file) return;

                pendingAudioFile = file;
                pendingImageFile = null;
                pendingVideoFile = null;
                pendingFile = null;
                clearImagePreview();
                clearVideoPreview();

                if (audioPreviewName) audioPreviewName.textContent = file.name;
                if (audioPreviewStrip) audioPreviewStrip.classList.remove('hidden');
                input.placeholder = 'Bu ses hakkında sorunuzu yazın...';
                sendBtn.disabled = false;
                input.focus();
            };
            fileInput.click();
        });
    }

    // ─── File Upload (PDF, DOCX, TXT, etc.) ───
    let pendingFile = null;
    const fileUploadBtn = document.getElementById('file-upload-btn');
    const filePreviewStrip = document.getElementById('file-preview-strip');
    const filePreviewIcon = document.getElementById('file-preview-icon');
    const filePreviewName = document.getElementById('file-preview-name');
    const fileRemoveBtn = document.getElementById('file-remove-btn');

    const FILE_ICONS = {
        pdf: 'fa-file-pdf', docx: 'fa-file-word', doc: 'fa-file-word',
        txt: 'fa-file-lines', md: 'fa-file-lines', log: 'fa-file-lines',
        csv: 'fa-file-csv', json: 'fa-file-code', xml: 'fa-file-code',
        html: 'fa-file-code', py: 'fa-file-code', js: 'fa-file-code',
        css: 'fa-file-code', sh: 'fa-file-code', c: 'fa-file-code',
        cpp: 'fa-file-code', java: 'fa-file-code', yaml: 'fa-file-code',
        yml: 'fa-file-code', rs: 'fa-file-code', go: 'fa-file-code',
    };

    if (fileUploadBtn) {
        fileUploadBtn.addEventListener('click', () => {
            if (isWaiting) return;

            if (attachPopover) attachPopover.classList.add('hidden');
            if (attachMenuBtn) attachMenuBtn.classList.remove('active');

            const fileInput = document.createElement('input');
            fileInput.type = 'file';
            // No accept filter — show all files
            fileInput.onchange = (e) => {
                const file = e.target.files[0];
                if (!file) return;

                const mimeType = file.type || '';
                const ext = file.name.split('.').pop().toLowerCase();

                // Auto-detect: image files → image handler
                if (mimeType.startsWith('image/') || ['jpg','jpeg','png','gif','webp','bmp','svg'].includes(ext)) {
                    pendingImageFile = file;
                    pendingVideoFile = null;
                    pendingAudioFile = null;
                    pendingFile = null;
                    clearVideoPreview();
                    clearAudioPreview();
                    const reader = new FileReader();
                    reader.onload = (ev) => {
                        if (previewThumb) previewThumb.src = ev.target.result;
                        if (previewStrip) previewStrip.classList.remove('hidden');
                    };
                    reader.readAsDataURL(file);
                    if (filePreviewStrip) filePreviewStrip.classList.add('hidden');
                    input.placeholder = 'Bu görsel hakkında sorunuzu yazın...';
                    sendBtn.disabled = false;
                    input.focus();
                    return;
                }

                // Auto-detect: video files → video handler
                if (mimeType.startsWith('video/') || ['mp4','webm','avi','mkv','mov','flv','wmv'].includes(ext)) {
                    pendingVideoFile = file;
                    pendingImageFile = null;
                    pendingAudioFile = null;
                    pendingFile = null;
                    clearImagePreview();
                    clearAudioPreview();
                    if (videoPreviewName) videoPreviewName.textContent = file.name;
                    if (videoPreviewStrip) videoPreviewStrip.classList.remove('hidden');
                    if (filePreviewStrip) filePreviewStrip.classList.add('hidden');
                    input.placeholder = 'Bu video hakkında sorunuzu yazın...';
                    sendBtn.disabled = false;
                    input.focus();
                    return;
                }

                // Auto-detect: audio files → audio handler
                if (mimeType.startsWith('audio/') || ['mp3','wav','ogg','flac','aac','m4a','wma','opus'].includes(ext)) {
                    pendingAudioFile = file;
                    pendingImageFile = null;
                    pendingVideoFile = null;
                    pendingFile = null;
                    clearImagePreview();
                    clearVideoPreview();
                    if (audioPreviewName) audioPreviewName.textContent = file.name;
                    if (audioPreviewStrip) audioPreviewStrip.classList.remove('hidden');
                    if (filePreviewStrip) filePreviewStrip.classList.add('hidden');
                    input.placeholder = 'Bu ses hakkında sorunuzu yazın...';
                    sendBtn.disabled = false;
                    input.focus();
                    return;
                }

                // Default: document/text file
                pendingFile = file;
                pendingImageFile = null;
                pendingVideoFile = null;
                pendingAudioFile = null;
                previewStrip.classList.add('hidden');
                if (videoPreviewStrip) videoPreviewStrip.classList.add('hidden');
                if (audioPreviewStrip) audioPreviewStrip.classList.add('hidden');

                const iconClass = FILE_ICONS[ext] || 'fa-file';
                filePreviewIcon.className = `fa-solid ${iconClass}`;
                filePreviewName.textContent = file.name;
                filePreviewStrip.classList.remove('hidden');
                input.placeholder = 'Bu dosya hakkında sorunuzu yazın...';
                sendBtn.disabled = false;
                input.focus();
            };
            fileInput.click();
        });
    }

    // ─── Remove File Preview ───
    if (fileRemoveBtn) {
        fileRemoveBtn.addEventListener('click', () => {
            clearImagePreview();
        });
    }

    // ─── Remove Image Preview ───
    if (previewRemoveBtn) {
        previewRemoveBtn.addEventListener('click', () => {
            clearImagePreview();
        });
    }

    function clearImagePreview() {
        pendingImageFile = null;
        pendingFile = null;
        previewStrip.classList.add('hidden');
        previewThumb.src = '';
        if (filePreviewStrip) filePreviewStrip.classList.add('hidden');
        input.placeholder = 'Pardus AI\'a mesaj yazın...';
        sendBtn.disabled = input.value.trim() === '' && !pendingImageFile && !pendingFile;
    }

    // ═══ Helpers ═══

    function addMessage(text, sender, save = true, imageDataUrl = null) {
        const div = document.createElement('div');
        div.className = `msg ${sender}`;

        let avatarHTML;
        if (sender === 'assistant') {
            avatarHTML = '<div class="msg-avatar"><img src="/static/parduslogo.png" class="msg-avatar-logo" alt="Pardus"></div>';
        } else {
            avatarHTML = '<div class="msg-avatar"><i class="fa-solid fa-user"></i></div>';
        }

        let formattedText = escapeHTML(text);
        if (sender === 'assistant') {
            formattedText = formatResponse(formattedText);
        } else {
            formattedText = formattedText.replace(/\n/g, '<br>');
        }

        // Image HTML (only for user messages with attached images)
        let imageHTML = '';
        if (imageDataUrl) {
            imageHTML = `<img src="${imageDataUrl}" class="msg-attached-image" alt="Ekli görsel">`;
        }

        // Action Buttons HTML (edit only for user messages)
        const editBtnHTML = sender === 'user' ? '<button class="msg-action-btn action-edit" title="Düzenle"><i class="fa-solid fa-pen"></i></button>' : '';
        const actionsHTML = `
            <div class="msg-actions">
                <button class="msg-action-btn action-copy" title="Kopyala"><i class="fa-solid fa-copy"></i></button>
                ${editBtnHTML}
                <button class="msg-action-btn action-delete" title="Sil"><i class="fa-solid fa-trash"></i></button>
            </div>
        `;

        div.innerHTML = `
            ${avatarHTML}
            <div class="msg-content-wrapper" style="position: relative; max-width: 100%;">
                <div class="msg-bubble">${imageHTML}${formattedText}</div>
                ${actionsHTML}
            </div>
        `;

        // Wire up action buttons
        const copyBtn = div.querySelector('.action-copy');
        const editBtn = div.querySelector('.action-edit');
        const delBtn  = div.querySelector('.action-delete');

        copyBtn.addEventListener('click', () => {
            navigator.clipboard.writeText(text).then(() => {
                copyBtn.innerHTML = '<i class="fa-solid fa-check" style="color:var(--accent)"></i>';
                setTimeout(() => copyBtn.innerHTML = '<i class="fa-solid fa-copy"></i>', 2000);
            });
        });

        if (editBtn) {
            editBtn.addEventListener('click', () => {
                input.value = text;
                input.dispatchEvent(new Event('input'));
                input.focus();
                deleteMessage(div, text, sender);
            });
        }

        delBtn.addEventListener('click', () => {
            deleteMessage(div, text, sender);
        });

        messagesEl.appendChild(div);
        scrollToBottom();

        if (save) saveMessage(text, sender, imageDataUrl);
    }

    function deleteMessage(div, text, sender) {
        div.remove();
        if (currentChatId && chats[currentChatId]) {
            const idx = chats[currentChatId].messages.findIndex(m => m.text === text && m.sender === sender);
            if (idx > -1) {
                chats[currentChatId].messages.splice(idx, 1);
                saveChats();
            }
        }
    }

    function showTyping() {
        const div = document.createElement('div');
        div.className = 'msg assistant';
        div.innerHTML = `
            <div class="msg-avatar"><img src="/static/parduslogo.png" class="msg-avatar-logo" alt="Pardus"></div>
            <div class="msg-bubble typing-indicator">
                <span class="dot"></span><span class="dot"></span><span class="dot"></span>
            </div>
        `;
        messagesEl.appendChild(div);
        scrollToBottom();
        return div;
    }

    function removeTyping(el) {
        if (el && el.parentNode) el.parentNode.removeChild(el);
    }

    function scrollToBottom() {
        chatArea.scrollTop = chatArea.scrollHeight;
    }

    function escapeHTML(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    }

    function formatResponse(text) {
        // Code blocks: ```lang\ncode\n```
        text = text.replace(/```(\w*)\n?([\s\S]*?)```/g, (_, lang, code) => {
            return `<pre><code>${code.trim()}</code></pre>`;
        });
        // Inline code: `code`
        text = text.replace(/`([^`]+)`/g, '<code>$1</code>');
        // Bold: **text**
        text = text.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        // Italic: *text* (simple version without lookbehind)
        text = text.replace(/(^|[^*])\*([^*]+)\*([^*]|$)/g, '$1<em>$2</em>$3');
        // Newlines
        text = text.replace(/\n/g, '<br>');
        return text;
    }

    // ─── INIT ───
    const initApp = async () => {
        try {
            await loadChats();
            // Always start with a fresh new chat
            createNewChat();
            console.log('[Pardus AI] App initialized OK. isWaiting:', isWaiting);
        } catch(initErr) {
            console.error('[Pardus AI] Init error:', initErr);
            createNewChat();
        }
    };

    initApp();

    // ═══════════════ CONTENT GENERATION (t2i / t2v) ═══════════════

    const genImageBtn    = document.getElementById('generate-image-btn');
    const genVideoBtn    = document.getElementById('generate-video-btn');
    const inputContainer = document.getElementById('input-container');
    const mediaPreviewOverlay = document.getElementById('media-preview-overlay');
    const mediaPreviewContent = document.getElementById('media-preview-content');
    const mediaPreviewClose   = document.getElementById('media-preview-close');

    let currentGenMode = 'chat'; // 'chat' | 'image' | 'video'
    const defaultPlaceholder = "Pardus AI'a mesaj yazın...";

    function activateGenMode(mode) {
        currentGenMode = mode;

        // Remove any existing gen-mode strip
        const oldStrip = document.querySelector('.gen-mode-strip');
        if (oldStrip) oldStrip.remove();

        // Add gen-mode strip above input container
        const strip = document.createElement('div');
        const isImage = mode === 'image';
        strip.className = `gen-mode-strip ${mode}`;
        strip.innerHTML = `
            <i class="fa-solid ${isImage ? 'fa-palette' : 'fa-film'}"></i>
            <span>${isImage ? '🎨 Görsel üretim modu' : '🎬 Video üretim modu'}</span>
            <button class="gen-mode-cancel" title="İptal"><i class="fa-solid fa-xmark"></i></button>
        `;
        inputContainer.parentNode.insertBefore(strip, inputContainer);

        strip.querySelector('.gen-mode-cancel').addEventListener('click', deactivateGenMode);

        // Update input styling
        inputContainer.classList.remove('gen-mode', 'gen-mode-video');
        inputContainer.classList.add(isImage ? 'gen-mode' : 'gen-mode-video');

        // Update placeholder
        input.placeholder = isImage
            ? '🎨 Oluşturmak istediğiniz görseli açıklayın...'
            : '🎬 Oluşturmak istediğiniz videoyu açıklayın...';

        // Close popover
        if (attachPopover) attachPopover.classList.add('hidden');
        if (attachMenuBtn) attachMenuBtn.classList.remove('active');

        input.focus();
    }

    function deactivateGenMode() {
        currentGenMode = 'chat';
        const strip = document.querySelector('.gen-mode-strip');
        if (strip) strip.remove();
        inputContainer.classList.remove('gen-mode', 'gen-mode-video');
        input.placeholder = agentMode ? '🤖 Ajan için görev yazın...' : defaultPlaceholder;
    }

    if (genImageBtn) genImageBtn.addEventListener('click', () => activateGenMode('image'));
    if (genVideoBtn) genVideoBtn.addEventListener('click', () => activateGenMode('video'));

    // Generation send logic
    async function handleGenSend() {
        const prompt = input.value.trim();
        if (!prompt) return false;
        if (currentGenMode === 'chat') return false;

        const mode = currentGenMode;
        const size = '16:9'; // Default size

        // Reset input
        input.value = '';
        input.style.height = 'auto';
        sendBtn.disabled = true;
        deactivateGenMode();

        // Show in chat
        welcomeScreen.classList.add('hidden');
        messagesEl.style.display = 'flex';

        const emoji = mode === 'image' ? '🎨' : '🎬';
        const label = mode === 'image' ? 'Görsel' : 'Video';
        addMessage(`${emoji} ${label} oluştur: "${prompt}"`, 'user');

        // Progress bar
        const typingDiv = document.createElement('div');
        typingDiv.className = 'msg assistant';
        const waitMsg = mode === 'image'
            ? '🎨 Görsel oluşturuluyor... (10-30 saniye)'
            : '🎬 Video oluşturuluyor... (1-2 dakika sürebilir)';
        typingDiv.innerHTML = `
            <div class="msg-avatar"><img src="/static/parduslogo.png" class="msg-avatar-logo" alt="Pardus"></div>
            <div class="msg-bubble">
                ${waitMsg}
                <div class="gen-progress-bar"></div>
            </div>
        `;
        messagesEl.appendChild(typingDiv);
        scrollToBottom();
        isWaiting = true;

        try {
            const endpoint = mode === 'image' ? '/api/generate-image' : '/api/generate-video';
            const res = await fetch(endpoint, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ prompt, size })
            });
            const data = await res.json();

            if (typingDiv.parentNode) typingDiv.parentNode.removeChild(typingDiv);

            if (data.success) {
                if (mode === 'image' && data.image_url) {
                    addGeneratedImageMessage(data.image_url, prompt);
                } else if (mode === 'video' && data.video_url) {
                    addGeneratedVideoMessage(data.video_url, prompt);
                } else {
                    addMessage('⚠️ İçerik URL\'i alınamadı.', 'assistant');
                }

                if (currentChatId && chats[currentChatId] && !chats[currentChatId].title) {
                    chats[currentChatId].title = `${emoji} ${prompt.substring(0, 30)}${prompt.length > 30 ? '...' : ''}`;
                    saveChats();
                    renderChatHistory();
                }
            } else {
                addMessage(`⚠️ ${label} oluşturulamadı: ${data.error || 'Bilinmeyen hata'}`, 'assistant');
            }
        } catch (err) {
            if (typingDiv.parentNode) typingDiv.parentNode.removeChild(typingDiv);
            addMessage('⚠️ Bağlantı hatası: ' + err.message, 'assistant');
        }

        isWaiting = false;
        input.focus();
        return true;
    }

    function addGeneratedImageMessage(imageUrl, prompt, save = true) {
        const div = document.createElement('div');
        div.className = 'msg assistant';
        div.innerHTML = `
            <div class="msg-avatar"><img src="/static/parduslogo.png" class="msg-avatar-logo" alt="Pardus"></div>
            <div class="msg-content-wrapper" style="position: relative; max-width: 100%;">
                <div class="msg-bubble">
                    🎨 İşte oluşturduğum görsel:<br>
                    <img src="${escapeHTML(imageUrl)}" class="msg-generated-image" alt="Üretilen görsel">
                    <div class="gen-action-bar">
                        <a href="${escapeHTML(imageUrl)}" download class="gen-action-btn action-download"><i class="fa-solid fa-download"></i> İndir</a>
                        <button class="gen-action-btn action-enlarge"><i class="fa-solid fa-expand"></i> Büyüt</button>
                    </div>
                </div>
                <div class="msg-actions">
                    <button class="msg-action-btn action-copy" title="URL Kopyala"><i class="fa-solid fa-copy"></i></button>
                    <button class="msg-action-btn action-delete" title="Sil"><i class="fa-solid fa-trash"></i></button>
                </div>
            </div>
        `;
        div.querySelector('.msg-generated-image').addEventListener('click', () => openMediaPreview('image', imageUrl));
        div.querySelector('.action-enlarge').addEventListener('click', () => openMediaPreview('image', imageUrl));
        const copyBtn = div.querySelector('.action-copy');
        copyBtn.addEventListener('click', () => {
            navigator.clipboard.writeText(imageUrl).then(() => {
                copyBtn.innerHTML = '<i class="fa-solid fa-check" style="color:var(--accent)"></i>';
                setTimeout(() => copyBtn.innerHTML = '<i class="fa-solid fa-copy"></i>', 2000);
            });
        });
        div.querySelector('.action-delete').addEventListener('click', () => div.remove());
        messagesEl.appendChild(div);
        scrollToBottom();
        if (save) saveMessage(`🎨 [Üretilen Görsel](${imageUrl})`, 'assistant');
    }

    function addGeneratedVideoMessage(videoUrl, prompt, save = true) {
        const div = document.createElement('div');
        div.className = 'msg assistant';
        div.innerHTML = `
            <div class="msg-avatar"><img src="/static/parduslogo.png" class="msg-avatar-logo" alt="Pardus"></div>
            <div class="msg-content-wrapper" style="position: relative; max-width: 100%;">
                <div class="msg-bubble">
                    🎬 İşte oluşturduğum video:<br>
                    <video src="${escapeHTML(videoUrl)}" class="msg-generated-video" controls preload="metadata"></video>
                    <div class="gen-action-bar">
                        <a href="${escapeHTML(videoUrl)}" download class="gen-action-btn action-download"><i class="fa-solid fa-download"></i> İndir</a>
                        <button class="gen-action-btn action-enlarge"><i class="fa-solid fa-expand"></i> Büyüt</button>
                    </div>
                </div>
                <div class="msg-actions">
                    <button class="msg-action-btn action-copy" title="URL Kopyala"><i class="fa-solid fa-copy"></i></button>
                    <button class="msg-action-btn action-delete" title="Sil"><i class="fa-solid fa-trash"></i></button>
                </div>
            </div>
        `;
        div.querySelector('.action-enlarge').addEventListener('click', () => openMediaPreview('video', videoUrl));
        const copyBtn = div.querySelector('.action-copy');
        copyBtn.addEventListener('click', () => {
            navigator.clipboard.writeText(videoUrl).then(() => {
                copyBtn.innerHTML = '<i class="fa-solid fa-check" style="color:var(--accent)"></i>';
                setTimeout(() => copyBtn.innerHTML = '<i class="fa-solid fa-copy"></i>', 2000);
            });
        });
        div.querySelector('.action-delete').addEventListener('click', () => div.remove());
        messagesEl.appendChild(div);
        scrollToBottom();
        if (save) saveMessage(`🎬 [Üretilen Video](${videoUrl})`, 'assistant');
    }

    // ─── Fullscreen media preview ───
    function openMediaPreview(type, url) {
        if (!mediaPreviewOverlay || !mediaPreviewContent) return;
        if (type === 'image') {
            mediaPreviewContent.innerHTML = `<img src="${escapeHTML(url)}" alt="Önizleme">`;
        } else {
            mediaPreviewContent.innerHTML = `<video src="${escapeHTML(url)}" controls autoplay></video>`;
        }
        mediaPreviewOverlay.classList.remove('hidden');
    }

    function closeMediaPreview() {
        if (!mediaPreviewOverlay) return;
        mediaPreviewOverlay.classList.add('hidden');
        mediaPreviewContent.innerHTML = '';
    }

    if (mediaPreviewClose) mediaPreviewClose.addEventListener('click', closeMediaPreview);
    if (mediaPreviewOverlay) {
        mediaPreviewOverlay.addEventListener('click', (e) => {
            if (e.target === mediaPreviewOverlay) closeMediaPreview();
        });
    }
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' && mediaPreviewOverlay && !mediaPreviewOverlay.classList.contains('hidden')) {
            closeMediaPreview();
        }
    });

    // ═══════════════ AGENT MODE ═══════════════
    const agentToggleBtn = document.getElementById('agent-toggle-btn');
    const agentPanel = document.getElementById('agent-panel');
    const agentPulse = document.querySelector('.agent-pulse');
    const agentStatusText = document.getElementById('agent-status-text');
    const agentStepCount = document.getElementById('agent-step-count');
    const agentStopBtn = document.getElementById('agent-stop-btn');
    const agentLog = document.getElementById('agent-log');
    const agentModalOverlay = document.getElementById('agent-modal-overlay');
    const agentModalQuestion = document.getElementById('agent-modal-question');
    const agentModalInput = document.getElementById('agent-modal-input');
    const agentModalSubmit = document.getElementById('agent-modal-submit');
    const agentModalCancel = document.getElementById('agent-modal-cancel');

    let agentMode = false;
    let agentPollingInterval = null;
    let lastStepCount = 0;

    // Toggle agent mode
    if (agentToggleBtn) {
        agentToggleBtn.addEventListener('click', () => {
            agentMode = !agentMode;
            agentToggleBtn.classList.toggle('active', agentMode);
            if (agentPanel) agentPanel.classList.toggle('hidden', !agentMode);
            if (agentMode) {
                input.placeholder = '🤖 Ajan için görev yazın... (ör: Firefox aç ve pardus.org.tr ye git)';
            } else {
                input.placeholder = 'Pardus AI\'a mesaj yazın...';
                stopAgentPolling();
            }
        });
    }

    // Override send for agent mode
    const origSendHandler = sendBtn.onclick;
    sendBtn.addEventListener('click', (e) => {
        if (!agentMode || browserAgentMode) return; // Let normal or browser agent handler run
        e.stopImmediatePropagation();

        const task = input.value.trim();
        if (!task) return;

        addMessage('🤖 Ajan görevi: ' + task, 'user');
        input.value = '';
        input.style.height = 'auto';
        sendBtn.disabled = true;

        fetch('/api/agent/start', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({task})
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                addMessage('🤖 Ajan başlatıldı. Bilgisayarı kontrol ediyor...', 'assistant');
                startAgentPolling();
            } else {
                addMessage('⚠️ Ajan başlatılamadı: ' + (data.error || ''), 'assistant');
            }
        })
        .catch(err => addMessage('⚠️ Bağlantı hatası: ' + err.message, 'assistant'));
    }, true); // Use capture to run before normal handler

    // Also handle Enter key in agent/browser-agent mode
    input.addEventListener('keydown', (e) => {
        if ((agentMode || browserAgentMode) && e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendBtn.click();
        }
    }, true);

    function startAgentPolling() {
        lastStepCount = 0;
        if (agentStopBtn) agentStopBtn.classList.remove('hidden');
        agentPollingInterval = setInterval(pollAgentStatus, 2000);
    }

    function stopAgentPolling() {
        if (agentPollingInterval) {
            clearInterval(agentPollingInterval);
            agentPollingInterval = null;
        }
        if (agentStopBtn) agentStopBtn.classList.add('hidden');
    }

    function pollAgentStatus() {
        fetch('/api/agent/status')
        .then(r => r.json())
        .then(status => {
            const state = status.state || 'idle';

            // Update pulse indicator
            if (agentPulse) {
                agentPulse.className = 'agent-pulse ' + state;
            }

            // Update status text
            const stateLabels = {
                'idle': 'Hazır',
                'running': '🔄 Çalışıyor...',
                'waiting_user': '⏳ Yanıt bekleniyor',
                'done': '✅ Tamamlandı',
                'error': '❌ Hata'
            };
            if (agentStatusText) agentStatusText.textContent = stateLabels[state] || state;

            // Update step count
            if (agentStepCount) {
                agentStepCount.textContent = `Adım ${status.current_step}/${status.max_steps}`;
            }

            // Update log
            if (status.steps && status.steps.length > lastStepCount && agentLog) {
                const newSteps = status.steps.slice(lastStepCount);
                newSteps.forEach(s => {
                    const entry = document.createElement('div');
                    entry.className = 'agent-log-entry';
                    entry.innerHTML = `
                        <span class="step-num">#${s.step}</span>
                        <span class="step-action">${escapeHTML(s.action)}</span>
                        <span class="step-thought">${escapeHTML(s.thought || '')}</span>
                    `;
                    agentLog.appendChild(entry);
                });
                agentLog.scrollTop = agentLog.scrollHeight;
                lastStepCount = status.steps.length;
            }

            // Handle waiting for user
            if (state === 'waiting_user') {
                const lastAction = status.last_action;
                if (lastAction && lastAction.action === 'ask_user') {
                    showAgentModal(lastAction.params?.question || 'Yanıtınızı girin.');
                }
            }

            // Handle completion
            if (state === 'done' || state === 'error' || state === 'idle') {
                stopAgentPolling();
                if (state === 'done' && status.last_action) {
                    addMessage('✅ Ajan görevi tamamladı: ' + (status.last_action.thought || ''), 'assistant');
                } else if (state === 'error' && status.last_action) {
                    addMessage('❌ Ajan hatası: ' + (status.last_action.thought || ''), 'assistant');
                }
            }
        })
        .catch(err => console.error('[Agent] Polling error:', err));
    }

    function showAgentModal(question) {
        if (agentModalQuestion) agentModalQuestion.textContent = question;
        if (agentModalInput) agentModalInput.value = '';
        if (agentModalOverlay) agentModalOverlay.classList.remove('hidden');
        if (agentModalInput) agentModalInput.focus();
    }

    function hideAgentModal() {
        if (agentModalOverlay) agentModalOverlay.classList.add('hidden');
    }

    if (agentModalSubmit) {
        agentModalSubmit.addEventListener('click', () => {
            const response = agentModalInput ? agentModalInput.value : '';
            fetch('/api/agent/respond', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({response})
            });
            hideAgentModal();
        });
    }

    if (agentModalCancel) {
        agentModalCancel.addEventListener('click', () => {
            fetch('/api/agent/respond', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({response: ''})
            });
            hideAgentModal();
        });
    }

    if (agentStopBtn) {
        agentStopBtn.addEventListener('click', () => {
            fetch('/api/agent/stop', {method: 'POST'})
            .then(r => r.json())
            .then(data => {
                addMessage('🛑 Ajan durduruldu.', 'assistant');
                stopAgentPolling();
                if (agentPulse) agentPulse.className = 'agent-pulse';
                if (agentStatusText) agentStatusText.textContent = 'Durduruldu';
            });
        });
    }

    function escapeHTMLAgent(str) {
        const d = document.createElement('div');
        d.textContent = str;
        return d.innerHTML;
    }

    // ═══════════════ BROWSER AGENT MODE ═══════════════
    const baToggleBtn = document.getElementById('browser-agent-toggle-btn');
    const baPanel = document.getElementById('browser-agent-panel');
    const baPulse = document.getElementById('ba-pulse');
    const baStatusText = document.getElementById('ba-status-text');
    const baStepCount = document.getElementById('ba-step-count');
    const baStopBtn = document.getElementById('ba-stop-btn');
    const baLog = document.getElementById('ba-log');
    const baBrowserSelect = document.getElementById('ba-browser-select');

    let browserAgentMode = false;
    let baPollingInterval = null;
    let baLastStepCount = 0;

    // Sistemdeki kurulu tarayıcıları tespit et
    function loadBrowserList() {
        fetch('/api/browser-agent/browsers')
        .then(r => r.json())
        .then(data => {
            if (!data.success || !data.browsers.length || !baBrowserSelect) return;
            baBrowserSelect.innerHTML = '';
            data.browsers.forEach(b => {
                const opt = document.createElement('option');
                opt.value = b.id;
                opt.textContent = b.label;
                baBrowserSelect.appendChild(opt);
            });
        })
        .catch(() => {});
    }
    loadBrowserList();

    if (baToggleBtn) {
        baToggleBtn.addEventListener('click', () => {
            browserAgentMode = !browserAgentMode;
            baToggleBtn.classList.toggle('active', browserAgentMode);
            if (baPanel) baPanel.classList.toggle('hidden', !browserAgentMode);

            // Diğer modu kapat
            if (browserAgentMode && agentMode) {
                agentMode = false;
                agentToggleBtn.classList.remove('active');
                if (agentPanel) agentPanel.classList.add('hidden');
                stopAgentPolling();
            }

            if (browserAgentMode) {
                input.placeholder = '🌐 Tarayıcı görevi yazın... (ör: Google\'da Pardus Linux ara)';
            } else {
                input.placeholder = defaultPlaceholder;
                stopBaPolling();
            }
        });
    }

    // Browser agent send override
    sendBtn.addEventListener('click', (e) => {
        if (!browserAgentMode) return;
        e.stopImmediatePropagation();

        const task = input.value.trim();
        if (!task) return;

        const browserType = baBrowserSelect ? baBrowserSelect.value : 'chromium';

        addMessage(`🌐 Tarayıcı görevi (${browserType}): ${task}`, 'user');
        input.value = '';
        input.style.height = 'auto';
        sendBtn.disabled = true;

        fetch('/api/browser-agent/start', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({task, browser: browserType, use_profile: true})
        })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                addMessage(`🌐 Tarayıcı ajanı başlatıldı (${browserType}). Çalışıyor...`, 'assistant');
                startBaPolling();
            } else {
                addMessage('⚠️ Tarayıcı ajanı başlatılamadı: ' + (data.error || ''), 'assistant');
            }
        })
        .catch(err => addMessage('⚠️ Bağlantı hatası: ' + err.message, 'assistant'));
    }, true);

    function startBaPolling() {
        baLastStepCount = 0;
        if (baStopBtn) baStopBtn.classList.remove('hidden');
        if (baLog) baLog.innerHTML = '';
        baPollingInterval = setInterval(pollBaStatus, 2000);
    }

    function stopBaPolling() {
        if (baPollingInterval) {
            clearInterval(baPollingInterval);
            baPollingInterval = null;
        }
        if (baStopBtn) baStopBtn.classList.add('hidden');
    }

    function pollBaStatus() {
        fetch('/api/browser-agent/status')
        .then(r => r.json())
        .then(status => {
            const state = status.state || 'idle';

            if (baPulse) baPulse.className = 'agent-pulse ' + state;

            const stateLabels = {
                'idle': 'Hazır', 'running': '🔄 Çalışıyor...',
                'done': '✅ Tamamlandı', 'error': '❌ Hata'
            };
            if (baStatusText) baStatusText.textContent = stateLabels[state] || state;
            if (baStepCount) baStepCount.textContent = `Adım ${status.current_step}/${status.max_steps}`;

            // Log entries
            if (status.steps && status.steps.length > baLastStepCount && baLog) {
                const newSteps = status.steps.slice(baLastStepCount);
                newSteps.forEach(s => {
                    const entry = document.createElement('div');
                    entry.className = 'agent-log-entry';
                    const icon = {
                        'click': '🖱️', 'type': '⌨️', 'navigate': '🔗', 'scroll': '📜',
                        'wait': '⏳', 'press_key': '⌨️', 'extract': '📄', 'done': '✅',
                        'system': '⚙️', 'error': '❌'
                    }[s.action] || '▶️';
                    entry.innerHTML = `
                        <span class="step-num">#${s.step}</span>
                        <span class="step-action">${icon} ${escapeHTML(s.action)}</span>
                        <span class="step-thought">${escapeHTML(s.thought || '')}</span>
                    `;
                    baLog.appendChild(entry);
                });
                baLog.scrollTop = baLog.scrollHeight;
                baLastStepCount = status.steps.length;
            }

            // Completion
            if (state === 'done' || state === 'error' || state === 'idle') {
                stopBaPolling();
                if (state === 'done') {
                    const answer = status.final_answer || (status.last_action && status.last_action.thought) || 'Görev tamamlandı.';
                    addMessage('✅ Tarayıcı ajanı tamamladı: ' + answer, 'assistant');
                } else if (state === 'error' && status.last_action) {
                    addMessage('❌ Tarayıcı ajanı hatası: ' + (status.last_action.thought || ''), 'assistant');
                }
            }
        })
        .catch(err => console.error('[BrowserAgent] Polling error:', err));
    }

    if (baStopBtn) {
        baStopBtn.addEventListener('click', () => {
            fetch('/api/browser-agent/stop', {method: 'POST'})
            .then(r => r.json())
            .then(() => {
                addMessage('🛑 Tarayıcı ajanı durduruldu.', 'assistant');
                stopBaPolling();
                if (baPulse) baPulse.className = 'agent-pulse';
                if (baStatusText) baStatusText.textContent = 'Durduruldu';
            });
        });
    }

});
