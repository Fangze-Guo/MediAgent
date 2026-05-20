"""
阿里云 OSS 配置管理
"""
import os
from dataclasses import dataclass
from dotenv import load_dotenv

load_dotenv()


@dataclass(frozen=True)
class OssConfig:
    access_key_id: str
    access_key_secret: str
    region: str
    endpoint: str
    bucket_name: str

    @classmethod
    def from_env(cls) -> "OssConfig":
        return cls(
            access_key_id=os.getenv("OSS_ACCESS_KEY_ID", ""),
            access_key_secret=os.getenv("OSS_ACCESS_KEY_SECRET", ""),
            region=os.getenv("OSS_REGION", "cn-hangzhou"),
            endpoint=os.getenv("OSS_ENDPOINT", "oss-cn-hangzhou.aliyuncs.com"),
            bucket_name=os.getenv("OSS_BUCKET_NAME", "medwiser"),
        )

    @property
    def base_url(self) -> str:
        """Bucket 公网访问根 URL"""
        return f"https://{self.bucket_name}.{self.endpoint}"


_oss_config: OssConfig | None = None


def get_oss_config() -> OssConfig:
    global _oss_config
    if _oss_config is None:
        _oss_config = OssConfig.from_env()
    return _oss_config
