# MinerU 使用指南

将 PDF 论文转换为 Markdown + 图片资源 + 页面结构记录，统一并入
`cases/<case-id>/normalized/`，供 AI 审稿、拆分单元、source mapping 和
作者版页码/行号意见生成使用。

- 上游项目：https://github.com/opendatalab/MinerU
- 本仓库入口脚本：`scripts/mineru_case_extract.sh`
- 专用环境：Linux 服务器上的 conda env `mineru312`（RTX 5090，CUDA 12.8）

---

## 1. 何时使用

需要把 `cases/<case-id>/source/*.pdf` 转成审稿用 Markdown 时使用。

产物应遵循 review case 约定：

```
cases/<case-id>/normalized/manuscript.md
cases/<case-id>/normalized/<stem>.assets/images/*.jpg
cases/<case-id>/normalized/<stem>.assets/*_content_list.json
cases/<case-id>/normalized/<stem>.assets/*_middle.json
cases/<case-id>/normalized/<stem>.assets/*_layout.pdf
cases/<case-id>/provenance/source_map.jsonl
```

Markdown 内图片链接应改写成 `<stem>.assets/images/...`。`*_content_list.json`
和 `*_middle.json` 必须保留，因为它们是 PDF 页码 / 版面框 / Markdown 文本之间
的 provenance 桥。

---

## 2. 运行位置

**必须在 Linux 服务器（ubuntu-303 / tailscale-ubuntu）上运行**。原因：

- PDF 解析需要 GPU（RTX 5090）
- 模型已缓存在 `/home/flemyng/.cache/modelscope/hub/models/OpenDataLab/`
- Linux 侧仓库工作副本应位于 `/home/flemyng/Code/review-council/`

Mac 端通过 SMB 访问这份代码时，**不要在 Mac 上跑脚本**——没有 CUDA 的 PyTorch + SMB I/O 会同时失败。

---

## 3. 日常使用

在 Linux 端：

```bash
cd ~/Code/review-council
bash scripts/mineru_case_extract.sh cases/<case-id>/source/<论文文件名>.pdf cases/<case-id>
```

脚本会：

1. 激活 `mineru312` 环境（若尚未激活）
2. 调用官方 CLI：`mineru -p <pdf> -o <tmp> -l en -b hybrid-auto-engine`
3. 把 `<tmp>/<stem>/hybrid_auto/` 下的产物搬到 `cases/<case-id>/normalized/`
4. 把图片引用改写成本仓库惯例
5. 保留 content-list / middle / layout PDF
6. 生成或辅助生成 `provenance/source_map.jsonl`
7. 清理临时目录

后端说明：

- `hybrid-auto-engine`（默认）——局部 VLM + 传统 pipeline 混合，公式/表格质量最好。适合科研 PDF
- `pipeline`——纯传统 OCR + 版面分析，CPU 可跑但质量较差
- `vlm-auto-engine`——纯 VLM，速度稍慢但对复杂版面鲁棒

---

## 4. 一次性安装（已完成，仅备查）

若未来需要在新机器重建此环境：

```bash
# 创建 env
conda create -n mineru312 python=3.12 -y

# 关键：屏蔽 user-site 污染（系统上装过其他版本 mineru 时必须）
conda env config vars set PYTHONNOUSERSITE=1 -n mineru312
conda activate mineru312

# 先装匹配 Blackwell (sm_120) 的 torch（cu128 wheel）
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu128

# 再装 mineru 全部可选依赖
pip install -U "mineru[all]"

# 下载模型（pipeline + vlm 全套，约 3 GB，从 modelscope 更快）
mineru-models-download -s modelscope -m all
```

**陷阱备注：**

- 不加 `PYTHONNOUSERSITE=1`，`~/.local/lib/python3.12/site-packages` 会污染新 env，导致 pip 看见旧 torch / 旧 mineru
- `pip install "mineru[all]"` 会因 vllm 依赖把 torch 锁到 2.9.x；这是正常的，它仍然是 cu128 变体，RTX 5090 可用
- 必须用 cu128（或更高）轮子；cu124/121 在 Blackwell 上会 `no kernel image is available`

模型配置文件落盘在 `~/mineru.json`，记录了缓存路径与默认源。

---

## 5. 环境变量

脚本内置的默认值，可在调用前覆写：

| 变量 | 默认 | 作用 |
|------|------|------|
| `MINERU_ENV` | `mineru312` | conda env 名 |
| `CONDA_BASE` | `~/miniconda3` | conda 安装根 |
| `MINERU_MODEL_SOURCE` | `modelscope` | 模型来源；境外机器可改 `huggingface` |

---

## 6. 故障排查

**"no kernel image is available for execution on the device"**
→ torch 轮子不匹配 GPU。确认 `torch.version.cuda` ≥ 12.8，且 torch 是 `+cu128` 而非 `+cpu`。

**脚本提示 "no <stem>.md produced"**
→ MinerU 真的失败了。查看上方日志；常见原因：模型未下载完整（重跑 `mineru-models-download -s modelscope -m all`）、PDF 文件损坏、扫描件应加 `-m ocr`。

**`modelscope` 下载卡住**
→ 切换 `MINERU_MODEL_SOURCE=huggingface` 重试（前提是有代理，本机通过 SSH remote forward 的 `:7897` 端口可用）。

**产物图片链接是 `images/xxx.jpg` 而不是 `<stem>.assets/images/xxx.jpg`**
→ 说明脚本中的 `sed` 改写没生效，请检查 `scripts/mineru_case_extract.sh` 是否被就地修改过。

**MinerU 原始输出目录结构发生变化（未来版本升级后）**
→ 当前脚本使用 `find` 定位 `<stem>.md`，对 `auto/`、`hybrid_auto/`、`vlm_auto/` 等子目录命名都兼容。如果上游又改了布局，按实际子目录名调整 `find` 的 `-maxdepth`。

---

## 7. 与 source mapping 的关系

MinerU 输出的 Markdown 只解决“可读文本”。审稿意见要返回页码/行号，还需要
`docs/source_mapping_protocol.md` 定义的 source map。

最小流程：

```bash
PYTHONPATH=src python -m review_council.cli index-markdown \
  cases/<case-id>/normalized/manuscript.md \
  cases/<case-id>/provenance/source_map.jsonl
```

这只能生成 Markdown 行号 fallback。更好的 PDF 页码映射应从 MinerU 的
`*_content_list.json` / `*_middle.json` 解析页面和 bbox 后生成。若自动行号不可靠，
作者版意见必须标注为 `p. X` 或人工校正后的行号，不得伪造精确行号。

## 8. 与其他文档的关系

- 本指南专注"如何把 PDF 变成 Markdown"
- source mapping 与作者版页码/行号意见见 `docs/source_mapping_protocol.md`
- 服务器通用操作（SSH、tmux、路径约定）见 NAS-303 共享文件夹；仓库内入口见 `docs/303硬件与基础设施说明.md`
- 审稿 case 目录规则见 `docs/paper_ingestion_protocol.md`
