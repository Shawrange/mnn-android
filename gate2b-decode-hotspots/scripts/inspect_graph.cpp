#include "MNN_generated.h"
#include <fstream>
#include <iostream>
#include <iterator>
#include <vector>
int main(int argc,char** argv) {
    if(argc!=2)return 2;
    std::ifstream in(argv[1],std::ios::binary);std::vector<char> b((std::istreambuf_iterator<char>(in)),{});
    flatbuffers::Verifier verifier(reinterpret_cast<const uint8_t*>(b.data()),b.size());
    if(!MNN::VerifyNetBuffer(verifier))return 3;
    auto net=MNN::GetNet(b.data());
    std::cout<<"name\ttype\tic\toc\tkx\tky\tquan_type\taMaxOrBits\treadType\tweightSize\texternal\tinput_indices\toutput_indices\n";
    for(auto op:*net->oplists()) {
        auto conv=op->main_as_Convolution2D();bool isConv=op->type()==MNN::OpType_Convolution;
        std::cout<<(op->name()?op->name()->str():"")<<'\t'<<MNN::EnumNameOpType(op->type());
        if(isConv && conv) {
            auto c=conv->common();auto q=conv->quanParameter();
            std::cout<<'\t'<<c->inputCount()<<'\t'<<c->outputCount()<<'\t'<<c->kernelX()<<'\t'<<c->kernelY();
            if(q)std::cout<<'\t'<<q->type()<<'\t'<<q->aMaxOrBits()<<'\t'<<q->readType()<<'\t'<<q->weightSize();
            else std::cout<<"\t-\t-\t-\t-";
            std::cout<<'\t';if(conv->external())for(auto n:*conv->external())std::cout<<n<<',';
        } else std::cout<<"\t\t\t\t\t\t\t\t\t";
        std::cout<<'\t';if(op->inputIndexes())for(auto i:*op->inputIndexes())std::cout<<i<<',';
        std::cout<<'\t';if(op->outputIndexes())for(auto i:*op->outputIndexes())std::cout<<i<<',';
        std::cout<<'\n';
    }
}
