import boto3
from botocore.client import Config
from django.conf import settings


def _get_s3_client():
    kwargs = {
        'aws_access_key_id': settings.AWS_ACCESS_KEY_ID,
        'aws_secret_access_key': settings.AWS_SECRET_ACCESS_KEY,
        'region_name': settings.AWS_S3_REGION_NAME,
        'config': Config(signature_version='s3v4'),
    }
    if settings.AWS_S3_ENDPOINT_URL:
        kwargs['endpoint_url'] = settings.AWS_S3_ENDPOINT_URL
    return boto3.client('s3', **kwargs)


def generate_presigned_view_url(file_key: str) -> str:
    """
    Generate a short-lived presigned URL for inline PDF viewing.
    Content-Disposition is inline to open in browser, not trigger download.
    """
    client = _get_s3_client()
    return client.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
            'Key': file_key,
            'ResponseContentDisposition': 'inline',
            'ResponseContentType': 'application/pdf',
        },
        ExpiresIn=settings.SIGNED_URL_EXPIRY_SECONDS,
    )


def generate_presigned_download_url(file_key: str, filename: str) -> str:
    """
    Generate a presigned URL for file download (longer TTL, attachment disposition).
    """
    client = _get_s3_client()
    return client.generate_presigned_url(
        'get_object',
        Params={
            'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
            'Key': file_key,
            'ResponseContentDisposition': f'attachment; filename="{filename}"',
            'ResponseContentType': 'application/pdf',
        },
        ExpiresIn=settings.DOWNLOAD_URL_EXPIRY_SECONDS,
    )


def generate_presigned_upload_url(file_key: str, content_type: str = 'application/pdf') -> str:
    """Generate a presigned PUT URL for direct-to-S3 upload from server."""
    client = _get_s3_client()
    return client.generate_presigned_url(
        'put_object',
        Params={
            'Bucket': settings.AWS_STORAGE_BUCKET_NAME,
            'Key': file_key,
            'ContentType': content_type,
        },
        ExpiresIn=300,
    )


def delete_s3_object(file_key: str) -> None:
    """Delete an object from S3/MinIO."""
    client = _get_s3_client()
    client.delete_object(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=file_key,
    )


def get_object_size_mb(file_key: str) -> float:
    """Return file size in MB for storage quota tracking."""
    client = _get_s3_client()
    response = client.head_object(
        Bucket=settings.AWS_STORAGE_BUCKET_NAME,
        Key=file_key,
    )
    size_bytes = response['ContentLength']
    return round(size_bytes / (1024 * 1024), 4)
