/**
 * Requestarr functionality - Media search and request system
 */

class RequestarrModule {
    constructor() {
        this.searchTimeout = null;
        this.instances = { sonarr: [], radarr: [] };
        this.selectedInstance = null;
        this.itemData = {};
        this.init();
    }

    init() {
        this.loadInstances();
        this.setupEventListeners();
    }

    setupEventListeners() {
        // Instance selection
        const instanceSelect = document.getElementById('requestarr-instance-select');
        if (instanceSelect) {
            instanceSelect.addEventListener('change', (e) => this.handleInstanceChange(e));
        }

        // Search input with debouncing
        const searchInput = document.getElementById('requestarr-search');
        if (searchInput) {
            searchInput.disabled = true;
            searchInput.placeholder = 'Select an instance first...';
            
            searchInput.addEventListener('input', (e) => {
                if (!this.selectedInstance) {
                    this.showNotification('Please select an instance first', 'warning');
                    return;
                }
                
                clearTimeout(this.searchTimeout);
                const query = e.target.value.trim();
                
                if (query.length >= 2) {
                    this.searchTimeout = setTimeout(() => {
                        this.searchMedia(query);
                    }, 500); // 500ms debounce
                } else {
                    this.clearResults();
                }
            });
        }
    }

    handleInstanceChange(event) {
        const selectedValue = event.target.value;
        if (selectedValue) {
            const [appType, instanceName] = selectedValue.split('|');
            this.selectedInstance = { appType, instanceName };
            
            // Clear previous results and enable search
            this.clearResults();
            const searchInput = document.getElementById('requestarr-search');
            if (searchInput) {
                searchInput.disabled = false;
                searchInput.placeholder = `Search for ${appType === 'radarr' ? 'movies' : 'TV shows'}...`;
                searchInput.value = '';
            }
        } else {
            this.selectedInstance = null;
            const searchInput = document.getElementById('requestarr-search');
            if (searchInput) {
                searchInput.disabled = true;
                searchInput.placeholder = 'Select an instance first...';
                searchInput.value = '';
            }
            this.clearResults();
        }
    }

    async loadInstances() {
        try {
            const response = await fetch('./api/requestarr/instances');
            this.instances = await response.json();
            this.updateInstanceSelect();
        } catch (error) {
            console.error('Error loading instances:', error);
            this.showNotification('Error loading instances', 'error');
        }
    }

    updateInstanceSelect() {
        const instanceSelect = document.getElementById('requestarr-instance-select');
        if (!instanceSelect) return;
        
        instanceSelect.innerHTML = '<option value="">Select an instance to search...</option>';
        
        // Add Sonarr instances
        this.instances.sonarr.forEach(instance => {
            const option = document.createElement('option');
            option.value = `sonarr|${instance.name}`;
            option.textContent = `Sonarr - ${instance.name}`;
            instanceSelect.appendChild(option);
        });
        
        // Add Radarr instances
        this.instances.radarr.forEach(instance => {
            const option = document.createElement('option');
            option.value = `radarr|${instance.name}`;
            option.textContent = `Radarr - ${instance.name}`;
            instanceSelect.appendChild(option);
        });
    }

    async searchMedia(query) {
        if (!this.selectedInstance) {
            this.showNotification('Please select an instance first', 'warning');
            return;
        }

        const resultsContainer = document.getElementById('requestarr-results');
        if (!resultsContainer) return;

        // Show loading
        resultsContainer.innerHTML = '<div class="loading">🔍 Searching...</div>';

        try {
            const params = new URLSearchParams({
                q: query,
                app_type: this.selectedInstance.appType,
                instance_name: this.selectedInstance.instanceName
            });
            
            // Use streaming endpoint for progressive loading
            const response = await fetch(`./api/requestarr/search/stream?${params}`);
            
            if (!response.ok) {
                throw new Error('Search failed');
            }
            
            const reader = response.body.getReader();
            const decoder = new TextDecoder();
            let buffer = '';
            let hasResults = false;
            
            // Clear loading message once we start getting results
            const clearLoadingOnce = () => {
                if (!hasResults) {
                    resultsContainer.innerHTML = '';
                    hasResults = true;
                }
            };
            
            while (true) {
                const { done, value } = await reader.read();
                
                if (done) break;
                
                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split('\n');
                buffer = lines.pop(); // Keep incomplete line in buffer
                
                for (const line of lines) {
                    if (line.startsWith('data: ')) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            
                            if (data.error) {
                                throw new Error(data.error);
                            }
                            
                            clearLoadingOnce();
                            
                            if (data._update) {
                                // This is an availability update for an existing result
                                this.updateResultAvailability(data);
                            } else {
                                // This is a new result
                                this.addResult(data);
                            }
                            
                        } catch (parseError) {
                            console.error('Error parsing streaming data:', parseError);
                        }
                    }
                }
            }
            
            // If no results were found
            if (!hasResults) {
                resultsContainer.innerHTML = '<div class="no-results">No results found.</div>';
            }
            
        } catch (error) {
            console.error('Error searching media:', error);
            resultsContainer.innerHTML = '<div class="error">Search failed. Please try again.</div>';
        }
    }

    displayResults(results) {
        const resultsContainer = document.getElementById('requestarr-results');
        if (!resultsContainer) return;

        if (results.length === 0) {
            resultsContainer.innerHTML = '<div class="no-results">No results found.</div>';
            return;
        }

        const resultsHTML = results.map(item => this.createResultCard(item)).join('');
        resultsContainer.innerHTML = resultsHTML;

        // Add event listeners to request buttons
        this.setupRequestButtons();
    }

    addResult(item) {
        const resultsContainer = document.getElementById('requestarr-results');
        if (!resultsContainer) return;

        // Create and append the new result card
        const cardHTML = this.createResultCard(item);
        const cardElement = document.createElement('div');
        cardElement.innerHTML = cardHTML;
        const actualCard = cardElement.firstElementChild;
        
        resultsContainer.appendChild(actualCard);

        // Add event listeners to the new request button
        const requestBtn = actualCard.querySelector('.request-btn:not([disabled])');
        if (requestBtn) {
            requestBtn.addEventListener('click', (e) => this.handleRequest(e.target));
        }
    }

    updateResultAvailability(updatedItem) {
        const cardId = `result-card-${updatedItem.tmdb_id}-${updatedItem.media_type}`;
        const card = document.querySelector(`[data-card-id="${cardId}"]`);
        
        if (!card) return;

        // Update stored item data
        this.itemData[cardId] = updatedItem;

        // Update availability status display
        const statusElement = card.querySelector('.availability-status');
        const requestButton = card.querySelector('.request-btn');
        
        if (statusElement && requestButton) {
            const statusInfo = this.getStatusInfo(updatedItem.availability);
            
            // Update status display
            statusElement.className = `availability-status ${statusInfo.className}`;
            statusElement.innerHTML = `<span class="status-icon">${statusInfo.icon}</span><span class="status-text">${statusInfo.message}</span>`;
            
            // Update button
            requestButton.textContent = statusInfo.buttonText;
            requestButton.className = `request-btn ${statusInfo.buttonClass}`;
            requestButton.disabled = statusInfo.disabled;
            
            // Add event listener if button is now enabled
            if (!statusInfo.disabled) {
                requestButton.addEventListener('click', (e) => this.handleRequest(e.target));
            }
        }
    }

    createResultCard(item) {
        const year = item.year ? `(${item.year})` : '';
        // Use a simple data URL placeholder instead of missing file
        const noPosterPlaceholder = 'data:image/svg+xml;base64,PHN2ZyB3aWR0aD0iMzAwIiBoZWlnaHQ9IjQ1MCIgdmlld0JveD0iMCAwIDMwMCA0NTAiIGZpbGw9Im5vbmUiIHhtbG5zPSJodHRwOi8vd3d3LnczLm9yZy8yMDAwL3N2ZyI+CjxyZWN0IHdpZHRoPSIzMDAiIGhlaWdodD0iNDUwIiBmaWxsPSIjMzMzIi8+Cjx0ZXh0IHg9IjE1MCIgeT0iMjI1IiBmb250LWZhbWlseT0iQXJpYWwiIGZvbnQtc2l6ZT0iMTgiIGZpbGw9IiM5OTkiIHRleHQtYW5jaG9yPSJtaWRkbGUiPk5vIFBvc3RlcjwvdGV4dD4KPC9zdmc+';
        const poster = item.poster_path || noPosterPlaceholder;
        const mediaTypeIcon = item.media_type === 'movie' ? '🎬' : '📺';
        const rating = item.vote_average ? `⭐ ${item.vote_average.toFixed(1)}` : '';
        
        // Generate availability status
        const availability = item.availability || {};
        const statusInfo = this.getStatusInfo(availability);
        
        // Generate unique ID for this card to store data safely
        const cardId = `result-card-${item.tmdb_id}-${item.media_type}`;
        
        // Store item data separately to avoid JSON parsing issues
        this.itemData = this.itemData || {};
        this.itemData[cardId] = item;
        
        return `
            <div class="result-card" data-card-id="${cardId}" data-tmdb-id="${item.tmdb_id}" data-media-type="${item.media_type}">
                <div class="result-poster">
                    <img src="${poster}" alt="${item.title}" onerror="this.src='${noPosterPlaceholder}'">
                    <div class="media-type-badge">${mediaTypeIcon}</div>
                </div>
                <div class="result-info">
                    <h3 class="result-title">${item.title} ${year}</h3>
                    <p class="result-overview">${item.overview.substring(0, 150)}${item.overview.length > 150 ? '...' : ''}</p>
                    <div class="result-meta">
                        <span class="rating">${rating}</span>
                        <span class="media-type">${item.media_type === 'movie' ? 'Movie' : 'TV Show'}</span>
                    </div>
                    <div class="availability-status ${statusInfo.className}">
                        <span class="status-icon">${statusInfo.icon}</span>
                        <span class="status-text">${statusInfo.message}</span>
                    </div>
                    <div class="request-section">
                        <button class="request-btn ${statusInfo.buttonClass}" 
                                data-card-id="${cardId}"
                                ${statusInfo.disabled ? 'disabled' : ''}>
                            ${statusInfo.buttonText}
                        </button>
                    </div>
                </div>
            </div>
        `;
    }

    getStatusInfo(availability) {
        switch (availability.status) {
            case 'available':
                return {
                    icon: '✅',
                    message: availability.message || 'Already in library',
                    className: 'status-available',
                    buttonText: 'In Library',
                    buttonClass: 'btn-disabled',
                    disabled: true
                };
            case 'available_to_request_granular':
                return {
                    icon: '📺',
                    message: availability.message || 'Request episodes or seasons',
                    className: 'status-granular',
                    buttonText: 'Request',
                    buttonClass: 'btn-primary',
                    disabled: false
                };
            case 'available_to_request_missing':
                return {
                    icon: '📺',
                    message: availability.message || 'Request missing episodes',
                    className: 'status-missing-episodes',
                    buttonText: 'Request Missing',
                    buttonClass: 'btn-warning',
                    disabled: false
                };
            case 'partially_requested':
                return {
                    icon: '📺',
                    message: availability.message || 'Some episodes requested - click to request more',
                    className: 'status-partial-request',
                    buttonText: 'Request More',
                    buttonClass: 'btn-warning',
                    disabled: false
                };
            case 'requested':
                return {
                    icon: '⏳',
                    message: 'Previously requested',
                    className: 'status-requested',
                    buttonText: 'Already Requested',
                    buttonClass: 'btn-disabled',
                    disabled: true
                };
            case 'available_to_request':
                return {
                    icon: '📥',
                    message: availability.message || 'Available to request',
                    className: 'status-requestable',
                    buttonText: 'Request',
                    buttonClass: 'btn-primary',
                    disabled: false
                };
            case 'error':
                return {
                    icon: '❌',
                    message: 'Error checking availability',
                    className: 'status-error',
                    buttonText: 'Error',
                    buttonClass: 'btn-disabled',
                    disabled: true
                };
            default:
                return {
                    icon: '❓',
                    message: 'Unknown status',
                    className: 'status-unknown',
                    buttonText: 'Unknown',
                    buttonClass: 'btn-disabled',
                    disabled: true
                };
        }
    }

    setupRequestButtons() {
        document.querySelectorAll('.request-btn:not([disabled])').forEach(button => {
            button.addEventListener('click', (e) => this.handleRequest(e.target));
        });
    }

    async handleRequest(button) {
        if (button.disabled) return;
        
        try {
            const cardId = button.dataset.cardId;
            if (!cardId) {
                throw new Error('Invalid card ID');
            }
            
            const item = this.itemData[cardId];
            if (!item) {
                throw new Error('Item data not found');
            }
            
            // Check if this is a TV show that supports granular selection
            if (item.media_type === 'tv' && 
                this.selectedInstance.appType === 'sonarr' && 
                item.availability && 
                item.availability.supports_granular) {
                
                // Show granular selection modal
                await this.showGranularSelectionModal(item);
                return;
            }
            
            // For movies or simple requests, proceed with normal request
            await this.performSimpleRequest(button, item);
            
        } catch (error) {
            console.error('Error handling request:', error);
            this.showNotification('Request failed', 'error');
            button.disabled = false;
            button.textContent = 'Request';
        }
    }

    async performSimpleRequest(button, item) {
        console.log('Requesting item:', item);
        console.log('Selected instance:', this.selectedInstance);
        
        button.disabled = true;
        button.textContent = 'Requesting...';
        
        const requestData = {
            tmdb_id: item.tmdb_id,
            media_type: item.media_type,
            title: item.title,
            year: item.year,
            overview: item.overview,
            poster_path: item.poster_path,
            backdrop_path: item.backdrop_path,
            app_type: this.selectedInstance.appType,
            instance_name: this.selectedInstance.instanceName
        };
        
        console.log('Request data:', requestData);
        
        const response = await fetch('./api/requestarr/request', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(requestData)
        });
        
        const result = await response.json();
        console.log('Request result:', result);
        
        if (result.success) {
            this.showNotification(result.message, 'success');
            button.textContent = 'Requested';
            button.className = 'request-btn btn-disabled';
            
            // Update availability status
            const statusElement = button.closest('.result-card').querySelector('.availability-status');
            if (statusElement) {
                statusElement.className = 'availability-status status-requested';
                statusElement.innerHTML = '<span class="status-icon">⏳</span><span class="status-text">Requested</span>';
            }
            
        } else {
            this.showNotification(result.message || 'Request failed', 'error');
            button.disabled = false;
            button.textContent = 'Request';
        }
    }

    async showGranularSelectionModal(item) {
        try {
            // Get detailed series information
            const params = new URLSearchParams({
                app_type: this.selectedInstance.appType,
                instance_name: this.selectedInstance.instanceName
            });
            
            const response = await fetch(`./api/requestarr/series/${item.tmdb_id}/details?${params}`);
            const seriesDetails = await response.json();
            
            if (!seriesDetails.success) {
                this.showNotification(seriesDetails.message || 'Failed to get series details', 'error');
                return;
            }
            
            // Create and show the modal
            this.createGranularSelectionModal(item, seriesDetails);
            
        } catch (error) {
            console.error('Error getting series details:', error);
            this.showNotification('Failed to load series details', 'error');
        }
    }

    clearResults() {
        const resultsContainer = document.getElementById('requestarr-results');
        if (resultsContainer) {
            resultsContainer.innerHTML = '';
        }
        // Clear stored item data
        this.itemData = {};
    }

    calculateEpisodeSummary(seasons) {
        let totalEpisodes = 0;
        let downloadedEpisodes = 0;
        
        seasons.forEach(season => {
            totalEpisodes += season.total_episodes;
            downloadedEpisodes += season.downloaded_episodes;
        });
        
        return {
            totalEpisodes,
            downloadedEpisodes,
            missingEpisodes: totalEpisodes - downloadedEpisodes
        };
    }

    createGranularSelectionModal(item, seriesDetails) {
        // Remove existing modal if present
        const existingModal = document.getElementById('granular-selection-modal');
        if (existingModal) {
            existingModal.remove();
        }
        
        const isMobile = window.innerWidth <= 768;
        
        // Calculate total missing episodes
        const episodeSummary = this.calculateEpisodeSummary(seriesDetails.seasons);
        
        // Create modal HTML
        const modalHTML = `
            <div id="granular-selection-modal" class="granular-modal-overlay">
                <div class="granular-modal">
                    <div class="granular-modal-header">
                        <h3>${item.title} ${item.year ? `(${item.year})` : ''}</h3>
                        <button class="granular-modal-close">&times;</button>
                    </div>
                    <div class="granular-modal-content">
                        <div class="series-summary">
                            <div class="summary-stats">
                                <span class="stat-item">
                                    <span class="stat-number">${episodeSummary.totalEpisodes}</span>
                                    <span class="stat-label">Total Episodes</span>
                                </span>
                                <span class="stat-item">
                                    <span class="stat-number">${episodeSummary.downloadedEpisodes}</span>
                                    <span class="stat-label">Downloaded</span>
                                </span>
                                <span class="stat-item missing">
                                    <span class="stat-number">${episodeSummary.missingEpisodes}</span>
                                    <span class="stat-label">Missing</span>
                                </span>
                            </div>
                        </div>
                        <div class="request-options">
                            <button class="request-option-btn" data-action="entire-series">
                                <span class="option-icon">📺</span>
                                <span class="option-text">Request Entire Series${episodeSummary.missingEpisodes > 0 ? ` (${episodeSummary.missingEpisodes} episodes)` : ''}</span>
                            </button>
                        </div>
                        <div class="seasons-container">
                            <h4>Select Seasons & Episodes</h4>
                            <div class="seasons-list">
                                ${this.createSeasonsHTML(seriesDetails.seasons, isMobile, item.tmdb_id)}
                            </div>
                        </div>
                        <div class="granular-modal-actions">
                            <button class="granular-cancel-btn">Cancel</button>
                            <button class="granular-request-btn" disabled>Request Selected</button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Add modal to DOM
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        
        // Setup modal event listeners
        this.setupGranularModalEvents(item, seriesDetails);
        
        // Show modal with animation
        requestAnimationFrame(() => {
            const modal = document.getElementById('granular-selection-modal');
            modal.classList.add('show');
        });
    }
    
    createSeasonsHTML(seasons, isMobile, tmdbId) {
        const requestedItems = this.getRequestedItems(tmdbId);
        
        return seasons.map(season => {
            const isComplete = season.downloaded_episodes >= season.total_episodes && season.total_episodes > 0;
            const hasEpisodes = season.episodes && season.episodes.length > 0;
            const isRequested = requestedItems.seasons.includes(season.season_number);
            const isDisabled = isComplete || isRequested;
            
            let statusBadge = '';
            if (isComplete) {
                statusBadge = '<span class="complete-badge">Complete</span>';
            } else if (isRequested) {
                statusBadge = '<span class="requested-badge">Requested</span>';
            }
            
            return `
                <div class="season-item ${isComplete ? 'season-complete' : ''} ${isRequested ? 'season-requested' : ''}" data-season="${season.season_number}">
                    <div class="season-header">
                        <div class="season-checkbox-container">
                            <input type="checkbox" 
                                   id="season-${season.season_number}" 
                                   class="season-checkbox"
                                   ${isDisabled ? 'disabled' : ''}
                                   data-season="${season.season_number}">
                            <label for="season-${season.season_number}" class="season-label">
                                <span class="season-title">Season ${season.season_number}</span>
                                <span class="season-stats">${season.downloaded_episodes}/${season.total_episodes} episodes</span>
                                ${statusBadge}
                            </label>
                        </div>
                        ${hasEpisodes && !isDisabled ? `
                            <button class="season-expand-btn" data-season="${season.season_number}">
                                <span class="expand-icon">▼</span>
                            </button>
                        ` : ''}
                    </div>
                    ${hasEpisodes && !isDisabled ? `
                        <div class="episodes-container" data-season="${season.season_number}" style="display: none;">
                            ${this.createEpisodesHTML(season.episodes, season.season_number, isMobile, requestedItems)}
                        </div>
                    ` : ''}
                </div>
            `;
        }).join('');
    }
    
    createEpisodesHTML(episodes, seasonNumber, isMobile, requestedItems) {
        return episodes.map(episode => {
            const isDownloaded = episode.has_file;
            const isRequested = requestedItems.episodes.some(req => 
                req.season === seasonNumber && req.episode === episode.episode_number
            );
            const isDisabled = isDownloaded || isRequested;
            const airDate = episode.air_date ? new Date(episode.air_date).toLocaleDateString() : '';
            
            let statusBadge = '';
            if (isDownloaded) {
                statusBadge = '<span class="downloaded-badge">Downloaded</span>';
            } else if (isRequested) {
                statusBadge = '<span class="requested-badge">Requested</span>';
            }
            
            return `
                <div class="episode-item ${isDownloaded ? 'episode-downloaded' : ''} ${isRequested ? 'episode-requested' : ''}" data-episode="${episode.episode_number}">
                    <div class="episode-checkbox-container">
                        <input type="checkbox" 
                               id="episode-${seasonNumber}-${episode.episode_number}" 
                               class="episode-checkbox"
                               ${isDisabled ? 'disabled' : ''}
                               data-season="${seasonNumber}"
                               data-episode="${episode.episode_number}">
                        <label for="episode-${seasonNumber}-${episode.episode_number}" class="episode-label">
                            <span class="episode-number">S${seasonNumber.toString().padStart(2, '0')}E${episode.episode_number.toString().padStart(2, '0')}</span>
                            ${!isMobile && episode.title ? `<span class="episode-title">${episode.title}</span>` : ''}
                            ${!isMobile && airDate ? `<span class="episode-date">${airDate}</span>` : ''}
                            ${statusBadge}
                        </label>
                    </div>
                </div>
            `;
        }).join('');
    }
    
    setupGranularModalEvents(item, seriesDetails) {
        const modal = document.getElementById('granular-selection-modal');
        
        // Close modal events
        const closeBtn = modal.querySelector('.granular-modal-close');
        const cancelBtn = modal.querySelector('.granular-cancel-btn');
        const overlay = modal;
        
        const closeModal = () => {
            modal.classList.remove('show');
            setTimeout(() => modal.remove(), 300);
        };
        
        closeBtn.addEventListener('click', closeModal);
        cancelBtn.addEventListener('click', closeModal);
        overlay.addEventListener('click', (e) => {
            if (e.target === overlay) closeModal();
        });
        
        // Request entire series
        const entireSeriesBtn = modal.querySelector('[data-action="entire-series"]');
        entireSeriesBtn.addEventListener('click', async () => {
            closeModal();
            const cardId = `result-card-${item.tmdb_id}-${item.media_type}`;
            const button = document.querySelector(`[data-card-id="${cardId}"] .request-btn`);
            if (button) {
                await this.performSimpleRequest(button, item);
            }
        });
        
        // Season expand/collapse
        modal.querySelectorAll('.season-expand-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const seasonNum = e.target.closest('.season-expand-btn').dataset.season;
                const episodesContainer = modal.querySelector(`.episodes-container[data-season="${seasonNum}"]`);
                const expandIcon = e.target.closest('.season-expand-btn').querySelector('.expand-icon');
                
                if (episodesContainer.style.display === 'none') {
                    episodesContainer.style.display = 'block';
                    expandIcon.textContent = '▲';
                } else {
                    episodesContainer.style.display = 'none';
                    expandIcon.textContent = '▼';
                }
            });
        });
        
        // Season checkbox logic
        modal.querySelectorAll('.season-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const seasonNum = e.target.dataset.season;
                const episodeCheckboxes = modal.querySelectorAll(`.episode-checkbox[data-season="${seasonNum}"]`);
                
                episodeCheckboxes.forEach(episodeCheckbox => {
                    if (!episodeCheckbox.disabled) {
                        episodeCheckbox.checked = e.target.checked;
                    }
                });
                
                this.updateRequestButton(modal);
            });
        });
        
        // Episode checkbox logic
        modal.querySelectorAll('.episode-checkbox').forEach(checkbox => {
            checkbox.addEventListener('change', (e) => {
                const seasonNum = e.target.dataset.season;
                const seasonCheckbox = modal.querySelector(`.season-checkbox[data-season="${seasonNum}"]`);
                const episodeCheckboxes = modal.querySelectorAll(`.episode-checkbox[data-season="${seasonNum}"]`);
                const checkedEpisodes = modal.querySelectorAll(`.episode-checkbox[data-season="${seasonNum}"]:checked`);
                
                // Update season checkbox state
                if (checkedEpisodes.length === 0) {
                    seasonCheckbox.checked = false;
                    seasonCheckbox.indeterminate = false;
                } else if (checkedEpisodes.length === episodeCheckboxes.length) {
                    seasonCheckbox.checked = true;
                    seasonCheckbox.indeterminate = false;
                } else {
                    seasonCheckbox.checked = false;
                    seasonCheckbox.indeterminate = true;
                }
                
                this.updateRequestButton(modal);
            });
        });
        
        // Request selected button
        const requestBtn = modal.querySelector('.granular-request-btn');
        requestBtn.addEventListener('click', async () => {
            await this.performGranularRequest(item, modal);
            closeModal();
        });
    }
    
    updateRequestButton(modal) {
        const requestBtn = modal.querySelector('.granular-request-btn');
        const checkedSeasons = modal.querySelectorAll('.season-checkbox:checked');
        const checkedEpisodes = modal.querySelectorAll('.episode-checkbox:checked');
        
        // Count total episodes to be requested
        let totalEpisodes = 0;
        let hasSelections = false;
        
        // Count episodes from selected seasons
        checkedSeasons.forEach(seasonCheckbox => {
            const seasonNum = seasonCheckbox.dataset.season;
            const seasonItem = modal.querySelector(`.season-item[data-season="${seasonNum}"]`);
            const seasonStats = seasonItem.querySelector('.season-stats');
            
            if (seasonStats) {
                // Extract episode count from "X/Y episodes" format
                const statsText = seasonStats.textContent;
                const match = statsText.match(/(\d+)\/(\d+)/);
                if (match) {
                    const totalInSeason = parseInt(match[2]);
                    const downloadedInSeason = parseInt(match[1]);
                    const missingInSeason = totalInSeason - downloadedInSeason;
                    totalEpisodes += missingInSeason; // Only count missing episodes
                }
            }
            hasSelections = true;
        });
        
        // Add individually selected episodes (that aren't part of a fully selected season)
        checkedEpisodes.forEach(episodeCheckbox => {
            const seasonNum = episodeCheckbox.dataset.season;
            const seasonCheckbox = modal.querySelector(`.season-checkbox[data-season="${seasonNum}"]`);
            
            // Only count if the whole season isn't selected
            if (!seasonCheckbox.checked) {
                totalEpisodes++;
            }
            hasSelections = true;
        });
        
        if (hasSelections && totalEpisodes > 0) {
            requestBtn.disabled = false;
            requestBtn.textContent = `Request ${totalEpisodes} Episode${totalEpisodes > 1 ? 's' : ''}`;
        } else if (hasSelections) {
            // Has selections but no episodes to request (all already downloaded)
            requestBtn.disabled = false;
            requestBtn.textContent = 'Request Selected';
        } else {
            requestBtn.disabled = true;
            requestBtn.textContent = 'Request Selected';
        }
    }
    
    async performGranularRequest(item, modal) {
        // Get selected seasons and episodes
        const checkedSeasons = modal.querySelectorAll('.season-checkbox:checked');
        const checkedEpisodes = modal.querySelectorAll('.episode-checkbox:checked');
        
        // Track what was requested
        const requestedSeasons = [];
        const requestedEpisodes = [];
        
        checkedSeasons.forEach(checkbox => {
            requestedSeasons.push(parseInt(checkbox.dataset.season));
        });
        
        checkedEpisodes.forEach(checkbox => {
            const seasonNum = parseInt(checkbox.dataset.season);
            const episodeNum = parseInt(checkbox.dataset.episode);
            // Only add if the whole season wasn't selected
            const seasonCheckbox = modal.querySelector(`.season-checkbox[data-season="${seasonNum}"]`);
            if (!seasonCheckbox.checked) {
                requestedEpisodes.push({ season: seasonNum, episode: episodeNum });
            }
        });
        
        // Store the requested items in localStorage
        this.saveRequestedItems(item.tmdb_id, requestedSeasons, requestedEpisodes);
        
        // For now, show notification about granular selection and fall back to simple request
        const selectedCount = checkedSeasons.length + checkedEpisodes.length;
        this.showNotification(`Granular selection (${selectedCount} items) coming soon! Using entire series request for now.`, 'info');
        
        // Update the card to show partial request status instead of full "Requested"
        const cardId = `result-card-${item.tmdb_id}-${item.media_type}`;
        const card = document.querySelector(`[data-card-id="${cardId}"]`);
        const button = card?.querySelector('.request-btn');
        const statusElement = card?.querySelector('.availability-status');
        
        if (button && statusElement) {
            // Check if all seasons are now requested
            const allRequestedItems = this.getRequestedItems(item.tmdb_id);
            const totalSeasons = modal.querySelectorAll('.season-checkbox').length;
            const isFullyRequested = allRequestedItems.seasons.length >= totalSeasons;
            
            if (isFullyRequested) {
                // All seasons requested - show as fully requested
                button.textContent = 'Already Requested';
                button.className = 'request-btn btn-disabled';
                button.disabled = true;
                
                statusElement.className = 'availability-status status-requested';
                statusElement.innerHTML = '<span class="status-icon">⏳</span><span class="status-text">Requested</span>';
                
                // Update item data
                if (this.itemData[cardId]) {
                    this.itemData[cardId].availability = {
                        ...this.itemData[cardId].availability,
                        status: 'requested',
                        message: 'Previously requested',
                        supports_granular: false
                    };
                }
            } else {
                // Partial request - keep button active
                button.textContent = 'Request More';
                button.className = 'request-btn btn-warning';
                button.disabled = false;
                
                statusElement.className = 'availability-status status-partial-request';
                statusElement.innerHTML = '<span class="status-icon">📺</span><span class="status-text">Partially Requested</span>';
                
                // Update item data
                if (this.itemData[cardId]) {
                    this.itemData[cardId].availability = {
                        ...this.itemData[cardId].availability,
                        status: 'partially_requested',
                        message: 'Some episodes requested - click to request more',
                        supports_granular: true
                    };
                }
            }
        }
    }
    
    saveRequestedItems(tmdbId, seasons, episodes) {
        const key = `requestarr_requested_${tmdbId}`;
        const existing = this.getRequestedItems(tmdbId);
        
        // Merge with existing requests
        const allSeasons = [...new Set([...existing.seasons, ...seasons])];
        const allEpisodes = [...existing.episodes, ...episodes];
        
        const requestData = {
            seasons: allSeasons,
            episodes: allEpisodes,
            timestamp: Date.now()
        };
        
        localStorage.setItem(key, JSON.stringify(requestData));
    }
    
    getRequestedItems(tmdbId) {
        const key = `requestarr_requested_${tmdbId}`;
        const stored = localStorage.getItem(key);
        
        if (stored) {
            try {
                return JSON.parse(stored);
            } catch (e) {
                console.error('Error parsing requested items:', e);
            }
        }
        
        return { seasons: [], episodes: [], timestamp: 0 };
    }

    showNotification(message, type = 'info') {
        // Create notification element
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        
        // Add to page
        document.body.appendChild(notification);
        
        // Remove after 3 seconds
        setTimeout(() => {
            if (notification.parentNode) {
                notification.parentNode.removeChild(notification);
            }
        }, 3000);
    }
}

// Initialize when DOM is loaded
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('requestarr-section')) {
        window.requestarrModule = new RequestarrModule();
    }
}); 