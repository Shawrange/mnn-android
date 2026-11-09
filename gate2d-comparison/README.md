# Gate 2-D｜有限CPU/OpenCL执行成本比较

固定版本、固定模型、三负载×两后端×六独立进程。质量验收未通过，本轮仅比较硬件执行成本。先读[报告](Gate2D_CPU_GPU性能对照报告.md)、[冻结协议](protocol.md)和[源码计时边界](源码与指标边界.md)。项目结束状态见根目录PROJECT_FREEZE.json。

## 结果复核：不需要手机

在 `E:\DUANCE`、Python 3.12标准库环境执行：

```powershell
python -B E:/DUANCE/gate2d-comparison/scripts/test_analysis.py
python -B E:/DUANCE/gate2d-comparison/scripts/analyze.py
python -B E:/DUANCE/gate2d-comparison/scripts/verify.py
python -B E:/DUANCE/verify_project.py
```

分析只读原始结果，重建analysis统计文件；项目最终manifest会校验结果内容。请勿更改正式protocol、数据或脚本。要复现实验，应复制项目到新目录，保留本次归档，只在新的运行批次重新配置路径并记录不同session；不要删除本项目FORMAL_STARTED或freeze标记来追加样本。

## 本轮实际执行流程

1. `scripts/prepare.py`：保护此前17,089文件、复制归档干净CPU/OpenCL库和CLI、生成新配置。
2. `scripts/run.py deploy`：新手机目录部署，验证本机/设备模型、二进制、配置SHA256。
3. 少量Pilot，保留初始GPU缓存创建；`scripts/fix_pilot_path.py`记录一次CLI路径元数据纠正，不覆盖首次Pilot。
4. WSL执行 `scripts/build_probe.sh`；`run.py count`核验真实count、输出IDs与KV重置。probe仅是功能工具，未用于正式性能统计。
5. `test_analysis.py`；`freeze.py`冻结协议、顺序、配置、脚本、clean产物；`run.py formal`仅允许一个36进程会话。
6. `analyze.py`、`summarize_state.py`、`write_reports.py`生成统计和报告；核查旧证据、冻结全项目。不再推理。

原始文件在results各session；`FORMAL_STARTED.json`指向唯一正式会话，`freeze.json`记录冻结时间、成功Pilot和功能检查。每样本有完整benchmark.command/stdout/stderr/exit、原生JSON、前后state、cooling记录及sample.json。首次Pilot错误的原记录保留，由`evidence/path-compatibility/pilot-review.json`明确标记不能用于比较。

构建证据在evidence/build及elf/environment日志；新源码快照和manifest在evidence/source；原始模型锁仍在gate0。本轮不重编译Runtime。依赖普通Windows ADB、Python；独立功能probe用WSL/NDK r27c构建。脚本没有Root/锁频/修改安全配置操作。
