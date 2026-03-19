"""Exchange rate data sources."""

from bluetrak.sources.dolarapp import DolarAppSource
from bluetrak.sources.infodolar import InfoDolarSource
from bluetrak.sources.western_union import WesternUnionSource

ALL_SOURCES = [DolarAppSource, WesternUnionSource, InfoDolarSource]

__all__ = ["ALL_SOURCES", "DolarAppSource", "InfoDolarSource", "WesternUnionSource"]
