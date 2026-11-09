#ifndef GATE_C3_CAPTURE_HPP
#define GATE_C3_CAPTURE_HPP
#include <cstdlib>
#include <cstdint>
#include <cstring>
#include <dlfcn.h>
#include <fstream>
#include <string>
#include <vector>
#include <mutex>
// Diagnostic build only. Copy during execution, write only once execution has ended.
class GateC3Capture {
    struct Blob {std::string name;std::vector<char> bytes;};
    std::string mPrefix,mMeta;std::vector<Blob> mBlobs;std::mutex mMutex;int mQuant=0;
public:
    GateC3Capture(const char* phase,bool allowed=true) {
        const char* p=std::getenv("MNN_GATEC3_PREFIX");if(p && *p && allowed)mPrefix=std::string(p)+"."+phase;
    }
    bool enabled()const{return !mPrefix.empty();}
    int nextQuant(){std::lock_guard<std::mutex> lock(mMutex);return mQuant++;}
    template<class T>void number(const std::string& name,T value){if(!enabled())return;std::lock_guard<std::mutex> lock(mMutex);mMeta+=name+"\t"+std::to_string(value)+"\n";}
    void symbol(const char* name,const void* ptr){if(!enabled())return;Dl_info info{};dladdr(ptr,&info);number(std::string(name)+"_offset",uintptr_t(ptr)-uintptr_t(info.dli_fbase));std::lock_guard<std::mutex> lock(mMutex);mMeta+=std::string(name)+"_symbol\t"+(info.dli_sname?info.dli_sname:"")+"\n";}
    void blob(const std::string& name,const void* data,size_t size){if(!enabled()||!data||!size)return;Blob b;b.name=name;b.bytes.resize(size);std::memcpy(b.bytes.data(),data,size);std::lock_guard<std::mutex> lock(mMutex);mBlobs.push_back(std::move(b));}
    void flush(){if(!enabled())return;for(auto& b:mBlobs){std::ofstream f(mPrefix+"."+b.name+".bin",std::ios::binary);f.write(b.bytes.data(),b.bytes.size());}std::ofstream meta(mPrefix+".meta.tsv");meta<<mMeta;meta<<"quant_calls\t"<<mQuant<<'\n';}
};
#endif
