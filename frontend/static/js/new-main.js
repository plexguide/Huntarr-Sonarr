/**
 * Huntarr - New UI Implementation
 * Main JavaScript file for handling UI interactions and API communication
 */

/**
 * Huntarr - New UI Implementation
 * Main JavaScript file for handling UI interactions and API communication
 */

let huntarrUI = {
    // Current state
    currentSection: 'home', // Default section
    currentHistoryApp: 'all', // Default history app
    currentLogApp: 'all', // Default log app for compatibility
    autoScroll: true,
    eventSources: {}, // Event sources for compatibility
    isLoadingStats: false, // Flag to prevent multiple simultaneous stats requests
    configuredApps: {
        sonarr: false,
        radarr: false,
        lidarr: false,
        readarr: false, // Added readarr
        whisparr: false, // Added whisparr
        eros: false, // Added eros
        swaparr: false // Added swaparr
    },
    originalSettings: {}, // Store the full original settings object
    settingsChanged: false, // Legacy flag (auto-save enabled)
    
    // Logo URL
    logoUrl: './static/logo/256.png',
    
    // Element references
    elements: {},
    
    // Initialize the application
    init: function() {
        console.log('[huntarrUI] Initializing UI...');
        
        // Skip initialization on login page
        const isLoginPage = document.querySelector('.login-container, #loginForm, .login-form');
        if (isLoginPage) {
            console.log('[huntarrUI] Login page detected, skipping full initialization');
            return;
        }
        
        // Cache frequently used DOM elements
        this.cacheElements();
        
        // Register event handlers
        this.setupEventListeners();
        this.setupLogoHandling();
        // Auto-save enabled - no unsaved changes handler needed
        
        // Check if Low Usage Mode is enabled BEFORE loading stats to avoid race condition
        this.checkLowUsageMode().then(() => {
            // Initialize media stats after low usage mode is determined
            if (window.location.pathname === '/') {
                this.loadMediaStats();
            }
        }).catch(() => {
            // If low usage mode check fails, still load stats
            if (window.location.pathname === '/') {
                this.loadMediaStats();
            }
        });
        
        // Initial navigation based on hash
        this.handleHashNavigation(window.location.hash);
        
        // Remove initial sidebar hiding style
        const initialSidebarStyle = document.getElementById('initial-sidebar-state');
        if (initialSidebarStyle) {
            initialSidebarStyle.remove();
        }
        
        // Check which sidebar should be shown based on current section
        const huntarrSections = ['sonarr', 'radarr', 'lidarr', 'readarr', 'whisparr', 'eros'];
        const requestarrSections = ['requestarr', 'requestarr-history'];
        const settingsSections = ['settings', 'scheduling', 'notifications', 'user'];
        
        if (huntarrSections.includes(this.currentSection)) {
            this.showHuntarrSidebar();
        } else if (requestarrSections.includes(this.currentSection)) {
            this.showRequestarrSidebar();
        } else if (settingsSections.includes(this.currentSection)) {
            this.showSettingsSidebar();
        } else {
            // Show main sidebar by default and clear settings sidebar preference
            localStorage.removeItem('huntarr-settings-sidebar');
            this.showMainSidebar();
        }
        
        // Auto-save enabled - no unsaved changes handler needed
        
        // Load username
        this.loadUsername();
        
        // Apply any preloaded theme immediately to avoid flashing
        const prefersDarkMode = localStorage.getItem('huntarr-dark-mode') === 'true';
        if (prefersDarkMode) {
            document.body.classList.add('dark-theme');
        }

        const resetButton = document.getElementById('reset-stats');
        if (resetButton) {
            resetButton.addEventListener('click', (e) => {
                e.preventDefault();
                this.resetMediaStats();
            });
        }
        // Ensure logo is visible immediately
        this.logoUrl = localStorage.getItem('huntarr-logo-url') || this.logoUrl;
        
        // Load current version
        this.loadCurrentVersion(); // Load current version
        
        // Load latest version from GitHub
        this.loadLatestVersion(); // Load latest version from GitHub
        
        // Load latest beta version from GitHub
        this.loadBetaVersion(); // Load latest beta version from GitHub
        
        // Load GitHub star count
        this.loadGitHubStarCount(); // Load GitHub star count
        
        // Preload stateful management info so it's ready when needed
        this.loadStatefulInfo();
        
        // Ensure logo is applied
        if (typeof window.applyLogoToAllElements === 'function') {
            window.applyLogoToAllElements();
        }
        
        // Initialize instance event handlers
        this.setupInstanceEventHandlers();
        
        // Setup navigation for sidebars
        this.setupRequestarrNavigation();
        this.setupSettingsNavigation();
        this.setupHuntarrNavigation();
        
        // Auto-save enabled - no unsaved changes handler needed
        
        // Setup Swaparr components
        this.setupSwaparrResetCycle();
        
        // Setup Swaparr status polling (refresh every 30 seconds)
        this.setupSwaparrStatusPolling();
        
        // Make dashboard visible after initialization to prevent FOUC
        setTimeout(() => {
            this.showDashboard();
        }, 50); // Reduced from implicit longer delay
    },
    
    // Cache DOM elements for better performance
    cacheElements: function() {
        // Navigation
        this.elements.navItems = document.querySelectorAll('.nav-item');
        this.elements.homeNav = document.getElementById('homeNav');
        this.elements.logsNav = document.getElementById('logsNav');
        this.elements.huntManagerNav = document.getElementById('huntManagerNav');
        this.elements.settingsNav = document.getElementById('settingsNav');
        this.elements.userNav = document.getElementById('userNav');
        
        // Sections
        this.elements.sections = document.querySelectorAll('.content-section');
        this.elements.homeSection = document.getElementById('homeSection');
        this.elements.logsSection = document.getElementById('logsSection');
        this.elements.huntManagerSection = document.getElementById('huntManagerSection');
        this.elements.settingsSection = document.getElementById('settingsSection');
        this.elements.schedulingSection = document.getElementById('schedulingSection');
        
        // History dropdown elements
        this.elements.historyOptions = document.querySelectorAll('.history-option'); // History dropdown options
        this.elements.currentHistoryApp = document.getElementById('current-history-app'); // Current history app text
        this.elements.historyDropdownBtn = document.querySelector('.history-dropdown-btn'); // History dropdown button
        this.elements.historyDropdownContent = document.querySelector('.history-dropdown-content'); // History dropdown content
        this.elements.historyPlaceholderText = document.getElementById('history-placeholder-text'); // Placeholder text for history
        
        // Settings dropdown elements
        this.elements.settingsOptions = document.querySelectorAll('.settings-option'); // New: settings dropdown options
        this.elements.currentSettingsApp = document.getElementById('current-settings-app'); // New: current settings app text
        this.elements.settingsDropdownBtn = document.querySelector('.settings-dropdown-btn'); // New: settings dropdown button
        this.elements.settingsDropdownContent = document.querySelector('.settings-dropdown-content'); // New: dropdown content
        
        this.elements.appSettingsPanels = document.querySelectorAll('.app-settings-panel');
        
        // Settings
        // Save button removed for auto-save
        
        // Status elements
        this.elements.sonarrHomeStatus = document.getElementById('sonarrHomeStatus');
        this.elements.radarrHomeStatus = document.getElementById('radarrHomeStatus');
        this.elements.lidarrHomeStatus = document.getElementById('lidarrHomeStatus');
        this.elements.readarrHomeStatus = document.getElementById('readarrHomeStatus'); // Added readarr
        this.elements.whisparrHomeStatus = document.getElementById('whisparrHomeStatus'); // Added whisparr
        this.elements.erosHomeStatus = document.getElementById('erosHomeStatus'); // Added eros
        
        // Actions
        this.elements.startHuntButton = document.getElementById('startHuntButton');
        this.elements.stopHuntButton = document.getElementById('stopHuntButton');
        
        // Logout
        this.elements.logoutLink = document.getElementById('logoutLink'); // Added logout link
    },
    
    // Set up event listeners
    setupEventListeners: function() {
        // Navigation
        document.addEventListener('click', (e) => {
            // Navigation link handling
            if (e.target.matches('.nav-link') || e.target.closest('.nav-link')) {
                const link = e.target.matches('.nav-link') ? e.target : e.target.closest('.nav-link');
                e.preventDefault();
                this.handleNavigation(e);
            }
            
            // Handle cycle reset button clicks
            if (e.target.matches('.cycle-reset-button') || e.target.closest('.cycle-reset-button')) {
                const button = e.target.matches('.cycle-reset-button') ? e.target : e.target.closest('.cycle-reset-button');
                const app = button.dataset.app;
                if (app) {
                    this.resetAppCycle(app, button);
                }
            }
        });
        
        // History dropdown toggle
        if (this.elements.historyDropdownBtn) {
            this.elements.historyDropdownBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation(); // Prevent event bubbling
                
                // Toggle this dropdown
                this.elements.historyDropdownContent.classList.toggle('show');
            });
            
            // Close dropdown when clicking outside
            document.addEventListener('click', (e) => {
                if (!e.target.closest('.history-dropdown') && this.elements.historyDropdownContent.classList.contains('show')) {
                    this.elements.historyDropdownContent.classList.remove('show');
                }
            });
        }
        
        // History options
        this.elements.historyOptions.forEach(option => {
            option.addEventListener('click', (e) => this.handleHistoryOptionChange(e));
        });
        
        // Settings dropdown toggle
        if (this.elements.settingsDropdownBtn) {
            this.elements.settingsDropdownBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation(); // Prevent event bubbling
                
                // Toggle this dropdown
                this.elements.settingsDropdownContent.classList.toggle('show');
            });
            
            // Close dropdown when clicking outside
            document.addEventListener('click', (e) => {
                if (!e.target.closest('.settings-dropdown') && this.elements.settingsDropdownContent.classList.contains('show')) {
                    this.elements.settingsDropdownContent.classList.remove('show');
                }
            });
        }
        
        // Settings options
        this.elements.settingsOptions.forEach(option => {
            option.addEventListener('click', (e) => this.handleSettingsOptionChange(e));
        });
        
        // Save settings button
        // Save button removed for auto-save
        
        // Test notification button (delegated event listener for dynamic content)
        document.addEventListener('click', (e) => {
            if (e.target.id === 'testNotificationBtn' || e.target.closest('#testNotificationBtn')) {
                this.testNotification();
            }
        });
        
        // Start hunt button
        if (this.elements.startHuntButton) {
            this.elements.startHuntButton.addEventListener('click', () => this.startHunt());
        }
        
        // Stop hunt button
        if (this.elements.stopHuntButton) {
            this.elements.stopHuntButton.addEventListener('click', () => this.stopHunt());
        }
        
        // Logout button
        if (this.elements.logoutLink) {
            this.elements.logoutLink.addEventListener('click', (e) => this.logout(e));
        }
        
        // Requestarr navigation
        this.setupRequestarrNavigation();
        
        // Dark mode toggle
        const darkModeToggle = document.getElementById('darkModeToggle');
        if (darkModeToggle) {
            const prefersDarkMode = localStorage.getItem('huntarr-dark-mode') === 'true';
            darkModeToggle.checked = prefersDarkMode;
            
            darkModeToggle.addEventListener('change', function() {
                const isDarkMode = this.checked;
                document.body.classList.toggle('dark-theme', isDarkMode);
                localStorage.setItem('huntarr-dark-mode', isDarkMode);
            });
        }
        
        // Settings auto-save setup
        this.setupSettingsAutoSave();
        
        // Auto-save enabled - no need to warn about unsaved changes
        
        // Stateful management reset button
        const resetStatefulBtn = document.getElementById('reset_stateful_btn');
        if (resetStatefulBtn) {
            resetStatefulBtn.addEventListener('click', () => this.handleStatefulReset());
        }
        
        // Stateful management hours input
        const statefulHoursInput = document.getElementById('stateful_management_hours');
        if (statefulHoursInput) {
            statefulHoursInput.addEventListener('change', () => {
                this.updateStatefulExpirationOnUI();
            });
        }
        
        // Handle window hash change
        window.addEventListener('hashchange', () => this.handleHashNavigation(window.location.hash)); // Ensure hash is passed

        // Settings form delegation - now triggers auto-save
        const settingsFormContainer = document.querySelector('.settings-form');
        if (settingsFormContainer) {
            settingsFormContainer.addEventListener('input', (event) => {
                if (event.target.closest('.app-settings-panel.active')) {
                    // Check if the target is an input, select, or textarea within the active panel
                    if (event.target.matches('input, select, textarea')) {
                        this.triggerSettingsAutoSave(); // Trigger auto-save instead of marking changed
                    }
                }
            });
             settingsFormContainer.addEventListener('change', (event) => {
                 if (event.target.closest('.app-settings-panel.active')) {
                    // Handle changes for checkboxes and selects that use 'change' event
                    if (event.target.matches('input[type="checkbox"], select')) {
                         this.triggerSettingsAutoSave(); // Trigger auto-save instead of marking changed
                    }
                 }
            });
        }

        // Auto-save enabled - no need for beforeunload warnings

        // Initial setup based on hash or default to home
        const initialHash = window.location.hash || '#home';
        this.handleHashNavigation(initialHash);

        // HISTORY: Listen for change on #historyAppSelect
        const historyAppSelect = document.getElementById('historyAppSelect');
        if (historyAppSelect) {
            historyAppSelect.addEventListener('change', (e) => {
                const app = e.target.value;
                this.handleHistoryOptionChange(app);
            });
        }
    },
    
    // Setup logo handling to prevent flashing during navigation
    setupLogoHandling: function() {
        // Get the logo image
        const logoImg = document.querySelector('.sidebar .logo');
        if (logoImg) {
            // Cache the source
            this.logoSrc = logoImg.src;
            
            // Ensure it's fully loaded
            if (!logoImg.complete) {
                logoImg.onload = () => {
                    // Once loaded, store the source
                    this.logoSrc = logoImg.src;
                };
            }
        }
        
        // Also add event listener to ensure logo is preserved during navigation
        window.addEventListener('beforeunload', () => {
            // Store logo src in session storage to persist across page loads
            if (this.logoSrc) {
                sessionStorage.setItem('huntarr-logo-src', this.logoSrc);
            }
        });
    },
    
    // Navigation handling
    handleNavigation: function(e) {
        const targetElement = e.currentTarget; // Get the clicked nav item
        const href = targetElement.getAttribute('href');
        const target = targetElement.getAttribute('target');
        
        // Allow links with target="_blank" to open in a new window (return early)
        if (target === '_blank') {
            return; // Let the default click behavior happen
        }
        
        // For all other links, prevent default behavior and handle internally
        e.preventDefault();

        if (!href) return; // Exit if no href

        let targetSection = null;
        let isInternalLink = href.startsWith('#');

        if (isInternalLink) {
            targetSection = href.substring(1) || 'home'; // Get section from hash, default to 'home' if only '#' 
        } else {
             // Handle external links (like /user) or non-hash links if needed
             // For now, assume non-hash links navigate away
        }

        // Auto-save enabled - no need to check for unsaved changes when navigating
        
        // Add special handling for apps section - clear global app module flags
        if (this.currentSection === 'apps' && targetSection !== 'apps') {
            // Reset the app module flags when navigating away
            if (window._appsModuleLoaded) {
                window._appsSuppressChangeDetection = true;
                if (window.appsModule && typeof window.appsModule.settingsChanged !== 'undefined') {
                    window.appsModule.settingsChanged = false;
                }
                // Schedule ending suppression to avoid any edge case issues
                setTimeout(() => {
                    window._appsSuppressChangeDetection = false;
                }, 1000);
            }
        }

        // Proceed with navigation
        if (isInternalLink) {
            window.location.hash = href; // Change hash to trigger handleHashNavigation
        } else {
            // If it's an external link (like /user), just navigate normally
            window.location.href = href;
        }
    },
    
    handleHashNavigation: function(hash) {
        const section = hash.substring(1) || 'home';
        this.switchSection(section);
    },
    
    switchSection: function(section) {
        // Update active section
        this.elements.sections.forEach(s => {
            s.classList.remove('active');
            s.style.display = 'none';
        });
        
        // Additionally, make sure scheduling section is completely hidden
        if (section !== 'scheduling' && this.elements.schedulingSection) {
            this.elements.schedulingSection.style.display = 'none';
        }
        
        // Update navigation
        this.elements.navItems.forEach(item => {
            item.classList.remove('active');
        });
        
        // Show selected section
        let newTitle = 'Home'; // Default title
        const sponsorsSection = document.getElementById('sponsorsSection'); // Get sponsors section element
        const sponsorsNav = document.getElementById('sponsorsNav'); // Get sponsors nav element

        if (section === 'home' && this.elements.homeSection) {
            this.elements.homeSection.classList.add('active');
            this.elements.homeSection.style.display = 'block';
            if (this.elements.homeNav) this.elements.homeNav.classList.add('active');
            newTitle = 'Home';
            this.currentSection = 'home';
            
            // Show main sidebar when returning to home and clear settings sidebar preference
            localStorage.removeItem('huntarr-settings-sidebar');
            this.showMainSidebar();
            
            // Disconnect logs if switching away from logs
            this.disconnectAllEventSources(); 
            // Check app connections when returning to home page to update status
            this.checkAppConnections();
            // Load Swaparr status
            this.loadSwaparrStatus();
            // Stats are already loaded, no need to reload unless data changed
            // this.loadMediaStats();
        } else if (section === 'logs' && this.elements.logsSection) {
            this.elements.logsSection.classList.add('active');
            this.elements.logsSection.style.display = 'block';
            if (this.elements.logsNav) this.elements.logsNav.classList.add('active');
            newTitle = 'Logs';
            this.currentSection = 'logs';
            
            // Show main sidebar for main sections and clear settings sidebar preference
            localStorage.removeItem('huntarr-settings-sidebar');
            this.showMainSidebar();
            
            // Comprehensive LogsModule debugging
            console.log('[huntarrUI] === LOGS SECTION DEBUG START ===');
            console.log('[huntarrUI] window object keys:', Object.keys(window).filter(k => k.includes('Log')));
            console.log('[huntarrUI] window.LogsModule exists:', !!window.LogsModule);
            console.log('[huntarrUI] window.LogsModule type:', typeof window.LogsModule);
            
            if (window.LogsModule) {
                console.log('[huntarrUI] LogsModule methods:', Object.keys(window.LogsModule));
                console.log('[huntarrUI] LogsModule.init type:', typeof window.LogsModule.init);
                console.log('[huntarrUI] LogsModule.connectToLogs type:', typeof window.LogsModule.connectToLogs);
                
                try {
                    console.log('[huntarrUI] Calling LogsModule.init()...');
                    window.LogsModule.init();
                    console.log('[huntarrUI] LogsModule.init() completed successfully');
                    
                    // LogsModule will handle its own connection - don't interfere with pagination
                    console.log('[huntarrUI] LogsModule initialized - letting it handle its own connections');
                } catch (error) {
                    console.error('[huntarrUI] Error during LogsModule calls:', error);
                }
            } else {
                console.error('[huntarrUI] LogsModule not found - logs functionality unavailable');
                console.log('[huntarrUI] Available window properties:', Object.keys(window).slice(0, 20));
            }
            console.log('[huntarrUI] === LOGS SECTION DEBUG END ===');
        } else if (section === 'hunt-manager' && document.getElementById('huntManagerSection')) {
            document.getElementById('huntManagerSection').classList.add('active');
            document.getElementById('huntManagerSection').style.display = 'block';
            if (document.getElementById('huntManagerNav')) document.getElementById('huntManagerNav').classList.add('active');
            newTitle = 'Hunt Manager';
            this.currentSection = 'hunt-manager';
            
            // Show main sidebar for main sections and clear settings sidebar preference
            localStorage.removeItem('huntarr-settings-sidebar');
            this.showMainSidebar();
            
            // Load hunt manager data if the module exists
            if (typeof huntManagerModule !== 'undefined') {
                huntManagerModule.refresh();
            }
        } else if (section === 'requestarr' && document.getElementById('requestarr-section')) {
            document.getElementById('requestarr-section').classList.add('active');
            document.getElementById('requestarr-section').style.display = 'block';
            if (document.getElementById('requestarrNav')) document.getElementById('requestarrNav').classList.add('active');
            newTitle = 'Requestarr';
            this.currentSection = 'requestarr';
            
            // Switch to Requestarr sidebar
            this.showRequestarrSidebar();
            
            // Show home view by default
            this.showRequestarrView('home');
            
            // Initialize requestarr module if it exists
            if (typeof window.requestarrModule !== 'undefined') {
                window.requestarrModule.loadInstances();
            }
        } else if (section === 'requestarr-history' && document.getElementById('requestarr-section')) {
            document.getElementById('requestarr-section').classList.add('active');
            document.getElementById('requestarr-section').style.display = 'block';
            newTitle = 'Requestarr - History';
            this.currentSection = 'requestarr-history';
            
            // Switch to Requestarr sidebar
            this.showRequestarrSidebar();
            
            // Show history view
            this.showRequestarrView('history');
        } else if (section === 'huntarr' && document.getElementById('appsSection')) {
            // Legacy apps section - redirect to Huntarr sidebar
            this.showHuntarrSidebar();
            // Default to Sonarr
            window.location.hash = '#sonarr';
            return;
        } else if (section === 'apps' && document.getElementById('appsSection')) {
            document.getElementById('appsSection').classList.add('active');
            document.getElementById('appsSection').style.display = 'block';
            if (document.getElementById('appsNav')) document.getElementById('appsNav').classList.add('active');
            newTitle = 'Apps';
            this.currentSection = 'apps';
            
            // Show main sidebar for main sections and clear settings sidebar preference
            localStorage.removeItem('huntarr-settings-sidebar');
            this.showMainSidebar();
            
            // Load app connections when switching to Apps
            this.checkAppConnections();
        } else if (section === 'sonarr' && document.getElementById('sonarrSection')) {
            document.getElementById('sonarrSection').classList.add('active');
            document.getElementById('sonarrSection').style.display = 'block';
            newTitle = 'Sonarr';
            this.currentSection = 'sonarr';
            
            // Show Huntarr sidebar and stay there
            this.showHuntarrSidebar();
            
            // Load Sonarr app settings
            this.loadIndividualApp('sonarr');
        } else if (section === 'radarr' && document.getElementById('radarrSection')) {
            document.getElementById('radarrSection').classList.add('active');
            document.getElementById('radarrSection').style.display = 'block';
            newTitle = 'Radarr';
            this.currentSection = 'radarr';
            
            // Show Huntarr sidebar and stay there
            this.showHuntarrSidebar();
            
            // Load Radarr app settings
            this.loadIndividualApp('radarr');
        } else if (section === 'lidarr' && document.getElementById('lidarrSection')) {
            document.getElementById('lidarrSection').classList.add('active');
            document.getElementById('lidarrSection').style.display = 'block';
            newTitle = 'Lidarr';
            this.currentSection = 'lidarr';
            
            // Show Huntarr sidebar and stay there
            this.showHuntarrSidebar();
            
            // Load Lidarr app settings
            this.loadIndividualApp('lidarr');
        } else if (section === 'readarr' && document.getElementById('readarrSection')) {
            document.getElementById('readarrSection').classList.add('active');
            document.getElementById('readarrSection').style.display = 'block';
            newTitle = 'Readarr';
            this.currentSection = 'readarr';
            
            // Show Huntarr sidebar and stay there
            this.showHuntarrSidebar();
            
            // Load Readarr app settings
            this.loadIndividualApp('readarr');
        } else if (section === 'whisparr' && document.getElementById('whisparrSection')) {
            document.getElementById('whisparrSection').classList.add('active');
            document.getElementById('whisparrSection').style.display = 'block';
            newTitle = 'Whisparr v2';
            this.currentSection = 'whisparr';
            
            // Show Huntarr sidebar and stay there
            this.showHuntarrSidebar();
            
            // Load Whisparr app settings
            this.loadIndividualApp('whisparr');
        } else if (section === 'eros' && document.getElementById('erosSection')) {
            document.getElementById('erosSection').classList.add('active');
            document.getElementById('erosSection').style.display = 'block';
            newTitle = 'Whisparr v3 (Eros)';
            this.currentSection = 'eros';
            
            // Show Huntarr sidebar and stay there
            this.showHuntarrSidebar();
            
            // Load Eros app settings
            this.loadIndividualApp('eros');
        } else if (section === 'swaparr' && document.getElementById('swaparrSection')) {
            document.getElementById('swaparrSection').classList.add('active');
            document.getElementById('swaparrSection').style.display = 'block';
            newTitle = 'Swaparr';
            this.currentSection = 'swaparr';
            
            // Show main sidebar for main sections and clear settings sidebar preference
            localStorage.removeItem('huntarr-settings-sidebar');
            this.showMainSidebar();
            
            // Load Swaparr app settings
            this.loadIndividualApp('swaparr');
        } else if (section === 'settings' && document.getElementById('settingsSection')) {
            document.getElementById('settingsSection').classList.add('active');
            document.getElementById('settingsSection').style.display = 'block';
            if (document.getElementById('settingsNav')) document.getElementById('settingsNav').classList.add('active');
            newTitle = 'Settings';
            this.currentSection = 'settings';
            
            // Switch to Settings sidebar
            this.showSettingsSidebar();
            
            // Set localStorage to maintain Settings sidebar preference
            localStorage.setItem('huntarr-settings-sidebar', 'true');
            
            // Initialize settings if not already done
            this.initializeSettings();
        } else if (section === 'scheduling' && document.getElementById('schedulingSection')) {
            document.getElementById('schedulingSection').classList.add('active');
            document.getElementById('schedulingSection').style.display = 'block';
            if (document.getElementById('schedulingNav')) document.getElementById('schedulingNav').classList.add('active');
            newTitle = 'Scheduling';
            this.currentSection = 'scheduling';
            
            // Switch to Settings sidebar for scheduling
            this.showSettingsSidebar();
            
            // Set localStorage to maintain Settings sidebar preference
            localStorage.setItem('huntarr-settings-sidebar', 'true');
        } else if (section === 'notifications' && document.getElementById('notificationsSection')) {
            document.getElementById('notificationsSection').classList.add('active');
            document.getElementById('notificationsSection').style.display = 'block';
            if (document.getElementById('settingsNotificationsNav')) document.getElementById('settingsNotificationsNav').classList.add('active');
            newTitle = 'Notifications';
            this.currentSection = 'notifications';
            
            // Switch to Settings sidebar for notifications
            this.showSettingsSidebar();
            
            // Set localStorage to maintain Settings sidebar preference
            localStorage.setItem('huntarr-settings-sidebar', 'true');
            
            // Initialize notifications settings if not already done
            this.initializeNotifications();
        } else if (section === 'user' && document.getElementById('userSection')) {
            document.getElementById('userSection').classList.add('active');
            document.getElementById('userSection').style.display = 'block';
            if (document.getElementById('userNav')) document.getElementById('userNav').classList.add('active');
            newTitle = 'User';
            this.currentSection = 'user';
            
            // Switch to Settings sidebar for user
            this.showSettingsSidebar();
            
            // Set localStorage to maintain Settings sidebar preference
            localStorage.setItem('huntarr-settings-sidebar', 'true');
            
            // Initialize user module if not already done
            if (typeof window.UserModule !== 'undefined' && !this.userModule) {
                this.userModule = new window.UserModule();
            }
        } else {
            // Default to home if section is unknown or element missing
            if (this.elements.homeSection) {
                this.elements.homeSection.classList.add('active');
                this.elements.homeSection.style.display = 'block';
            }
            if (this.elements.homeNav) this.elements.homeNav.classList.add('active');
            newTitle = 'Home';
            this.currentSection = 'home';
            
            // Show main sidebar and clear settings sidebar preference
            localStorage.removeItem('huntarr-settings-sidebar');
            this.showMainSidebar();
        }

        // Disconnect logs when switching away from logs section
        if (this.currentSection !== 'logs' && window.LogsModule) {
            window.LogsModule.disconnectAllEventSources();
        }

        // Update the page title
        const pageTitleElement = document.getElementById('currentPageTitle');
        if (pageTitleElement) {
            pageTitleElement.textContent = newTitle;
        } else {
            console.warn("[huntarrUI] currentPageTitle element not found during section switch.");
        }
    },
    
    // Simple event source disconnection for compatibility
    disconnectAllEventSources: function() {
        // Delegate to LogsModule if it exists
        if (window.LogsModule && typeof window.LogsModule.disconnectAllEventSources === 'function') {
            window.LogsModule.disconnectAllEventSources();
        }
        // Clear local references
        this.eventSources = {};
    },
    
    // App tab switching
    handleAppTabChange: function(e) {
        const app = e.target.getAttribute('data-app');
        if (!app) return;
        
        // Update active tab
        this.elements.appTabs.forEach(tab => {
            tab.classList.remove('active');
        });
        e.target.classList.add('active');
        
        // Let LogsModule handle app switching to preserve pagination
        this.currentApp = app;
        if (window.LogsModule && typeof window.LogsModule.handleAppChange === 'function') {
            window.LogsModule.handleAppChange(app);
        }
    },
    
    // Log option dropdown handling - Delegated to LogsModule
    // (Removed to prevent conflicts with LogsModule.handleLogOptionChange)
    
    // History option dropdown handling
    handleHistoryOptionChange: function(app) {
        if (app && app.target && typeof app.target.value === 'string') {
            app = app.target.value;
        } else if (app && app.target && typeof app.target.getAttribute === 'function') {
            app = app.target.getAttribute('data-app');
        }
        if (!app || app === this.currentHistoryApp) return;
        // Update the select value
        const historyAppSelect = document.getElementById('historyAppSelect');
        if (historyAppSelect) historyAppSelect.value = app;
        // Update the current history app text with proper capitalization
        let displayName = app.charAt(0).toUpperCase() + app.slice(1);
        if (app === 'whisparr') displayName = 'Whisparr V2';
        else if (app === 'eros') displayName = 'Whisparr V3';
        if (this.elements.currentHistoryApp) this.elements.currentHistoryApp.textContent = displayName;
        // Update the placeholder text
        this.updateHistoryPlaceholder(app);
        // Switch to the selected app history
        this.currentHistoryApp = app;
    },
    
    // Update the history placeholder text based on the selected app
    updateHistoryPlaceholder: function(app) {
        if (!this.elements.historyPlaceholderText) return;
        
        let message = "";
        if (app === 'all') {
            message = "The History feature will be available in a future update. Stay tuned for enhancements that will allow you to view your media processing history.";
        } else {
            let displayName = this.capitalizeFirst(app);
            message = `The ${displayName} History feature is under development and will be available in a future update. You'll be able to track your ${displayName} media processing history here.`;
        }
        
        this.elements.historyPlaceholderText.textContent = message;
    },
    
    // Settings option handling
    handleSettingsOptionChange: function(e) {
        e.preventDefault(); // Prevent default anchor behavior
        
        const app = e.target.getAttribute('data-app');
        if (!app || app === this.currentSettingsApp) return; // Do nothing if same tab clicked
        
        // Update active option
        this.elements.settingsOptions.forEach(option => {
            option.classList.remove('active');
        });
        e.target.classList.add('active');
        
        // Update the current settings app text with proper capitalization
        let displayName = app.charAt(0).toUpperCase() + app.slice(1);
        this.elements.currentSettingsApp.textContent = displayName;
        
        // Close the dropdown
        this.elements.settingsDropdownContent.classList.remove('show');
        
        // Hide all settings panels
        this.elements.appSettingsPanels.forEach(panel => {
            panel.classList.remove('active');
            panel.style.display = 'none';
        });
        
        // Show the selected app's settings panel
        const selectedPanel = document.getElementById(app + 'Settings');
        if (selectedPanel) {
            selectedPanel.classList.add('active');
            selectedPanel.style.display = 'block';
        }
        
        this.currentSettingsTab = app;
        console.log(`[huntarrUI] Switched settings tab to: ${this.currentSettingsTab}`); // Added logging
    },
    
    // Compatibility methods that delegate to LogsModule
    connectToLogs: function() {
        if (window.LogsModule && typeof window.LogsModule.connectToLogs === 'function') {
            window.LogsModule.connectToLogs();
        }
    },
    
    clearLogs: function() {
        if (window.LogsModule && typeof window.LogsModule.clearLogs === 'function') {
            window.LogsModule.clearLogs();
        }
    },
    
    // Insert log entry in chronological order to maintain proper reverse time sorting
    insertLogInChronologicalOrder: function(newLogEntry) {
        if (!this.elements.logsContainer || !newLogEntry) return;
        
        // Parse timestamp from the new log entry
        const newTimestamp = this.parseLogTimestamp(newLogEntry);
        
        // If we can't parse the timestamp, just append to the end
        if (!newTimestamp) {
            this.elements.logsContainer.appendChild(newLogEntry);
            return;
        }
        
        // Get all existing log entries
        const existingEntries = Array.from(this.elements.logsContainer.children);
        
        // If no existing entries, just add the new one
        if (existingEntries.length === 0) {
            this.elements.logsContainer.appendChild(newLogEntry);
            return;
        }
        
        // Find the correct position to insert (maintaining chronological order)
        // Since CSS will reverse the order, we want older entries first in DOM
        let insertPosition = null;
        
        for (let i = 0; i < existingEntries.length; i++) {
            const existingTimestamp = this.parseLogTimestamp(existingEntries[i]);
            
            // If we can't parse existing timestamp, skip it
            if (!existingTimestamp) continue;
            
            // If new log is newer than existing log, insert before it
            if (newTimestamp > existingTimestamp) {
                insertPosition = existingEntries[i];
                break;
            }
        }
        
        // Insert in the correct position
        if (insertPosition) {
            this.elements.logsContainer.insertBefore(newLogEntry, insertPosition);
        } else {
            // If no position found, append to the end (oldest)
            this.elements.logsContainer.appendChild(newLogEntry);
        }
    },
    
    // Parse timestamp from log entry DOM element
    parseLogTimestamp: function(logEntry) {
        if (!logEntry) return null;
        
        try {
            // Look for timestamp elements
            const dateSpan = logEntry.querySelector('.log-timestamp .date');
            const timeSpan = logEntry.querySelector('.log-timestamp .time');
            
            if (!dateSpan || !timeSpan) return null;
            
            const dateText = dateSpan.textContent.trim();
            const timeText = timeSpan.textContent.trim();
            
            // Skip invalid timestamps
            if (!dateText || !timeText || dateText === '--' || timeText === '--:--:--') {
                return null;
            }
            
            // Combine date and time into a proper timestamp
            const timestampString = `${dateText} ${timeText}`;
            const timestamp = new Date(timestampString);
            
            // Return timestamp if valid, null otherwise
            return isNaN(timestamp.getTime()) ? null : timestamp;
        } catch (error) {
            console.warn('[huntarrUI] Error parsing log timestamp:', error);
            return null;
        }
    },
    
    // Search logs functionality with performance optimization
    searchLogs: function() {
        if (!this.elements.logsContainer || !this.elements.logSearchInput) return;
        
        const searchText = this.elements.logSearchInput.value.trim().toLowerCase();
        
        // If empty search, reset everything
        if (!searchText) {
            this.clearLogSearch();
            return;
        }
        
        // Show clear search button when searching
        if (this.elements.clearSearchButton) {
            this.elements.clearSearchButton.style.display = 'block';
        }
        
        // Filter log entries based on search text - with performance optimization
        const logEntries = Array.from(this.elements.logsContainer.querySelectorAll('.log-entry'));
        let matchCount = 0;
        
        // Set a limit for highlighting to prevent browser lockup
        const MAX_ENTRIES_TO_PROCESS = 300;
        const processedLogEntries = logEntries.slice(0, MAX_ENTRIES_TO_PROCESS);
        const remainingCount = Math.max(0, logEntries.length - MAX_ENTRIES_TO_PROCESS);
        
        // Process in batches to prevent UI lockup
        processedLogEntries.forEach((entry, index) => {
            const entryText = entry.textContent.toLowerCase();
            
            // Show/hide based on search match
            if (entryText.includes(searchText)) {
                entry.style.display = '';
                matchCount++;
                
                // Simple highlight by replacing HTML - much more performant
                this.simpleHighlightMatch(entry, searchText);
            } else {
                entry.style.display = 'none';
            }
        });
        
        // Handle any remaining entries - only for visibility, don't highlight
        if (remainingCount > 0) {
            logEntries.slice(MAX_ENTRIES_TO_PROCESS).forEach(entry => {
                const entryText = entry.textContent.toLowerCase();
                if (entryText.includes(searchText)) {
                    entry.style.display = '';
                    matchCount++;
                } else {
                    entry.style.display = 'none';
                }
            });
        }
        
        // Update search results info
        if (this.elements.logSearchResults) {
            let resultsText = `Found ${matchCount} matching log entries`;
            this.elements.logSearchResults.textContent = resultsText;
            this.elements.logSearchResults.style.display = 'block';
        }
        
        // Disable auto-scroll when searching
        if (this.elements.autoScrollCheckbox && this.elements.autoScrollCheckbox.checked) {
            // Save auto-scroll state to restore later if needed
            this.autoScrollWasEnabled = true;
            this.elements.autoScrollCheckbox.checked = false;
        }
    },
    
    // New simplified highlighting method that's much more performant
    simpleHighlightMatch: function(logEntry, searchText) {
        // Only proceed if the search text is meaningful
        if (searchText.length < 2) return;
        
        // Store original HTML if not already stored
        if (!logEntry.hasAttribute('data-original-html')) {
            logEntry.setAttribute('data-original-html', logEntry.innerHTML);
        }
        
        const html = logEntry.getAttribute('data-original-html');
        const escapedSearchText = searchText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&'); // Escape regex special chars
        
        // Simple case-insensitive replace with highlight span (using a more efficient regex approach)
        const regex = new RegExp(`(${escapedSearchText})`, 'gi');
        const newHtml = html.replace(regex, '<span class="search-highlight">$1</span>');
        
        logEntry.innerHTML = newHtml;
    },
    
    // Clear log search and reset to default view
    clearLogSearch: function() {
        if (!this.elements.logsContainer) return;
        
        // Clear search input
        if (this.elements.logSearchInput) {
            this.elements.logSearchInput.value = '';
        }
        
        // Hide clear search button
        if (this.elements.clearSearchButton) {
            this.elements.clearSearchButton.style.display = 'none';
        }
        
        // Hide search results info
        if (this.elements.logSearchResults) {
            this.elements.logSearchResults.style.display = 'none';
        }
        
        // Show all log entries - use a more efficient approach
        const allLogEntries = this.elements.logsContainer.querySelectorAll('.log-entry');
        
        // Process in batches for better performance
        Array.from(allLogEntries).forEach(entry => {
            // Display all entries
            entry.style.display = '';
            
            // Restore original HTML if it exists
            if (entry.hasAttribute('data-original-html')) {
                entry.innerHTML = entry.getAttribute('data-original-html');
            }
        });
        
        // Restore auto-scroll if it was enabled
        if (this.autoScrollWasEnabled && this.elements.autoScrollCheckbox) {
            this.elements.autoScrollCheckbox.checked = true;
            this.autoScrollWasEnabled = false;
        }
    },
    
    // Settings handling
    loadAllSettings: function() {
        // Disable save button until changes are made
        this.updateSaveResetButtonState(false);
        this.settingsChanged = false;
        
        // Get all settings to populate forms
        HuntarrUtils.fetchWithTimeout('./api/settings')
            .then(response => response.json())
            .then(data => {
                console.log('Loaded settings:', data);
                
                // Store original settings for comparison
                this.originalSettings = data;
                
                // Cache settings in localStorage for timezone access
                try {
                    localStorage.setItem('huntarr-settings-cache', JSON.stringify(data));
                } catch (e) {
                    console.warn('[huntarrUI] Failed to cache settings in localStorage:', e);
                }
                
                // Populate each app's settings form
                if (data.sonarr) this.populateSettingsForm('sonarr', data.sonarr);
                if (data.radarr) this.populateSettingsForm('radarr', data.radarr);
                if (data.lidarr) this.populateSettingsForm('lidarr', data.lidarr);
                if (data.readarr) this.populateSettingsForm('readarr', data.readarr);
                if (data.whisparr) this.populateSettingsForm('whisparr', data.whisparr);
                if (data.eros) this.populateSettingsForm('eros', data.eros);
                if (data.swaparr) {
                    // Cache Swaparr settings globally for instance visibility logic
                    window.swaparrSettings = data.swaparr;
                    this.populateSettingsForm('swaparr', data.swaparr);
                }
                if (data.general) this.populateSettingsForm('general', data.general);
                
                // Update duration displays (like sleep durations)
                if (typeof SettingsForms !== 'undefined' && 
                    typeof SettingsForms.updateDurationDisplay === 'function') {
                    SettingsForms.updateDurationDisplay();
                }
                
                // Update Swaparr instance visibility based on global setting
                if (typeof SettingsForms !== 'undefined' && 
                    typeof SettingsForms.updateAllSwaparrInstanceVisibility === 'function') {
                    SettingsForms.updateAllSwaparrInstanceVisibility();
                }
                
                // Load stateful info immediately, don't wait for loadAllSettings to complete
                this.loadStatefulInfo();
            })
            .catch(error => {
                console.error('Error loading settings:', error);
                this.showNotification('Error loading settings. Please try again.', 'error');
            });
    },
    
    populateSettingsForm: function(app, appSettings) {
        // Cache the form for this app
        const form = document.getElementById(`${app}Settings`);
        if (!form) return;
        
        // Check if SettingsForms is loaded to generate the form
        if (typeof SettingsForms !== 'undefined') {
            const formFunction = SettingsForms[`generate${app.charAt(0).toUpperCase()}${app.slice(1)}Form`];
            if (typeof formFunction === 'function') {
                formFunction(form, appSettings); // This function already calls setupInstanceManagement internally
                
                // Update duration displays for this app
                if (typeof SettingsForms.updateDurationDisplay === 'function') {
                    try {
                        SettingsForms.updateDurationDisplay();
                    } catch (e) {
                        console.error(`[huntarrUI] Error updating duration display:`, e);
                    }
                }
                
                // Update Swaparr instance visibility based on global setting
                if (typeof SettingsForms.updateAllSwaparrInstanceVisibility === 'function') {
                    try {
                        SettingsForms.updateAllSwaparrInstanceVisibility();
                    } catch (e) {
                        console.error(`[huntarrUI] Error updating Swaparr instance visibility:`, e);
                    }
                }
            } else {
                console.error(`[huntarrUI] Form generator function not found for app: ${app}`);
            }
        } else {
            console.error('[huntarrUI] SettingsForms is not defined');
            return;
        }
    },
    
    // Called when any setting input changes in the active tab
    markSettingsAsChanged() {
        if (!this.settingsChanged) {
            console.log("[huntarrUI] Settings marked as changed.");
            this.settingsChanged = true;
            this.updateSaveResetButtonState(true); // Enable buttons
        }
    },

    saveSettings: function() {
        const app = this.currentSettingsTab;
        console.log(`[huntarrUI] saveSettings called for app: ${app}`);
        
        // Clear the unsaved changes flag BEFORE sending the request
        // This prevents the "unsaved changes" dialog from appearing
        this.settingsChanged = false;
        this.updateSaveResetButtonState(false);
        
        // Use getFormSettings for all apps, as it handles different structures
        let settings = this.getFormSettings(app);

        if (!settings) {
            console.error(`[huntarrUI] Failed to collect settings for app: ${app}`);
            this.showNotification('Error collecting settings from form.', 'error');
            return;
        }

        console.log(`[huntarrUI] Collected settings for ${app}:`, settings);
        
        // Check if this is general settings and if the authentication mode has changed
        const isAuthModeChanged = app === 'general' && 
            this.originalSettings && 
            this.originalSettings.general && 
            this.originalSettings.general.auth_mode !== settings.auth_mode;
            
        // Log changes to authentication settings
        console.log(`[huntarrUI] Authentication mode changed: ${isAuthModeChanged}`);

        console.log(`[huntarrUI] Sending settings payload for ${app}:`, settings);

        // Use the correct endpoint based on app type
        const endpoint = app === 'general' ? './api/settings/general' : `./api/settings/${app}`;
        
        HuntarrUtils.fetchWithTimeout(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(settings)
        })
        .then(response => {
            if (!response.ok) {
                // Try to get error message from response body
                return response.json().then(errData => {
                    throw new Error(errData.error || `HTTP error! status: ${response.status}`);
                }).catch(() => {
                    // Fallback if response body is not JSON or empty
                    throw new Error(`HTTP error! status: ${response.status}`);
                });
            }
            return response.json();
        })
        .then(savedConfig => {
            console.log('[huntarrUI] Settings saved successfully. Full config received:', savedConfig);
            
            // Only reload the page if Authentication Mode was changed
            if (isAuthModeChanged) {
                this.showNotification('Settings saved successfully. Reloading page to apply authentication changes...', 'success');
                setTimeout(() => {
                    window.location.href = './'; // Redirect to home page after a brief delay
                }, 1500);
                return;
            }
            
            this.showNotification('Settings saved successfully', 'success');

            // Update original settings state with the full config returned from backend
            if (typeof savedConfig === 'object' && savedConfig !== null) {
                this.originalSettings = JSON.parse(JSON.stringify(savedConfig));
                
                // Cache Swaparr settings globally if they were updated
                if (app === 'swaparr') {
                    // Handle both nested (savedConfig.swaparr) and direct (savedConfig) formats
                    const swaparrData = savedConfig.swaparr || (savedConfig && !savedConfig.sonarr && !savedConfig.radarr ? savedConfig : null);
                    if (swaparrData) {
                        window.swaparrSettings = swaparrData;
                        console.log('[huntarrUI] Updated Swaparr settings cache:', window.swaparrSettings);
                    }
                }
                
                // Check if low usage mode setting has changed and apply it immediately
                if (app === 'general' && 'low_usage_mode' in settings) {
                    this.applyLowUsageMode(settings.low_usage_mode);
                }
            } else {
                console.error('[huntarrUI] Invalid config received from backend after save:', savedConfig);
                this.loadAllSettings();
                return;
            }

            // Re-populate the form with the saved data
            const currentAppSettings = this.originalSettings[app] || {};
            
            // Preserve instances data if missing in the response but was in our sent data
            if (app === 'sonarr' && !currentAppSettings.instances && settings.instances) {
                currentAppSettings.instances = settings.instances;
            }
            
            this.populateSettingsForm(app, currentAppSettings);

            // Update connection status and UI
            this.checkAppConnection(app);
            this.updateHomeConnectionStatus();
            
            // If general settings were saved, refresh the stateful info display
            if (app === 'general') {
                // Update the displayed interval hours if it's available in the settings
                if (settings.stateful_management_hours && document.getElementById('stateful_management_hours')) {
                    const intervalInput = document.getElementById('stateful_management_hours');
                    const intervalDaysSpan = document.getElementById('stateful_management_days');
                    const expiresDateEl = document.getElementById('stateful_expires_date');
                    
                    // Update the input value
                    intervalInput.value = settings.stateful_management_hours;
                    
                    // Update the days display
                    if (intervalDaysSpan) {
                        const days = (settings.stateful_management_hours / 24).toFixed(1);
                        intervalDaysSpan.textContent = `${days} days`;
                    }
                    
                    // Show updating indicator
                    if (expiresDateEl) {
                        expiresDateEl.textContent = 'Updating...';
                    }
                    
                    // Also directly update the stateful expiration on the server and update UI
                    this.updateStatefulExpirationOnUI();
                } else {
                    this.loadStatefulInfo();
                }
                
                // Dispatch a custom event that community-resources.js can listen for
                window.dispatchEvent(new CustomEvent('settings-saved', {
                    detail: { appType: app, settings: settings }
                }));
            }
        })
        .catch(error => {
            console.error('Error saving settings:', error);
            this.showNotification(`Error saving settings: ${error.message}`, 'error');
            // If there was an error, mark settings as changed again
            this.settingsChanged = true;
            this.updateSaveResetButtonState(true);
        });
    },

    // Auto-save enabled - save button removed, no state to update
    updateSaveResetButtonState(enable) {
        // No-op since save button is removed for auto-save
    },

    // Setup auto-save for settings
    setupSettingsAutoSave: function() {
        console.log('[huntarrUI] Setting up immediate settings auto-save');
        
        // Add event listeners to both settings container and individual app sections
        const settingsContainer = document.getElementById('settingsSection');
        const swaparrSection = document.getElementById('swaparrSection');
        const sonarrSection = document.getElementById('sonarrSection');
        const radarrSection = document.getElementById('radarrSection');
        const lidarrSection = document.getElementById('lidarrSection');
        const readarrSection = document.getElementById('readarrSection');
        const whisparrSection = document.getElementById('whisparrSection');
        const erosSection = document.getElementById('erosSection');
        
        // Function to add auto-save listeners to a container
        const addAutoSaveListeners = (container, containerName) => {
            if (!container) return;
            
            console.log(`[huntarrUI] Adding auto-save listeners to ${containerName}`);
            
            // Listen for input events (for text inputs, textareas, range sliders)
            container.addEventListener('input', (event) => {
                if (event.target.matches('input, textarea')) {
                    console.log(`[huntarrUI] Input change detected in ${containerName}:`, event.target.id);
                    this.triggerSettingsAutoSave();
                }
            });
            
            // Listen for change events (for checkboxes, selects, radio buttons)
            container.addEventListener('change', (event) => {
                if (event.target.matches('input, select, textarea')) {
                    console.log(`[huntarrUI] Change event detected in ${containerName}:`, event.target.id);
        
                    // Special handling for settings that can take effect immediately
                    if (event.target.id === 'low_usage_mode') {
                        console.log('[huntarrUI] Low Usage Mode toggled, applying immediately');
                        // Apply low usage mode immediately by toggling CSS class
                        if (event.target.checked) {
                            document.body.classList.add('low-usage-mode');
                        } else {
                            document.body.classList.remove('low-usage-mode');
                        }
                    } else if (event.target.id === 'timezone') {
                        console.log('[huntarrUI] Timezone changed, applying immediately');
                        // Timezone changes take effect on next page load or refresh
                    } else if (event.target.id === 'auth_mode') {
                        console.log('[huntarrUI] Authentication mode changed, applying immediately');
                        // Auth mode changes take effect immediately via backend
                    } else if (event.target.id === 'check_for_updates') {
                        console.log('[huntarrUI] Update checking toggled, applying immediately');
                        this.applyUpdateCheckingChange(event.target.checked);
                    }
                    
                    this.triggerSettingsAutoSave();
                }
            });
        };
        
        // Add listeners to all relevant containers
        addAutoSaveListeners(settingsContainer, 'settingsSection');
        addAutoSaveListeners(swaparrSection, 'swaparrSection');
        addAutoSaveListeners(sonarrSection, 'sonarrSection');
        addAutoSaveListeners(radarrSection, 'radarrSection');
        addAutoSaveListeners(lidarrSection, 'lidarrSection');
        addAutoSaveListeners(readarrSection, 'readarrSection');
        addAutoSaveListeners(whisparrSection, 'whisparrSection');
        addAutoSaveListeners(erosSection, 'erosSection');
        
        console.log('[huntarrUI] Settings auto-save listeners added to all containers');
    },

    // Trigger immediate auto-save
    triggerSettingsAutoSave: function() {
        if (window._settingsCurrentlySaving) {
            console.log('[huntarrUI] Settings auto-save skipped - already saving');
            return;
        }
        
        // Determine what type of settings we're saving
        const app = this.currentSettingsTab;
        
        if (!app) {
            console.log('[huntarrUI] No current settings tab for auto-save');
            return;
        }
        
        console.log(`[huntarrUI] Triggering immediate settings auto-save for: ${app}`);
        this.autoSaveSettings(app);
    },

    // Auto-save settings function
    autoSaveSettings: function(app) {
        if (window._settingsCurrentlySaving) {
            console.log(`[huntarrUI] Auto-save for ${app} skipped - already saving`);
            return;
        }
        
        console.log(`[huntarrUI] Auto-saving settings for: ${app}`);
        window._settingsCurrentlySaving = true;
        
        // Use custom auto-save logic that doesn't regenerate the form
        let settings = this.getFormSettings(app);

        if (!settings) {
            console.error(`[huntarrUI] Failed to collect settings for app: ${app}`);
            window._settingsCurrentlySaving = false;
            return;
        }

        console.log(`[huntarrUI] Auto-saving settings for ${app}:`, settings);

        // Use the correct endpoint based on app type
        const endpoint = app === 'general' ? './api/settings/general' : `./api/settings/${app}`;
        
        HuntarrUtils.fetchWithTimeout(endpoint, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(settings)
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(errData => {
                    throw new Error(errData.error || `HTTP error! status: ${response.status}`);
                }).catch(() => {
                    throw new Error(`HTTP error! status: ${response.status}`);
                });
            }
            return response.json();
        })
        .then(savedConfig => {
            console.log(`[huntarrUI] Auto-save completed for ${app}`);
            
            // Update original settings state but DON'T regenerate the form
            if (typeof savedConfig === 'object' && savedConfig !== null) {
                this.originalSettings = JSON.parse(JSON.stringify(savedConfig));
                
                // Cache Swaparr settings globally if they were updated
                if (app === 'swaparr') {
                    const swaparrData = savedConfig.swaparr || (savedConfig && !savedConfig.sonarr && !savedConfig.radarr ? savedConfig : null);
                    if (swaparrData) {
                        window.swaparrSettings = swaparrData;
                        console.log('[huntarrUI] Updated Swaparr settings cache:', window.swaparrSettings);
                    }
                }
                
                // For general settings, dispatch event to notify other modules (like home page display)
                if (app === 'general') {
                    console.log('[huntarrUI] Dispatching settings-saved event for general settings');
                    window.dispatchEvent(new CustomEvent('settings-saved', {
                        detail: { app: app, settings: savedConfig }
                    }));
                }
            }
            
            window._settingsCurrentlySaving = false;
        })
        .catch(error => {
            console.error(`[huntarrUI] Auto-save error for ${app}:`, error);
            // Silent auto-save - no notifications for failures
            window._settingsCurrentlySaving = false;
        });
    },

    // Clean URL by removing special characters from the end
    cleanUrlString: function(url) {
        if (!url) return "";
        
        // Trim whitespace first
        let cleanUrl = url.trim();
        
        // First remove any trailing slashes
        cleanUrl = cleanUrl.replace(/[\/\\]+$/g, '');
        
        // Then remove any other trailing special characters
        // This regex will match any special character at the end that is not alphanumeric, hyphen, period, or underscore
        return cleanUrl.replace(/[^a-zA-Z0-9\-\._]$/g, '');
    },
    
    // Get settings from the form, updated to handle instances consistently
    getFormSettings: function(app) {
        const settings = {};
        const form = document.getElementById(`${app}Settings`);
        if (!form) {
            console.error(`[huntarrUI] Settings form for ${app} not found.`);
            return null;
        }

        // Special handling for general settings
        if (app === 'general') {
            console.log('[huntarrUI] Processing general settings');
            console.log('[huntarrUI] Form:', form);
            console.log('[huntarrUI] Form HTML (first 500 chars):', form.innerHTML.substring(0, 500));
            
            // Debug: Check if apprise_urls exists anywhere
            const globalAppriseElement = document.querySelector('#apprise_urls');
            console.log('[huntarrUI] Global apprise_urls element:', globalAppriseElement);
            
            // Get all inputs and select elements in the general form
            const inputs = form.querySelectorAll('input, select, textarea');
            inputs.forEach(input => {
                let key = input.id;
                let value;
                
                if (input.type === 'checkbox') {
                    value = input.checked;
                } else if (input.type === 'number') {
                    value = input.value === '' ? null : parseInt(input.value, 10);
                } else {
                    value = input.value.trim();
                }
                
                console.log(`[huntarrUI] Processing input: ${key} = ${value}`);
                
                // Handle special cases
                if (key === 'apprise_urls') {
                    console.log('[huntarrUI] Processing Apprise URLs');
                    console.log('[huntarrUI] Raw apprise_urls value:', input.value);
                    
                    // Split by newline and filter empty lines
                    settings.apprise_urls = input.value.split('\n')
                        .map(url => url.trim())
                        .filter(url => url.length > 0);
                    
                    console.log('[huntarrUI] Processed apprise_urls:', settings.apprise_urls);
                } else if (key && !key.includes('_instance_')) {
                    // Only include non-instance fields
                    settings[key] = value;
                }
            });
            
            console.log('[huntarrUI] Final general settings:', settings);
            return settings;
        }
        
        // Special handling for Swaparr (doesn't use instances)
        if (app === 'swaparr') {
            console.log('[huntarrUI] Processing Swaparr settings');
            
            // Get all inputs and select elements in the Swaparr form
            const inputs = form.querySelectorAll('input, select, textarea');
            inputs.forEach(input => {
                let key = input.id;
                let value;
                
                if (input.type === 'checkbox') {
                    value = input.checked;
                } else if (input.type === 'number') {
                    value = input.value === '' ? null : parseInt(input.value, 10);
                } else {
                    value = input.value.trim();
                }
                
                console.log(`[huntarrUI] Processing Swaparr input: ${key} = ${value}`);
                
                // Remove 'swaparr_' prefix from key
                if (key.startsWith('swaparr_')) {
                    key = key.substring(8); // Remove 'swaparr_' prefix
                }
                
                // Handle special cases for tag inputs and other complex fields
                if (key.includes('_input') || key.includes('_tags') || key.includes('stars-count')) {
                    return; // Skip these helper fields
                }
                
                if (key && value !== undefined) {
                    // Handle special duration conversion for sleep_duration (minutes to seconds)
                    if (key === 'sleep_duration' && value !== null) {
                        settings[key] = value * 60; // Convert minutes to seconds
                    } else {
                        settings[key] = value;
                    }
                }
            });
            
            // Handle tag-based settings (malicious extensions, suspicious patterns, quality patterns)
            const maliciousExtensions = Array.from(document.querySelectorAll('#swaparr_malicious_extensions_tags .tag')).map(tag => tag.textContent.trim());
            const suspiciousPatterns = Array.from(document.querySelectorAll('#swaparr_suspicious_patterns_tags .tag')).map(tag => tag.textContent.trim());
            const qualityPatterns = Array.from(document.querySelectorAll('#swaparr_quality_patterns_tags .tag')).map(tag => tag.textContent.trim());
            
            if (maliciousExtensions.length > 0) settings.malicious_file_extensions = maliciousExtensions;
            if (suspiciousPatterns.length > 0) settings.suspicious_filename_patterns = suspiciousPatterns;
            if (qualityPatterns.length > 0) settings.blocked_quality_patterns = qualityPatterns;
            
            console.log('[huntarrUI] Final Swaparr settings:', settings);
            return settings;
        }
        
        // Handle apps that use instances (Sonarr, Radarr, etc.)
        // Get all instance items in the form
        const instanceItems = form.querySelectorAll('.instance-item');
        settings.instances = [];
        
        // Check if multi-instance UI elements exist (like Sonarr)
        if (instanceItems.length > 0) {
            console.log(`[huntarrUI] Found ${instanceItems.length} instance items for ${app}. Processing multi-instance mode.`);
            // Multi-instance logic (current Sonarr logic)
            instanceItems.forEach((item, index) => {
                const instanceId = item.dataset.instanceId; // Gets the data-instance-id
                const nameInput = form.querySelector(`#${app}-name-${instanceId}`);
                const urlInput = form.querySelector(`#${app}-url-${instanceId}`);
                const keyInput = form.querySelector(`#${app}-key-${instanceId}`);
                const enabledInput = form.querySelector(`#${app}-enabled-${instanceId}`);

                if (urlInput && keyInput) { // Need URL and Key at least
                    const instance = {
                        // Use nameInput value if available, otherwise generate a default
                        name: nameInput && nameInput.value.trim() !== '' ? nameInput.value.trim() : `Instance ${index + 1}`,
                        api_url: this.cleanUrlString(urlInput.value),
                        api_key: keyInput.value.trim(),
                        // Default to true if toggle doesn't exist or is checked
                        enabled: enabledInput ? enabledInput.checked : true
                    };
                    
                    // Collect per-instance settings for this instance
                    const perInstanceFields = [
                        'hunt_missing_items', 'hunt_upgrade_items', 'hunt_missing_books', 'hunt_upgrade_books',
                        'hunt_missing_movies', 'hunt_upgrade_movies', 'hunt_missing_mode', 'upgrade_mode',
                        'state_management_mode', 'state_management_hours', 'swaparr_enabled'
                    ];
                    
                    perInstanceFields.forEach(fieldName => {
                        const fieldInput = form.querySelector(`#${app}-${fieldName.replace(/_/g, '-')}-${instanceId}`);
                        if (fieldInput) {
                            if (fieldInput.type === 'checkbox') {
                                instance[fieldName] = fieldInput.checked;
                            } else if (fieldInput.type === 'number') {
                                instance[fieldName] = fieldInput.value === '' ? null : parseInt(fieldInput.value, 10);
                            } else {
                                instance[fieldName] = fieldInput.value.trim();
                            }
                            console.log(`[huntarrUI] Collected per-instance setting for ${app} instance ${instanceId}: ${fieldName} = ${instance[fieldName]}`);
                        }
                    });
                    
                    settings.instances.push(instance);
                }
            });
        } else {
            console.log(`[huntarrUI] No instance items found for ${app}. Processing single-instance mode.`);
            // Single-instance logic (for Radarr, Lidarr, etc.)
            // Look for the standard IDs used in their forms
            const nameInput = form.querySelector(`#${app}_instance_name`); // Check for a specific name field
            const urlInput = form.querySelector(`#${app}_api_url`);
            const keyInput = form.querySelector(`#${app}_api_key`);
            // Assuming single instances might have an enable toggle like #app_enabled
            const enabledInput = form.querySelector(`#${app}_enabled`);

            // Only add if URL and Key have values
            if (urlInput && urlInput.value.trim() && keyInput && keyInput.value.trim()) {
                 settings.instances.push({
                     name: nameInput && nameInput.value.trim() !== '' ? nameInput.value.trim() : `${app} Instance 1`, // Default name
                     api_url: this.cleanUrlString(urlInput.value),
                     api_key: keyInput.value.trim(),
                     // Default to true if toggle doesn't exist or is checked
                     enabled: enabledInput ? enabledInput.checked : true
                 });
            }
        }

        console.log(`[huntarrUI] Processed instances for ${app}:`, settings.instances);

        // Now collect any OTHER settings NOT part of the instance structure
        const allInputs = form.querySelectorAll('input, select');
        const handledInstanceFieldIds = new Set();

        // Identify IDs used in instance collection to avoid double-adding them
        if (instanceItems.length > 0) {
            // Multi-instance: Iterate items again to get IDs
            instanceItems.forEach((item) => {
                const instanceId = item.dataset.instanceId;
                if(instanceId) {
                    // Basic instance fields
                    handledInstanceFieldIds.add(`${app}-name-${instanceId}`);
                    handledInstanceFieldIds.add(`${app}-url-${instanceId}`);
                    handledInstanceFieldIds.add(`${app}-key-${instanceId}`);
                    handledInstanceFieldIds.add(`${app}-enabled-${instanceId}`);
                    
                    // Per-instance settings fields
                    const perInstanceFields = [
                        'hunt_missing_items', 'hunt_upgrade_items', 'hunt_missing_books', 'hunt_upgrade_books',
                        'hunt_missing_movies', 'hunt_upgrade_movies', 'hunt_missing_mode', 'upgrade_mode',
                        'state_management_mode', 'state_management_hours', 'swaparr_enabled'
                    ];
                    
                    perInstanceFields.forEach(fieldName => {
                        handledInstanceFieldIds.add(`${app}-${fieldName.replace(/_/g, '-')}-${instanceId}`);
                    });
                }
            });
        } else {
            // Single-instance: Check for standard IDs
             if (form.querySelector(`#${app}_instance_name`)) handledInstanceFieldIds.add(`${app}_instance_name`);
             if (form.querySelector(`#${app}_api_url`)) handledInstanceFieldIds.add(`${app}_api_url`);
             if (form.querySelector(`#${app}_api_key`)) handledInstanceFieldIds.add(`${app}_api_key`);
             if (form.querySelector(`#${app}_enabled`)) handledInstanceFieldIds.add(`${app}_enabled`);
        }

        allInputs.forEach(input => {
            // Handle special case for Whisparr version
            if (input.id === 'whisparr_version') {
                if (app === 'whisparr') {
                    settings['whisparr_version'] = input.value.trim();
                    return; // Skip further processing for this field
                }
            }

            // Skip buttons and fields already processed as part of an instance
            if (input.type === 'button' || handledInstanceFieldIds.has(input.id)) {
                return;
            }

            // Get the field key (remove app prefix)
            let key = input.id;
            
            if (key.startsWith(`${app}_`)) {
                key = key.substring(app.length + 1);
            }
            
            // Skip empty keys or keys that are just numbers (unlikely but possible)
            if (!key || /^\d+$/.test(key)) return;

            // Store the value
            if (input.type === 'checkbox') {
                settings[key] = input.checked;
            } else if (input.type === 'number') {
                // Handle potential empty string for numbers, store as null or default?
                let numValue = input.value === '' ? null : parseInt(input.value, 10);
                
                // Special handling for sleep_duration fields - convert minutes to seconds
                if (key === 'sleep_duration' && numValue !== null) {
                    numValue = numValue * 60; // Convert minutes to seconds
                    console.log(`[huntarrUI] Converted ${app} sleep_duration from ${input.value} minutes to ${numValue} seconds`);
                }
                
                settings[key] = numValue;
            } else {
                settings[key] = input.value.trim();
            }
        });

        console.log(`[huntarrUI] Final collected settings for ${app}:`, settings);
        return settings;
    },

    // Test notification functionality
    testNotification: function() {
        console.log('[huntarrUI] Testing notification...');
        
        const statusElement = document.getElementById('testNotificationStatus');
        const buttonElement = document.getElementById('testNotificationBtn');
        
        if (!statusElement || !buttonElement) {
            console.error('[huntarrUI] Test notification elements not found');
            return;
        }
        
        // Disable button and show loading
        buttonElement.disabled = true;
        buttonElement.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Auto-saving...';
        statusElement.innerHTML = '<span style="color: #fbbf24;">Auto-saving settings before testing...</span>';
        
        // Auto-save general settings before testing
        this.autoSaveGeneralSettings()
            .then(() => {
                // Update button text to show we're now testing
                buttonElement.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Sending...';
                statusElement.innerHTML = '<span style="color: #fbbf24;">Sending test notification...</span>';
                
                // Now test with the saved settings
                return HuntarrUtils.fetchWithTimeout('./api/test-notification', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    }
                });
            })
            .then(response => response.json())
            .then(data => {
                console.log('[huntarrUI] Test notification response:', data);
                
                if (data.success) {
                    statusElement.innerHTML = '<span style="color: #10b981;">✓ Test notification sent successfully!</span>';
                    this.showNotification('Test notification sent! Check your notification service.', 'success');
                } else {
                    statusElement.innerHTML = '<span style="color: #ef4444;">✗ Failed to send test notification</span>';
                    this.showNotification(data.error || 'Failed to send test notification', 'error');
                }
            })
            .catch(error => {
                console.error('[huntarrUI] Test notification error:', error);
                statusElement.innerHTML = '<span style="color: #ef4444;">✗ Error during auto-save or testing</span>';
                this.showNotification('Error during auto-save or testing: ' + error.message, 'error');
            })
            .finally(() => {
                // Re-enable button
                buttonElement.disabled = false;
                buttonElement.innerHTML = '<i class="fas fa-bell"></i> Test Notification';
                
                // Clear status after 5 seconds
                setTimeout(() => {
                    if (statusElement) {
                        statusElement.innerHTML = '';
                    }
                }, 5000);
            });
    },

    // Auto-save general settings (used by test notification and auto-save)
    autoSaveGeneralSettings: function(silent = false) {
        console.log('[huntarrUI] Auto-saving general settings...');
        
        return new Promise((resolve, reject) => {
            // Find the general settings form using the correct selectors
            const generalForm = document.querySelector('#generalSettings') ||
                              document.querySelector('.app-settings-panel[data-app-type="general"]') ||
                              document.querySelector('.settings-form[data-app-type="general"]') ||
                              document.querySelector('#general');
            
            if (!generalForm) {
                console.error('[huntarrUI] Could not find general settings form for auto-save');
                console.log('[huntarrUI] Available forms:', document.querySelectorAll('.app-settings-panel, .settings-form, [id*="general"], [id*="General"]'));
                reject(new Error('Could not find general settings form'));
                return;
            }
            
            console.log('[huntarrUI] Found general form:', generalForm);
            
            // Get settings from the form using the correct app parameter
            let settings = {};
            try {
                settings = this.getFormSettings('general');
                console.log('[huntarrUI] Auto-save collected settings:', settings);
            } catch (error) {
                console.error('[huntarrUI] Error collecting settings for auto-save:', error);
                reject(error);
                return;
            }
            
            // Save the settings
            HuntarrUtils.fetchWithTimeout('./api/settings/general', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(settings)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success !== false) {  // API returns all settings on success, not just success:true
                    console.log('[huntarrUI] Auto-save successful');
                    resolve();
                } else {
                    console.error('[huntarrUI] Auto-save failed:', data);
                    reject(new Error(data.error || 'Failed to auto-save settings'));
                }
            })
            .catch(error => {
                console.error('[huntarrUI] Auto-save request failed:', error);
                reject(error);
            });
        });
    },
    
    // Handle instance management events
    setupInstanceEventHandlers: function() {
        console.log("DEBUG: setupInstanceEventHandlers called"); // Added logging
        const settingsPanels = document.querySelectorAll('.app-settings-panel');
        
        settingsPanels.forEach(panel => {
            console.log(`DEBUG: Adding listeners to panel '${panel.id}'`); // Added logging
            panel.addEventListener('addInstance', (e) => {
                console.log(`DEBUG: addInstance event listener fired for panel '${panel.id}'. Event detail:`, e.detail);
                this.addAppInstance(e.detail.appName);
            });
            
            panel.addEventListener('removeInstance', (e) => {
                this.removeAppInstance(e.detail.appName, e.detail.instanceId);
            });
            
            panel.addEventListener('testConnection', (e) => {
                this.testInstanceConnection(e.detail.appName, e.detail.instanceId, e.detail.url, e.detail.apiKey);
            });
        });
    },
    
    // Add a new instance to the app
    addAppInstance: function(appName) {
        console.log(`DEBUG: addAppInstance called for app '${appName}'`);
        const container = document.getElementById(`${appName}Settings`);
        if (!container) return;
        
        // Get current settings
        const currentSettings = this.getFormSettings(appName);

        if (!currentSettings.instances) {
            currentSettings.instances = [];
        }
        
        // Limit to 9 instances
        if (currentSettings.instances.length >= 9) {
            this.showNotification('Maximum of 9 instances allowed', 'error');
            return;
        }
        
        // Add new instance with a default name
        currentSettings.instances.push({
            name: `Instance ${currentSettings.instances.length + 1}`,
            api_url: '',
            api_key: '',
            enabled: true
        });
        
        // Regenerate form with new instance
        SettingsForms[`generate${appName.charAt(0).toUpperCase()}${appName.slice(1)}Form`](container, currentSettings);
        
        // Update controls like duration displays
        SettingsForms.updateDurationDisplay();
        
        this.showNotification('New instance added', 'success');
    },
    
    // Remove an instance
    removeAppInstance: function(appName, instanceId) {
        const container = document.getElementById(`${appName}Settings`);
        if (!container) return;
        
        // Get current settings
        const currentSettings = this.getFormSettings(appName);
        
        // Remove the instance
        if (currentSettings.instances && instanceId >= 0 && instanceId < currentSettings.instances.length) {
            // Keep at least one instance
            if (currentSettings.instances.length > 1) {
                const removedName = currentSettings.instances[instanceId].name;
                currentSettings.instances.splice(instanceId, 1);
                
                // Regenerate form
                SettingsForms[`generate${appName.charAt(0).toUpperCase()}${appName.slice(1)}Form`](container, currentSettings);
                
                // Update controls like duration displays
                SettingsForms.updateDurationDisplay();
                
                this.showNotification(`Instance "${removedName}" removed`, 'info');
            } else {
                this.showNotification('Cannot remove the last instance', 'error');
            }
        }
    },
    
    // Test connection for a specific instance
    testInstanceConnection: function(appName, instanceId, url, apiKey) {
        console.log(`Testing connection for ${appName} instance ${instanceId} with URL: ${url}`);
        
        // Make sure instanceId is treated as a number
        instanceId = parseInt(instanceId, 10);
        
        // Find the status span where we'll display the result
        const statusSpan = document.getElementById(`${appName}_instance_${instanceId}_status`);
        if (!statusSpan) {
            console.error(`Status span not found for ${appName} instance ${instanceId}`);
            return;
        }
        
        // Show testing status
        statusSpan.textContent = 'Testing...';
        statusSpan.className = 'connection-status testing';
        
        // Validate URL and API key
        if (!url || !apiKey) {
            statusSpan.textContent = 'Missing URL or API key';
            statusSpan.className = 'connection-status error';
            return;
        }
        
        // Check if URL is properly formatted
        if (!url.startsWith('http://') && !url.startsWith('https://')) {
            statusSpan.textContent = 'URL must start with http:// or https://';
            statusSpan.className = 'connection-status error';
            return;
        }
        
        // Clean the URL (remove special characters from the end)
        url = this.cleanUrlString(url);
        
        // Make the API request to test the connection
        HuntarrUtils.fetchWithTimeout(`./api/${appName}/test-connection`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                api_url: url,
                api_key: apiKey
            })
        })
        .then(response => {
            if (!response.ok) {
                return response.json().then(errorData => {
                    throw new Error(errorData.message || this.getConnectionErrorMessage(response.status));
                }).catch(() => {
                    // Fallback if response body is not JSON or empty
                    throw new Error(this.getConnectionErrorMessage(response.status));
                });
            }
            return response.json();
        })
        .then(data => {
            console.log(`Connection test response data for ${appName} instance ${instanceId}:`, data);
            if (data.success) {
                statusSpan.textContent = data.message || 'Connected';
                statusSpan.className = 'connection-status success';
                
                // If a version was returned, display it
                if (data.version) {
                    statusSpan.textContent += ` (v${data.version})`;
                }
            } else {
                statusSpan.textContent = data.message || 'Failed';
                statusSpan.className = 'connection-status error';
            }
        })
        .catch(error => {
            console.error(`Error testing connection for ${appName} instance ${instanceId}:`, error);
            
            // Extract the most relevant part of the error message
            let errorMessage = error.message || 'Unknown error';
            if (errorMessage.includes('Name or service not known')) {
                errorMessage = 'Unable to resolve hostname. Check the URL.';
            } else if (errorMessage.includes('Connection refused')) {
                errorMessage = 'Connection refused. Check that the service is running.';
            } else if (errorMessage.includes('connect ETIMEDOUT') || errorMessage.includes('timeout')) {
                errorMessage = 'Connection timed out. Check URL and port.';
            } else if (errorMessage.includes('401') || errorMessage.includes('Authentication failed')) {
                errorMessage = 'Invalid API key';
            } else if (errorMessage.includes('404') || errorMessage.includes('not found')) {
                errorMessage = 'URL endpoint not found. Check the URL.';
            } else if (errorMessage.startsWith('HTTP error!')) {
                errorMessage = 'Connection failed. Check URL and port.';
            }
            
            statusSpan.textContent = errorMessage;
            statusSpan.className = 'connection-status error';
        });
    },
    
    // Helper function to translate HTTP error codes to user-friendly messages
    getConnectionErrorMessage: function(status) {
        switch(status) {
            case 400:
                return 'Invalid request. Check URL format.';
            case 401:
                return 'Invalid API key';
            case 403:
                return 'Access forbidden. Check permissions.';
            case 404:
                return 'Service not found at this URL. Check address.';
            case 500:
                return 'Server error. Check if the service is working properly.';
            case 502:
                return 'Bad gateway. Check network connectivity.';
            case 503:
                return 'Service unavailable. Check if the service is running.';
            case 504:
                return 'Gateway timeout. Check network connectivity.';
            default:
                return `Connection error. Check URL and port.`;
        }
    },
    
    // App connections
    checkAppConnections: function() {
        this.checkAppConnection('sonarr');
        this.checkAppConnection('radarr');
        this.checkAppConnection('lidarr');
        this.checkAppConnection('readarr'); // Added readarr
        this.checkAppConnection('whisparr'); // Added whisparr
        this.checkAppConnection('eros'); // Enable actual Eros API check
    },
    
    checkAppConnection: function(app) {
        HuntarrUtils.fetchWithTimeout(`./api/status/${app}`)
            .then(response => response.json())
            .then(data => {
                // Pass the whole data object for all apps
                this.updateConnectionStatus(app, data); 

                // Still update the configuredApps flag for potential other uses, but after updating status
                this.configuredApps[app] = data.configured === true; // Ensure it's a boolean
            })
            .catch(error => {
                console.error(`Error checking ${app} connection:`, error);
                // Pass a default 'not configured' status object on error
                this.updateConnectionStatus(app, { configured: false, connected: false }); 
            });
    },
    
    updateConnectionStatus: function(app, statusData) {
        const statusElement = this.elements[`${app}HomeStatus`];
        if (!statusElement) return;

        let isConfigured = false;
        let isConnected = false;

        // Try to determine configured and connected status from statusData object
        // Default to false if properties are missing
        isConfigured = statusData?.configured === true;
        isConnected = statusData?.connected === true;

        // Special handling for *arr apps' multi-instance connected count
        let connectedCount = statusData?.connected_count ?? 0;
        let totalConfigured = statusData?.total_configured ?? 0;
        
        // For all *arr apps, 'isConfigured' means at least one instance is configured
        if (['sonarr', 'radarr', 'lidarr', 'readarr', 'whisparr', 'eros', 'swaparr'].includes(app)) {
            isConfigured = totalConfigured > 0;
            // For *arr apps, 'isConnected' means at least one instance is connected
            isConnected = isConfigured && connectedCount > 0; 
        }

        // --- Visibility Logic --- 
        if (isConfigured) {
            // Ensure the box is visible
            if (this.elements[`${app}HomeStatus`].closest('.app-stats-card')) {
                this.elements[`${app}HomeStatus`].closest('.app-stats-card').style.display = ''; 
            }
        } else {
            // Not configured - HIDE the box
            if (this.elements[`${app}HomeStatus`].closest('.app-stats-card')) {
                this.elements[`${app}HomeStatus`].closest('.app-stats-card').style.display = 'none';
            }
            // Update badge even if hidden (optional, but good practice)
            statusElement.className = 'status-badge not-configured';
            statusElement.innerHTML = '<i class="fas fa-times-circle"></i> Not Configured';
            return; // No need to update badge further if not configured
        }

        // --- Badge Update Logic (only runs if configured) ---
        if (['sonarr', 'radarr', 'lidarr', 'readarr', 'whisparr', 'eros', 'swaparr'].includes(app)) {
            // *Arr specific badge text (already checked isConfigured)
            statusElement.innerHTML = `<i class="fas fa-plug"></i> Connected ${connectedCount}/${totalConfigured}`;
            statusElement.className = 'status-badge ' + (isConnected ? 'connected' : 'error');
        } else {
            // Standard badge update for other configured apps
            if (isConnected) {
                statusElement.className = 'status-badge connected';
                statusElement.innerHTML = '<i class="fas fa-check-circle"></i> Connected';
            } else {
                statusElement.className = 'status-badge not-connected';
                statusElement.innerHTML = '<i class="fas fa-times-circle"></i> Not Connected';
            }
        }
    },

    // Load and update Swaparr status card
    loadSwaparrStatus: function() {
        HuntarrUtils.fetchWithTimeout('./api/swaparr/status')
            .then(response => response.json())
            .then(data => {
                const swaparrCard = document.getElementById('swaparrStatusCard');
                if (!swaparrCard) return;

                // Show/hide card based on whether Swaparr is enabled
                if (data.enabled && data.configured) {
                    swaparrCard.style.display = 'block';
                    
                    // Update persistent statistics with large number formatting (like other apps)
                    const persistentStats = data.persistent_statistics || {};
                    document.getElementById('swaparr-processed').textContent = this.formatLargeNumber(persistentStats.processed || 0);
                    document.getElementById('swaparr-strikes').textContent = this.formatLargeNumber(persistentStats.strikes || 0);
                    document.getElementById('swaparr-removals').textContent = this.formatLargeNumber(persistentStats.removals || 0);
                    document.getElementById('swaparr-ignored').textContent = this.formatLargeNumber(persistentStats.ignored || 0);
                    
                    // Setup button event handlers after content is loaded
                    setTimeout(() => {
                        this.setupSwaparrResetCycle();
                    }, 100);
                    
                } else {
                    swaparrCard.style.display = 'none';
                }
            })
            .catch(error => {
                console.error('Error loading Swaparr status:', error);
                const swaparrCard = document.getElementById('swaparrStatusCard');
                if (swaparrCard) {
                    swaparrCard.style.display = 'none';
                }
            });
    },

    // Setup Swaparr Reset buttons
    setupSwaparrResetCycle: function() {
        // Handle header reset data button (like Live Hunts Executed)
        const resetDataButton = document.getElementById('reset-swaparr-data');
        if (resetDataButton) {
            resetDataButton.addEventListener('click', () => {
                this.resetSwaparrData();
            });
        }

        // Note: Inline reset cycle button is now handled automatically by CycleCountdown system
        // via the cycle-reset-button class and data-app="swaparr" attribute
    },

    // Reset Swaparr data function
    resetSwaparrData: function() {
        // Prevent multiple executions
        if (this.swaparrResetInProgress) {
            return;
        }
        
        // Show confirmation
        if (!confirm('Are you sure you want to reset all Swaparr data? This will clear all strike counts and removed items data.')) {
            return;
        }
        
        this.swaparrResetInProgress = true;
        
        // Immediately update the UI first to provide immediate feedback (like Live Hunts)
        this.updateSwaparrStatsDisplay({
            processed: 0,
            strikes: 0, 
            removals: 0,
            ignored: 0
        });
        
        // Show success notification immediately
        this.showNotification('Swaparr statistics reset successfully', 'success');

        // Try to send the reset to the server, but don't depend on it for UI feedback
        try {
            HuntarrUtils.fetchWithTimeout('./api/swaparr/reset-stats', { method: 'POST' })
                .then(response => {
                    // Just log the response, don't rely on it for UI feedback
                    if (!response.ok) {
                        console.warn('Server responded with non-OK status for Swaparr stats reset');
                    }
                    return response.json().catch(() => ({}));
                })
                .then(data => {
                    console.log('Swaparr stats reset response:', data);
                })
                .catch(error => {
                    console.warn('Error communicating with server for Swaparr stats reset:', error);
                })
                .finally(() => {
                    // Reset the flag after a delay
                    setTimeout(() => {
                        this.swaparrResetInProgress = false;
                    }, 1000);
                });
        } catch (error) {
            console.warn('Error in Swaparr stats reset:', error);
            this.swaparrResetInProgress = false;
        }
    },

    // Update Swaparr stats display with animation (like Live Hunts)
    updateSwaparrStatsDisplay: function(stats) {
        const elements = {
            'processed': document.getElementById('swaparr-processed'),
            'strikes': document.getElementById('swaparr-strikes'),
            'removals': document.getElementById('swaparr-removals'),
            'ignored': document.getElementById('swaparr-ignored')
        };

        for (const [key, element] of Object.entries(elements)) {
            if (element && stats.hasOwnProperty(key)) {
                const currentValue = this.parseFormattedNumber(element.textContent);
                const targetValue = stats[key];
                
                if (currentValue !== targetValue) {
                    // Animate the number change
                    this.animateNumber(element, currentValue, targetValue, 500);
                }
            }
        }
    },

    // Setup Swaparr status polling
    setupSwaparrStatusPolling: function() {
        // Load initial status
        this.loadSwaparrStatus();
        
        // Set up polling to refresh Swaparr status every 30 seconds
        // Only poll when home section is active to reduce unnecessary requests
        setInterval(() => {
            if (this.currentSection === 'home') {
                this.loadSwaparrStatus();
            }
        }, 30000);
    },
    

    
    // User
    loadUsername: function() {
        const usernameElement = document.getElementById('username');
        if (!usernameElement) return;
        
        HuntarrUtils.fetchWithTimeout('./api/user/info')
            .then(response => response.json())
            .then(data => {
                if (data.username) {
                    usernameElement.textContent = data.username;
                }
                
                // Check if local access bypass is enabled and update UI visibility
                this.checkLocalAccessBypassStatus();
            })
            .catch(error => {
                console.error('Error loading username:', error);
                
                // Still check local access bypass status even if username loading failed
                this.checkLocalAccessBypassStatus();
            });
    },
    
    // Check if local access bypass is enabled and update UI accordingly
    checkLocalAccessBypassStatus: function() {
        console.log("Checking local access bypass status...");
        HuntarrUtils.fetchWithTimeout('./api/get_local_access_bypass_status') // Corrected URL
            .then(response => {
                if (!response.ok) {
                    // Log error if response is not OK (e.g., 404, 500)
                    console.error(`Error fetching bypass status: ${response.status} ${response.statusText}`);
                    // Attempt to read response body for more details, if available
                    response.text().then(text => console.error('Response body:', text));
                    // Throw an error to trigger the catch block with a clearer message
                    throw new Error(`HTTP error ${response.status}`); 
                }
                return response.json(); // Only parse JSON if response is OK
            })
            .then(data => {
                if (data && typeof data.isEnabled === 'boolean') {
                    console.log("Local access bypass status received:", data.isEnabled);
                    this.updateUIForLocalAccessBypass(data.isEnabled);
                } else {
                    // Handle cases where response is JSON but not the expected format
                    console.error('Invalid data format received for bypass status:', data);
                    this.updateUIForLocalAccessBypass(false); // Default to disabled/showing elements
                }
            })
            .catch(error => {
                 // Catch network errors and the error thrown from !response.ok
                console.error('Error checking local access bypass status:', error);
                // Default to showing elements if we can't determine status
                this.updateUIForLocalAccessBypass(false);
            });
    },
    
    // Update UI elements visibility based on local access bypass status
    updateUIForLocalAccessBypass: function(isEnabled) {
        console.log("Updating UI for local access bypass:", isEnabled);
        
        // Get the user info container in topbar (username and logout button)
        const userInfoContainer = document.getElementById('userInfoContainer');
        
        // Get the user nav item in sidebar
        const userNav = document.getElementById('userNav');
        
        // Set display style explicitly based on local access bypass setting
        if (isEnabled === true) {
            console.log("Local access bypass is ENABLED - hiding user elements");
            
            // Hide user info in topbar
            if (userInfoContainer) {
                userInfoContainer.style.display = 'none';
                console.log("  • Hidden userInfoContainer");
            } else {
                console.warn("  ⚠ userInfoContainer not found");
            }
            
            // Always show user nav in sidebar regardless of authentication mode
            if (userNav) {
                userNav.style.display = '';
                userNav.style.removeProperty('display'); // Remove any !important styles
                console.log("  • User nav always visible (regardless of auth mode)");
            } else {
                console.warn("  ⚠ userNav not found");
            }
        } else {
            console.log("Local access bypass is DISABLED - showing user elements");
            
            // Show user info in topbar
            if (userInfoContainer) {
                userInfoContainer.style.display = '';
                console.log("  • Showing userInfoContainer");
            } else {
                console.warn("  ⚠ userInfoContainer not found");
            }
            
            // Show user nav in sidebar
            if (userNav) {
                userNav.style.display = '';
                console.log("  • Showing userNav");
            } else {
                console.warn("  ⚠ userNav not found");
            }
        }
    },
    
    logout: function(e) { // Added logout function
        e.preventDefault(); // Prevent default link behavior
        console.log('[huntarrUI] Logging out...');
        HuntarrUtils.fetchWithTimeout('./logout', { // Use the correct endpoint defined in Flask
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('[huntarrUI] Logout successful, redirecting to login.');
                window.location.href = './login'; // Redirect to login page
            } else {
                console.error('[huntarrUI] Logout failed:', data.message);
                this.showNotification('Logout failed. Please try again.', 'error');
            }
        })
        .catch(error => {
            console.error('Error during logout:', error);
            this.showNotification('An error occurred during logout.', 'error');
        });
    },
    
    // Media statistics handling
    loadMediaStats: function() {
        // Prevent multiple simultaneous stats loading
        if (this.isLoadingStats) {
            console.debug('Stats already loading, skipping duplicate request');
            return;
        }
        
        this.isLoadingStats = true;
        
        // Try to load cached stats first for immediate display
        const cachedStats = localStorage.getItem('huntarr-stats-cache');
        if (cachedStats) {
            try {
                const parsedStats = JSON.parse(cachedStats);
                const cacheAge = Date.now() - (parsedStats.timestamp || 0);
                // Use cache if less than 5 minutes old
                if (cacheAge < 300000) {
                    console.log('[huntarrUI] Using cached stats for immediate display');
                    this.updateStatsDisplay(parsedStats.stats, true); // true = from cache
                }
            } catch (e) {
                console.log('[huntarrUI] Failed to parse cached stats');
            }
        }
        
        // Add loading class to stats container to hide raw JSON
        const statsContainer = document.querySelector('.media-stats-container');
        if (statsContainer) {
            statsContainer.classList.add('stats-loading');
        }
        
        HuntarrUtils.fetchWithTimeout('./api/stats')
            .then(response => {
                if (!response.ok) {
                    throw new Error('Network response was not ok');
                }
                return response.json();
            })
            .then(data => {
                if (data.success && data.stats) {
                    // Store raw stats data globally for tooltips to access
                    window.mediaStats = data.stats;
                    
                    // Cache the fresh stats with timestamp
                    localStorage.setItem('huntarr-stats-cache', JSON.stringify({
                        stats: data.stats,
                        timestamp: Date.now()
                    }));
                    
                    // Update display
                    this.updateStatsDisplay(data.stats);
                    
                    // Remove loading class after stats are loaded
                    if (statsContainer) {
                        statsContainer.classList.remove('stats-loading');
                    }
                } else {
                    console.error('Failed to load statistics:', data.message || 'Unknown error');
                }
            })
            .catch(error => {
                console.error('Error fetching statistics:', error);
                // Remove loading class on error too
                if (statsContainer) {
                    statsContainer.classList.remove('stats-loading');
                }
            })
            .finally(() => {
                // Always clear the loading flag
                this.isLoadingStats = false;
            });
    },
    
    updateStatsDisplay: function(stats, isFromCache = false) {
        // Update each app's statistics
        const apps = ['sonarr', 'radarr', 'lidarr', 'readarr', 'whisparr', 'eros', 'swaparr'];
        const statTypes = ['hunted', 'upgraded'];
        
        // More robust low usage mode detection - check multiple sources
        const isLowUsageMode = this.isLowUsageModeEnabled();
        
        
        console.log(`[huntarrUI] updateStatsDisplay - Low usage mode: ${isLowUsageMode}, from cache: ${isFromCache}`);
        
        apps.forEach(app => {
            if (stats[app]) {
                statTypes.forEach(type => {
                    const element = document.getElementById(`${app}-${type}`);
                    if (element) {
                        // Get current and target values, ensuring they're valid numbers
                        const currentText = element.textContent || '0';
                        const currentValue = this.parseFormattedNumber(currentText);
                        const targetValue = Math.max(0, parseInt(stats[app][type]) || 0); // Ensure non-negative
                        
                        // If low usage mode is enabled or loading from cache, skip animations and set values directly
                        if (isLowUsageMode || isFromCache) {
                            element.textContent = this.formatLargeNumber(targetValue);
                        } else {
                            // Only animate if values are different and both are valid
                            if (currentValue !== targetValue && !isNaN(currentValue) && !isNaN(targetValue)) {
                                // Cancel any existing animation for this element
                                if (element.animationFrame) {
                                    cancelAnimationFrame(element.animationFrame);
                                }
                                
                                // Animate the number change
                                this.animateNumber(element, currentValue, targetValue);
                            } else if (isNaN(currentValue) || currentValue < 0) {
                                // If current value is invalid, set directly without animation
                                element.textContent = this.formatLargeNumber(targetValue);
                            }
                        }
                    }
                });
            }
        });
    },

    // Helper function to parse formatted numbers back to integers
    parseFormattedNumber: function(formattedStr) {
        if (!formattedStr || typeof formattedStr !== 'string') return 0;
        
        // Remove any formatting (K, M, commas, etc.)
        const cleanStr = formattedStr.replace(/[^\d.-]/g, '');
        const parsed = parseInt(cleanStr);
        
        // Handle K and M suffixes
        if (formattedStr.includes('K')) {
            return Math.floor(parsed * 1000);
        } else if (formattedStr.includes('M')) {
            return Math.floor(parsed * 1000000);
        }
        
        return isNaN(parsed) ? 0 : Math.max(0, parsed);
    },

    animateNumber: function(element, start, end) {
        // Ensure start and end are valid numbers
        start = Math.max(0, parseInt(start) || 0);
        end = Math.max(0, parseInt(end) || 0);
        
        // If start equals end, just set the value
        if (start === end) {
            element.textContent = this.formatLargeNumber(end);
            return;
        }
        
        const duration = 600; // Animation duration in milliseconds - reduced for faster loading feel
        const startTime = performance.now();
        
        const updateNumber = (currentTime) => {
            const elapsedTime = currentTime - startTime;
            const progress = Math.min(elapsedTime / duration, 1);
            
            // Easing function for smooth animation
            const easeOutQuad = progress * (2 - progress);
            
            const currentValue = Math.max(0, Math.floor(start + (end - start) * easeOutQuad));
            
            // Format number for display
            element.textContent = this.formatLargeNumber(currentValue);
            
            if (progress < 1) {
                // Store the animation frame ID to allow cancellation
                element.animationFrame = requestAnimationFrame(updateNumber);
            } else {
                // Ensure we end with the exact formatted target number
                element.textContent = this.formatLargeNumber(end);
                // Clear the animation frame reference
                element.animationFrame = null;
            }
        };
        
        // Store the animation frame ID to allow cancellation
        element.animationFrame = requestAnimationFrame(updateNumber);
    },
    
    // Format large numbers with appropriate suffixes (K, M, B, T)  
    formatLargeNumber: function(num) {
        if (num < 1000) {
            // 0-999: Display as is
            return num.toString();
        } else if (num < 10000) {
            // 1,000-9,999: Display with single decimal and K (e.g., 5.2K)
            return (num / 1000).toFixed(1) + 'K';
        } else if (num < 100000) {
            // 10,000-99,999: Display with single decimal and K (e.g., 75.4K)
            return (num / 1000).toFixed(1) + 'K';
        } else if (num < 1000000) {
            // 100,000-999,999: Display with K (no decimal) (e.g., 982K)
            return Math.floor(num / 1000) + 'K';
        } else if (num < 10000000) {
            // 1,000,000-9,999,999: Display with single decimal and M (e.g., 9.7M)
            return (num / 1000000).toFixed(1) + 'M';
        } else if (num < 100000000) {
            // 10,000,000-99,999,999: Display with single decimal and M (e.g., 99.7M)
            return (num / 1000000).toFixed(1) + 'M';
        } else if (num < 1000000000) {
            // 100,000,000-999,999,999: Display with M (no decimal)
            return Math.floor(num / 1000000) + 'M';
        } else if (num < 1000000000000) {
            // 1B - 999B: Display with single decimal and B
            return (num / 1000000000).toFixed(1) + 'B';
        } else {
            // 1T+: Display with T
            return (num / 1000000000000).toFixed(1) + 'T';
        }
    },

    resetMediaStats: function(appType = null) {
        // Directly update the UI first to provide immediate feedback
        const stats = {
            'sonarr': {'hunted': 0, 'upgraded': 0},
            'radarr': {'hunted': 0, 'upgraded': 0},
            'lidarr': {'hunted': 0, 'upgraded': 0},
            'readarr': {'hunted': 0, 'upgraded': 0},
            'whisparr': {'hunted': 0, 'upgraded': 0},
            'eros': {'hunted': 0, 'upgraded': 0}
        };
        
        // Immediately update UI before even showing the confirmation
        if (appType) {
            // Only reset the specific app's stats
            this.updateStatsDisplay({
                [appType]: stats[appType]
            });
        } else {
            // Reset all stats
            this.updateStatsDisplay(stats);
        }
        
        // Show a success notification
        this.showNotification('Statistics reset successfully', 'success');

        // Try to send the reset to the server, but don't depend on it
        try {
            const requestBody = appType ? { app_type: appType } : {};
            
            HuntarrUtils.fetchWithTimeout('./api/stats/reset_public', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify(requestBody)
            })
            .then(response => {
                // Just log the response, don't rely on it for UI feedback
                if (!response.ok) {
                    console.warn('Server responded with non-OK status for stats reset');
                }
                return response.json().catch(() => ({}));
            })
            .then(data => {
                console.log('Stats reset response:', data);
            })
            .catch(error => {
                console.warn('Error communicating with server for stats reset:', error);
            });
        } catch (error) {
            console.warn('Error in stats reset:', error);
        }
    },
    
    // Utility functions
    showNotification: function(message, type) {
        // Create a notification element
        const notification = document.createElement('div');
        notification.className = `notification ${type}`;
        notification.textContent = message;
        
        // Add to the document
        document.body.appendChild(notification);
        
        // Ensure any existing notification is removed first to prevent stacking
        const existingNotifications = document.querySelectorAll('.notification');
        existingNotifications.forEach(n => {
            if (n !== notification) {
                n.classList.remove('show');
                setTimeout(() => n.remove(), 300);
            }
        });
        
        // Fade in
        setTimeout(() => {
            notification.classList.add('show');
        }, 10);
        
        // Remove after a delay
        setTimeout(() => {
            notification.classList.remove('show');
            setTimeout(() => {
                notification.remove();
            }, 300);
        }, 3000);
    },
    
    capitalizeFirst: function(string) {
        return string.charAt(0).toUpperCase() + string.slice(1);
    },

    // Load current version from version.txt
    loadCurrentVersion: function() {
        HuntarrUtils.fetchWithTimeout('./version.txt')
            .then(response => {
                if (!response.ok) {
                    throw new Error('Failed to load version.txt');
                }
                return response.text();
            })
            .then(version => {
                const versionElement = document.getElementById('version-value');
                if (versionElement) {
                    versionElement.textContent = version.trim();
                    versionElement.style.display = 'inline'; // Show the element
                }
                
                // Store in localStorage for topbar access
                try {
                    const versionInfo = localStorage.getItem('huntarr-version-info') || '{}';
                    const parsedInfo = JSON.parse(versionInfo);
                    parsedInfo.currentVersion = version.trim();
                    localStorage.setItem('huntarr-version-info', JSON.stringify(parsedInfo));
                } catch (e) {
                    console.error('Error saving current version to localStorage:', e);
                }
            })
            .catch(error => {
                console.error('Error loading current version:', error);
                const versionElement = document.getElementById('version-value');
                if (versionElement) {
                    versionElement.textContent = 'Error';
                    versionElement.style.display = 'inline'; // Show the element even on error
                }
            });
    },

    // Load latest version from GitHub releases
    loadLatestVersion: function() {
        HuntarrUtils.fetchWithTimeout('https://api.github.com/repos/plexguide/Huntarr.io/releases/latest')
            .then(response => {
                if (!response.ok) {
                    // Handle rate limiting or other errors
                    if (response.status === 403) {
                        console.warn('GitHub API rate limit likely exceeded.');
                        throw new Error('Rate limited');
                    }
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                const latestVersionElement = document.getElementById('latest-version-value');
                if (latestVersionElement && data && data.tag_name) {
                    // Remove potential 'v' prefix for consistency if needed, or keep it
                    latestVersionElement.textContent = data.tag_name;
                    latestVersionElement.style.display = 'inline'; // Show the element
                    
                    // Store in localStorage for topbar access
                    try {
                        const versionInfo = localStorage.getItem('huntarr-version-info') || '{}';
                        const parsedInfo = JSON.parse(versionInfo);
                        parsedInfo.latestVersion = data.tag_name;
                        localStorage.setItem('huntarr-version-info', JSON.stringify(parsedInfo));
                    } catch (e) {
                        console.error('Error saving latest version to localStorage:', e);
                    }
                } else if (latestVersionElement) {
                     latestVersionElement.textContent = 'N/A';
                     latestVersionElement.style.display = 'inline'; // Show the element
                }
            })
            .catch(error => {
                console.error('Error loading latest version from GitHub:', error);
                const latestVersionElement = document.getElementById('latest-version-value');
                if (latestVersionElement) {
                    latestVersionElement.textContent = error.message === 'Rate limited' ? 'Rate Limited' : 'Error';
                    latestVersionElement.style.display = 'inline'; // Show the element even on error
                }
            });
    },
    
    // Load latest beta version from GitHub tags
    loadBetaVersion: function() {
        HuntarrUtils.fetchWithTimeout('https://api.github.com/repos/plexguide/Huntarr.io/tags?per_page=100')
            .then(response => {
                if (!response.ok) {
                    // Handle rate limiting or other errors
                    if (response.status === 403) {
                        console.warn('GitHub API rate limit likely exceeded.');
                        throw new Error('Rate limited');
                    }
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                const betaVersionElement = document.getElementById('beta-version-value');
                
                if (betaVersionElement && data && Array.isArray(data) && data.length > 0) {
                    // Find the first tag that starts with B (case insensitive)
                    const betaTag = data.find(tag => tag.name.toUpperCase().startsWith('B'));
                    
                    if (betaTag) {
                        betaVersionElement.textContent = betaTag.name;
                        // Store in localStorage for future reference
                        try {
                            const versionInfo = localStorage.getItem('huntarr-version-info') || '{}';
                            const parsedInfo = JSON.parse(versionInfo);
                            parsedInfo.betaVersion = betaTag.name;
                            localStorage.setItem('huntarr-version-info', JSON.stringify(parsedInfo));
                        } catch (e) {
                            console.error('Error saving beta version to localStorage:', e);
                        }
                    } else {
                        betaVersionElement.textContent = 'None';
                    }
                } else if (betaVersionElement) {
                    betaVersionElement.textContent = 'N/A';
                }
            })
            .catch(error => {
                console.error('Error loading beta version from GitHub:', error);
                const betaVersionElement = document.getElementById('beta-version-value');
                if (betaVersionElement) {
                    betaVersionElement.textContent = error.message === 'Rate limited' ? 'Rate Limited' : 'Error';
                }
            });
    },

    // Load GitHub star count
    loadGitHubStarCount: function() {
        const starsElement = document.getElementById('github-stars-value');
        if (!starsElement) return;
        
        // First, try to load from cache immediately for fast display
        const cachedData = localStorage.getItem('huntarr-github-stars');
        if (cachedData) {
            try {
                const parsed = JSON.parse(cachedData);
                if (parsed.stars !== undefined) {
                    starsElement.textContent = parsed.stars.toLocaleString();
                    // If cache is recent (less than 1 hour), skip API call
                    const cacheAge = Date.now() - (parsed.timestamp || 0);
                    if (cacheAge < 3600000) { // 1 hour = 3600000ms
                        return;
                    }
                }
            } catch (e) {
                console.warn('Invalid cached star data, will fetch fresh');
                localStorage.removeItem('huntarr-github-stars');
            }
        }
        
        starsElement.textContent = 'Loading...';
        
        // GitHub API endpoint for repository information
        const apiUrl = 'https://api.github.com/repos/plexguide/huntarr';
        
        HuntarrUtils.fetchWithTimeout(apiUrl)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`GitHub API error: ${response.status}`);
                }
                return response.json();
            })
            .then(data => {
                if (data && data.stargazers_count !== undefined) {
                    // Format the number with commas for thousands
                    const formattedStars = data.stargazers_count.toLocaleString();
                    starsElement.textContent = formattedStars;
                    
                    // Store in localStorage to avoid excessive API requests
                    const cacheData = {
                        stars: data.stargazers_count,
                        timestamp: Date.now()
                    };
                    localStorage.setItem('huntarr-github-stars', JSON.stringify(cacheData));
                } else {
                    throw new Error('Star count not found in response');
                }
            })
            .catch(error => {
                console.error('Error fetching GitHub stars:', error);
                
                // Try to load from cache if we have it
                const cachedData = localStorage.getItem('huntarr-github-stars');
                if (cachedData) {
                    try {
                        const parsed = JSON.parse(cachedData);
                        if (parsed.stars !== undefined) {
                            starsElement.textContent = parsed.stars.toLocaleString();
                        } else {
                            starsElement.textContent = 'N/A';
                        }
                    } catch (e) {
                        console.error('Failed to parse cached star data:', e);
                        starsElement.textContent = 'N/A';
                        localStorage.removeItem('huntarr-github-stars'); // Clear bad cache
                    }
                } else {
                    starsElement.textContent = 'N/A';
                }
            });
    },

    // Update home connection status
    updateHomeConnectionStatus: function() {
        console.log('[huntarrUI] Updating home connection statuses...');
        // This function should ideally call checkAppConnection for all relevant apps
        // or use the stored configuredApps status if checkAppConnection updates it.
        this.checkAppConnections(); // Re-check all connections after a save might be simplest
    },
    
    // Load stateful management info
    loadStatefulInfo: function(attempts = 0, skipCache = false) {
        const initialStateEl = document.getElementById('stateful_initial_state');
        const expiresDateEl = document.getElementById('stateful_expires_date');
        const intervalInput = document.getElementById('stateful_management_hours');
        const intervalDaysSpan = document.getElementById('stateful_management_days');
        
        // Max retry attempts - increased for better reliability
        const maxAttempts = 5;
        
        console.log(`[StatefulInfo] Loading stateful info (attempt ${attempts + 1}, skipCache: ${skipCache})`);
        
        // Update UI to show loading state instead of N/A on first attempt
        if (attempts === 0) {
            if (initialStateEl && initialStateEl.textContent !== 'Loading...') initialStateEl.textContent = 'Loading...';
            if (expiresDateEl && expiresDateEl.textContent !== 'Updating...') expiresDateEl.textContent = 'Loading...';
        }
        
        // First check if we have cached data in localStorage that we can use immediately
        const cachedStatefulData = localStorage.getItem('huntarr-stateful-data');
        if (!skipCache && cachedStatefulData && attempts === 0) {
            try {
                const parsedData = JSON.parse(cachedStatefulData);
                const cacheAge = Date.now() - parsedData.timestamp;
                
                // Use cache if it's less than 5 minutes old while waiting for fresh data
                if (cacheAge < 300000) {
                    console.log('[StatefulInfo] Using cached data while fetching fresh data');
                    
                    // Display cached data
                    if (initialStateEl && parsedData.created_at_ts) {
                        const createdDate = new Date(parsedData.created_at_ts * 1000);
                        initialStateEl.textContent = this.formatDateNicely(createdDate);
                    }
                    
                    if (expiresDateEl && parsedData.expires_at_ts) {
                        const expiresDate = new Date(parsedData.expires_at_ts * 1000);
                        expiresDateEl.textContent = this.formatDateNicely(expiresDate);
                    }
                    
                    // Update interval input and days display
                    if (intervalInput && parsedData.interval_hours) {
                        intervalInput.value = parsedData.interval_hours;
                        if (intervalDaysSpan) {
                            const days = (parsedData.interval_hours / 24).toFixed(1);
                            intervalDaysSpan.textContent = `${days} days`;
                        }
                    }
                }
            } catch (e) {
                console.warn('[StatefulInfo] Error parsing cached data:', e);
            }
        }
        
        // Always fetch fresh data from the server
        HuntarrUtils.fetchWithTimeout('./api/stateful/info', { 
            cache: 'no-cache',
            headers: {
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status} ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                // Cache the response with a timestamp for future use
                localStorage.setItem('huntarr-stateful-data', JSON.stringify({
                    ...data,
                    timestamp: Date.now()
                }));
                
                // Handle initial state date
                if (initialStateEl) {
                    if (data.created_at_ts) {
                        const createdDate = new Date(data.created_at_ts * 1000);
                        initialStateEl.textContent = this.formatDateNicely(createdDate);
                    } else {
                        initialStateEl.textContent = 'Not yet created';
                        
                        // If this is the first state load attempt and no timestamp exists,
                        // it might be because the state file hasn't been created yet
                        if (attempts < maxAttempts) {
                            console.log(`[StatefulInfo] No initial state timestamp, will retry (${attempts + 1}/${maxAttempts})`);
                            setTimeout(() => {
                                this.loadStatefulInfo(attempts + 1);
                            }, 500); // Longer delay for better chance of success
                            return;
                        }
                    }
                }
                
                // Handle expiration date
                if (expiresDateEl) {
                    if (data.expires_at_ts) {
                        const expiresDate = new Date(data.expires_at_ts * 1000);
                        expiresDateEl.textContent = this.formatDateNicely(expiresDate);
                    } else {
                        expiresDateEl.textContent = 'Not set';
                    }
                }
                
                // Update interval input and days display
                if (intervalInput && data.interval_hours) {
                    intervalInput.value = data.interval_hours;
                    if (intervalDaysSpan) {
                        const days = (data.interval_hours / 24).toFixed(1);
                        intervalDaysSpan.textContent = `${days} days`;
                    }
                }
                
                // Hide error notification if it was visible
                const notification = document.getElementById('stateful-notification');
                if (notification) {
                    notification.style.display = 'none';
                }
                
                // Store the data for future reference
                this._cachedStatefulData = data;
                
                console.log('[StatefulInfo] Successfully loaded and displayed stateful data');
            } else {
                throw new Error(data.message || 'Failed to load stateful info');
            }
        })
        .catch(error => {
            console.error(`Error loading stateful info (attempt ${attempts + 1}/${maxAttempts + 1}):`, error);
            
            // Retry if we haven't reached max attempts with exponential backoff
            if (attempts < maxAttempts) {
                const delay = Math.min(2000, 300 * Math.pow(2, attempts)); // Exponential backoff with max 2000ms
                console.log(`[StatefulInfo] Retrying in ${delay}ms (attempt ${attempts + 1}/${maxAttempts})`);
                setTimeout(() => {
                    // Double-check if still on the same page before retrying
                    if (document.getElementById('stateful_management_hours')) {
                        this.loadStatefulInfo(attempts + 1);
                    } else {
                        console.log(`[StatefulInfo] Stateful info retry cancelled; user navigated away.`);
                    }
                }, delay);
                return;
            }
            
            // Use cached data as fallback if available
            const cachedStatefulData = localStorage.getItem('huntarr-stateful-data');
            if (cachedStatefulData) {
                try {
                    console.log('[StatefulInfo] Using cached data as fallback after failed fetch');
                    const parsedData = JSON.parse(cachedStatefulData);
                    
                    if (initialStateEl && parsedData.created_at_ts) {
                        const createdDate = new Date(parsedData.created_at_ts * 1000);
                        initialStateEl.textContent = this.formatDateNicely(createdDate) + ' (cached)';
                    } else if (initialStateEl) {
                        initialStateEl.textContent = 'Not available';
                    }
                    
                    if (expiresDateEl && parsedData.expires_at_ts) {
                        const expiresDate = new Date(parsedData.expires_at_ts * 1000);
                        expiresDateEl.textContent = this.formatDateNicely(expiresDate) + ' (cached)';
                    } else if (expiresDateEl) {
                        expiresDateEl.textContent = 'Not available';
                    }
                    
                    // Update interval input and days display from cache
                    if (intervalInput && parsedData.interval_hours) {
                        intervalInput.value = parsedData.interval_hours;
                        if (intervalDaysSpan) {
                            const days = (parsedData.interval_hours / 24).toFixed(1);
                            intervalDaysSpan.textContent = `${days} days`;
                        }
                    }
                    
                    return;
                } catch (e) {
                    console.warn('[StatefulInfo] Error parsing cached data as fallback:', e);
                }
            }
            
            // Final fallback if no cached data
            if (initialStateEl) initialStateEl.textContent = 'Not available';
            if (expiresDateEl) expiresDateEl.textContent = 'Not available';
            
            // Show error notification
            const notification = document.getElementById('stateful-notification');
            if (notification) {
                notification.style.display = 'block';
                notification.textContent = 'Could not load stateful management info. This may affect media tracking.';
            }
        });
    },
    
    // Format date nicely with time, day, and relative time indication
    formatDateNicely: function(date) {
        if (!(date instanceof Date) || isNaN(date)) {
            console.warn('[formatDateNicely] Invalid date provided:', date);
            return 'Invalid date';
        }
        
        // Get the user's configured timezone from settings or default to UTC
        const userTimezone = this.getUserTimezone();
        
        console.log(`[formatDateNicely] Formatting date ${date.toISOString()} for timezone: ${userTimezone}`);
        
        const options = { 
            weekday: 'short',
            year: 'numeric', 
            month: 'short', 
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            hour12: false, // Use 24-hour format (global world time)
            timeZone: userTimezone
        };
        
        let formattedDate;
        try {
            formattedDate = date.toLocaleDateString(undefined, options);
            console.log(`[formatDateNicely] Formatted result: ${formattedDate}`);
        } catch (error) {
            console.error(`[formatDateNicely] Error formatting date with timezone ${userTimezone}:`, error);
            // Fallback to UTC if timezone is invalid
            const fallbackOptions = { ...options, timeZone: 'UTC' };
            formattedDate = date.toLocaleDateString(undefined, fallbackOptions) + ' (UTC fallback)';
        }
        
        // Add relative time indicator (e.g., "in 6 days" or "7 days ago")
        const now = new Date();
        const diffTime = date.getTime() - now.getTime();
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));
        
        let relativeTime = '';
        if (diffDays > 0) {
            relativeTime = ` (in ${diffDays} day${diffDays !== 1 ? 's' : ''})`;
        } else if (diffDays < 0) {
            relativeTime = ` (${Math.abs(diffDays)} day${Math.abs(diffDays) !== 1 ? 's' : ''} ago)`;
        } else {
            relativeTime = ' (today)';
        }
        
        return `${formattedDate}${relativeTime}`;
    },
    
    // Helper function to get the user's configured timezone from settings
    getUserTimezone: function() {
        // Assume UTC as default if no timezone is set
        const defaultTimezone = 'UTC';
        
        // Try multiple sources for the timezone setting
        let timezone = null;
        
        // 1. Try to get from originalSettings.general
        if (this.originalSettings && this.originalSettings.general && this.originalSettings.general.timezone) {
            timezone = this.originalSettings.general.timezone;
        }
        
        // 2. Try to get from the timezone dropdown if it exists (for immediate updates)
        if (!timezone) {
            const timezoneSelect = document.getElementById('timezone');
            if (timezoneSelect && timezoneSelect.value) {
                timezone = timezoneSelect.value;
            }
        }
        
        // 3. Try to get from localStorage cache
        if (!timezone) {
            const cachedSettings = localStorage.getItem('huntarr-settings-cache');
            if (cachedSettings) {
                try {
                    const parsed = JSON.parse(cachedSettings);
                    if (parsed.general && parsed.general.timezone) {
                        timezone = parsed.general.timezone;
                    }
                } catch (e) {
                    console.warn('[getUserTimezone] Error parsing cached settings:', e);
                }
            }
        }
        
        // 4. Fallback to default
        if (!timezone) {
            timezone = defaultTimezone;
        }
        
        console.log(`[getUserTimezone] Using timezone: ${timezone}`);
        return timezone;
    },
    
    // Reset stateful management - clear all processed IDs
    resetStatefulManagement: function() {
        console.log("Reset stateful management function called");
        
        // Show a loading indicator or disable the button
        const resetBtn = document.getElementById('reset_stateful_btn');
        if (resetBtn) {
            resetBtn.disabled = true;
            const originalText = resetBtn.innerHTML;
            resetBtn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Resetting...';
            console.log("Reset button found and disabled:", resetBtn);
        } else {
            console.error("Reset button not found in the DOM!");
        }
        
        // Add debug logging
        console.log("Sending reset request to /api/stateful/reset");
        
        HuntarrUtils.fetchWithTimeout('./api/stateful/reset', {
            method: 'POST',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache'
            },
            cache: 'no-cache' // Add cache control to prevent caching
        })
        .then(response => {
            console.log("Reset response received:", response.status, response.statusText);
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log("Reset response data:", data);
            
            if (data.success) {
                this.showNotification('Stateful management reset successfully', 'success');
                // Wait a moment before reloading the info to ensure it's refreshed
                setTimeout(() => {
                    this.loadStatefulInfo(0); // Reload stateful info with fresh attempt
                    
                    // Re-enable the button
                    if (resetBtn) {
                        resetBtn.disabled = false;
                        resetBtn.innerHTML = '<i class="fas fa-trash"></i> Reset';
                    }
                }, 1000);
            } else {
                throw new Error(data.message || 'Unknown error resetting stateful management');
            }
        })
        .catch(error => {
             console.error("Error resetting stateful management:", error);
             this.showNotification(`Error resetting stateful management: ${error.message}`, 'error');
            
             // Re-enable the button
             if (resetBtn) {
                 resetBtn.disabled = false;
                 resetBtn.innerHTML = '<i class="fas fa-trash"></i> Reset';
             }
        });
    },
    
    // Update stateful management expiration based on hours input
    updateStatefulExpirationOnUI: function() {
        const hoursInput = document.getElementById('stateful_management_hours');
        if (!hoursInput) return;
        
        const hours = parseInt(hoursInput.value) || 168;
        
        // Show updating indicator
        const expiresDateEl = document.getElementById('stateful_expires_date');
        const initialStateEl = document.getElementById('stateful_initial_state');
        
        if (expiresDateEl) {
            expiresDateEl.textContent = 'Updating...';
        }
        
        const url = './api/stateful/update-expiration';
        const cleanedUrl = this.cleanUrlString(url);
        
        HuntarrUtils.fetchWithTimeout(cleanedUrl, {
            method: 'POST',
            headers: {
                'Accept': 'application/json',
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ hours: hours }),
            cache: 'no-cache'
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status} ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                console.log('[huntarrUI] Stateful expiration updated successfully:', data);
                
                // Get updated info to show proper dates
                this.loadStatefulInfo();
                
                // Show a notification
                this.showNotification(`Updated expiration to ${hours} hours (${(hours/24).toFixed(1)} days)`, 'success');
            } else {
                throw new Error(data.message || 'Unknown error updating expiration');
            }
        })
        .catch(error => {
             console.error('Error updating stateful expiration:', error);
             this.showNotification(`Failed to update expiration: ${error.message}`, 'error');
             // Reset the UI
             if (expiresDateEl) {
                 expiresDateEl.textContent = 'Error updating';
             }
             
             // Try to reload original data
             setTimeout(() => this.loadStatefulInfo(), 1000);
        });
    },

    // Add the updateStatefulExpiration method
    updateStatefulExpiration: function(hours) {
        if (!hours || typeof hours !== 'number' || hours <= 0) {
            console.error('[huntarrUI] Invalid hours value for updateStatefulExpiration:', hours);
            return;
        }
        
        console.log(`[huntarrUI] Directly updating stateful expiration to ${hours} hours`);
        
        // Make a direct API call to update the stateful expiration
        HuntarrUtils.fetchWithTimeout('./api/stateful/update-expiration', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ hours: hours })
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! Status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log('[huntarrUI] Stateful expiration updated successfully:', data);
            // Update the expiration date display
            const expiresDateEl = document.getElementById('stateful_expires_date');
            if (expiresDateEl && data.expires_date) {
                expiresDateEl.textContent = data.expires_date;
            }
        })
        .catch(error => {
            console.error('[huntarrUI] Error updating stateful expiration:', error);
        });
    },
    
    // Add global event handler and method to track saved settings across all apps
    // Auto-save enabled - unsaved changes handlers removed
    
    // Add a proper hasFormChanges function to compare form values with original values
    hasFormChanges: function(app) {
        // If we don't have original settings or current app settings, we can't compare
        if (!this.originalSettings || !this.originalSettings[app]) {
            return false;
        }
        
        // Get current settings from the form
        const currentSettings = this.getFormSettings(app);
        
        // For complex objects like instances, we need to stringify them for comparison
        const originalJSON = JSON.stringify(this.originalSettings[app]);
        const currentJSON = JSON.stringify(currentSettings);
        
        return originalJSON !== currentJSON;
    },
    
    // Check if Low Usage Mode is enabled in settings and apply it
    checkLowUsageMode: function() {
        return HuntarrUtils.fetchWithTimeout('./api/settings/general', {
            method: 'GET'
        })
        .then(response => response.json())
        .then(config => {
            if (config && config.low_usage_mode === true) {
                this.applyLowUsageMode(true);
            } else {
                this.applyLowUsageMode(false);
            }
            return config;
        })
        .catch(error => {
            console.error('[huntarrUI] Error checking Low Usage Mode:', error);
            // Default to disabled on error
            this.applyLowUsageMode(false);
            throw error;
        });
    },
    
    // Apply Low Usage Mode effects based on setting
    applyLowUsageMode: function(enabled) {
        console.log(`[huntarrUI] Setting Low Usage Mode: ${enabled ? 'Enabled' : 'Disabled'}`);
        
        // Store the previous state to detect changes
        const wasEnabled = document.body.classList.contains('low-usage-mode');
        
        if (enabled) {
            // Add CSS class to body to disable animations
            document.body.classList.add('low-usage-mode');
            
            // Low Usage Mode now runs without any visual indicator for a cleaner interface
        } else {
            // Remove CSS class from body to enable animations
            document.body.classList.remove('low-usage-mode');
        }
        
        // If low usage mode state changed and we have stats data, update the display
        if (wasEnabled !== enabled && window.mediaStats) {
            console.log(`[huntarrUI] Low usage mode changed from ${wasEnabled} to ${enabled}, updating stats display`);
            this.updateStatsDisplay(window.mediaStats);
        }
    },

    // Apply timezone change immediately
    applyTimezoneChange: function(timezone) {
        console.log(`[huntarrUI] Applying timezone change to: ${timezone}`);
        
        // Call the backend to apply timezone immediately
        fetch('./api/settings/apply-timezone', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ timezone: timezone })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('[huntarrUI] Timezone applied successfully');
                this.showNotification(`Timezone changed to ${timezone}`, 'success');
                
                // Refresh any time displays that might be affected
                this.refreshTimeDisplays();
            } else {
                console.error('[huntarrUI] Failed to apply timezone:', data.error);
                this.showNotification(`Failed to apply timezone: ${data.error}`, 'error');
            }
        })
        .catch(error => {
            console.error('[huntarrUI] Error applying timezone:', error);
            this.showNotification(`Error applying timezone: ${error.message}`, 'error');
        });
    },

    // Apply authentication mode change immediately
    applyAuthModeChange: function(authMode) {
        console.log(`[huntarrUI] Authentication mode changed to: ${authMode}`);
        
        // Show notification about the change
        const modeNames = {
            'login': 'Login Mode',
            'local_bypass': 'Local Bypass Mode', 
            'no_login': 'No Login Mode'
        };
        
        const modeName = modeNames[authMode] || authMode;
        this.showNotification(`Authentication mode changed to ${modeName}`, 'info');
        
        // Add warning for No Login Mode
        if (authMode === 'no_login') {
            setTimeout(() => {
                this.showNotification('Warning: No Login Mode disables all authentication. Ensure your reverse proxy is securing access!', 'warning');
            }, 1000);
        }
    },

    // Apply update checking change immediately
    applyUpdateCheckingChange: function(enabled) {
        console.log(`[huntarrUI] Update checking ${enabled ? 'enabled' : 'disabled'}`);
        // Silent update - no notification needed for auto-save
    },

    // Refresh time displays after timezone change
    refreshTimeDisplays: function() {
        // Refresh any elements that display time and might be affected by timezone changes
        const timeElements = document.querySelectorAll('[data-time], .time-display, .timestamp');
        timeElements.forEach(element => {
            // If element has a refresh method or data attribute, trigger refresh
            if (element.dataset.refreshTime) {
                // Custom refresh logic could go here
                console.log('[huntarrUI] Refreshing time display element');
            }
        });
        
        // Refresh logs if they're currently visible (they contain timestamps)
        if (this.currentSection === 'logs') {
            console.log('[huntarrUI] Refreshing logs for timezone change');
            // The logs will refresh automatically via the EventSource, but we could trigger a manual refresh here if needed
        }
    },
    
    // Reset the app cycle for a specific app
    resetAppCycle: function(app, button) {
        // Make sure we have the app and button elements
        if (!app || !button) {
            console.error('[huntarrUI] Missing app or button for resetAppCycle');
            return;
        }
        
        // First, disable the button to prevent multiple clicks
        button.disabled = true;
        button.innerHTML = '<i class="fas fa-circle-notch fa-spin"></i> Resetting...';
        
        // API endpoint
        const endpoint = `./api/cycle/reset/${app}`;
        
        HuntarrUtils.fetchWithTimeout(endpoint, {
            method: 'POST'
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`Failed to reset ${app} cycle`);
            }
            return response.json();
        })
        .then(data => {
            this.showNotification(`Successfully reset ${this.capitalizeFirst(app)} cycle`, 'success');
            console.log(`[huntarrUI] Reset ${app} cycle response:`, data);
            
            // Re-enable the button with original text
            button.disabled = false;
            button.innerHTML = `<i class="fas fa-sync-alt"></i> Reset`;
        })
        .catch(error => {
            console.error(`[huntarrUI] Error resetting ${app} cycle:`, error);
            this.showNotification(`Error resetting ${this.capitalizeFirst(app)} cycle: ${error.message}`, 'error');
            
            // Re-enable the button with original text
            button.disabled = false;
            button.innerHTML = `<i class="fas fa-sync-alt"></i> Reset`;
        });
    },

    // More robust low usage mode detection
    isLowUsageModeEnabled: function() {
        // Check multiple sources to determine if low usage mode is enabled
        
        // 1. Check CSS class on body (primary method)
        const hasLowUsageClass = document.body.classList.contains('low-usage-mode');
        
        // 2. Check if the standalone low-usage-mode.js module is enabled
        const standaloneModuleEnabled = window.LowUsageMode && window.LowUsageMode.isEnabled && window.LowUsageMode.isEnabled();
        
        // 3. Final determination based on reliable sources (no indicator checking needed)
        const isEnabled = hasLowUsageClass || standaloneModuleEnabled;
        
        console.log(`[huntarrUI] Low usage mode detection - CSS class: ${hasLowUsageClass}, Module: ${standaloneModuleEnabled}, Final: ${isEnabled}`);
        
        return isEnabled;
    },

    showDashboard: function() {
        // Make the dashboard grid visible after initialization to prevent FOUC
        const dashboardGrid = document.querySelector('.dashboard-grid');
        if (dashboardGrid) {
            dashboardGrid.style.opacity = '1';
            console.log('[huntarrUI] Dashboard made visible after initialization');
        } else {
            console.warn('[huntarrUI] Dashboard grid not found');
        }
    },

    applyFilterToSingleEntry: function(logEntry, selectedLevel) {
        // Apply the same filtering logic used in filterLogsByLevel to a single entry
        const levelBadge = logEntry.querySelector('.log-level-badge, .log-level, .log-level-error, .log-level-warning, .log-level-info, .log-level-debug');
        
        // Clear any existing filter attribute first
        logEntry.removeAttribute('data-hidden-by-filter');
        
        if (levelBadge) {
            // Get the level from the badge text
            let entryLevel = '';
            
            // Get badge text and normalize it
            const badgeText = levelBadge.textContent.toLowerCase().trim();
            
            // Fixed mapping - match the actual badge text created in log entries
            switch(badgeText) {
                case 'information':
                case 'info':
                    entryLevel = 'info';
                    break;
                case 'warning':
                case 'warn':
                    entryLevel = 'warning';
                    break;
                case 'error':
                    entryLevel = 'error';
                    break;
                case 'debug':
                    entryLevel = 'debug';
                    break;
                case 'fatal':
                case 'critical':
                    entryLevel = 'error'; // Map fatal/critical to error for filtering
                    break;
                default:
                    // Try class-based detection as secondary method
                    if (levelBadge.classList.contains('log-level-error')) {
                        entryLevel = 'error';
                    } else if (levelBadge.classList.contains('log-level-warning')) {
                        entryLevel = 'warning';
                    } else if (levelBadge.classList.contains('log-level-info')) {
                        entryLevel = 'info';
                    } else if (levelBadge.classList.contains('log-level-debug')) {
                        entryLevel = 'debug';
                    } else {
                        // NO FALLBACK - if we can't determine the level, hide it
                        entryLevel = null;
                    }
            }
            
            // Show or hide based on filter match, using data attributes for pagination cooperation
            if (entryLevel && entryLevel === selectedLevel) {
                logEntry.style.display = '';
            } else {
                logEntry.style.display = 'none';
                logEntry.setAttribute('data-hidden-by-filter', 'true');
            }
        } else {
            // If no level badge found, hide the entry when filtering
            logEntry.style.display = 'none';
            logEntry.setAttribute('data-hidden-by-filter', 'true');
        }
    },

    filterLogsByLevel: function(selectedLevel) {
        if (!this.elements.logsContainer) return;
        
        const allLogEntries = this.elements.logsContainer.querySelectorAll('.log-entry');
        let visibleCount = 0;
        let totalCount = allLogEntries.length;
        
        console.log(`[huntarrUI] Filtering logs by level: ${selectedLevel}, total entries: ${totalCount}`);
        
        // Debug: Log first few badge texts to see what we're working with
        allLogEntries.forEach((entry, index) => {
            if (index < 5) { // Log first 5 entries for debugging
                const levelBadge = entry.querySelector('.log-level-badge, .log-level, .log-level-error, .log-level-warning, .log-level-info, .log-level-debug');
                if (levelBadge) {
                    console.log(`[huntarrUI] Entry ${index}: Badge text = "${levelBadge.textContent.trim()}", Classes = ${levelBadge.className}`);
                }
            }
        });
        
        // Clear any existing filter attributes first
        allLogEntries.forEach(entry => {
            entry.removeAttribute('data-hidden-by-filter');
        });
        
        allLogEntries.forEach(entry => {
            if (selectedLevel === 'all') {
                // Show all entries - remove any filter hiding
                entry.style.display = '';
                visibleCount++;
            } else {
                // Check if this entry matches the selected level
                const levelBadge = entry.querySelector('.log-level-badge, .log-level, .log-level-error, .log-level-warning, .log-level-info, .log-level-debug');
                
                if (levelBadge) {
                    // Get the level from the badge text
                    let entryLevel = '';
                    
                    // Get badge text and normalize it
                    const badgeText = levelBadge.textContent.toLowerCase().trim();
                    
                    // Fixed mapping - match the actual badge text created in log entries
                    switch(badgeText) {
                        case 'information':
                        case 'info':
                            entryLevel = 'info';
                            break;
                        case 'warning':
                        case 'warn':
                            entryLevel = 'warning';
                            break;
                        case 'error':
                            entryLevel = 'error';
                            break;
                        case 'debug':
                            entryLevel = 'debug';
                            break;
                        case 'fatal':
                        case 'critical':
                            entryLevel = 'error'; // Map fatal/critical to error for filtering
                            break;
                        default:
                            // Try class-based detection as secondary method
                            if (levelBadge.classList.contains('log-level-error')) {
                                entryLevel = 'error';
                            } else if (levelBadge.classList.contains('log-level-warning')) {
                                entryLevel = 'warning';
                            } else if (levelBadge.classList.contains('log-level-info')) {
                                entryLevel = 'info';
                            } else if (levelBadge.classList.contains('log-level-debug')) {
                                entryLevel = 'debug';
                            } else {
                                // Log unmapped badge text for debugging
                                console.log(`[huntarrUI] Unmapped badge text: "${badgeText}" - hiding entry`);
                                entryLevel = null; // Set to null to indicate unmapped
                            }
                    }
                    
                    // Show or hide based on filter match, using data attributes for pagination cooperation
                    if (entryLevel && entryLevel === selectedLevel) {
                        entry.style.display = '';
                        visibleCount++;
                    } else {
                        entry.style.display = 'none';
                        entry.setAttribute('data-hidden-by-filter', 'true');
                    }
                } else {
                    // If no level badge found, hide the entry when filtering
                    entry.style.display = 'none';
                    entry.setAttribute('data-hidden-by-filter', 'true');
                }
            }
        });
        
        // Pagination controls remain visible at all times - removed hiding logic
        
        // Auto-scroll to top to show newest entries (logs are in reverse order)
        if (this.autoScroll && this.elements.autoScrollCheckbox && this.elements.autoScrollCheckbox.checked && visibleCount > 0) {
            setTimeout(() => {
                window.scrollTo({
                    top: 0,
                    behavior: 'smooth'
                });
            }, 100);
        }
        
        console.log(`[huntarrUI] Filtered logs by level '${selectedLevel}': showing ${visibleCount}/${totalCount} entries`);
    },
    
    // Helper method to detect JSON fragments that shouldn't be displayed as log entries
    isJsonFragment: function(logString) {
        if (!logString || typeof logString !== 'string') return false;
        
        const trimmed = logString.trim();
        
        // Check for common JSON fragment patterns
        const jsonPatterns = [
            /^"[^"]*":\s*"[^"]*",?$/,           // "key": "value",
            /^"[^"]*":\s*\d+,?$/,                // "key": 123,
            /^"[^"]*":\s*true|false,?$/,         // "key": true,
            /^"[^"]*":\s*null,?$/,               // "key": null,
            /^"[^"]*":\s*\[[^\]]*\],?$/,         // "key": [...],
            /^"[^"]*":\s*\{[^}]*\},?$/,          // "key": {...},
            /^\s*\{?\s*$/,                       // Just opening brace or whitespace
            /^\s*\}?,?\s*$/,                     // Just closing brace
            /^\s*\[?\s*$/,                       // Just opening bracket
            /^\s*\]?,?\s*$/,                     // Just closing bracket
            /^,?\s*$/,                           // Just comma or whitespace
            /^[^"]*':\s*[^,]*,.*':/,          // Mid-object fragments like "g_items': 1, 'hunt_upgrade_items': 0"
            /^[a-zA-Z_][a-zA-Z0-9_]*':\s*\d+,/,  // Property names starting without quotes
            /^[a-zA-Z_][a-zA-Z0-9_]*':\s*True|False,/, // Boolean properties without opening quotes
            /^[a-zA-Z_][a-zA-Z0-9_]*':\s*'[^']*',/, // String properties without opening quotes
            /.*':\s*\d+,.*':\s*\d+,/,            // Multiple numeric properties in sequence
            /.*':\s*True,.*':\s*False,/,         // Multiple boolean properties in sequence
            /.*':\s*'[^']*',.*':\s*'[^']*',/,    // Multiple string properties in sequence
            /^"[^"]*":\s*\[$/,                   // JSON key with opening bracket: "global": [
            /^[a-zA-Z_][a-zA-Z0-9_\s]*:\s*\[$/,  // Property key with opening bracket: global: [
            /^[a-zA-Z_][a-zA-Z0-9_\s]*:\s*\{$/,  // Property key with opening brace: config: {
            /^[a-zA-Z_]+\s+(Mode|Setting|Config|Option):\s*(True|False|\d+)$/i, // Config fragments: "ug Mode: False"
            /^[a-zA-Z_]+\s*Mode:\s*(True|False)$/i, // Mode fragments: "Debug Mode: False"
            /^[a-zA-Z_]+\s*Setting:\s*.*$/i,     // Setting fragments
            /^[a-zA-Z_]+\s*Config:\s*.*$/i       // Config fragments
        ];
        
        return jsonPatterns.some(pattern => pattern.test(trimmed));
    },
    
    // Helper method to detect other invalid log lines
    isInvalidLogLine: function(logString) {
        if (!logString || typeof logString !== 'string') return true;
        
        const trimmed = logString.trim();
        
        // Skip empty lines or lines with only whitespace
        if (trimmed.length === 0) return true;
        
        // Skip lines that are clearly not log entries
        if (trimmed.length < 10) return true; // Too short to be a meaningful log
        
        // Skip lines that look like HTTP headers or other metadata
        if (/^(HTTP\/|Content-|Connection:|Host:|User-Agent:)/i.test(trimmed)) return true;
        
        // Skip partial words or fragments that don't form complete sentences
        if (/^[a-zA-Z]{1,5}\s+(Mode|Setting|Config|Debug|Info|Error|Warning):/i.test(trimmed)) return true;
        
        // Skip single words that are clearly fragments
        if (/^[a-zA-Z]{1,8}$/i.test(trimmed)) return true;
        
        // Skip lines that start with partial words and contain colons (config fragments)
        if (/^[a-z]{1,8}\s*[A-Z]/i.test(trimmed) && trimmed.includes(':')) return true;
        
        return false;
    },
    
    // Load instance-specific state management information
    loadInstanceStateInfo: function(appType, instanceIndex) {
        const supportedApps = ['sonarr', 'radarr', 'lidarr', 'readarr', 'whisparr', 'eros'];
        if (!supportedApps.includes(appType)) return;
        
        // Try multiple methods to get the correct instance name
        let instanceName = null;
        
        // Method 1: Try the name input field
        const instanceNameElement = document.getElementById(`${appType}-name-${instanceIndex}`);
        if (instanceNameElement && instanceNameElement.value && instanceNameElement.value.trim()) {
            instanceName = instanceNameElement.value.trim();
        }
        
        // Method 2: Try to get from the instance header/title
        if (!instanceName) {
            const instanceHeader = document.querySelector(`#${appType}-instance-${instanceIndex} h3, #${appType}-instance-${instanceIndex} .instance-title`);
            if (instanceHeader && instanceHeader.textContent) {
                // Extract instance name from header text like "Instance 1: Default" or "Instance 2: EP Mode"
                const headerText = instanceHeader.textContent.trim();
                const match = headerText.match(/Instance \d+:\s*(.+)$/);
                if (match && match[1]) {
                    instanceName = match[1].trim();
                }
            }
        }
        
        // Method 3: Fallback to Default for first instance, descriptive name for others
        if (!instanceName) {
            instanceName = instanceIndex === 0 ? 'Default' : `Instance ${instanceIndex + 1}`;
        }
        
        const hoursInput = document.getElementById(`${appType}-state-management-hours-${instanceIndex}`);
        const customHours = parseInt(hoursInput?.value) || 168;
        
        console.log(`[huntarrUI] Loading state info for ${appType}/${instanceName} (index ${instanceIndex})`);
        
        // Load state information for this specific instance using per-instance API
        const apiUrl = `./api/stateful/summary?app_type=${appType}&instance_name=${encodeURIComponent(instanceName)}`;
        console.log(`[huntarrUI] Making API call: ${apiUrl}`);
        
        HuntarrUtils.fetchWithTimeout(apiUrl, {
            method: 'GET'
        })
        .then(response => {
            console.log(`[huntarrUI] API response status for ${appType}/${instanceName}:`, response.status);
            return response.json();
        })
        .then(summaryData => {
            console.log(`[huntarrUI] State data received for ${appType}/${instanceName}:`, summaryData);
            this.updateInstanceStateDisplay(appType, instanceIndex, summaryData, instanceName, customHours);
        })
        .catch(error => {
            console.error(`[huntarrUI] Error loading state info for ${appType}/${instanceName} (index ${instanceIndex}):`, error);
            // Fallback to default display
            this.updateInstanceStateDisplay(appType, instanceIndex, null, instanceName, customHours);
        });
    },
    
    // Update the instance state management display
    updateInstanceStateDisplay: function(appType, instanceIndex, summaryData, instanceName, customHours) {
        console.log(`[huntarrUI] updateInstanceStateDisplay called for ${appType}/${instanceName} (index ${instanceIndex}):`, summaryData);
        
        const resetTimeElement = document.getElementById(`${appType}-state-reset-time-${instanceIndex}`);
        const itemsCountElement = document.getElementById(`${appType}-state-items-count-${instanceIndex}`);
        
        console.log(`[huntarrUI] DOM elements found:`, {
            resetTimeElement: !!resetTimeElement,
            itemsCountElement: !!itemsCountElement,
            resetTimeId: `${appType}-state-reset-time-${instanceIndex}`,
            itemsCountId: `${appType}-state-items-count-${instanceIndex}`
        });
        
        // Update reset time from server data ONLY - no fallback calculations
        if (resetTimeElement) {
            if (summaryData && summaryData.success && summaryData.next_reset_time) {
                resetTimeElement.textContent = summaryData.next_reset_time;
                console.log(`[huntarrUI] Updated reset time for ${appType}/${instanceName}: ${summaryData.next_reset_time}`);
            } else {
                // Show error state - server should always provide this
                console.error(`[huntarrUI] No valid next_reset_time in server response for ${appType}/${instanceName}:`, summaryData);
                resetTimeElement.textContent = 'Error loading time';
            }
        } else {
            console.error(`[huntarrUI] Reset time element not found: ${appType}-state-reset-time-${instanceIndex}`);
        }
        
        // Update processed items count
        if (itemsCountElement) {
            const count = (summaryData && summaryData.success) ? (summaryData.processed_count || 0) : 0;
            itemsCountElement.textContent = count.toString();
            console.log(`[huntarrUI] Updated items count for ${appType}/${instanceName}: ${count}`);
        } else {
            console.error(`[huntarrUI] Items count element not found: ${appType}-state-items-count-${instanceIndex}`);
        }
    },

    showRequestarrSidebar: function() {
        // Hide main sidebar and settings sidebar
        const mainSidebar = document.getElementById('sidebar');
        const requestarrSidebar = document.getElementById('requestarr-sidebar');
        const settingsSidebar = document.getElementById('settings-sidebar');
        
        if (mainSidebar) mainSidebar.style.display = 'none';
        if (settingsSidebar) settingsSidebar.style.display = 'none';
        if (requestarrSidebar) requestarrSidebar.style.display = 'block';
        
        // Update active states in Requestarr sidebar
        this.updateRequestarrSidebarActive();
    },

    showRequestarrView: function(view) {
        // Hide all Requestarr views
        const homeView = document.getElementById('requestarr-home-view');
        const historyView = document.getElementById('requestarr-history-view');
        
        if (homeView) homeView.style.display = 'none';
        if (historyView) historyView.style.display = 'none';
        
        // Show selected view
        if (view === 'home' && homeView) {
            homeView.style.display = 'block';
        } else if (view === 'history' && historyView) {
            historyView.style.display = 'block';
        }
        
        // Update navigation states
        this.updateRequestarrNavigation(view);
    },

    showMainSidebar: function() {
        console.log('[huntarrUI] showMainSidebar called');
        
        // Show main sidebar
        const mainSidebar = document.getElementById('sidebar');
        const requestarrSidebar = document.getElementById('requestarr-sidebar');
        const settingsSidebar = document.getElementById('settings-sidebar');
        
        console.log('[huntarrUI] Sidebar elements found:', {
            main: !!mainSidebar,
            requestarr: !!requestarrSidebar,
            settings: !!settingsSidebar
        });
        
        if (mainSidebar) {
            mainSidebar.style.display = 'block';
            mainSidebar.style.setProperty('display', 'block', 'important');
        }
        if (requestarrSidebar) {
            requestarrSidebar.style.display = 'none';
            requestarrSidebar.style.setProperty('display', 'none', 'important');
        }
        if (settingsSidebar) {
            settingsSidebar.style.display = 'none';
            settingsSidebar.style.setProperty('display', 'none', 'important');
        }
        
        console.log('[huntarrUI] Sidebar styles applied');
        
        // Clear Settings sidebar preference when showing main sidebar
        localStorage.removeItem('huntarr-settings-sidebar');
    },

    showSettingsSidebar: function() {
        // Remove flash prevention style if it exists
        const flashPreventionStyle = document.getElementById('sidebar-flash-prevention');
        if (flashPreventionStyle) {
            flashPreventionStyle.remove();
        }
        
        // Hide main sidebar and show settings sidebar
        const mainSidebar = document.getElementById('sidebar');
        const requestarrSidebar = document.getElementById('requestarr-sidebar');
        const settingsSidebar = document.getElementById('settings-sidebar');
        
        if (mainSidebar) mainSidebar.style.display = 'none';
        if (requestarrSidebar) requestarrSidebar.style.display = 'none';
        if (settingsSidebar) settingsSidebar.style.display = 'block';
        
        // Update active states in Settings sidebar
        this.updateSettingsSidebarActive();
    },

    updateRequestarrSidebarActive: function() {
        // Remove active from all Requestarr nav items
        const requestarrNavItems = document.querySelectorAll('#requestarr-sidebar .nav-item');
        requestarrNavItems.forEach(item => item.classList.remove('active'));
        
        // Set appropriate active state based on current section
        if (this.currentSection === 'requestarr') {
            const homeNav = document.getElementById('requestarrHomeNav');
            if (homeNav) homeNav.classList.add('active');
        } else if (this.currentSection === 'requestarr-history') {
            const historyNav = document.getElementById('requestarrHistoryNav');
            if (historyNav) historyNav.classList.add('active');
        }
    },

    updateRequestarrNavigation: function(view) {
        // Remove active from all Requestarr nav items
        const requestarrNavItems = document.querySelectorAll('#requestarr-sidebar .nav-item');
        requestarrNavItems.forEach(item => item.classList.remove('active'));
        
        // Set active state based on view
        if (view === 'home') {
            const homeNav = document.getElementById('requestarrHomeNav');
            if (homeNav) homeNav.classList.add('active');
        } else if (view === 'history') {
            const historyNav = document.getElementById('requestarrHistoryNav');
            if (historyNav) historyNav.classList.add('active');
        }
    },

    setupRequestarrNavigation: function() {
        // Return button - goes back to main Huntarr
        const returnNav = document.getElementById('requestarrReturnNav');
        if (returnNav) {
            returnNav.addEventListener('click', (e) => {
                e.preventDefault();
                window.location.hash = '#home';
            });
        }
        
        // Home button - shows Requestarr home
        const homeNav = document.getElementById('requestarrHomeNav');
        if (homeNav) {
            homeNav.addEventListener('click', (e) => {
                e.preventDefault();
                window.location.hash = '#requestarr';
            });
        }
        
        // History button - shows Requestarr history
        const historyNav = document.getElementById('requestarrHistoryNav');
        if (historyNav) {
            historyNav.addEventListener('click', (e) => {
                e.preventDefault();
                window.location.hash = '#requestarr-history';
            });
        }
    },

    updateSettingsSidebarActive: function() {
        // Remove active from all Settings nav items
        const settingsNavItems = document.querySelectorAll('#settings-sidebar .nav-item');
        settingsNavItems.forEach(item => item.classList.remove('active'));
        
        // Set appropriate active state based on current section
        if (this.currentSection === 'settings') {
            const mainNav = document.getElementById('settingsMainNav');
            if (mainNav) mainNav.classList.add('active');
        } else if (this.currentSection === 'scheduling') {
            const schedulingNav = document.getElementById('settingsSchedulingNav');
            if (schedulingNav) schedulingNav.classList.add('active');
        } else if (this.currentSection === 'notifications') {
            const notificationsNav = document.getElementById('settingsNotificationsNav');
            if (notificationsNav) notificationsNav.classList.add('active');
        } else if (this.currentSection === 'user') {
            const userNav = document.getElementById('settingsUserNav');
            if (userNav) userNav.classList.add('active');
        }
    },

    setupSettingsNavigation: function() {
        // Return button - goes back to main Huntarr
        const returnNav = document.getElementById('settingsReturnNav');
        if (returnNav) {
            returnNav.addEventListener('click', (e) => {
                e.preventDefault();
                // Clear Settings sidebar preference when returning to main
                localStorage.removeItem('huntarr-settings-sidebar');
                window.location.hash = '#home';
            });
        }
        
        // Main button - shows Settings main page
        const mainNav = document.getElementById('settingsMainNav');
        if (mainNav) {
            mainNav.addEventListener('click', (e) => {
                e.preventDefault();
                window.location.hash = '#settings';
            });
        }
        
        // Scheduling button - shows Scheduling page
        const schedulingNav = document.getElementById('settingsSchedulingNav');
        if (schedulingNav) {
            schedulingNav.addEventListener('click', (e) => {
                e.preventDefault();
                window.location.hash = '#scheduling';
            });
        }
        
        // Notifications button - shows Notifications page
        const notificationsNav = document.getElementById('settingsNotificationsNav');
        if (notificationsNav) {
            notificationsNav.addEventListener('click', (e) => {
                e.preventDefault();
                window.location.hash = '#notifications';
            });
        }
        
        // User button - shows User page
        const userNav = document.getElementById('settingsUserNav');
        if (userNav) {
            userNav.addEventListener('click', (e) => {
                e.preventDefault();
                window.location.hash = '#user';
            });
        }
    },

    setupHuntarrNavigation: function() {
        // Return button - goes back to main Huntarr
        const returnNav = document.getElementById('huntarrReturnNav');
        if (returnNav) {
            returnNav.addEventListener('click', (e) => {
                e.preventDefault();
                window.location.hash = '#home';
            });
        }
        
        // Individual app buttons
        const appNavButtons = [
            { id: 'huntarrSonarrNav', hash: '#sonarr' },
            { id: 'huntarrRadarrNav', hash: '#radarr' },
            { id: 'huntarrLidarrNav', hash: '#lidarr' },
            { id: 'huntarrReadarrNav', hash: '#readarr' },
            { id: 'huntarrWhisparrNav', hash: '#whisparr' },
            { id: 'huntarrErosNav', hash: '#eros' }
        ];
        
        appNavButtons.forEach(button => {
            const navElement = document.getElementById(button.id);
            if (navElement) {
                navElement.addEventListener('click', (e) => {
                    e.preventDefault();
                    window.location.hash = button.hash;
                });
            }
        });
    },

    showHuntarrSidebar: function() {
        // Hide all other sidebars
        const mainSidebar = document.getElementById('sidebar');
        const requestarrSidebar = document.getElementById('requestarr-sidebar');
        const settingsSidebar = document.getElementById('settings-sidebar');
        const huntarrSidebar = document.getElementById('huntarr-sidebar');
        
        if (mainSidebar) mainSidebar.style.display = 'none';
        if (requestarrSidebar) requestarrSidebar.style.display = 'none';
        if (settingsSidebar) settingsSidebar.style.display = 'none';
        if (huntarrSidebar) huntarrSidebar.style.display = 'block';
        
        // Update navigation state
        this.updateHuntarrSidebarActive();
    },

    updateHuntarrSidebarActive: function() {
        // Remove active from all Huntarr nav items
        const huntarrNavItems = document.querySelectorAll('#huntarr-sidebar .nav-item');
        huntarrNavItems.forEach(item => item.classList.remove('active'));
        
        // Set appropriate active state based on current section
        const appNavMap = {
            'sonarr': 'huntarrSonarrNav',
            'radarr': 'huntarrRadarrNav',
            'lidarr': 'huntarrLidarrNav',
            'readarr': 'huntarrReadarrNav',
            'whisparr': 'huntarrWhisparrNav',
            'eros': 'huntarrErosNav'
        };
        
        const activeNavId = appNavMap[this.currentSection];
        if (activeNavId) {
            const activeNav = document.getElementById(activeNavId);
            if (activeNav) activeNav.classList.add('active');
        }
    },

    showMainSidebar: function() {
        // Hide all other sidebars
        const mainSidebar = document.getElementById('sidebar');
        const requestarrSidebar = document.getElementById('requestarr-sidebar');
        const settingsSidebar = document.getElementById('settings-sidebar');
        const huntarrSidebar = document.getElementById('huntarr-sidebar');
        
        if (mainSidebar) mainSidebar.style.display = 'block';
        if (requestarrSidebar) requestarrSidebar.style.display = 'none';
        if (settingsSidebar) settingsSidebar.style.display = 'none';
        if (huntarrSidebar) huntarrSidebar.style.display = 'none';
    },

    showRequestarrSidebar: function() {
        // Hide all other sidebars
        const mainSidebar = document.getElementById('sidebar');
        const requestarrSidebar = document.getElementById('requestarr-sidebar');
        const settingsSidebar = document.getElementById('settings-sidebar');
        const huntarrSidebar = document.getElementById('huntarr-sidebar');
        
        if (mainSidebar) mainSidebar.style.display = 'none';
        if (requestarrSidebar) requestarrSidebar.style.display = 'block';
        if (settingsSidebar) settingsSidebar.style.display = 'none';
        if (huntarrSidebar) huntarrSidebar.style.display = 'none';
        
        // Update navigation state
        this.updateRequestarrSidebarActive();
    },

    showSettingsSidebar: function() {
        // Hide all other sidebars
        const mainSidebar = document.getElementById('sidebar');
        const requestarrSidebar = document.getElementById('requestarr-sidebar');
        const settingsSidebar = document.getElementById('settings-sidebar');
        const huntarrSidebar = document.getElementById('huntarr-sidebar');
        
        if (mainSidebar) mainSidebar.style.display = 'none';
        if (requestarrSidebar) requestarrSidebar.style.display = 'none';
        if (settingsSidebar) settingsSidebar.style.display = 'block';
        if (huntarrSidebar) huntarrSidebar.style.display = 'none';
        
        // Update navigation state
        this.updateSettingsSidebarActive();
    },

    loadIndividualApp: function(app) {
        console.log(`[huntarrUI] Loading individual app: ${app}`);
        
        // Set current settings tab for auto-save functionality
        this.currentSettingsTab = app;
        console.log(`[huntarrUI] Set currentSettingsTab to: ${this.currentSettingsTab}`);
        
        // Get the container for this app
        const appContainer = document.getElementById(app + 'Container');
        if (!appContainer) {
            console.error(`[huntarrUI] Container not found for app: ${app}`);
            return;
        }
        
        // Show loading state
        appContainer.innerHTML = '<div class="loading-panel"><i class="fas fa-spinner fa-spin"></i> Loading ' + app + ' settings...</div>';
        
        // Fetch both app settings and Swaparr settings for proper dependency checking
        Promise.all([
            fetch(`./api/settings/${app}`).then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            }),
            fetch('./api/settings/swaparr').then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            })
        ])
            .then(([appSettings, swaparrSettings]) => {
                // Store Swaparr settings for the form generation to access
                if (!window.huntarrUI.originalSettings) {
                    window.huntarrUI.originalSettings = {};
                }
                window.huntarrUI.originalSettings.swaparr = swaparrSettings;
                console.log(`[huntarrUI] Received settings for ${app}:`, appSettings);
                
                // Clear loading message
                appContainer.innerHTML = '';
                
                // Generate the form using SettingsForms module
                if (typeof SettingsForms !== 'undefined') {
                    const formFunction = SettingsForms[`generate${app.charAt(0).toUpperCase()}${app.slice(1)}Form`];
                    if (typeof formFunction === 'function') {
                        // Create a form container with the app-type attribute and correct ID for auto-save
                        const formElement = document.createElement('form');
                        formElement.classList.add('settings-form');
                        formElement.setAttribute('data-app-type', app);
                        formElement.id = `${app}Settings`; // Add ID for getFormSettings to find
                        appContainer.appendChild(formElement);
                        
                        // Use .call() to set the 'this' context correctly
                        formFunction.call(SettingsForms, formElement, appSettings);
                        
                        // Update duration displays for this app
                        if (typeof SettingsForms.updateDurationDisplay === 'function') {
                            SettingsForms.updateDurationDisplay();
                        }
                        
                        console.log(`[huntarrUI] Successfully loaded ${app} form`);
                    } else {
                        console.error(`[huntarrUI] Form function not found for ${app}`);
                        appContainer.innerHTML = `<p>Error: Form function not available for ${app}</p>`;
                    }
                } else {
                    console.error('[huntarrUI] SettingsForms not available');
                    appContainer.innerHTML = '<p>Error: Settings forms not loaded</p>';
                }
            })
            .catch(error => {
                console.error(`[huntarrUI] Error loading ${app} settings:`, error);
                appContainer.innerHTML = `<p>Error loading ${app} settings: ${error.message}</p>`;
            });
    },

    initializeSettings: function() {
        // Check if settings are already initialized
        const generalSettings = document.getElementById('generalSettings');
        if (!generalSettings || generalSettings.innerHTML.trim() !== '') {
            return; // Already initialized
        }

        // Set current settings tab for auto-save functionality
        this.currentSettingsTab = 'general';
        console.log('[huntarrUI] Set currentSettingsTab to: general for auto-save');

        // Load settings from API and generate the form
        fetch('./api/settings')
            .then(response => response.json())
            .then(settings => {
                console.log('[huntarrUI] Loaded settings:', settings);
                console.log('[huntarrUI] General settings:', settings.general);
                
                // Generate the general settings form - pass only the general settings
                if (typeof SettingsForms !== 'undefined' && SettingsForms.generateGeneralForm) {
                    // Ensure the container has the correct ID for auto-save
                    generalSettings.id = 'generalSettings';
                    SettingsForms.generateGeneralForm(generalSettings, settings.general || {});
                } else {
                    console.error('[huntarrUI] SettingsForms not available');
                    generalSettings.innerHTML = '<p>Error: Settings forms not loaded</p>';
                }
            })
            .catch(error => {
                console.error('[huntarrUI] Error loading settings:', error);
                generalSettings.innerHTML = '<p>Error loading settings</p>';
            });
    },

    initializeNotifications: function() {
        console.log('[huntarrUI] initializeNotifications called');
        
        // Check if notifications are already initialized
        const notificationsContainer = document.getElementById('notificationsContainer');
        if (!notificationsContainer) {
            console.error('[huntarrUI] notificationsContainer element not found!');
            return;
        }
        
        console.log('[huntarrUI] notificationsContainer found:', notificationsContainer);
        console.log('[huntarrUI] Current container content:', notificationsContainer.innerHTML.trim());
        
        // Check if notifications are actually initialized (ignore HTML comments)
        const currentContent = notificationsContainer.innerHTML.trim();
        if (currentContent !== '' && !currentContent.includes('<!-- Notifications content will be loaded here -->')) {
            console.log('[huntarrUI] Notifications already initialized, skipping');
            return; // Already initialized
        }

        console.log('[huntarrUI] Loading notifications settings from API...');
        
        // Load settings from API and generate the notifications form
        fetch('./api/settings')
            .then(response => response.json())
            .then(settings => {
                console.log('[huntarrUI] Loaded settings for notifications:', settings);
                console.log('[huntarrUI] General settings:', settings.general);
                console.log('[huntarrUI] SettingsForms available:', typeof SettingsForms !== 'undefined');
                console.log('[huntarrUI] generateNotificationsForm available:', typeof SettingsForms !== 'undefined' && SettingsForms.generateNotificationsForm);
                
                // Generate the notifications form - pass the general settings which contain notification settings
                if (typeof SettingsForms !== 'undefined' && SettingsForms.generateNotificationsForm) {
                    console.log('[huntarrUI] Calling SettingsForms.generateNotificationsForm...');
                    SettingsForms.generateNotificationsForm(notificationsContainer, settings.general || {});
                    console.log('[huntarrUI] Notifications form generated successfully');
                } else {
                    console.error('[huntarrUI] SettingsForms.generateNotificationsForm not available');
                    notificationsContainer.innerHTML = '<p>Error: Notifications forms not loaded</p>';
                }
            })
            .catch(error => {
                console.error('[huntarrUI] Error loading notifications settings:', error);
                notificationsContainer.innerHTML = '<p>Error loading notifications settings</p>';
            });
    }
};

// Initialize when document is ready
document.addEventListener('DOMContentLoaded', function() {
    huntarrUI.init();
    
    // Initialize our enhanced UI features
    if (typeof StatsTooltips !== 'undefined') {
        StatsTooltips.init();
    }
    
    if (typeof CardHoverEffects !== 'undefined') {
        CardHoverEffects.init();
    }
    
    if (typeof CircularProgress !== 'undefined') {
        CircularProgress.init();
    }
    
    if (typeof BackgroundPattern !== 'undefined') {
        BackgroundPattern.init();
    }
    
    // Initialize per-instance reset button listeners
    if (typeof SettingsForms !== 'undefined' && typeof SettingsForms.setupInstanceResetListeners === 'function') {
        SettingsForms.setupInstanceResetListeners();
    }
});

// Expose huntarrUI to the global scope for access by app modules
window.huntarrUI = huntarrUI;
