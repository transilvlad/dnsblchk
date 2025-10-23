from pathlib import Path

import yaml


class Config:
    """
    Handles loading the configuration from config.yaml and provides access to the settings.
    """

    def __init__(self):
        """Loads the configuration from config.yaml and resolves file paths."""
        root_path = Path(__file__).parent
        config_path = root_path / 'config/config.yaml'

        with open(config_path, 'r') as f:
            self._config_data = yaml.safe_load(f)

        # Resolve file paths to be absolute
        self._resolve_paths()

    def _resolve_paths(self):
        """Resolves all file paths in the config to be absolute."""
        self._config_data['servers_file'] = self._get_absolute_path('servers_file')
        self._config_data['ips_file'] = self._get_absolute_path('ips_file')
        self._config_data['log_dir'] = self._get_absolute_path('log_dir')
        self._config_data['error_log'] = self._get_absolute_path('error_log')

    def _get_absolute_path(self, key: str) -> Path:
        """Returns an absolute path for a given config key."""
        root_path = Path(__file__).parent
        return root_path / self._config_data[key]

    def __getattr__(self, name):
        """Provides attribute-style access to the configuration settings."""
        if name in self._config_data:
            return self._config_data[name]
        raise AttributeError(f"'Config' object has no attribute '{name}'")


# Create a single instance of the Config class to be used throughout the application
config = Config()
