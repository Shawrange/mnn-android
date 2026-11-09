#include "MNN_generated.h"
#include <fstream>
#include <iostream>
#include <iterator>
#include <vector>
int main(int argc,char** argv) {
    if(argc!=2)return 2;
    std::ifstream f(argv[1],std::ios::binary);std::vector<char> b((std::istreambuf_iterator<char>(f)),{});
    flatbuffers::Verifier verifier(reinterpret_cast<const uint8_t*>(b.data()),b.size());if(!MNN::VerifyNetBuffer(verifier))return 3;
    auto net=MNN::GetNet(b.data());std::cout<<"name\ttype\tweight_bits\treadType\tloader_asymmetric\toutput_c4\tkv_cache\n";
    for(auto op:*net->oplists()) {
        if(op->type()==MNN::OpType_Convolution) {
            auto q=op->main_as_Convolution2D()->quanParameter();
            if(q)std::cout<<op->name()->str()<<"\tConvolution\t"<<q->aMaxOrBits()<<'\t'<<q->readType()<<'\t'<<int(q->readType()!=0 || (q->type()==4&&q->aMin()==0&&q->quantScale()<1e-6f))<<"\t\t\n";
        } else if(op->type()==MNN::OpType_Attention) {
            auto a=op->main_as_AttentionParam();std::cout<<op->name()->str()<<"\tAttention\t\t\t\t"<<int(a->output_c4())<<'\t'<<int(a->kv_cache())<<'\n';
        }
    }
}
