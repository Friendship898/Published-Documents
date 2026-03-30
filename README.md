# PNG/JPG 颜色转换工具（v3）

本工具不再做“全量红色硬替换”，而是采用 **semantic_soft_recolor**：

- 分层识别红色光效 / 强调色与暗红材质
- 对洋红/粉红高亮做联动偏移
- 使用软掩码权重混合，避免硬边
- 增加亮度补偿，减少脏橙/土黄
- 全程保留 alpha 与原图尺寸

## 安装

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## CLI 用法

```bash
python main.py --input ./input_assets --output ./output_assets --source-color "#FF0000" --target-color "#FF8A00" --mode semantic_soft_recolor
```

### 参数

- `--input` 输入目录（必填，支持 png/jpg/jpeg）
- `--output` 输出目录（必填）
- `--source-color` 初始颜色（默认 `#FF0000`，即红色）
- `--target-color` 目标颜色（默认 `#FF8A00`，即橙色）
- `--mode` 处理模式（默认 `semantic_soft_recolor`）
- `--recursive` / `--no-recursive` 递归扫描开关
- `--dry-run` 只分析不写正式输出
- `--workers` 并发数
- `--preview [N]` 生成前 N 张 before/after 对照图（默认 5）
- `--preview-mask` 输出语义权重掩码图
- `--max-files` 仅处理前 N 张（0 表示全部）


## 打包为免环境依赖可执行文件

使用 `PyInstaller` 生成独立可执行文件（CLI / GUI），部署端无需 Python 环境。

```bash
pip install -r requirements-build.txt
python package.py --target all --clean-artifacts
```

可选参数：

- `--target cli|gui|all`：指定打包目标
- `--onedir`：生成目录模式（默认 onefile 单文件）
- `--clean-artifacts`：打包前清理 `build/` 与 `dist/`

默认产物：

- `dist/recolor-cli`（或 `recolor-cli.exe`）
- `dist/recolor-gui`（或 `recolor-gui.exe`）

## GUI 用法

```bash
python gui.py
```

界面支持：

- 输入/输出目录选择
- 模式选择（semantic_soft_recolor）
- 初始颜色与目标颜色设置
- 递归、dry-run、mask 预览
- 并发数、preview 数量、max-files 试跑
- 实时日志（processed / skipped / failed）

## 输出说明

- 正式输出：`<output>/<原目录结构>/*.(png|jpg|jpeg)`
- PNG 保留 alpha；JPG/JPEG 自动按 RGB 输出
- 对照预览：`<output>/_preview/.../*.png`（左 before，右 after）
- 掩码预览：`<output>/_mask_preview/.../*.png`（灰度权重）

## 代码结构

- `main.py`：CLI + 批处理调度 + preview 输出
- `processor.py`：文件级处理、RGBA 读写、结果数据结构
- `color_masks.py`：红光效/洋红联动/暗部抑制权重图
- `recolor.py`：软混合重着色 + 亮度补偿
- `gui.py`：可视化界面
- `requirements.txt`

## 日志字段

每个文件会输出：

- 文件路径
- 状态：`processed` / `skipped` / `failed`
- 初始色主区命中像素数 `source_pixels`
- 高亮联动区命中像素数 `highlight_pixels`
- 输出路径
- 错误信息
