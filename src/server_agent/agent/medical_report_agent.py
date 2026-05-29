"""
Specialized medical imaging report agent.

This agent is intentionally narrow: it receives prepared visual inputs
and metadata, then returns a structured report JSON object. File access,
permission checks, NIfTI preview generation, and HTML rendering stay in
tools/services outside this agent.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Any, Dict, List

from langchain_core.messages import HumanMessage, SystemMessage

logger = logging.getLogger(__name__)


SYSTEM_PROMPT = """\
你是医学影像报告生成智能体，专门根据医学图像预览和元数据生成结构化影像报告。

规则：
- 只基于输入图像、元数据和用户指定任务生成报告。
- 不得编造患者身份、检查日期、病理结果、精确测量值或明确诊断。
- 如果身体部位、病灶性质、范围或分级不能确认，必须写“需医生复核”。
- 如果输入是 NIfTI，通常只提供 axial/coronal/sagittal 中心切片预览，不代表完整三维阅片。
- 除非用户明确说明或图像证据非常清楚，不要默认写胸部、肺部、腹部、头颅等部位。
- 输出必须是合法 JSON，不要输出 Markdown。

JSON schema:
{
  "title": string,
  "summary": string,
  "image_findings": [
    {"image_index": number, "image_name": string, "finding": string, "caption": string}
  ],
  "measurement_table": [
    {"item": string, "value": string, "unit": string, "note": string}
  ],
  "impression": string[],
  "recommendation": string[]
}
""".strip()


class MedicalImageReportAgent:
    """Domain agent for medical imaging report JSON generation."""

    def __init__(self, llm: Any) -> None:
        self.llm = llm

    @staticmethod
    def _extract_json(text: str) -> Dict[str, Any]:
        try:
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else {}
        except Exception:
            match = re.search(r"\{.*\}", text, re.S)
            if not match:
                return {}
            try:
                parsed = json.loads(match.group(0))
                return parsed if isinstance(parsed, dict) else {}
            except Exception:
                return {}

    async def generate_report(
        self,
        *,
        visual_content_parts: List[dict],
        input_metadata: List[dict],
        report_type: str,
        language: str,
        fallback_report: Dict[str, Any],
    ) -> Dict[str, Any]:
        prompt = {
            "report_type": report_type,
            "language": language,
            "input_metadata": input_metadata,
        }
        content_parts: List[dict] = [
            {
                "type": "text",
                "text": (
                    "请生成固定格式医学影像报告 JSON。"
                    f"\n任务参数：{json.dumps(prompt, ensure_ascii=False)}"
                ),
            },
            *visual_content_parts,
        ]

        try:
            response = await self.llm.ainvoke(
                [
                    SystemMessage(content=SYSTEM_PROMPT),
                    HumanMessage(content=content_parts),
                ],
                config={
                    "run_name": "MedicalImageReportAgent",
                    "tags": ["medical-report", "medical-image"],
                },
            )
            report = self._extract_json(str(response.content or ""))
            return report or fallback_report
        except Exception as exc:
            logger.warning("MedicalImageReportAgent failed: %s", exc, exc_info=True)
            return fallback_report
