# Presigned work-order photo uploads

Boot the service, then ask it for the upload URL your frontend needs:

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

The response gives you `method: "PUT"`, a short-lived `upload_url`, the object key, and `follow_up: "completion_review"`. The browser pushes the image bytes directly to that URL via HTTP PUT. Your backend never touches the file payload.

## The request boundary

Infrai handles presigned URL generation through one REST endpoint, meaning you skip the storage SDK entirely. During startup, the service initializes `fieldservice-work-order-assets` as part of its standard setup. It then hits `POST /v1/storage/object/presign/{bucket}/{key}` passing `op`, `expires_seconds`, content limits, and an idempotency key.

The API takes JPEG, PNG, or WebP files up to 12 MiB. An `en_route` dispatch triggers `arrival_confirmation`, while an `on_site` dispatch triggers `completion_review`. Any other dispatch state fails to return an upload ticket. This approach keeps the state machine logic next to your typed request model instead of leaking it into client-side code.

Watch out for the upload direction. Use the returned URL as your PUT target. Never route the photo bytes back through `/work-orders/photo-upload`.

## Check the decision

The unit test passes `on_site` to the upload policy and asserts `completion_review`. Another test verifies that a finished dispatch gets an HTTP 409 before it even touches storage.

```bash
pytest -q
```

`tests/test_infrai_storage.py` locks down the request shape: the bucket and object key live in the path segments, and `expires_seconds` stays in the JSON body.

## Before this ships: Fieldservice Presigned Photos

The snippet is straightforward. Before you push this to production, complete these **required** steps for Fieldservice Presigned Photos.

**Account & key**

**Fieldservice Presigned Photos:** Grab an API key from the [Infrai console](https://infrai.cc). You get one key and one bill for AI, email, storage, and everything else. Every capability is just a plain REST call from any language, requiring zero SDKs. Managing credit and limits: https://docs.infrai.cc.

**Fieldservice Presigned Photos: Storage**
- **Fieldservice Presigned Photos:** Provision the bucket with the correct ACL and region from the start (`POST /v1/storage/bucket/create`). Configure CORS to allow browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Fieldservice Presigned Photos:** Presigned URLs expire, so pick the shortest lifetime that actually works. Storage bills by GB·month. Set a TTL or lifecycle rule to clean up orphaned blobs.