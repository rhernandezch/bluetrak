"""Exchange rate data sources."""

from bluetrak.sources.arq import ArqSource
from bluetrak.sources.infodolar import InfoDolarSource
from bluetrak.sources.western_union import WesternUnionSource

ALL_SOURCES: tuple[type[ArqSource], type[WesternUnionSource], type[InfoDolarSource]] = (
    ArqSource,
    WesternUnionSource,
    InfoDolarSource,
)

__all__ = ["ALL_SOURCES", "ArqSource", "InfoDolarSource", "WesternUnionSource"]
