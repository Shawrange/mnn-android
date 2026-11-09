#include "MNN_generated.h"
#include "json.hpp"
#include <fstream>
#include <iterator>
#include <vector>
#include <string>
using json=nlohmann::json;
int main(int argc,char** argv){
    if(argc!=4)return 2;std::string model=argv[1],weight=argv[2],prefix=argv[3];
    std::ifstream f(model,std::ios::binary);std::vector<char> bytes((std::istreambuf_iterator<char>(f)),{});
    flatbuffers::Verifier v((uint8_t*)bytes.data(),bytes.size());if(!MNN::VerifyNetBuffer(v))return 3;
    auto net=MNN::GetNet(bytes.data());const MNN::Op* q=nullptr;
    for(auto op:*net->oplists())if(op->name()&&op->name()->str()=="/layers.0/self_attn/q_proj/Linear")q=op;
    if(!q)return 4;auto c=q->main_as_Convolution2D();auto z=c->quanParameter();
    std::vector<int64_t> ext(c->external()->begin(),c->external()->end());
    json m={{"op",q->name()->str()},{"ic",c->common()->inputCount()},{"oc",c->common()->outputCount()},
      {"external",ext},{"quant_type",z->type()},{"readType",z->readType()},{"aMin",z->aMin()},{"aMaxOrBits",z->aMaxOrBits()},
      {"quantScale",z->quantScale()},{"has_scaleInt",z->has_scaleInt()},{"shapeInt32",z->shapeInt32()},
      {"scaleStorage",int(z->scaleStorage())},{"relu",c->common()->relu()},{"relu6",c->common()->relu6()}};
    std::ifstream w(weight,std::ios::binary);w.seekg(ext[0]);
    const char* names[]={"raw_weight","raw_alpha","raw_bias"};
    for(size_t i=1;i<ext.size()&&i<=3;++i){std::vector<char> b(ext[i]);w.read(b.data(),b.size());if(w.gcount()!=b.size())return 5;std::ofstream out(prefix+"."+names[i-1]+".bin",std::ios::binary);out.write(b.data(),b.size());}
    std::vector<float> bias;if(c->bias())bias.assign(c->bias()->begin(),c->bias()->end());
    std::ofstream bf(prefix+".inline_bias.f32",std::ios::binary);bf.write((const char*)bias.data(),bias.size()*4);m["inline_bias_elements"]=bias.size();
    std::ofstream out(prefix+".meta.json");out<<m.dump(2);return 0;
}
