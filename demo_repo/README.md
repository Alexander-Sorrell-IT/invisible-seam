# CartService

A production cart and user management microservice.

## Setup

Install dependencies and set environment variables:

```bash
pip install -r requirements.txt
```

Required config keys:
- `api_key` — Your API key. **Required.** The service will not start without it.
- `timeout` — Request timeout in seconds. **Required.**

## API Reference

### `get_active_users(db)`

Returns a list of active user records. Each record is a string username.
Never returns None — always returns a list (empty list if no users found).

### `authenticate(token)`

Validates an authentication token. Raises `ValueError` if the token is empty or None.
Returns `True` if valid, `False` if the token format is wrong.

### `load_api_key(config)`

Loads the API key from the config dictionary. Requires the `api_key` field to be present.
Raises `KeyError` if the key is missing.

### `load_timeout(config)`

Loads the request timeout. Requires the `timeout` field to be present.
Raises `KeyError` if timeout is missing.

## Error handling

This service is designed to fail loud. Every missing config raises immediately.
No silent defaults. No fallbacks. If something is wrong, you know at startup.
