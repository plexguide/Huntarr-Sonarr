/**
 * Huntarr Logs Module
 * Handles all logging functionality including streaming, filtering, search, and display
 */

console.log('[LOGS.JS] Script is loading and executing...');
console.log('[LOGS.JS] About to define window.LogsModule');

window.LogsModule = {
    // Current state
    eventSources: {},
    currentLogApp: 'all',
    userTimezone: null, // Cache for user's timezone setting
    initialized: false, // Track initialization to prevent duplicates
    
    // Pagination state
    currentPage: 1,
    totalPages: 1,
    pageSize: 20,
    totalLogs: 0,
    
    // Element references
    elements: {},
    
    // Initialize the logs module
    init: function() {
        if (this.initialized) {
            console.log('[LogsModule] Already initialized, skipping...');
            return;
        }
        
        console.log('[LogsModule] Initializing logs module...');
        this.cacheElements();
        this.loadUserTimezone();
        this.setupEventListeners();
        
        // Load initial logs for the default app without resetting pagination
        console.log('[LogsModule] Loading initial logs...');
        this.loadLogsFromAPI(this.currentLogApp);
        this.setupLogPolling(this.currentLogApp);
        
        // Listen for settings changes that might affect timezone
        window.addEventListener('settings-saved', (event) => {
            console.debug('[LogsModule] Settings saved event received, reloading timezone and logs');
            if (event.detail && event.detail.app === 'general') {
                // Reload the user timezone to reflect changes immediately
                this.loadUserTimezone();
                // Reload current logs to show timestamps in new timezone
                this.loadLogsFromAPI(this.currentLogApp, false);
            }
        });
        
        this.initialized = true;
        console.log('[LogsModule] Initialization complete');
    },
    
    // Load user's timezone setting from the backend
    loadUserTimezone: function() {
        // Set immediate fallback to prevent warnings during loading
        this.userTimezone = this.userTimezone || 'UTC';
        
        HuntarrUtils.fetchWithTimeout('./api/settings')
            .then(response => response.json())
            .then(settings => {
                this.userTimezone = settings.general?.timezone || 'UTC';
                console.log('[LogsModule] User timezone loaded:', this.userTimezone);
            })
            .catch(error => {
                console.warn('[LogsModule] Failed to load user timezone, using UTC:', error);
                this.userTimezone = 'UTC';
            });
    },
    
    // Validate timestamp format and values
    isValidTimestamp: function(timestamp) {
        if (!timestamp || typeof timestamp !== 'string') return false;
        
        // Check for pipe-separated format: YYYY-MM-DD HH:MM:SS
        const timestampRegex = /^\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2}$/;
        if (!timestampRegex.test(timestamp.trim())) return false;
        
        // Parse the components to validate ranges
        const parts = timestamp.trim().split(' ');
        if (parts.length !== 2) return false;
        
        const datePart = parts[0];
        const timePart = parts[1];
        
        // Validate date part: YYYY-MM-DD
        const dateMatch = datePart.match(/^(\d{4})-(\d{2})-(\d{2})$/);
        if (!dateMatch) return false;
        
        const year = parseInt(dateMatch[1]);
        const month = parseInt(dateMatch[2]);
        const day = parseInt(dateMatch[3]);
        
        // Basic range validation
        if (year < 2020 || year > 2030) return false;
        if (month < 1 || month > 12) return false;
        if (day < 1 || day > 31) return false;
        
        // Validate time part: HH:MM:SS
        const timeMatch = timePart.match(/^(\d{2}):(\d{2}):(\d{2})$/);
        if (!timeMatch) return false;
        
        const hour = parseInt(timeMatch[1]);
        const minute = parseInt(timeMatch[2]);
        const second = parseInt(timeMatch[3]);
        
        // Validate time ranges
        if (hour < 0 || hour > 23) return false;
        if (minute < 0 || minute > 59) return false;
        if (second < 0 || second > 59) return false;
        
        // Try to create a Date object to catch edge cases
        try {
            const testDate = new Date(`${datePart}T${timePart}Z`);
            return !isNaN(testDate.getTime());
        } catch (error) {
            return false;
        }
    },
    
    // Parse timestamp that's already converted to user's timezone by the backend
    convertToUserTimezone: function(timestamp) {
        if (!timestamp) {
            console.debug('[LogsModule] No timestamp provided for parsing');
            return { date: '', time: '' };
        }
        
        try {
            // The backend already converts timestamps to user's timezone
            // So we just need to parse the "YYYY-MM-DD HH:MM:SS" format
            const parts = timestamp.split(' ');
            if (parts.length >= 2) {
                return {
                    date: parts[0],
                    time: parts[1]
                };
            } else {
                // Fallback for unexpected format
                return { date: timestamp, time: '' };
            }
        } catch (error) {
            console.warn('[LogsModule] Error parsing timestamp:', error);
            // Fallback to original timestamp
            return { date: timestamp?.split(' ')[0] || '', time: timestamp?.split(' ')[1] || '' };
        }
    },
    
    // Cache DOM elements for better performance
    cacheElements: function() {
        // Logs elements
        this.elements.logsContainer = document.getElementById('logsContainer');
        this.elements.clearLogsButton = document.getElementById('clearLogsButton');
        this.elements.logConnectionStatus = document.getElementById('logConnectionStatus');
        
        // Log search elements
        this.elements.logSearchInput = document.getElementById('logSearchInput');
        this.elements.logSearchButton = document.getElementById('logSearchButton');
        this.elements.clearSearchButton = document.getElementById('clearSearchButton');
        this.elements.logSearchResults = document.getElementById('logSearchResults');
        
        // Log level filter element
        this.elements.logLevelSelect = document.getElementById('logLevelSelect');
        
        // Log dropdown elements
        this.elements.logOptions = document.querySelectorAll('.log-option');
        this.elements.currentLogApp = document.getElementById('current-log-app');
        this.elements.logDropdownBtn = document.querySelector('.log-dropdown-btn');
        this.elements.logDropdownContent = document.querySelector('.log-dropdown-content');
        
        // Pagination elements
        this.elements.logsPrevPage = document.getElementById('logsPrevPage');
        this.elements.logsNextPage = document.getElementById('logsNextPage');
        this.elements.logsCurrentPage = document.getElementById('logsCurrentPage');
        this.elements.logsTotalPages = document.getElementById('logsTotalPages');
        this.elements.logsPageSize = document.getElementById('logsPageSize');
    },
    
    // Set up event listeners for logging functionality
    setupEventListeners: function() {
        // Auto-scroll functionality removed
        
        // Clear logs button
        if (this.elements.clearLogsButton) {
            this.elements.clearLogsButton.addEventListener('click', () => this.clearLogs());
        }
        
        // Log search functionality
        if (this.elements.logSearchButton) {
            this.elements.logSearchButton.addEventListener('click', () => this.searchLogs());
        }
        
        if (this.elements.logSearchInput) {
            this.elements.logSearchInput.addEventListener('keypress', (e) => {
                if (e.key === 'Enter') {
                    this.searchLogs();
                }
            });
            
            // Clear search when input is emptied
            this.elements.logSearchInput.addEventListener('input', (e) => {
                if (e.target.value.trim() === '') {
                    this.clearLogSearch();
                }
            });
        }
        
        // Clear search button
        if (this.elements.clearSearchButton) {
            this.elements.clearSearchButton.addEventListener('click', () => this.clearLogSearch());
        }
        
        // Log options dropdown
        this.elements.logOptions.forEach(option => {
            option.addEventListener('click', (e) => this.handleLogOptionChange(e));
        });
        
        // Log dropdown toggle
        if (this.elements.logDropdownBtn) {
            this.elements.logDropdownBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                this.elements.logDropdownContent.classList.toggle('show');
            });
            
            // Close dropdown when clicking outside
            document.addEventListener('click', (e) => {
                if (!e.target.closest('.log-dropdown') && this.elements.logDropdownContent.classList.contains('show')) {
                    this.elements.logDropdownContent.classList.remove('show');
                }
            });
        }
        
        // LOG LEVEL FILTER: Listen for change on #logLevelSelect
        const logLevelSelect = document.getElementById('logLevelSelect');
        if (logLevelSelect) {
            logLevelSelect.addEventListener('change', (e) => {
                this.filterLogsByLevel(e.target.value);
            });
        }
        
        // LOGS: Listen for change on #logAppSelect
        const logAppSelect = document.getElementById('logAppSelect');
        if (logAppSelect) {
            logAppSelect.addEventListener('change', (e) => {
                const app = e.target.value;
                this.handleLogOptionChange(app);
            });
        }
        
        // Pagination event listeners
        if (this.elements.logsPrevPage) {
            this.elements.logsPrevPage.addEventListener('click', () => this.handlePagination('prev'));
        }
        
        if (this.elements.logsNextPage) {
            this.elements.logsNextPage.addEventListener('click', () => this.handlePagination('next'));
        }
        
        if (this.elements.logsPageSize) {
            this.elements.logsPageSize.addEventListener('change', () => this.handlePageSizeChange());
        }
    },
    
    // Handle log option dropdown changes
    handleLogOptionChange: function(app) {
        if (app && app.target && typeof app.target.value === 'string') {
            app = app.target.value;
        } else if (app && app.target && typeof app.target.getAttribute === 'function') {
            app = app.target.getAttribute('data-app');
        }
        if (!app || app === this.currentLogApp) {
            console.log(`[LogsModule] handleLogOptionChange - no change needed (${app} === ${this.currentLogApp})`);
            return;
        }
        
        console.log(`[LogsModule] handleLogOptionChange - switching from ${this.currentLogApp} to ${app}`);
        
        // Update the select value
        const logAppSelect = document.getElementById('logAppSelect');
        if (logAppSelect) logAppSelect.value = app;
        
        // Update the current log app text with proper capitalization
        let displayName = app.charAt(0).toUpperCase() + app.slice(1);
        if (app === 'whisparr') displayName = 'Whisparr V2';
        else if (app === 'eros') displayName = 'Whisparr V3';

        if (this.elements.currentLogApp) this.elements.currentLogApp.textContent = displayName;
        
        // Switch to the selected app logs
        this.currentLogApp = app;
        this.currentPage = 1; // Reset to first page when switching apps
        this.clearLogs();
        this.connectToLogs();
    },
    
    // Handle app changes from external sources (like huntarrUI tab switching)
    handleAppChange: function(app) {
        if (!app || app === this.currentLogApp) {
            console.log(`[LogsModule] handleAppChange - no change needed (${app} === ${this.currentLogApp})`);
            return;
        }
        
        console.log(`[LogsModule] handleAppChange - switching from ${this.currentLogApp} to ${app}`);
        
        // Update the select value
        const logAppSelect = document.getElementById('logAppSelect');
        if (logAppSelect) logAppSelect.value = app;
        
        // Update the current log app text with proper capitalization
        let displayName = app.charAt(0).toUpperCase() + app.slice(1);
        if (app === 'whisparr') displayName = 'Whisparr V2';
        else if (app === 'eros') displayName = 'Whisparr V3';

        if (this.elements.currentLogApp) this.elements.currentLogApp.textContent = displayName;
        
        // Switch to the selected app logs
        this.currentLogApp = app;
        this.currentPage = 1; // Reset to first page when switching apps
        this.clearLogs();
        this.connectToLogs();
    },
    
    // Connect to logs stream
    connectToLogs: function() {
        console.log(`[LogsModule] connectToLogs() called - currentLogApp: ${this.currentLogApp}, currentPage: ${this.currentPage}`);
        console.trace('[LogsModule] connectToLogs call stack');
        
        // Disconnect any existing event sources
        this.disconnectAllEventSources();
        
        // Connect to logs stream for the currentLogApp
        this.connectEventSource(this.currentLogApp);
        if (this.elements.logConnectionStatus) {
            this.elements.logConnectionStatus.textContent = 'Connecting...';
            this.elements.logConnectionStatus.className = '';
        }
    },
    
    // Connect to database-based logs API (replaces EventSource)
    connectEventSource: function(appType) {
        // Clear any existing polling interval
        if (this.logPollingInterval) {
            clearInterval(this.logPollingInterval);
        }
        
        // Set connection status
        if (this.elements.logConnectionStatus) {
            this.elements.logConnectionStatus.textContent = 'Connecting...';
            this.elements.logConnectionStatus.className = '';
        }
        
        // Load logs for the current page (don't always reset to page 1)
        console.log(`[LogsModule] connectEventSource - loading page ${this.currentPage} for app ${appType}`);
        this.loadLogsFromAPI(appType);
        
        // Set up polling with user's configured interval
        this.setupLogPolling(appType);
        
        // Status will be updated by loadLogsFromAPI on success/failure
    },
    
    // Set up log polling with user's configured interval
    setupLogPolling: function(appType) {
        // Fetch the log refresh interval from general settings
        HuntarrUtils.fetchWithTimeout('./api/settings/general', {
            method: 'GET'
        })
        .then(response => response.json())
        .then(settings => {
            // Use the configured interval, default to 30 seconds if not set
            const intervalSeconds = settings.log_refresh_interval_seconds || 30;
            const intervalMs = intervalSeconds * 1000;
            
            console.log(`[LogsModule] Setting up log polling with ${intervalSeconds} second interval`);
            
            // Set up polling for new logs using the configured interval
            this.logPollingInterval = setInterval(() => {
                // Only poll for new logs when on page 1 (latest logs)
                if (this.currentPage === 1) {
                    this.loadLogsFromAPI(appType, true);
                }
            }, intervalMs);
        })
        .catch(error => {
            console.error('[LogsModule] Error fetching log refresh interval, using default 30 seconds:', error);
            // Fallback to 30 seconds if settings fetch fails
            this.logPollingInterval = setInterval(() => {
                // Only poll for new logs when on page 1 (latest logs)
                if (this.currentPage === 1) {
                    this.loadLogsFromAPI(appType, true);
                }
            }, 30000);
        });
    },
    
    // Load logs from the database API
    loadLogsFromAPI: function(appType, isPolling = false) {
        // Use the correct API endpoint - the backend now supports 'all' as an app_type
        const apiUrl = `./api/logs/${appType}`;
        
        // For polling, always get latest logs (offset=0, small limit)
        // For pagination, use current page and page size
        let limit, offset;
        if (isPolling) {
            limit = 20;
            offset = 0;
        } else {
            limit = this.pageSize;
            offset = (this.currentPage - 1) * this.pageSize;
        }
        
        // Include level filter in API call if a specific level is selected
        const currentLogLevel = this.elements.logLevelSelect ? this.elements.logLevelSelect.value : 'all';
        let apiParams = `limit=${limit}&offset=${offset}`;
        if (currentLogLevel !== 'all') {
            apiParams += `&level=${currentLogLevel.toUpperCase()}`;
        }
        
        HuntarrUtils.fetchWithTimeout(`${apiUrl}?${apiParams}`)
            .then(response => {
                return response.json();
            })
            .then(data => {
                if (data.success && data.logs) {
                    this.processLogsFromAPI(data.logs, appType, isPolling);
                    
                    // Update pagination info (only on non-polling requests)
                    if (!isPolling && data.total !== undefined) {
                        this.totalLogs = data.total;
                        this.totalPages = Math.max(1, Math.ceil(this.totalLogs / this.pageSize));
                        console.log(`[LogsModule] Updated pagination: totalLogs=${this.totalLogs}, totalPages=${this.totalPages}, currentPage=${this.currentPage}`);
                        this.updatePaginationUI();
                    } else if (isPolling) {
                        console.log(`[LogsModule] Polling request - not updating pagination. Current: totalLogs=${this.totalLogs}, totalPages=${this.totalPages}, currentPage=${this.currentPage}`);
                    }
                    
                    // Update connection status on successful API call (only on initial load, not polling)
                    if (this.elements.logConnectionStatus && !isPolling) {
                        this.elements.logConnectionStatus.textContent = 'Connected';
                        this.elements.logConnectionStatus.className = 'status-connected';
                    }
                } else {
                    console.error('[LogsModule] Failed to load logs:', data.error || 'No logs in response');
                    if (this.elements.logConnectionStatus) {
                        this.elements.logConnectionStatus.textContent = data.error || 'Error loading logs';
                        this.elements.logConnectionStatus.className = 'status-error';
                    }
                }
            })
            .catch(error => {
                console.error('[LogsModule] Error loading logs:', error);
                if (this.elements.logConnectionStatus) {
                    this.elements.logConnectionStatus.textContent = 'Connection error';
                    this.elements.logConnectionStatus.className = 'status-error';
                }
            });
    },
    
    // Process logs received from API
    processLogsFromAPI: function(logs, appType, isPolling = false) {
        if (!this.elements.logsContainer) return;
        
        // If not polling, clear existing logs first
        if (!isPolling) {
            this.elements.logsContainer.innerHTML = '';
        }
        
        // Track existing log entries to avoid duplicates when polling
        // Use API timestamp + message for duplicate detection
        const existingLogEntries = new Set();
        if (isPolling) {
            const existingEntries = this.elements.logsContainer.querySelectorAll('.log-entry');
            existingEntries.forEach(entry => {
                const messageElement = entry.querySelector('.log-message');
                const timestampElement = entry.querySelector('.log-timestamp');
                if (messageElement && timestampElement) {
                    // Create a unique key using display timestamp + message
                    const timestampText = timestampElement.textContent.trim().replace(/\s+/g, ' ');
                    const messageText = messageElement.textContent.trim();
                    existingLogEntries.add(`${timestampText}|${messageText}`);
                }
            });
        }
        
        logs.forEach(logString => {
            try {
                // Process clean log format - same as before
                const logRegex = /^(?:\[[\w]+\]\s+)?([^|]+)\|([^|]+)\|([^|]+)\|(.*)$/;
                const match = logString.match(logRegex);

                if (!match) {
                    return; // Skip non-clean log entries entirely
                }
                
                // Extract log components from clean format
                const timestamp = match[1];
                const level = match[2]; 
                const logAppType = match[3].toLowerCase();
                const originalMessage = match[4];
                
                // Convert timestamp for display first
                const userTime = this.convertToUserTimezone(timestamp);
                const displayTimestamp = `${userTime.date} ${userTime.time}`;
                
                // Skip if we already have this log entry (when polling)
                // Use the display timestamp + message for duplicate detection
                if (isPolling && existingLogEntries.has(`${displayTimestamp}|${originalMessage.trim()}`)) {
                    return;
                }
                
                // Validate timestamp
                if (!this.isValidTimestamp(timestamp)) {
                    console.log('[LogsModule] Skipping log entry with invalid timestamp:', timestamp);
                    return;
                }
                
                // No need for client-side app filtering since the API handles this correctly now
                // The API returns the right logs based on the selected app type
                
                const logEntry = document.createElement('div');
                logEntry.className = 'log-entry';

                // Use the already converted timestamp
                const date = userTime.date;
                const time = userTime.time;
                
                // Clean the message - since we're now receiving clean logs from backend,
                // minimal processing should be needed
                let cleanMessage = originalMessage;
                
                // The backend clean logging system should already provide clean messages,
                // but we'll keep a simple cleanup as a fallback for any edge cases
                cleanMessage = cleanMessage.replace(/^\s*-\s*/, ''); // Remove any leading dashes
                cleanMessage = cleanMessage.trim(); // Remove extra whitespace
                
                // Create level badge
                const levelClass = level.toLowerCase();
                let levelBadge = '';
                
                switch(levelClass) {
                    case 'error':
                        levelBadge = `<span class="log-level-badge log-level-error">Error</span>`;
                        break;
                    case 'warning':
                    case 'warn':
                        levelBadge = `<span class="log-level-badge log-level-warning">Warning</span>`;
                        break;
                    case 'info':
                        levelBadge = `<span class="log-level-badge log-level-info">Information</span>`;
                        break;
                    case 'debug':
                        levelBadge = `<span class="log-level-badge log-level-debug">Debug</span>`;
                        break;
                    case 'fatal':
                    case 'critical':
                        levelBadge = `<span class="log-level-badge log-level-fatal">Fatal</span>`;
                        break;
                    default:
                        levelBadge = `<span class="log-level-badge log-level-info">Information</span>`;
                }
                
                // Determine app source for display
                let appSource = 'SYSTEM';
                if (logAppType && logAppType !== 'system') {
                    appSource = logAppType.toUpperCase();
                }
                
                logEntry.innerHTML = `
                    <div class="log-entry-row">
                        <span class="log-timestamp">
                            <span class="date">${date}</span>
                            <span class="time">${time}</span>
                        </span>
                        ${levelBadge}
                        <span class="log-source">${appSource}</span>
                        <span class="log-message">${cleanMessage}</span>
                    </div>
                `;
                logEntry.classList.add(`log-${levelClass}`);
            
                // Add to logs container
                this.insertLogEntryInOrder(logEntry);
                
                // Special event dispatching for Swaparr logs
                if (logAppType === 'swaparr' && this.currentLogApp === 'swaparr') {
                    // Dispatch a custom event for swaparr.js to process
                    const swaparrEvent = new CustomEvent('swaparrLogReceived', {
                        detail: {
                            logData: cleanMessage
                        }
                    });
                    document.dispatchEvent(swaparrEvent);
                }
                
                // Apply current log level filter
                const currentLogLevel = this.elements.logLevelSelect ? this.elements.logLevelSelect.value : 'all';
                if (currentLogLevel !== 'all') {
                    this.applyFilterToSingleEntry(logEntry, currentLogLevel);
                }
                
                // Auto-scroll functionality removed
            } catch (error) {
                console.error('[LogsModule] Error processing log message:', error, 'Data:', logString);
            }
        });
    },
    
    // Disconnect all event sources (now handles polling intervals)
    disconnectAllEventSources: function() {
        // Clear polling interval if it exists
        if (this.logPollingInterval) {
            clearInterval(this.logPollingInterval);
            this.logPollingInterval = null;
            console.log('[LogsModule] Cleared log polling interval');
        }
        
        // Clear any remaining event sources (legacy)
        Object.keys(this.eventSources).forEach(key => {
            const source = this.eventSources[key];
            if (source) {
                try {
                    if (source.readyState !== EventSource.CLOSED) {
                        source.close();
                        console.log(`[LogsModule] Closed event source for ${key}.`);
                    }
                } catch (e) {
                    console.error(`[LogsModule] Error closing event source for ${key}:`, e);
                }
            }
            delete this.eventSources[key];
        });
        
        if (this.elements.logConnectionStatus) {
            this.elements.logConnectionStatus.textContent = 'Disconnected';
            this.elements.logConnectionStatus.className = 'status-disconnected';
        }
    },
    
    // Clear all logs
    clearLogs: function() {
        if (this.elements.logsContainer) {
            this.elements.logsContainer.innerHTML = '';
        }
    },
    
    // Insert log entry in reverse chronological order (newest first)
    insertLogEntryInOrder: function(newLogEntry) {
        if (!this.elements.logsContainer || !newLogEntry) return;
        
        const newTimestamp = this.parseLogTimestamp(newLogEntry);
        
        // If no timestamp, add at the top (newest entries go to top)
        if (!newTimestamp) {
            this.elements.logsContainer.insertBefore(newLogEntry, this.elements.logsContainer.firstChild);
            return;
        }
        
        // If empty container, just add the entry
        if (this.elements.logsContainer.children.length === 0) {
            this.elements.logsContainer.appendChild(newLogEntry);
            return;
        }
        
        const existingEntries = Array.from(this.elements.logsContainer.children);
        let insertPosition = null;
        
        // Find the correct position - newest entries should be at the top
        // For same-timestamp logs, insert at the top to maintain "newest first" order
        for (let i = 0; i < existingEntries.length; i++) {
            const existingTimestamp = this.parseLogTimestamp(existingEntries[i]);
            
            if (!existingTimestamp) continue;
            
            // If new log is newer than existing log, OR if timestamps are equal (same second),
            // insert before it to maintain newest-first order
            if (newTimestamp >= existingTimestamp) {
                insertPosition = existingEntries[i];
                break;
            }
        }
        
        if (insertPosition) {
            // Insert before the older or same-timestamp entry (maintains newest-first order)
            this.elements.logsContainer.insertBefore(newLogEntry, insertPosition);
        } else {
            // If it's older than all existing entries, add at the end
            this.elements.logsContainer.appendChild(newLogEntry);
        }
    },
    
    // Parse timestamp from log entry DOM element
    parseLogTimestamp: function(logEntry) {
        if (!logEntry) return null;
        
        try {
            const dateSpan = logEntry.querySelector('.log-timestamp .date');
            const timeSpan = logEntry.querySelector('.log-timestamp .time');
            
            if (!dateSpan || !timeSpan) return null;
            
            const dateText = dateSpan.textContent.trim();
            const timeText = timeSpan.textContent.trim();
            
            if (!dateText || !timeText || dateText === '--' || timeText === '--:--:--') {
                return null;
            }
            
            const timestampString = `${dateText} ${timeText}`;
            const timestamp = new Date(timestampString);
            
            return isNaN(timestamp.getTime()) ? null : timestamp;
        } catch (error) {
            console.warn('[LogsModule] Error parsing log timestamp:', error);
            return null;
        }
    },
    
    // Search logs functionality
    searchLogs: function() {
        if (!this.elements.logsContainer || !this.elements.logSearchInput) return;
        
        const searchText = this.elements.logSearchInput.value.trim().toLowerCase();
        
        if (!searchText) {
            this.clearLogSearch();
            return;
        }
        
        if (this.elements.clearSearchButton) {
            this.elements.clearSearchButton.style.display = 'block';
        }
        
        const logEntries = Array.from(this.elements.logsContainer.querySelectorAll('.log-entry'));
        let matchCount = 0;
        
        const MAX_ENTRIES_TO_PROCESS = 300;
        const processedLogEntries = logEntries.slice(0, MAX_ENTRIES_TO_PROCESS);
        const remainingCount = Math.max(0, logEntries.length - MAX_ENTRIES_TO_PROCESS);
        
        processedLogEntries.forEach((entry, index) => {
            const entryText = entry.textContent.toLowerCase();
            
            if (entryText.includes(searchText)) {
                entry.style.display = '';
                matchCount++;
                this.simpleHighlightMatch(entry, searchText);
            } else {
                entry.style.display = 'none';
            }
        });
        
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
        
        if (this.elements.logSearchResults) {
            let resultsText = `Found ${matchCount} matching log entries`;
            this.elements.logSearchResults.textContent = resultsText;
            this.elements.logSearchResults.style.display = 'block';
        }
        
        // Auto-scroll functionality removed from search
    },
    
    // Simple highlighting method
    simpleHighlightMatch: function(logEntry, searchText) {
        if (searchText.length < 2) return;
        
        if (!logEntry.hasAttribute('data-original-html')) {
            logEntry.setAttribute('data-original-html', logEntry.innerHTML);
        }
        
        const html = logEntry.getAttribute('data-original-html');
        const escapedSearchText = searchText.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        
        const regex = new RegExp(`(${escapedSearchText})`, 'gi');
        const newHtml = html.replace(regex, '<span class="search-highlight">$1</span>');
        
        logEntry.innerHTML = newHtml;
    },
    
    // Clear log search
    clearLogSearch: function() {
        if (!this.elements.logsContainer) return;
        
        if (this.elements.logSearchInput) {
            this.elements.logSearchInput.value = '';
        }
        
        if (this.elements.clearSearchButton) {
            this.elements.clearSearchButton.style.display = 'none';
        }
        
        if (this.elements.logSearchResults) {
            this.elements.logSearchResults.style.display = 'none';
        }
        
        const allLogEntries = this.elements.logsContainer.querySelectorAll('.log-entry');
        
        Array.from(allLogEntries).forEach(entry => {
            entry.style.display = '';
            
            if (entry.hasAttribute('data-original-html')) {
                entry.innerHTML = entry.getAttribute('data-original-html');
            }
        });
        
        // Auto-scroll functionality removed from clear search
    },
    
    // Filter logs by level
    filterLogsByLevel: function(selectedLevel) {
        console.log(`[LogsModule] Filtering logs by level: ${selectedLevel}`);
        
        // Reset to first page when changing filter
        this.currentPage = 1;
        
        // Reload logs from API with new filter
        this.loadLogsFromAPI(this.currentLogApp, false);
    },
    
    // Apply filter to single entry
    applyFilterToSingleEntry: function(logEntry, selectedLevel) {
        const levelBadge = logEntry.querySelector('.log-level-badge, .log-level, .log-level-error, .log-level-warning, .log-level-info, .log-level-debug');
        
        logEntry.removeAttribute('data-hidden-by-filter');
        
        if (levelBadge) {
            let entryLevel = '';
            const badgeText = levelBadge.textContent.toLowerCase().trim();
            
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
                    entryLevel = 'error';
                    break;
                default:
                    if (levelBadge.classList.contains('log-level-error')) {
                        entryLevel = 'error';
                    } else if (levelBadge.classList.contains('log-level-warning')) {
                        entryLevel = 'warning';
                    } else if (levelBadge.classList.contains('log-level-info')) {
                        entryLevel = 'info';
                    } else if (levelBadge.classList.contains('log-level-debug')) {
                        entryLevel = 'debug';
                    } else {
                        entryLevel = null;
                    }
            }
            
            if (entryLevel && entryLevel === selectedLevel) {
                logEntry.style.display = '';
            } else {
                logEntry.style.display = 'none';
                logEntry.setAttribute('data-hidden-by-filter', 'true');
            }
        } else {
            logEntry.style.display = 'none';
            logEntry.setAttribute('data-hidden-by-filter', 'true');
        }
    },
    
    // Helper method to detect JSON fragments
    isJsonFragment: function(logString) {
        if (!logString || typeof logString !== 'string') return false;
        
        const trimmed = logString.trim();
        
        const jsonPatterns = [
            /^"[^"]*":\s*"[^"]*",?$/,
            /^"[^"]*":\s*\d+,?$/,
            /^"[^"]*":\s*true|false,?$/,
            /^"[^"]*":\s*null,?$/,
            /^"[^"]*":\s*\[[^\]]*\],?$/,
            /^"[^"]*":\s*\{[^}]*\},?$/,
            /^\s*\{?\s*$/,
            /^\s*\}?,?\s*$/,
            /^\s*\[?\s*$/,
            /^\s*\]?,?\s*$/,
            /^,?\s*$/,
            /^[^"]*':\s*[^,]*,.*':/,
            /^[a-zA-Z_][a-zA-Z0-9_]*':\s*\d+,/,
            /^[a-zA-Z_][a-zA-Z0-9_]*':\s*True|False,/,
            /^[a-zA-Z_][a-zA-Z0-9_]*':\s*'[^']*',/,
            /.*':\s*\d+,.*':\s*\d+,/,
            /.*':\s*True,.*':\s*False,/,
            /.*':\s*'[^']*',.*':\s*'[^']*',/,
            /^"[^"]*":\s*\[$/,
            /^[a-zA-Z_][a-zA-Z0-9_\s]*:\s*\[$/,
            /^[a-zA-Z_][a-zA-Z0-9_\s]*:\s*\{$/,
            /^[a-zA-Z_][a-zA-Z0-9_\s]*:\s*(True|False)$/i,
            /^[a-zA-Z_]+\s+(Mode|Setting|Config|Option):\s*(True|False|\d+)$/i,
            /^[a-zA-Z_]+\s*Mode:\s*(True|False)$/i,
            /^[a-zA-Z_]+\s*Setting:\s*.*$/i,
            /^[a-zA-Z_]+\s*Config:\s*.*$/i
        ];
        
        return jsonPatterns.some(pattern => pattern.test(trimmed));
    },
    
    // Helper method to detect invalid log lines
    isInvalidLogLine: function(logString) {
        if (!logString || typeof logString !== 'string') return true;
        
        const trimmed = logString.trim();
        
        if (trimmed.length === 0) return true;
        if (trimmed.length < 10) return true;
        if (/^(HTTP\/|Content-|Connection:|Host:|User-Agent:)/i.test(trimmed)) return true;
        if (/^[a-zA-Z]{1,5}\s+(Mode|Setting|Config|Debug|Info|Error|Warning):/i.test(trimmed)) return true;
        if (/^[a-zA-Z]{1,8}$/i.test(trimmed)) return true;
        if (/^[a-z]{1,8}\s*[A-Z]/i.test(trimmed) && trimmed.includes(':')) return true;
        
        return false;
    },
    
    // Handle pagination navigation
    handlePagination: function(direction) {
        console.log(`[LogsModule] =================== PAGINATION CALL START ===================`);
        console.log(`[LogsModule] handlePagination called - direction: ${direction}, currentPage BEFORE: ${this.currentPage}, totalPages: ${this.totalPages}`);
        console.trace('[LogsModule] handlePagination call stack');
        
        if (direction === 'prev' && this.currentPage > 1) {
            const oldPage = this.currentPage;
            this.currentPage--;
            console.log(`[LogsModule] PREV: Changed from page ${oldPage} to page ${this.currentPage}`);
            this.loadLogsFromAPI(this.currentLogApp, false);
        } else if (direction === 'next' && this.currentPage < this.totalPages) {
            const oldPage = this.currentPage;
            this.currentPage++;
            console.log(`[LogsModule] NEXT: Changed from page ${oldPage} to page ${this.currentPage}`);
            this.loadLogsFromAPI(this.currentLogApp, false);
        } else {
            console.log(`[LogsModule] Pagination blocked - direction: ${direction}, currentPage: ${this.currentPage}, totalPages: ${this.totalPages}`);
        }
        console.log(`[LogsModule] =================== PAGINATION CALL END ===================`);
    },
    
    // Handle page size change
    handlePageSizeChange: function() {
        const newPageSize = parseInt(this.elements.logsPageSize.value);
        if (newPageSize !== this.pageSize) {
            this.pageSize = newPageSize;
            this.currentPage = 1; // Reset to first page
            this.loadLogsFromAPI(this.currentLogApp, false);
        }
    },
    
    // Update pagination UI elements
    updatePaginationUI: function() {
        console.log(`[LogsModule] updatePaginationUI called - currentPage: ${this.currentPage}, totalPages: ${this.totalPages}`);
        console.log(`[LogsModule] DOM elements found:`, {
            logsCurrentPage: !!this.elements.logsCurrentPage,
            logsTotalPages: !!this.elements.logsTotalPages,
            logsPrevPage: !!this.elements.logsPrevPage,
            logsNextPage: !!this.elements.logsNextPage
        });
        
        if (this.elements.logsCurrentPage) {
            this.elements.logsCurrentPage.textContent = this.currentPage;
            console.log(`[LogsModule] Updated logsCurrentPage to: ${this.currentPage}`);
        } else {
            console.warn('[LogsModule] logsCurrentPage element not found!');
        }
        
        if (this.elements.logsTotalPages) {
            this.elements.logsTotalPages.textContent = this.totalPages;
            console.log(`[LogsModule] Updated logsTotalPages to: ${this.totalPages}`);
        } else {
            console.warn('[LogsModule] logsTotalPages element not found!');
        }
        
        if (this.elements.logsPrevPage) {
            this.elements.logsPrevPage.disabled = this.currentPage <= 1;
        }
        
        if (this.elements.logsNextPage) {
            this.elements.logsNextPage.disabled = this.currentPage >= this.totalPages;
        }
    },
    
    // Reset logs to default state
    resetToDefaults: function() {
        this.currentLogApp = 'all';
        this.currentPage = 1; // Reset pagination
        
        const logAppSelect = document.getElementById('logAppSelect');
        if (logAppSelect && logAppSelect.value !== 'all') {
            logAppSelect.value = 'all';
        }
        
        const logLevelSelect = document.getElementById('logLevelSelect');
        if (logLevelSelect && logLevelSelect.value !== 'info') {
            logLevelSelect.value = 'info';
            this.filterLogsByLevel('info');
        }
        
        const logSearchInput = document.getElementById('logSearchInput');
        if (logSearchInput && logSearchInput.value) {
            logSearchInput.value = '';
            this.clearLogSearch();
        }
        
        console.log('[LogsModule] Reset logs to defaults: All apps, INFO level, cleared search');
    }
};

console.log('[LOGS.JS] window.LogsModule defined successfully:', typeof window.LogsModule);
console.log('[LOGS.JS] LogsModule methods available:', Object.keys(window.LogsModule));

// Auto-initialize when DOM is ready
document.addEventListener('DOMContentLoaded', function() {
    if (window.LogsModule && typeof window.LogsModule.init === 'function') {
        window.LogsModule.init();
    }
});

// Also initialize immediately if DOM is already ready
if (document.readyState === 'loading') {
    // DOM is still loading, wait for DOMContentLoaded
} else {
    // DOM is already ready, initialize now
    if (window.LogsModule && typeof window.LogsModule.init === 'function') {
        window.LogsModule.init();
    }
} 