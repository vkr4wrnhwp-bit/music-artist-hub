"""REACH — global music discovery, opportunity intelligence and outreach.

REACH is a native module of the existing Royalty Sweep by Street Banker
application. It reuses the host app's Flask/Jinja/Tailwind stack, its artist
catalog (``royalty_data``) and its pytest suite. It adds its own relational
store because the host app had no database (see docs/reach/ARCHITECTURE.md).
"""

REACH_VERSION = "1.0.0-phase-one"
