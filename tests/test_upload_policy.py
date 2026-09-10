from fastapi import HTTPException
import pytest

from fieldservice_uploads.upload_service import DispatchStatus, FollowUp, upload_policy


def test_on_site_photo_moves_to_completion_review() -> None:
    assert upload_policy(DispatchStatus.ON_SITE) == FollowUp.COMPLETION_REVIEW


def test_completed_dispatch_cannot_request_another_upload() -> None:
    with pytest.raises(HTTPException) as caught:
        upload_policy(DispatchStatus.COMPLETED)
    assert caught.value.status_code == 409
