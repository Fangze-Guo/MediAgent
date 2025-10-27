from pydantic import BaseModel, Field
from typing import Optional


class UpdateDatasetRequest(BaseModel):
    """更新数据集请求"""
    id: int = Field(..., description="数据集ID")
    dataset_name: Optional[str] = Field(None, description="数据集名称")
    case_count: Optional[int] = Field(None, description="案例数量")
    clinical_data_desc: Optional[str] = Field(None, description="临床数据描述")
    text_data_desc: Optional[str] = Field(None, description="文本数据描述")
    imaging_data_desc: Optional[str] = Field(None, description="影像数据描述")
    pathology_data_desc: Optional[str] = Field(None, description="病理数据描述")
    genomics_data_desc: Optional[str] = Field(None, description="基因组数据描述")
    annotation_desc: Optional[str] = Field(None, description="标注描述")
    notes: Optional[str] = Field(None, description="备注")

