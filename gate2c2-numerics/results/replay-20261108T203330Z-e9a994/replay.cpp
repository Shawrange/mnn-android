#include <MNN/Interpreter.hpp>
#include <MNN/Tensor.hpp>
#include "MNN_generated.h"
#include "core/TensorUtils.hpp"
#include "core/Backend.hpp"
#include "json.hpp"
#include <fstream>
#include <memory>
#include <iterator>
#include <cstring>
using namespace MNN;
using json=nlohmann::json;
static void write(const std::string& path,const Tensor& t){std::ofstream f(path,std::ios::binary);f.write(t.host<char>(),t.elementSize()*4);if(!f)throw std::runtime_error("write failed");}
int main(int argc,char** argv){
    if(argc!=8)return 2;
    std::string model=argv[1],backend=argv[2],precision=argv[3],memory=argv[4],input=argv[5],prefix=argv[6];int batch=std::atoi(argv[7]);
    std::ifstream f(model,std::ios::binary);std::vector<char> bytes((std::istreambuf_iterator<char>(f)),{});
    flatbuffers::Verifier verifier((const uint8_t*)bytes.data(),bytes.size());if(!VerifyNetBuffer(verifier))return 3;
    auto net=GetNet(bytes.data());const Op* q=nullptr;
    for(auto op:*net->oplists())if(op->name() && op->name()->str()=="/layers.0/self_attn/q_proj/Linear")q=op;
    if(!q||q->type()!=OpType_Convolution||q->inputIndexes()->size()!=1||q->outputIndexes()->size()!=1)return 4;
    std::string in=net->tensorName()->Get(q->inputIndexes()->Get(0))->str(),out=net->tensorName()->Get(q->outputIndexes()->Get(0))->str();
    std::unique_ptr<Interpreter> interpreter(Interpreter::createFromFile(model.c_str()));if(!interpreter)return 5;
    interpreter->setExternalFile((model+".weight").c_str());interpreter->setSessionMode(Interpreter::Session_Resize_Defer);
    interpreter->setSessionHint(Interpreter::DYNAMIC_QUANT_OPTIONS,0);
    ScheduleConfig config;BackendConfig bc;bc.precision=precision=="low"?BackendConfig::Precision_Low:BackendConfig::Precision_High;
    bc.memory=memory=="low"?BackendConfig::Memory_Low:BackendConfig::Memory_High;
    config.type=backend=="cpu"?MNN_FORWARD_CPU:MNN_FORWARD_OPENCL;config.numThread=backend=="cpu"?4:580;config.backendConfig=&bc;
    config.path.mode=ScheduleConfig::Path::Tensor;config.path.inputs={in};config.path.outputs={out};config.saveTensors={out};
    auto session=interpreter->createSession(config);if(!session)return 6;
    auto it=interpreter->getSessionInput(session,in.c_str());if(!it)return 7;
    interpreter->resizeTensor(it,{batch,1024,1,1});interpreter->resizeSession(session);
    Tensor host(it,Tensor::CAFFE);std::ifstream src(input,std::ios::binary);src.read(host.host<char>(),host.elementSize()*4);if(src.gcount()!=host.elementSize()*4)return 8;
    if(!it->copyFromHostTensor(&host))return 9;
    Tensor back(it,Tensor::CAFFE);if(!it->copyToHostTensor(&back))return 10;write(prefix+".input.f32",back);
    json meta={{"input_name",in},{"output_name",out},{"op",q->name()->str()},{"precision",precision},{"memory",memory},{"input_shape",host.shape()},{"runs",json::array()}};
    for(int i=0;i<3;++i){
        json ops=json::array();auto code=interpreter->runSessionWithCallBackInfo(session,[](const std::vector<Tensor*>&,const OperatorInfo*){return true;},[&](const std::vector<Tensor*>& ts,const OperatorInfo* info){
            auto bn=TensorUtils::getDescribeOrigin(ts.at(0))->getBackend();ops.push_back({{"name",info->name()},{"type",info->type()},{"backend_type",bn?int(bn->type()):-1}});return true;},true);
        auto ot=interpreter->getSessionOutput(session,out.c_str());if(!ot||code!=NO_ERROR)return 11;
        int wait=ot->wait(Tensor::MAP_TENSOR_READ,true);Tensor result(ot,Tensor::CAFFE);if(!ot->copyToHostTensor(&result)||wait!=0)return 12;
        write(prefix+".r"+std::to_string(i)+".f32",result);
        meta["runs"].push_back({{"exit_code",int(code)},{"wait",wait},{"ops",ops},{"shape",result.shape()}});
        if(ops.size()!=1||ops[0]["name"]!=q->name()->str())return 13;
    }
    std::ofstream m(prefix+".meta.json");m<<meta.dump(2);return 0;
}
