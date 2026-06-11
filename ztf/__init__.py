"""ZTF -- Zero Touch Framework for Nutanix infrastructure automation."""

from importlib.metadata import PackageNotFoundError, version

try:
    __version__: str = version("nutanix-ztf")
except PackageNotFoundError:
    __version__ = "0.0.0"

__all__ = ["__version__"]
