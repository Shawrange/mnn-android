#define CL_TARGET_OPENCL_VERSION 200
#define CL_USE_DEPRECATED_OPENCL_1_2_APIS
#include <CL/cl.h>
#include <dlfcn.h>
#include <cstdio>
#include <cstring>
#include <vector>
#include <string>
#include <cmath>
int main(int argc,char** argv) {
    const char* path=argc>1?argv[1]:"libOpenCL.so";
    std::printf("requested_library=%s\n",path);
    void* handle=dlopen(path,RTLD_NOW|RTLD_LOCAL);
    if(!handle){std::printf("dlopen_error=%s\n",dlerror());return 2;}
#define LOAD(name) auto p_##name=reinterpret_cast<decltype(&name)>(dlsym(handle,#name)); if(!p_##name){std::printf("missing_symbol=%s\n",#name);return 3;}
    LOAD(clGetPlatformIDs) LOAD(clGetPlatformInfo) LOAD(clGetDeviceIDs) LOAD(clGetDeviceInfo)
    LOAD(clCreateContext) LOAD(clCreateCommandQueue) LOAD(clCreateBuffer) LOAD(clCreateProgramWithSource)
    LOAD(clBuildProgram) LOAD(clGetProgramBuildInfo) LOAD(clCreateKernel) LOAD(clSetKernelArg)
    LOAD(clEnqueueNDRangeKernel) LOAD(clEnqueueReadBuffer) LOAD(clGetEventProfilingInfo)
    LOAD(clReleaseEvent) LOAD(clReleaseMemObject) LOAD(clReleaseKernel) LOAD(clReleaseProgram)
    LOAD(clReleaseCommandQueue) LOAD(clReleaseContext) LOAD(clGetEventInfo)
#undef LOAD
    Dl_info info{};dladdr(reinterpret_cast<void*>(p_clGetPlatformIDs),&info);
    std::printf("resolved_library=%s\n",info.dli_fname?info.dli_fname:"");
    cl_uint platforms=0;cl_int err=p_clGetPlatformIDs(0,nullptr,&platforms);
    std::printf("platform_query_error=%d\nplatform_count=%u\n",err,platforms);
    if(err||!platforms)return 4;
    std::vector<cl_platform_id> ps(platforms);p_clGetPlatformIDs(platforms,ps.data(),nullptr);
    cl_device_id gpu=nullptr;
    for(size_t pi=0;pi<ps.size();++pi) {
        for(auto key:{CL_PLATFORM_NAME,CL_PLATFORM_VENDOR,CL_PLATFORM_VERSION,CL_PLATFORM_PROFILE,CL_PLATFORM_EXTENSIONS}) {
            size_t n=0;err=p_clGetPlatformInfo(ps[pi],key,0,nullptr,&n);std::vector<char> v(n+1);
            if(!err)err=p_clGetPlatformInfo(ps[pi],key,n,v.data(),nullptr);
            std::printf("platform_%zu_info_%u_error=%d value=%s\n",pi,key,err,v.data());
        }
        cl_uint count=0;err=p_clGetDeviceIDs(ps[pi],CL_DEVICE_TYPE_ALL,0,nullptr,&count);
        std::printf("platform_%zu_device_query=%d count=%u\n",pi,err,count);if(err)continue;
        std::vector<cl_device_id> ds(count);p_clGetDeviceIDs(ps[pi],CL_DEVICE_TYPE_ALL,count,ds.data(),nullptr);
        for(size_t di=0;di<ds.size();++di) {
            auto d=ds[di];cl_device_type type=0;p_clGetDeviceInfo(d,CL_DEVICE_TYPE,sizeof(type),&type,nullptr);
            std::printf("device_%zu_%zu_type=%llu\n",pi,di,(unsigned long long)type);if((type&CL_DEVICE_TYPE_GPU)&&!gpu)gpu=d;
            for(auto key:{CL_DEVICE_NAME,CL_DEVICE_VENDOR,CL_DEVICE_VERSION,CL_DRIVER_VERSION,CL_DEVICE_OPENCL_C_VERSION,CL_DEVICE_EXTENSIONS}) {
                size_t n=0;err=p_clGetDeviceInfo(d,key,0,nullptr,&n);std::vector<char> v(n+1);
                if(!err)err=p_clGetDeviceInfo(d,key,n,v.data(),nullptr);
                std::printf("device_%zu_%zu_info_%u_error=%d value=%s\n",pi,di,key,err,v.data());
            }
            cl_ulong global=0,alloc=0,local=0;size_t wgs=0;cl_bool image=0;cl_uint units=0;cl_device_svm_capabilities svm=0;
            p_clGetDeviceInfo(d,CL_DEVICE_GLOBAL_MEM_SIZE,sizeof(global),&global,nullptr);
            p_clGetDeviceInfo(d,CL_DEVICE_MAX_MEM_ALLOC_SIZE,sizeof(alloc),&alloc,nullptr);
            p_clGetDeviceInfo(d,CL_DEVICE_LOCAL_MEM_SIZE,sizeof(local),&local,nullptr);
            p_clGetDeviceInfo(d,CL_DEVICE_MAX_WORK_GROUP_SIZE,sizeof(wgs),&wgs,nullptr);
            p_clGetDeviceInfo(d,CL_DEVICE_IMAGE_SUPPORT,sizeof(image),&image,nullptr);
            p_clGetDeviceInfo(d,CL_DEVICE_MAX_COMPUTE_UNITS,sizeof(units),&units,nullptr);
            auto se=p_clGetDeviceInfo(d,CL_DEVICE_SVM_CAPABILITIES,sizeof(svm),&svm,nullptr);
            std::printf("device_%zu_%zu_global_mem=%llu max_alloc=%llu local_mem=%llu max_wgs=%zu image=%u compute_units=%u svm_error=%d svm_caps=%llu\n",pi,di,(unsigned long long)global,(unsigned long long)alloc,(unsigned long long)local,wgs,image,units,se,(unsigned long long)svm);
        }
    }
    if(!gpu)return 5;
#define CHECK(call) do { err=(call); if(err){std::printf("failed_api=%s error=%d\n",#call,err);return 6;} }while(0)
    cl_context ctx=p_clCreateContext(nullptr,1,&gpu,nullptr,nullptr,&err);if(err||!ctx)return 6;
    cl_command_queue q=p_clCreateCommandQueue(ctx,gpu,CL_QUEUE_PROFILING_ENABLE,&err);if(err||!q)return 6;
    float input[16],output[16];for(int i=0;i<16;++i)input[i]=float(i);
    auto a=p_clCreateBuffer(ctx,CL_MEM_READ_ONLY|CL_MEM_COPY_HOST_PTR,sizeof(input),input,&err);if(err)return 6;
    auto b=p_clCreateBuffer(ctx,CL_MEM_WRITE_ONLY,sizeof(output),nullptr,&err);if(err)return 6;
    const char* src="__kernel void smoke(__global const float* a,__global float* b){int i=get_global_id(0);b[i]=a[i]*2.0f+1.0f;}";
    auto prog=p_clCreateProgramWithSource(ctx,1,&src,nullptr,&err);if(err)return 6;
    err=p_clBuildProgram(prog,1,&gpu,"-cl-std=CL1.2",nullptr,nullptr);
    if(err){size_t n=0;p_clGetProgramBuildInfo(prog,gpu,CL_PROGRAM_BUILD_LOG,0,nullptr,&n);std::vector<char> log(n+1);p_clGetProgramBuildInfo(prog,gpu,CL_PROGRAM_BUILD_LOG,n,log.data(),nullptr);std::printf("build_error=%d log=%s\n",err,log.data());return 7;}
    auto k=p_clCreateKernel(prog,"smoke",&err);if(err)return 6;
    CHECK(p_clSetKernelArg(k,0,sizeof(a),&a));CHECK(p_clSetKernelArg(k,1,sizeof(b),&b));
    size_t size=16;cl_event event=nullptr;CHECK(p_clEnqueueNDRangeKernel(q,k,1,nullptr,&size,nullptr,0,nullptr,&event));
    CHECK(p_clEnqueueReadBuffer(q,b,CL_TRUE,0,sizeof(output),output,0,nullptr,nullptr));
    cl_ulong start=0,end=0;cl_int status=-999;CHECK(p_clGetEventInfo(event,CL_EVENT_COMMAND_EXECUTION_STATUS,sizeof(status),&status,nullptr));
    CHECK(p_clGetEventProfilingInfo(event,CL_PROFILING_COMMAND_START,sizeof(start),&start,nullptr));
    CHECK(p_clGetEventProfilingInfo(event,CL_PROFILING_COMMAND_END,sizeof(end),&end,nullptr));
    bool correct=true;for(int i=0;i<16;++i)correct&=std::isfinite(output[i])&&std::fabs(output[i]-(i*2.0f+1.0f))<1e-6f;
    std::printf("kernel_event_status=%d gpu_start_ns=%llu gpu_end_ns=%llu output_correct=%d\n",status,(unsigned long long)start,(unsigned long long)end,int(correct));
    p_clReleaseEvent(event);p_clReleaseKernel(k);p_clReleaseProgram(prog);p_clReleaseMemObject(a);p_clReleaseMemObject(b);p_clReleaseCommandQueue(q);p_clReleaseContext(ctx);dlclose(handle);
    return correct&&status==CL_COMPLETE&&end>=start?0:8;
}
