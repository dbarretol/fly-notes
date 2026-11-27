"""Fly Notes — a minimal floating, always-on-top task widget for Windows 11."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("fly-notes")
except PackageNotFoundError:  # running from a tree that was never installed
    __version__ = "0.0.0+unknown"

__all__ = ["__version__"]
