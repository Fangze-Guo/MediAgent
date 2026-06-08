import logging
from typing import Any, Dict, List, Optional

import asyncpg

from src.server_agent.configs.pg_config import get_pg_config
from src.server_agent.model.entity.PatientInfo import PatientInfo

logger = logging.getLogger(__name__)


class PatientMapper:
    """PostgreSQL data access for the global patient registry."""

    def __init__(self):
        self._config = get_pg_config()
        self._pool: Optional[asyncpg.Pool] = None

    async def init(self) -> None:
        await self._get_pool()
        await self._ensure_tables()
        logger.info("[PatientMapper] Initialized")

    async def close(self) -> None:
        if self._pool is not None:
            await self._pool.close()
            self._pool = None

    async def _get_pool(self) -> asyncpg.Pool:
        if self._pool is None:
            self._pool = await asyncpg.create_pool(
                host=self._config.host,
                port=self._config.port,
                database=self._config.database,
                user=self._config.user,
                password=self._config.password,
                min_size=1,
                max_size=10,
            )
        return self._pool

    async def _ensure_tables(self) -> None:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS patients (
                    id BIGSERIAL PRIMARY KEY,
                    patient_id VARCHAR(64) NOT NULL UNIQUE,
                    name VARCHAR(128) NOT NULL,
                    sex VARCHAR(20),
                    age INT,
                    phone VARCHAR(64),
                    height_cm NUMERIC(6,2),
                    smoking_status VARCHAR(64),
                    pathology_type VARCHAR(128),
                    pd_l1_status VARCHAR(128),
                    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await conn.execute("""
                CREATE INDEX IF NOT EXISTS idx_patients_name
                ON patients(name)
            """)

    @staticmethod
    def _to_patient(record: asyncpg.Record) -> PatientInfo:
        return PatientInfo(
            id=record["id"],
            patient_id=record["patient_id"],
            name=record["name"],
            sex=record["sex"],
            age=record["age"],
            phone=record["phone"],
            height_cm=float(record["height_cm"]) if record["height_cm"] is not None else None,
            smoking_status=record["smoking_status"],
            pathology_type=record["pathology_type"],
            pd_l1_status=record["pd_l1_status"],
            created_at=record["created_at"],
            updated_at=record["updated_at"],
        )

    async def create_patient(self, data: Dict[str, Any]) -> PatientInfo:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            record = await conn.fetchrow("""
                INSERT INTO patients (
                    patient_id, name, sex, age, phone, height_cm,
                    smoking_status, pathology_type, pd_l1_status
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                RETURNING *
            """,
                data["patient_id"],
                data["name"],
                data.get("sex"),
                data.get("age"),
                data.get("phone"),
                data.get("height_cm"),
                data.get("smoking_status"),
                data.get("pathology_type"),
                data.get("pd_l1_status"),
            )
        return self._to_patient(record)

    async def upsert_patient(self, data: Dict[str, Any]) -> PatientInfo:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            record = await conn.fetchrow("""
                INSERT INTO patients (
                    patient_id, name, sex, age, phone, height_cm,
                    smoking_status, pathology_type, pd_l1_status
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9)
                ON CONFLICT (patient_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    sex = EXCLUDED.sex,
                    age = EXCLUDED.age,
                    phone = EXCLUDED.phone,
                    height_cm = EXCLUDED.height_cm,
                    smoking_status = EXCLUDED.smoking_status,
                    pathology_type = EXCLUDED.pathology_type,
                    pd_l1_status = EXCLUDED.pd_l1_status,
                    updated_at = CURRENT_TIMESTAMP
                RETURNING *
            """,
                data["patient_id"],
                data["name"],
                data.get("sex"),
                data.get("age"),
                data.get("phone"),
                data.get("height_cm"),
                data.get("smoking_status"),
                data.get("pathology_type"),
                data.get("pd_l1_status"),
            )
        return self._to_patient(record)

    async def get_patient(self, patient_id: str) -> Optional[PatientInfo]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            record = await conn.fetchrow(
                "SELECT * FROM patients WHERE patient_id = $1",
                patient_id,
            )
        return self._to_patient(record) if record else None

    async def list_patients(self, keyword: Optional[str], limit: int, offset: int) -> List[PatientInfo]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if keyword:
                pattern = f"%{keyword}%"
                records = await conn.fetch("""
                    SELECT * FROM patients
                    WHERE patient_id ILIKE $1 OR name ILIKE $1 OR phone ILIKE $1
                    ORDER BY updated_at DESC, id DESC
                    LIMIT $2 OFFSET $3
                """, pattern, limit, offset)
            else:
                records = await conn.fetch("""
                    SELECT * FROM patients
                    ORDER BY updated_at DESC, id DESC
                    LIMIT $1 OFFSET $2
                """, limit, offset)
        return [self._to_patient(record) for record in records]

    async def count_patients(self, keyword: Optional[str]) -> int:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            if keyword:
                pattern = f"%{keyword}%"
                return int(await conn.fetchval("""
                    SELECT COUNT(*) FROM patients
                    WHERE patient_id ILIKE $1 OR name ILIKE $1 OR phone ILIKE $1
                """, pattern))
            return int(await conn.fetchval("SELECT COUNT(*) FROM patients"))

    async def list_all_patients(self) -> List[PatientInfo]:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            records = await conn.fetch("""
                SELECT * FROM patients
                ORDER BY updated_at DESC, id DESC
            """)
        return [self._to_patient(record) for record in records]

    async def update_patient(self, patient_id: str, data: Dict[str, Any]) -> Optional[PatientInfo]:
        allowed_fields = [
            "name",
            "sex",
            "age",
            "phone",
            "height_cm",
            "smoking_status",
            "pathology_type",
            "pd_l1_status",
        ]
        update_fields = [field for field in allowed_fields if field in data]
        if not update_fields:
            return await self.get_patient(patient_id)

        assignments = []
        values: list[Any] = []
        for index, field in enumerate(update_fields, start=1):
            assignments.append(f"{field} = ${index}")
            values.append(data[field])
        patient_id_index = len(values) + 1
        values.append(patient_id)

        pool = await self._get_pool()
        async with pool.acquire() as conn:
            record = await conn.fetchrow(
                f"""
                UPDATE patients
                SET {", ".join(assignments)},
                    updated_at = CURRENT_TIMESTAMP
                WHERE patient_id = ${patient_id_index}
                RETURNING *
                """,
                *values,
            )
        return self._to_patient(record) if record else None

    async def delete_patient(self, patient_id: str) -> bool:
        pool = await self._get_pool()
        async with pool.acquire() as conn:
            result = await conn.execute(
                "DELETE FROM patients WHERE patient_id = $1",
                patient_id,
            )
        return result.endswith("1")
