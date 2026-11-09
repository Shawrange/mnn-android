#include "llm/llm.hpp"
#include <MNN/expr/ExecutorScope.hpp>
#include "json.hpp"
#include <fstream>
#include <memory>
#include <cmath>
#include <cstring>
using namespace MNN::Transformer;
using json=nlohmann::json;
static json load(const std::string& p){std::ifstream f(p);json j;f>>j;return j;}
static void save(const std::string& p,const json& j){std::ofstream f(p);f<<j.dump(2,' ',false,json::error_handler_t::replace);if(!f)throw std::runtime_error("write failed");}
static void bytes(const std::string& p,const char* v,size_t n){std::ofstream f(p,std::ios::binary);f.write(v,n);if(!f)throw std::runtime_error("write failed");}
int main(int argc,char** argv){
    if(argc!=7)return 2;
    std::string backend=argv[2],prefix=argv[5],mode=argv[6];auto settings=load(argv[3]);auto request=load(argv[4]);
    std::unique_ptr<Llm> llm(Llm::createLLM(argv[1]));if(!llm)return 3;
    // Preserve the pinned model's complete Jinja template; only supply its documented context.
    auto cfg=json::parse(llm->dump_config());
    if(!cfg.contains("jinja")||!cfg["jinja"].contains("chat_template"))return 3;
    auto jinja=cfg["jinja"];jinja["context"]["enable_thinking"]=false;settings["jinja"]=jinja;settings["backend_type"]=backend;
    if(!llm->set_config(settings.dump())||!llm->load())return 4;
    auto activation=llm->getExecutor()->activte();
    std::string rendered=llm->apply_chat_template(request["input"].get<std::string>());
    if(rendered.size()<20||rendered.find("<think>\n\n</think>\n\n")==std::string::npos)return 5;
    auto prompt=llm->tokenizer_encode(rendered);std::vector<int> ids=prompt;
    size_t initialKV=llm->getCurrentHistory();if(initialKV!=0)return 6;
    if(mode=="logits"){
        auto suffix=request.value("prefix_ids",std::vector<int>{});ids.insert(ids.end(),suffix.begin(),suffix.end());
    }
    if(ids.empty()||ids.size()>=2048)return 7;
    save(prefix+".input_ids.json",ids);save(prefix+".prompt_ids.json",prompt);save(prefix+".config.json",json::parse(llm->dump_config()));
    bytes(prefix+".rendered_prompt.txt",rendered.data(),rendered.size());
    json meta={{"id",request["id"]},{"backend",backend},{"mode",mode},{"initial_kv",initialKV},{"input_len",ids.size()},{"prompt_len",prompt.size()},{"thinking",false}};
    if(mode=="generate"){
        llm->response(ids,nullptr,nullptr,96);auto c=llm->getContext();
        auto out=c->output_tokens;bool stopped=!out.empty()&&llm->is_stop(out.back());
        save(prefix+".output_ids.json",out);bytes(prefix+".text.txt",c->generate_str.data(),c->generate_str.size());
        meta.update({{"status",int(c->status)},{"stopped",stopped},{"generated_count",out.size()},{"gen_seq_len",c->gen_seq_len},{"kv_after",llm->getCurrentHistory()},{"stop_token",stopped?out.back():-1}});
        save(prefix+".meta.json",meta);
        return c->status==LlmStatus::NORMAL_FINISHED||c->status==LlmStatus::MAX_TOKENS_FINISHED?0:8;
    }
    if(mode!="logits")return 2;
    llm->response(ids,nullptr,nullptr,0);auto outputs=llm->getOutputs();if(outputs.empty())return 9;
    auto info=outputs[0]->getInfo();if(!info||info->type.code!=halide_type_float||info->type.bits!=32)return 10;
    const float* f=outputs[0]->readMap<float>();if(!f||info->dim!=std::vector<int>({1,1,151936}))return 11;
    std::vector<float> values(f,f+info->size);int bad=0;for(float x:values)bad+=!std::isfinite(x);
    bytes(prefix+".logits.f32",(const char*)values.data(),values.size()*4);
    bool stable=!std::memcmp(values.data(),outputs[0]->readMap<float>(),values.size()*4);
    auto reference=request.value("reference",std::string());auto refFull=llm->tokenizer_encode(rendered+reference);bool refPrefix=refFull.size()>=prompt.size()&&std::equal(prompt.begin(),prompt.end(),refFull.begin());
    std::vector<int> refIds;if(refPrefix)refIds.assign(refFull.begin()+prompt.size(),refFull.end());
    save(prefix+".reference_ids.json",refIds);
    // Decode candidates for human-readable diagnostics, including possibly partial UTF-8 tokens.
    std::vector<int> order(values.size());for(size_t i=0;i<order.size();++i)order[i]=i;
    std::partial_sort(order.begin(),order.begin()+5,order.end(),[&](int a,int b){return values[a]>values[b]||(values[a]==values[b]&&a<b);});
    json candidates=json::array();for(int i=0;i<5;++i)candidates.push_back({{"id",order[i]},{"text",llm->tokenizer_decode(order[i])}});
    meta.update({{"shape",info->dim},{"host_type","float32"},{"nonfinite",bad},{"read_twice_identical",stable},{"kv_after",llm->getCurrentHistory()},{"generated_count",llm->getContext()->gen_seq_len},{"reference_prompt_prefix_matches",refPrefix},{"top5_text",candidates}});
    save(prefix+".meta.json",meta);
    return bad==0&&stable&&llm->getCurrentHistory()==ids.size()&&llm->getContext()->gen_seq_len==0?0:12;
}
