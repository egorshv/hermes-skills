from __future__ import annotations

import os
from pathlib import Path

from google_auth_oauthlib.flow import InstalledAppFlow

# Must stay identical to SCOPES in planner_mcp/server.py. Reads of user calendars go
# through the google-workspace skill, so planning-core never asks for them.
SCOPES = ["https://www.googleapis.com/auth/calendar.app.created"]

client_file = Path(os.path.expandvars(os.environ["GOOGLE_OAUTH_CLIENT"])).expanduser()
token_file = Path(os.path.expandvars(os.environ["GOOGLE_TOKEN"])).expanduser()
token_file.parent.mkdir(parents=True, exist_ok=True)

flow = InstalledAppFlow.from_client_secrets_file(str(client_file), SCOPES)
creds = flow.run_local_server(
    host="127.0.0.1",
    port=8765,
    open_browser=False,
    authorization_prompt_message=(
        "\nOpen this URL in your local browser while SSH port-forwarding "
        "localhost:8765 to the server:\n{url}\n"
    ),
)

token_file.write_text(creds.to_json(), encoding="utf-8")
os.chmod(token_file, 0o600)
print(f"Saved OAuth token to {token_file}")
