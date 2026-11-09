from pathlib import Path
import subprocess
S=Path('/home/shawrange/src/MNN-quant-gate2c3');R=Path('/mnt/e/DUANCE/gate2c3-quant')
p=S/'source/backend/cpu/compute/ConvInt8TiledExecutor.cpp'
assert subprocess.check_output(['git','-C',str(S),'rev-parse','HEAD']).decode().strip()=='7e3c6fb5225d3ccf22807ee641332669df34650d'
original=subprocess.check_output(['git','-C',str(S),'show','HEAD:source/backend/cpu/compute/ConvInt8TiledExecutor.cpp']).decode()
s=original.replace('#define WEIGHT_ONLINE_REORDER 8','#ifdef MNN_GATEC3_CAPTURE\n#include "GateC3Capture.hpp"\n#endif\n\n#define WEIGHT_ONLINE_REORDER 8')
needle='    mBlockNum = blockNum;\n\n    // backend info'
assert s.count(needle)==1
s=s.replace(needle,'''    mBlockNum = blockNum;
#ifdef MNN_GATEC3_CAPTURE
    if (oc == 2048 && ic == 1024 && quanCommon) {
        GateC3Capture record("load");
        record.number("ic", ic); record.number("oc", oc); record.number("blockNum", blockNum);
        record.number("canUseInt4", quanCommon->canUseInt4); record.number("originBits", quanCommon->originBits);
        record.number("asymmetric", quanCommon->asymmetric); record.number("alphaSize", quanCommon->alphaSize);
        record.number("alphaIsFp16", quanCommon->alphaIsFp16);
        record.blob("decoded_weight", quanCommon->weight.get(), quanCommon->weight.size());
        if (quanCommon->alpha.get()) record.blob("alpha", quanCommon->alpha.get(), quanCommon->alphaSize * 4);
        if (quanCommon->alphaHalf.get()) record.blob("alpha_half", quanCommon->alphaHalf.get(), quanCommon->alphaSize * 2);
        record.flush();
    }
#endif

    // backend info''')
needle='    auto dynamicOption = static_cast<CPUBackend*>(backend())->getRuntime()->hint().dynamicQuantOption % 8;'
assert s.count(needle)==1
s=s.replace(needle,needle+'''
#ifdef MNN_GATEC3_CAPTURE
    GateC3Capture c3("exec", input->channel() == 1024 && output->channel() == 2048);
    c3.number("bytes", gcore->bytes); c3.number("pack", gcore->pack);
    c3.number("plane", input->batch()*input->width()*input->height());
    c3.number("ic", input->channel()); c3.number("oc", output->channel());
    c3.number("dynamicOption", dynamicOption); c3.number("blockNum", mBlockNum); c3.number("inputBlockNum", mInputBlockNum);
    c3.number("im2colBasedInt8", mIm2ColBasedInt8); c3.number("useBatchQuan", mUseBatchQuan); c3.number("splitByOc", mSplitByOc);
    c3.number("weightQuantInfoMode", weightQuantInfoMode); c3.number("weightBits", mResourceInt8->mWeightBits);
    c3.number("UNIT", mGemmUnits[0]); c3.number("SRC_UNIT", mGemmUnits[1]); c3.number("DST_XUNIT", mGemmUnits[2]);
    c3.symbol("MNNAbsMax", (const void*)gcore->MNNAbsMax);
    c3.symbol("MNNQuantScale", (const void*)gcore->MNNQuantScale);
    c3.symbol("MNNDynamicQuant", (const void*)gcore->MNNDynamicQuant);
    c3.symbol("mGemmKernel", (const void*)mGemmKernel);
    c3.symbol("SumByAxis", (const void*)mRelatedFunctions.MNNSumByAxisLForMatmul_A);
    uint64_t fpcr=0; __asm__ volatile("mrs %0, fpcr" : "=r"(fpcr)); c3.number("FPCR", fpcr);
    c3.blob("entry_packed", input->host<uint8_t>(), size_t(input->batch())*input->width()*input->height()*ROUND_UP(input->channel(), gcore->pack)*gcore->bytes);
#endif''')
needle='        inputZero = 0;\n    };'
assert s.count(needle)==1
s=s.replace(needle,'''        inputZero = 0;
#ifdef MNN_GATEC3_CAPTURE
        if (c3.enabled()) {
            const auto tag = "q" + std::to_string(c3.nextQuant());
            c3.number(tag+"_LU", LU); c3.number(tag+"_EP", EP); c3.number(tag+"_LP", LP);
            c3.number(tag+"_threads", availableThreads); c3.number(tag+"_tId", tId); c3.number(tag+"_zero", inputZero);
            c3.blob(tag+"_pre", floatPtr, size_t(LU)*EP*LP*gcore->bytes);
            c3.blob(tag+"_absmax", maxPtr, availableThreads*EP*gcore->bytes);
            c3.blob(tag+"_qscale", quantPtr, EP*sizeof(float));
            c3.blob(tag+"_dscale", inputDequantScale, EP*sizeof(float));
            c3.blob(tag+"_integer", dstInt8, size_t(LU)*EP*LP);
        }
#endif
    };''')
needle='    if (compactWorkerFailed.load(std::memory_order_relaxed)) {\n        return NOT_SUPPORT;\n    }\n    if (m4BitPtq)'
assert s.count(needle)==1
s=s.replace(needle,'''#ifdef MNN_GATEC3_CAPTURE
    c3.blob("output_packed", output->host<uint8_t>(), size_t(plane)*ROUND_UP(output->channel(), PackUnit)*dstBytes);
    c3.blob("bias", mResourceInt8->mOriginBias->host<uint8_t>(), mResourceInt8->mOriginBias->size());
    c3.blob("relu", mResourceInt8->mReluThreshold.data(), 2*gcore->bytes);
    c3.blob("weight_packed", mResourceInt8->mWeightInt8->host<uint8_t>(), mResourceInt8->mWeightInt8->size());
    c3.flush();
#endif
'''+needle)
p.write_text(s)
(S/'source/backend/cpu/compute/GateC3Capture.hpp').write_bytes((R/'scripts/GateC3Capture.hpp').read_bytes())
print('Patched independent worktree only')
