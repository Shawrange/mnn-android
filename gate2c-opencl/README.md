# Gate2-C0/C1 OpenCL可行性

入口：[报告](Gate2C_OpenCL可行性报告.md)、[后端机制与源码](后端选择机制与源码入口.md)、[正确性计划](GPU正确性对照计划.md)、[NPU静态调查](Hexagon与QNN静态调查.md)。GPU执行已确认，Logits初筛未通过，暂不进入性能基线或优化。

## 文件位置

- `evidence/prior-stage-hashes.json`：之前四阶段5,756个文件的保护快照，不重新生成。
- `evidence/source/`：固定提交45份源码/文档及manifest。
- `evidence/build/clean`、`profile`：完整CMake/Ninja命令/日志/退出码/cache/ELF/哈希/与CPU差异。
- `evidence/driver-elf/`：只读拉取的两份设备vendor库及ELF依赖检查，不用于覆盖driver。
- `evidence/npu-static/`：模型量化/C4属性、FlatBuffer验证和SDK配置状态，只读，无NPU执行。
- `staging/clean`、`profile`：两份新MNN产物；`cl_probe`、`logits_probe`为独立小工具。
- `results/probe-*`：驱动Platform/Device/extensions/算术kernel原始日志。
- `results/clean-*`：一次配置错误和一次成功模型烟测，错误虽exit0但semantic_success=false；raw全保留。
- `results/profile-*`：事件及回退诊断烟测、help、运行日志与配置。
- `results/logits-*`：CPU归档库/GPU clean库的两个小Prefill输入、完整logits/ids/meta/配置和原始退出码。
- `analysis/`：GPU事件计数、运行语义分类、Logits数值分析；不建立性能样本池。
- `experiment-config.json`：本轮真实条件及继承metadata标签更正，原会话protocol不改。

## 当前机器复现

所有路径为本机已固定环境；换主机需调整新目录脚本中的WSL源码/NDK、Windows ADB/serial、模型路径。不要改原CPU脚本或资产。

Windows工作目录 `E:\DUANCE`：

```powershell
wsl -d Ubuntu -- bash -lc "ANDROID_NDK=/home/shawrange/Android/android-ndk-r27c bash /mnt/e/DUANCE/gate2c-opencl/scripts/build_opencl.sh /home/shawrange/src/MNN-3.6.2 /home/shawrange/src/MNN-3.6.2/build-android-arm64-opencl-gate2c-new"
```

诊断构建使用 `build_opencl_profile.sh` 和另一个全新build目录。原目录已有CMakeCache会拒绝；`stage.py`默认收集本次实际目录，复现新目录时先调整其路径。构建参数和程序输入不自动优化。

```powershell
wsl -d Ubuntu -- bash /mnt/e/DUANCE/gate2c-opencl/scripts/build_probe.sh
wsl -d Ubuntu -- python3 /mnt/e/DUANCE/gate2c-opencl/scripts/stage.py clean
wsl -d Ubuntu -- python3 /mnt/e/DUANCE/gate2c-opencl/scripts/stage.py profile
python -B gate2c-opencl/scripts/run.py probe
python -B gate2c-opencl/scripts/run.py clean
python -B gate2c-opencl/scripts/run.py profile
wsl -d Ubuntu -- bash /mnt/e/DUANCE/gate2c-opencl/scripts/build_logits_probe.sh
python -B gate2c-opencl/scripts/run_logits.py
python -B gate2c-opencl/scripts/compare_logits.py
wsl -d Ubuntu -- bash /mnt/e/DUANCE/gate2c-opencl/scripts/inspect_npu_model.sh
wsl -d Ubuntu -- python3 /mnt/e/DUANCE/gate2c-opencl/scripts/inspect_sdk.py
python -B gate2c-opencl/scripts/analyze.py
python -B gate2c-opencl/scripts/write_report.py
python -B gate2c-opencl/scripts/verify.py
```

每次ADB运行新建UTC+UUID目录，不覆盖旧结果。首次错误保留并停止；timeout后需确认远端进程已结束再重试，不能自动叠加运行。分析器会遍历本项目的会话，复现新实验时用新独立目录或明确筛选，不能新增条件后混池沿用本报告。

`prepare.py`仅为首次保护快照/构建脚本生成器，**不要再次覆盖保护哈希**。`collect_source.py`用git show核对固定提交；`inspect_driver.py`另存设备依赖与CLI help。完整性的true不意味着numerical_screening通过，见verification-summary的分项结果。

只使用Python标准库、现有WSL g++/NDK/CMake/Ninja和ADB；未安装额外OpenCL SDK或QNN/Hexagon SDK。NPU缺失配置和后续验证方法见静态调查。没有Root、SELinux修改、DSP自定义库编译或GPU/NPU性能优化。
