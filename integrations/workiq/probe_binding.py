"""Temporary, server-owned binding for the approved Work IQ diagnostic."""

from datetime import datetime

TENANT_ID = "9492545f-58bd-4fe2-974e-7124c38e4c2b"
ALEX_OBJECT_ID = "e04db6b6-ab94-4718-ae08-4e75023b7a4c"
JORDAN_OBJECT_ID = "fed4348d-b983-4757-ab9f-0146ed52bfcd"
TEAM_ID = "6cbd1c71-8a78-49eb-9d47-aef266fb55da"
CHANNEL_ID = "19:2ROXbDFk-xAzLDwt8NJAsRozD1zhz1XtG5QXqzGppsw1@thread.tacv2"
MESSAGE_ID = "1788577543694"

# The deployment controller replaces both values immediately before deployment.
PROBE_START_UTC: datetime | None = None
PROBE_END_UTC: datetime | None = None
