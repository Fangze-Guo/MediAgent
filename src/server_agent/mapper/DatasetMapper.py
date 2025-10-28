"""
数据集 Mapper - 处理数据集的数据库操作
"""
import logging
import secrets
from typing import List, Optional
from pathlib import Path

from .BaseMapper import BaseMapper
from ..model.entity.DatasetInfo import DatasetInfo
from ..exceptions import DatabaseError, handle_mapper_exception

logger = logging.getLogger(__name__)


class DatasetMapper(BaseMapper):
    """数据集数据库操作类"""

    def __init__(self, db_path: Path):
        super().__init__(db_path)
        
    def _generate_dataset_id(self) -> int:
        """生成随机数据集ID（10位数）"""
        return secrets.randbelow(9_000_000_000) + 1_000_000_000
    
    async def check_dataset_id_exists(self, dataset_id: int) -> bool:
        """检查数据集ID是否已存在"""
        query = "SELECT 1 FROM dataset_catalog WHERE id = ? LIMIT 1"
        result = await self.execute_query(query, (dataset_id,), fetch_one=True)
        return result is not None
    
    async def generate_unique_dataset_id(self) -> int:
        """生成唯一的数据集ID"""
        max_attempts = 100
        for _ in range(max_attempts):
            dataset_id = self._generate_dataset_id()
            if not await self.check_dataset_id_exists(dataset_id):
                return dataset_id
        
        raise RuntimeError(f"Failed to generate unique dataset ID after {max_attempts} attempts")
        
    async def init_table(self):
        """初始化数据集表"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS dataset_catalog (
            id INTEGER PRIMARY KEY,
            dataset_name TEXT NOT NULL,
            case_count INTEGER DEFAULT 0,
            clinical_data_desc TEXT,
            text_data_desc TEXT,
            imaging_data_desc TEXT,
            pathology_data_desc TEXT,
            genomics_data_desc TEXT,
            annotation_desc TEXT,
            notes TEXT,
            user_id INTEGER NOT NULL,
            has_data INT DEFAULT 0,
            has_description_file INT DEFAULT 0,
            data_path TEXT,
            create_time TEXT DEFAULT (datetime('now', 'localtime')),
            description_file_path TEXT,
            FOREIGN KEY (user_id) REFERENCES users(uid)
        )
        """
        await self.execute_query(create_table_sql)
        logger.info("Dataset catalog table initialized")

    @handle_mapper_exception
    async def create_dataset(self, dataset: DatasetInfo) -> int:
        """创建数据集"""
        # 生成唯一的数据集ID
        dataset_id = await self.generate_unique_dataset_id()
        
        query = """
        INSERT INTO dataset_catalog 
        (id, dataset_name, case_count, clinical_data_desc, text_data_desc, 
         imaging_data_desc, pathology_data_desc, genomics_data_desc, 
         annotation_desc, notes, user_id, has_data, has_description_file, 
         data_path, description_file_path)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            dataset_id,
            dataset.dataset_name,
            dataset.case_count,
            dataset.clinical_data_desc,
            dataset.text_data_desc,
            dataset.imaging_data_desc,
            dataset.pathology_data_desc,
            dataset.genomics_data_desc,
            dataset.annotation_desc,
            dataset.notes,
            dataset.user_id,
            dataset.has_data or 0,
            dataset.has_description_file or 0,
            dataset.data_path,
            dataset.description_file_path
        )
        
        async with self.get_connection() as db:
            await db.execute(query, params)
            await db.commit()
            return dataset_id

    @handle_mapper_exception
    async def get_dataset_by_id(self, dataset_id: int) -> Optional[DatasetInfo]:
        """根据ID获取数据集"""
        query = "SELECT * FROM dataset_catalog WHERE id = ?"
        row = await self.execute_query(query, (dataset_id,), fetch_one=True)
        
        if row:
            return DatasetInfo(**dict(row))
        return None

    @handle_mapper_exception
    async def get_dataset_by_name_and_user(self, dataset_name: str, user_id: int) -> Optional[DatasetInfo]:
        """根据数据集名称和用户ID获取数据集"""
        query = "SELECT * FROM dataset_catalog WHERE dataset_name = ? AND user_id = ?"
        row = await self.execute_query(query, (dataset_name, user_id), fetch_one=True)
        
        if row:
            return DatasetInfo(**dict(row))
        return None

    @handle_mapper_exception
    async def get_datasets_by_user(self, user_id: int) -> List[DatasetInfo]:
        """获取用户的所有数据集"""
        query = "SELECT * FROM dataset_catalog WHERE user_id = ? ORDER BY id DESC"
        rows = await self.execute_query(query, (user_id,), fetch_all=True)
        
        return [DatasetInfo(**dict(row)) for row in rows] if rows else []

    @handle_mapper_exception
    async def get_all_datasets(self) -> List[DatasetInfo]:
        """获取所有数据集（管理员用）"""
        query = "SELECT * FROM dataset_catalog ORDER BY id DESC"
        rows = await self.execute_query(query, fetch_all=True)
        
        return [DatasetInfo(**dict(row)) for row in rows] if rows else []

    @handle_mapper_exception
    async def update_dataset(self, dataset_id: int, update_data: dict) -> bool:
        """更新数据集信息"""
        # 构建动态更新语句
        fields = []
        params = []
        
        for key, value in update_data.items():
            if value is not None and key != 'id' and key != 'user_id':
                fields.append(f"{key} = ?")
                params.append(value)
        
        if not fields:
            return False
        
        params.append(dataset_id)
        query = f"UPDATE dataset_catalog SET {', '.join(fields)} WHERE id = ?"
        
        async with self.get_connection() as db:
            await db.execute(query, params)
            await db.commit()
            return True

    @handle_mapper_exception
    async def delete_dataset(self, dataset_id: int) -> bool:
        """删除数据集"""
        query = "DELETE FROM dataset_catalog WHERE id = ?"
        
        async with self.get_connection() as db:
            await db.execute(query, (dataset_id,))
            await db.commit()
            return True

    @handle_mapper_exception
    async def update_case_count(self, dataset_id: int, case_count: int) -> bool:
        """更新案例数量"""
        query = "UPDATE dataset_catalog SET case_count = ? WHERE id = ?"
        
        async with self.get_connection() as db:
            await db.execute(query, (case_count, dataset_id))
            await db.commit()
            return True

