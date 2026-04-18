    });

    if (response) {
        toggleOverlay('edit-goal-modal', false);
        showBanner('Goal updated.', 'success');
        await refreshData({ forceGoalRefresh: true });
    }
}

async function initApp() {
    const authOverlay = document.getElementById('auth-overlay');
    const appNode = document.getElementById('app');

    if (!state.auth) {
        setInitStatus('Checking session...');
        authOverlay.classList.remove('hidden');
        appNode.classList.add('hidden');
        renderAssistantThread();
        hideInitOverlay();
        return;
    }

    setInitStatus('Checking session...');
    const authOk = await validateSessionFast();
    if (!authOk) {
        sessionStorage.removeItem('jarvis_auth');
        state.auth = null;
        localStorage.removeItem('axis_token_validated_at');
        document.getElementById('auth-error').textContent = 'That token could not open the Axis workspace.';
        document.getElementById('auth-error').classList.remove('hidden');
        authOverlay.classList.remove('hidden');
        appNode.classList.add('hidden');
        hideInitOverlay();
        return;
    }

    setInitStatus('Loading workspace...');
    authOverlay.classList.add('hidden');

    appNode.classList.remove('hidden');
    renderPageSkeleton(state.activePage);
    await showPage(state.activePage);
    hideInitOverlay();

    ensureAssistantConversationId();

    if (!state.voice.recognition && state.voice.note === 'Checking voice support...') {
        initVoice();
    } else {
        renderVoiceState();
    }

    void initAuthContext();
    void refreshData({ forceGoalRefresh: true });
    void restoreAssistantConversation();

    if (state.assistant.restorePendingNotice) {
        showAssistantRestoreIndicator();
        state.assistant.restorePendingNotice = false;
    }

    if (!state.polling) {
        state.polling = window.setInterval(() => {
            void refreshData({ silent: true, forceGoalRefresh: state.activePage === 'goals' });
        }, 20000);
    }
}

function bindEvents() {
    document.getElementById('login-btn').addEventListener('click', () => void login());
    const pairBtn = document.getElementById('pair-connect-btn');
    if (pairBtn) pairBtn.addEventListener('click', () => void pairDevice());

    const copyBtn = document.getElementById('copy-device-token-btn');
    if (copyBtn) copyBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(document.getElementById('new-device-token').textContent);
        copyBtn.textContent = 'Copied!';
    });

    document.querySelectorAll('.auth-tab').forEach(tab => {
        tab.addEventListener('click', (e) => {
            document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
            document.querySelectorAll('.auth-section').forEach(s => s.classList.add('hidden'));
            e.target.classList.add('active');
            document.getElementById('auth-section-' + e.target.dataset.authTab).classList.remove('hidden');
            document.getElementById('auth-error').classList.add('hidden');
        });
    });

    // Pairing code input auto-format
    const pairInput = document.getElementById('pairing-code-input');
    if (pairInput) {
        pairInput.addEventListener('input', (e) => {
            let val = e.target.value.replace(/[^a-zA-Z0-9]/g, '').toUpperCase();
            if (val.length > 4) val = val.slice(0, 4) + '-' + val.slice(4, 8);
            e.target.value = val;
        });
    }

    // --- Mobile Drawer ---
    function openDrawer() {
        document.getElementById('sidebar-drawer')?.classList.add('is-open');
        document.getElementById('drawer-backdrop')?.classList.add('is-visible');
        document.body.style.overflow = 'hidden';
    }
    function closeDrawer() {
        document.getElementById('sidebar-drawer')?.classList.remove('is-open');
        document.getElementById('drawer-backdrop')?.classList.remove('is-visible');
        document.body.style.overflow = '';
    }
    document.getElementById('sidebar-toggle')?.addEventListener('click', openDrawer);
    document.getElementById('drawer-close')?.addEventListener('click', closeDrawer);
    document.getElementById('drawer-backdrop')?.addEventListener('click', closeDrawer);
    // Close drawer on any nav item click inside the drawer
    document.getElementById('drawer-nav')?.addEventListener('click', (e) => {
        if (e.target.closest('[data-page]')) closeDrawer();
    });

    // --- Assistant Bottom Sheet (mobile) ---
    function openSheet() {
        document.getElementById('assistant-sheet')?.classList.add('is-open');
        document.body.style.overflow = 'hidden';
    }
    function closeSheet() {
        document.getElementById('assistant-sheet')?.classList.remove('is-open');
        document.body.style.overflow = '';
    }
    document.getElementById('assistant-fab')?.addEventListener('click', openSheet);
    document.querySelector('.assistant-sheet__handle')?.addEventListener('click', closeSheet);

    // --- Device Revoked Overlay Buttons ---
    document.getElementById('revoked-pair-again')?.addEventListener('click', () => {
        document.getElementById('device-revoked-overlay')?.classList.add('hidden');
        // Show auth overlay with "Pair This Device" tab active
        document.getElementById('auth-overlay')?.classList.remove('hidden');
        document.getElementById('app')?.classList.add('hidden');
        document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.auth-section').forEach(s => s.classList.add('hidden'));
        const deviceTab = document.querySelector('[data-auth-tab="device"]');
        if (deviceTab) {
            deviceTab.classList.add('active');
            document.getElementById('auth-section-device')?.classList.remove('hidden');
        }
    });
    document.getElementById('revoked-dismiss')?.addEventListener('click', () => {
        document.getElementById('device-revoked-overlay')?.classList.add('hidden');
        // Show auth overlay with Owner Login tab active
        document.getElementById('auth-overlay')?.classList.remove('hidden');
        document.getElementById('app')?.classList.add('hidden');
        document.querySelectorAll('.auth-tab').forEach(t => t.classList.remove('active'));
        document.querySelectorAll('.auth-section').forEach(s => s.classList.add('hidden'));
        const ownerTab = document.querySelector('[data-auth-tab="owner"]');
        if (ownerTab) {
            ownerTab.classList.add('active');
            document.getElementById('auth-section-owner')?.classList.remove('hidden');
        }
    });

    // Sync drawer nav with sidebar nav so they stay in sync
    const sidebarNav = document.querySelector('.sidebar .sidebar-nav');
    const drawerNav = document.getElementById('drawer-nav');
    if (sidebarNav && drawerNav) {
        drawerNav.innerHTML = sidebarNav.innerHTML;
        drawerNav.querySelectorAll('[data-page]').forEach(btn => {
            btn.addEventListener('click', () => {
                const page = btn.dataset.page;
                if (page) void showPage(page);
            });
        });
    }

    document.getElementById('logout-btn').addEventListener('click', logout);

    document.getElementById('assistant-send-btn').addEventListener('click', () => void sendAssistantMessage(document.getElementById('assistant-input').value));
    document.getElementById('assistant-input').addEventListener('input', () => {
        autoSizeAssistantInput();
        updateAssistantComposerState();
    });
    document.getElementById('assistant-input').addEventListener('keydown', (event) => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            void sendAssistantMessage(event.currentTarget.value);
        }
    });
    document.getElementById('assistant-attach-btn').addEventListener('click', () => {
        showBanner('Assistant image attachments are coming soon.', 'success');
    });
    document.querySelectorAll('[data-assistant-mode]').forEach((button) => {
        button.addEventListener('click', () => setAssistantMode(button.dataset.assistantMode));
    });
    let voiceHoldStart = 0;
    let voiceHoldTimer = null;

    function handleVoiceStart(e) {
        if (!state.voice.available || state.assistant.pending || state.voice.listening) return;
        e.preventDefault();
        voiceHoldStart = Date.now();
        state.voice.recognition?.start();

        // Safety auto-stop after 30s
        voiceHoldTimer = setTimeout(() => {
            if (state.voice.listening) handleVoiceEnd(e);
        }, 30000);
    }

    function handleVoiceEnd(e) {
        if (!state.voice.listening) return;
        e.preventDefault();
        clearTimeout(voiceHoldTimer);

        const duration = Date.now() - voiceHoldStart;
        if (duration < 300) {
            state.voice.recognition?.stop();
            showBanner('Hold to record, release to send.', 'success');
            return;
        }

        state.voice.recognition?.stop();
    }

    const voiceBtn = document.getElementById('assistant-voice-btn');
    if (voiceBtn) {
        voiceBtn.addEventListener('mousedown', handleVoiceStart);
        voiceBtn.addEventListener('mouseup', handleVoiceEnd);
        voiceBtn.addEventListener('touchstart', handleVoiceStart);
        voiceBtn.addEventListener('touchend', handleVoiceEnd);
        voiceBtn.addEventListener('mouseleave', () => {
            if (state.voice.listening) handleVoiceEnd({ preventDefault: () => { } });
        });
    }

    document.getElementById('stop-speaking-btn')?.addEventListener('click', stopSpeaking);

    autoSizeAssistantInput();
    updateAssistantComposerState();

    document.getElementById('goal-cancel-btn').addEventListener('click', () => toggleOverlay('new-goal-modal', false));
    document.getElementById('goal-submit-btn').addEventListener('click', () => void createGoalFromModal());
    document.getElementById('edit-goal-cancel-btn').addEventListener('click', () => toggleOverlay('edit-goal-modal', false));
    document.getElementById('edit-goal-submit-btn').addEventListener('click', () => void saveGoalEdits());

    document.addEventListener('click', (event) => {
        const navButton = event.target.closest('.nav-btn[data-page]');
        if (navButton) {
            void showPage(navButton.dataset.page);
            return;
        }
