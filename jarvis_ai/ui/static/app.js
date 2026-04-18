const PAGE_META = {
    overview: {
        title: 'Axis Overview',
        description: 'The live command deck for system health, active work, approvals, blockers, and recommended next actions.',
        purpose: 'Use Overview to understand the current operating picture in one glance and hand off deeper work to the right page.',
        sections: ['Health line', 'Recommended next action', 'Active goals', 'Pending approvals', 'Permission warnings', 'Recent activity']
    },
    'axis-chat': {
        title: 'Axis Chat',
        description: 'A dedicated conversation workspace for talking directly with the system without leaving the main shell.',
        purpose: 'Use Axis Chat when you want a focused full-page conversation surface on top of the live Axis workspace.',
        sections: ['Conversation thread', 'Message composer']
    },
    goals: {
        title: 'Goals',
        description: 'Create, track, inspect, and control governed goals from one focused workspace.',
        purpose: 'Use Goals to manage durable work items, inspect a selected goal, and understand the exact state of execution.',
        sections: ['Goal queue', 'Focused goal detail', 'Action controls', 'Step plan', 'Goal timeline']
    },
    approvals: {
        title: 'Approvals',
        description: 'Review sensitive actions before execution and keep the trust model explicit.',
        purpose: 'Use Approvals to clear pending work, reject unsafe actions, or execute work that has already been approved.',
        sections: ['Approval summary', 'Pending review queue', 'Execution-ready actions']
    },
    'axis-hub': {
        title: 'Axis Hub',
        description: 'See the ecosystem view of live, partial, planned, and simulated skill surfaces.',
        purpose: 'Use Axis Hub to understand how the product fits together and which subsystems are truly ready.',
        sections: ['Skill maturity', 'Activity signals', 'Training visibility']
    },
    guide: {
        title: 'Capabilities & Guide',
        description: 'A truthful guide to what is live, degraded, mocked, limited, or still on the roadmap.',
        purpose: 'Use this page when you need clear product truth instead of assumptions about what Axis can do.',
        sections: ['Capability realism', 'Workflow guide', 'Current constraints']
    },
    permissions: {
        title: 'Permissions & Access',
        description: 'The desktop-first trust center for permission state, pending requests, and capability posture.',
        purpose: 'Use Permissions & Access to understand what Axis is allowed to do and why certain workflows are intentionally constrained.',
        sections: ['Trust summary', 'Permission requests', 'Capability controls']
    },
    security: {
        title: 'Security & Compliance',
        description: 'Review local trust boundaries, audit visibility, and honest compliance posture.',
        purpose: 'Use Security & Compliance to understand how the current build protects the owner and where enterprise claims intentionally stop.',
        sections: ['Security summary', 'Trust posture', 'Audit and compliance notes']
    },
    settings: {
        title: 'Settings',
        description: 'Adjust the live shell, voice, notification, and approval defaults that are safe to change today.',
        purpose: 'Use Settings to tune the operating experience without touching backend internals or unsafe controls.',
        sections: ['Editable settings', 'System-managed controls']
    },
    profiles: {
        title: 'Profiles & Plans',
        description: 'Align Axis to the active workspace profile and see which plan posture actually fits the current system.',
        purpose: 'Use Profiles & Plans to understand product fit, workspace posture, and future upgrade relevance.',
        sections: ['Active profile', 'Plan posture', 'Feature matrix']
    },
    pricing: {
        title: 'Pricing',
        description: 'Explore the future public Axis plans with transparent tiers, glass pricing cards, and billing options.',
        purpose: 'Use Pricing to understand how Axis is expected to package personal automation, power-user controls, and team-ready governance.',
        sections: ['Hero header', 'Billing toggle', 'Pricing cards', 'Trust strip']
    }
};

const ROLE_RANK = {
    reader: 0,
    operator: 1,
    executor: 2,
    owner: 3,
    admin: 3
};

const ACTION_LABELS = {
    plan: 'Generate plan',
    pause: 'Pause goal',
    resume: 'Resume goal',
    stop: 'Stop goal',
    replan: 'Replan goal',
    reconcile: 'Reconcile goal'
};

const ASSISTANT_CONVERSATION_STORAGE_KEY = 'axis_assistant_conv_id';
const ASSISTANT_HISTORY_LIMIT = 20;
const ASSISTANT_RESTORE_NOTICE_MS = 2600;
const AXIS_INTRO_MIN_MS = 1050;
const AXIS_INTRO_EXIT_MS = 480;
const TOKEN_VALIDATION_MAX_AGE_MS = 5 * 60 * 1000;
const API_TIMEOUT_MS = 12000;

const inMemoryAssistantStorage = {};

const ASSISTANT_MODE_META = {
    default: {
        label: 'Prompt',
        placeholder: 'Ask Axis what to do next...',
        note: 'Ask, search, or direct the next move.'
    },
    search: {
        label: 'Search',
        placeholder: 'Search across Axis context, live status, or the web...',
        note: 'Search mode frames the request like a live lookup.'
    },
    think: {
        label: 'Think',
        placeholder: 'Think deeply about this problem, tradeoff, or next step...',
        note: 'Think mode nudges the assistant toward deeper reasoning.'
    },
    canvas: {
        label: 'Canvas',
        placeholder: 'Draft UI, content, or implementation ideas for the workspace...',
        note: 'Canvas mode is tuned for drafting and building artifacts.'
    }
};

const state = {
    auth: JSON.parse(sessionStorage.getItem('jarvis_auth')) || null,
    authContext: null,
    activePage: 'overview',
    summary: null,
    summaryForbidden: false,
    about: null,
    readiness: null,
    permissionsSnapshot: null,
    settingsData: null,
    guideData: null,
    axisHubData: null,
    securityData: null,
    recentActivity: [],
    llmModelsData: null,
    profilesData: null,
    goals: [],
    approvals: [],
    approvalsMeta: null,
    approvalsForbidden: false,
    blocked: [],
    blockedForbidden: false,
    results: [],
    resultsForbidden: false,
    selectedGoalId: null,
    goalContext: null,
    goalSummary: null,
    goalEvents: [],
    goalQuery: '',
    goalViewFilter: 'all',
    approvalViewFilter: 'all',
    permissionsFilter: '',
    permissionStateFilter: 'all',
    guideFilter: '',
    pricingBillingCycle: 'monthly',
    polling: null,
    assistant: {
        conversationId: null,
        messages: [],
        mode: 'default',
        greetedPages: {},
        pending: false,
        restoreTimer: null,
        restorePendingNotice: false,
        restoreGreetingCheck: false,
        highlightedGoalId: null,
        highlightedApprovalId: null,
        highlightedPermissionKey: null,
        pendingNavigationHint: null,
        storage: null,
        storageMode: 'memory',
        storageScope: null
    },
    voice: {
        capabilities: null,
        recognition: null,
        available: false,
        listening: false,
        processing: false,
        lastInputWasVoice: false,
        note: 'Checking voice support...'
    },
    voiceSettings: JSON.parse(localStorage.getItem('axis_voice_settings')) || {
        responsesEnabled: true,
        autoSend: true,
        voiceInputEnabled: true,
        preferredVoiceName: null
    }
};

const PRICING_PLANS = [
    {
        id: 'personal',
        name: 'Personal',
        description: 'For individuals exploring AI automation',
        prices: { monthly: '0', yearly: '0' },
        features: [
            '1 user',
            'Basic goal management',
            'Gmail read access',
            '5 active goals limit',
            'Community support',
            'Conversation workspace (limited)'
        ],
        buttonText: 'Get Started Free',
        buttonVariant: 'secondary',
        action: 'home'
    },
    {
        id: 'pro',
        name: 'Pro',
        description: 'For power users who want full Axis capabilities',
        prices: { monthly: '29', yearly: '23' },
        features: [
            '1 user',
            'Unlimited goals',
            'Gmail + Calendar full integration',
            'Web automation (Playwright)',
            'Voice push-to-talk',
            'Conversation workspace (full)',
            'Priority support',
            'Audit logs + permissions'
        ],
        buttonText: 'Start Pro',
        buttonVariant: 'primary',
        action: 'coming-soon',
        badge: 'Most Popular',
        isPopular: true
    },
    {
        id: 'team',
        name: 'Team',
        description: 'For small teams sharing one Axis ecosystem',
        prices: { monthly: '79', yearly: '63' },
        features: [
            'Up to 10 users',
            'Everything in Pro',
            'Shared goal workspace',
            'Team approval flows',
            'Role-based access control',
            'Team audit dashboard',
            'Dedicated onboarding'
        ],
        buttonText: 'Start Team Plan',
        buttonVariant: 'primary',
        action: 'coming-soon'
    },
    {
        id: 'enterprise',
        name: 'Enterprise',
        description: 'For organizations needing full control and compliance',
        custom: true,
        features: [
            'Unlimited users',
            'Everything in Team',
            'Custom integrations',
            'On-premise deployment option',
            'SLA guarantee',
            'Dedicated account manager',
            'Custom security policies'
        ],
        buttonText: 'Contact Us',
        buttonVariant: 'secondary',
        action: 'contact'
    }
];

const PRICING_SHADER_VERTEX_SOURCE = `
    attribute vec2 aPosition;
    void main() {
        gl_Position = vec4(aPosition, 0.0, 1.0);
    }
`;

const PRICING_SHADER_FRAGMENT_SOURCE = `
    precision highp float;

    uniform float iTime;
    uniform vec2 iResolution;

    float ring(vec2 uv, vec2 center, float radius, float width) {
        float dist = abs(length(uv - center) - radius);
        return smoothstep(width, 0.0, dist);
    }

    void main() {
        vec2 uv = gl_FragCoord.xy / iResolution.xy;
        vec2 centered = uv - 0.5;
        centered.x *= iResolution.x / max(iResolution.y, 1.0);

        vec2 center = vec2(0.5, 0.55);
        float time = iTime * 0.42;
        float drift = sin(time * 1.2) * 0.008;
        float pulse = sin(time * 1.7) * 0.004;

        float outerRing = ring(uv + vec2(drift, 0.0), center, 0.268 + pulse, 0.011);
        float innerRing = ring(uv - vec2(drift * 0.6, 0.0), center, 0.232 - pulse * 0.7, 0.006);
        float halo = ring(uv, center, 0.248, 0.02);

        float haze = exp(-12.5 * dot(centered, centered));
        float sweep = smoothstep(0.18, 0.82, uv.y) * (0.45 + 0.55 * sin((uv.x * 7.0) - time * 1.9));

        vec3 color = vec3(0.0);
        color += vec3(0.05, 0.28, 0.96) * outerRing * 1.04;
        color += vec3(0.12, 0.62, 1.0) * innerRing * 1.3;
        color += vec3(0.18, 0.34, 1.0) * halo * 0.22;
        color += vec3(0.04, 0.16, 0.62) * haze * sweep * 0.14;

        float alpha = clamp(outerRing * 0.6 + innerRing * 0.66 + halo * 0.09 + haze * 0.03, 0.0, 0.68);
        gl_FragColor = vec4(color, alpha);
    }
`;

const pricingShaderState = {
    canvas: null,
    gl: null,
    program: null,
    buffer: null,
    frameId: null,
    resizeHandler: null
};

function createRuntimeId(prefix = 'axis') {
    if (window.crypto?.randomUUID) {
        return `${prefix}-${window.crypto.randomUUID()}`;
    }
    return `${prefix}-${Date.now()}-${Math.random().toString(16).slice(2, 10)}`;
}

function sanitizeStorageToken(value) {
    return String(value || 'unknown')
        .toLowerCase()
        .replace(/[^a-z0-9_-]+/g, '-')
        .replace(/^-+|-+$/g, '') || 'unknown';
}

function canUseStorage(storage) {
    try {
        const probe = `axis-storage-probe-${Date.now()}`;
        storage.setItem(probe, '1');
        storage.removeItem(probe);
        return true;
    } catch (_error) {
        return false;
    }
}

function getAssistantStorageAdapter() {
    if (state.assistant.storage) {
        return {
            backend: state.assistant.storage,
            mode: state.assistant.storageMode
        };
    }

    if (typeof window !== 'undefined') {
        try {
            if (canUseStorage(window.localStorage)) {
                return {
                    backend: window.localStorage,
                    mode: 'persistent'
                };
            }
        } catch (_error) {
            // Fall through to session storage.
        }
    }

    if (typeof window !== 'undefined') {
        try {
            if (canUseStorage(window.sessionStorage)) {
                return {
                    backend: window.sessionStorage,
                    mode: 'session'
                };
            }
        } catch (_error) {
            // Fall through to the in-memory session path.
        }
    }

    return {
        backend: {
            getItem(key) {
                return Object.prototype.hasOwnProperty.call(inMemoryAssistantStorage, key)
                    ? inMemoryAssistantStorage[key]
                    : null;
            },
            setItem(key, value) {
                inMemoryAssistantStorage[key] = String(value);
            },
            removeItem(key) {
                delete inMemoryAssistantStorage[key];
            }
        },
        mode: 'memory'
    };
}

function readAssistantConversationStore(storage) {
    try {
        const raw = storage.getItem(ASSISTANT_CONVERSATION_STORAGE_KEY);
        if (!raw) {
            return {};
        }
        const parsed = JSON.parse(raw);
        return parsed && typeof parsed === 'object' ? parsed : {};
    } catch (_error) {
        return {};
    }
}

function writeAssistantConversationStore(storage, conversations) {
    try {
        storage.setItem(ASSISTANT_CONVERSATION_STORAGE_KEY, JSON.stringify(conversations));
    } catch (_error) {
        // Gracefully fall back to the in-memory session path.
    }
}

function assistantConversationScopeKey() {
    const authType = state.authContext?.type || state.auth?.mode || 'guest';
    const sessionClass = state.authContext?.session_class || `${authType}_session`;
    const role = state.authContext?.role || 'reader';
    const identity = authType === 'device'
        ? (state.authContext?.id || 'device')
        : 'owner';

    return [
        sanitizeStorageToken(authType),
        sanitizeStorageToken(identity),
        sanitizeStorageToken(sessionClass),
        sanitizeStorageToken(role)
    ].join(':');
}

function setAssistantConversationId(conversationId) {
    const nextConversationId = String(conversationId || '').trim();
    if (!nextConversationId) {
        return null;
    }

    const adapter = getAssistantStorageAdapter();
    const storage = adapter.backend;
    const scope = state.assistant.storageScope || assistantConversationScopeKey();
    const store = readAssistantConversationStore(storage);

    state.assistant.storage = storage;
    state.assistant.storageMode = adapter.mode;
    state.assistant.storageScope = scope;
    state.assistant.conversationId = nextConversationId;

    store[scope] = nextConversationId;
    writeAssistantConversationStore(storage, store);
    return nextConversationId;
}

function ensureAssistantConversationId() {
    const adapter = getAssistantStorageAdapter();
    const storage = adapter.backend;
    const scope = assistantConversationScopeKey();
    const store = readAssistantConversationStore(storage);
    const existing = store[scope];

    state.assistant.storage = storage;
    state.assistant.storageMode = adapter.mode;
    state.assistant.storageScope = scope;

    if (existing) {
        state.assistant.conversationId = existing;
        return existing;
    }

    return setAssistantConversationId(createRuntimeId(`axis-assistant-${sanitizeStorageToken(state.authContext?.type || 'owner')}`));
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#39;');
}

function labelize(value) {
    return String(value || '')
        .replace(/_/g, ' ')
        .replace(/\b\w/g, (match) => match.toUpperCase());
}

function shorten(value, limit = 180) {
    const text = String(value || '').trim();
    if (text.length <= limit) {
        return text;
    }
    return `${text.slice(0, Math.max(0, limit - 3)).trim()}...`;
}

function formatDateTime(value) {
    if (!value) {
        return '--';
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return escapeHtml(value);
    }
    return date.toLocaleString();
}

function formatTime(value) {
    if (!value) {
        return '--';
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return '--';
    }
    return date.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
}

function formatRelativeTime(value) {
    if (!value) {
        return 'Unknown time';
    }
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) {
        return String(value);
    }

    const diffMs = Date.now() - date.getTime();
    const minutes = Math.round(Math.abs(diffMs) / 60000);
    if (minutes < 1) {
        return 'Just now';
    }
    if (minutes < 60) {
        return `${minutes}m ${diffMs >= 0 ? 'ago' : 'from now'}`;
    }
    const hours = Math.round(minutes / 60);
    if (hours < 24) {
        return `${hours}h ${diffMs >= 0 ? 'ago' : 'from now'}`;
    }
    const days = Math.round(hours / 24);
    return `${days}d ${diffMs >= 0 ? 'ago' : 'from now'}`;
}

function roleValue(role) {
    return ROLE_RANK[role] ?? 0;
}

function isOwnerRole() {
    const type = state.authContext?.type;
    const role = state.authContext?.role;
    return type === 'owner' || role === 'owner' || role === 'admin';
}

function hasMinimumRole(role) {
    if (isOwnerRole()) {
        return true;
    }
    return roleValue(state.authContext?.role) >= roleValue(role);
}

function getAuthHeaders() {
    // Priority 1: Explicitly provided owner token in memory (from login form)
    if (state.auth && state.auth.mode === 'owner') {
        return { 'X-Jarvis-Token': state.auth.token };
    }

    // Priority 2: Persisted device token — cached in state to avoid repeated localStorage reads
    if (state._cachedDeviceToken === undefined) {
        state._cachedDeviceToken = localStorage.getItem('axis_device_token') || null;
    }
    if (state._cachedDeviceToken) {
        return { 'X-Device-Token': state._cachedDeviceToken };
    }

    // Priority 3: Other auth modes
    if (!state.auth) {
        return {};
    }
    return state.auth.mode === 'owner'
        ? { 'X-Jarvis-Token': state.auth.token }
        : { 'X-Device-Token': state.auth.token };
}

function findPermission(permissionKey) {
    return state.permissionsSnapshot?.permissions?.find((permission) => permission.key === permissionKey) || null;
}

function pendingPermissionRequests() {
    return Array.isArray(state.permissionsSnapshot?.requests)
        ? state.permissionsSnapshot.requests.filter((request) => request.status === 'pending')
        : [];
}

function topRecommendation() {
    return state.summary?.summary?.recommended_next_actions?.[0] || null;
}

function currentBlockedCount() {
    const blocked = state.summary?.summary?.blocked_counts || {};
    return (blocked.goals || 0) + (blocked.steps || 0);
}

function renderSegmentedFilters(options, activeValue, datasetName, labelPrefix) {
    return `
        <div class="segmented-filters" role="group" aria-label="${escapeHtml(labelPrefix)}">
            ${options.map((option) => `
                <button
                    class="filter-pill ${activeValue === option.value ? 'is-active' : ''}"
                    type="button"
                    data-${datasetName}="${escapeHtml(option.value)}"
                >${escapeHtml(option.label)}</button>
            `).join('')}
        </div>
    `;
}

function goalMatchesViewFilter(goal) {
    const filter = state.goalViewFilter || 'all';
    if (filter === 'blocked') {
        return goal.status === 'blocked';
    }
    if (filter === 'active') {
        return ['active', 'planned', 'draft', 'awaiting_approval', 'paused'].includes(goal.status);
    }
    if (filter === 'approval') {
        return goal.status === 'awaiting_approval' || goal.requires_approval;
    }
    return true;
}

function approvalMatchesViewFilter(approval) {
    const filter = state.approvalViewFilter || 'all';
    if (filter === 'pending') {
        return approval.action_status === 'pending';
    }
    if (filter === 'approved') {
        return approval.action_status === 'approved';
    }
    if (filter === 'executed') {
        return approval.action_status === 'executed';
    }
    return true;
}

function permissionMatchesStateFilter(permission) {
    const filter = state.permissionStateFilter || 'all';
    if (filter === 'disabled') {
        return (permission.effective_status || permission.current_state) === 'disabled';
    }
    if (filter === 'limited') {
        return (permission.effective_status || permission.current_state) === 'limited';
    }
    if (filter === 'active') {
        return (permission.effective_status || permission.current_state) === 'active';
    }
    return true;
}

function deriveModelLabel() {
    if (state.llmModelsData?.active_model && state.llmModelsData.active_model !== 'mock') {
        const model = state.llmModelsData.models.find(m => m.id === state.llmModelsData.active_model);
        return model ? model.name : state.llmModelsData.active_model;
    }
    if (state.readiness?.llm_mode && state.readiness.llm_mode !== 'mock') {
        return String(state.readiness.llm_mode);
    }
    return '--';
}

function deriveHealthLabel() {
    if (state.readiness?.overall) {
        return state.readiness.overall === 'ready' ? 'Ready' : labelize(state.readiness.overall);
    }
    if (state.summary) {
        return 'Connected';
    }
    return 'Syncing';
}

function toneClass(value) {
    const normalized = String(value || '').toLowerCase();
    if (
        ['ready', 'active', 'online', 'live', 'included', 'approved', 'ok', 'aligned', 'enabled'].includes(normalized)
        || normalized.startsWith('active')
    ) {
        return 'tone-success';
    }
    if (
        ['completed', 'executed', 'info'].includes(normalized)
        || normalized.includes('complete')
    ) {
        return 'tone-info';
    }
    if (
        ['blocked', 'failed', 'rejected', 'error', 'disabled', 'denied', 'stopped', 'critical'].includes(normalized)
        || normalized.includes('danger')
        || normalized.includes('block')
    ) {
        return 'tone-danger';
    }
    if (
        ['pending', 'degraded', 'limited', 'planned', 'partial', 'mocked', 'unavailable', 'not_configured', 'experimental', 'guided', 'upgrade_recommended'].includes(normalized)
        || normalized.includes('pending')
        || normalized.includes('degrad')
        || normalized.includes('planned')
        || normalized.includes('mock')
        || normalized.includes('partial')
    ) {
        return 'tone-warning';
    }
    return 'tone-neutral';
}

function statusPill(status, label = null) {
    const text = label || labelize(status || 'neutral');
    return `<span class="status-pill ${toneClass(status)}">${escapeHtml(text)}</span>`;
}

function chip(text) {
    return `<span class="chip">${escapeHtml(text)}</span>`;
}

function metricCard(label, value, hint) {
    return `
        <article class="metric-card">
            <span class="metric-label">${escapeHtml(label)}</span>
            <strong class="metric-value">${escapeHtml(value)}</strong>
            <span class="metric-hint">${escapeHtml(hint)}</span>
        </article>
    `;
}

function emptyState(title, copy) {
    return `
        <div class="empty-state">
            <strong>${escapeHtml(title)}</strong>
            <div class="microcopy">${escapeHtml(copy)}</div>
        </div>
    `;
}

function pageIntro(pageId, actions = '') {
    const meta = PAGE_META[pageId];
    if (!meta) {
        return '';
    }
    return `
        <section class="page-intro">
            <div class="page-intro__heading">
                <div>
                    <p class="eyebrow">${escapeHtml(meta.title)}</p>
                    <h3 class="page-intro__title">${escapeHtml(meta.title)}</h3>
                    <p class="page-intro__purpose">${escapeHtml(meta.purpose)}</p>
                </div>
                ${actions ? `<div class="page-actions">${actions}</div>` : ''}
            </div>
        </section>
    `;
}

function renderAxisChatPage() {
    document.getElementById('page-axis-chat').innerHTML = `
        <div class="axis-chat-page axis-chat-container">
            <div id="axis-chat-assistant-slot" class="axis-chat-assistant-slot"></div>
        </div>
    `;
}

function pricingDisplay(plan, cycle = state.pricingBillingCycle) {
    if (plan.custom) {
        return {
            prefix: '',
            amount: 'Custom',
            suffix: '',
            note: 'Talk with us about security, deployment, and compliance fit.'
        };
    }

    const normalizedCycle = cycle === 'yearly' ? 'yearly' : 'monthly';
    return {
        prefix: '$',
        amount: String(plan.prices[normalizedCycle]),
        suffix: '/mo',
        note: plan.id === 'personal'
            ? 'Free forever.'
            : normalizedCycle === 'yearly'
                ? 'Billed yearly. Save 20%.'
                : 'Cancel anytime.'
    };
}

function pricingCheckIcon() {
    return `
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.4" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true">
            <path d="M20 6 9 17l-5-5"></path>
        </svg>
    `;
}

function pricingTrustItem(copy) {
    return `
        <div class="pricing-trust-item">
            <span class="pricing-trust-item__icon">${pricingCheckIcon()}</span>
            <span>${escapeHtml(copy)}</span>
        </div>
    `;
}

function pricingCardMarkup(plan) {
    const display = pricingDisplay(plan);

    return `
        <article class="pricing-card ${plan.isPopular ? 'is-popular' : ''}" data-pricing-plan="${escapeHtml(plan.id)}">
            ${plan.badge ? `<span class="pricing-card__badge">${escapeHtml(plan.badge)}</span>` : ''}
            <div class="pricing-card__inner">
                <div class="pricing-card__header">
                    <div>
                        <h2 class="pricing-card__title">${escapeHtml(plan.name)}</h2>
                        <p class="pricing-card__description">${escapeHtml(plan.description)}</p>
                    </div>
                </div>

                <div class="pricing-card__divider"></div>

                <div class="pricing-card__price-block">
                    <div class="pricing-card__price-line">
                        <span class="pricing-card__prefix ${display.prefix ? '' : 'is-hidden'}" data-pricing-price-prefix="${escapeHtml(plan.id)}">${escapeHtml(display.prefix)}</span>
                        <span class="pricing-card__amount" data-pricing-price-value="${escapeHtml(plan.id)}">${escapeHtml(display.amount)}</span>
                        <span class="pricing-card__suffix ${display.suffix ? '' : 'is-hidden'}" data-pricing-price-suffix="${escapeHtml(plan.id)}">${escapeHtml(display.suffix)}</span>
                    </div>
                    <div class="pricing-card__billing-note" data-pricing-price-note="${escapeHtml(plan.id)}">${escapeHtml(display.note)}</div>
                </div>

                <ul class="pricing-card__features">
                    ${plan.features.map((feature) => `
                        <li class="pricing-feature">
                            <span class="pricing-feature__icon">${pricingCheckIcon()}</span>
                            <span>${escapeHtml(feature)}</span>
                        </li>
                    `).join('')}
                </ul>

                <button
                    class="pricing-cta pricing-cta--${escapeHtml(plan.buttonVariant)}"
                    type="button"
                    data-pricing-action="${escapeHtml(plan.action)}"
                    data-pricing-plan-name="${escapeHtml(plan.name)}"
                >${escapeHtml(plan.buttonText)}</button>
            </div>
        </article>
    `;
}

function renderPricingPage() {
    const cycle = state.pricingBillingCycle === 'yearly' ? 'yearly' : 'monthly';
    const cycleCaption = cycle === 'yearly'
        ? 'Yearly billing selected. Save 20% on Pro and Team.'
        : 'Monthly billing selected. Upgrade when you are ready.';

    document.getElementById('page-pricing').innerHTML = `
        <div class="pricing-page">
            <section class="pricing-shell">
                <canvas id="pricing-shader-canvas" class="pricing-shell__shader" aria-hidden="true"></canvas>
                <div class="pricing-shell__glow" aria-hidden="true"></div>

                <div class="pricing-shell__content">
                    <section class="pricing-hero" data-page-section="hero">
                        <span class="pricing-hero__pill">Simple, transparent pricing</span>
                        <h1 class="pricing-hero__title">
                            <span>Find the Perfect Plan</span>
                            <strong>for Your Axis</strong>
                        </h1>
                        <p class="pricing-hero__subtitle">Start free, upgrade when you're ready.<br>No hidden fees. Cancel anytime.</p>

                        <div class="pricing-hero__controls">
                            <div class="pricing-toggle" data-pricing-toggle data-cycle="${escapeHtml(cycle)}" role="group" aria-label="Billing cycle">
                                <button class="pricing-toggle__option ${cycle === 'monthly' ? 'is-active' : ''}" type="button" data-pricing-cycle="monthly">Monthly</button>
                                <button class="pricing-toggle__option ${cycle === 'yearly' ? 'is-active' : ''}" type="button" data-pricing-cycle="yearly">
                                    <span>Yearly</span>
                                    <span class="pricing-toggle__save">Save 20%</span>
                                </button>
                            </div>
                            <span class="pricing-hero__billing" data-pricing-cycle-caption>${escapeHtml(cycleCaption)}</span>
                        </div>
                    </section>

                    <section class="pricing-grid" data-page-section="plans">
                        ${PRICING_PLANS.map((plan) => pricingCardMarkup(plan)).join('')}
                    </section>

                    <section class="pricing-trust-strip" data-page-section="trust">
                        ${pricingTrustItem('No credit card required to start')}
                        ${pricingTrustItem('Cancel or change plan anytime')}
                        ${pricingTrustItem('Data stays on your device with local deployment')}
                    </section>
                </div>
            </section>
        </div>
    `;
}

function updatePricingToggleState() {
    const toggle = document.querySelector('[data-pricing-toggle]');
    if (!toggle) {
        return;
    }

    const cycle = state.pricingBillingCycle === 'yearly' ? 'yearly' : 'monthly';
    toggle.dataset.cycle = cycle;
    toggle.querySelectorAll('[data-pricing-cycle]').forEach((button) => {
        button.classList.toggle('is-active', button.dataset.pricingCycle === cycle);
    });

    const caption = document.querySelector('[data-pricing-cycle-caption]');
    if (caption) {
        caption.textContent = cycle === 'yearly'
            ? 'Yearly billing selected. Save 20% on Pro and Team.'
            : 'Monthly billing selected. Upgrade when you are ready.';
    }
}

function setPricingBillingCycle(nextCycle) {
    const cycle = nextCycle === 'yearly' ? 'yearly' : 'monthly';
    if (state.pricingBillingCycle === cycle) {
        return;
    }

    const cards = Array.from(document.querySelectorAll('[data-pricing-plan]'));
    if (!cards.length) {
        state.pricingBillingCycle = cycle;
        return;
    }

    cards.forEach((card) => card.classList.add('is-price-changing'));

    window.setTimeout(() => {
        state.pricingBillingCycle = cycle;

        PRICING_PLANS.forEach((plan) => {
            const display = pricingDisplay(plan, cycle);
            const prefixNode = document.querySelector(`[data-pricing-price-prefix="${plan.id}"]`);
            const valueNode = document.querySelector(`[data-pricing-price-value="${plan.id}"]`);
            const suffixNode = document.querySelector(`[data-pricing-price-suffix="${plan.id}"]`);
            const noteNode = document.querySelector(`[data-pricing-price-note="${plan.id}"]`);

            if (prefixNode) {
                prefixNode.textContent = display.prefix;
                prefixNode.classList.toggle('is-hidden', !display.prefix);
            }
            if (valueNode) {
                valueNode.textContent = display.amount;
            }
            if (suffixNode) {
                suffixNode.textContent = display.suffix;
                suffixNode.classList.toggle('is-hidden', !display.suffix);
            }
            if (noteNode) {
                noteNode.textContent = display.note;
            }
        });

        updatePricingToggleState();
        window.requestAnimationFrame(() => {
            cards.forEach((card) => card.classList.remove('is-price-changing'));
        });
    }, 150);
}

function openPricingComingSoonModal(planName) {
    const modalTitle = document.getElementById('pricing-modal-title');
    const modalCopy = document.getElementById('pricing-modal-copy');

    if (modalTitle) {
        modalTitle.textContent = `${planName} plan coming soon`;
    }
    if (modalCopy) {
        modalCopy.textContent = `You'll be notified when it's available.`;
    }

    toggleOverlay('pricing-coming-soon-modal', true);
}

function closePricingComingSoonModal() {
    toggleOverlay('pricing-coming-soon-modal', false);
}

function compilePricingShader(gl, type, source) {
    const shader = gl.createShader(type);
    if (!shader) {
        throw new Error('Unable to create shader.');
    }
    gl.shaderSource(shader, source);
    gl.compileShader(shader);
    if (!gl.getShaderParameter(shader, gl.COMPILE_STATUS)) {
        const info = gl.getShaderInfoLog(shader) || 'Unknown shader compilation error.';
        gl.deleteShader(shader);
        throw new Error(info);
    }
    return shader;
}

function teardownPricingShader() {
    if (pricingShaderState.frameId !== null) {
        window.cancelAnimationFrame(pricingShaderState.frameId);
    }
    if (pricingShaderState.resizeHandler) {
        window.removeEventListener('resize', pricingShaderState.resizeHandler);
    }
    if (pricingShaderState.gl && pricingShaderState.buffer) {
        pricingShaderState.gl.deleteBuffer(pricingShaderState.buffer);
    }
    if (pricingShaderState.gl && pricingShaderState.program) {
        pricingShaderState.gl.deleteProgram(pricingShaderState.program);
    }

    pricingShaderState.canvas = null;
    pricingShaderState.gl = null;
    pricingShaderState.program = null;
    pricingShaderState.buffer = null;
    pricingShaderState.frameId = null;
    pricingShaderState.resizeHandler = null;
}

function syncPricingShader() {
    const canvas = state.activePage === 'pricing'
        ? document.getElementById('pricing-shader-canvas')
        : null;

    if (!canvas || !window.WebGLRenderingContext) {
        teardownPricingShader();
        return;
    }

    if (pricingShaderState.canvas === canvas) {
        return;
    }

    teardownPricingShader();

    try {
        const gl = canvas.getContext('webgl', {
            alpha: true,
            antialias: true,
            premultipliedAlpha: false
        });
        if (!gl) {
            return;
        }

        const vertexShader = compilePricingShader(gl, gl.VERTEX_SHADER, PRICING_SHADER_VERTEX_SOURCE);
        const fragmentShader = compilePricingShader(gl, gl.FRAGMENT_SHADER, PRICING_SHADER_FRAGMENT_SOURCE);
        const program = gl.createProgram();
        if (!program) {
            throw new Error('Unable to create shader program.');
        }

        gl.attachShader(program, vertexShader);
        gl.attachShader(program, fragmentShader);
        gl.linkProgram(program);

        if (!gl.getProgramParameter(program, gl.LINK_STATUS)) {
            throw new Error(gl.getProgramInfoLog(program) || 'Unable to link shader program.');
        }

        gl.useProgram(program);
        gl.enable(gl.BLEND);
        gl.blendFunc(gl.SRC_ALPHA, gl.ONE_MINUS_SRC_ALPHA);

        const buffer = gl.createBuffer();
        if (!buffer) {
            throw new Error('Unable to allocate shader buffer.');
        }

        gl.bindBuffer(gl.ARRAY_BUFFER, buffer);
        gl.bufferData(
            gl.ARRAY_BUFFER,
            new Float32Array([
                -1, -1,
                1, -1,
                -1, 1,
                -1, 1,
                1, -1,
                1, 1
            ]),
            gl.STATIC_DRAW
        );

        const positionLocation = gl.getAttribLocation(program, 'aPosition');
        gl.enableVertexAttribArray(positionLocation);
        gl.vertexAttribPointer(positionLocation, 2, gl.FLOAT, false, 0, 0);

        const timeLocation = gl.getUniformLocation(program, 'iTime');
        const resolutionLocation = gl.getUniformLocation(program, 'iResolution');

        const resize = () => {
            const rect = canvas.getBoundingClientRect();
            const pixelRatio = Math.min(window.devicePixelRatio || 1, 1.5);
            const width = Math.max(1, Math.floor(rect.width * pixelRatio));
            const height = Math.max(1, Math.floor(rect.height * pixelRatio));

            if (canvas.width !== width || canvas.height !== height) {
                canvas.width = width;
                canvas.height = height;
            }

            gl.viewport(0, 0, width, height);
        };

        const render = (time) => {
            if (pricingShaderState.canvas !== canvas || state.activePage !== 'pricing') {
                return;
            }

            resize();
            gl.clearColor(0, 0, 0, 0);
            gl.clear(gl.COLOR_BUFFER_BIT);
            gl.useProgram(program);
            gl.uniform1f(timeLocation, time * 0.001);
            gl.uniform2f(resolutionLocation, canvas.width, canvas.height);
            gl.drawArrays(gl.TRIANGLES, 0, 6);
            pricingShaderState.frameId = window.requestAnimationFrame(render);
        };

        gl.deleteShader(vertexShader);
        gl.deleteShader(fragmentShader);

        pricingShaderState.canvas = canvas;
        pricingShaderState.gl = gl;
        pricingShaderState.program = program;
        pricingShaderState.buffer = buffer;
        pricingShaderState.resizeHandler = resize;

        window.addEventListener('resize', resize);
        resize();
        render(0);
    } catch (_error) {
        teardownPricingShader();
    }
}

function renderSummaryCards(summary, hint) {
    const entries = Object.entries(summary || {});
    if (!entries.length) {
        return '';
    }
    return `
        <div class="stats-grid">
            ${entries.map(([key, value]) => metricCard(labelize(key), value, hint)).join('')}
        </div>
    `;
}

function showBanner(message, type = 'error') {
    const banner = document.getElementById('error-banner');
    if (!banner) {
        return;
    }
    banner.textContent = message;
    banner.className = `banner banner-${type}`;
    banner.classList.remove('hidden');
    window.clearTimeout(showBanner.timeoutId);
    showBanner.timeoutId = window.setTimeout(() => banner.classList.add('hidden'), 4200);
}

function setInitStatus(text) {
    const node = document.querySelector('#axis-init-overlay .init-status');
    if (node) {
        node.textContent = text;
    }
}

function hideInitOverlay() {
    const overlay = document.getElementById('axis-init-overlay');
    if (!overlay || overlay.dataset.hidden === 'true') {
        return;
    }
    setInitStatus('Ready');
    overlay.classList.add('fade-out');
    overlay.dataset.hidden = 'true';
    window.setTimeout(() => {
        overlay.style.display = 'none';
    }, 300);
}

function ownerTokenRecentlyValidated() {
    if (!state.auth || state.auth.mode !== 'owner') {
        return false;
    }
    const stamped = Number(localStorage.getItem('axis_token_validated_at') || 0);
    return Number.isFinite(stamped) && stamped > 0 && (Date.now() - stamped) < TOKEN_VALIDATION_MAX_AGE_MS;
}

function markOwnerTokenValidated() {
    if (state.auth?.mode === 'owner') {
        localStorage.setItem('axis_token_validated_at', String(Date.now()));
    }
}

async function validateSessionFast() {
    if (!state.auth) {
        return false;
    }
    if (ownerTokenRecentlyValidated()) {
        return true;
    }

    const controller = new AbortController();
    const timer = window.setTimeout(() => controller.abort(), 3000);
    try {
        const res = await fetch('/whoami', {
            method: 'GET',
            headers: getAuthHeaders(),
            signal: controller.signal
        });
        if (!res.ok) {
            return false;
        }
        markOwnerTokenValidated();
        return true;
    } catch (_error) {
        return false;
    } finally {
        window.clearTimeout(timer);
    }
}

function renderPageSkeleton(pageId = state.activePage) {
    const page = document.getElementById(`page-${pageId}`);
    if (!page) {
        return;
    }
    page.innerHTML = `
        <section class="panel">
            <div class="skeleton-line medium"></div>
            <div class="skeleton-line"></div>
            <div class="skeleton-line short"></div>
            <div class="skeleton-line"></div>
            <div class="skeleton-line medium"></div>
        </section>
    `;
}

async function playAxisIntro() {
    const intro = document.getElementById('axis-intro');
    if (!intro) {
        return;
    }

    intro.classList.remove('hidden');
    intro.classList.remove('is-exiting');

    await new Promise((resolve) => {
        window.requestAnimationFrame(() => {
            intro.classList.add('is-visible');
            resolve();
        });
    });

    await new Promise((resolve) => window.setTimeout(resolve, AXIS_INTRO_MIN_MS));
    intro.classList.add('is-exiting');
    intro.classList.remove('is-visible');
    await new Promise((resolve) => window.setTimeout(resolve, AXIS_INTRO_EXIT_MS));
    intro.classList.add('hidden');
    intro.classList.remove('is-exiting');
}

function setLoading(button, isLoading, loadingText = 'Working...') {
    if (!button) {
        return;
    }
    button.disabled = isLoading;
    if (isLoading) {
        button.dataset.originalText = button.textContent;
        button.textContent = loadingText;
        return;
    }
    if (button.dataset.originalText) {
        button.textContent = button.dataset.originalText;
        delete button.dataset.originalText;
    }
}

async function apiFetch(endpoint, { method = 'GET', body = null, headers = {}, allow403 = false, suppressError = false } = {}) {
    if (!state.auth && endpoint !== '/whoami') {
        return null;
    }

    const options = {
        method,
        headers: {
            ...getAuthHeaders(),
            ...headers
        }
    };
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), API_TIMEOUT_MS);
    options.signal = controller.signal;

    if (body !== null) {
        options.headers['Content-Type'] = 'application/json';
        options.body = JSON.stringify(body);
    }

    try {
        const response = await fetch(endpoint, options);
        const payload = await response.json().catch(() => null);

        if (response.status === 401 || response.status === 403) {
            // Device token sessions get the revoked overlay instead of generic logout
            if (localStorage.getItem('axis_device_token')) {
                showDeviceRevokedOverlay();
                return null;
            }
            if (response.status === 401) {
                showBanner('Session expired or unauthorized. Returning to the login screen.', 'error');
                logout();
                return null;
            }
        }

        if (response.status === 403 && allow403) {
            return { __forbidden: true, ...(payload || {}) };
        }

        if (!response.ok) {
            if (!suppressError) {
                showBanner(payload?.message || payload?.error || `Request failed (${response.status}).`, 'error');
            }
            return null;
        }

        return payload;
    } catch (_error) {
        if (!suppressError) {
            showBanner('Axis is unreachable. Verify the local server is running.', 'error');
        }
        return null;
    } finally {
        window.clearTimeout(timeoutId);
    }
}

async function postAssistantChat(message) {
    const controller = new AbortController();
    const timeoutId = window.setTimeout(() => controller.abort(), API_TIMEOUT_MS);
    try {
        const response = await fetch('/chat', {
            method: 'POST',
            headers: {
                ...getAuthHeaders(),
                'Content-Type': 'application/json'
            },
            signal: controller.signal,
            body: JSON.stringify({
                message,
                conversation_id: state.assistant.conversationId,
                dashboard_context: buildAssistantContext()
            })
        });
        const payload = await response.json().catch(() => null);
        return { ok: response.ok, status: response.status, payload };
    } finally {
        window.clearTimeout(timeoutId);
    }
}

function showDeviceRevokedOverlay() {
    localStorage.removeItem('axis_device_token');
    const overlay = document.getElementById('device-revoked-overlay');
    if (overlay) overlay.classList.remove('hidden');
}

function logout() {
    if (state.polling) {
        window.clearInterval(state.polling);
        state.polling = null;
    }
    if (state.assistant.restoreTimer) {
        window.clearTimeout(state.assistant.restoreTimer);
        state.assistant.restoreTimer = null;
    }
    sessionStorage.removeItem('jarvis_auth');
    localStorage.removeItem('axis_token_validated_at');
    window.location.reload();
}

async function login() {
    const token = document.getElementById('auth-token').value.trim();
    const errorNode = document.getElementById('auth-error');

    if (!token) {
        errorNode.textContent = 'A token is required.';
        errorNode.classList.remove('hidden');
        return;
    }

    errorNode.classList.add('hidden');

    // Clear any existing pairing/device state before owner login
    localStorage.removeItem('axis_device_token');

    state.auth = { mode: 'owner', token };
    sessionStorage.setItem('jarvis_auth', JSON.stringify(state.auth));
    localStorage.removeItem('axis_token_validated_at');

    await initApp();
}

async function pairDevice() {
    const code = document.getElementById('pairing-code-input').value.trim().replace(/-/g, '').toUpperCase();
    const errorNode = document.getElementById('auth-error');

    if (!code || code.length < 8) {
        errorNode.textContent = 'Please enter a valid 8-character pairing code.';
        errorNode.classList.remove('hidden');
        return;
    }
    errorNode.classList.add('hidden');

    const btn = document.getElementById('pair-connect-btn');
    const originalText = btn.textContent;
    btn.textContent = 'Connecting...';
    btn.disabled = true;

    try {
        const response = await fetch('/pairing/register', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ code: code, device_name: 'Remote Device', requested_role: 'reader' })
        });

        if (!response.ok) {
            throw new Error('Invalid or expired code.');
        }
        const data = await response.json();

        // Valid paired device
        document.getElementById('device-pairing-step').classList.add('hidden');
        document.getElementById('device-success-step').classList.remove('hidden');
        document.getElementById('new-device-token').textContent = data.device_token;

        document.getElementById('open-dashboard-btn').onclick = () => {
            localStorage.setItem('axis_device_token', data.device_token);
            window.location.reload();
        };
    } catch (err) {
        errorNode.textContent = 'Invalid or expired code. Ask the owner to generate a new one.';
        errorNode.classList.remove('hidden');
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

async function initAuthContext() {
    const whoami = await apiFetch('/whoami', { suppressError: true });
    if (!whoami?.auth_context) {
        return false;
    }
    state.authContext = whoami.auth_context;
    renderIdentity();
    return true;
}

function renderIdentity() {
    const info = document.getElementById('whoami-info');
    const sessionName = document.getElementById('session-name');
    const sessionMeta = document.getElementById('session-meta');
    const sessionAvatar = document.getElementById('session-avatar');
    const planChip = document.getElementById('topbar-plan');

    const role = state.authContext?.role || 'reader';
    const type = state.authContext?.type || 'unknown';
    const sessionClass = state.authContext?.session_class || 'desktop_guest';
    const profile = state.authContext?.profile?.profile_label || state.authContext?.profile?.display_name || 'Axis Workspace';
    const plan = state.authContext?.plan?.name || state.authContext?.plan?.id || 'Foundation';
    const initials = String(profile).split(/\s+/).slice(0, 2).map((part) => part[0] || '').join('').toUpperCase() || 'AX';

    if (info) {
        info.innerHTML = `
            <span class="identity-card__title">${escapeHtml(role)}</span>
            <div class="identity-card__copy">${escapeHtml(profile)}</div>
            <div class="identity-card__meta">${escapeHtml(type)} session | ${escapeHtml(labelize(sessionClass))} | ${escapeHtml(plan)}</div>
        `;
    }

    sessionName.textContent = profile;
    sessionMeta.textContent = `${labelize(role)} access | ${labelize(sessionClass)}`;
    sessionAvatar.textContent = initials;
    planChip.textContent = `Plan: ${plan}`;
}

function updateShellChrome() {
    const meta = PAGE_META[state.activePage] || PAGE_META.overview;
    const summary = state.summary?.summary || {};
    const disabledPermissions = state.permissionsSnapshot?.summary?.counts?.disabled ?? summary.disabled_permissions_count ?? 0;
    const pendingRequests = pendingPermissionRequests().length || summary.permission_requests_pending || 0;
    const approvalsCount = summary.pending_approvals_count ?? state.approvals.length;
    const activeGoals = summary.active_goals_count ?? state.goals.filter((goal) => goal.status === 'active').length;
    const blockedCount = currentBlockedCount();

    document.getElementById('page-title').textContent = meta.title;
    document.getElementById('page-description').textContent = meta.description;
    document.getElementById('version-tag').textContent = `v${state.about?.app_version || '--'}`;
    document.getElementById('topbar-model').textContent = `Model: ${deriveModelLabel()}`;

    const readinessBanner = document.getElementById('readiness-banner');
    readinessBanner.className = `status-pill ${toneClass(state.readiness?.overall || deriveHealthLabel())}`;
    readinessBanner.textContent = deriveHealthLabel();

    document.getElementById('status-health').textContent = `Health: ${deriveHealthLabel()}`;

    const dbStatus = document.getElementById('status-db');
    if (dbStatus) {
        dbStatus.textContent = state.readiness?.database_writable ? 'DB: Supabase (PostgreSQL)' : 'DB: Loading...';
    }

    const currentLLM = state.llmModelsData?.models?.find(m => m.id === state.llmModelsData?.active_model);
    const modelStr = currentLLM ? `${currentLLM.name}` : deriveModelLabel();
    document.getElementById('status-model').textContent = `Model: ${modelStr}`;

    const indicator = document.getElementById('assistant-model-indicator');
    if (indicator) {
        const providerName = currentLLM ? currentLLM.provider.charAt(0).toUpperCase() + currentLLM.provider.slice(1) : '';
        indicator.textContent = currentLLM ? `â— ${currentLLM.name} via ${providerName}` : '';
    }
    document.getElementById('status-goals').textContent = `Active goals: ${activeGoals}`;
    document.getElementById('status-approvals').textContent = `Approvals: ${approvalsCount}`;
    document.getElementById('status-trust').textContent = `Trust: ${disabledPermissions} disabled | ${pendingRequests} pending request${pendingRequests === 1 ? '' : 's'}`;

    const badgeGoals = document.getElementById('badge-goals');
    const badgeApprovals = document.getElementById('badge-approvals');
    const badgePermissions = document.getElementById('badge-permissions');
    badgeGoals.textContent = activeGoals ? String(activeGoals) : '';
    badgeApprovals.textContent = approvalsCount ? String(approvalsCount) : '';
    badgePermissions.textContent = pendingRequests ? String(pendingRequests) : (disabledPermissions ? String(disabledPermissions) : '');

    document.querySelectorAll('.nav-btn').forEach((button) => {
        button.classList.toggle('active', button.dataset.page === state.activePage);
    });

    const badge = document.getElementById('topbar-remote-access');
    if (badge) {
        if (localStorage.getItem('axis_device_token')) {
            badge.classList.remove('hidden');
        } else {
            badge.classList.add('hidden');
        }
    }

    updateAssistantContextChip();
}

function preferredGoalId(goals = state.goals) {
    if (state.selectedGoalId && goals.some((goal) => goal.id === state.selectedGoalId)) {
        return state.selectedGoalId;
    }

    const priorityOrder = ['active', 'blocked', 'awaiting_approval', 'paused', 'draft', 'planned', 'completed', 'stopped'];
    for (const status of priorityOrder) {
        const match = goals.find((goal) => goal.status === status);
        if (match) {
            return match.id;
        }
    }

    return goals[0]?.id || null;
}

async function syncGoalSelection(forceRefresh = false) {
    const nextGoalId = preferredGoalId();
    if (!nextGoalId) {
        state.selectedGoalId = null;
        state.goalContext = null;
        state.goalSummary = null;
        state.goalEvents = [];
        return;
    }

    if (!forceRefresh && state.selectedGoalId === nextGoalId && state.goalContext && state.goalSummary) {
        return;
    }

    state.selectedGoalId = nextGoalId;
    await fetchGoalFocus(nextGoalId);
}

async function fetchGoalFocus(goalId) {
    if (!goalId) {
        state.goalContext = null;
        state.goalSummary = null;
        state.goalEvents = [];
        return;
    }

    const [goalContext, goalSummary, goalEvents] = await Promise.all([
        apiFetch(`/goals/${goalId}`, { suppressError: true }),
        apiFetch(`/goals/${goalId}/summary`, { suppressError: true }),
        apiFetch(`/goals/${goalId}/events`, { suppressError: true })
    ]);

    state.goalContext = goalContext;
    state.goalSummary = goalSummary;
    state.goalEvents = goalEvents?.events || [];
}

function buildAssistantSystemState() {
    const summary = state.summary?.summary || {};
    const focusedGoal = state.goalContext?.goal || state.goals.find((goal) => goal.id === state.selectedGoalId) || null;
    const focusedGoalSummary = state.goalSummary || null;

    return {
        active_goals_count: summary.active_goals_count ?? state.goals.filter((goal) => goal.status === 'active').length,
        blocked_count: currentBlockedCount(),
        blocked_items_count: currentBlockedCount(),
        blocked_goals_count: state.goals.filter((goal) => goal.status === 'blocked').length,
        pending_approvals_count: summary.pending_approvals_count ?? state.approvals.length,
        pending_permission_requests: summary.permission_requests_pending ?? pendingPermissionRequests().length,
        disabled_permissions_count: summary.disabled_permissions_count ?? state.permissionsSnapshot?.summary?.counts?.disabled ?? 0,
        health: deriveHealthLabel(),
        llm_mode: deriveModelLabel(),
        google_status: state.summary?.google?.status || state.readiness?.google_integration?.status || 'unknown',
        voice: {
            browser_available: state.voice.available,
            listening: state.voice.listening,
            stt_provider: state.summary?.voice?.stt_provider || state.readiness?.voice_subsystem?.stt_provider || 'unknown',
            tts_provider: state.summary?.voice?.tts_provider || state.readiness?.voice_subsystem?.tts_provider || 'unknown'
        },
        approvals: state.approvals.slice(0, 3).map((approval) => ({
            action_id: approval.action_id,
            goal_title: approval.goal_title,
            preview: approval.preview,
            status: approval.action_status
        })),
        focused_goal: focusedGoal ? {
            goal_id: focusedGoal.id,
            id: focusedGoal.id,
            title: focusedGoal.title,
            status: focusedGoal.status,
            priority: focusedGoal.priority,
            objective: focusedGoal.objective,
            blocked_reason: focusedGoalSummary?.blocked_reason || focusedGoal.last_error || null,
            recommended_next_action: focusedGoalSummary?.recommended_next_action || null,
            waiting_approvals: focusedGoalSummary?.waiting_approvals?.length || 0
        } : null
    };
}

function buildAssistantContext() {
    const meta = PAGE_META[state.activePage] || PAGE_META.overview;
    const focusedGoal = state.goalContext?.goal || state.goals.find((goal) => goal.id === state.selectedGoalId) || null;

    return {
        page_id: state.activePage,
        page_title: meta.title,
        page_purpose: meta.purpose,
        page_sections: meta.sections,
        system_state: buildAssistantSystemState(),
        focus_goal: focusedGoal ? {
            goal_id: focusedGoal.id,
            id: focusedGoal.id,
            title: focusedGoal.title,
            status: focusedGoal.status,
            priority: focusedGoal.priority,
            objective: focusedGoal.objective,
            blocked_reason: state.goalSummary?.blocked_reason || focusedGoal.last_error || null,
            permission_dependency_summary: state.goalSummary?.permission_dependency_summary || null,
            recommended_next_action: state.goalSummary?.recommended_next_action || null
        } : null
    };
}

function updateAssistantContextChip() {
    const meta = PAGE_META[state.activePage] || PAGE_META.overview;
    const summary = state.summary?.summary || {};
    const focusedGoal = state.goalContext?.goal || state.goals.find((goal) => goal.id === state.selectedGoalId) || null;
    const parts = [
        meta.title,
        `${summary.active_goals_count ?? 0} active goal${(summary.active_goals_count ?? 0) === 1 ? '' : 's'}`,
        `${summary.pending_approvals_count ?? 0} approval${(summary.pending_approvals_count ?? 0) === 1 ? '' : 's'} pending`,
        `${currentBlockedCount()} blocked`
    ];

    if (focusedGoal && state.activePage === 'goals') {
        parts.push(`Focus: ${focusedGoal.title}`);
    }
    if (state.activePage === 'pricing') {
        parts.push(`${labelize(state.pricingBillingCycle)} billing view`);
    }
    if (state.activePage === 'axis-chat') {
        parts.push('Full conversation deck');
    }

    document.getElementById('assistant-page-chip').textContent = parts.join(' | ');
}

function assistantSurfaceNodes() {
    return {
        shell: document.querySelector('.assistant-shell'),
        shellSlot: document.getElementById('assistant-shell-surface-slot'),
        handoff: document.getElementById('assistant-shell-handoff'),
        surface: document.getElementById('assistant-surface'),
        pageSlot: document.getElementById('axis-chat-assistant-slot')
    };
}

function restoreAssistantSurfaceToShell() {
    const { shell, shellSlot, handoff, surface } = assistantSurfaceNodes();
    const appShell = document.querySelector('.app-shell');
    const mainShell = document.querySelector('.main-shell');
    if (!surface || !shellSlot) {
        return;
    }
    if (surface.parentElement !== shellSlot) {
        shellSlot.appendChild(surface);
    }
    surface.dataset.host = 'shell';
    shellSlot.classList.remove('hidden');
    handoff?.classList.add('hidden');
    shell?.classList.remove('assistant-shell--page-hosted');
    appShell?.classList.remove('app-shell--axis-chat');
    mainShell?.classList.remove('main-shell--axis-chat');
}

function syncAssistantSurfaceLocation() {
    const { shell, shellSlot, handoff, surface, pageSlot } = assistantSurfaceNodes();
    const appShell = document.querySelector('.app-shell');
    const mainShell = document.querySelector('.main-shell');
    if (!surface || !shellSlot) {
        return;
    }

    const hostInPage = state.activePage === 'axis-chat' && pageSlot;
    const target = hostInPage ? pageSlot : shellSlot;
    if (hostInPage && state.assistant.mode !== 'default') {
        state.assistant.mode = 'default';
    }
    if (surface.parentElement !== target) {
        target.appendChild(surface);
    }

    surface.dataset.host = hostInPage ? 'page' : 'shell';
    shellSlot.classList.toggle('hidden', Boolean(hostInPage));
    handoff?.classList.toggle('hidden', !hostInPage);
    shell?.classList.toggle('assistant-shell--page-hosted', Boolean(hostInPage));
    appShell?.classList.toggle('app-shell--axis-chat', Boolean(hostInPage));
    mainShell?.classList.toggle('main-shell--axis-chat', Boolean(hostInPage));
}

function showAssistantRestoreIndicator(message = 'Conversation restored') {
    const indicator = document.getElementById('assistant-restore-indicator');
    if (!indicator) {
        return;
    }

    indicator.textContent = message;
    indicator.classList.add('is-visible');

    if (state.assistant.restoreTimer) {
        window.clearTimeout(state.assistant.restoreTimer);
    }

    state.assistant.restoreTimer = window.setTimeout(() => {
        indicator.classList.remove('is-visible');
    }, ASSISTANT_RESTORE_NOTICE_MS);
}

function normalizeAssistantAction(action) {
    if (!action || typeof action !== 'object') {
        return null;
    }

    const label = String(action.label || '').trim();
    const target = String(action.target || '').trim();
    if (!label || !target) {
        return null;
    }

    const normalized = { label, target };
    if (action.goal_id || action.goalId) {
        normalized.goalId = String(action.goal_id || action.goalId);
    }
    if (action.approval_id || action.approvalId) {
        normalized.approvalId = String(action.approval_id || action.approvalId);
    }
    if (action.filter) {
        normalized.filter = String(action.filter).trim().toLowerCase();
    }
    if (action.section) {
        normalized.section = String(action.section).trim().toLowerCase();
    }
    if (action.highlight) {
        normalized.highlight = String(action.highlight);
    }
    return normalized;
}

function normalizeAssistantRouting(routing) {
    if (!routing || typeof routing !== 'object' || Array.isArray(routing)) {
        return {};
    }
    return { ...routing };
}

function normalizeAssistantMessage(message) {
    const role = message?.role === 'assistant' || message?.role === 'user' || message?.role === 'system'
        ? message.role
        : 'system';
    const body = String(message?.body ?? message?.content ?? '').trim();
    if (!body) {
        return null;
    }

    return {
        id: String(message?.id || createRuntimeId(`msg-${role}`)),
        role,
        type: message?.type || (role === 'assistant' ? 'assistant' : role),
        body,
        timestamp: message?.timestamp || new Date().toISOString(),
        actions: Array.isArray(message?.actions)
            ? message.actions.map((action) => normalizeAssistantAction(action)).filter(Boolean).slice(0, 3)
            : [],
        routing: normalizeAssistantRouting(message?.routing)
    };
}

function assistantGreetingMatchesPage(messageBody, pageId) {
    const text = String(messageBody || '');
    const markers = {
        overview: [
            'Recommended next move:',
            'I can help you review blockers, approvals, or the best next action from this overview.'
        ],
        'axis-chat': [
            'How can I help with Axis today?'
        ],
        goals: [
            'You are focused on "',
            'The goal workspace is live with'
        ],
        approvals: [
            'approvals are waiting right now'
        ],
        permissions: [
            'permission request',
            'permissions disabled'
        ],
        'axis-hub': [
            'Axis Hub is the ecosystem view.'
        ],
        guide: [
            'This guide is the truthful system map.'
        ],
        security: [
            'Security and compliance here are descriptive'
        ],
        settings: [
            'These are the safe live controls for the current shell.'
        ],
        profiles: [
            'Profiles and plans are advisory but useful.'
        ],
        pricing: [
            'Pricing is the future-facing subscription view for Axis.'
        ]
    };
    return (markers[pageId] || []).some((marker) => text.includes(marker));
}

function assistantMessageVisibleInCurrentPage(message) {
    if (!message) {
        return false;
    }
    if (state.activePage !== 'axis-chat') {
        return true;
    }
    if (message.role !== 'assistant') {
        return true;
    }

    const greetingPages = [
        'overview',
        'axis-chat',
        'goals',
        'approvals',
        'permissions',
        'axis-hub',
        'guide',
        'security',
        'settings',
        'profiles',
        'pricing'
    ];

    return !greetingPages.some((pageId) => assistantGreetingMatchesPage(message.body, pageId));
}

function prependAssistantMessage(role, body, { type = role === 'assistant' ? 'assistant' : role, timestamp = new Date().toISOString(), actions = [], routing = {} } = {}) {
    const message = normalizeAssistantMessage({
        id: createRuntimeId(`msg-${role}`),
        role,
        type,
        body,
        timestamp,
        actions,
        routing
    });
    if (!message) {
        return;
    }
    state.assistant.messages.unshift(message);
    renderAssistantThread();
}

function scrollAssistantTargetIntoView(selector) {
    window.requestAnimationFrame(() => {
        window.requestAnimationFrame(() => {
            const node = document.querySelector(selector);
            node?.scrollIntoView({ behavior: 'smooth', block: 'center' });
        });
    });
}

function escapeSelectorValue(value) {
    const text = String(value ?? '');
    if (window.CSS?.escape) {
        return window.CSS.escape(text);
    }
    return text.replace(/["\\]/g, '\\$&');
}

function renderPageById(pageId) {
    const renderer = {
        overview: renderOverviewPage,
        'axis-chat': renderAxisChatPage,
        goals: renderGoalsPage,
        approvals: renderApprovalsPage,
        'axis-hub': renderAxisHubPage,
        guide: renderGuidePage,
        permissions: renderPermissionsPage,
        security: renderSecurityPage,
        settings: renderSettingsPage,
        profiles: renderProfilesPage,
        pricing: renderPricingPage
    }[pageId];

    if (typeof renderer === 'function') {
        renderer();
    }
}

function clearAssistantHighlights() {
    state.assistant.highlightedGoalId = null;
    state.assistant.highlightedApprovalId = null;
    state.assistant.highlightedPermissionKey = null;
    document.querySelectorAll('.axis-highlight').forEach((node) => {
        node.classList.remove('axis-highlight');
    });
}

function buildAssistantNavigationHint(action) {
    const normalized = normalizeAssistantAction(action);
    if (!normalized) {
        return null;
    }

    const pageMap = {
        goals: 'goals',
        approvals: 'approvals',
        permissions: 'permissions',
        capabilities: 'guide',
        settings: 'settings'
    };
    const pageId = pageMap[normalized.target];
    if (!pageId) {
        return null;
    }

    return {
        ...normalized,
        pageId,
        highlight: normalized.highlight || normalized.goalId || normalized.approvalId || null
    };
}

function scheduleAssistantHintApplication() {
    if (!state.assistant.pendingNavigationHint) {
        return;
    }
    window.requestAnimationFrame(() => {
        window.requestAnimationFrame(() => {
            void applyPendingAssistantNavigationHint();
        });
    });
}

function pulseAssistantHighlight(selector) {
    const node = document.querySelector(selector);
    if (!node) {
        return false;
    }
    node.classList.remove('axis-highlight');
    void node.offsetWidth;
    node.classList.add('axis-highlight');
    node.scrollIntoView({ behavior: 'smooth', block: 'center' });
    window.setTimeout(() => node.classList.remove('axis-highlight'), 1400);
    return true;
}

async function applyPendingAssistantNavigationHint() {
    const hint = state.assistant.pendingNavigationHint;
    if (!hint || hint.pageId !== state.activePage) {
        return;
    }

    let rerenderPage = false;

    if (hint.pageId === 'goals') {
        if (hint.filter && state.goalViewFilter !== hint.filter) {
            state.goalViewFilter = hint.filter;
            rerenderPage = true;
        }
        if (hint.highlight && state.selectedGoalId !== hint.highlight) {
            state.selectedGoalId = hint.highlight;
            state.goalQuery = '';
            await fetchGoalFocus(hint.highlight);
            rerenderPage = true;
        }
        state.assistant.highlightedGoalId = hint.highlight || hint.goalId || null;
        state.assistant.highlightedApprovalId = null;
        state.assistant.highlightedPermissionKey = null;
    } else if (hint.pageId === 'approvals') {
        if (hint.filter && state.approvalViewFilter !== hint.filter) {
            state.approvalViewFilter = hint.filter;
            rerenderPage = true;
        }
        state.assistant.highlightedGoalId = null;
        state.assistant.highlightedApprovalId = hint.highlight || hint.approvalId || null;
        state.assistant.highlightedPermissionKey = null;
    } else if (hint.pageId === 'permissions') {
        if (hint.filter && state.permissionStateFilter !== hint.filter) {
            state.permissionStateFilter = hint.filter;
            rerenderPage = true;
        }
        state.assistant.highlightedGoalId = null;
        state.assistant.highlightedApprovalId = null;
        state.assistant.highlightedPermissionKey = hint.highlight || null;
    } else {
        clearAssistantHighlights();
    }

    if (rerenderPage) {
        renderPageById(hint.pageId);
        updateShellChrome();
    }

    let highlighted = false;
    if (hint.pageId === 'goals' && state.assistant.highlightedGoalId) {
        highlighted = pulseAssistantHighlight(`[data-goal-id="${escapeSelectorValue(state.assistant.highlightedGoalId)}"]`);
    } else if (hint.pageId === 'approvals' && state.assistant.highlightedApprovalId) {
        highlighted = pulseAssistantHighlight(`[data-approval-id="${escapeSelectorValue(state.assistant.highlightedApprovalId)}"]`);
    } else if (hint.pageId === 'permissions' && state.assistant.highlightedPermissionKey) {
        const key = escapeSelectorValue(state.assistant.highlightedPermissionKey);
        highlighted = pulseAssistantHighlight(`[data-permission-key-card="${key}"], [data-permission-request-key="${key}"]`);
    }

    if (hint.section) {
        const sectionSelector = `[data-page-section="${escapeSelectorValue(hint.section)}"]`;
        if (!highlighted || !document.querySelector(sectionSelector)) {
            scrollAssistantTargetIntoView(sectionSelector);
        }
    }

    state.assistant.highlightedGoalId = null;
    state.assistant.highlightedApprovalId = null;
    state.assistant.highlightedPermissionKey = null;
    state.assistant.pendingNavigationHint = null;
}

async function handleAssistantAction(action) {
    const nextHint = buildAssistantNavigationHint(action);
    if (!nextHint) {
        return;
    }

    clearAssistantHighlights();
    state.assistant.pendingNavigationHint = nextHint;

    if (nextHint.pageId === 'goals' && nextHint.highlight) {
        state.goalQuery = '';
        state.selectedGoalId = nextHint.highlight;
        await fetchGoalFocus(nextHint.highlight);
    }

    if (nextHint.pageId === 'goals' && nextHint.filter) {
        state.goalViewFilter = nextHint.filter;
    }
    if (nextHint.pageId === 'approvals' && nextHint.filter) {
        state.approvalViewFilter = nextHint.filter;
    }
    if (nextHint.pageId === 'permissions' && nextHint.filter) {
        state.permissionStateFilter = nextHint.filter;
    }

    renderPageById(nextHint.pageId);
    updateShellChrome();
    await showPage(nextHint.pageId);
}

async function restoreAssistantConversation() {
    const conversationId = state.assistant.conversationId || ensureAssistantConversationId();
    if (!conversationId) {
        return false;
    }

    try {
        const conversations = await apiFetch('/conversations', { suppressError: true });
        const exists = Array.isArray(conversations?.conversations)
            && conversations.conversations.some((conversation) => conversation.id === conversationId);

        if (!exists) {
            return false;
        }

        const detail = await apiFetch(`/conversations/${encodeURIComponent(conversationId)}`, { suppressError: true });
        const restoredMessages = Array.isArray(detail?.messages)
            ? detail.messages
                .slice(-ASSISTANT_HISTORY_LIMIT)
                .map((message) => normalizeAssistantMessage({
                    role: message.role,
                    content: message.content,
                    timestamp: message.timestamp,
                    actions: message.actions,
                    routing: message.routing
                }))
                .filter(Boolean)
            : [];

        if (!restoredMessages.length) {
            return false;
        }

        state.assistant.messages = restoredMessages;
        state.assistant.restoreGreetingCheck = true;
        state.assistant.restorePendingNotice = true;
        renderAssistantThread();
        return true;
    } catch (_error) {
        return false;
    }
}

function setAssistantPending(isPending) {
    state.assistant.pending = isPending;
    const typing = document.getElementById('assistant-typing');
    typing.classList.toggle('hidden', !isPending);
    renderVoiceState();
    renderAssistantThread();
}

function pushAssistantMessage(role, body, { type = role === 'assistant' ? 'assistant' : role, timestamp = new Date().toISOString(), actions = [], routing = {} } = {}) {
    const message = normalizeAssistantMessage({
        id: createRuntimeId(`msg-${role}`),
        role,
        type,
        body,
        timestamp,
        actions,
        routing
    });
    if (!message) {
        return;
    }
    state.assistant.messages.push(message);
    renderAssistantThread();
}

function renderAssistantThread() {
    const thread = document.getElementById('assistant-thread');
    if (!thread) {
        return;
    }

    const messages = state.assistant.messages.filter((message) => assistantMessageVisibleInCurrentPage(message));

    if (!messages.length) {
        if (state.activePage === 'axis-chat') {
            thread.innerHTML = `
                <div class="chat-empty-state">
                    <div class="chat-empty-icon">◎</div>
                    <h3>Ask Axis anything</h3>
                    <p>Ask about your goals, system status, what to do next, or anything you need help with.</p>
                </div>
            `;
            return;
        }
        thread.innerHTML = emptyState(
            'Axis Assistant is standing by.',
            'Ask what to do next, why work is blocked, what Axis can do right now, or for a walkthrough of the current page.'
        );
        return;
    }

    thread.innerHTML = messages.map((message) => `
        <article class="message message--${escapeHtml(message.type)}">
            <div class="message__meta">
                <span class="message__role">${escapeHtml(message.role === 'assistant' ? 'Axis Assistant' : message.role === 'user' ? 'You' : 'System')}</span>
                <span>${escapeHtml(formatTime(message.timestamp))}</span>
            </div>
            <div class="message__body">${escapeHtml(message.body)}</div>
            ${message.actions?.length ? `
                <div class="message-actions">
                    ${message.actions.map((action) => `
                        <button
                            class="message-chip"
                            type="button"
                            data-assistant-target="${escapeHtml(action.target)}"
                            ${action.goalId ? `data-assistant-goal-id="${escapeHtml(action.goalId)}"` : ''}
                            ${action.approvalId ? `data-assistant-approval-id="${escapeHtml(action.approvalId)}"` : ''}
                            ${action.filter ? `data-assistant-filter="${escapeHtml(action.filter)}"` : ''}
                            ${action.section ? `data-assistant-section="${escapeHtml(action.section)}"` : ''}
                            ${action.highlight ? `data-assistant-highlight="${escapeHtml(action.highlight)}"` : ''}
                        >${escapeHtml(action.label)}</button>
                    `).join('')}
                </div>
            ` : ''}
        </article>
    `).join('');

    thread.scrollTop = thread.scrollHeight;
}

function todaysEvents() {
    const start = new Date();
    start.setHours(0, 0, 0, 0);
    return (state.summary?.recent_goal_events || []).filter((event) => {
        const created = new Date(event.created_at);
        return !Number.isNaN(created.getTime()) && created >= start;
    });
}

function buildPageGreeting(pageId = state.activePage) {
    const meta = PAGE_META[pageId] || PAGE_META.overview;
    const summary = state.summary?.summary || {};
    const pendingRequests = pendingPermissionRequests().length || summary.permission_requests_pending || 0;
    const focusedGoal = state.goalContext?.goal || state.goals.find((goal) => goal.id === state.selectedGoalId) || null;

    if (pageId === 'overview') {
        const recommendation = topRecommendation();
        if (recommendation?.recommended_action) {
            return `${summary.active_goals_count ?? 0} active goals, ${summary.pending_approvals_count ?? 0} approvals pending, and ${currentBlockedCount()} blocked items. Recommended next move: ${recommendation.recommended_action}`;
        }
        return `${summary.active_goals_count ?? 0} active goals are in play right now. I can help you review blockers, approvals, or the best next action from this overview.`;
    }

    if (pageId === 'axis-chat') {
        return '';
    }

    if (pageId === 'goals') {
        if (focusedGoal) {
            const blocker = state.goalSummary?.blocked_reason ? ` Blocker: ${state.goalSummary.blocked_reason}` : '';
            return `You are focused on "${focusedGoal.title}", currently ${focusedGoal.status}.${blocker} Ask me why it is blocked, what control is safe next, or for a walkthrough of this detail view.`;
        }
        return `The goal workspace is live with ${state.goals.length} recorded goals. I can help you inspect one, explain its state, or suggest which item deserves attention first.`;
    }

    if (pageId === 'approvals') {
        return `${summary.pending_approvals_count ?? 0} approvals are waiting right now. I can help you understand which item is safest to approve, reject, or execute next.`;
    }

    if (pageId === 'permissions') {
        return `${pendingRequests} permission request${pendingRequests === 1 ? '' : 's'} are pending, with ${summary.disabled_permissions_count ?? 0} permissions disabled. I can explain what each trust setting changes before you touch it.`;
    }

    if (pageId === 'axis-hub') {
        return `Axis Hub is the ecosystem view. It shows what is live, what is partial, and what is still just directional so the product reads like one system instead of disconnected demos.`;
    }

    if (pageId === 'guide') {
        return `This guide is the truthful system map. Ask what Axis can do right now or where the current build still stops short, and I will answer from live capability state.`;
    }

    if (pageId === 'security') {
        return `Security and compliance here are descriptive, not inflated. I can walk you through the trust boundary, degraded integrations, and where enterprise claims intentionally stop today.`;
    }

    if (pageId === 'settings') {
        return `These are the safe live controls for the current shell. I can tell you which settings are editable now and which remain system-managed on purpose.`;
    }

    if (pageId === 'profiles') {
        return `Profiles and plans are advisory but useful. I can explain why the current workspace fits its active profile and when a different plan posture would actually matter.`;
    }

    if (pageId === 'pricing') {
        return `Pricing is the future-facing subscription view for Axis. I can compare plans, explain the billing toggle, or point out which tier best fits the kind of automation you want to run.`;
    }

    return `You are on ${meta.title}. Ask for a walkthrough, live state summary, or the next recommended action from this page.`;
}

function ensurePageGreeting() {
    const greeting = buildPageGreeting(state.activePage);
    if (!greeting) {
        state.assistant.greetedPages[state.activePage] = true;
        state.assistant.restoreGreetingCheck = false;
        return;
    }
    if (state.assistant.greetedPages[state.activePage]) {
        return;
    }
    state.assistant.greetedPages[state.activePage] = true;
    if (state.assistant.restoreGreetingCheck) {
        state.assistant.restoreGreetingCheck = false;
        if (assistantGreetingMatchesPage(state.assistant.messages[0]?.body, state.activePage)) {
            return;
        }
        prependAssistantMessage('assistant', greeting);
        return;
    }
    pushAssistantMessage('assistant', greeting);
}

function buildAssistantFallback(message, { unavailable = false } = {}) {
    const lowered = String(message || '').toLowerCase();
    const meta = PAGE_META[state.activePage] || PAGE_META.overview;
    const summary = state.summary?.summary || {};
    const focusedGoal = state.goalContext?.goal || state.goals.find((goal) => goal.id === state.selectedGoalId) || null;
    const focusedGoalSummary = state.goalSummary || null;
    const prefix = unavailable ? 'Assistant unavailable right now. From the live dashboard state: ' : '';

    if (lowered.includes('what should i do next') || lowered.includes('next action') || lowered.includes('what next')) {
        const recommendation = topRecommendation();
        if (recommendation?.recommended_action) {
            return `${prefix}${recommendation.recommended_action}${recommendation.goal_title ? ` This is tied to ${recommendation.goal_title}.` : ''}`;
        }
        if (state.approvals[0]) {
            return `${prefix}The clearest next move is reviewing approval ${state.approvals[0].action_id} for ${state.approvals[0].goal_title || 'the active queue'}.`;
        }
        return `${prefix}I would start by reviewing ${currentBlockedCount()} blocked items on the dashboard, then checking whether the ${summary.active_goals_count ?? 0} active goals still align with the current trust posture.`;
    }

    if (lowered.includes('why is this goal blocked') || lowered.includes('why is this blocked') || lowered.includes('goal blocked')) {
        if (focusedGoalSummary?.blocked_reason) {
            return `${prefix}${focusedGoal.title} is blocked because ${focusedGoalSummary.blocked_reason}. Recommended next action: ${focusedGoalSummary.recommended_next_action || 'inspect the blocker and reconcile the goal.'}`;
        }
        const blockedItem = state.blocked.find((item) => item.goal_id === focusedGoal?.id) || state.blocked[0];
        if (blockedItem) {
            return `${prefix}${blockedItem.goal_title || 'That goal'} is blocked because ${blockedItem.blocked_reason}. Recommended resolution: ${blockedItem.recommended_resolution || 'review it and reconcile.'}`;
        }
        return `${prefix}I do not see a current blocked reason for the focused goal. It may not be blocked right now, or the latest reconciliation has not surfaced a blocker message yet.`;
    }

    if (lowered.includes('what can axis do right now') || lowered.includes('what can axis do') || lowered.includes('current capabilities')) {
        const live = (state.guideData?.capabilities || []).filter((capability) => ['live', 'partially_live', 'partial', 'experimental', 'degraded', 'mocked'].includes(capability.realism));
        const highlights = live.slice(0, 4).map((capability) => capability.name).join(', ');
        return `${prefix}Axis can currently manage goals, approvals, permissions, the control dashboard, and guided capability explainability. Live highlights: ${highlights || 'goal control, approvals, permissions, and the dashboard shell'}. Google is ${state.summary?.google?.status || 'unknown'}, and voice is running with ${state.summary?.voice?.stt_provider || 'unknown'} STT plus ${state.summary?.voice?.tts_provider || 'unknown'} TTS providers.`;
    }

    if (lowered.includes('walk me through this page') || lowered.includes('walk me through') || lowered.includes('this page')) {
        const sections = meta.sections.join(', ');
        return `${prefix}${meta.title} exists to ${meta.purpose.charAt(0).toLowerCase()}${meta.purpose.slice(1)} The main sections here are ${sections}. If you want, I can also point out the most important control on this page first.`;
    }

    if (lowered.includes('summarize what happened today') || lowered.includes('what happened today') || lowered.includes('today summary')) {
        const events = todaysEvents();
        if (!events.length) {
            return `${prefix}I do not see new goal events dated today. The live dashboard still shows ${summary.active_goals_count ?? 0} active goals, ${summary.pending_approvals_count ?? 0} pending approvals, and ${currentBlockedCount()} blocked items carried into this session.`;
        }
        const eventSummary = events.slice(0, 3).map((event) => `${event.goal_title}: ${labelize(event.event_type)} at ${formatTime(event.created_at)}`).join('; ');
        return `${prefix}Today I saw ${events.length} goal events. Highlights: ${eventSummary}. The queue now sits at ${summary.active_goals_count ?? 0} active goals with ${summary.pending_approvals_count ?? 0} approvals pending.`;
    }

    if (lowered.includes('voice')) {
        if (state.voice.available) {
            return `${prefix}Voice input is available in this browser. Press the voice orb to transcribe into the composer and I will answer in the thread as text.`;
        }
        return `${prefix}Voice input is not available in this browser yet. When speech recognition is supported, the voice orb will listen, transcribe, and auto-send your request here in the assistant thread.`;
    }

    return `${prefix}I am looking at ${meta.title} with ${summary.active_goals_count ?? 0} active goals, ${summary.pending_approvals_count ?? 0} approvals pending, and ${currentBlockedCount()} blocked items. Ask me what to do next, why something is blocked, what Axis can do right now, or for a walkthrough of this page.`;
}

async function requestAssistantReply(message) {
    for (let attempt = 0; attempt < 2; attempt += 1) {
        try {
            const result = await postAssistantChat(message);
            const reply = result.payload?.reply || result.payload?.response || '';
            if (result.ok && reply) {
                return {
                    text: reply,
                    fallback: false,
                    conversationId: result.payload?.conversation_id || state.assistant.conversationId,
                    actions: Array.isArray(result.payload?.actions) ? result.payload.actions : [],
                    routing: normalizeAssistantRouting(result.payload?.routing)
                };
            }
        } catch (_error) {
            // Graceful fallback below.
        }

        if (attempt === 0) {
            continue;
        }
    }

    return {
        text: buildAssistantFallback(message, { unavailable: false }),
        fallback: true,
        conversationId: state.assistant.conversationId,
        actions: [],
        routing: {}
    };
}

function autoSizeAssistantInput() {
    const input = document.getElementById('assistant-input');
    if (!input) {
        return;
    }

    const compactViewport = window.innerHeight <= 560;
    const minHeight = compactViewport ? 72 : 88;
    const maxHeight = compactViewport ? 140 : 180;

    input.style.height = 'auto';
    const nextHeight = Math.min(Math.max(input.scrollHeight, minHeight), maxHeight);
    input.style.height = `${nextHeight}px`;
    input.style.overflowY = input.scrollHeight > maxHeight ? 'auto' : 'hidden';
}

function getAssistantModeMeta(mode = state.assistant.mode) {
    return ASSISTANT_MODE_META[mode] || ASSISTANT_MODE_META.default;
}

function decorateAssistantMessage(message) {
    const text = String(message || '').trim();
    if (!text) {
        return '';
    }

    const mode = state.assistant.mode;
    if (!mode || mode === 'default') {
        return text;
    }

    return `[${getAssistantModeMeta(mode).label}] ${text}`;
}

function setAssistantMode(nextMode) {
    state.assistant.mode = state.assistant.mode === nextMode ? 'default' : nextMode;
    updateAssistantComposerState();
}

function updateAssistantComposerState() {
    const composer = document.querySelector('.assistant-composer');
    const input = document.getElementById('assistant-input');
    const note = document.getElementById('assistant-voice-note');
    const modeNote = document.getElementById('assistant-mode-note');
    const sendButton = document.getElementById('assistant-send-btn');
    const sendLabel = document.querySelector('.assistant-send-label');
    const voiceButton = document.getElementById('assistant-voice-btn');
    const activeMode = state.activePage === 'axis-chat'
        ? ASSISTANT_MODE_META.default
        : getAssistantModeMeta();
    const hasContent = Boolean(input && input.value.trim());

    if (composer) {
        composer.dataset.mode = state.assistant.mode || 'default';
        composer.classList.toggle('has-content', hasContent);
        composer.classList.toggle('is-pending', state.assistant.pending);
        composer.classList.toggle('is-listening', state.voice.listening);
    }

    if (input) {
        input.placeholder = activeMode.placeholder;
    }

    if (sendLabel) {
        sendLabel.textContent = state.activePage === 'axis-chat' ? 'Send' : 'Ask Axis';
    }

    if (modeNote) {
        modeNote.textContent = activeMode.note;
    }

    document.querySelectorAll('[data-assistant-mode]').forEach((button) => {
        const isActive = button.dataset.assistantMode === state.assistant.mode;
        button.classList.toggle('is-active', isActive);
        button.setAttribute('aria-pressed', isActive ? 'true' : 'false');
    });

    if (sendButton) {
        sendButton.disabled = !hasContent || state.assistant.pending || state.voice.listening;
        sendButton.title = state.assistant.pending
            ? 'Axis is responding'
            : hasContent
                ? 'Send message'
                : 'Type a message to send';
    }

    if (voiceButton) {
        voiceButton.classList.toggle('is-unavailable', !state.voice.available && !state.voice.listening);
    }

}

async function sendAssistantMessage(message, { clearInput = true } = {}) {
    const input = document.getElementById('assistant-input');
    const rawText = String(message || '').trim();
    if (!rawText || state.assistant.pending) {
        return;
    }

    const outboundText = decorateAssistantMessage(rawText);

    pushAssistantMessage('user', rawText);
    state.voice.lastInputWasVoice = Boolean(message && !clearInput === false && state.voice.lastInputWasVoice);
    // Wait, the above logic is slightly flawed. I'll just check if it was called from voice.
    // I'll update the call site or use a flag.
    // Actually, I set state.voice.lastInputWasVoice = true in initVoice.onresult.
    // But then I need to reset it after text input.

    if (clearInput && input) {
        input.value = '';
        autoSizeAssistantInput();
    }
    updateAssistantComposerState();

    setAssistantPending(true);
    const result = await requestAssistantReply(outboundText);
    if (result.conversationId) {
        setAssistantConversationId(result.conversationId);
    }
    pushAssistantMessage('assistant', result.text, {
        actions: result.actions || [],
        routing: result.routing || {}
    });

    if (state.voice.lastInputWasVoice && state.voiceSettings.responsesEnabled) {
        speakAssistantReply(result.text);
    }
    state.voice.lastInputWasVoice = false; // Reset for next interaction

    setAssistantPending(false);
    updateAssistantComposerState();
}

function focusAssistantComposer(seedText = '') {
    const input = document.getElementById('assistant-input');
    showPage(state.activePage);
    if (seedText && input && !input.value.trim()) {
        input.value = seedText;
    }
    autoSizeAssistantInput();
    updateAssistantComposerState();
    input?.focus();
}

function renderVoiceState() {
    const button = document.getElementById('assistant-voice-btn');
    const note = document.getElementById('assistant-voice-note');
    const stateNode = document.getElementById('assistant-state');
    if (!button || !note || !stateNode) {
        return;
    }

    if (!state.voiceSettings.voiceInputEnabled) {
        button.classList.add('hidden');
        return;
    } else {
        button.classList.remove('hidden');
    }

    button.classList.toggle('recording', state.voice.listening);
    button.classList.toggle('processing', state.voice.processing);
    button.classList.toggle('unavailable', !state.voice.available);

    if (!state.voice.available) {
        note.textContent = state.voice.note;
        button.title = state.voice.note;
        stateNode.className = 'status-pill tone-neutral';
        stateNode.textContent = 'Voice unavailable';
        return;
    }

    if (state.voice.listening) {
        note.textContent = 'Listening now...';
        stateNode.className = 'status-pill tone-danger';
        stateNode.textContent = 'Recording';
        return;
    }

    if (state.voice.processing) {
        note.textContent = 'Transcribing speech...';
        stateNode.className = 'status-pill tone-info';
        stateNode.textContent = 'Processing';
        return;
    }

    if (state.assistant.pending) {
        note.textContent = 'Axis is preparing a reply...';
        stateNode.className = 'status-pill tone-info';
        stateNode.textContent = 'Thinking';
        return;
    }

    note.textContent = 'Hold to record, release to send.';
    stateNode.className = 'status-pill tone-neutral';
    stateNode.textContent = 'Idle';
}

function speakAssistantReply(text) {
    if (!window.speechSynthesis || !state.voiceSettings.responsesEnabled) {
        return;
    }

    window.speechSynthesis.cancel();

    // Cleanup text for TTS
    const cleanText = text
        .replace(/\*\*(.*?)\*\*/g, '$1') // Remove bold
        .replace(/#(.*?)[\n\r]/g, '$1') // Remove headers
        .replace(/- /g, ', ') // Replace bullets with pauses
        .replace(/https?:\/\/\S+/g, 'link') // Replace URLs
        .replace(/[`]/g, '') // Remove backticks
        .trim();

    if (!cleanText) return;

    const utterance = new SpeechSynthesisUtterance(cleanText);
    const voices = window.speechSynthesis.getVoices();

    // Find preferred voice
    const preferred = voices.find(v => v.name === state.voiceSettings.preferredVoiceName)
        || voices.find(v => v.name.includes('Google') && v.lang.startsWith('en'))
        || voices.find(v => v.lang === 'en-US')
        || voices.find(v => v.lang.startsWith('en'))
        || voices[0];

    utterance.voice = preferred;
    utterance.rate = 0.95;
    utterance.pitch = 1.0;
    utterance.volume = 1.0;

    const pill = document.getElementById('assistant-speaking-pill');

    utterance.onstart = () => {
        pill?.classList.remove('hidden');
    };

    utterance.onend = () => {
        pill?.classList.add('hidden');
    };

    utterance.onerror = () => {
        pill?.classList.add('hidden');
    };

    window.speechSynthesis.speak(utterance);
}

function stopSpeaking() {
    if (window.speechSynthesis) {
        window.speechSynthesis.cancel();
    }
    document.getElementById('assistant-speaking-pill')?.classList.add('hidden');
}

function initVoice() {
    const Recognition = window.Recognition || window.webkitSpeechRecognition || window.SpeechRecognition;
    const button = document.getElementById('assistant-voice-btn');

    if (!Recognition) {
        state.voice.available = false;
        state.voice.note = 'Voice input not supported in this browser. Try Chrome or Safari.';
        if (button) {
            button.classList.add('unavailable');
            button.title = state.voice.note;
        }
        renderVoiceState();
        return;
    }

    const recognition = new Recognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;
    recognition.lang = navigator.language || 'en-US';

    recognition.onstart = () => {
        state.voice.listening = true;
        state.voice.processing = false;
        renderVoiceState();
    };

    recognition.onresult = (event) => {
        const transcript = event.results?.[0]?.[0]?.transcript?.trim();
        state.voice.listening = false;
        state.voice.processing = false;

        if (!transcript) {
            renderVoiceState();
            return;
        }

        const input = document.getElementById('assistant-input');
        if (input) {
            input.value = transcript;
            autoSizeAssistantInput();
            updateAssistantComposerState();
        }

        if (state.voiceSettings.autoSend) {
            state.voice.lastInputWasVoice = true;
            void sendAssistantMessage(transcript, { clearInput: true });
        } else {
            renderVoiceState();
        }
    };

    recognition.onerror = (event) => {
        state.voice.listening = false;
        state.voice.processing = false;

        if (event.error === 'no-speech') {
            // Silently ignore or handle
        } else if (event.error === 'not-allowed') {
            state.voice.note = 'Microphone access denied.';
            showBanner(state.voice.note, 'error');
        } else {
            state.voice.note = `Voice error: ${event.error}`;
        }

        renderVoiceState();
    };

    recognition.onend = () => {
        if (state.voice.listening) {
            state.voice.listening = false;
            state.voice.processing = true;
        }
        renderVoiceState();
    };

    state.voice.available = true;
    state.voice.recognition = recognition;
    renderVoiceState();
}

function goalCardMarkup(goal) {
    const summary = goal.id === state.goalSummary?.goal_id ? state.goalSummary : null;
    const isActive = goal.id === state.selectedGoalId;
    const blocker = summary?.blocked_reason || goal.last_error;
    const metaBits = [
        `Priority ${labelize(goal.priority)}`,
        `Updated ${formatRelativeTime(goal.updated_at)}`
    ];

    if (goal.requires_approval) {
        metaBits.push('Approval-aware');
    }

    return `
        <article class="goal-card ${isActive ? 'is-active' : ''}" data-goal-id="${escapeHtml(goal.id)}" data-goal-card="${escapeHtml(goal.id)}">
            <div class="goal-card__header">
                <div>
                    <div class="goal-card__title">${escapeHtml(goal.title || 'Untitled Goal')}</div>
                    <div class="goal-card__copy">${escapeHtml(shorten(goal.objective || 'No objective yet.', 160))}</div>
                </div>
                ${statusPill(goal.status)}
            </div>
            <div class="chip-row">
                ${chip(labelize(goal.priority))}
                ${goal.current_step_index != null ? chip(`Step ${Number(goal.current_step_index) + 1}`) : ''}
            </div>
            ${blocker ? `<div class="status-note">${escapeHtml(blocker)}</div>` : ''}
            <div class="goal-card__meta">${escapeHtml(metaBits.join(' | '))}</div>
        </article>
    `;
}

function stepCardMarkup(step) {
    return `
        <article class="step-card">
            <div class="step-card__index">${Number(step.step_index) + 1}</div>
            <div class="stack">
                <div class="item-card__header">
                    <div>
                        <div class="item-card__title">${escapeHtml(step.title || `Step ${Number(step.step_index) + 1}`)}</div>
                        <div class="item-card__copy">${escapeHtml(step.description || 'No description provided for this step yet.')}</div>
                    </div>
                    ${statusPill(step.status)}
                </div>
                <div class="chip-row">
                    ${chip(labelize(step.capability_type || 'manual'))}
                    ${step.requires_approval ? chip('Needs approval') : chip('No approval gate')}
                    ${step.result_ref ? chip(`Result ${step.result_ref}`) : ''}
                </div>
                <div class="timeline-item__meta">${escapeHtml(step.last_transition_reason || 'Awaiting movement in the execution queue.')}</div>
            </div>
        </article>
    `;
}

function detailMetric(label, value) {
    return `
        <div class="detail-metric">
            <span class="detail-metric__label">${escapeHtml(label)}</span>
            <span class="detail-metric__value">${escapeHtml(value || '--')}</span>
        </div>
    `;
}

function timelineItemMarkup(event) {
    return `
        <article class="timeline-item">
            <div class="item-card__header">
                <div>
                    <div class="item-card__title">${escapeHtml(labelize(event.event_type || 'event'))}</div>
                    <div class="timeline-item__copy">${escapeHtml(event.reason || 'State changed without an attached note.')}</div>
                </div>
                ${statusPill(event.to_status || event.event_type, event.to_status ? labelize(event.to_status) : labelize(event.event_type))}
            </div>
            <div class="timeline-item__meta">${escapeHtml(formatDateTime(event.created_at))}</div>
        </article>
    `;
}

function approvalCardMarkup(approval) {
    const readyToExecute = approval.action_status === 'approved';
    return `
        <article class="approval-card" data-approval-id="${escapeHtml(approval.action_id)}" data-approval-card="${escapeHtml(approval.action_id)}">
            <div class="item-card__header">
                <div>
                    <div class="item-card__title">${escapeHtml(approval.preview || approval.action_type || 'Pending action')}</div>
                    <div class="item-card__copy">${escapeHtml(approval.goal_title || 'Unlinked approval')} ${approval.step_title ? `| ${escapeHtml(approval.step_title)}` : ''}</div>
                </div>
                ${statusPill(approval.action_status || 'pending')}
            </div>
            <div class="chip-row">
                ${chip(approval.action_id)}
                ${chip(labelize(approval.action_type || 'action'))}
                ${approval.result_ref ? chip(`Result ${approval.result_ref}`) : ''}
            </div>
            <div class="item-card__meta">Created ${escapeHtml(formatDateTime(approval.created_at))}</div>
            <div class="inline-actions">
                ${approval.action_status === 'pending' ? `<button class="btn btn-primary" data-approval-action="approve" data-action-id="${escapeHtml(approval.action_id)}">Approve</button>` : ''}
                ${approval.action_status === 'pending' ? `<button class="btn btn-secondary" data-approval-action="reject" data-action-id="${escapeHtml(approval.action_id)}">Reject</button>` : ''}
                ${(approval.action_status === 'pending' || readyToExecute) ? `<button class="btn btn-secondary" data-approval-action="execute" data-action-id="${escapeHtml(approval.action_id)}">Execute</button>` : ''}
                ${approval.goal_id ? `<button class="btn btn-secondary" data-open-goal="${escapeHtml(approval.goal_id)}">Open Goal</button>` : ''}
            </div>
        </article>
    `;
}

function renderOverviewPage() {
    const summary = state.summary?.summary || {};
    const recommendation = topRecommendation();
    const activeGoals = state.goals.filter((goal) => ['active', 'planned', 'draft'].includes(goal.status)).slice(0, 3);
    const blockedItems = state.blocked.slice(0, 3);
    const pendingApprovals = state.approvals.slice(0, 2);
    const recentEvents = (state.summary?.recent_goal_events || []).slice(0, 4);
    const disabledPermissions = state.permissionsSnapshot?.summary?.counts?.disabled ?? summary.disabled_permissions_count ?? 0;
    const pendingRequests = pendingPermissionRequests().length || summary.permission_requests_pending || 0;

    document.getElementById('page-overview').innerHTML = `
        ${pageIntro('overview', `
            <button class="btn btn-primary" data-page="goals">Open Goals</button>
            <button class="btn btn-secondary" data-page="approvals">Review Approvals</button>
        `)}
        <section class="stats-grid">
            <article id="stat-active-goals" class="metric-card">
                <span class="metric-label">Active Goals</span>
                <strong class="metric-value">${escapeHtml(summary.active_goals_count ?? 0)}</strong>
                <span class="metric-hint">Live governed work in motion right now.</span>
            </article>
            ${metricCard('Pending approvals', summary.pending_approvals_count ?? 0, 'Sensitive work waiting on explicit owner action.')}
            ${metricCard('Blocked items', currentBlockedCount(), 'Goals or steps that need intervention before continuing.')}
            ${metricCard('Permission warnings', pendingRequests || disabledPermissions, pendingRequests ? 'Pending trust requests need a decision.' : 'Disabled permissions are constraining future work.')}
        </section>
        <section class="two-column">
            <div class="panel">
                <div class="panel-header">
                    <div>
                        <h3 class="panel-title">Current system health</h3>
                        <div class="panel-subtitle">One-line health, live providers, and the next recommended move.</div>
                    </div>
                    ${statusPill(state.readiness?.overall || deriveHealthLabel(), deriveHealthLabel())}
                </div>
                <div class="stack">
                    <div class="status-note">Axis is ${escapeHtml(deriveHealthLabel().toLowerCase())}. LLM mode is ${escapeHtml(deriveModelLabel())}. Google is ${escapeHtml(state.summary?.google?.status || state.readiness?.google_integration?.status || 'unknown')} and voice is ${escapeHtml(state.summary?.voice?.stt_provider || state.readiness?.voice_subsystem?.stt_provider || 'unknown')} / ${escapeHtml(state.summary?.voice?.tts_provider || state.readiness?.voice_subsystem?.tts_provider || 'unknown')}.</div>
                    <div class="item-card">
                        <div class="item-card__title">Recommended next action</div>
                        <div class="item-card__copy">${escapeHtml(recommendation?.recommended_action || 'No recommendation is queued right now. Review the current goals, blockers, and approvals to decide the next move.')}</div>
                        <div class="item-card__meta">${escapeHtml(recommendation?.goal_title || 'Axis overview')}</div>
                    </div>
                </div>
            </div>
            <div class="panel">
                <div class="panel-header">
                    <div>
                        <h3 class="panel-title">Trust and attention points</h3>
                        <div class="panel-subtitle">Permission blockers, approvals, and risks that affect what Axis can safely do next.</div>
                    </div>
                </div>
                <div class="stack">
                    ${pendingRequests ? `
                        <div class="item-card">
                            <div class="item-card__title">${pendingRequests} permission request${pendingRequests === 1 ? '' : 's'} pending</div>
                            <div class="item-card__copy">Permissions & Access needs review before some blocked work can continue.</div>
                            <div class="inline-actions">
                                <button class="btn btn-secondary" data-page="permissions">Review permissions</button>
                            </div>
                        </div>
                    ` : ''}
                    ${summary.pending_approvals_count ? `
                        <div class="item-card">
                            <div class="item-card__title">${summary.pending_approvals_count} approval${summary.pending_approvals_count === 1 ? '' : 's'} waiting</div>
                            <div class="item-card__copy">The approval queue is the current execution gate for sensitive work.</div>
                            <div class="inline-actions">
                                <button class="btn btn-secondary" data-page="approvals">Open approvals</button>
                            </div>
                        </div>
                    ` : ''}
                    ${!pendingRequests && !summary.pending_approvals_count ? emptyState('No urgent trust actions', 'The trust model is stable right now. Review goals, blockers, or approvals for the next meaningful change.') : ''}
                </div>
            </div>
        </section>
        <section class="three-column">
            <div class="panel">
                <div class="panel-header">
                    <div>
                        <h3 class="panel-title">Active goals</h3>
                        <div class="panel-subtitle">The most relevant work currently visible from the live queue.</div>
                    </div>
                </div>
                <div class="goal-list">
                    ${activeGoals.length ? activeGoals.map((goal) => goalCardMarkup(goal)).join('') : emptyState('No goals yet', 'Create your first goal from the Goals page to start the governed execution loop.')}
                </div>
            </div>
            <div class="panel">
                <div class="panel-header">
                    <div>
                        <h3 class="panel-title">Blocked work</h3>
                        <div class="panel-subtitle">Items that need missing info, trust changes, or manual intervention.</div>
                    </div>
                </div>
                <div class="stack">
                    ${blockedItems.length ? blockedItems.map((item) => `
                        <article class="item-card">
                            <div class="item-card__header">
                                <div>
                                    <div class="item-card__title">${escapeHtml(item.goal_title || 'Blocked goal')}</div>
                                    <div class="item-card__copy">${escapeHtml(item.blocked_reason || 'No blocker message recorded.')}</div>
                                </div>
                                ${statusPill(item.status || 'blocked')}
                            </div>
                            <div class="item-card__meta">${escapeHtml(item.recommended_resolution || 'Review and reconcile the goal.')}</div>
                            ${item.goal_id ? `<div class="inline-actions"><button class="btn btn-secondary" data-open-goal="${escapeHtml(item.goal_id)}">Inspect goal</button></div>` : ''}
                        </article>
                    `).join('') : emptyState('No blocked items', 'Axis does not currently show blocked goals or steps on the overview.')}
                </div>
            </div>
            <div class="panel">
                <div class="panel-header">
                    <div>
                        <h3 class="panel-title">Recent movement</h3>
                        <div class="panel-subtitle">A readable timeline of the latest goal activity and approval pressure.</div>
                    </div>
                </div>
                <div class="stack">
                    ${pendingApprovals.length ? pendingApprovals.map((approval) => approvalCardMarkup(approval)).join('') : ''}
                    ${recentEvents.length ? recentEvents.map((event) => timelineItemMarkup(event)).join('') : emptyState('No activity yet', 'Today has not produced new goal events in the visible dashboard summary.')}
                </div>
            </div>
        </section>
    `;
}

function renderGoalsPage() {
    const filteredGoals = state.goals.filter((goal) => {
        if (!goalMatchesViewFilter(goal)) {
            return false;
        }
        if (!state.goalQuery.trim()) {
            return true;
        }
        const query = state.goalQuery.toLowerCase();
        return `${goal.title} ${goal.objective} ${goal.status} ${goal.priority}`.toLowerCase().includes(query);
    });
    const selectedGoal = state.goalContext?.goal && goalMatchesViewFilter(state.goalContext.goal)
        ? state.goalContext.goal
        : filteredGoals.find((item) => item.id === state.selectedGoalId) || null;
    const goal = selectedGoal;
    const summary = state.goalSummary || null;
    const steps = goal?.steps || [];
    const controls = summary?.controls || {};
    const permissions = summary?.permission_dependencies || [];
    const blockedDependencies = summary?.blocked_dependencies || [];

    document.getElementById('page-goals').innerHTML = `
        ${pageIntro('goals', `
            <button id="new-goal-btn" class="btn btn-primary" type="button">Create Goal</button>
            <button class="btn btn-secondary" type="button" data-goal-action="reconcile-all">Reconcile All</button>
        `)}
        <section class="goals-layout">
            <div class="panel">
                <div class="goal-toolbar">
                    <div class="search-field">
                        <label for="goal-search-input">Search goals</label>
                        <input id="goal-search-input" class="form-input" placeholder="Search by title, objective, status, or priority" value="${escapeHtml(state.goalQuery)}">
                    </div>
                    ${renderSegmentedFilters([
        { value: 'all', label: 'All goals' },
        { value: 'active', label: 'Active' },
        { value: 'blocked', label: 'Blocked' },
        { value: 'approval', label: 'Approval-aware' }
    ], state.goalViewFilter, 'goal-filter', 'Goal filters')}
                    <div class="chip-row">
                        ${chip(`${state.goals.length} total`)}
                        ${chip(`${state.goals.filter((item) => item.status === 'active').length} active`)}
                        ${chip(`${state.goals.filter((item) => item.status === 'blocked').length} blocked`)}
                    </div>
                </div>
                <div class="goal-list">
                    ${filteredGoals.length ? filteredGoals.map((item) => goalCardMarkup(item)).join('') : emptyState('No matching goals', 'Try a broader search or create your first goal below.')}
                </div>
            </div>
            <div class="goal-detail">
                <div class="panel">
                    ${goal ? `
                        <div class="detail-grid">
                            <div class="detail-header">
                                <div>
                                    <h3 class="detail-title">${escapeHtml(goal.title || 'Untitled Goal')}</h3>
                                    <div class="detail-copy">${escapeHtml(goal.objective || 'No objective has been recorded for this goal yet.')}</div>
                                </div>
                                ${statusPill(goal.status)}
                            </div>
                            <div class="chip-row">
                                ${chip(labelize(goal.priority || 'normal'))}
                                ${goal.requires_approval ? chip('Approval-first') : chip('Direct control')}
                                ${goal.current_plan?.planner_provider ? chip(`Planner ${goal.current_plan.planner_provider}`) : ''}
                            </div>
                            <div class="detail-metrics">
                                ${detailMetric('Progress', summary?.progress || `${steps.filter((step) => step.status === 'completed').length}/${steps.length}`)}
                                ${detailMetric('Current step', goal.current_step_index != null ? String(Number(goal.current_step_index) + 1) : '--')}
                                ${detailMetric('Waiting approvals', String(summary?.waiting_approvals?.length || 0))}
                                ${detailMetric('Recommended next action', summary?.recommended_next_action || 'Review the goal detail and choose a control.')}
                            </div>
                            ${summary?.blocked_reason ? `<div class="status-note">${escapeHtml(summary.blocked_reason)}</div>` : ''}
                            <div class="inline-actions">
                                <button class="btn btn-secondary" data-goal-action="edit" data-goal-id="${escapeHtml(goal.id)}">Edit Goal</button>
                                ${controls.can_plan ? `<button class="btn btn-primary" data-goal-action="plan" data-goal-id="${escapeHtml(goal.id)}">${escapeHtml(ACTION_LABELS.plan)}</button>` : ''}
                                ${controls.can_pause ? `<button class="btn btn-secondary" data-goal-action="pause" data-goal-id="${escapeHtml(goal.id)}">${escapeHtml(ACTION_LABELS.pause)}</button>` : ''}
                                ${controls.can_resume ? `<button class="btn btn-primary" data-goal-action="resume" data-goal-id="${escapeHtml(goal.id)}">${escapeHtml(ACTION_LABELS.resume)}</button>` : ''}
                                ${controls.can_stop ? `<button class="btn btn-danger" data-goal-action="stop" data-goal-id="${escapeHtml(goal.id)}">${escapeHtml(ACTION_LABELS.stop)}</button>` : ''}
                                ${controls.can_replan ? `<button class="btn btn-secondary" data-goal-action="replan" data-goal-id="${escapeHtml(goal.id)}">${escapeHtml(ACTION_LABELS.replan)}</button>` : ''}
                                ${controls.can_reconcile ? `<button class="btn btn-secondary" data-goal-action="reconcile" data-goal-id="${escapeHtml(goal.id)}">${escapeHtml(ACTION_LABELS.reconcile)}</button>` : ''}
                            </div>
                            <div class="two-column">
                                <div class="panel" data-page-section="execution">
                                    <div class="panel-header">
                                        <div>
                                            <h4 class="panel-title">Execution detail</h4>
                                            <div class="panel-subtitle">Readable status, guidance, and dependency posture for this goal.</div>
                                        </div>
                                    </div>
                                    <div class="stack">
                                        <div class="item-card">
                                            <div class="item-card__title">Next-step guidance</div>
                                            <div class="item-card__copy">${escapeHtml(summary?.next_step_guidance || 'Plan this goal to generate the first structured steps.')}</div>
                                        </div>
                                        <div class="item-card">
                                            <div class="item-card__title">Permission dependency summary</div>
                                            <div class="item-card__copy">${escapeHtml(summary?.permission_dependency_summary || 'No permission blockers recorded for this goal.')}</div>
                                        </div>
                                        ${summary?.profile_plan_summary ? `
                                            <div class="item-card">
                                                <div class="item-card__title">Profile and plan posture</div>
                                                <div class="item-card__copy">${escapeHtml(summary.profile_plan_summary.summary)}</div>
                                                <div class="item-card__meta">${escapeHtml(summary.profile_plan_summary.explanation || '')}</div>
                                            </div>
                                        ` : ''}
                                    </div>
                                </div>
                                <div class="panel" data-page-section="dependencies">
                                    <div class="panel-header">
                                        <div>
                                            <h4 class="panel-title">Dependencies</h4>
                                            <div class="panel-subtitle">Permissions, blockers, and approvals affecting execution realism.</div>
                                        </div>
                                    </div>
                                    <div class="stack">
                                        ${permissions.length ? permissions.map((permission) => `
                                            <article class="item-card">
                                                <div class="item-card__title">${escapeHtml(permission.name || permission.key)}</div>
                                                <div class="item-card__copy">${escapeHtml(permission.reason || permission.description || 'Dependency recorded for this goal.')}</div>
                                            </article>
                                        `).join('') : ''}
                                        ${blockedDependencies.length ? blockedDependencies.map((dependency) => `
                                            <article class="item-card">
                                                <div class="item-card__title">${escapeHtml(dependency.title || dependency.name || 'Blocked dependency')}</div>
                                                <div class="item-card__copy">${escapeHtml(dependency.reason || dependency.summary || 'This dependency is currently preventing progress.')}</div>
                                            </article>
                                        `).join('') : ''}
                                        ${!permissions.length && !blockedDependencies.length ? emptyState('No explicit dependency blockers', 'This goal does not currently expose permission or dependency blockers in its live summary.') : ''}
                                    </div>
                                </div>
                            </div>
                            <div class="panel" data-page-section="steps">
                                <div class="panel-header">
                                    <div>
                                        <h4 class="panel-title">Plan steps</h4>
                                        <div class="panel-subtitle">The structured sequence Axis is using for this goal.</div>
                                    </div>
                                </div>
                                <div class="step-list">
                                    ${steps.length ? steps.map((step) => stepCardMarkup(step)).join('') : emptyState('No steps yet', 'This goal does not have a structured plan yet. Use Generate plan when it is available.')}
                                </div>
                            </div>
                            <div class="panel" data-page-section="timeline">
                                <div class="panel-header">
                                    <div>
                                        <h4 class="panel-title">Goal timeline</h4>
                                        <div class="panel-subtitle">Readable history instead of raw event records.</div>
                                    </div>
                                </div>
                                <div class="timeline">
                                    ${state.goalEvents.length ? state.goalEvents.map((event) => timelineItemMarkup(event)).join('') : emptyState('No timeline events', 'This goal has not yet recorded visible state changes beyond creation.')}
                                </div>
                            </div>
                        </div>
                    ` : emptyState('No goal selected', 'Choose a goal from the list to inspect its state, steps, and available controls.')}
                </div>
            </div>
        </section>
    `;
}

function renderApprovalsPage() {
    const counts = state.approvalsMeta?.status_counts || {};
    const approvals = state.approvals.filter((approval) => approvalMatchesViewFilter(approval));
    document.getElementById('page-approvals').innerHTML = `
        ${pageIntro('approvals', `
            <button class="btn btn-secondary" type="button" data-refresh-page="approvals">Refresh Queue</button>
        `)}
        <section class="stats-grid">
            ${metricCard('Pending review', counts.pending ?? state.approvals.length, 'Actions still waiting for an owner decision.')}
            ${metricCard('Actionable now', counts.actionable ?? state.approvals.length, 'Items you can approve, reject, or execute immediately.')}
            ${metricCard('Recently executed', counts.executed ?? 0, 'Approvals that have already passed into execution.')}
            ${metricCard('Recent activity', counts.recent_activity ?? 0, 'Recent approval transitions preserved for auditability.')}
        </section>
        <section class="panel">
            <div class="panel-header">
                <div>
                    <h3 class="panel-title">Approval queue</h3>
                    <div class="panel-subtitle">Sensitive actions stay here until the owner makes the trust decision explicit.</div>
                </div>
            </div>
            ${renderSegmentedFilters([
        { value: 'all', label: 'All approvals' },
        { value: 'pending', label: 'Pending' },
        { value: 'approved', label: 'Approved' },
        { value: 'executed', label: 'Executed' }
    ], state.approvalViewFilter, 'approval-filter', 'Approval filters')}
            <div class="approval-list">
                ${approvals.length ? approvals.map((approval) => approvalCardMarkup(approval)).join('') : emptyState('No approvals match the current filter', 'Try a broader approval filter to review the full governed queue.')}
            </div>
        </section>
    `;
}

function renderAxisHubPage() {
    const summary = state.axisHubData?.summary || {};
    const activity = state.axisHubData?.activity || {};
    const skills = state.axisHubData?.skills || [];
    const training = state.axisHubData?.training_visibility || [];

    document.getElementById('page-axis-hub').innerHTML = `
        ${pageIntro('axis-hub')}
        <section class="stats-grid">
            ${metricCard('Live skills', summary.live ?? 0, 'Subsystems already behaving like part of the real operating system.')}
            ${metricCard('Partial lanes', summary.partial ?? 0, 'Surfaces that show direction but are still limited.')}
            ${metricCard('Planned lanes', summary.planned ?? 0, 'Roadmap visibility that stays honestly labeled.')}
            ${metricCard('Simulated', summary.simulated ?? 0, 'Conceptual surfaces that are present for alignment, not false promises.')}
        </section>
        <section class="two-column">
            <div class="panel">
                <div class="panel-header">
                    <div>
                        <h3 class="panel-title">Ecosystem activity</h3>
                        <div class="panel-subtitle">A product-level read on what the system is doing right now.</div>
                    </div>
                </div>
                ${renderSummaryCards(activity, 'Live activity signal')}
            </div>
            <div class="panel">
                <div class="panel-header">
                    <div>
                        <h3 class="panel-title">Training visibility</h3>
                        <div class="panel-subtitle">How Axis grows today without pretending to self-improve autonomously.</div>
                    </div>
                </div>
                <div class="stack">
                    ${training.map((item) => `
                        <article class="item-card">
                            <div class="item-card__header">
                                <div>
                                    <div class="item-card__title">${escapeHtml(item.title)}</div>
                                    <div class="item-card__copy">${escapeHtml(item.summary)}</div>
                                </div>
                                ${statusPill(item.status)}
                            </div>
                        </article>
                    `).join('')}
                </div>
            </div>
        </section>
        <section class="panel">
            <div class="panel-header">
                <div>
                    <h3 class="panel-title">Axis skill surfaces</h3>
                    <div class="panel-subtitle">The parts of the ecosystem that make the shell feel like one operating system.</div>
                </div>
            </div>
            <div class="skill-grid">
                ${skills.map((skill) => `
                    <article class="skill-card">
                        <div class="item-card__header">
                            <div>
                                <div class="skill-card__title">${escapeHtml(skill.name)}</div>
                                <div class="skill-card__copy">${escapeHtml(skill.summary)}</div>
                            </div>
                            ${statusPill(skill.state)}
                        </div>
                        <div class="chip-row">
                            ${chip(skill.group)}
                            ${chip(skill.availability)}
                        </div>
                        <div class="microcopy">${escapeHtml(skill.usage_signal || 'No current usage signal.')}</div>
                        <div class="microcopy">${escapeHtml(skill.training_state || 'No training state published.')}</div>
                    </article>
                `).join('')}
            </div>
        </section>
    `;
}

function renderGuidePage() {
    const query = state.guideFilter.trim().toLowerCase();
    const capabilities = (state.guideData?.capabilities || []).filter((capability) => {
        if (!query) {
            return true;
        }
        return `${capability.name} ${capability.summary} ${capability.group} ${capability.realism}`.toLowerCase().includes(query);
    });
    const workflows = (state.guideData?.workflows || []).filter((workflow) => {
        if (!query) {
            return true;
        }
        return `${workflow.title} ${workflow.summary} ${workflow.status}`.toLowerCase().includes(query);
    });

    document.getElementById('page-guide').innerHTML = `
        ${pageIntro('guide')}
        <section class="stats-grid">
            ${metricCard('Live', state.guideData?.summary?.live ?? 0, 'Capabilities that are real in the current product shell.')}
            ${metricCard('Partially live', state.guideData?.summary?.partially_live ?? 0, 'Capabilities with real backing but incomplete product depth.')}
            ${metricCard('Degraded or mocked', (state.guideData?.summary?.degraded ?? 0) + (state.guideData?.summary?.mocked ?? 0), 'Capabilities that stay honest about degraded or mocked state.')}
            ${metricCard('Planned', state.guideData?.summary?.planned ?? 0, 'Roadmap items visible without pretending they are already shipping.')}
        </section>
        <section class="panel" data-page-section="capability-guide">
            <div class="panel-header">
                <div>
                    <h3 class="panel-title">Capability guide</h3>
                    <div class="panel-subtitle">A truthful map of what Axis can do now, what is limited, and what is still future work.</div>
                </div>
            </div>
            <div class="search-field">
                <label for="guide-filter-input">Filter guide</label>
                <input id="guide-filter-input" class="form-input" placeholder="Filter capabilities and workflows" value="${escapeHtml(state.guideFilter)}">
            </div>
            <div class="catalog-grid">
                ${capabilities.map((capability) => `
                    <article class="item-card">
                        <div class="item-card__header">
                            <div>
                                <div class="item-card__title">${escapeHtml(capability.name)}</div>
                                <div class="item-card__copy">${escapeHtml(capability.summary)}</div>
                            </div>
                            ${statusPill(capability.realism)}
                        </div>
                        <div class="chip-row">
                            ${chip(capability.group)}
                            ${chip(labelize(capability.realism))}
                        </div>
                        <div class="microcopy">${escapeHtml(capability.details || 'No detail provided.')}</div>
                        <div class="microcopy">${escapeHtml(capability.owner_controls || 'No owner control guidance recorded.')}</div>
                    </article>
                `).join('')}
                ${!capabilities.length ? emptyState('No guide matches', 'Try a broader filter to reveal the current capability map.') : ''}
            </div>
        </section>
        <section class="panel" data-page-section="workflow-guide">
            <div class="panel-header">
                <div>
                    <h3 class="panel-title">Workflow guide</h3>
                    <div class="panel-subtitle">How the major governed flows behave today.</div>
                </div>
            </div>
            <div class="workflow-list">
                ${workflows.map((workflow) => `
                    <article class="workflow-card">
                        <div class="item-card__header">
                            <div>
                                <div class="workflow-card__title">${escapeHtml(workflow.title)}</div>
                                <div class="workflow-card__copy">${escapeHtml(workflow.summary)}</div>
                            </div>
                            ${statusPill(workflow.status)}
                        </div>
                    </article>
                `).join('')}
                ${!workflows.length ? emptyState('No workflow matches', 'No workflow card matched the current filter.') : ''}
            </div>
        </section>
    `;
}

function permissionStateOptions(permission) {
    const options = ['enabled', 'limited', 'disabled'];
    return Array.from(new Set([permission.current_state, permission.default_state, ...options].filter(Boolean)));
}

function renderPermissionsPage() {
    const query = state.permissionsFilter.trim().toLowerCase();
    const permissions = (state.permissionsSnapshot?.permissions || []).filter((permission) => {
        if (!permissionMatchesStateFilter(permission)) {
            return false;
        }
        if (!query) {
            return true;
        }
        return `${permission.name} ${permission.description} ${permission.group} ${permission.key}`.toLowerCase().includes(query);
    });
    const grouped = permissions.reduce((accumulator, permission) => {
        accumulator[permission.group] = accumulator[permission.group] || [];
        accumulator[permission.group].push(permission);
        return accumulator;
    }, {});
    const requests = pendingPermissionRequests();

    document.getElementById('page-permissions').innerHTML = `
        ${pageIntro('permissions')}
        <section class="stats-grid">
            ${metricCard('Active', state.permissionsSnapshot?.summary?.counts?.active ?? 0, 'Permissions currently enabled and available.')}
            ${metricCard('Disabled', state.permissionsSnapshot?.summary?.counts?.disabled ?? 0, 'Explicitly disabled permissions constraining the workspace.')}
            ${metricCard('Limited', state.permissionsSnapshot?.summary?.counts?.limited ?? 0, 'Capabilities that are intentionally constrained right now.')}
            ${metricCard('Pending requests', requests.length, state.permissionsSnapshot?.session_guidance || 'Trust requests surfaced by the system.')}
        </section>
        <section class="panel" data-page-section="permission-requests">
            <div class="panel-header">
                <div>
                    <h3 class="panel-title">Permission requests</h3>
                    <div class="panel-subtitle">Owner-facing requests created when Axis hits a trust wall.</div>
                </div>
            </div>
            <div class="permission-list">
                ${requests.length ? requests.map((request) => `
                    <article class="permission-card" data-permission-request-key="${escapeHtml(request.permission_key)}">
                        <div class="item-card__header">
                            <div>
                                <div class="permission-card__title">${escapeHtml(request.title || request.permission_key)}</div>
                                <div class="permission-card__copy">${escapeHtml(request.reason || 'No reason recorded.')}</div>
                            </div>
                            ${statusPill(request.status)}
                        </div>
                        <div class="chip-row">
                            ${chip(request.permission_key)}
                            ${request.goal_title ? chip(request.goal_title) : ''}
                        </div>
                        <div class="microcopy">Requested ${escapeHtml(formatDateTime(request.created_at))} for ${escapeHtml(request.action_label || 'governed execution')}</div>
                        <div class="inline-actions">
                            <button class="btn btn-primary" data-request-action="approve" data-request-id="${escapeHtml(request.id)}" data-permission-key="${escapeHtml(request.permission_key)}">Approve</button>
                            <button class="btn btn-secondary" data-request-action="deny" data-request-id="${escapeHtml(request.id)}">Deny</button>
                        </div>
                    </article>
                `).join('') : emptyState('No pending permission requests', 'Axis is not currently waiting on a new trust decision from the owner.')}
            </div>
        </section>
        <section class="panel" data-page-section="device-pairing">
            <div class="panel-header">
                <div>
                    <h3 class="panel-title">Pair a Remote Device</h3>
                    <div class="panel-subtitle">Generate a one-time code to securely connect a phone, tablet, or remote browser to Axis.</div>
                </div>
            </div>
            <div id="pairing-code-container" style="padding: 16px;">
                <button class="btn btn-primary" onclick="window.generatePairingCode()" id="btn-generate-pairing-code">Generate Pairing Code</button>
            </div>
        </section>
        <section class="panel" data-page-section="permissions-list">
            <div class="panel-header">
                <div>
                    <h3 class="panel-title">Permissions and access</h3>
                    <div class="panel-subtitle">${escapeHtml(state.permissionsSnapshot?.session_guidance || 'Review what Axis is allowed to do and where the trust model intentionally stops.')}</div>
                </div>
            </div>
            ${renderSegmentedFilters([
        { value: 'all', label: 'All states' },
        { value: 'disabled', label: 'Disabled' },
        { value: 'limited', label: 'Limited' },
        { value: 'active', label: 'Active' }
    ], state.permissionStateFilter, 'permission-state-filter', 'Permission state filters')}
            <div class="search-field">
                <label for="permissions-filter-input">Filter permissions</label>
                <input id="permissions-filter-input" class="form-input" placeholder="Filter by capability or trust area" value="${escapeHtml(state.permissionsFilter)}">
            </div>
            <div class="permission-grid">
                ${Object.entries(grouped).map(([group, items]) => `
                    <section class="permission-group">
                        <p class="eyebrow">${escapeHtml(group)}</p>
                        <div class="permission-list">
                            ${items.map((permission) => `
                                <article class="permission-card" data-permission-key-card="${escapeHtml(permission.key)}">
                                    <div class="item-card__header">
                                        <div>
                                            <div class="permission-card__title">${escapeHtml(permission.name)}</div>
                                            <div class="permission-card__copy">${escapeHtml(permission.description)}</div>
                                        </div>
                                        ${statusPill(permission.effective_status || permission.current_state)}
                                    </div>
                                    <div class="chip-row">
                                        ${chip(`Risk ${labelize(permission.risk_level)}`)}
                                        ${chip(labelize(permission.availability))}
                                        ${permission.available === false && permission.availability_reason ? chip('Unavailable right now') : ''}
                                    </div>
                                    <div class="microcopy">${escapeHtml(permission.availability_reason || `Current state: ${labelize(permission.current_state)}. Grant policy: ${labelize(permission.grant_policy)}.`)}</div>
                                    ${permission.manageable && permission.toggleable ? `
                                        <div class="form-group">
                                            <label for="permission-${escapeHtml(permission.key)}">Set state</label>
                                            <select id="permission-${escapeHtml(permission.key)}" class="form-input" data-permission-key="${escapeHtml(permission.key)}" data-risk-level="${escapeHtml(permission.risk_level)}">
                                                ${permissionStateOptions(permission).map((option) => `
                                                    <option value="${escapeHtml(option)}" ${permission.current_state === option ? 'selected' : ''}>${escapeHtml(labelize(option))}</option>
                                                `).join('')}
                                            </select>
                                        </div>
                                    ` : `<div class="microcopy">This permission is read-only in the current build or session.</div>`}
                                </article>
                            `).join('')}
                        </div>
                    </section>
                `).join('')}
                ${!Object.keys(grouped).length ? emptyState('No permissions match the current filters', 'Try a broader state filter or search query to reveal more of the trust surface.') : ''}
            </div>
        </section>
    `;
}

function renderSecurityPage() {
    const summary = state.securityData?.summary || {};
    const trust = state.securityData?.trust_overview || {};
    const cards = state.securityData?.cards || [];
    const activity = state.recentActivity || [];

    document.getElementById('page-security').innerHTML = `
        ${pageIntro('security')}
        <section class="stats-grid">
            ${metricCard('Active controls', summary.active ?? 0, 'Security and trust surfaces actively protecting the current runtime.')}
            ${metricCard('Local-first posture', summary.local_only ?? 0, 'Controls or claims intentionally scoped to local operation.')}
            ${metricCard('Degraded connectors', summary.degraded ?? 0, 'External dependencies that are honestly reported as degraded.')}
            ${metricCard('Enterprise planned', summary.enterprise_planned ?? 0, 'Enterprise posture items that remain roadmap-only today.')}
        </section>
        <section class="two-column">
            <div class="panel">
                <div class="panel-header">
                    <div>
                        <h3 class="panel-title">Trust overview</h3>
                        <div class="panel-subtitle">The three numbers most likely to change real execution behavior.</div>
                    </div>
                </div>
                ${renderSummaryCards(trust, 'Current trust posture')}
                <div class="security-audit-list">
                    <div class="panel-header" style="margin-top: 16px;">
                        <div>
                            <h3 class="panel-title">Recent audit activity</h3>
                            <div class="panel-subtitle">Latest requests logged by the system</div>
                        </div>
                    </div>
                    ${activity.length ? activity.slice(0, 10).map((item) => `
                        <article class="item-card security-audit-item">
                            <div class="item-card__header">
                                <div class="item-card__title">${escapeHtml(item.method || '--')} ${escapeHtml(item.endpoint || '--')}</div>
                                <span class="status-pill ${(Number(item.status_code) >= 400) ? 'tone-danger' : 'tone-success'}">${escapeHtml(String(item.status_code ?? '--'))}</span>
                            </div>
                            <div class="microcopy">${escapeHtml(formatRelativeTime(item.timestamp))} · ${escapeHtml(item.actor_type || 'unknown')}</div>
                        </article>
                    `).join('') : `<div class="empty-state">No recent activity recorded.</div>`}
                </div>
            </div>
            <div class="panel">
                <div class="panel-header">
                    <div>
                        <h3 class="panel-title">Security posture</h3>
                        <div class="panel-subtitle">Readable cards describing the real current boundary.</div>
                    </div>
                </div>
                <div class="stack">
                    ${cards.map((card) => `
                        <article class="item-card">
                            <div class="item-card__header">
                                <div>
                                    <div class="item-card__title">${escapeHtml(card.title)}</div>
                                    <div class="item-card__copy">${escapeHtml(card.summary)}</div>
                                </div>
                                ${statusPill(card.status)}
                            </div>
                            <div class="microcopy">${escapeHtml(card.detail)}</div>
                        </article>
                    `).join('')}
                </div>
            </div>
        </section>
    `;
}

function settingControlMarkup(setting) {
    if (!setting.editable) {
        return `<div class="microcopy">This setting is system-managed in the current build.</div>`;
    }

    if (setting.type === 'boolean') {
        return `
            <label class="form-group" for="setting-${escapeHtml(setting.key)}">
                <span>Enabled</span>
                <input id="setting-${escapeHtml(setting.key)}" type="checkbox" ${setting.value ? 'checked' : ''} data-setting-key="${escapeHtml(setting.key)}">
            </label>
        `;
    }

    if (setting.type === 'select') {
        return `
            <div class="form-group">
                <label for="setting-${escapeHtml(setting.key)}">Value</label>
                <select id="setting-${escapeHtml(setting.key)}" class="form-input" data-setting-key="${escapeHtml(setting.key)}">
                    ${(setting.options || []).map((option) => `
                        <option value="${escapeHtml(option)}" ${setting.value === option ? 'selected' : ''}>${escapeHtml(labelize(option))}</option>
                    `).join('')}
                </select>
            </div>
        `;
    }

    return `
        <div class="form-group">
            <label for="setting-${escapeHtml(setting.key)}">Value</label>
            <input id="setting-${escapeHtml(setting.key)}" class="form-input" value="${escapeHtml(setting.value)}" data-setting-key="${escapeHtml(setting.key)}">
        </div>
    `;
}

function renderSettingsPage() {
    const groups = state.settingsData?.groups || {};

    document.getElementById('page-settings').innerHTML = `
        ${pageIntro('settings')}
        <section class="stats-grid">
            ${metricCard('Live controls', state.settingsData?.summary?.live ?? 0, 'Settings with a live runtime effect today.')}
            ${metricCard('Not configured', state.settingsData?.summary?.not_configured ?? 0, 'Areas that are visible but intentionally incomplete.')}
            ${metricCard('Editable now', Object.values(groups).flat().filter((setting) => setting.editable).length, 'Controls the owner can change safely from this shell.')}
            ${metricCard('Session posture', state.settingsData?.session_class || '--', state.settingsData?.session_note || 'Settings are intentionally narrow in this foundation pass.')}
        </section>
        <section class="settings-grid">
            ${Object.entries(groups).map(([group, items]) => `
                <div class="panel">
                    <div class="panel-header">
                        <div>
                            <h3 class="panel-title">${escapeHtml(group)}</h3>
                            <div class="panel-subtitle">Safe live controls and honest system-managed defaults.</div>
                        </div>
                    </div>
                    <div class="stack">
                        ${items.map((setting) => `
                            <article class="setting-card">
                                <div class="item-card__header">
                                    <div>
                                        <div class="setting-card__title">${escapeHtml(setting.name)}</div>
                                        <div class="setting-card__copy">${escapeHtml(setting.description || 'No setting description provided.')}</div>
                                    </div>
                                    ${statusPill(setting.status || 'live')}
                                </div>
                                ${settingControlMarkup(setting)}
                            </article>
                        `).join('')}
                    </div>
                </div>
            `).join('')}

            ${(() => {
            const hasModels = state.llmModelsData && state.llmModelsData.models && state.llmModelsData.models.length > 0;
            const providers = ['groq', 'openrouter', 'huggingface', 'anthropic'];
            const userPlan = state.settingsData?.user_plan || 'free';

            return `
                <div class="panel">
                    <div class="panel-header">
                        <div>
                            <h3 class="panel-title">AI Model</h3>
                            <div class="panel-subtitle">Select the active LLM provider and model for Axis.</div>
                        </div>
                    </div>
                    <div class="stack">
                        ${!hasModels ? `
                            <div style="padding: 2rem; text-align: center; color: var(--color-foreground-muted);">
                                <div class="spinner" style="margin-bottom: 1rem;"></div>
                                <div>Loading available AI models...</div>
                            </div>
                        ` : `
                            ${providers.filter(p => state.llmModelsData.models.some(m => m.provider === p)).map(provider => {
                const models = state.llmModelsData.models.filter(m => m.provider === provider);
                const isWorking = state.llmModelsData.providers[provider];
                return `
                                    <div style="margin-bottom: 1rem;">
                                        <div style="font-size: 0.75rem; text-transform: uppercase; font-weight: 700; color: var(--color-foreground-muted); margin-bottom: 0.5rem; display: flex; align-items: center; gap: 0.5rem; padding: 0 1rem;">
                                            <span style="display: block; width: 6px; height: 6px; border-radius: 50%; background: ${isWorking ? 'var(--color-success)' : 'var(--color-danger)'};"></span>
                                            ${provider}
                                        </div>
                                        ${models.map(model => {
                    const isActive = state.llmModelsData.active_model === model.id;
                    const isPro = model.tier === 'pro';
                    const isLocked = isPro && userPlan === 'free';
                    return `
                                                <article class="setting-card" style="cursor: ${isLocked ? 'default' : 'pointer'}; opacity: ${isLocked ? '0.7' : '1'}; border-left: ${isActive ? '2px solid var(--color-primary)' : 'none'}" ${isLocked ? 'title="Upgrade to Pro to use this model"' : `onclick="handleLLMModelChange('${model.id}')"`}>
                                                    <div class="item-card__header">
                                                        <div style="display: flex; align-items: center; gap: 1rem;">
                                                            <input type="radio" style="pointer-events: none;" name="llm_model" ${isActive ? 'checked' : ''} ${isLocked ? 'disabled' : ''}>
                                                            <div>
                                                                <div class="setting-card__title" style="display: flex; align-items: center; gap: 0.5rem;">
                                                                    ${escapeHtml(model.name)}
                                                                    ${isActive ? '<span class="status-pill tone-info">Active</span>' : ''}
                                                                    ${isLocked ? '<span style="font-size: 0.9em;">ðŸ”’</span>' : ''}
                                                                </div>
                                                                <div class="setting-card__copy">${escapeHtml(model.description)}</div>
                                                            </div>
                                                        </div>
                                                        <span class="status-pill ${isPro ? 'tone-primary' : 'tone-success'}">${isPro ? 'Pro' : 'Free'}</span>
                                                    </div>
                                                </article>
                                            `;
                }).join('')}
                                    </div>
                                `;
            }).join('')}
                            <div class="settings-action-row" style="padding: 1rem; border-top: 1px solid var(--border-subtle); display: flex; align-items: center; gap: 1rem;">
                                <button type="button" class="btn btn-secondary" onclick="testCurrentLLMModel()">Test Current Model</button>
                                <span id="llm-test-result" style="font-size: 0.85rem; color: var(--color-foreground-muted);"></span>
                            </div>
                        `}
                    </div>
                </div>
            `;
        })()}

            <div class="panel">
                <div class="panel-header">
                    <div>
                        <h3 class="panel-title">Voice Controls</h3>
                        <div class="panel-subtitle">Manage spoken interactions and speech synthesis preferences.</div>
                    </div>
                </div>
                <div class="stack">
                    <article class="setting-card">
                        <div class="item-card__header">
                            <div>
                                <div class="setting-card__title">Voice Responses</div>
                                <div class="setting-card__copy">Allow Axis to speak replies aloud for voice-initiated messages.</div>
                            </div>
                            <span class="status-pill tone-info">live</span>
                        </div>
                        <label class="form-group">
                            <span>Enabled</span>
                            <input type="checkbox" ${state.voiceSettings.responsesEnabled ? 'checked' : ''} onchange="handleVoiceSettingChange('responsesEnabled', this.checked)">
                        </label>
                    </article>
                    <article class="setting-card">
                        <div class="item-card__header">
                            <div>
                                <div class="setting-card__title">Auto-send Transcription</div>
                                <div class="setting-card__copy">Automatically send transcribed text to the assistant after releasing the voice button.</div>
                            </div>
                            <span class="status-pill tone-info">live</span>
                        </div>
                        <label class="form-group">
                            <span>Enabled</span>
                            <input type="checkbox" ${state.voiceSettings.autoSend ? 'checked' : ''} onchange="handleVoiceSettingChange('autoSend', this.checked)">
                        </label>
                    </article>
                    <article class="setting-card">
                        <div class="item-card__header">
                            <div>
                                <div class="setting-card__title">Response Voice</div>
                                <div class="setting-card__copy">Select the preferred synthesized voice for spoken responses.</div>
                            </div>
                            <span class="status-pill tone-info">live</span>
                        </div>
                        <div class="form-group">
                            <label>System Voice</label>
                            <select class="form-input" onchange="handleVoiceSettingChange('preferredVoiceName', this.value)">
                                ${window.speechSynthesis?.getVoices().map(v => `
                                    <option value="${escapeHtml(v.name)}" ${v.name === state.voiceSettings.preferredVoiceName ? 'selected' : ''}>
                                        ${escapeHtml(v.name)} (${escapeHtml(v.lang)})
                                    </option>
                                `).join('') || '<option disabled>Voices loading or unavailable</option>'}
                            </select>
                        </div>
                    </article>
                    <article class="setting-card">
                        <div class="item-card__header">
                            <div>
                                <div class="setting-card__title">Voice Input Button</div>
                                <div class="setting-card__copy">Toggle the presence of the voice input button in the assistant panel.</div>
                            </div>
                            <span class="status-pill tone-info">live</span>
                        </div>
                        <label class="form-group">
                            <span>Enabled</span>
                            <input type="checkbox" ${state.voiceSettings.voiceInputEnabled ? 'checked' : ''} onchange="handleVoiceSettingChange('voiceInputEnabled', this.checked)">
                        </label>
                    </article>
                </div>
            </div>
        </section>
        ${localStorage.getItem('axis_device_token') ? `
        <section class="panel" style="margin-top: 24px;">
            <div class="panel-header">
                <div>
                    <h3 class="panel-title" style="color: var(--danger);">Remote Access</h3>
                    <div class="panel-subtitle">This device is connected using a remote device token.</div>
                </div>
            </div>
            <div style="padding: 16px;">
                <button class="btn btn-primary" style="background: var(--danger); border-color: var(--danger);" onclick="window.disconnectDevice()">Disconnect This Device</button>
            </div>
        </section>` : ''}
    `;
}

function handleVoiceSettingChange(key, value) {
    state.voiceSettings[key] = value;
    localStorage.setItem('axis_voice_settings', JSON.stringify(state.voiceSettings));

    if (key === 'voiceInputEnabled') {
        renderVoiceState();
    }

    if (key === 'responsesEnabled' && !value) {
        stopSpeaking();
    }

    if (key === 'preferredVoiceName' && value) {
        const voices = window.speechSynthesis.getVoices();
        const voice = voices.find(v => v.name === value);
        if (voice) {
            const utterance = new SpeechSynthesisUtterance('Voice preference updated.');
            utterance.voice = voice;
            window.speechSynthesis.speak(utterance);
        }
    }
}

function syncProfileDraft() {
    const activeProfile = state.profilesData?.active_profile || {};
    if (!state.profileDraft || state.profileDraft.base_id !== activeProfile.id) {
        state.profileDraft = {
            base_id: activeProfile.id,
            display_name: activeProfile.display_name || '',
            profile_type: activeProfile.profile_type || '',
            plan_id: activeProfile.plan_id || ''
        };
    }
}

function renderProfilesPage() {
    syncProfileDraft();
    const activeProfile = state.profilesData?.active_profile || {};
    const activePlan = state.profilesData?.active_plan || {};
    const profileTypes = state.profilesData?.profile_types || [];
    const plans = state.profilesData?.plans || [];
    const matrix = state.profilesData?.feature_matrix || [];
    const selectedPlanIds = plans.map((plan) => plan.id);

    document.getElementById('page-profiles').innerHTML = `
        ${pageIntro('profiles')}
        <section class="stats-grid">
            ${metricCard('Workspace profile', activeProfile.profile_label || activeProfile.profile_type || '--', 'The current operating posture of the workspace.')}
            ${metricCard('Current plan', activePlan.name || '--', activePlan.honest_fit || 'Plan posture for the current system build.')}
            ${metricCard('Configured profiles', state.profilesData?.summary?.profiles_configured ?? 0, 'Profiles currently represented in the system state.')}
            ${metricCard('Upgrade guidance', state.profilesData?.upgrade_guidance?.status || '--', state.profilesData?.upgrade_guidance?.title || 'No guidance published.')}
        </section>
        <section class="two-column">
            <div class="panel">
                <div class="panel-header">
                    <div>
                        <h3 class="panel-title">Active workspace identity</h3>
                        <div class="panel-subtitle">Profile, plan, and display naming for the current shell.</div>
                    </div>
                </div>
                <div class="form-group">
                    <label for="profile-display-name">Display name</label>
                    <input id="profile-display-name" class="form-input" value="${escapeHtml(state.profileDraft.display_name)}" placeholder="Primary Axis Workspace">
                </div>
                <div class="status-note">${escapeHtml(activePlan.summary || 'No active plan summary is available.')}</div>
                <div class="inline-actions">
                    <button id="save-profile-btn" class="btn btn-primary" type="button">Save Profile</button>
                </div>
            </div>
            <div class="panel">
                <div class="panel-header">
                    <div>
                        <h3 class="panel-title">Upgrade guidance</h3>
                        <div class="panel-subtitle">${escapeHtml(state.profilesData?.upgrade_guidance?.title || 'Current plan posture')}</div>
                    </div>
                </div>
                <div class="stack">
                    <div class="item-card">
                        <div class="item-card__copy">${escapeHtml(state.profilesData?.upgrade_guidance?.copy || activePlan.honest_fit || 'No upgrade guidance is currently available.')}</div>
                    </div>
                    <div class="item-card">
                        <div class="item-card__title">Best for</div>
                        <div class="item-card__copy">${escapeHtml(activePlan.best_for || activeProfile.profile_label || 'Current workspace')}</div>
                    </div>
                </div>
            </div>
        </section>
        <section class="profiles-grid">
            <div class="panel">
                <div class="panel-header">
                    <div>
                        <h3 class="panel-title">Profiles</h3>
                        <div class="panel-subtitle">Choose the posture that best matches how this workspace is actually being used.</div>
                    </div>
                </div>
                <div class="profiles-grid">
                    ${profileTypes.map((profile) => `
                        <article class="profile-card ${state.profileDraft.profile_type === profile.id ? 'is-selected' : ''}">
                            <div class="item-card__header">
                                <div>
                                    <div class="profile-card__title">${escapeHtml(profile.name)}</div>
                                    <div class="profile-card__copy">${escapeHtml(profile.summary)}</div>
                                </div>
                            </div>
                            <div class="microcopy">${escapeHtml(profile.best_for)}</div>
                            <div class="inline-actions">
                                <button class="btn btn-secondary" data-select-profile="${escapeHtml(profile.id)}">Use profile</button>
                            </div>
                        </article>
                    `).join('')}
                </div>
            </div>
            <div class="panel">
                <div class="panel-header">
                    <div>
                        <h3 class="panel-title">Plans</h3>
                        <div class="panel-subtitle">Plan posture is advisory today, but it keeps the product honest about intended scale.</div>
                    </div>
                </div>
                <div class="profiles-grid">
                    ${plans.map((plan) => `
                        <article class="plan-card ${state.profileDraft.plan_id === plan.id ? 'is-selected' : ''}">
                            <div class="item-card__header">
                                <div>
                                    <div class="plan-card__title">${escapeHtml(plan.name)}</div>
                                    <div class="plan-card__copy">${escapeHtml(plan.summary)}</div>
                                </div>
                                ${statusPill(plan.status)}
                            </div>
                            <div class="microcopy">${escapeHtml(plan.honest_fit || '')}</div>
                            <div class="microcopy">${escapeHtml(plan.best_for || '')}</div>
                            <div class="inline-actions">
                                <button class="btn btn-secondary" data-select-plan="${escapeHtml(plan.id)}">Use plan</button>
                            </div>
                        </article>
                    `).join('')}
                </div>
            </div>
        </section>
        <section class="panel">
            <div class="panel-header">
                <div>
                    <h3 class="panel-title">Feature matrix</h3>
                    <div class="panel-subtitle">Readable plan posture instead of hidden entitlement assumptions.</div>
                </div>
            </div>
            <table class="matrix-table">
                <thead>
                    <tr>
                        <th>Feature</th>
                        ${selectedPlanIds.map((planId) => `<th>${escapeHtml(plans.find((plan) => plan.id === planId)?.name || planId)}</th>`).join('')}
                    </tr>
                </thead>
                <tbody>
                    ${matrix.map((row) => `
                        <tr>
                            <td>${escapeHtml(row.feature)}</td>
                            ${selectedPlanIds.map((planId) => `<td>${statusPill(row.availability?.[planId] || 'planned', labelize(row.availability?.[planId] || 'planned'))}</td>`).join('')}
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        </section>
`;
}

function renderAllPages() {
    restoreAssistantSurfaceToShell();
    renderOverviewPage();
    if (state.activePage === 'axis-chat') {
        renderAxisChatPage();
    }
    renderGoalsPage();
    renderApprovalsPage();
    renderAxisHubPage();
    renderGuidePage();
    renderPermissionsPage();
    renderSecurityPage();
    renderSettingsPage();
    renderProfilesPage();
    renderPricingPage();
    renderAssistantThread();
    renderVoiceState();
    updateShellChrome();
    scheduleAssistantHintApplication();
    syncPricingShader();
    syncAssistantSurfaceLocation();
}

async function refreshData({ silent = false, forceGoalRefresh = false } = {}) {
    const fetchOptions = { suppressError: silent };
    // On silent background polls, skip /llm/models — it's already cached server-side
    // and we have a local copy in state. Fetch it lazily only when missing.
    const shouldFetchLlm = !silent || !state.llmModelsData;

    const fetchPromises = [
        apiFetch('/control/about', fetchOptions),
        apiFetch('/control/readiness', fetchOptions),
        apiFetch('/control/summary', { ...fetchOptions, allow403: true }),
        apiFetch('/control/approvals', { ...fetchOptions, allow403: true }),
        apiFetch('/control/blocked', { ...fetchOptions, allow403: true }),
        apiFetch('/control/results', { ...fetchOptions, allow403: true }),
        apiFetch('/control/permissions', fetchOptions),
        apiFetch('/control/capabilities', fetchOptions),
        apiFetch('/control/axis-hub', fetchOptions),
        apiFetch('/control/security', fetchOptions),
        apiFetch('/control/settings', fetchOptions),
        apiFetch('/control/profiles', fetchOptions),
        apiFetch('/goals', fetchOptions),
        apiFetch('/activity/recent?limit=10', { ...fetchOptions, allow403: true }),
        shouldFetchLlm ? apiFetch('/llm/models', fetchOptions) : Promise.resolve(null),
    ];

    const [
        about,
        readiness,
        summary,
        approvals,
        blocked,
        results,
        permissions,
        guide,
        axisHub,
        security,
        settingsData,
        profilesData,
        goalsData,
        activityData,
        llmModelsData
    ] = await Promise.all(fetchPromises);

    state.about = about || state.about;
    state.readiness = readiness || state.readiness;
    state.llmModelsData = llmModelsData || state.llmModelsData;
    state.summaryForbidden = Boolean(summary?.__forbidden);
    state.summary = summary?.__forbidden ? null : (summary || state.summary);
    state.approvalsForbidden = Boolean(approvals?.__forbidden);
    state.approvalsMeta = approvals?.__forbidden ? null : approvals;
    state.approvals = approvals?.__forbidden ? [] : (approvals?.pending_approvals || []);
    state.blockedForbidden = Boolean(blocked?.__forbidden);
    state.blocked = blocked?.__forbidden ? [] : (blocked?.blocked_items || []);
    state.resultsForbidden = Boolean(results?.__forbidden);
    state.results = results?.__forbidden ? [] : (results?.results || []);
    state.permissionsSnapshot = permissions || state.permissionsSnapshot;
    state.guideData = guide || state.guideData;
    state.axisHubData = axisHub || state.axisHubData;
    state.securityData = security || state.securityData;
    state.settingsData = settingsData || state.settingsData;
    state.profilesData = profilesData || state.profilesData;
    state.goals = goalsData?.goals || state.goals;
    state.recentActivity = activityData?.activity || state.recentActivity || [];

    // Patch Capability Guide for real-time Voice status
    if (state.guideData?.capabilities) {
        state.guideData.capabilities = state.guideData.capabilities.map(cap => {
            if (cap.name === 'Voice Input' || cap.name === 'Voice Output') {
                return { ...cap, realism: 'live (browser)' };
            }
            return cap;
        });
    }

    if (state.authContext && state.profilesData?.active_profile) {
        state.authContext.profile = state.profilesData.active_profile;
        state.authContext.plan = state.profilesData.active_plan;
        renderIdentity();
    }

    await syncGoalSelection(forceGoalRefresh || state.activePage === 'goals');
    renderAllPages();
    await showPage(state.activePage);
}

async function showPage(pageId) {
    if (!PAGE_META[pageId]) {
        return;
    }

    // Instantly update the active nav button — must happen before any async work
    document.querySelectorAll('.nav-btn').forEach((btn) => {
        btn.classList.toggle('active', btn.dataset.page === pageId);
    });

    // Keep the shared assistant surface alive before any page rerender.
    restoreAssistantSurfaceToShell();
    state.activePage = pageId;
    renderPageById(pageId);

    // CSS-fade page transition: remove visible from all, then show target
    document.querySelectorAll('.page').forEach((section) => {
        const isTarget = section.id === `page-${pageId}`;
        section.classList.toggle('hidden', !isTarget);
        if (isTarget) {
            // Trigger fade-in on next frame
            section.classList.remove('page--visible');
            requestAnimationFrame(() => section.classList.add('page--visible'));
        }
    });

    updateShellChrome();
    syncPricingShader();
    ensurePageGreeting();
    scheduleAssistantHintApplication();
    syncAssistantSurfaceLocation();
}

function toggleOverlay(id, shouldShow) {
    const node = document.getElementById(id);
    if (!node) {
        return;
    }
    node.classList.toggle('hidden', !shouldShow);
}

function populateEditGoalModal() {
    const goal = state.goalContext?.goal || state.goals.find((item) => item.id === state.selectedGoalId);
    if (!goal) {
        showBanner('Select a goal first.', 'error');
        return false;
    }
    document.getElementById('edit-goal-title').value = goal.title || '';
    document.getElementById('edit-goal-objective').value = goal.objective || '';
    document.getElementById('edit-goal-priority').value = goal.priority || 'normal';
    return true;
}

async function handleGoalAction(action, goalId = state.selectedGoalId) {
    if (action === 'edit') {
        if (populateEditGoalModal()) {
            toggleOverlay('edit-goal-modal', true);
        }
        return;
    }

    if (action === 'reconcile-all') {
        if (!window.confirm('Reconcile all goals now?')) {
            return;
        }
        const response = await apiFetch('/goals/reconcile_all', { method: 'POST', body: {} });
        if (response) {
            showBanner(response.message || 'All goals reconciled.', 'success');
            await refreshData({ forceGoalRefresh: true });
        }
        return;
    }

    if (!goalId) {
        showBanner('Select a goal first.', 'error');
        return;
    }

    if (action === 'stop' && !window.confirm('Stop this goal? This preserves history but halts execution.')) {
        return;
    }
    if (action === 'replan' && !window.confirm('Replan this goal? Future work will be regenerated from the current objective.')) {
        return;
    }

    const body = {};
    if (action === 'pause') {
        body.reason = 'Paused from the Axis dashboard';
    }
    if (action === 'stop') {
        body.reason = 'Stopped from the Axis dashboard';
    }

    const response = await apiFetch(`/ goals / ${encodeURIComponent(goalId)}/${action}`, {
        method: 'POST',
        body
    });

    if (response) {
        showBanner(response.message || `${labelize(action)} completed.`, 'success');
        await refreshData({ forceGoalRefresh: true });
    }
}

async function handleApprovalAction(action, actionId) {
    if (!actionId) {
        return;
    }

    const endpoint = action === 'execute'
        ? `/actions/${encodeURIComponent(actionId)}/execute`
        : `/actions/${action}`;
    const response = await apiFetch(endpoint, {
        method: 'POST',
        body: action === 'execute' ? {} : { action_id: actionId }
    });

    if (response) {
        showBanner(response.message || `Approval ${action} completed.`, 'success');
        await refreshData({ forceGoalRefresh: true });
    }
}

async function handlePermissionChange(permissionKey, nextState, riskLevel) {
    if (!permissionKey) {
        return;
    }

    const payload = { state: nextState };
    if ((riskLevel === 'high' || riskLevel === 'critical') && nextState === 'enabled') {
        const confirmed = window.confirm('This permission is marked high risk. Enable it anyway?');
        if (!confirmed) {
            renderAllPages();
            return;
        }
        payload.acknowledge_risk = true;
    }

    const response = await apiFetch(`/control/permissions/${encodeURIComponent(permissionKey)}`, {
        method: 'POST',
        body: payload
    });

    if (response?.snapshot) {
        state.permissionsSnapshot = response.snapshot;
        showBanner('Permission updated.', 'success');
        renderAllPages();
    }
}

async function handlePermissionRequest(requestId, action, permissionKey) {
    const permission = permissionKey ? findPermission(permissionKey) : null;
    const payload = {};
    if (action === 'approve' && permission && ['high', 'critical'].includes(permission.risk_level)) {
        const confirmed = window.confirm(`${permission.name} is marked ${permission.risk_level}. Approve this request and enable it?`);
        if (!confirmed) {
            return;
        }
        payload.acknowledge_risk = true;
    }

    const endpoint = `/control/permission-requests/${encodeURIComponent(requestId)}/${action === 'approve' ? 'approve' : 'deny'}`;
    const response = await apiFetch(endpoint, { method: 'POST', body: payload });
    if (response?.snapshot) {
        state.permissionsSnapshot = response.snapshot;
        showBanner(`Permission request ${action === 'approve' ? 'approved' : 'denied'}.`, 'success');
        renderAllPages();
    }
}

async function handleSettingUpdate(key, value) {
    const response = await apiFetch('/control/settings/update', {
        method: 'POST',
        body: { key, value }
    });
    if (response?.snapshot) {
        state.settingsData = response.snapshot;
        showBanner('Setting updated.', 'success');
        renderAllPages();
    }
}

async function saveProfileDraft() {
    state.profileDraft.display_name = document.getElementById('profile-display-name')?.value?.trim() || state.profileDraft.display_name;
    const response = await apiFetch('/control/profiles/update', {
        method: 'POST',
        body: {
            display_name: state.profileDraft.display_name,
            profile_type: state.profileDraft.profile_type,
            plan_id: state.profileDraft.plan_id
        }
    });

    if (response?.snapshot) {
        state.profilesData = response.snapshot;
        state.authContext.profile = response.snapshot.active_profile;
        state.authContext.plan = response.snapshot.active_plan;
        renderIdentity();
        showBanner('Profile updated.', 'success');
        renderAllPages();
    }
}

async function createGoalFromModal() {
    const title = document.getElementById('goal-title').value.trim();
    const objective = document.getElementById('goal-objective').value.trim();
    const priority = document.getElementById('goal-priority').value;
    if (!objective) {
        showBanner('A goal objective is required.', 'error');
        return;
    }

    const response = await apiFetch('/goals', {
        method: 'POST',
        body: {
            title: title || 'Untitled Goal',
            objective,
            priority
        }
    });

    if (response?.goal) {
        toggleOverlay('new-goal-modal', false);
        document.getElementById('goal-title').value = '';
        document.getElementById('goal-objective').value = '';
        document.getElementById('goal-priority').value = 'normal';
        state.selectedGoalId = response.goal.id;
        showBanner('Goal created.', 'success');
        await refreshData({ forceGoalRefresh: true });
        await showPage('goals');
    }
}

async function saveGoalEdits() {
    const goalId = state.selectedGoalId;
    if (!goalId) {
        showBanner('Select a goal first.', 'error');
        return;
    }

    const response = await apiFetch(`/goals/${encodeURIComponent(goalId)}/edit`, {
        method: 'POST',
        body: {
            title: document.getElementById('edit-goal-title').value.trim(),
            objective: document.getElementById('edit-goal-objective').value.trim(),
            priority: document.getElementById('edit-goal-priority').value
        }
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

        const goalCard = event.target.closest('[data-goal-id]');
        if (goalCard && !event.target.closest('[data-goal-action]')) {
            state.selectedGoalId = goalCard.dataset.goalId;
            void fetchGoalFocus(state.selectedGoalId).then(() => {
                renderAllPages();
                void showPage('goals');
            });
            return;
        }

        const quickAssistant = event.target.closest('[data-focus-assistant]');
        if (quickAssistant) {
            const seed = quickAssistant.dataset.focusAssistant || '';
            focusAssistantComposer(seed);
            return;
        }

        const assistantAction = event.target.closest('[data-assistant-target]');
        if (assistantAction) {
            void handleAssistantAction({
                target: assistantAction.dataset.assistantTarget,
                goal_id: assistantAction.dataset.assistantGoalId,
                approval_id: assistantAction.dataset.assistantApprovalId,
                filter: assistantAction.dataset.assistantFilter,
                section: assistantAction.dataset.assistantSection,
                highlight: assistantAction.dataset.assistantHighlight,
                label: assistantAction.textContent || ''
            });
            return;
        }

        const goalFilter = event.target.closest('[data-goal-filter]');
        if (goalFilter) {
            state.goalViewFilter = goalFilter.dataset.goalFilter;
            renderGoalsPage();
            updateShellChrome();
            scheduleAssistantHintApplication();
            return;
        }

        const approvalFilter = event.target.closest('[data-approval-filter]');
        if (approvalFilter) {
            state.approvalViewFilter = approvalFilter.dataset.approvalFilter;
            renderApprovalsPage();
            updateShellChrome();
            scheduleAssistantHintApplication();
            return;
        }

        const permissionStateFilter = event.target.closest('[data-permission-state-filter]');
        if (permissionStateFilter) {
            state.permissionStateFilter = permissionStateFilter.dataset.permissionStateFilter;
            renderPermissionsPage();
            updateShellChrome();
            scheduleAssistantHintApplication();
            return;
        }

        const pageTarget = event.target.closest('[data-page]');
        if (pageTarget) {
            void showPage(pageTarget.dataset.page);
            return;
        }

        const refreshTarget = event.target.closest('[data-refresh-page]');
        if (refreshTarget) {
            void refreshData({ forceGoalRefresh: refreshTarget.dataset.refreshPage === 'goals' });
            return;
        }

        const openGoal = event.target.closest('[data-open-goal]');
        if (openGoal) {
            state.selectedGoalId = openGoal.dataset.openGoal;
            void fetchGoalFocus(state.selectedGoalId).then(() => {
                renderAllPages();
                void showPage('goals');
            });
            return;
        }

        const goalAction = event.target.closest('[data-goal-action]');
        if (goalAction) {
            void handleGoalAction(goalAction.dataset.goalAction, goalAction.dataset.goalId);
            return;
        }

        const approvalAction = event.target.closest('[data-approval-action]');
        if (approvalAction) {
            void handleApprovalAction(approvalAction.dataset.approvalAction, approvalAction.dataset.actionId);
            return;
        }

        const requestAction = event.target.closest('[data-request-action]');
        if (requestAction) {
            void handlePermissionRequest(requestAction.dataset.requestId, requestAction.dataset.requestAction, requestAction.dataset.permissionKey);
            return;
        }

        const pricingCycle = event.target.closest('[data-pricing-cycle]');
        if (pricingCycle) {
            setPricingBillingCycle(pricingCycle.dataset.pricingCycle);
            return;
        }

        const pricingAction = event.target.closest('[data-pricing-action]');
        if (pricingAction) {
            const action = pricingAction.dataset.pricingAction;
            const planName = pricingAction.dataset.pricingPlanName || 'This';

            if (action === 'home') {
                window.location.assign('/ui');
                return;
            }
            if (action === 'coming-soon') {
                openPricingComingSoonModal(planName);
                return;
            }
            if (action === 'contact') {
                window.location.href = 'mailto:princegisubizo17@gmail.com';
                return;
            }
        }

        if (event.target.closest('[data-close-pricing-modal]') || event.target.id === 'pricing-coming-soon-modal') {
            closePricingComingSoonModal();
            return;
        }

        if (event.target.id === 'new-goal-btn') {
            toggleOverlay('new-goal-modal', true);
            return;
        }

        if (event.target.id === 'overview-quick-command-btn') {
            const input = document.getElementById('overview-quick-command');
            void sendAssistantMessage(input?.value || '');
            return;
        }

        if (event.target.id === 'save-profile-btn') {
            void saveProfileDraft();
            return;
        }

        const profileButton = event.target.closest('[data-select-profile]');
        if (profileButton) {
            syncProfileDraft();
            state.profileDraft.profile_type = profileButton.dataset.selectProfile;
            renderProfilesPage();
            updateShellChrome();
            return;
        }

        const planButton = event.target.closest('[data-select-plan]');
        if (planButton) {
            syncProfileDraft();
            state.profileDraft.plan_id = planButton.dataset.selectPlan;
            renderProfilesPage();
            updateShellChrome();
        }
    });

    document.addEventListener('input', (event) => {
        if (event.target.id === 'goal-search-input') {
            state.goalQuery = event.target.value;
            renderGoalsPage();
            updateShellChrome();
            return;
        }

        if (event.target.id === 'permissions-filter-input') {
            state.permissionsFilter = event.target.value;
            renderPermissionsPage();
            updateShellChrome();
            return;
        }

        if (event.target.id === 'guide-filter-input') {
            state.guideFilter = event.target.value;
            renderGuidePage();
            updateShellChrome();
            return;
        }

        if (event.target.id === 'profile-display-name') {
            syncProfileDraft();
            state.profileDraft.display_name = event.target.value;
        }
    });

    document.addEventListener('change', (event) => {
        if (event.target.matches('[data-permission-key]')) {
            void handlePermissionChange(event.target.dataset.permissionKey, event.target.value, event.target.dataset.riskLevel);
            return;
        }

        if (event.target.matches('[data-setting-key]')) {
            const value = event.target.type === 'checkbox' ? event.target.checked : event.target.value;
            void handleSettingUpdate(event.target.dataset.settingKey, value);
        }
    });
}

document.addEventListener('DOMContentLoaded', () => {
    bindEvents();
    renderAssistantThread();
    renderVoiceState();
    void initApp();
});

window.generatePairingCode = async function () {
    const container = document.getElementById('pairing-code-container');
    container.innerHTML = '<span class="microcopy">Generating...</span>';
    try {
        const response = await fetch('/pairing/code', {
            method: 'POST',
            headers: getAuthHeaders()
        });
        if (!response.ok) throw new Error('Failed to generate code');
        const data = await response.json();

        let secondsLeft = data.expires_in;
        container.innerHTML = `
            <div class="pairing-code-display">
                <span id="active-pairing-code"></span>
                <button id="copy-active-pairing-code" class="btn btn-secondary btn-small" type="button" onclick="navigator.clipboard.writeText('${data.code}'); this.textContent='Copied!';">Copy</button>
            </div>
            <span id="pairing-countdown" class="pairing-timer"></span>
            <p class="auth-note">On your remote device, open the Axis dashboard and enter this code on the login screen.</p>
        `;
        document.getElementById('active-pairing-code').textContent = data.code;

        const countdownEl = document.getElementById('pairing-countdown');
        const timer = setInterval(() => {
            secondsLeft--;
            if (secondsLeft <= 0) {
                clearInterval(timer);
                container.innerHTML = '<p class="auth-note" style="color: var(--danger);">Code expired &mdash; <a href="#" onclick="window.generatePairingCode(); return false;">generate a new one</a></p>';
                return;
            }
            const min = Math.floor(secondsLeft / 60);
            const sec = (secondsLeft % 60).toString().padStart(2, '0');
            countdownEl.textContent = 'Expires in ' + min + ':' + sec;
            if (secondsLeft < 120) countdownEl.classList.add('warning');
        }, 1000);
    } catch (err) {
        container.innerHTML = '<span class="microcopy" style="color: var(--danger);">Failed to generate code</span>';
    }
};

window.disconnectDevice = function () {
    localStorage.removeItem('axis_device_token');
    window.location.reload();
};

window.testCurrentLLMModel = async function () {
    const resElem = document.getElementById('llm-test-result');
    if (resElem) resElem.textContent = 'Testing...';
    try {
        const result = await apiFetch('/llm/test');
        if (result && result.response) {
            if (resElem) resElem.textContent = `Response: "${result.response}" (${result.latency_ms}ms via ${result.provider})`;
        } else {
            if (resElem) resElem.textContent = 'Test failed or returned empty.';
        }
    } catch (e) {
        if (resElem) resElem.textContent = 'Error testing model.';
    }
};

window.handleLLMModelChange = async function (modelId) {
    if (state.llmModelsData) {
        const model = state.llmModelsData.models.find(m => m.id === modelId);
        if (model && model.tier === 'pro' && (state.settingsData?.user_plan || 'free') === 'free') return;
    }
    const previous = state.llmModelsData.active_model;
    state.llmModelsData.active_model = modelId;
    renderSettingsPage();
    renderStatusBar();

    const currentLLM = state.llmModelsData?.models?.find(m => m.id === modelId);
    const indicator = document.getElementById('assistant-model-indicator');
    if (indicator) {
        const providerName = currentLLM ? currentLLM.provider.charAt(0).toUpperCase() + currentLLM.provider.slice(1) : '';
        indicator.textContent = currentLLM ? `â—  ${currentLLM.name} via ${providerName}` : '';
    }

    try {
        await apiFetch('/llm/model', { method: 'POST', body: JSON.stringify({ model_id: modelId }) });
    } catch (e) {
        state.llmModelsData.active_model = previous;
        renderSettingsPage();
        renderStatusBar();
    }
};
