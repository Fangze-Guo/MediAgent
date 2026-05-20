"""
阿里云 OSS 服务 - 预签名 URL 直传
使用 alibabacloud-oss-v2 SDK
"""
import uuid
import logging
from datetime import timedelta
from pathlib import Path
from typing import Optional

import alibabacloud_oss_v2 as oss

from src.server_agent.configs.oss_config import get_oss_config

logger = logging.getLogger(__name__)


class OssService:
    """生成预签名 PUT URL，供前端直传图片到 OSS"""

    def __init__(self):
        self._client: Optional[oss.Client] = None

    def _get_client(self) -> oss.Client:
        if self._client is None:
            cfg = get_oss_config()
            # 使用环境变量凭证（SDK 自动读取 OSS_ACCESS_KEY_ID / OSS_ACCESS_KEY_SECRET）
            credentials_provider = oss.credentials.EnvironmentVariableCredentialsProvider()
            oss_cfg = oss.config.load_default()
            oss_cfg.credentials_provider = credentials_provider
            oss_cfg.region = cfg.region
            self._client = oss.Client(oss_cfg)
        return self._client

    def generate_presign_url(
        self,
        user_id: str,
        conversation_id: str,
        filename: str,
        content_type: str,
        expires_seconds: int = 120,
    ) -> dict:
        """
        生成预签名 PUT URL。

        存储路径：{user_id}/{conversation_id}/{uuid}{ext}

        Returns:
            {
                "put_url": str,          # 前端直接 PUT 到这个 URL
                "signed_headers": dict,  # PUT 请求必须携带的 Headers
                "access_url": str,       # 上传成功后的永久访问 URL
                "object_key": str,
            }
        """
        cfg = get_oss_config()
        client = self._get_client()

        ext = Path(filename).suffix.lower() or ".bin"
        object_key = f"{user_id}/{conversation_id}/{uuid.uuid4()}{ext}"

        pre_result = client.presign(
            oss.PutObjectRequest(
                bucket=cfg.bucket_name,
                key=object_key,
                content_type=content_type,
            ),
            expires=timedelta(seconds=expires_seconds),
        )

        return {
            "put_url": pre_result.url,
            "signed_headers": dict(pre_result.signed_headers),
            "access_url": f"{cfg.base_url}/{object_key}",
            "object_key": object_key,
        }

    def delete_objects(self, object_keys: list[str]) -> None:
        """批量删除 OSS 对象（忽略不存在的 key）"""
        if not object_keys:
            return
        cfg = get_oss_config()
        client = self._get_client()
        for key in object_keys:
            try:
                client.delete_object(oss.DeleteObjectRequest(
                    bucket=cfg.bucket_name,
                    key=key,
                ))
                logger.debug("OSS 对象已删除: %s", key)
            except Exception as e:
                logger.warning("OSS 对象删除失败（跳过）: %s — %s", key, e)

    def extract_object_key(self, access_url: str) -> Optional[str]:
        """从访问 URL 中提取 object_key（去除 base_url 前缀）"""
        cfg = get_oss_config()
        prefix = cfg.base_url + "/"
        if access_url.startswith(prefix):
            return access_url[len(prefix):]
        return None
