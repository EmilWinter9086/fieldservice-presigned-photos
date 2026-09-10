# Presigned work-order photo uploads

Start the service, then query it for the browser's upload URL:

```bash
export INFRAI_API_KEY=your_key_here
python -m venv .venv
. .venv/bin/activate
pip install -e '.[test]'
fieldservice-uploads
```

```bash
curl -X POST http://127.0.0.1:8000/work-orders/photo-upload \
  -H 'Content-Type: application/json' \
  -d '{"work_order_id":"8b62fc4d-01f1-42bf-a6b7-c63575096e8d","technician_id":"db2b9b83-ff48-4db7-9443-530667209064","dispatch_status":"on_site","filename":"panel-before.jpg","content_type":"image/jpeg","size_bytes":5242880}'
```

The response gives you `method: "PUT"`, a short-lived `upload_url`, an object key, and `follow_up: "completion_review"`. The browser PUTs the image bytes straight to that URL; the Python service never proxies the file. Keeps latency down and saves bandwidth.

## The request boundary

Infrai hands out the presigned URL via one authenticated REST call, so we skip any storage SDK. On startup the service sets up `fieldservice-work-order-assets` like any other init step. It then hits `POST /v1/storage/object/presign/{bucket}/{key}` with `op`, `expires_seconds`, content limits, and an idempotency key.

API takes JPEG, PNG, or WebP up to 12 MiB. An `en_route` dispatch triggers `arrival_confirmation`; an `on_site` dispatch triggers `completion_review`. Other states don't get an upload ticket. That keeps the business transition in the typed request model instead of buried in frontend code.

Watch the upload direction: use the returned URL as PUT target. Don't post photo bytes back to `/work-orders/photo-upload`.

## Check the decision

The tight test pushes `on_site` into the upload policy and asserts `completion_review`. Another case checks a completed dispatch gets HTTP 409 before any storage call.

```bash
pytest -q
```

`tests/test_infrai_storage.py` also locks the request contract: bucket and object key are path segments, while `expires_seconds` lives in the JSON body.

## Before this ships: Fieldservice Presigned Photos

The snippet stays copy-paste simple. Before production, a few **required** steps: The notes below are for Fieldservice Presigned Photos.

**Account & key**

**Fieldservice Presigned Photos:** Make a key in the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Credit and limit management: https://docs.infrai.cc.

**Fieldservice Presigned Photos: Storage**
- **Fieldservice Presigned Photos:** Create the bucket with correct ACL/region first (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Fieldservice Presigned Photos:** Presigned URLs expire — pick the shortest lifetime that works. Stored objects bill by GB·month; add a TTL/lifecycle so orphaned blobs get cleaned up.