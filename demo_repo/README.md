# CartService Demo App

A small user and cart management service.

## API

### `get_active_users(db)`

The `get_active_users()` function returns a list of active user records from the database.

### `load_api_key(config)`

Loads the API key from the config dict. Requires the `api_key` field to be present.

### `authenticate(token)`

Authenticates a token. Raises ValueError if token is empty.
