"""Synthetic bindings; these strings never authorize a real device or network."""

import json


def bundle():
    bindings = []
    for site in ("home", "work"):
        bindings.append(
            {
                "schema_version": 1,
                "device_id": "display-a",
                "ssid": f"{site}-demo",
                "wifi_password": "synthetic-password",
                "gateway_url": f"https://{site}.test:8443",
                "token": site * 16,
                "ca_pem": "-----BEGIN CERTIFICATE-----\nSYNTHETIC-NOT-A-CERT\n-----END CERTIFICATE-----\n",
                "interval_seconds": 900,
                "wifi_timeout_ms": 15000,
                "http_timeout_ms": 5000,
                "seed_utc": 1800000000,
            }
        )
    return {
        "schema_version": 1,
        "seed_utc": 1800000000,
        "policy": {
            "night_mode_enabled": True,
            "night_start": "00:00",
            "night_end": "08:00",
            "timezone": "America/Argentina/Buenos_Aires",
        },
        "routes": [{"site_id": "home", "binding": 0}, {"site_id": "work", "binding": 1}],
        "bindings": bindings,
    }


if __name__ == "__main__":
    print(json.dumps(bundle(), separators=(",", ":")), end="")
