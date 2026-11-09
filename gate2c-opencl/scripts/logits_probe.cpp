#include "llm/llm.hpp"
#include <MNN/expr/ExecutorScope.hpp>
#include <fstream>
#include <memory>
#include <cmath>
using namespace MNN::Transformer;
int main(int argc,char** argv) {
    if(argc!=5)return 2;
    std::string backend=argv[2],kind=argv[3],prefix=argv[4];
    std::unique_ptr<Llm> llm(Llm::createLLM(argv[1]));
    if(!llm)return 3;
    if(!llm->set_config(R"({"thread_num":4,"precision":"low","memory":"low","power":"normal","sampler_type":"greedy","ignore_eos":true,"async":false,"reuse_kv":false,"use_mmap":false,"dynamic_option":0,"attention_mode":8,"tmp_path":"tmp"})"))return 3;
    if(!llm->set_config("{\"backend_type\":\""+backend+"\"}"))return 3;
    if(!llm->load())return 4;
    auto activation=llm->getExecutor()->activte();
    std::vector<int> ids;
    if(kind=="synthetic")ids=std::vector<int>(8,16);
    else ids=llm->tokenizer_encode(llm->apply_chat_template(std::string(u8"你好，请说明人工智能。")));
    llm->response(ids,nullptr,nullptr,0);
    auto outputs=llm->getOutputs();if(outputs.empty())return 5;
    auto info=outputs[0]->getInfo();if(!info)return 5;
    const float* values=outputs[0]->readMap<float>();if(!values)return 5;
    std::ofstream in(prefix+".ids.txt");for(int t:ids)in<<t<<'\n';
    std::ofstream binary(prefix+".logits.f32",std::ios::binary);binary.write(reinterpret_cast<const char*>(values),info->size*sizeof(float));
    int nonfinite=0;for(int i=0;i<info->size;++i)nonfinite+=!std::isfinite(values[i]);
    std::ofstream meta(prefix+".meta.txt");meta<<"elements="<<info->size<<"\nprompt="<<llm->getContext()->prompt_len<<"\nkv="<<llm->getCurrentHistory()<<"\nnonfinite="<<nonfinite<<"\ntype_code="<<int(info->type.code)<<"\ntype_bits="<<int(info->type.bits)<<"\nshape=";
    for(auto dim:info->dim)meta<<dim<<',';meta<<'\n';
    std::ofstream cfg(prefix+".config.json");cfg<<llm->dump_config();
    return info->size>=151936 && nonfinite==0 && info->type.code==halide_type_float && info->type.bits==32?0:6;
}
