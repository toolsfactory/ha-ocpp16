"""Domain layer of the Standalone-Kern: OCPP-agnostic state and services.

Nothing in this package imports ``ocpp.*`` or ``homeassistant.*`` — it is the
part of the kernel that the OCPP-1.6 handlers (``core.ocpp16``) drive, and
that consumers (console, later HA-Layer) read through ``QueryService`` /
``CommandService``.
"""
