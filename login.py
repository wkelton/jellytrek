#!/usr/bin/env python3

import json
import click

from lib.jellyfin_client import JellyfinClient, authenticate, make_device_id


@click.group(invoke_without_command=True)
@click.option('--url', help='URL to your Jellyfin instance')
@click.option('--user', help='Jellyfin username')
@click.option('--password', help='Jellyfin password')
@click.pass_context
def cli(ctx, url: str, user: str, password: str):
    """Login to Jellyfin with user creds by making a device/client
    """
    device_id = make_device_id()
    client = JellyfinClient(base_url=url, device_id=device_id)
    result = authenticate(user, password, client)

    print(f"Authenticated {result.user.name}: {result.user.id}")
    print(f"Access token: {result.access_token}")
    print(f"Device ID: {device_id}")

    auth_data = {
        "url": url,
        "user_id": result.user.id,
        "token": result.access_token,
        "device_id": device_id,
    }

    with open("login.json", "w") as f:
        json.dump(auth_data, f)


if __name__ == "__main__":
    cli()
