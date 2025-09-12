"""
数据处理工具
"""
import pandas as pd
from pathlib import Path
from typing import Annotated
from .base_tool import BaseTool


class DataTools(BaseTool):
    """数据处理工具类"""
    
    def register_tools(self):
        """注册数据处理工具到MCP服务器"""
        if not self.mcp_server:
            return
            
        @self.mcp_server.tool()
        def csv_summary(
            csv_path: Annotated[str, "CSV 文件路径"],
            delimiter: Annotated[str, "分隔符，默认逗号"] = ",",
            max_rows: Annotated[int, "最多抽样行数"] = 5000,
            timeout: Annotated[int, "超时时间(秒)"] = 60
        ) -> str:
            """CSV文件统计分析"""
            return self.csv_summary_impl(csv_path, delimiter, max_rows, timeout)

        @self.mcp_server.tool()
        def csv_preview(
            csv_path: Annotated[str, "CSV 文件路径"],
            delimiter: Annotated[str, "分隔符，默认逗号"] = ",",
            rows: Annotated[int, "预览行数"] = 10
        ) -> str:
            """CSV文件预览"""
            return self.csv_preview_impl(csv_path, delimiter, rows)
    
    def csv_summary_impl(
        self,
        csv_path: str,
        delimiter: str = ",",
        max_rows: int = 5000,
        timeout: int = 60
    ) -> str:
        """CSV文件统计分析"""
        try:
            self._log_operation("csv_summary", csv_path=csv_path, delimiter=delimiter, max_rows=max_rows)
            
            # 验证文件
            valid, error_msg, csv_file = self._validate_file_path(csv_path, must_exist=True)
            if not valid:
                return self._json_response(2, "", error_msg, {"args": {"csv_path": csv_path}})
            
            # 读取CSV文件
            try:
                # 限制读取行数
                nrows = max_rows if max_rows > 0 else None
                df = pd.read_csv(csv_file, delimiter=delimiter, nrows=nrows)
                
                # 生成统计信息
                summary = {
                    "file_info": {
                        "filename": csv_file.name,
                        "file_size_bytes": csv_file.stat().st_size,
                        "file_size_mb": round(csv_file.stat().st_size / (1024 * 1024), 2),
                        "delimiter": delimiter,
                        "max_rows_processed": max_rows
                    },
                    "data_info": {
                        "total_rows": len(df),
                        "total_columns": len(df.columns),
                        "column_names": df.columns.tolist(),
                        "data_types": df.dtypes.astype(str).to_dict()
                    },
                    "statistics": df.describe(include="all").to_dict(),
                    "missing_values": df.isnull().sum().to_dict(),
                    "memory_usage": df.memory_usage(deep=True).to_dict()
                }
                
                # 添加列级别的详细信息
                column_details = {}
                for col in df.columns:
                    col_info = {
                        "dtype": str(df[col].dtype),
                        "non_null_count": df[col].count(),
                        "null_count": df[col].isnull().sum(),
                        "unique_count": df[col].nunique()
                    }
                    
                    # 数值列的特殊信息
                    if df[col].dtype in ['int64', 'float64']:
                        col_info.update({
                            "min": df[col].min(),
                            "max": df[col].max(),
                            "mean": df[col].mean(),
                            "std": df[col].std()
                        })
                    
                    # 文本列的特殊信息
                    elif df[col].dtype == 'object':
                        col_info.update({
                            "most_common": df[col].value_counts().head(5).to_dict(),
                            "avg_length": df[col].astype(str).str.len().mean()
                        })
                    
                    column_details[col] = col_info
                
                summary["column_details"] = column_details
                
                result_msg = f"CSV分析完成: {csv_file.name} ({len(df)}行, {len(df.columns)}列)"
                self.log(f"[csv_summary] {result_msg}")
                
                return self._json_response(0, result_msg, "", {"summary": summary})
                
            except Exception as e:
                error_msg = f"CSV文件读取失败: {e}"
                self.log(f"[csv_summary] ERROR: {error_msg}")
                return self._json_response(1, "", error_msg)
                
        except Exception as e:
            error_msg = f"CSV分析异常: {e}"
            self.log(f"[csv_summary] EXCEPTION: {error_msg}")
            return self._json_response(1, "", error_msg)
    
    def csv_preview_impl(
        self,
        csv_path: str,
        delimiter: str = ",",
        rows: int = 10
    ) -> str:
        """CSV文件预览"""
        try:
            self._log_operation("csv_preview", csv_path=csv_path, delimiter=delimiter, rows=rows)
            
            # 验证文件
            valid, error_msg, csv_file = self._validate_file_path(csv_path, must_exist=True)
            if not valid:
                return self._json_response(2, "", error_msg)
            
            # 读取CSV文件
            try:
                df = pd.read_csv(csv_file, delimiter=delimiter, nrows=rows)
                
                preview = {
                    "file_info": {
                        "filename": csv_file.name,
                        "delimiter": delimiter,
                        "preview_rows": rows
                    },
                    "columns": df.columns.tolist(),
                    "data": df.to_dict('records'),  # 转换为字典列表
                    "dtypes": df.dtypes.astype(str).to_dict()
                }
                
                result_msg = f"CSV预览完成: {csv_file.name} (前{len(df)}行)"
                self.log(f"[csv_preview] {result_msg}")
                
                return self._json_response(0, result_msg, "", {"preview": preview})
                
            except Exception as e:
                error_msg = f"CSV文件读取失败: {e}"
                self.log(f"[csv_preview] ERROR: {error_msg}")
                return self._json_response(1, "", error_msg)
                
        except Exception as e:
            error_msg = f"CSV预览异常: {e}"
            self.log(f"[csv_preview] EXCEPTION: {error_msg}")
            return self._json_response(1, "", error_msg)
