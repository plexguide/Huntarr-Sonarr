"""
Readarr module initialization
"""

# Use src.primary imports
from src.primary.apps.readarr.missing import process_missing_books
from src.primary.apps.readarr.upgrade import process_cutoff_upgrades
# Add necessary imports
from src.primary.settings_manager import load_settings
from src.primary.utils.logger import get_logger

# Define logger for this module
readarr_logger = get_logger("readarr")

def get_configured_instances():
    """Get all configured and enabled Readarr instances"""
    settings = load_settings("readarr")
    instances = []
    readarr_logger.info(f"Loaded Readarr settings for instance check: {settings}") 

    if not settings:
        readarr_logger.debug("No settings found for Readarr")
        return instances

    # Check if instances are configured
    if "instances" in settings and isinstance(settings["instances"], list) and settings["instances"]:
        readarr_logger.info(f"Found 'instances' list with {len(settings['instances'])} items. Processing...")
        for idx, instance in enumerate(settings["instances"]):
            readarr_logger.debug(f"Checking instance #{idx}: {instance}")
            # Enhanced validation
            api_url = instance.get("api_url", "").strip()
            api_key = instance.get("api_key", "").strip()

            # Enhanced URL validation - ensure URL has proper scheme
            if api_url and not (api_url.startswith('http://') or api_url.startswith('https://')):
                readarr_logger.warning(f"Instance '{instance.get('name', 'Unnamed')}' has URL without http(s) scheme: {api_url}")
                api_url = f"http://{api_url}"
                readarr_logger.warning(f"Auto-correcting URL to: {api_url}")

            is_enabled = instance.get("enabled", True)

            # Only include properly configured instances
            if is_enabled and api_url and api_key:
                # Return only essential instance details
                instance_data = {
                    "instance_name": instance.get("name", "Default"),
                    "api_url": api_url,
                    "api_key": api_key,
                }
                instances.append(instance_data) 
                readarr_logger.info(f"Added valid instance: {instance_data}") 
            elif not is_enabled:
                readarr_logger.debug(f"Skipping disabled instance: {instance.get('name', 'Unnamed')}")
            else:
                # Log specifically why it's skipped (missing URL/Key but enabled)
                readarr_logger.warning(f"Skipping instance '{instance.get('name', 'Unnamed')}' due to missing API URL or key (URL: '{api_url}', Key Set: {bool(api_key)}) ")
    else:
        readarr_logger.info("No 'instances' list found or list is empty. Checking legacy config.")
        # Fallback to legacy single-instance config
        api_url = settings.get("api_url", "").strip()
        api_key = settings.get("api_key", "").strip()

        # Ensure URL has proper scheme
        if api_url and not (api_url.startswith('http://') or api_url.startswith('https://')):
            readarr_logger.warning(f"API URL missing http(s) scheme: {api_url}")
            api_url = f"http://{api_url}"
            readarr_logger.warning(f"Auto-correcting URL to: {api_url}")

        if api_url and api_key:
            # Create a clean instance_data dict for the legacy instance
            instance_data = {
                "instance_name": "Default", 
                "api_url": api_url,
                "api_key": api_key,
            }
            instances.append(instance_data) 
            readarr_logger.info(f"Added valid legacy instance: {instance_data}") 
        else:
            readarr_logger.warning("No API URL or key found in legacy configuration")

    readarr_logger.info(f"Returning {len(instances)} configured instances: {instances}") 
    return instances

__all__ = ["process_missing_books", "process_cutoff_upgrades", "get_configured_instances"]