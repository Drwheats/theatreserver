import os
from datetime import datetime
from uuid import uuid4

import requests


def load_dotenv(path=".env"):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = value


def send_test_message():
    homeserver = os.getenv("MATRIX_HOMESERVER_URL", "").rstrip("/")
    access_token = os.getenv("MATRIX_ACCESS_TOKEN", "")
    room_id = os.getenv("MATRIX_ROOM_ID", "")

    if not homeserver or not access_token or not room_id:
        raise RuntimeError(
            "Missing MATRIX_HOMESERVER_URL, MATRIX_ACCESS_TOKEN, or MATRIX_ROOM_ID"
        )

    txn_id = uuid4().hex
    url = f"{homeserver}/_matrix/client/v3/rooms/{room_id}/send/m.room.message/{txn_id}"
    message = f"🧪 Matrix test from theatreserver at {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
    payload = {"msgtype": "m.text", "body": message}
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    response = requests.put(url, headers=headers, json=payload, timeout=20)
    response.raise_for_status()
    print("Matrix test message sent successfully")


if __name__ == "__main__":
    load_dotenv()
    send_test_message()
