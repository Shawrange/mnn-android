#include "llm/llm.hpp"
#include <MNN/expr/ExecutorScope.hpp>
#include <chrono>
#include <fstream>
#include <memory>
#include <unordered_map>
#include <pthread.h>
#include <cstdio>
#include <ctime>
using namespace MNN::Transformer;
using Clock=std::chrono::steady_clock;
static uint64_t stamp() { return std::chrono::duration_cast<std::chrono::nanoseconds>(Clock::now().time_since_epoch()).count(); }
struct Record { uint32_t op, token; uint64_t start, ns; };
struct Meta { std::string name,type,inputs,outputs; };
static std::string shapes(const std::vector<MNN::Tensor*>& ts) {
    std::string s;
    for(auto t:ts) { if(!s.empty())s+=';';s+='[';for(int i=0;i<t->dimensions();++i){if(i)s+=',';s+=std::to_string(t->length(i));}s+=']'; }
    for(char& c:s)if(c=='\t'||c=='\n'||c=='\r')c=' ';
    return s;
}
int main(int argc,char** argv) {
    if(argc==2 && std::string(argv[1])=="--clock") {
        timespec boot;clock_gettime(CLOCK_BOOTTIME,&boot);
        std::printf("%llu %llu\n",(unsigned long long)stamp(),(unsigned long long)(uint64_t(boot.tv_sec)*1000000000ULL+boot.tv_nsec));return 0;
    }
    if(argc!=7)return 2;
    std::string kind=argv[2],mode=argv[4],prefix=argv[5];
    int tg=std::atoi(argv[3]);bool correctness=std::atoi(argv[6])!=0,profile=mode=="detail";
    if(tg<=0 || (mode!="off"&&!profile))return 2;
    std::vector<Record> records;std::vector<Meta> metadata;
    std::unordered_map<const MNN::OperatorInfo*,uint32_t> ids;
    if(profile) { records.reserve(500000);metadata.reserve(4096);ids.reserve(4096); }
    bool active=false;uint32_t current=0;uint64_t start=0;int token=0,depth=0,nested=0,foreign=0,dropped=0,newMeasured=0;
    pthread_t owner=pthread_self();
    std::unique_ptr<Llm> llm(Llm::createLLM(argv[1]));
    if(!llm || !llm->set_config(R"({"backend_type":"cpu","thread_num":4,"precision":"low","memory":"low","power":"normal","dynamic_option":0,"attention_mode":8,"use_mmap":false,"async":false,"reuse_kv":false,"sampler_type":"greedy","ignore_eos":true,"tmp_path":"tmp"})"))return 3;
    if(profile) {
        llm->set_config(R"({"enable_debug":true})");
        llm->setDebugCallback([&](const std::vector<MNN::Tensor*>& in,const MNN::OperatorInfo* info){
            if(!pthread_equal(owner,pthread_self()))++foreign;
            if(depth++)++nested;
            auto found=ids.find(info);
            if(found==ids.end()) {
                current=metadata.size();ids[info]=current;
                std::string name=info->name(),type=info->type();
                for(char& c:name)if(c=='\t'||c=='\n'||c=='\r')c=' ';
                metadata.push_back({name,type,shapes(in),""});
                if(active)++newMeasured;
            } else current=found->second;
            token=llm->getContext()->gen_seq_len;
            if(active)start=stamp();
            return true;
        },[&](const std::vector<MNN::Tensor*>& out,const MNN::OperatorInfo*){
            for(auto t:out)t->wait(MNN::Tensor::MAP_TENSOR_READ,true);
            uint64_t end=active?stamp():0;
            if(active) {
                if(records.size()<records.capacity())records.push_back({current,uint32_t(token),start,end-start});
                else ++dropped;
            }
            if(metadata[current].outputs.empty())metadata[current].outputs=shapes(out);
            --depth;return true;
        });
    }
    if(!llm->load())return 4;
    auto activation=llm->getExecutor()->activte();
    llm->tuning(OP_ENCODER_NUMBER,{1,5,10,20,30,50,100});
    auto response=[&](){
        if(kind=="synthetic")llm->response(std::vector<int>(128,16),nullptr,nullptr,tg);
        else llm->response(std::string(u8"请用中文详细解释为什么大语言模型在生成文本时需要保存历史Key和Value，以及这会如何影响长文本推理。请给出完整示例。"),nullptr,nullptr,tg);
    };
    if(!correctness)response();
    active=true;auto wall=stamp();response();wall=stamp()-wall;active=false;
    auto c=llm->getContext();
    std::ofstream tokens(prefix+".tokens.txt");for(auto t:c->output_tokens)tokens<<t<<'\n';
    std::ofstream text(prefix+".text.txt",std::ios::binary);text<<c->generate_str;
    std::ofstream cfg(prefix+".config.json");cfg<<llm->dump_config();
    std::ofstream summary(prefix+".summary.txt");
    summary<<"status="<<int(c->status)<<"\nprompt="<<c->prompt_len<<"\ngenerated="<<c->gen_seq_len<<"\nkv="<<llm->getCurrentHistory()<<"\nprefill_us="<<c->prefill_us<<"\ndecode_us="<<c->decode_us<<"\nresponse_wall_ns="<<wall<<"\nrecords="<<records.size()<<"\nnested="<<nested<<"\nforeign="<<foreign<<"\ndropped="<<dropped<<"\nnew_metadata_measured="<<newMeasured<<"\n";
    if(profile) {
        std::ofstream meta(prefix+".ops.tsv");meta<<"id\tname\ttype\tinputs\toutputs\n";
        for(size_t i=0;i<metadata.size();++i) { auto& m=metadata[i];meta<<i<<'\t'<<m.name<<'\t'<<m.type<<'\t'<<m.inputs<<'\t'<<m.outputs<<'\n'; }
        std::ofstream trace(prefix+".calls.csv");trace<<"op,token,start_ns,ns\n";
        for(auto& r:records)trace<<r.op<<','<<r.token<<','<<r.start<<','<<r.ns<<'\n';
    }
    return c->status==LlmStatus::MAX_TOKENS_FINISHED && c->output_tokens.size()==size_t(tg) && !nested && !foreign && !dropped ? 0 : 5;
}
