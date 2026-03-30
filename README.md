# PNG 红色转橙色批量工具

读取 RGBA PNG，在 HSV 中识别红色区域，将其色相映射到橙色，保留亮度、饱和度和透明度后输出 PNG。

## 功能

- 只处理 `.png`
- 只改红色区域，其他颜色不变
- 尺寸保持不变
- 输出仍为 PNG
- 保留 alpha 透明通道
- 支持递归处理目录
- 支持并发处理、dry-run、单文件失败隔离

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## 用法

```bash
python main.py --input ./input_png --output ./output_png --target-color "#FF8A00"
```

### 参数

- `--input` 输入目录（必填）
- `--output` 输出目录（必填）
- `--target-color` 目标颜色，默认 `#FF8A00`
- `--recursive` 递归扫描（默认开启）
- `--dry-run` 仅检测不写文件
- `--workers` 并发数（默认 4）

## 日志字段

每个文件至少输出：

- 文件路径
- 状态：`processed` / `skipped` / `failed`
- 命中红色像素数
- 输出路径
- 错误信息（失败时）

## 处理逻辑说明

1. 扫描输入目录中的 PNG
2. 以 RGBA 读取
3. 转为 HSV（向量化 numpy 实现）
4. 根据阈值识别红色区域（处理色相环绕）
5. 将命中区域的色相替换为目标橙色色相
6. 保留原有饱和度、明度、透明度
7. 输出到目标目录并保持原有目录结构

> 默认阈值在 `processor.py` 的 `HSVThreshold` 中，可按素材微调。
