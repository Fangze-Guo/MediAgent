from pydantic import BaseModel
from typing import Optional


class DatasetVO(BaseModel):
    """数据集视图对象"""
    id: int
    dataset_name: str
    case_count: int
    clinical_data_desc: Optional[str] = None
    text_data_desc: Optional[str] = None
    imaging_data_desc: Optional[str] = None
    pathology_data_desc: Optional[str] = None
    genomics_data_desc: Optional[str] = None
    annotation_desc: Optional[str] = None
    notes: Optional[str] = None
    user_id: int
    has_data: Optional[int] = 0
    has_description_file: Optional[int] = 0
    data_path: Optional[str] = None
    description_file_path: Optional[str] = None
    create_time: Optional[str] = None
    
    class Config:
        from_attributes = True

