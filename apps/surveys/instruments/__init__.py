"""Instrument registry for survey instruments."""

from apps.surveys.instruments.base import BaseInstrument, InstrumentRegistry

registry = InstrumentRegistry()


def register(cls):
    """Decorator to register an instrument class."""
    registry.register(cls)
    return cls


__all__ = ["BaseInstrument", "InstrumentRegistry", "registry", "register"]
