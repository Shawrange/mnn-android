#include "llm/llm.hpp"
#include <MNN/expr/ExecutorScope.hpp>
#include "core/TensorUtils.hpp"
#include "core/Backend.hpp"
#include "json.hpp"
#include <fstream>
#include <memory>
#include <cmath>
#include <cstring>
#include <set>
using namespace MNN;
using namespace MNN::Transformer;
using json=nlohmann::json;
struct Snapshot {std::string key; json meta; std::vector<float> data;};
static void writeData(const std::string& path,const std::vector<float>& data) {
    std::ofstream f(path,std::ios::binary);f.write((const char*)data.data(),data.size()*sizeof(float));
    if(!f)throw std::runtime_error("write failed: "+path);
}
static json stats(const std::vector<float>& x) {
    int nf=0,halfgrid=0;double mn=INFINITY,mx=-INFINITY;
    for(float f:x){if(!std::isfinite(f)){++nf;continue;}mn=std::min(mn,double(f));mx=std::max(mx,double(f));if(float((_Float16)f)==f)++halfgrid;}
    return {{"elements",x.size()},{"nonfinite",nf},{"min",mn},{"max",mx},{"exact_half_fraction",double(halfgrid)/x.size()}};
}
int main(int argc,char** argv) {
    if(argc!=8)return 2;
    std::string backend=argv[2],precision=argv[3],kind=argv[4],mode=argv[5],prefix=argv[6];
    int repeats=std::atoi(argv[7]);bool debug=mode=="checkpoints";
    if((precision!="low"&&precision!="high")||repeats<1)return 2;
    std::unique_ptr<Llm> llm(Llm::createLLM(argv[1]));if(!llm)return 3;
    json config={{"backend_type",backend},{"precision",precision},{"thread_num",4},{"memory","low"},{"power","normal"},
        {"sampler_type","greedy"},{"ignore_eos",true},{"async",false},{"reuse_kv",false},{"use_mmap",false},
        {"dynamic_option",0},{"attention_mode",8},{"tmp_path","tmp"},{"enable_debug",debug},{"all_logits",false}};
    if(!llm->set_config(config.dump()))return 3;
    std::vector<Snapshot> snapshots;std::set<std::string> captured;bool capture=false;json inventory=json::array();
    std::set<std::string> selected={"/input_layernorm/Mul_1_output_0","/layers.0/self_attn/q_proj/Linear",
        "/layers.0/self_attn/k_proj/Linear","/layers.0/self_attn/v_proj/Linear","Attention/Reshape_8_output_0",
        "/Add_4_output_0","hidden_states","/norm/Mul_1_output_0","/lm/lm_head/Linear"};
    auto copy=[&](const std::string& key,Tensor* t,const OperatorInfo* op,const char* phase){
        if(captured.count(key))throw std::runtime_error("duplicate checkpoint: "+key);
        captured.insert(key);
        if(t->getType().code!=halide_type_float || t->getType().bits!=32)throw std::runtime_error("nominal type not f32");
        auto bn=TensorUtils::getDescribeOrigin(t)->getBackend();
        int wait=t->wait(Tensor::MAP_TENSOR_READ,true);
        Tensor host(t,Tensor::CAFFE);bool copied=t->copyToHostTensor(&host);
        if(!copied || !host.host<float>() || wait!=0)throw std::runtime_error("checkpoint copy/wait failed");
        Snapshot s;s.key=key;s.data.assign(host.host<float>(),host.host<float>()+host.elementSize());
        s.meta={{"key",key},{"op_name",op->name()},{"op_type",op->type()},{"phase",phase},{"backend_type",bn?int(bn->type()):-1},
            {"source_shape",t->shape()},{"source_format",int(TensorUtils::getDescribe(t)->dimensionFormat)},
            {"host_shape",host.shape()},{"host_format","NCHW"},{"host_type","float32"},{"nominal_type_bits",t->getType().bits},
            {"wait_result",wait},{"copy_succeeded",copied},{"stats",stats(s.data)}};
        snapshots.push_back(std::move(s));
    };
    if(debug)llm->setDebugCallback([&](const std::vector<Tensor*>& ts,const OperatorInfo* op){
        if(capture && op->name()=="/input_layernorm/Mul_1_output_0" && !ts.empty())copy("embedding_on_backend",ts[0],op,"before");
        if(capture && op->name()=="/layers.0/self_attn/q_proj/Linear" && !ts.empty())copy("q_input",ts[0],op,"before");
        return true;
    },[&](const std::vector<Tensor*>& ts,const OperatorInfo* op){
        if(capture){inventory.push_back({{"name",op->name()},{"type",op->type()}});
            if(selected.count(op->name()) && !ts.empty()){
                std::string key=op->name();for(char& c:key)if(c=='/'||c=='.')c='_';copy(key,ts[0],op,"after");}}
        return true;
    });
    if(!llm->load())return 4;
    auto activation=llm->getExecutor()->activte();
    std::vector<int> ids=kind=="synthetic"?std::vector<int>(8,16):llm->tokenizer_encode(llm->apply_chat_template(std::string(u8"你好，请说明人工智能。")));
    std::ofstream idsfile(prefix+".ids.json");idsfile<<json(ids).dump(2);idsfile.close();
    std::ofstream cfg(prefix+".config.json");cfg<<llm->dump_config();cfg.close();
    // Warmup executes the same full prefill; reuse_kv=false clears state on the next response.
    llm->response(ids,nullptr,nullptr,0);
    json runs=json::array();
    for(int r=0;r<repeats;++r){
        snapshots.clear();captured.clear();inventory=json::array();capture=debug;
        llm->response(ids,nullptr,nullptr,0);capture=false;
        auto out=llm->getOutputs();if(out.empty())return 5;
        auto info=out[0]->getInfo();if(!info||info->type.code!=halide_type_float||info->type.bits!=32)return 6;
        const float* a=out[0]->readMap<float>();if(!a)return 7;
        std::vector<float> logits(a,a+info->size);
        const float* b=out[0]->readMap<float>();bool stable=b && !std::memcmp(logits.data(),b,logits.size()*4);
        auto c=llm->getContext();
        std::string p=prefix+".r"+std::to_string(r);
        writeData(p+".logits.f32",logits);
        json meta={{"repeat",r},{"shape",info->dim},{"order",int(info->order)},{"type","float32"},
            {"read_twice_identical",stable},{"prompt_len",c->prompt_len},{"generated",c->gen_seq_len},
            {"all_seq_len",c->all_seq_len},{"kv_history",llm->getCurrentHistory()},{"status",int(c->status)},
            {"stats",stats(logits)},{"checkpoints",json::array()}};
        for(auto& s:snapshots){writeData(p+"."+s.key+".f32",s.data);meta["checkpoints"].push_back(s.meta);}
        std::ofstream mf(p+".meta.json");mf<<meta.dump(2);
        if(debug){std::ofstream inv(p+".ops.json");inv<<inventory.dump(2);}
        if(!stable || info->dim!=std::vector<int>({1,1,151936}) || c->gen_seq_len!=0 || c->prompt_len!=ids.size() || llm->getCurrentHistory()!=ids.size() || stats(logits)["nonfinite"]!=0)return 8;
        runs.push_back(meta);
    }
    std::ofstream summary(prefix+".summary.json");summary<<json({{"backend",backend},{"precision",precision},{"mode",mode},{"repeats",runs}}).dump(2);
    return 0;
}
