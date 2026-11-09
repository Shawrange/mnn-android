# Hexagon与QNN静态可行性调查

只读固定提交源码与文档，不下载SDK、不构建DSP库、不运行NPU。当前主线仍是同一端侧Runtime项目。

## 两条路径不同

|项|MNN直接Hexagon|MNN QNN SDK后端|
|---|---|---|
|后端标识|`MNN_HEXAGON=ON`，backend_type=hexagon，枚举10|`MNN_QNN=ON`，backend_type=qnn，枚举16；不要用npu/NN=5冒充|
|计算实现|MNN自有HTP/HVX等命令与算子，FastRPC送往DSP skeleton|调用QNN SDK接口创建/读取图及graphExecute，使用QNN HTP实现|
|开发依赖|构建自定义DSP库需要Hexagon SDK及对应DSP工具链；Android host MNN部分可使用仓库已有stub/header，不代表DSP库已准备|QNN/QAIRT SDK的include/QNN与对应架构库；CMake读QNN_SDK_ROOT（CMake变量优先于环境）|
|设备库|`libMNN_htpops.so` host stub、`libMNN_htpops_skel.so`或版本化skeleton、FastRPC/CDSP库与访问能力|online通常libQnnHtp、对应v79 Stub/Skel、libQnnHtpPrepare；offline使用libQnnSystem替换Prepare等，按SDK/产物实际依赖验证|
|模型流|按MNN Hexagon支持的算子、布局/量化构建命令；不是QNN在线/离线转换的别名|在线构图：常规模型静态图，runtime graphCreate/finalize；离线：x86_64 Linux MNN2QNNModel/脚本生成bin与替代Plugin模型，支持有限shape组合及部分LLM|
|加载环境|普通库路径和ADSP_LIBRARY_PATH定位DSP skeleton，仍需设备允许执行；不绕过权限|普通库路径/ADSP路径依部署和SDK；offline plugin在CPU backend上调QNN context，所以配置CPU本身不表示实际计算在CPU|

源码：`llm.cpp:41–60`、`MNNForwardType.h:38–59`、`source/backend/hexagon/README.md:5–66`、`HexagonRuntime.cpp:489–526`（FastRPC和dlopen自定义stub）、`source/backend/qnn/CMakeLists.txt:25–35,70–80`、`QNNUtils.cpp:164–182`（dlopen libQnnHtp/取providers）、`QNNBackend.cpp:1698–1744,1944–1948`（反序列化/graphExecute）、`:3413–3443`（online create/finalize）。

`docs/inference/npu.md:47–53`将8 Elite列为SOC ID69、Hexagon ARCH79。这是固定版本文档映射，本轮未查询/运行NPU验证，不等于证明本机NPU访问权限或SDK兼容已通过。

## 在线与离线QNN不能混淆

- `docs/inference/npu.md:74–117`：online使用MNN_QNN=ON、CONVERT_MODE=OFF、WITH_PLUGIN=OFF，明确type16；Module shapeMutable=false。启动需构图/编译，不能套用offline启动行为。
- `docs/inference/npu.md:124–140`：host转换库CONVERT_MODE=ON；device运行CONVERT_MODE=OFF、WITH_PLUGIN=ON，读取目标SoC/DSP的bin与替代模型。Plugin登记CPU，所以需结合Plugin/QNN执行证据判定实际落点。
- `docs/transformers/llm.md:1247–1266,1269–1437`给出LLM专用校准/导出和QNN模型生成、依赖部署步骤。不能把一个已有动态KV模型直接换backend字符串认定为QNN LLM可运行。
- 同提交 `source/backend/qnn/README.md`的旧online示例写NN=5，与当前枚举/`backend_type_convert("qnn")`及npu.md不一致；本研究采用真实代码的QNN=16，不把旧片段当新接口。

## 当前模型的实查属性

独立FlatBuffer verifier与只读解析得到：

- 197个量化Convolution：196个4bit，词表头1个8bit。
- 197个quan.readType均非零；按 `ConvolutionCommon.cpp:788–793` 的真实loader规则，它们被解释为asymmetric权重。
- 28个Attention的output_c4均false，kv_cache均true。

逐节点数据在 `evidence/npu-static/model-properties.tsv`，不是根据文件名猜导出参数。

`docs/transformers/llm.md:121–136` 推荐Hexagon LLM使用4bit对称量化、block64、Transformer C4，说明output_c4=false不在其支持组合内。现模型**不满足该文档的推荐组合**。

但同一固定提交的实际源码已经更广：`HexagonConvolution.cpp:1135–1195,1221–1248,1276–1285,1355`包含W4/W8及部分block-asymmetric处理；不能仅依据位宽/asymmetric就断言所有Hexagon Runtime路径绝对不支持。`HexagonAttention::onBuildCmd` (`HexagonAttention.cpp:218–244,382–404`) 还按实际tensor维度/布局/字节宽度拒绝组合，其普通LLM分支要求packed V和输出，具体geometry转换能否满足必须另行核对/实测。

因此本轮结论是：**当前模型尚不能按文档直接宣称Hexagon兼容；源码和文档支持面有差异，需独立模型/布局验证。QNN同样未转换、未校准/构图、未执行，兼容性待验证。** 没有把CPU/GPU模型直接改配置当作NPU通过，也没有制造一个未经运行验证的绝对“不支持”结论。

## 当前依赖准备情况与验证方法

`evidence/npu-static/sdk-state.json`显示本WSL会话QNN_SDK_ROOT/QNN_ROOT/HEXAGON_SDK_ROOT均未配置，默认htp-ops-lib/outputs不存在。仅检查这些已知位置，不声称扫描全电脑后证明SDK绝对不存在。

后续若启动NPU阶段，需先验证：

1. SDK版本及 `QNN_SDK_ROOT/include/QNN/QnnInterface.h`、host x86_64工具、aarch64库和hexagon-v79 unsigned skeleton是否存在；用 `test -f`、工具`--help`和SHA256逐项记录。
2. Hexagon SDK编译器/工具链和目标v79支持；当前阶段不执行`htp-ops-lib/build.sh`。MNN自定义stub/skeleton的版本必须成对。
3. MNN2QNNModel/LLM专用导出工具、校准数据及新模型资产锁；不得覆盖当前模型Revision。逐项验证量化/激活精度、C4/shape/算子支持。
4. 设备普通权限能否加载库与访问DSP；只在授权的新阶段做官方烟测，失败保存实际错误，不关闭SELinux、不Root。

当前没有完成这些依赖准备、NPU构建或运行，故不能将静态调查写为NPU可用性通过。OpenCL已可运行，本轮无需以NPU“兜底成功”为目标。
