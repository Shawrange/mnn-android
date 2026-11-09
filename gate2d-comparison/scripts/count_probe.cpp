// Functional contract check only; never used for formal performance samples.
#include "llm/llm.hpp"
#include <MNN/expr/ExecutorScope.hpp>
#include "json.hpp"
#include <fstream>
#include <memory>
using namespace MNN::Transformer;
using json=nlohmann::json;
int main(int argc,char** argv) {
    if(argc!=4)return 2;
    std::unique_ptr<Llm> llm(Llm::createLLM(argv[1]));
    if(!llm||!llm->load())return 3;
    auto activation=llm->getExecutor()->activte();
    llm->tuning(OP_ENCODER_NUMBER,{1,5,10,20,30,50,100});
    json all=json::array();
    for(auto pair:std::vector<std::pair<int,int>>{{32,64},{128,64},{128,256}}) {
        for(int repeat=0;repeat<2;++repeat) {
            if(std::string(argv[2])=="opencl")llm->switchMode(Llm::Prefill);
            std::vector<int> ids(pair.first,16);
            llm->response(ids,nullptr,nullptr,pair.second);
            auto c=llm->getContext();
            all.push_back({{"pp",pair.first},{"tg",pair.second},{"repeat",repeat},{"input_ids",ids},
                {"gen_seq_len",c->gen_seq_len},{"output_ids",c->output_tokens},{"status",int(c->status)},
                {"kv_after",llm->getCurrentHistory()},{"prefill_us",c->prefill_us},{"decode_us",c->decode_us}});
            if(c->status!=LlmStatus::MAX_TOKENS_FINISHED||c->gen_seq_len!=pair.second||c->output_tokens.size()!=pair.second)return 4;
        }
    }
    std::ofstream f(argv[3]);f<<json{{"config",json::parse(llm->dump_config())},{"runs",all}}.dump(2);
    return f?0:5;
}
