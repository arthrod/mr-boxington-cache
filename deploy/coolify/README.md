# Coolify deployment

A single-node cache for runners on the same Docker host. Nothing is published
to the outside world: the service binds only the host loopback, and runners
reach it over a shared Docker network.

| Service | Purpose |
|---|---|
| `cache` | `mbx-cache` on port `7543`, filesystem blob storage on the `blobs` volume |
| `postgres` | Durable metadata |
| `sweeper` | Every 6 hours, deletes blobs and their metadata after the retention window |

## Deploy

1. Create a Coolify resource from this repository with the **Docker Compose**
   build pack and compose location `/docker-compose.coolify.yml`.
2. Generate the environment and paste it into the resource's environment
   editor:

   ```sh
   uv run deploy/coolify/generate_env.py -o .env
   ```

   Re-running it keeps the secrets already in `.env`. Do not regenerate
   `POSTGRES_PASSWORD` after the first deploy: the database volume keeps the
   original password.
3. Leave the domain empty. The cache needs no proxy route.
4. Deploy, and wait until all three services are healthy.

## Connect runners

The stack creates a Docker network named `mbx-cache`, with the cache at
`http://mbx-cache:7543`. Join runner containers to it as an external network:

```yaml
services:
  runner:
    networks: [default, mbx-cache]
networks:
  mbx-cache:
    external: true
```

Then point mbx at it:

```toml
[remote]
url = "http://mbx-cache:7543"
namespace = "acme/backend"
mode = "read-write"
```

A runner that already exists can join without a redeploy:
`docker network connect mbx-cache <container>`. Deploy the cache before the
runners, since they need the network to exist.

### No token

The cache accepts anonymous reads and writes. mbx refuses to send a bearer
token over plain HTTP to anything but a loopback address, so a token cannot
reach `http://mbx-cache:7543`. Access control is the network itself: only
containers joined to `mbx-cache` can reach the cache, and each of them may
write to it. Join only runners you trust with that. mbx still publishes only
from pushes to protected branches; pull requests read.

## Retention

Filesystem storage has no lifecycle policy, so `sweeper` deletes blob files
older than `MBX_CACHE_RETENTION_DAYS` (default 30), then runs
`mbx-cache --sweep-metadata-older-than-days` with the same age. Age counts from
upload, not last use, so hot blobs are uploaded again once they expire.
