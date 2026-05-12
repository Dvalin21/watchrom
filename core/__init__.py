"""
core/__init__.py — Auto-load all vendor and band backend implementations
so @register_vendor and @register_band_config decorators fire on import.
"""
# Import order matters: interfaces first, then registry, then concrete implementations
from core.interfaces import *          # noqa: F401 - base classes
from core.registry   import *          # noqa: F401 - registry functions
import core.vendors                    # triggers @register_vendor decorators
import core.band_backends              # triggers @register_band_config decorators
