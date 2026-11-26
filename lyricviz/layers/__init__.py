"""Importing this package registers every built-in layer type."""
from . import background, illustrations, particles  # noqa: F401
from .. import artwork  # noqa: F401  (registers the `artwork` layer)
from .base import REGISTRY, Layer, register  # noqa: F401
