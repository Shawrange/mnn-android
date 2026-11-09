from pathlib import Path
import subprocess, shutil, json, hashlib
S=Path('/home/shawrange/src/MNN-decode-gate2a')
OUT=Path('/mnt/e/DUANCE/gate2-decode/evidence/source')
files=['transformers/llm/engine/src/speculative_decoding/generate.cpp','transformers/llm/engine/src/llm.cpp','transformers/llm/engine/src/kvmeta.hpp','transformers/llm/engine/include/llm/llm.hpp','transformers/llm/engine/tools/llm_bench.cpp','source/backend/cpu/CPUAttention.cpp','source/backend/cpu/CPUKVCacheManager.cpp','source/backend/cpu/CPUKVCacheManager.hpp','source/core/KVCacheManager.hpp','include/MNN/AutoTime.hpp']
assert subprocess.check_output(['git','-C',str(S),'rev-parse','HEAD']).decode().strip()=='7e3c6fb5225d3ccf22807ee641332669df34650d'
assert not subprocess.check_output(['git','-C',str(S),'status','--porcelain','--untracked-files=no']).strip()
for f in files:
    d=OUT/'clean'/f;d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(S/f,d)
header=r'''#pragma once
#ifdef MNN_GATE2_TRACE
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <ctime>
namespace MNN { namespace Gate2 {
inline uint64_t now(clockid_t id = CLOCK_MONOTONIC) {
    timespec t; clock_gettime(id, &t); return uint64_t(t.tv_sec)*1000000000ULL+t.tv_nsec;
}
struct Step {
    int response, token, id, before, after, attentionCount, kvCount;
    uint64_t start, wall, cpu, attention, alloc, realloc, update;
};
struct Event { int response, token, before, after, past, disk; uintptr_t manager; uint64_t ns; };
struct State {
    bool enabled, active = false;
    const char* prefix;
    int response = 0, count = 0, events = 0, dropped = 0;
    Step rows[8192] = {};
    Event growth[8192] = {};
    State() : prefix(std::getenv("MNN_GATE2_TRACE_PREFIX")) { enabled = prefix && prefix[0]; }
    ~State() {
        if (!enabled) return;
        char path[1024]; std::snprintf(path,sizeof(path),"%s.steps.csv",prefix);
        FILE* f = std::fopen(path,"w"); if (!f) return;
        std::fprintf(f,"response,token,token_id,kv_before,kv_after,attention_count,kv_count,start_ns,wall_ns,caller_cpu_ns,attention_ns,alloc_ns,realloc_ns,update_ns\n");
        for (int i=0;i<count;++i) { const auto& s=rows[i];
            std::fprintf(f,"%d,%d,%d,%d,%d,%d,%d,%llu,%llu,%llu,%llu,%llu,%llu,%llu\n",s.response,s.token,s.id,s.before,s.after,s.attentionCount,s.kvCount,(unsigned long long)s.start,(unsigned long long)s.wall,(unsigned long long)s.cpu,(unsigned long long)s.attention,(unsigned long long)s.alloc,(unsigned long long)s.realloc,(unsigned long long)s.update);
        } std::fclose(f);
        std::snprintf(path,sizeof(path),"%s.growth.csv",prefix); f=std::fopen(path,"w"); if (!f) return;
        std::fprintf(f,"response,token,capacity_before,capacity_after,past_before,in_disk,manager,ns\n");
        for (int i=0;i<events;++i) { const auto& e=growth[i];
            std::fprintf(f,"%d,%d,%d,%d,%d,%d,%llu,%llu\n",e.response,e.token,e.before,e.after,e.past,e.disk,(unsigned long long)e.manager,(unsigned long long)e.ns);
        } std::fclose(f);
        std::snprintf(path,sizeof(path),"%s.status.txt",prefix); f=std::fopen(path,"w");
        if (f) { std::fprintf(f,"responses=%d\nsteps=%d\nevents=%d\ndropped=%d\n",response,count,events,dropped); std::fclose(f); }
    }
};
inline State& state() { static State s; return s; }
inline Step* current() { auto& s=state(); return s.enabled && s.active ? &s.rows[s.count] : nullptr; }
inline void response() { auto& s=state(); if(s.enabled) ++s.response; }
struct Token {
    Step* p = nullptr;
    uint64_t cpu = 0;
    Token(int token,int id,int before) {
        auto& s=state(); if (!s.enabled) return;
        if(s.count>=8192) { ++s.dropped; return; }
        p=&s.rows[s.count]; p->response=s.response; p->token=token; p->id=id; p->before=before;
        s.active=true; cpu=now(CLOCK_THREAD_CPUTIME_ID); p->start=now();
    }
    void finish(int after) {
        if(!p) return;
        p->wall=now()-p->start; p->cpu=now(CLOCK_THREAD_CPUTIME_ID)-cpu; p->after=after;
        auto& s=state(); s.active=false; ++s.count; p=nullptr;
    }
    ~Token() { if(p) finish(-1); }
};
struct Attention {
    Step* p; uint64_t start;
    Attention() : p(current()), start(p ? now() : 0) {}
    ~Attention() { if(p) { p->attention+=now()-start; ++p->attentionCount; } }
};
template<class T> struct KV {
    Step* p; T* manager; int kind,cap,past; uint64_t start;
    KV(T* m,int k) : p(current()),manager(m),kind(k),cap(p?m->maxLength():0),past(p?m->kvLength():0),start(p?now():0) {}
    ~KV() {
        if(!p) return;
        uint64_t ns=now()-start;
        if(kind==0) p->alloc+=ns; else if(kind==1) p->realloc+=ns; else { p->update+=ns; ++p->kvCount; }
        if(cap!=manager->maxLength()) {
            auto& s=state(); if(s.events>=8192) { ++s.dropped; return; }
            s.growth[s.events++]={p->response,p->token,cap,manager->maxLength(),past,manager->inDisk()?1:0,reinterpret_cast<uintptr_t>(manager),ns};
        }
    }
};
} }
#endif
'''
(S/'include/MNN/Gate2Trace.hpp').write_text(header)
def edit(file,old,new):
    p=S/file;t=p.read_text();assert t.count(old)==1,(file,old,t.count(old));p.write_text(t.replace(old,new))
g=files[0]
edit(g,'#include "generate.hpp"','#include "generate.hpp"\n#include <MNN/Gate2Trace.hpp>')
edit(g,'void ArGeneration::generate(GenerationParams& param) {','void ArGeneration::generate(GenerationParams& param) {\n#ifdef MNN_GATE2_TRACE\n    MNN::Gate2::response();\n#endif')
edit(g,'        // Decode and Output\n        MNN::Timer _t;','        // Decode and Output\n#ifdef MNN_GATE2_TRACE\n        MNN::Gate2::Token traceToken(len+1, mContext->current_token, mLlm->getCurrentHistory());\n#endif\n        MNN::Timer _t;')
edit(g,'        mContext->decode_us += _t.durationInUs();','        mContext->decode_us += _t.durationInUs();\n#ifdef MNN_GATE2_TRACE\n        traceToken.finish(mLlm->getCurrentHistory());\n#endif')
f='source/backend/cpu/CPUAttention.cpp'
edit(f,'#include "CPUAttention.hpp"','#include "CPUAttention.hpp"\n#include <MNN/Gate2Trace.hpp>')
edit(f,'ErrorCode CPUAttention::onExecute(const std::vector<Tensor*>& inputs, const std::vector<Tensor*>& outputs) {','ErrorCode CPUAttention::onExecute(const std::vector<Tensor*>& inputs, const std::vector<Tensor*>& outputs) {\n#ifdef MNN_GATE2_TRACE\n    MNN::Gate2::Attention traceAttention;\n#endif')
f='source/backend/cpu/CPUKVCacheManager.cpp'
edit(f,'#include "CPUKVCacheManager.hpp"','#include "CPUKVCacheManager.hpp"\n#include <MNN/Gate2Trace.hpp>')
for kind,sig in enumerate(['void CPUKVCacheManager::onAlloc(KVMeta* meta, int seq_len) {','void CPUKVCacheManager::onRealloc(KVMeta* meta) {','void CPUKVCacheManager::onUpdateKV(const Tensor* key, const Tensor* value, int add) {']):
    edit(f,sig,sig+f'\n#ifdef MNN_GATE2_TRACE\n    MNN::Gate2::KV<CPUKVCacheManager> traceKV(this, {kind});\n#endif')
subprocess.run(['git','-C',str(S),'add','-N','include/MNN/Gate2Trace.hpp'],check=True)
patch=subprocess.check_output(['git','-C',str(S),'diff','--binary'])
(OUT.parent/'diagnostic.patch').write_bytes(patch)
for f in files+['include/MNN/Gate2Trace.hpp']:
    d=OUT/'diagnostic'/f;d.parent.mkdir(parents=True,exist_ok=True);shutil.copyfile(S/f,d)
print('Patch saved:',len(patch),'bytes')
