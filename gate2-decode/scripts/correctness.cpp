#include "llm/llm.hpp"
#include <fstream>
#include <memory>
using namespace MNN::Transformer;
int main(int argc,char** argv) {
    if(argc!=4) return 2;
    std::unique_ptr<Llm> llm(Llm::createLLM(argv[1]));
    if(!llm || !llm->set_config(R"({"backend_type":"cpu","thread_num":4,"precision":"low","memory":"low","power":"normal","dynamic_option":0,"attention_mode":8,"use_mmap":false,"async":false,"reuse_kv":false,"sampler_type":"greedy","ignore_eos":true,"tmp_path":"tmp"})")) return 3;
    if(!llm->load()) return 4;
    llm->tuning(OP_ENCODER_NUMBER,{1,5,10,20,30,50,100});
    std::string kind=argv[2],prefix=argv[3];
    if(kind=="synthetic") llm->response(std::vector<int>(128,16),nullptr,nullptr,256);
    else llm->response(std::string(u8"请用中文详细解释为什么大语言模型在生成文本时需要保存历史Key和Value，以及这会如何影响长文本推理。请给出完整示例。"),nullptr,nullptr,256);
    auto c=llm->getContext();
    std::ofstream tokens(prefix+".tokens.txt");
    for(auto t:c->output_tokens) tokens<<t<<'\n';
    std::ofstream text(prefix+".text.txt",std::ios::binary); text<<c->generate_str;
    std::ofstream meta(prefix+".meta.txt");
    meta<<"status="<<int(c->status)<<"\nprompt="<<c->prompt_len<<"\ngenerated="<<c->gen_seq_len<<"\nkv="<<llm->getCurrentHistory()<<"\n";
    return c->status==LlmStatus::MAX_TOKENS_FINISHED && c->output_tokens.size()==256 ? 0 : 5;
}
