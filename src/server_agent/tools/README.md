# 医学图像处理工具

## 概述

医学图像处理工具是一个支持完整医学图像处理流程的MCP工具，能够自动编排执行从DICOM到最终归一化的整个处理流程。

## 功能特性

### 支持的处理步骤

1. **DICOM转NII** (`dicom_to_nii`)
   - 将DICOM格式转换为NII格式
   - 自动识别C0序列

2. **图像配准** (`registration`)
   - 执行图像配准处理
   - 生成配准后的图像

3. **nnUNet分割** (`nnunet_segmentation`)
   - 使用nnUNet进行医学图像分割
   - 生成分割掩码

4. **N4偏置场校正** (`n4_correction`)
   - 执行N4偏置场校正
   - 改善图像质量

5. **重采样** (`resample`)
   - 统一图像分辨率和方向
   - 标准化图像格式

6. **归一化** (`normalization`)
   - 执行强度归一化
   - 标准化图像强度

### MCP工具接口

#### 1. `process_medical_images`
执行完整的医学图像处理流程

**参数:**
- `data_root`: 数据根目录路径（包含0_DICOM等子目录）
- `patient_id`: 患者ID（可选，如果为None则处理所有患者）
- `steps`: 要执行的处理步骤列表（可选，如果为None则执行所有步骤）

**返回:**
处理结果字典，包含成功/失败状态和详细信息

#### 2. `get_patient_status`
获取患者处理状态

**参数:**
- `data_root`: 数据根目录路径
- `patient_id`: 患者ID（可选，如果为None则获取所有患者状态）

**返回:**
患者状态信息

#### 3. `process_single_step`
执行单个处理步骤

**参数:**
- `data_root`: 数据根目录路径
- `patient_id`: 患者ID
- `step`: 处理步骤名称

**返回:**
步骤执行结果

#### 4. `get_available_steps`
获取可用的处理步骤列表

**返回:**
处理步骤名称列表

#### 5. `get_data_structure`
获取数据目录结构信息

**参数:**
- `data_root`: 数据根目录路径

**返回:**
目录结构信息

## 数据目录结构

```
data_root/
├── 0_DICOM/          # 原始DICOM数据
│   └── patient_id/
│       └── C0/       # C0序列目录
│           └── *.dcm
├── 1_NII/            # NII格式数据
│   └── patient_id/
│       └── C0.nii.gz
├── 2_Reg/            # 配准后数据
│   └── patient_id/
│       ├── C0.nii.gz
│       └── C0_mask.nii.gz
├── 3_N4/             # N4校正后数据
│   └── patient_id/
│       ├── C0.nii.gz
│       └── C0_mask.nii.gz
├── 4_Res/            # 重采样后数据
│   └── patient_id/
│       ├── C0.nii.gz
│       └── C0_mask.nii.gz
└── 5_Norm/           # 归一化后数据
    └── patient_id/
        ├── C0.nii.gz
        └── C0_mask.nii.gz
```

## 使用示例

### 1. 处理所有患者

```python
# 通过MCP调用
result = await process_medical_images(
    data_root="/path/to/data",
    patient_id=None,  # 处理所有患者
    steps=None        # 执行所有步骤
)
```

### 2. 处理单个患者

```python
# 通过MCP调用
result = await process_medical_images(
    data_root="/path/to/data",
    patient_id="patient_001",
    steps=None
)
```

### 3. 执行特定步骤

```python
# 只执行DICOM转NII和分割
result = await process_medical_images(
    data_root="/path/to/data",
    patient_id="patient_001",
    steps=["dicom_to_nii", "nnunet_segmentation"]
)
```

### 4. 获取处理状态

```python
# 获取单个患者状态
status = await get_patient_status(
    data_root="/path/to/data",
    patient_id="patient_001"
)

# 获取所有患者状态
all_status = await get_patient_status(
    data_root="/path/to/data",
    patient_id=None
)
```

### 5. 检查数据目录结构

```python
# 检查数据目录结构
structure = await get_data_structure("/path/to/data")
print(structure)
```

## 进度跟踪

工具支持进度跟踪和状态反馈：

- 每个处理步骤都有开始、进行中、完成、失败等状态
- 支持进度百分比显示
- 提供详细的错误信息和日志

## 错误处理

- 自动检测输入文件是否存在
- 验证数据目录结构
- 提供详细的错误信息
- 支持步骤级别的错误处理

## 扩展性

### 添加新的处理步骤

1. 在 `ProcessingStep` 枚举中添加新步骤
2. 在 `MedicalImagePipeline` 类中实现对应的处理方法
3. 更新MCP工具接口

### 自定义处理逻辑

可以通过继承 `MedicalImagePipeline` 类来自定义处理逻辑：

```python
class CustomMedicalPipeline(MedicalImagePipeline):
    def _custom_step(self, patient_id: str, result: StepResult) -> StepResult:
        # 自定义处理逻辑
        pass
```

## 测试

运行单元测试：

```bash
python src/server_agent/tools/test_medical_tools.py
```

运行使用示例：

```bash
python src/server_agent/tools/example_usage.py
```

## 依赖

- SimpleITK
- nnUNet
- MONAI
- MCP (Model Context Protocol)
- asyncio
- pathlib

## 注意事项

1. 确保数据目录结构正确
2. 确保nnUNet模型已正确安装和配置
3. 处理大文件时注意内存使用
4. 建议在处理前备份原始数据
5. 支持Windows和Linux系统

## 故障排除

### 常见问题

1. **导入错误**: 确保所有依赖包已正确安装
2. **路径错误**: 检查数据目录路径是否正确
3. **权限问题**: 确保有读写数据目录的权限
4. **内存不足**: 处理大文件时可能需要更多内存

### 调试

启用详细日志：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 更新日志

- v1.0.0: 初始版本，支持完整的医学图像处理流程
- 支持MCP协议调用
- 支持进度跟踪和状态反馈
- 支持单患者和批量处理
- 支持步骤级别的控制