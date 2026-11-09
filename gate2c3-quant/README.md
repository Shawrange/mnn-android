# Gate2-C3：第一层Q动态输入量化独立验证

[报告](Gate2C3_动态量化数值验证报告.md)｜[精确计算契约与源码](精确计算契约与源码位置.md)｜[实验协议](protocol.md)｜[核验结果](verification-summary.json)。结论A：按真实量化、ARMV86各tile后处理及FP16输出复算，两个输入全部结果精确一致；结束此算子定位，不修改Runtime。

## 证据位置

- `evidence/prior-hashes.json`：开始时保护8971个旧文件，不得重写。
- `evidence/source`：18个固定提交文件快照及manifest。
- `evidence/diagnostic.patch`、`diagnostic-source`、`source-state.json`：独立分支源码修改和补丁，原工作树tracked clean。
- `evidence/build`：configure/build原始日志及退出码、CMakeCache、Ninja命令、ELF、库哈希；link map为实际地址映射，重新链接前后库哈希一致。
- `evidence/weight`：第一Q原始权重段/alpha/零Bias/FlatBuffer元数据及主机独立解码。
- `evidence/inputs`：C2原始固定q_input、IDs与元数据的独立拷贝，原文件保持不变。
- `results/q-only-*`：10配置进程，保存3次完整输入回读、实际输出、ops/shape/backend、日志/退出码/设备状态；diag-on另含全部trace buffer及实际函数地址/FPCR。
- `references/{synthetic,natural}`：A64、B64 ideal、B32 prehalf、B16 contract、重建INT8/scale及独立INT32 block dot/sum。
- `evidence/reference-attempt1`：未模拟真实TILE_1的初版参照源程序、可执行文件及原始输出，不用容差静默掩盖6处差异。
- `analysis/results.json`、`errors.csv`：全部数值范围、逐项功能核验、函数映射、诊断墙钟时间、初版差异清单。
- `evidence/environment`：开发/设备信息、最终设备库哈希。UTC命名与原时间戳原样保存。
- `artifact-manifest.sha256.json`：本项目文件哈希。

`.bin`原始类型由trace meta及契约说明：entry/pre为FP16 NC8 `[128,N,8]`；q_integer为INT8同布局；qscale/dscale为N个FP32；absmax为N个FP16；output为FP16 `[256,N,8]`；prepared weight为`[256,16,320]` uint8。`.f32/.f64/.i8/.i32`无头、小端；独立参照输出canonical `[N,2048]`，I32 dot为`[N,16,2048]`。

## 本机复现

工作目录`E:\DUANCE`；使用既有Linux NDK r27c/g++、Python标准库和已安装NumPy、Windows ADB serial ee19377b。无需下载依赖。换机只改新项目副本路径，不能改旧模型/脚本。

独立诊断worktree已创建为 `/home/shawrange/src/MNN-quant-gate2c3`、分支 `feature/quant-gate2c3-diagnostic`。首次创建应基于固定commit；`instrument.py`只作用该目录，`build_diagnostic.sh`必须用全新构建目录。不要对原CPU构建执行它。

```powershell
# 已有诊断分支可用；新建时先核对固定commit并应用保存的patch。
wsl -d Ubuntu -- bash /mnt/e/DUANCE/gate2c3-quant/scripts/build_replay.sh
wsl -d Ubuntu -- bash /mnt/e/DUANCE/gate2c3-quant/scripts/extract_weight.sh
python -B gate2c3-quant/scripts/decode_weight.py
wsl -d Ubuntu -- bash /mnt/e/DUANCE/gate2c3-quant/scripts/build_reference.sh
python -B gate2c3-quant/scripts/run.py
python -B gate2c3-quant/scripts/run_reference.py
python -B gate2c3-quant/scripts/analyze.py
python -B gate2c3-quant/scripts/write_report.py
python -B gate2c3-quant/scripts/verify.py
```

重建诊断库示例（新目录；脚本拒绝现有CMakeCache）：

```powershell
wsl -d Ubuntu -- bash -lc "ANDROID_NDK=/home/shawrange/Android/android-ndk-r27c bash /mnt/e/DUANCE/gate2c3-quant/scripts/build_diagnostic.sh /home/shawrange/src/MNN-quant-gate2c3 /home/shawrange/src/MNN-quant-gate2c3/build-c3-new"
```

`stage.py`读取本轮固定build目录，换新目录时先调整其路径并重新保存库/日志/hash；地址核查需同一库的link map，不能直接沿用原偏移。重新采集会生成新UUID会话；分析器显式选择最新completed会话并逐项验证入口/量化中间值，报告需重新生成。失败与超时不进入有效数据；先确认远端进程结束再重试。

`prepare.py`只用于首次保护快照，不再运行。`collect_source.py`用git show验证，`capture_environment.py`保存当前设备状态/库哈希；它们均已真实执行。原模型和正式库只读，新构建和新部署目录隔离。当前研究已得到A停止条件，以上命令用于审查/复现，不代表建议继续扩展实验。
