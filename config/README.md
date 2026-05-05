# Local Config

This directory is for local runtime configuration.

Tracked files may document config shape. Files matching `*.local.env` or
`secrets*.env` are ignored by Git and may contain provider API keys.

Expected private file:

```text
config/secrets.local.env
```

Supported variables:

```text
DEEPSEEK_API_KEY=...
```
