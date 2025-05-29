/**
 * Settings forms for Huntarr
 * This file handles generating HTML forms for each app's settings
 */

const SettingsForms = {
    // Generate Sonarr settings form
    generateSonarrForm: function(container, settings = {}) {
        // Add data-app-type attribute to container
        container.setAttribute('data-app-type', 'sonarr');
        
        // Make sure the instances array exists
        if (!settings.instances || !Array.isArray(settings.instances) || settings.instances.length === 0) {
            settings.instances = [{
                name: "Default",
                api_url: settings.api_url || "", // Legacy support
                api_key: settings.api_key || "", // Legacy support
                enabled: true
            }];
        }

        // Create a container for instances
        let instancesHtml = `
            <div class="settings-group">
                <h3>Sonarr Instances</h3>
                <div class="instances-container">
        `;

        // Generate form elements for each instance
        settings.instances.forEach((instance, index) => {
            instancesHtml += `
                <div class="instance-item" data-instance-id="${index}">
                    <div class="instance-header">
                        <h4>Instance ${index + 1}: ${instance.name || 'Unnamed'}</h4>
                        <div class="instance-actions">
                            ${index > 0 ? '<button type="button" class="remove-instance-btn">Remove</button>' : ''}
                            <button type="button" class="test-connection-btn" data-instance="${index}" style="margin-left: 10px;">
                                <i class="fas fa-plug"></i> Test Connection
                            </button>
                        </div>
                    </div>
                    <div class="instance-content">
                        <div class="setting-item">
                            <label for="sonarr-name-${index}"><a href="/Huntarr.io/docs/#/guides/multi-instance?id=naming-instances" class="info-icon" title="Learn more about naming your Sonarr instance" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Name:</label>
                            <input type="text" id="sonarr-name-${index}" name="name" value="${instance.name || ''}" placeholder="Friendly name for this Sonarr instance">
                            <p class="setting-help">Friendly name for this Sonarr instance</p>
                        </div>
                        <div class="setting-item">
                            <label for="sonarr-url-${index}"><a href="https://huntarr.io/threads/sonarr-missing-search-mode.16/" class="info-icon" title="Learn more about Sonarr URL configuration" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>URL:</label>
                            <input type="text" id="sonarr-url-${index}" name="api_url" value="${instance.api_url || ''}" placeholder="Base URL for Sonarr (e.g., http://localhost:8989)">
                            <p class="setting-help">Base URL for Sonarr (e.g., http://localhost:8989)</p>
                        </div>
                        <div class="setting-item">
                            <label for="sonarr-key-${index}"><a href="/Huntarr.io/docs/#/installation?id=api-keys" class="info-icon" title="Learn more about finding your Sonarr API key" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>API Key:</label>
                            <input type="text" id="sonarr-key-${index}" name="api_key" value="${instance.api_key || ''}" placeholder="API key for Sonarr">
                            <p class="setting-help">API key for Sonarr</p>
                        </div>
                        <div class="setting-item">
                            <label for="sonarr-enabled-${index}"><a href="/Huntarr.io/docs/#/guides/multi-instance?id=enabling-disabling-instances" class="info-icon" title="Learn more about enabling/disabling instances" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Enabled:</label>
                            <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                                <input type="checkbox" id="sonarr-enabled-${index}" name="enabled" ${instance.enabled !== false ? 'checked' : ''}>
                                <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                            </label>
                        </div>
                    </div>
                </div>
            `;
        });

        instancesHtml += `
                </div> <!-- instances-container -->
                <div class="button-container" style="text-align: center; margin-top: 15px;">
                    <button type="button" class="add-instance-btn add-sonarr-instance-btn">
                        <i class="fas fa-plus"></i> Add Sonarr Instance (${settings.instances.length}/9)
                    </button>
                </div>
            </div> <!-- settings-group -->
        `;

        // Search Settings
        let searchSettingsHtml = `
            <div class="settings-group">
                <h3>Search Settings</h3>
                <div class="setting-item">
                    <label for="sonarr-hunt-missing-mode"><a href="https://huntarr.io/threads/sonarr-missing-search-mode.16/" class="info-icon" title="Learn more about missing search modes" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Missing Search Mode:</label>
                    <select id="sonarr-hunt-missing-mode" name="hunt_missing_mode">
                        <option value="episodes" ${settings.hunt_missing_mode === 'episodes' ? 'selected' : ''}>Episodes</option>
                        <option value="seasons_packs" ${settings.hunt_missing_mode === 'seasons_packs' ? 'selected' : ''}>Season Packs</option>
                        <option value="shows" ${settings.hunt_missing_mode === 'shows' ? 'selected' : ''}>Shows</option>
                    </select>
                    <p class="setting-help">How to search for missing Sonarr content (Season Packs recommended for torrent users)</p>
                </div>
                <div class="setting-item">
                    <label for="sonarr-upgrade-mode"><a href="/Huntarr.io/docs/#/configuration?id=upgrade-modes" class="info-icon" title="Learn more about upgrade modes" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Upgrade Mode:</label>
                    <select id="sonarr-upgrade-mode" name="upgrade_mode">
                        <option value="episodes" ${settings.upgrade_mode === 'episodes' || !settings.upgrade_mode ? 'selected' : ''}>Episodes</option>
                        <option value="seasons_packs" ${settings.upgrade_mode === 'seasons_packs' ? 'selected' : ''}>Season Packs</option>
                    </select>
                    <p class="setting-help">How to search for Sonarr upgrades (Seasons/Shows modes upgrade entire seasons or shows at once)</p>
                </div>
                <div class="setting-item">
                    <label for="sonarr-hunt-missing-items"><a href="/Huntarr.io/docs/#/configuration?id=missing-items-search" class="info-icon" title="Learn more about missing items search" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Missing Search:</label>
                    <input type="number" id="sonarr-hunt-missing-items" name="hunt_missing_items" min="0" value="${settings.hunt_missing_items !== undefined ? settings.hunt_missing_items : 1}">
                    <p class="setting-help">Number of missing items to search per cycle (0 to disable)</p>
                </div>
                <div class="setting-item">
                    <label for="sonarr-hunt-upgrade-items"><a href="https://huntarr.io" class="info-icon" title="Learn more about upgrade items search" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Upgrade Search:</label>
                    <input type="number" id="sonarr-hunt-upgrade-items" name="hunt_upgrade_items" min="0" value="${settings.hunt_upgrade_items !== undefined ? settings.hunt_upgrade_items : 0}">
                    <p class="setting-help">Number of episodes to upgrade per cycle (0 to disable)</p>
                </div>
                <div class="setting-item">
                    <label for="sonarr_sleep_duration"><a href="/Huntarr.io/docs/#/configuration?id=sleep-duration" class="info-icon" title="Learn more about sleep duration" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Sleep Duration:</label>
                    <input type="number" id="sonarr_sleep_duration" name="sleep_duration" min="60" value="${settings.sleep_duration !== undefined ? settings.sleep_duration : 900}">
                    <p class="setting-help">Time in seconds between processing cycles</p>
                </div>
                <div class="setting-item">
                    <label for="sonarr_hourly_cap"><a href="#" class="info-icon" title="Maximum API requests per hour for this app" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>API Cap - Hourly:</label>
                    <input type="number" id="sonarr_hourly_cap" name="hourly_cap" min="1" max="500" value="${settings.hourly_cap !== undefined ? settings.hourly_cap : 20}">
                    <p class="setting-help">Maximum API requests per hour (helps prevent rate limiting)</p>
                    <p class="setting-help" style="color: #cc0000; font-weight: bold;">Setting this too high will risk your accounts being banned! You have been warned!</p>
                </div>
            </div>
            
            <div class="settings-group">
                <h3>Additional Options</h3>
                <div class="setting-item">
                    <label for="sonarr_monitored_only"><a href="/Huntarr.io/docs/#/configuration?id=monitored-only" class="info-icon" title="Learn more about monitored only option" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Monitored Only:</label>
                    <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                        <input type="checkbox" id="sonarr_monitored_only" name="monitored_only" ${settings.monitored_only !== false ? 'checked' : ''}>
                        <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                    </label>
                    <p class="setting-help">Only search for monitored items</p>
                </div>
                <div class="setting-item">
                    <label for="sonarr_skip_future_episodes"><a href="https://huntarr.io" class="info-icon" title="Learn more about skipping future episodes" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Skip Future Episodes:</label>
                    <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                        <input type="checkbox" id="sonarr_skip_future_episodes" name="skip_future_episodes" ${settings.skip_future_episodes !== false ? 'checked' : ''}>
                        <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                    </label>
                    <p class="setting-help">Skip searching for episodes with future air dates</p>
                </div>
            </div>
        `;

        // Set the content
        container.innerHTML = instancesHtml + searchSettingsHtml;

        // Setup instance management (add/remove/test)
        SettingsForms.setupInstanceManagement(container, 'sonarr', settings.instances.length);
    },
    
    // Generate Radarr settings form
    generateRadarrForm: function(container, settings = {}) {
        // Add data-app-type attribute to container
        container.setAttribute('data-app-type', 'radarr');
        
        // Make sure the instances array exists
        if (!settings.instances || !Array.isArray(settings.instances) || settings.instances.length === 0) {
            settings.instances = [{
                name: "Default",
                api_url: settings.api_url || "",
                api_key: settings.api_key || "",
                enabled: true
            }];
        }
        
        // Create a container for instances with a scrollable area for many instances
        let instancesHtml = `
            <div class="settings-group">
                <h3>Radarr Instances</h3>
                <div class="instances-container">
        `;
        
        // Generate form elements for each instance
        settings.instances.forEach((instance, index) => {
            instancesHtml += `
                <div class="instance-item" data-instance-id="${index}">
                    <div class="instance-header">
                        <h4>Instance ${index + 1}: ${instance.name || 'Unnamed'}</h4>
                        <div class="instance-actions">
                            ${index > 0 ? '<button type="button" class="remove-instance-btn">Remove</button>' : ''}
                            <button type="button" class="test-connection-btn" data-instance="${index}" style="margin-left: 10px;">
                                <i class="fas fa-plug"></i> Test Connection
                            </button>
                        </div>
                    </div>
                    <div class="instance-content">
                        <div class="setting-item">
                            <label for="radarr-name-${index}"><a href="https://huntarr.io/threads/name-field.18/" class="info-icon" title="Learn more about naming your Radarr instance" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Name:</label>
                            <input type="text" id="radarr-name-${index}" name="name" value="${instance.name || ''}" placeholder="Friendly name for this Radarr instance">
                            <p class="setting-help">Friendly name for this Radarr instance</p>
                        </div>
                        <div class="setting-item">
                            <label for="radarr-url-${index}"><a href="https://huntarr.io/threads/url.19/" class="info-icon" title="Learn more about Radarr URL configuration" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>URL:</label>
                            <input type="text" id="radarr-url-${index}" name="api_url" value="${instance.api_url || ''}" placeholder="Base URL for Radarr (e.g., http://localhost:7878)">
                            <p class="setting-help">Base URL for Radarr (e.g., http://localhost:7878)</p>
                        </div>
                        <div class="setting-item">
                            <label for="radarr-key-${index}"><a href="https://huntarr.io/threads/api-key.20/" class="info-icon" title="Learn more about finding your Radarr API key" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>API Key:</label>
                            <input type="text" id="radarr-key-${index}" name="api_key" value="${instance.api_key || ''}" placeholder="API key for Radarr">
                            <p class="setting-help">API key for Radarr</p>
                        </div>
                        <div class="setting-item">
                            <label for="radarr-enabled-${index}"><a href="https://huntarr.io/threads/enable-toggle.21/" class="info-icon" title="Learn more about enabling/disabling instances" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Enabled:</label>
                            <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                                <input type="checkbox" id="radarr-enabled-${index}" name="enabled" ${instance.enabled !== false ? 'checked' : ''}>
                                <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                            </label>
                        </div>
                    </div>
                </div>
            `;
        });

        // Add a button to add new instances (limit to 9 total)
        instancesHtml += `
                </div> <!-- instances-container -->
                <div class="button-container" style="text-align: center; margin-top: 15px;">
                    <button type="button" class="add-instance-btn add-radarr-instance-btn">
                        <i class="fas fa-plus"></i> Add Radarr Instance (${settings.instances.length}/9)
                    </button>
                </div>
            </div> <!-- settings-group -->
        `;
        
        // Continue with the rest of the settings form
        let searchSettingsHtml = `
            <div class="settings-group">
                <h3>Search Settings</h3>
                <div class="setting-item">
                    <label for="radarr_hunt_missing_movies"><a href="https://huntarr.io" class="info-icon" title="Learn more about missing movies search" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Missing Search:</label>
                    <input type="number" id="radarr_hunt_missing_movies" name="hunt_missing_movies" min="0" value="${settings.hunt_missing_movies !== undefined ? (settings.hunt_missing_movies === 0 ? 0 : settings.hunt_missing_movies) : 1}">
                    <p class="setting-help">Number of missing movies to search per cycle (0 to disable)</p>
                </div>
                <div class="setting-item">
                    <label for="radarr_hunt_upgrade_movies"><a href="https://huntarr.io" class="info-icon" title="Learn more about upgrading movies" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Upgrade Search:</label>
                    <input type="number" id="radarr_hunt_upgrade_movies" name="hunt_upgrade_movies" min="0" value="${settings.hunt_upgrade_movies !== undefined ? (settings.hunt_upgrade_movies === 0 ? 0 : settings.hunt_upgrade_movies) : 0}">
                    <p class="setting-help">Number of movies to search for quality upgrades per cycle (0 to disable)</p>
                </div>
                <div class="setting-item">
                    <label for="radarr_sleep_duration"><a href="/Huntarr.io/docs/#/configuration?id=sleep-duration" class="info-icon" title="Learn more about sleep duration" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Sleep Duration:</label>
                    <input type="number" id="radarr_sleep_duration" name="sleep_duration" min="60" value="${settings.sleep_duration !== undefined ? settings.sleep_duration : 900}">
                    <p class="setting-help">Time in seconds between processing cycles</p>
                </div>
                <div class="setting-item">
                    <label for="radarr_hourly_cap"><a href="#" class="info-icon" title="Maximum API requests per hour for this app" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>API Cap - Hourly:</label>
                    <input type="number" id="radarr_hourly_cap" name="hourly_cap" min="1" max="500" value="${settings.hourly_cap !== undefined ? settings.hourly_cap : 20}">
                    <p class="setting-help">Maximum API requests per hour (helps prevent rate limiting)</p>
                    <p class="setting-help" style="color: #cc0000; font-weight: bold;">Setting this too high will risk your accounts being banned! You have been warned!</p>
                </div>
            </div>
            
            <div class="settings-group">
                <h3>Additional Options</h3>
                <div class="setting-item">
                    <label for="radarr_monitored_only"><a href="/Huntarr.io/docs/#/configuration?id=monitored-only" class="info-icon" title="Learn more about monitored only option" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Monitored Only:</label>
                    <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                        <input type="checkbox" id="radarr_monitored_only" ${settings.monitored_only !== false ? 'checked' : ''}>
                        <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                    </label>
                    <p class="setting-help">Only search for monitored items</p>
                </div>
                <div class="setting-item">
                    <label for="radarr_skip_future_releases"><a href="https://huntarr.io" class="info-icon" title="Learn more about skipping future releases" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Skip Future Releases:</label>
                    <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                        <input type="checkbox" id="radarr_skip_future_releases" ${settings.skip_future_releases !== false ? 'checked' : ''}>
                        <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                    </label>
                    <p class="setting-help">Skip searching for movies with future release dates</p>
                </div>
                <div class="setting-item" id="future_release_type_container" style="${settings.skip_future_releases !== false ? '' : 'display: none;'}">
                    <label for="radarr_release_type"><a href="https://huntarr.io/threads/radarr-release-type.24/" class="info-icon" title="Learn more about release type options" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Release Type for Future Status:</label>
                    <select id="radarr_release_type">
                        <option value="digital" ${settings.release_type === 'digital' ? 'selected' : ''}>Digital Release</option>
                        <option value="physical" ${settings.release_type === 'physical' || !settings.release_type ? 'selected' : ''}>Physical Release</option>
                        <option value="cinema" ${settings.release_type === 'cinema' ? 'selected' : ''}>Cinema Release</option>
                    </select>
                    <p class="setting-help">Select which release date type to use when determining if a movie is considered a future release</p>
                </div>
            </div>
        `;

        // Set the content
        container.innerHTML = instancesHtml + searchSettingsHtml;

        // Add event listeners for the instance management
        SettingsForms.setupInstanceManagement(container, 'radarr', settings.instances.length);
        
        // Set up event listeners for the skip_future_releases checkbox
        const skipFutureCheckbox = container.querySelector('#radarr_skip_future_releases');
        const releaseTypeContainer = container.querySelector('#future_release_type_container');
        
        if (skipFutureCheckbox) {
            skipFutureCheckbox.addEventListener('change', function() {
                if (this.checked) {
                    releaseTypeContainer.style.display = '';
                } else {
                    releaseTypeContainer.style.display = 'none';
                }
            });
        }
    },
    
    // Generate Lidarr settings form
    generateLidarrForm: function(container, settings = {}) {
        // Add data-app-type attribute to container
        container.setAttribute('data-app-type', 'lidarr');
        
        // Make sure the instances array exists
        if (!settings.instances || !Array.isArray(settings.instances) || settings.instances.length === 0) {
            settings.instances = [{
                name: "Default",
                api_url: settings.api_url || "", // Legacy support
                api_key: settings.api_key || "", // Legacy support
                enabled: true
            }];
        }
        
        // Create a container for instances
        let instancesHtml = `
            <div class="settings-group">
                <h3>Lidarr Instances</h3>
                <div class="instances-container">
        `;
        
        // Generate form elements for each instance
        settings.instances.forEach((instance, index) => {
            instancesHtml += `
                <div class="instance-item" data-instance-id="${index}">
                    <div class="instance-header">
                        <h4>Instance ${index + 1}: ${instance.name || 'Unnamed'}</h4>
                        <div class="instance-actions">
                            ${index > 0 ? '<button type="button" class="remove-instance-btn">Remove</button>' : ''}
                            <button type="button" class="test-connection-btn" data-instance="${index}" style="margin-left: 10px;">
                                <i class="fas fa-plug"></i> Test Connection
                            </button>
                        </div>
                    </div>
                    <div class="instance-content">
                        <div class="setting-item">
                            <label for="lidarr-name-${index}"><a href="https://huntarr.io/threads/name-field.18/" class="info-icon" title="Learn more about naming your Lidarr instance" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Name:</label>
                            <input type="text" id="lidarr-name-${index}" name="name" value="${instance.name || ''}" placeholder="Friendly name for this Lidarr instance">
                            <p class="setting-help">Friendly name for this Lidarr instance</p>
                        </div>
                        <div class="setting-item">
                            <label for="lidarr-url-${index}"><a href="https://huntarr.io/threads/url.19/" class="info-icon" title="Learn more about Lidarr URL configuration" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>URL:</label>
                            <input type="text" id="lidarr-url-${index}" name="api_url" value="${instance.api_url || ''}" placeholder="Base URL for Lidarr (e.g., http://localhost:8686)">
                            <p class="setting-help">Base URL for Lidarr (e.g., http://localhost:8686)</p>
                        </div>
                        <div class="setting-item">
                            <label for="lidarr-key-${index}"><a href="https://huntarr.io/threads/api-key.20/" class="info-icon" title="Learn more about finding your Lidarr API key" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>API Key:</label>
                            <input type="text" id="lidarr-key-${index}" name="api_key" value="${instance.api_key || ''}" placeholder="API key for Lidarr">
                            <p class="setting-help">API key for Lidarr</p>
                        </div>
                        <div class="setting-item">
                            <label for="lidarr-enabled-${index}"><a href="https://huntarr.io/threads/enable-toggle.21/" class="info-icon" title="Learn more about enabling/disabling instances" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Enabled:</label>
                            <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                                <input type="checkbox" id="lidarr-enabled-${index}" name="enabled" ${instance.enabled !== false ? 'checked' : ''}>
                                <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                            </label>
                        </div>
                    </div>
                </div>
            `;
        });

        instancesHtml += `
                </div> <!-- instances-container -->
                <div class="button-container" style="text-align: center; margin-top: 15px;">
                    <button type="button" class="add-instance-btn add-lidarr-instance-btn">
                        <i class="fas fa-plus"></i> Add Lidarr Instance (${settings.instances.length}/9)
                    </button>
                </div>
            </div> <!-- settings-group -->
        `;
        
        // Continue with the rest of the settings form
        container.innerHTML = `
            ${instancesHtml}
            
            <div class="settings-group">
                <h3>Search Settings</h3>
                <div class="setting-item">
                    <label for="lidarr_hunt_missing_mode"><a href="https://huntarr.io" class="info-icon" title="Learn more about missing search modes" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Missing Search Mode:</label>
                    <select id="lidarr_hunt_missing_mode" name="hunt_missing_mode">
                        <option value="artist" ${settings.hunt_missing_mode === 'artist' ? 'selected' : ''}>Artist</option>
                        <option value="album" ${settings.hunt_missing_mode === 'album' ? 'selected' : ''}>Album</option>
                    </select>
                    <p class="setting-help">Whether to search by artist (all missing albums for artist) or individual albums</p>
                </div>
                <div class="setting-item">
                    <label for="lidarr_hunt_missing_items"><a href="https://huntarr.io" class="info-icon" title="Learn more about missing items search" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Missing Search:</label>
                    <input type="number" id="lidarr_hunt_missing_items" name="hunt_missing_items" min="0" value="${settings.hunt_missing_items !== undefined ? settings.hunt_missing_items : 1}">
                    <p class="setting-help">Number of artists with missing albums to search per cycle (0 to disable)</p>
                </div>
                
                <div class="setting-item">
                    <label for="lidarr_hunt_upgrade_items"><a href="https://huntarr.io" class="info-icon" title="Learn more about upgrading items" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Upgrade Search:</label>
                    <input type="number" id="lidarr_hunt_upgrade_items" name="hunt_upgrade_items" min="0" value="${settings.hunt_upgrade_items !== undefined ? settings.hunt_upgrade_items : 0}">
                    <p class="setting-help">Number of albums to search for quality upgrades per cycle (0 to disable)</p>
                </div>
                <div class="setting-item">
                    <label for="lidarr_sleep_duration"><a href="/Huntarr.io/docs/#/configuration?id=sleep-duration" class="info-icon" title="Learn more about sleep duration" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Sleep Duration:</label>
                    <input type="number" id="lidarr_sleep_duration" name="sleep_duration" min="60" value="${settings.sleep_duration !== undefined ? settings.sleep_duration : 900}">
                    <p class="setting-help">Time in seconds between processing cycles</p>
                </div>
                <div class="setting-item">
                    <label for="lidarr_hourly_cap"><a href="#" class="info-icon" title="Maximum API requests per hour for this app" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>API Cap - Hourly:</label>
                    <input type="number" id="lidarr_hourly_cap" name="hourly_cap" min="1" max="500" value="${settings.hourly_cap !== undefined ? settings.hourly_cap : 20}">
                    <p class="setting-help">Maximum API requests per hour (helps prevent rate limiting)</p>
                    <p class="setting-help" style="color: #cc0000; font-weight: bold;">Setting this too high will risk your accounts being banned! You have been warned!</p>
                </div>
            </div>
            
            <div class="settings-group">
                <h3>Additional Options</h3>
                <div class="setting-item">
                    <label for="lidarr_monitored_only"><a href="/Huntarr.io/docs/#/configuration?id=monitored-only" class="info-icon" title="Learn more about monitored only option" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Monitored Only:</label>
                    <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                        <input type="checkbox" id="lidarr_monitored_only" ${settings.monitored_only !== false ? 'checked' : ''}>
                        <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                    </label>
                    <p class="setting-help">Only search for monitored items</p>
                </div>
                <div class="setting-item">
                    <label for="lidarr_skip_future_releases"><a href="https://huntarr.io" class="info-icon" title="Learn more about skipping future releases" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Skip Future Releases:</label>
                    <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                        <input type="checkbox" id="lidarr_skip_future_releases" ${settings.skip_future_releases !== false ? 'checked' : ''}>
                        <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                    </label>
                    <p class="setting-help">Skip searching for albums with future release dates</p>
                </div>
            </div>
        `;

        // Add event listeners for the instance management
        SettingsForms.setupInstanceManagement(container, 'lidarr', settings.instances.length);
    },
    
    // Generate Readarr settings form
    generateReadarrForm: function(container, settings = {}) {
        // Add data-app-type attribute to container
        container.setAttribute('data-app-type', 'readarr');
        
        // Make sure the instances array exists
        if (!settings.instances || !Array.isArray(settings.instances) || settings.instances.length === 0) {
            settings.instances = [{
                name: "Default",
                api_url: settings.api_url || "", // Legacy support
                api_key: settings.api_key || "", // Legacy support
                enabled: true
            }];
        }
        
        // Create a container for instances
        let instancesHtml = `
            <div class="settings-group">
                <h3>Readarr Instances</h3>
                <div class="instances-container">
        `;
        
        // Generate form elements for each instance
        settings.instances.forEach((instance, index) => {
            instancesHtml += `
                <div class="instance-item" data-instance-id="${index}">
                    <div class="instance-header">
                        <h4>Instance ${index + 1}: ${instance.name || 'Unnamed'}</h4>
                        <div class="instance-actions">
                            ${index > 0 ? '<button type="button" class="remove-instance-btn">Remove</button>' : ''}
                            <button type="button" class="test-connection-btn" data-instance="${index}" style="margin-left: 10px;">
                                <i class="fas fa-plug"></i> Test Connection
                            </button>
                        </div>
                    </div>
                    <div class="instance-content">
                        <div class="setting-item">
                            <label for="readarr-name-${index}"><a href="https://huntarr.io/threads/name-field.18/" class="info-icon" title="Learn more about naming your Readarr instance" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Name:</label>
                            <input type="text" id="readarr-name-${index}" name="name" value="${instance.name || ''}" placeholder="Friendly name for this Readarr instance">
                            <p class="setting-help">Friendly name for this Readarr instance</p>
                        </div>
                        <div class="setting-item">
                            <label for="readarr-url-${index}"><a href="https://huntarr.io/threads/url.19/" class="info-icon" title="Learn more about Readarr URL configuration" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>URL:</label>
                            <input type="text" id="readarr-url-${index}" name="api_url" value="${instance.api_url || ''}" placeholder="Base URL for Readarr (e.g., http://localhost:8787)">
                            <p class="setting-help">Base URL for Readarr (e.g., http://localhost:8787)</p>
                        </div>
                        <div class="setting-item">
                            <label for="readarr-key-${index}"><a href="https://huntarr.io/threads/api-key.20/" class="info-icon" title="Learn more about finding your Readarr API key" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>API Key:</label>
                            <input type="text" id="readarr-key-${index}" name="api_key" value="${instance.api_key || ''}" placeholder="API key for Readarr">
                            <p class="setting-help">API key for Readarr</p>
                        </div>
                        <div class="setting-item">
                            <label for="readarr-enabled-${index}"><a href="https://huntarr.io/threads/enable-toggle.21/" class="info-icon" title="Learn more about enabling/disabling instances" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Enabled:</label>
                            <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                                <input type="checkbox" id="readarr-enabled-${index}" name="enabled" ${instance.enabled !== false ? 'checked' : ''}>
                                <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                            </label>
                        </div>
                    </div>
                </div>
            `;
        });

        instancesHtml += `
                </div> <!-- instances-container -->
                <div class="button-container" style="text-align: center; margin-top: 15px;">
                    <button type="button" class="add-instance-btn add-readarr-instance-btn">
                        <i class="fas fa-plus"></i> Add Readarr Instance (${settings.instances.length}/9)
                    </button>
                </div>
            </div> <!-- settings-group -->
        `;
        
        // Continue with the rest of the settings form
        container.innerHTML = `
            ${instancesHtml}
            
            <div class="settings-group">
                <h3>Search Settings</h3>
                <div class="setting-item">
                    <label for="readarr_hunt_missing_books"><a href="https://huntarr.io" class="info-icon" title="Learn more about missing books search" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Missing Search:</label>
                    <input type="number" id="readarr_hunt_missing_books" name="hunt_missing_books" min="0" value="${settings.hunt_missing_books !== undefined ? settings.hunt_missing_books : 1}">
                    <p class="setting-help">Number of missing books to search per cycle (0 to disable)</p>
                </div>
                <div class="setting-item">
                    <label for="readarr_hunt_upgrade_books"><a href="https://huntarr.io" class="info-icon" title="Learn more about upgrading books" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Upgrade Search:</label>
                    <input type="number" id="readarr_hunt_upgrade_books" name="hunt_upgrade_books" min="0" value="${settings.hunt_upgrade_books !== undefined ? settings.hunt_upgrade_books : 0}">
                    <p class="setting-help">Number of books to search for quality upgrades per cycle (0 to disable)</p>
                </div>
                <div class="setting-item">
                    <label for="readarr_sleep_duration"><a href="/Huntarr.io/docs/#/configuration?id=sleep-duration" class="info-icon" title="Learn more about sleep duration" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Sleep Duration:</label>
                    <input type="number" id="readarr_sleep_duration" name="sleep_duration" min="60" value="${settings.sleep_duration !== undefined ? settings.sleep_duration : 900}">
                    <p class="setting-help">Time in seconds between processing cycles</p>
                </div>
                <div class="setting-item">
                    <label for="readarr_hourly_cap"><a href="#" class="info-icon" title="Maximum API requests per hour for this app" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>API Cap - Hourly:</label>
                    <input type="number" id="readarr_hourly_cap" name="hourly_cap" min="1" max="500" value="${settings.hourly_cap !== undefined ? settings.hourly_cap : 20}">
                    <p class="setting-help">Maximum API requests per hour (helps prevent rate limiting)</p>
                    <p class="setting-help" style="color: #cc0000; font-weight: bold;">Setting this too high will risk your accounts being banned! You have been warned!</p>
                </div>
            </div>
            
            <div class="settings-group">
                <h3>Additional Options</h3>
                <div class="setting-item">
                    <label for="readarr_monitored_only"><a href="/Huntarr.io/docs/#/configuration?id=monitored-only" class="info-icon" title="Learn more about monitored only option" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Monitored Only:</label>
                    <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                        <input type="checkbox" id="readarr_monitored_only" ${settings.monitored_only !== false ? 'checked' : ''}>
                        <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                    </label>
                    <p class="setting-help">Only search for monitored items</p>
                </div>
                <div class="setting-item">
                    <label for="readarr_skip_future_releases"><a href="https://huntarr.io" class="info-icon" title="Learn more about skipping future releases" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Skip Future Releases:</label>
                    <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                        <input type="checkbox" id="readarr_skip_future_releases" ${settings.skip_future_releases !== false ? 'checked' : ''}>
                        <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                    </label>
                    <p class="setting-help">Skip searching for books with future release dates</p>
                </div>
            </div>
        `;

        // Add event listeners for the instance management
        SettingsForms.setupInstanceManagement(container, 'readarr', settings.instances.length);
    },
    
    // Generate Whisparr settings form
    generateWhisparrForm: function(container, settings = {}) {
        // Add data-app-type attribute to container
        container.setAttribute('data-app-type', 'whisparr');
        
        // Make sure the instances array exists
        if (!settings.instances || !Array.isArray(settings.instances) || settings.instances.length === 0) {
            settings.instances = [{
                name: "Default",
                api_url: "",
                api_key: "",
                enabled: true
            }];
        }

        // Create a container for instances
        let instancesHtml = `
            <div class="settings-group">
                <h3>Whisparr V2 Instances</h3>
                <div class="instances-container">
        `;

        // Generate form elements for each instance
        settings.instances.forEach((instance, index) => {
            instancesHtml += `
                <div class="instance-item" data-instance-id="${index}">
                    <div class="instance-header">
                        <h4>Instance ${index + 1}: ${instance.name || 'Unnamed'}</h4>
                        <div class="instance-actions">
                            ${index > 0 ? '<button type="button" class="remove-instance-btn">Remove</button>' : ''}
                            <button type="button" class="test-connection-btn" data-instance="${index}" style="margin-left: 10px;">
                                <i class="fas fa-plug"></i> Test Connection
                            </button>
                        </div>
                    </div>
                    <div class="instance-content">
                        <div class="setting-item">
                            <label for="whisparr-name-${index}"><a href="https://huntarr.io/threads/name-field.18/" class="info-icon" title="Learn more about naming your Whisparr instance" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Name:</label>
                            <input type="text" id="whisparr-name-${index}" name="name" value="${instance.name || ''}" placeholder="Friendly name for this Whisparr V2 instance">
                            <p class="setting-help">Friendly name for this Whisparr V2 instance</p>
                        </div>
                        <div class="setting-item">
                            <label for="whisparr-url-${index}"><a href="https://huntarr.io/threads/url.19/" class="info-icon" title="Learn more about Whisparr URL configuration" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>URL:</label>
                            <input type="text" id="whisparr-url-${index}" name="api_url" value="${instance.api_url || ''}" placeholder="Base URL for Whisparr V2 (e.g., http://localhost:6969)">
                            <p class="setting-help">Base URL for Whisparr V2 (e.g., http://localhost:6969)</p>
                        </div>
                        <div class="setting-item">
                            <label for="whisparr-key-${index}"><a href="https://huntarr.io/threads/api-key.20/" class="info-icon" title="Learn more about finding your Whisparr API key" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>API Key:</label>
                            <input type="text" id="whisparr-key-${index}" name="api_key" value="${instance.api_key || ''}" placeholder="API key for Whisparr V2">
                            <p class="setting-help">API key for Whisparr V2</p>
                        </div>
                        <div class="setting-item">
                            <label for="whisparr-enabled-${index}"><a href="https://huntarr.io/threads/enable-toggle.21/" class="info-icon" title="Learn more about enabling/disabling instances" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Enabled:</label>
                            <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                                <input type="checkbox" id="whisparr-enabled-${index}" name="enabled" ${instance.enabled !== false ? 'checked' : ''}>
                                <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                            </label>
                        </div>
                    </div>
                </div>
            `;
        });

        instancesHtml += `
                </div> <!-- instances-container -->
                <div class="button-container" style="text-align: center; margin-top: 15px;">
                    <button type="button" class="add-instance-btn add-whisparr-instance-btn">
                        <i class="fas fa-plus"></i> Add Whisparr V2 Instance (${settings.instances.length}/9)
                    </button>
                </div>
            </div> <!-- settings-group -->
        `;
        
        // Search Settings
        let searchSettingsHtml = `
            <div class="settings-group">
                <h3>Search Settings</h3>
                <div class="setting-item">
                    <label for="whisparr_hunt_missing_items"><a href="https://huntarr.io" class="info-icon" title="Learn more about missing items search" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Missing Search:</label>
                    <input type="number" id="whisparr_hunt_missing_items" name="hunt_missing_items" min="0" value="${settings.hunt_missing_items !== undefined ? settings.hunt_missing_items : 1}">
                    <p class="setting-help">Number of missing items to search per cycle (0 to disable)</p>
                </div>
                <div class="setting-item">
                    <label for="whisparr_hunt_upgrade_items"><a href="https://huntarr.io" class="info-icon" title="Learn more about upgrading items" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Upgrade Search:</label>
                    <input type="number" id="whisparr_hunt_upgrade_items" name="hunt_upgrade_items" min="0" value="${settings.hunt_upgrade_items !== undefined ? settings.hunt_upgrade_items : 0}">
                    <p class="setting-help">Number of items to search for quality upgrades per cycle (0 to disable)</p>
                </div>
                <div class="setting-item">
                    <label for="whisparr_sleep_duration"><a href="/Huntarr.io/docs/#/configuration?id=sleep-duration" class="info-icon" title="Learn more about sleep duration" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Sleep Duration:</label>
                    <input type="number" id="whisparr_sleep_duration" name="sleep_duration" min="60" value="${settings.sleep_duration !== undefined ? settings.sleep_duration : 900}">
                    <p class="setting-help">Time in seconds between processing cycles</p>
                </div>
                <div class="setting-item">
                    <label for="whisparr_hourly_cap"><a href="#" class="info-icon" title="Maximum API requests per hour for this app" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>API Cap - Hourly:</label>
                    <input type="number" id="whisparr_hourly_cap" name="hourly_cap" min="1" max="500" value="${settings.hourly_cap !== undefined ? settings.hourly_cap : 20}">
                    <p class="setting-help">Maximum API requests per hour (helps prevent rate limiting)</p>
                    <p class="setting-help" style="color: #cc0000; font-weight: bold;">Setting this too high will risk your accounts being banned! You have been warned!</p>
                </div>
            </div>
            
            <div class="settings-group">
                <h3>Additional Options</h3>
                <div class="setting-item">
                    <label for="whisparr_monitored_only"><a href="/Huntarr.io/docs/#/configuration?id=monitored-only" class="info-icon" title="Learn more about monitored only option" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Monitored Only:</label>
                    <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                        <input type="checkbox" id="whisparr_monitored_only" name="monitored_only" ${settings.monitored_only !== false ? 'checked' : ''}>
                        <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                    </label>
                    <p class="setting-help">Only search for monitored items</p>
                </div>
                <div class="setting-item">
                    <label for="whisparr_skip_future_releases"><a href="https://huntarr.io" class="info-icon" title="Learn more about skipping future releases" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Skip Future Releases:</label>
                    <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                        <input type="checkbox" id="whisparr_skip_future_releases" name="skip_future_releases" ${settings.skip_future_releases !== false ? 'checked' : ''}>
                        <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                    </label>
                    <p class="setting-help">Skip searching for scenes with future release dates</p>
                </div>
            </div>
        `;

        // Set the content
        container.innerHTML = instancesHtml + searchSettingsHtml;

        // Add event listeners for the instance management
        this.setupInstanceManagement(container, 'whisparr', settings.instances.length);
        
        // Update duration display
        this.updateDurationDisplay();
    },
    
    // Generate Eros settings form
    generateErosForm: function(container, settings = {}) {
        // Add data-app-type attribute to container
        container.setAttribute('data-app-type', 'eros');
        
        // Make sure the instances array exists
        if (!settings.instances || !Array.isArray(settings.instances) || settings.instances.length === 0) {
            settings.instances = [{
                name: "Default",
                api_url: "",
                api_key: "",
                enabled: true
            }];
        }

        // Create a container for instances
        let instancesHtml = `
            <div class="settings-group">
                <h3>Whisparr V3 Instances</h3>
                <div class="instances-container">
        `;

        // Generate form elements for each instance
        settings.instances.forEach((instance, index) => {
            instancesHtml += `
                <div class="instance-item" data-instance-id="${index}">
                    <div class="instance-header">
                        <h4>Instance ${index + 1}: ${instance.name || 'Unnamed'}</h4>
                        <div class="instance-actions">
                            ${index > 0 ? '<button type="button" class="remove-instance-btn">Remove</button>' : ''}
                            <button type="button" class="test-connection-btn" data-instance="${index}" style="margin-left: 10px;">
                                <i class="fas fa-plug"></i> Test Connection
                            </button>
                        </div>
                    </div>
                    <div class="instance-content">
                        <div class="setting-item">
                            <label for="eros-name-${index}"><a href="https://huntarr.io/threads/name-field.18/" class="info-icon" title="Learn more about naming your Whisparr V3 instance" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Name:</label>
                            <input type="text" id="eros-name-${index}" name="name" value="${instance.name || ''}" placeholder="Friendly name for this Whisparr V3 instance">
                            <p class="setting-help">Friendly name for this Whisparr V3 instance</p>
                        </div>
                        <div class="setting-item">
                            <label for="eros-url-${index}"><a href="https://huntarr.io/threads/url.19/" class="info-icon" title="Learn more about Whisparr V3 URL configuration" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>URL:</label>
                            <input type="text" id="eros-url-${index}" name="api_url" value="${instance.api_url || ''}" placeholder="Base URL for Whisparr V3 (e.g., http://localhost:6969)">
                            <p class="setting-help">Base URL for Whisparr V3 (e.g., http://localhost:6969)</p>
                        </div>
                        <div class="setting-item">
                            <label for="eros-key-${index}"><a href="https://huntarr.io/threads/api-key.20/" class="info-icon" title="Learn more about finding your Whisparr V3 API key" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>API Key:</label>
                            <input type="text" id="eros-key-${index}" name="api_key" value="${instance.api_key || ''}" placeholder="API key for Whisparr V3">
                            <p class="setting-help">API key for Whisparr V3</p>
                        </div>
                        <div class="setting-item">
                            <label for="eros-enabled-${index}"><a href="https://huntarr.io/threads/enable-toggle.21/" class="info-icon" title="Learn more about enabling/disabling instances" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Enabled:</label>
                            <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                                <input type="checkbox" id="eros-enabled-${index}" name="enabled" ${instance.enabled !== false ? 'checked' : ''}>
                                <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                            </label>
                        </div>
                    </div>
                </div>
            `;
        });

        instancesHtml += `
                </div> <!-- instances-container -->
                <div class="button-container" style="text-align: center; margin-top: 15px;">
                    <button type="button" class="add-instance-btn add-eros-instance-btn">
                        <i class="fas fa-plus"></i> Add Whisparr V3 Instance (${settings.instances.length}/9)
                    </button>
                </div>
            </div> <!-- settings-group -->
        `;
        
        // Search Mode dropdown
        let searchSettingsHtml = `
            <div class="settings-group">
                <h3>Search Settings</h3>
                <div class="setting-item">
                    <label for="eros_search_mode"><a href="https://huntarr.io" class="info-icon" title="Learn more about search modes" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Search Mode:</label>
                    <select id="eros_search_mode" name="search_mode">
                        <option value="movie" ${settings.search_mode === 'movie' || !settings.search_mode ? 'selected' : ''}>Movie</option>
                        <option value="scene" ${settings.search_mode === 'scene' ? 'selected' : ''}>Scene</option>
                    </select>
                    <p class="setting-help">How to search for missing and upgradable Whisparr V3 content (Movie-based or Scene-based)</p>
                </div>
                <div class="setting-item">
                    <label for="eros_hunt_missing_items"><a href="https://huntarr.io" class="info-icon" title="Learn more about missing items search" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Missing Search:</label>
                    <input type="number" id="eros_hunt_missing_items" name="hunt_missing_items" min="0" value="${settings.hunt_missing_items !== undefined ? settings.hunt_missing_items : 1}">
                    <p class="setting-help">Number of missing items to search per cycle (0 to disable)</p>
                </div>
                <div class="setting-item">
                    <label for="eros_hunt_upgrade_items"><a href="https://huntarr.io" class="info-icon" title="Learn more about upgrading items" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Upgrade Search:</label>
                    <input type="number" id="eros_hunt_upgrade_items" name="hunt_upgrade_items" min="0" value="${settings.hunt_upgrade_items !== undefined ? settings.hunt_upgrade_items : 0}">
                    <p class="setting-help">Number of items to search for quality upgrades per cycle (0 to disable)</p>
                </div>
                <div class="setting-item">
                    <label for="eros_sleep_duration"><a href="/Huntarr.io/docs/#/configuration?id=sleep-duration" class="info-icon" title="Learn more about sleep duration" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Sleep Duration:</label>
                    <input type="number" id="eros_sleep_duration" name="sleep_duration" min="60" value="${settings.sleep_duration !== undefined ? settings.sleep_duration : 900}">
                    <p class="setting-help">Time in seconds between processing cycles</p>
                </div>
                <div class="setting-item">
                    <label for="eros_hourly_cap"><a href="#" class="info-icon" title="Maximum API requests per hour for this app" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>API Cap - Hourly:</label>
                    <input type="number" id="eros_hourly_cap" name="hourly_cap" min="1" max="500" value="${settings.hourly_cap !== undefined ? settings.hourly_cap : 20}">
                    <p class="setting-help">Maximum API requests per hour (helps prevent rate limiting)</p>
                    <p class="setting-help" style="color: #cc0000; font-weight: bold;">Setting this too high will risk your accounts being banned! You have been warned!</p>
                </div>
            </div>
            
            <div class="settings-group">
                <h3>Additional Options</h3>
                <div class="setting-item">
                    <label for="eros_monitored_only"><a href="/Huntarr.io/docs/#/configuration?id=monitored-only" class="info-icon" title="Learn more about monitored only option" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Monitored Only:</label>
                    <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                        <input type="checkbox" id="eros_monitored_only" name="monitored_only" ${settings.monitored_only !== false ? 'checked' : ''}>
                        <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                    </label>
                    <p class="setting-help">Only search for monitored items</p>
                </div>
                <div class="setting-item">
                    <label for="eros_skip_future_releases"><a href="https://huntarr.io" class="info-icon" title="Learn more about skipping future releases" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Skip Future Releases:</label>
                    <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                        <input type="checkbox" id="eros_skip_future_releases" name="skip_future_releases" ${settings.skip_future_releases !== false ? 'checked' : ''}>
                        <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                    </label>
                    <p class="setting-help">Skip searching for scenes with future release dates</p>
                </div>
            </div>
        `;

        // Set the content
        container.innerHTML = instancesHtml + searchSettingsHtml;

        // Add event listeners for the instance management
        this.setupInstanceManagement(container, 'eros', settings.instances.length);
        
        // Update duration display
        this.updateDurationDisplay();
    },
    
    // Generate Swaparr settings form
    generateSwaparrForm: function(container, settings = {}) {
        // Add data-app-type attribute to container
        container.setAttribute('data-app-type', 'swaparr');
        
        container.innerHTML = `
            <div class="settings-group">
                <h3>Swaparr (Beta) - Only For Torrent Users</h3>
                <div class="setting-item">
                    <p>Swaparr addresses the issue of stalled downloads and I rewrote it to support Huntarr. Visit Swaparr's <a href="https://github.com/ThijmenGThN/swaparr" target="_blank">GitHub</a> for more information and support the developer!</p>
                </div>
            </div>

            <div class="settings-group">
                <h3>Swaparr Settings</h3>
                <div class="setting-item">
                    <label for="swaparr_enabled"><a href="/Huntarr.io/docs/#/guides/swaparr?id=overview" class="info-icon" title="Learn more about Swaparr's functionality" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Enable Swaparr:</label>
                    <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                        <input type="checkbox" id="swaparr_enabled" ${settings.enabled ? 'checked' : ''}>
                        <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                    </label>
                    <p class="setting-help">Enable automatic handling of stalled downloads</p>
                </div>
                <div class="setting-item">
                    <label for="swaparr_max_strikes"><a href="/Huntarr.io/docs/#/guides/swaparr?id=strike-system" class="info-icon" title="Learn more about strike system for stalled downloads" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Maximum Strikes:</label>
                    <input type="number" id="swaparr_max_strikes" min="1" max="10" value="${settings.max_strikes || 3}">
                    <p class="setting-help">Number of strikes before removing a stalled download</p>
                </div>
                <div class="setting-item">
                    <label for="swaparr_max_download_time"><a href="/Huntarr.io/docs/#/guides/swaparr?id=time-thresholds" class="info-icon" title="Learn more about maximum download time setting" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Max Download Time:</label>
                    <input type="text" id="swaparr_max_download_time" value="${settings.max_download_time || '2h'}">
                    <p class="setting-help">Maximum time a download can be stalled (e.g., 30m, 2h, 1d)</p>
                </div>
                <div class="setting-item">
                    <label for="swaparr_ignore_above_size"><a href="https://huntarr.io" class="info-icon" title="Learn more about size threshold settings" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Ignore Above Size:</label>
                    <input type="text" id="swaparr_ignore_above_size" value="${settings.ignore_above_size || '25GB'}">
                    <p class="setting-help">Ignore files larger than this size (e.g., 1GB, 25GB, 1TB)</p>
                </div>
                <div class="setting-item">
                    <label for="swaparr_remove_from_client"><a href="https://huntarr.io" class="info-icon" title="Learn more about client removal options" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Remove From Client:</label>
                    <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                        <input type="checkbox" id="swaparr_remove_from_client" ${settings.remove_from_client !== false ? 'checked' : ''}>
                        <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                    </label>
                    <p class="setting-help">Remove the download from the torrent/usenet client when removed</p>
                </div>
                <div class="setting-item">
                    <label for="swaparr_dry_run"><a href="https://huntarr.io" class="info-icon" title="Learn more about dry run testing mode" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Dry Run Mode:</label>
                    <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                        <input type="checkbox" id="swaparr_dry_run" ${settings.dry_run === true ? 'checked' : ''}>
                        <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                    </label>
                    <p class="setting-help">Log actions but don't actually remove downloads. Useful for testing the first time!</p>
                </div>
            </div>
            
            <div class="settings-group">
                <h3>Swaparr Status</h3>
                <div id="swaparr_status_container">
                    <div class="button-container" style="display: flex; justify-content: flex-end; margin-bottom: 15px;">
                        <button type="button" id="reset_swaparr_strikes" style="background-color: #e74c3c; color: white; border: none; padding: 5px 10px; border-radius: 4px; font-size: 0.9em; cursor: pointer;">
                            <i class="fas fa-trash"></i> Reset
                        </button>
                    </div>
                    <div id="swaparr_status" class="status-display">
                        <p>Loading Swaparr status...</p>
                    </div>
                </div>
            </div>
        `;
        
        // Load Swaparr status automatically
        const resetStrikesBtn = container.querySelector('#reset_swaparr_strikes');
        const statusContainer = container.querySelector('#swaparr_status');
        
        HuntarrUtils.fetchWithTimeout('/api/swaparr/status')
            .then(response => response.json())
            .then(data => {
                let statusHTML = '';
                
                // Add stats for each app if available
                if (data.statistics && Object.keys(data.statistics).length > 0) {
                    statusHTML += '<ul>';
                    
                    for (const [app, stats] of Object.entries(data.statistics)) {
                        statusHTML += `<li><strong>${app.toUpperCase()}</strong>: `;
                        if (stats.error) {
                            statusHTML += `Error: ${stats.error}</li>`;
                        } else {
                            statusHTML += `${stats.currently_striked} currently striked, ${stats.removed} removed (${stats.total_tracked} total tracked)</li>`;
                        }
                    }
                    
                    statusHTML += '</ul>';
                } else {
                    statusHTML += '<p>No statistics available yet.</p>';
                }
                
                statusContainer.innerHTML = statusHTML;
            })
            .catch(error => {
                console.error('Error loading Swaparr status:', error);
                statusContainer.innerHTML = `<p>Error fetching status: ${error.message}</p>`;
            });
            
        // Add event listener for the Reset Strikes button
        if (resetStrikesBtn) {
            resetStrikesBtn.addEventListener('click', function() {
                if (confirm('Are you sure you want to reset all Swaparr strikes? This will clear the strike history for all apps.')) {
                    statusContainer.innerHTML = '<p>Resetting strikes...</p>';
                    
                    HuntarrUtils.fetchWithTimeout('/api/swaparr/reset', {
                        method: 'POST',
                        headers: {
                            'Content-Type': 'application/json'
                        },
                        body: JSON.stringify({})
                    })
                    .then(response => response.json())
                    .then(data => {
                        if (data.success) {
                            statusContainer.innerHTML = `<p>Success: ${data.message}</p>`;
                            // Reload status after a short delay
                            setTimeout(() => {
                                HuntarrUtils.fetchWithTimeout('/api/swaparr/status')
                                    .then(response => response.json())
                                    .then(data => {
                                        let statusHTML = '';
                                        if (data.statistics && Object.keys(data.statistics).length > 0) {
                                            statusHTML += '<ul>';
                                            for (const [app, stats] of Object.entries(data.statistics)) {
                                                statusHTML += `<li><strong>${app.toUpperCase()}</strong>: `;
                                                if (stats.error) {
                                                    statusHTML += `Error: ${stats.error}</li>`;
                                                } else {
                                                    statusHTML += `${stats.currently_striked} currently striked, ${stats.removed} removed (${stats.total_tracked} total tracked)</li>`;
                                                }
                                            }
                                            statusHTML += '</ul>';
                                        } else {
                                            statusHTML += '<p>No statistics available yet.</p>';
                                        }
                                        statusContainer.innerHTML = statusHTML;
                                    });
                            }, 1000);
                        } else {
                            statusContainer.innerHTML = `<p>Error: ${data.message}</p>`;
                        }
                    })
                    .catch(error => {
                        statusContainer.innerHTML = `<p>Error resetting strikes: ${error.message}</p>`;
                    });
                }
            });
        } else if (!resetStrikesBtn) {
            console.warn('Could not find #reset_swaparr_strikes to attach listener.');
        } else {
             console.warn('huntarrUI or huntarrUI.resetStatefulManagement is not available.');
        }

        // Add confirmation dialog for local access bypass toggle
        const localAccessBypassCheckbox = container.querySelector('#local_access_bypass');
        if (localAccessBypassCheckbox) {
            // Store original state
            const originalState = localAccessBypassCheckbox.checked;
            
            localAccessBypassCheckbox.addEventListener('change', function() {
                const newState = this.checked;
                
                // Preview the UI changes immediately, but they'll be reverted if user doesn't save
                if (typeof huntarrUI !== 'undefined' && typeof huntarrUI.updateUIForLocalAccessBypass === 'function') {
                    huntarrUI.updateUIForLocalAccessBypass(newState);
                }
                // Also ensure the main app knows settings have changed if the preview runs
                if (typeof huntarrUI !== 'undefined' && typeof huntarrUI.markSettingsAsChanged === 'function') {
                     huntarrUI.markSettingsAsChanged();
                }
            });
        }
    },

    // Format date nicely for display
    formatDate: function(date) {
        if (!date) return 'Never';
        
        const options = {
            year: 'numeric',
            month: 'short',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            hour12: true
        };
        
        return date.toLocaleString('en-US', options);
    },
    
    // Get settings from form
    getFormSettings: function(container, appType) {
        let settings = {};
        
        // Helper function to get input value with fallback
        function getInputValue(selector, defaultValue) {
            const element = container.querySelector(selector);
            if (!element) return defaultValue;
            
            if (element.type === 'checkbox') {
                return element.checked;
            } else if (element.type === 'number') {
                const parsedValue = parseInt(element.value);
                return !isNaN(parsedValue) ? parsedValue : defaultValue;
            } else {
                return element.value || defaultValue;
            }
        }
        
        // For the general settings form, collect settings including advanced settings
        if (appType === 'general') {
            console.log('Processing general settings');
            console.log('Container:', container);
            console.log('Container HTML (first 500 chars):', container.innerHTML.substring(0, 500));
            
            // Debug: Check if apprise_urls exists anywhere
            const globalAppriseElement = document.querySelector('#apprise_urls');
            console.log('Global apprise_urls element:', globalAppriseElement);
            
            settings.instances = [];
            settings.check_for_updates = getInputValue('#check_for_updates', true);
            settings.debug_mode = getInputValue('#debug_mode', false);
            settings.display_community_resources = getInputValue('#display_community_resources', true);
            settings.low_usage_mode = getInputValue('#low_usage_mode', false);
            settings.stateful_management_hours = getInputValue('#stateful_management_hours', 168);
            
            // Auth mode handling
            const authModeElement = container.querySelector('#auth_mode');
            if (authModeElement) {
                settings.auth_mode = authModeElement.value;
            }
            
            settings.ssl_verify = getInputValue('#ssl_verify', true);
            settings.api_timeout = getInputValue('#api_timeout', 120);
            settings.command_wait_delay = getInputValue('#command_wait_delay', 1);
            settings.command_wait_attempts = getInputValue('#command_wait_attempts', 600);
            settings.minimum_download_queue_size = getInputValue('#minimum_download_queue_size', -1);
            settings.log_refresh_interval_seconds = getInputValue('#log_refresh_interval_seconds', 30);
            settings.ssl_verify = getInputValue('#ssl_verify', true);
            settings.stateful_management_hours = getInputValue('#stateful_management_hours', 168);
            
            // Notification settings
            settings.enable_notifications = getInputValue('#enable_notifications', false);
            settings.notification_level = container.querySelector('#notification_level')?.value || 'info';
            
            // Process apprise URLs (split by newline)
            const appriseUrlsElement = container.querySelector('#apprise_urls');
            console.log('Container apprise_urls element found:', appriseUrlsElement);
            const appriseUrlsText = appriseUrlsElement?.value || '';
            console.log('Apprise URLs raw text:', appriseUrlsText);
            settings.apprise_urls = appriseUrlsText.split('\n')
                .map(url => url.trim())
                .filter(url => url.length > 0);
            console.log('Apprise URLs processed:', settings.apprise_urls);
                
            settings.notify_on_missing = getInputValue('#notify_on_missing', true);
            settings.notify_on_upgrade = getInputValue('#notify_on_upgrade', true);
            settings.notification_include_instance = getInputValue('#notification_include_instance', true);
            settings.notification_include_app = getInputValue('#notification_include_app', true);
            
            // Handle the auth_mode dropdown
            const authMode = container.querySelector('#auth_mode')?.value || 'login';
            
            // Save the auth_mode value directly
            settings.auth_mode = authMode;
            
            // Set the appropriate flags based on the selected auth mode
            switch (authMode) {
                case 'local_bypass':
                    settings.local_access_bypass = true;
                    settings.proxy_auth_bypass = false;
                    break;
                case 'no_login':
                    settings.local_access_bypass = false;
                    settings.proxy_auth_bypass = true;
                    break;
                case 'login':
                default:
                    settings.local_access_bypass = false;
                    settings.proxy_auth_bypass = false;
                    break;
            }
        }
        
        // For other app types, collect settings
        else {
            // Handle instances differently
            const instances = [];
            // Find instance containers with both old and new class names
            const instanceContainers = container.querySelectorAll('.instance-item, .instance-panel');
            
            // Collect instance data with improved error handling
            instanceContainers.forEach((instance, index) => {
                const nameInput = instance.querySelector('input[name="name"]');
                const urlInput = instance.querySelector('input[name="api_url"]');
                const keyInput = instance.querySelector('input[name="api_key"]');
                const enabledInput = instance.querySelector('input[name="enabled"]');
                
                const name = nameInput ? nameInput.value : null;
                const url = urlInput ? urlInput.value : null;
                const key = keyInput ? keyInput.value : null;
                const enabled = enabledInput ? enabledInput.checked : true; // Default to enabled if checkbox not found
                
                if (!name || !url || !key) {
                    console.warn(`Instance ${index} is missing required fields`);
                }
                
                const instanceObj = {
                    name: name || `Instance ${index + 1}`,
                    api_url: url || "",
                    api_key: key || "",
                    enabled: enabled
                };
                
                instances.push(instanceObj);
            });
            
            // Ensure we always have at least one instance
            if (instances.length === 0) {
                console.warn('No instances found, adding a default empty instance');
                instances.push({
                    name: 'Default',
                    api_url: '',
                    api_key: '',
                    enabled: true
                });
            }
            
            settings.instances = instances;
            
            // Add app-specific settings
            if (appType === 'sonarr') {
                settings.hunt_missing_mode = getInputValue('#sonarr-hunt-missing-mode', 'episodes');
                settings.upgrade_mode = getInputValue('#sonarr-upgrade-mode', 'episodes');
                settings.hunt_missing_items = getInputValue('#sonarr-hunt-missing-items', 1);
                settings.hunt_upgrade_items = getInputValue('#sonarr-hunt-upgrade-items', 0);
                settings.sleep_duration = getInputValue('#sonarr_sleep_duration', 900);
                settings.hourly_cap = getInputValue('#sonarr_hourly_cap', 20);
                settings.monitored_only = getInputValue('#sonarr_monitored_only', true);
                settings.skip_future_episodes = getInputValue('#sonarr_skip_future_episodes', true);

            } 
            else if (appType === 'radarr') {
                settings.hunt_missing_movies = getInputValue('#radarr_hunt_missing_movies', 1);
                settings.hunt_upgrade_movies = getInputValue('#radarr_hunt_upgrade_movies', 0);
                settings.sleep_duration = getInputValue('#radarr_sleep_duration', 900);
                settings.hourly_cap = getInputValue('#radarr_hourly_cap', 20);
                settings.monitored_only = getInputValue('#radarr_monitored_only', true);
                settings.skip_future_releases = getInputValue('#radarr_skip_future_releases', true);

                settings.release_type = getInputValue('#radarr_release_type', 'physical');
            } 
            else if (appType === 'lidarr') {
                settings.hunt_missing_items = getInputValue('#lidarr_hunt_missing_items', 1);
                settings.hunt_upgrade_items = getInputValue('#lidarr_hunt_upgrade_items', 0);
                settings.hunt_missing_mode = getInputValue('#lidarr_hunt_missing_mode', 'artist');
                settings.monitored_only = getInputValue('#lidarr_monitored_only', true);
                settings.sleep_duration = getInputValue('#lidarr_sleep_duration', 900);
                settings.hourly_cap = getInputValue('#lidarr_hourly_cap', 20);
            } 
            else if (appType === 'readarr') {
                settings.hunt_missing_books = getInputValue('#readarr_hunt_missing_books', 1);
                settings.hunt_upgrade_books = getInputValue('#readarr_hunt_upgrade_books', 0);
                settings.monitored_only = getInputValue('#readarr_monitored_only', true);
                settings.skip_future_releases = getInputValue('#readarr_skip_future_releases', true);

                settings.sleep_duration = getInputValue('#readarr_sleep_duration', 900);
                settings.hourly_cap = getInputValue('#readarr_hourly_cap', 20);
            } 
            else if (appType === 'whisparr') {
                settings.hunt_missing_items = getInputValue('#whisparr_hunt_missing_items', 1);
                settings.hunt_upgrade_items = getInputValue('#whisparr_hunt_upgrade_items', 0);
                settings.monitored_only = getInputValue('#whisparr_monitored_only', true);
                settings.whisparr_version = getInputValue('#whisparr-api-version', 'v3');
                settings.skip_future_releases = getInputValue('#whisparr_skip_future_releases', true);

                settings.sleep_duration = getInputValue('#whisparr_sleep_duration', 900);
                settings.hourly_cap = getInputValue('#whisparr_hourly_cap', 20);
            }
            else if (appType === 'eros') {
                settings.search_mode = getInputValue('#eros_search_mode', 'movie');
                settings.hunt_missing_items = getInputValue('#eros_hunt_missing_items', 1);
                settings.hunt_upgrade_items = getInputValue('#eros_hunt_upgrade_items', 0);
                settings.monitored_only = getInputValue('#eros_monitored_only', true);
                settings.skip_future_releases = getInputValue('#eros_skip_future_releases', true);

                settings.sleep_duration = getInputValue('#eros_sleep_duration', 900);
                settings.hourly_cap = getInputValue('#eros_hourly_cap', 20);
            }
            else if (appType === 'swaparr') {
                settings.enabled = getInputValue('#swaparr_enabled', false);
                settings.max_strikes = getInputValue('#swaparr_max_strikes', 3);
                settings.max_download_time = getInputValue('#swaparr_max_download_time', '2h');
                settings.ignore_above_size = getInputValue('#swaparr_ignore_above_size', '25GB');
                settings.remove_from_client = getInputValue('#swaparr_remove_from_client', true);
                settings.dry_run = getInputValue('#swaparr_dry_run', false);
            }
        }
        
        console.log('Collected settings for', appType, settings);
        return settings;
    },
    
    // Generate General settings form
    generateGeneralForm: function(container, settings = {}) {
        // Add data-app-type attribute to container
        container.setAttribute('data-app-type', 'general');
        
        container.innerHTML = `
            <div class="settings-group">
                <h3>System Settings</h3>
                <div class="setting-item">
                    <label for="check_for_updates"><a href="https://plexguide.github.io/Huntarr.io/settings/settings.html#check-for-updates" class="info-icon" title="Learn more about update checking" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Check for Updates:</label>
                    <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                        <input type="checkbox" id="check_for_updates" ${settings.check_for_updates !== false ? 'checked' : ''}>
                        <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                    </label>
                    <p class="setting-help" style="margin-left: -3ch !important;">Automatically check for Huntarr updates</p>
                </div>
                <div class="setting-item">
                    <label for="debug_mode"><a href="https://plexguide.github.io/Huntarr.io/settings/settings.html#debug-mode" class="info-icon" title="Learn more about debug mode" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Debug Mode:</label>
                    <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                        <input type="checkbox" id="debug_mode" ${settings.debug_mode === true ? 'checked' : ''}>
                        <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                    </label>
                    <p class="setting-help" style="margin-left: -3ch !important;">Enable verbose logging for troubleshooting (applies to all apps)</p>
                </div>
                <div class="setting-item">
                    <label for="display_community_resources"><a href="https://plexguide.github.io/Huntarr.io/settings/settings.html#display-resources" class="info-icon" title="Learn more about resources display options" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Display Resources:</label>
                    <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                        <input type="checkbox" id="display_community_resources" ${settings.display_community_resources !== false ? 'checked' : ''}>
                        <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                    </label>
                    <p class="setting-help" style="margin-left: -3ch !important;">Show or hide the Resources section on the home page</p>
                </div>
                <div class="setting-item">
                    <label for="low_usage_mode"><a href="#" class="info-icon" title="Learn more about Low Usage Mode" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Low Usage Mode:</label>
                    <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                        <input type="checkbox" id="low_usage_mode" ${settings.low_usage_mode === true ? 'checked' : ''}>
                        <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                    </label>
                    <p class="setting-help" style="margin-left: -3ch !important;">Disables animations to reduce CPU/GPU usage on older devices</p>
                </div>

            </div>
            
            <div class="settings-group">
                <div class="stateful-header-row">
                    <h3>Stateful Management</h3>
                    <!-- Original reset button removed, now using emergency button -->
                </div>
                <div id="stateful-section" class="setting-info-block">
                    <div id="stateful-notification" class="notification error" style="display: none;">
                        Failed to load stateful management info. Check logs for details.
                    </div>
                    <div class="info-container">
                        <div class="date-info-block">
                            <div class="date-label">Initial State Created:</div>
                            <div id="stateful_initial_state" class="date-value">Loading...</div>
                        </div>
                        <div class="date-info-block">
                            <div class="date-label">State Reset Date:</div>
                            <div id="stateful_expires_date" class="date-value">Loading...</div>
                        </div>
                    </div>
                </div>
                <div class="setting-item">
                    <label for="stateful_management_hours"><a href="https://plexguide.github.io/Huntarr.io/settings/settings.html#stateful-management" class="info-icon" title="Learn more about state reset intervals" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>State Reset (Hours):</label>
                    <input type="number" id="stateful_management_hours" min="1" value="${settings.stateful_management_hours || 168}" style="width: 50% !important; max-width: 200px !important; box-sizing: border-box !important; margin: 0 !important; padding: 8px 12px !important; border-radius: 4px !important; display: block !important; text-align: left !important;">
                    <p class="setting-help" style="margin-left: -3ch !important;">Hours before resetting processed media state (<span id="stateful_management_days">${((settings.stateful_management_hours || 168) / 24).toFixed(1)} days</span>)</p>
                    <p class="setting-help reset-help" style="margin-left: -3ch !important;">Reset clears all processed media IDs to allow reprocessing</p>
                </div>
            </div>
            
            <div class="settings-group">
                <h3>Security</h3>
                <div class="setting-item">
                    <label for="auth_mode"><a href="https://plexguide.github.io/Huntarr.io/settings/settings.html#authentication-mode" class="info-icon" title="Learn more about authentication modes" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Authentication Mode:</label>
                    <select id="auth_mode" name="auth_mode" style="width: 300px; padding: 8px 12px; border-radius: 6px; cursor: pointer; border: 1px solid rgba(255, 255, 255, 0.1); background-color: #1f2937; color: #d1d5db;">
                        <option value="login" ${(settings.auth_mode === 'login' || (!settings.auth_mode && !settings.local_access_bypass && !settings.proxy_auth_bypass)) ? 'selected' : ''}>Login Mode</option>
                        <option value="local_bypass" ${(settings.auth_mode === 'local_bypass' || (!settings.auth_mode && settings.local_access_bypass === true && !settings.proxy_auth_bypass)) ? 'selected' : ''}>Local Bypass Mode</option>
                        <option value="no_login" ${(settings.auth_mode === 'no_login' || (!settings.auth_mode && settings.proxy_auth_bypass === true)) ? 'selected' : ''}>No Login Mode</option>
                    </select>
                    <p class="setting-help" style="margin-left: -3ch !important;">
                        <strong>Login Mode:</strong> Standard login required for all connections<br>
                        <strong>Local Bypass Mode:</strong> Only local network connections (192.168.x.x, 10.x.x.x) bypass login<br>
                        <strong>No Login Mode:</strong> Completely disable authentication
                    </p>
                    <p class="setting-help warning" style="color: #ff6b6b; margin-left: -3ch !important;"><strong>Warning:</strong> Only use No Login Mode if your reverse proxy (e.g., Cloudflare, Nginx) is properly securing access!</p>
                </div>
                <div class="setting-item">
                    <label for="ssl_verify"><a href="https://plexguide.github.io/Huntarr.io/settings/settings.html#enable-ssl-verify" class="info-icon" title="Learn more about SSL verification" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Enable SSL Verify:</label>
                    <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                        <input type="checkbox" id="ssl_verify" ${settings.ssl_verify === true ? 'checked' : ''}>
                        <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                    </label>
                    <p class="setting-help" style="margin-left: -3ch !important;">Disable SSL certificate verification when using self-signed certificates in private networks.</p>
                </div>
            </div>
            
            <div class="settings-group">
                <h3>Advanced Settings</h3>
                <div class="setting-item">
                    <label for="api_timeout"><a href="https://plexguide.github.io/Huntarr.io/settings/settings.html#api-timeout" class="info-icon" title="Learn more about API timeout settings" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>API Timeout:</label>
                    <input type="number" id="api_timeout" min="10" value="${settings.api_timeout !== undefined ? settings.api_timeout : 120}">
                    <p class="setting-help" style="margin-left: -3ch !important;">API request timeout in seconds</p>
                </div>
                <div class="setting-item">
                    <label for="command_wait_delay"><a href="https://plexguide.github.io/Huntarr.io/settings/settings.html#command-wait-delay" class="info-icon" title="Learn more about command wait settings" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Command Wait Delay:</label>
                    <input type="number" id="command_wait_delay" min="1" value="${settings.command_wait_delay !== undefined ? settings.command_wait_delay : 1}">
                    <p class="setting-help" style="margin-left: -3ch !important;">Delay between command status checks in seconds</p>
                </div>
                <div class="setting-item">
                    <label for="command_wait_attempts"><a href="https://plexguide.github.io/Huntarr.io/settings/settings.html#cmd-wait-attempts" class="info-icon" title="Learn more about command wait settings" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>CMD Wait Attempts:</label>
                    <input type="number" id="command_wait_attempts" min="1" value="${settings.command_wait_attempts !== undefined ? settings.command_wait_attempts : 600}">
                    <p class="setting-help" style="margin-left: -3ch !important;">Maximum number of attempts to check command status</p>
                </div>
                <div class="setting-item">
                    <label for="minimum_download_queue_size"><a href="https://plexguide.github.io/Huntarr.io/settings/settings.html#max-dl-queue-size" class="info-icon" title="Learn more about download queue management" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Max DL Queue Size:</label>
                    <input type="number" id="minimum_download_queue_size" min="-1" value="${settings.minimum_download_queue_size !== undefined ? settings.minimum_download_queue_size : -1}">
                    <p class="setting-help" style="margin-left: -3ch !important;">If the current download queue for an app instance exceeds this value, downloads will be skipped until the queue reduces. Set to -1 to disable this limit.</span>
                </div>
                <div class="setting-item">
                    <label for="log_refresh_interval_seconds"><a href="https://plexguide.github.io/Huntarr.io/settings/settings.html#log-refresh-interval" class="info-icon" title="Learn more about log settings" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Log Refresh Interval:</label>
                    <input type="number" id="log_refresh_interval_seconds" min="5" value="${settings.log_refresh_interval_seconds !== undefined ? settings.log_refresh_interval_seconds : 30}">
                    <p class="setting-help" style="margin-left: -3ch !important;">How often Huntarr refreshes logs from apps (seconds)</p>
                </div>
                <div class="setting-item">
                    <label for="base_url"><a href="https://plexguide.github.io/Huntarr.io/settings/settings.html#base-url" class="info-icon" title="Learn more about reverse proxy base URL settings" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Base URL:</label>
                    <input type="text" id="base_url" value="${settings.base_url || ''}" placeholder="/huntarr">
                    <p class="setting-help" style="margin-left: -3ch !important;">Base URL path for reverse proxy (e.g., '/huntarr'). Leave empty for root path. Requires restart. Credit <a href="https://github.com/scr4tchy" target="_blank">scr4tchy</a>.</p>
                </div>
            </div>

            <div class="settings-group">
                <h3>Apprise Notifications</h3>
                <div class="setting-item">
                    <label for="enable_notifications"><a href="https://plexguide.github.io/Huntarr.io/settings/settings.html#enable-notifications" class="info-icon" title="Enable or disable notifications" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Enable Notifications:</label>
                    <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                        <input type="checkbox" id="enable_notifications" ${settings.enable_notifications === true ? 'checked' : ''}>
                        <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                    </label>
                    <p class="setting-help" style="margin-left: -3ch !important;">Enable sending notifications via Apprise for media processing events</p>
                </div>
                <div class="setting-item">
                    <label for="notification_level"><a href="https://plexguide.github.io/Huntarr.io/settings/settings.html#notification-level" class="info-icon" title="Set minimum notification level" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Notification Level:</label>
                    <select id="notification_level" name="notification_level" style="width: 200px; padding: 8px 12px; border-radius: 6px; cursor: pointer; border: 1px solid rgba(255, 255, 255, 0.1); background-color: #1f2937; color: #d1d5db;">
                        <option value="info" ${settings.notification_level === 'info' || !settings.notification_level ? 'selected' : ''}>Info</option>
                        <option value="success" ${settings.notification_level === 'success' ? 'selected' : ''}>Success</option>
                        <option value="warning" ${settings.notification_level === 'warning' ? 'selected' : ''}>Warning</option>
                        <option value="error" ${settings.notification_level === 'error' ? 'selected' : ''}>Error</option>
                    </select>
                    <p class="setting-help" style="margin-left: -3ch !important;">Minimum level of events that will trigger notifications</p>
                </div>
                <div class="setting-item">
                    <label for="apprise_urls"><a href="https://plexguide.github.io/Huntarr.io/settings/settings.html#apprise-urls" class="info-icon" title="Learn about Apprise URL formats" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Apprise URLs:</label>
                    <textarea id="apprise_urls" rows="4" style="width: 100%; padding: 8px 12px; border-radius: 6px; border: 1px solid rgba(255, 255, 255, 0.1); background-color: #1f2937; color: #d1d5db;">${(settings.apprise_urls || []).join('\n')}</textarea>
                    <p class="setting-help" style="margin-left: -3ch !important;">Enter one Apprise URL per line (e.g., discord://, telegram://, etc)</p>
                    <p class="setting-help"><a href="https://plexguide.github.io/Huntarr.io/settings/settings.html#apprise-urls" target="_blank">Click here for detailed Apprise URL documentation</a></p>
                    <div style="margin-top: 10px;">
                        <button type="button" id="testNotificationBtn" class="btn btn-secondary" style="background-color: #6366f1; color: white; border: none; padding: 8px 16px; border-radius: 6px; cursor: pointer; font-size: 14px;">
                            <i class="fas fa-bell"></i> Test Notification
                        </button>
                        <span id="testNotificationStatus" style="margin-left: 10px; font-size: 14px;"></span>
                    </div>
                </div>
                <div class="setting-item">
                    <label for="notify_on_missing"><a href="https://plexguide.github.io/Huntarr.io/settings/settings.html#notify-on-missing" class="info-icon" title="Send notifications for missing media" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Notify on Missing:</label>
                    <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                        <input type="checkbox" id="notify_on_missing" ${settings.notify_on_missing !== false ? 'checked' : ''}>
                        <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                    </label>
                    <p class="setting-help" style="margin-left: -3ch !important;">Send notifications when missing media is processed</p>
                </div>
                <div class="setting-item">
                    <label for="notify_on_upgrade"><a href="https://plexguide.github.io/Huntarr.io/settings/settings.html#notify-on-upgrade" class="info-icon" title="Learn more about upgrade notifications" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Notify on Upgrade:</label>
                    <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                        <input type="checkbox" id="notify_on_upgrade" ${settings.notify_on_upgrade !== false ? 'checked' : ''}>
                        <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                    </label>
                    <p class="setting-help" style="margin-left: -3ch !important;">Send notifications when media is upgraded</p>
                </div>
                <div class="setting-item">
                    <label for="notification_include_instance"><a href="https://plexguide.github.io/Huntarr.io/settings/settings.html#include-instance" class="info-icon" title="Include instance name in notifications" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Include Instance:</label>
                    <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                        <input type="checkbox" id="notification_include_instance" ${settings.notification_include_instance !== false ? 'checked' : ''}>
                        <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                    </label>
                    <p class="setting-help" style="margin-left: -3ch !important;">Include instance name in notification messages</p>
                </div>
                <div class="setting-item">
                    <label for="notification_include_app"><a href="https://plexguide.github.io/Huntarr.io/settings/settings.html#include-app-name" class="info-icon" title="Include app name in notifications" target="_blank" rel="noopener"><i class="fas fa-info-circle"></i></a>Include App Name:</label>
                    <label class="toggle-switch" style="width:40px; height:20px; display:inline-block; position:relative;">
                        <input type="checkbox" id="notification_include_app" ${settings.notification_include_app !== false ? 'checked' : ''}>
                        <span class="toggle-slider" style="position:absolute; cursor:pointer; top:0; left:0; right:0; bottom:0; background-color:#3d4353; border-radius:20px; transition:0.4s;"></span>
                    </label>
                    <p class="setting-help" style="margin-left: -3ch !important;">Include app name (Sonarr, Radarr, etc.) in notification messages</p>
                </div>
            </div>
        `;
        
        // Get hours input and days span elements once
        const statefulHoursInput = container.querySelector('#stateful_management_hours');
        const statefulDaysSpan = container.querySelector('#stateful_management_days');
        
        if (statefulHoursInput && statefulDaysSpan) {
            statefulHoursInput.addEventListener('input', function() {
                const hours = parseInt(this.value);
                const days = (hours / 24).toFixed(1);
                statefulDaysSpan.textContent = `${days} days`;
            });
        }
        
        // Load stateful management info
        const createdDateEl = document.getElementById('stateful_initial_state');
        const expiresDateEl = document.getElementById('stateful_expires_date');

        // Skip loading if huntarrUI has already loaded this data to prevent flashing
        if (window.huntarrUI && window.huntarrUI._cachedStatefulData) {
            console.log('[SettingsForms] Using existing huntarrUI cached stateful data');
            return; // Exit early - main.js already has this covered
        }
        
        // Only set to Loading if not already populated
        if (createdDateEl && (!createdDateEl.textContent || createdDateEl.textContent === 'N/A')) {
            createdDateEl.textContent = 'Loading...';
        }
        if (expiresDateEl && (!expiresDateEl.textContent || expiresDateEl.textContent === 'N/A')) {
            expiresDateEl.textContent = 'Loading...';
        }

        // Check if data is already cached in localStorage
        const cachedStatefulData = localStorage.getItem('huntarr-stateful-data');
        if (cachedStatefulData) {
            try {
                const parsedData = JSON.parse(cachedStatefulData);
                const cacheAge = Date.now() - parsedData.timestamp;
                
                // Use cache if it's less than 5 minutes old
                if (cacheAge < 300000) {
                    console.log('[SettingsForms] Using cached stateful data');
                    
                    if (createdDateEl && parsedData.created_at_ts) {
                        const createdDate = new Date(parsedData.created_at_ts * 1000);
                        createdDateEl.textContent = this.formatDate(createdDate);
                    }
                    
                    if (expiresDateEl && parsedData.expires_at_ts) {
                        const expiresDate = new Date(parsedData.expires_at_ts * 1000);
                        expiresDateEl.textContent = this.formatDate(expiresDate);
                    }
                    
                    // Still fetch fresh data in the background, but don't update UI
                    fetchStatefulInfoSilently();
                    return;
                }
            } catch (e) {
                console.warn('[SettingsForms] Error parsing cached stateful data:', e);
            }
        }

        HuntarrUtils.fetchWithTimeout('/api/stateful/info', {
            cache: 'no-cache',
            headers: {
                'Cache-Control': 'no-cache, no-store, must-revalidate',
                'Pragma': 'no-cache',
                'Expires': '0'
            }
        })
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! Status: ${response.status}`);
                }
                return response.json();
             })
            .then(data => {
                // Cache the response with a timestamp for future use
                localStorage.setItem('huntarr-stateful-data', JSON.stringify({
                    ...data,
                    timestamp: Date.now()
                }));
                
                if (createdDateEl) {
                    if (data.created_at_ts) {
                        const createdDate = new Date(data.created_at_ts * 1000);
                        createdDateEl.textContent = this.formatDate(createdDate);
                    } else {
                        createdDateEl.textContent = 'Not yet created';
                    }
                }
                
                if (expiresDateEl) {
                    if (data.expires_at_ts) {
                        const expiresDate = new Date(data.expires_at_ts * 1000);
                        expiresDateEl.textContent = this.formatDate(expiresDate);
                    } else {
                        expiresDateEl.textContent = 'Not set';
                    }
                }
                
                // Store data for other components to use
                if (window.huntarrUI) {
                    window.huntarrUI._cachedStatefulData = data;
                }
            })
            .catch(error => {
                console.error('Error loading stateful info:', error);
                
                // Try using cached data as fallback
                if (cachedStatefulData) {
                    try {
                        const parsedData = JSON.parse(cachedStatefulData);
                        
                        if (createdDateEl && parsedData.created_at_ts) {
                            const createdDate = new Date(parsedData.created_at_ts * 1000);
                            createdDateEl.textContent = this.formatDate(createdDate) + ' (cached)';
                        } else if (createdDateEl) {
                            createdDateEl.textContent = 'Not available';
                        }
                        
                        if (expiresDateEl && parsedData.expires_at_ts) {
                            const expiresDate = new Date(parsedData.expires_at_ts * 1000);
                            expiresDateEl.textContent = this.formatDate(expiresDate) + ' (cached)';
                        } else if (expiresDateEl) {
                            expiresDateEl.textContent = 'Not available';
                        }
                    } catch (e) {
                        if (createdDateEl) createdDateEl.textContent = 'Not available';
                        if (expiresDateEl) expiresDateEl.textContent = 'Not available';
                    }
                } else {
                    if (createdDateEl) createdDateEl.textContent = 'Not available';
                    if (expiresDateEl) expiresDateEl.textContent = 'Not available';
                }
            });
            
        // Helper function to fetch data silently without updating UI
        function fetchStatefulInfoSilently() {
            HuntarrUtils.fetchWithTimeout('/api/stateful/info', {
                cache: 'no-cache',
                headers: {
                    'Cache-Control': 'no-cache, no-store, must-revalidate',
                    'Pragma': 'no-cache',
                    'Expires': '0'
                }
            })
                .then(response => response.ok ? response.json() : null)
                .then(data => {
                    if (data && data.success) {
                        localStorage.setItem('huntarr-stateful-data', JSON.stringify({
                            ...data,
                            timestamp: Date.now()
                        }));
                        
                        if (window.huntarrUI) {
                            window.huntarrUI._cachedStatefulData = data;
                        }
                    }
                })
                .catch(error => console.warn('Silent stateful info fetch failed:', error));
        }
    },
    
    // Update duration display - e.g., convert seconds to hours
    updateDurationDisplay: function() {
        // Function to update a specific sleep duration display
        const updateSleepDisplay = function(inputId, spanId) {
            const input = document.getElementById(inputId);
            const span = document.getElementById(spanId);
            if (!input || !span) return;
            
            const seconds = parseInt(input.value);
            if (isNaN(seconds)) return;
            
            const hours = (seconds / 3600).toFixed(1);
            if (hours < 1) {
                const minutes = Math.round(seconds / 60);
                span.textContent = `${minutes} minutes`;
            } else {
                span.textContent = `${hours} hours`;
            }
        };

        // Update for each app
        updateSleepDisplay('sleep_duration', 'sleep_duration_hours');
        updateSleepDisplay('radarr_sleep_duration', 'radarr_sleep_duration_hours');
        updateSleepDisplay('lidarr_sleep_duration', 'lidarr_sleep_duration_hours');
        updateSleepDisplay('readarr_sleep_duration', 'readarr_sleep_duration_hours');
        updateSleepDisplay('whisparr_sleep_duration', 'whisparr_sleep_duration_hours'); // Added Whisparr
    },
    
    // Setup instance management - test connection buttons and add/remove instance buttons
    setupInstanceManagement: function(container, appType, initialCount) {
        console.log(`Setting up instance management for ${appType} with ${initialCount} instances`);
        
        // Make sure container has the app type set
        const form = container.closest('.settings-form');
        if (form && !form.hasAttribute('data-app-type')) {
            form.setAttribute('data-app-type', appType);
        }
        
        // Add listeners for test connection buttons
        const testButtons = container.querySelectorAll('.test-connection-btn');
        testButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                // Prevent any default form submission
                e.preventDefault();
                
                console.log('Test connection button clicked');
                
                // Get the instance panel containing this button - look for both old and new class names
                const instancePanel = button.closest('.instance-item') || button.closest('.instance-panel');
                if (!instancePanel) {
                    console.error('Could not find instance panel for test button', button);
                    alert('Error: Could not find instance panel');
                    return;
                }
                
                // Get the URL and API key inputs directly within this instance panel
                const urlInput = instancePanel.querySelector('input[name="api_url"]');
                const keyInput = instancePanel.querySelector('input[name="api_key"]');
                
                console.log('Found inputs:', urlInput, keyInput);
                
                if (!urlInput || !keyInput) {
                    console.error('Could not find URL or API key inputs in panel', instancePanel);
                    alert('Error: Could not find URL or API key inputs');
                    return;
                }
                
                const url = urlInput.value.trim();
                const apiKey = keyInput.value.trim();
                
                console.log(`Testing connection for ${appType} - URL: ${url}, API Key: ${apiKey.substring(0, 5)}...`);
                
                if (!url) {
                    alert('Please enter a valid URL');
                    urlInput.focus();
                    return;
                }
                
                if (!apiKey) {
                    alert('Please enter a valid API key');
                    keyInput.focus();
                    return;
                }
                
                // Show testing status
                const originalButtonHTML = button.innerHTML;
                button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing...';
                button.disabled = true;
                
                // Make the API request
                HuntarrUtils.fetchWithTimeout(`/api/${appType}/test-connection`, {
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
                        throw new Error(`HTTP error ${response.status}: ${response.statusText}`);
                    }
                    return response.json();
                })
                .then(data => {
                    console.log(`Test connection response:`, data);
                    
                    // Reset button
                    button.disabled = false;
                    
                    if (data.success) {
                        // Success
                        button.innerHTML = '<i class="fas fa-check"></i> Connected!';
                        button.classList.add('test-success');
                        
                        let successMessage = `Successfully connected to ${appType.charAt(0).toUpperCase() + appType.slice(1)}`;
                        if (data.version) {
                            successMessage += ` (version ${data.version})`;
                        }
                        
                        // Alert the user of success
                        alert(successMessage);
                        
                        // Reset button after delay
                        setTimeout(() => {
                            button.innerHTML = originalButtonHTML;
                            button.classList.remove('test-success');
                        }, 3000);
                    } else {
                        // Failure
                        button.innerHTML = '<i class="fas fa-times"></i> Failed';
                        button.classList.add('test-failed');
                        
                        alert(`Connection failed: ${data.message || 'Unknown error'}`);
                        
                        setTimeout(() => {
                            button.innerHTML = originalButtonHTML;
                            button.classList.remove('test-failed');
                        }, 3000);
                    }
                })
                .catch(error => {
                    console.error(`Test connection error:`, error);
                    
                    button.disabled = false;
                    button.innerHTML = '<i class="fas fa-times"></i> Error';
                    button.classList.add('test-failed');
                    
                    alert(`Connection test failed: ${error.message}`);
                    
                    setTimeout(() => {
                        button.innerHTML = originalButtonHTML;
                        button.classList.remove('test-failed');
                    }, 3000);
                });
            });
        });
        
        // Add a button to add new instances (limit to 9 total)
        const addBtn = container.querySelector(`.add-${appType}-instance-btn`);
        if (addBtn) {
            // Function to update the button text with current instance count
            const updateAddButtonText = () => {
                const instancesContainer = container.querySelector('.instances-container');
                if (!instancesContainer) return;
                const currentCount = instancesContainer.querySelectorAll('.instance-item').length;
                addBtn.innerHTML = `<i class="fas fa-plus"></i> Add ${appType.charAt(0).toUpperCase() + appType.slice(1)} Instance (${currentCount}/9)`;
                
                // Disable button if we've reached the maximum
                if (currentCount >= 9) {
                    addBtn.disabled = true;
                    addBtn.title = "Maximum number of instances reached";
                } else {
                    addBtn.disabled = false;
                    addBtn.title = "";
                }
            };
            
            // Initialize button text
            updateAddButtonText();
            
            addBtn.addEventListener('click', function() {
                const instancesContainer = container.querySelector('.instances-container');
                if (!instancesContainer) return;
                
                // Count current instances
                const currentCount = instancesContainer.querySelectorAll('.instance-item').length;
                
                // Don't add more if we have 9 already
                if (currentCount >= 9) {
                    alert("Maximum of 9 instances allowed");
                    return;
                }
                
                // Create new instance div
                const newInstanceDiv = document.createElement('div');
                newInstanceDiv.className = 'instance-item'; // Use instance-item
                newInstanceDiv.dataset.instanceId = currentCount;
                
                // Set content for the new instance using the updated structure
                newInstanceDiv.innerHTML = `
                    <div class="instance-header">
                        <h4>Instance ${currentCount + 1}: Instance ${currentCount + 1}</h4>
                        <div class="instance-actions">
                             <button type="button" class="remove-instance-btn">Remove</button>
                             <button type="button" class="test-connection-btn" data-instance="${currentCount}" style="margin-left: 10px;">
                                <i class="fas fa-plug"></i> Test Connection
                            </button>
                        </div>
                    </div>
                    <div class="instance-content">
                        <div class="setting-item">
                            <label for="${appType}-name-${currentCount}">Name:</label>
                            <input type="text" id="${appType}-name-${currentCount}" name="name" value="Instance ${currentCount + 1}" placeholder="Friendly name for this instance">
                            <p class="setting-help">Friendly name for this ${appType} instance</p>
                        </div>
                        <div class="setting-item">
                            <label for="${appType}-url-${currentCount}">URL:</label>
                            <input type="text" id="${appType}-url-${currentCount}" name="api_url" value="" placeholder="Base URL (e.g., http://localhost:8989)">
                             <p class="setting-help">Base URL for ${appType} (e.g., http://localhost:8989)</p>
                        </div>
                        <div class="setting-item">
                            <label for="${appType}-key-${currentCount}">API Key:</label>
                            <input type="text" id="${appType}-key-${currentCount}" name="api_key" value="" placeholder="API key">
                             <p class="setting-help">API key for ${appType}</p>
                        </div>
                        <div class="setting-item">
                            <label for="${appType}-enabled-${currentCount}">Enabled:</label>
                            <label class="toggle-switch">
                                <input type="checkbox" id="${appType}-enabled-${currentCount}" name="enabled" checked>
                                <span class="toggle-slider"></span>
                            </label>
                        </div>
                    </div>
                `;
                
                // Add the new instance to the container
                instancesContainer.appendChild(newInstanceDiv);
                
                // Update the button text with new count
                updateAddButtonText();
                
                // Add event listener for the remove button
                const removeBtn = newInstanceDiv.querySelector('.remove-instance-btn');
                if (removeBtn) {
                    removeBtn.addEventListener('click', function() {
                        instancesContainer.removeChild(newInstanceDiv);
                        
                        // Update the add button text after removing
                        updateAddButtonText();
                        
                        // Trigger change event to update save button state
                        const changeEvent = new Event('change');
                        container.dispatchEvent(changeEvent);
                    });
                }
                
                // Add event listener for test connection button
                const testBtn = newInstanceDiv.querySelector('.test-connection-btn');
                if (testBtn) {
                    testBtn.addEventListener('click', function() {
                        // Get the URL and API key inputs from the parent instance item
                        const instanceContainer = testBtn.closest('.instance-item') || testBtn.closest('.instance-panel');
                        if (!instanceContainer) {
                            alert('Error: Could not find instance container');
                            return;
                        }
                        
                        const urlInput = instanceContainer.querySelector('input[name="api_url"]');
                        const keyInput = instanceContainer.querySelector('input[name="api_key"]');
                        
                        if (!urlInput || !keyInput) {
                            alert('Error: Could not find URL or API key inputs');
                            return;
                        }
                        
                        const url = urlInput.value.trim();
                        const apiKey = keyInput.value.trim();
                        
                        if (!url) {
                            alert('Please enter a valid URL');
                            urlInput.focus();
                            return;
                        }
                        
                        if (!apiKey) {
                            alert('Please enter a valid API key');
                            keyInput.focus();
                            return;
                        }
                        
                        // Call the test connection function
                        SettingsForms.testConnection(appType, url, apiKey, testBtn);
                    });
                }
                
                // Trigger change event to update save button state
                const changeEvent = new Event('change');
                container.dispatchEvent(changeEvent);
            });
        }
        
        // Set up remove buttons for existing instances
        const removeButtons = container.querySelectorAll('.remove-instance-btn');
        removeButtons.forEach(btn => {
            btn.addEventListener('click', function() {
                const instancePanel = btn.closest('.instance-item') || btn.closest('.instance-panel');
                if (instancePanel && instancePanel.parentNode) {
                    instancePanel.parentNode.removeChild(instancePanel);
                    
                    // Update the button text with new count if updateAddButtonText exists
                    if (typeof updateAddButtonText === 'function') {
                        updateAddButtonText();
                    }
                    
                    // Trigger change event to update save button state
                    const changeEvent = new Event('change');
                    container.dispatchEvent(changeEvent);
                }
            });
        });
    },
    
    // Test connection to an *arr API
    testConnection: function(app, url, apiKey, buttonElement) {
        // Temporarily suppress change detection to prevent the unsaved changes dialog
        if (window.huntarrUI && window.huntarrUI.suppressUnsavedChangesCheck) {
            window.huntarrUI.suppressUnsavedChangesCheck = true;
        }
        
        // Also set a global flag used by the apps module
        window._suppressUnsavedChangesDialog = true;
        
        // Find or create a status message element next to the button
        let statusElement = buttonElement.closest('.instance-actions').querySelector('.connection-message');
        if (!statusElement) {
            statusElement = document.createElement('span');
            statusElement.className = 'connection-message';
            statusElement.style.marginLeft = '10px';
            statusElement.style.fontWeight = 'bold';
            buttonElement.closest('.instance-actions').insertBefore(statusElement, buttonElement);
        }
        
        // Show testing status
        const originalButtonHTML = buttonElement.innerHTML;
        buttonElement.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Testing...';
        buttonElement.disabled = true;
        statusElement.textContent = 'Testing connection...';
        statusElement.style.color = '#888';
        
        console.log(`Testing connection for ${app} - URL: ${url}, API Key: ${apiKey.substring(0, 5)}...`);
        
        if (!url) {
            statusElement.textContent = 'Please enter a valid URL';
            statusElement.style.color = 'red';
            buttonElement.innerHTML = originalButtonHTML;
            buttonElement.disabled = false;
            // Reset suppression flags
            this._resetSuppressionFlags();
            return;
        }
        
        if (!apiKey) {
            statusElement.textContent = 'Please enter a valid API key';
            statusElement.style.color = 'red';
            buttonElement.innerHTML = originalButtonHTML;
            buttonElement.disabled = false;
            // Reset suppression flags
            this._resetSuppressionFlags();
            return;
        }
        
        // Make the API request
        HuntarrUtils.fetchWithTimeout(`/api/${app}/test-connection`, {
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
                throw new Error(`HTTP error ${response.status}: ${response.statusText}`);
            }
            return response.json();
        })
        .then(data => {
            console.log(`Test connection response:`, data);
            
            // Reset button
            buttonElement.disabled = false;
            
            if (data.success) {
                // Success
                buttonElement.innerHTML = '<i class="fas fa-plug"></i> Test Connection';
                
                let successMessage = `Connected successfully`;
                if (data.version) {
                    successMessage += ` (v${data.version})`;
                }
                
                // Show success message
                statusElement.textContent = successMessage;
                statusElement.style.color = 'green';
            } else {
                // Failure
                buttonElement.innerHTML = '<i class="fas fa-plug"></i> Test Connection';
                
                // Show error message
                const errorMsg = data.message || 'Connection failed';
                statusElement.textContent = errorMsg;
                statusElement.style.color = 'red';
            }
            
            // Reset suppression flags after a short delay to handle any potential redirects
            setTimeout(() => {
                this._resetSuppressionFlags();
            }, 500);
        })
        .catch(error => {
            console.error(`Connection test error:`, error);
            
            // Reset button
            buttonElement.innerHTML = originalButtonHTML;
            buttonElement.disabled = false;
            
            // Show error message
            statusElement.textContent = `Error: ${error.message}`;
            statusElement.style.color = 'red';
            
            // Reset suppression flags
            this._resetSuppressionFlags();
        });
    },
    
    // Helper method to reset unsaved changes suppression flags
    _resetSuppressionFlags: function() {
        // Reset all suppression flags
        if (window.huntarrUI) {
            window.huntarrUI.suppressUnsavedChangesCheck = false;
        }
        window._suppressUnsavedChangesDialog = false;
    },
};

// Add CSS for toggle circle
const styleEl = document.createElement('style');
styleEl.innerHTML = `
    .toggle-switch input:checked + .toggle-slider {
        background-color: #3498db !important;
    }
    .toggle-slider:before {
        position: absolute;
        content: "";
        height: 14px;
        width: 14px;
        left: 3px;
        bottom: 3px;
        background-color: white;
        transition: .4s;
        border-radius: 50%;
    }
    .toggle-switch input:checked + .toggle-slider:before {
        transform: translateX(20px);
    }
    
    /* Align setting help text 3 characters to the left */
    .setting-help {
        margin-left: -3ch !important;
    }
`;
document.head.appendChild(styleEl);
