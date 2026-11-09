# GitHub 归档说明

GitHub 展示版对应冻结实验归档，目标仓库为 `Shawrange/mnn-android`。本次只整理文档和版本管理，没有新增推理实验。

## 仓库内容

保留实验脚本、C++ 诊断工具和补丁、报告、原始测量/数值/质量结果、clean 与诊断二进制。模型图和 Tokenizer 随原模型文件保留，完整大权重不上传。没有将上游 MNN 的完整 Git 数据库纳入项目历史。

以下文件仍留在原开发环境，由 `.gitignore` 排除：

|内容|获取方式|
|---|---|
|Linux Android NDK r27c 安装包|`gate0/download_ndk.py`、`gate0/install_ndk.sh`；版本校验记录在 `gate0/evidence/installation`|
|Qwen3-0.6B-MNN 大权重|`gate0/download_model.py`；模型锁见 `gate0/evidence/model/model-lock.json`|
|上游 Git 副本|`gate0/checkout_source.sh`；固定提交见下方|
|手机 vendor 驱动二进制|使用目标设备自带 OpenCL 库；仓库保留能力探针及 ELF 检查结果|
|重复交付 zip / Python 缓存|不是复现所需输入|

源码：`https://github.com/alibaba/MNN`，commit `7e3c6fb5225d3ccf22807ee641332669df34650d`。

模型：`https://huggingface.co/taobao-mnn/Qwen3-0.6B-MNN`，revision `34dfccda1187ded6e07ea06426da576b0b793c6b`。权重 SHA256：`953afb7e0165818add34a7a6caf0af5d0ed9428da102eb22c9b98ee9da292e9f`。

原构建/运行脚本含本机 Windows 和 WSL 路径，换机器运行时需要在新实验副本中调整；不要覆盖归档数据。

## 冻结快照与展示文档

根目录的 `PROJECT_FREEZE.json` 和 `project-manifest.json` 保留原版本。冻结时的 README 和校验程序原文存放在 `publication/frozen/`，文件哈希仍须匹配旧清单；当前 README 是后续面向 GitHub 阅读的改写版本。

`publication.json` 记录这些路径映射及新文档哈希。校验程序会同时检查原冻结内容和本次文档，不通过重写旧清单掩盖变更。

```powershell
# 完整本地归档：包括下载依赖和模型权重
python -B verify_project.py

# GitHub 克隆：只允许跳过明确列出的未上传文件，其他缺失仍报错
python -B verify_project.py --available
```

离线测试可直接执行，无需连接手机。需要重新跑统计或真机实验时，建议使用新的工作副本；原始数据保持不变。
