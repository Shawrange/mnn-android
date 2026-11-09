#include <algorithm>
#include <cmath>
#include <cfenv>
#include <cstdint>
#include <fstream>
#include <stdexcept>
#include <string>
#include <vector>
template<class T>std::vector<T> read(const std::string& p,size_t n){std::vector<T> a(n);std::ifstream f(p,std::ios::binary);f.read((char*)a.data(),n*sizeof(T));if(f.gcount()!=n*sizeof(T))throw std::runtime_error("bad input: "+p);return a;}
template<class T>void write(const std::string& p,const std::vector<T>& a){std::ofstream f(p,std::ios::binary);f.write((const char*)a.data(),a.size()*sizeof(T));}
int main(int argc,char** argv){
    if(argc!=7)return 2;if(std::fegetround()!=FE_TONEAREST)return 3;
    std::string xfile=argv[1],wfile=argv[2],afile=argv[3],bfile=argv[4],prefix=argv[5];int n=std::stoi(argv[6]);
    constexpr int IC=1024,OC=2048,BL=16,BS=64;
    auto x=read<float>(xfile,n*IC);auto w=read<int8_t>(wfile,OC*IC);auto alpha=read<float>(afile,OC*BL*2);auto bias=read<float>(bfile,OC);
    std::vector<int8_t> q(n*IC);std::vector<float> qs(n),ds(n),b32(n*OC),bHalf(n*OC);std::vector<double>a64(n*OC),b64(n*OC);
    for(int t=0;t<n;++t){
        float m=0;for(int k=0;k<IC;++k)m=std::max(m,std::abs(float((_Float16)x[t*IC+k])));
        if(m<=0)m=127.f;qs[t]=127.f/m;ds[t]=m/127.f;
        const float sh=float((_Float16)qs[t]);
        for(int k=0;k<IC;++k){float product=float((_Float16)(float((_Float16)x[t*IC+k])*sh));int value=int(std::round(product));q[t*IC+k]=std::clamp(value,-128,127);}
        for(int o=0;o<OC;++o){
            double av=bias[o],bv=bias[o];float accum=0;
            for(int bl=0;bl<BL;++bl){
                float z=alpha[(o*BL+bl)*2],s=alpha[(o*BL+bl)*2+1];int32_t dot=0,sum=0;
                for(int k=bl*BS;k<(bl+1)*BS;++k){
                    int wi=w[o*IC+k];int qi=q[t*IC+k];double wf=double(wi)*double(s)+double(z);
                    av+=double(x[t*IC+k])*wf;bv+=double(qi)*double(ds[t])*wf;
                    dot+=qi*(wi+8);sum+=qi;
                }
                // Match observed metadata mode0 and ARMV86 FP32 post-treat, not an idealized INT8 formula.
                volatile float mulOffset=-8.f*s;float offset=z+mulOffset;
                volatile float scaled=float(dot)*s;
                volatile float dequant=scaled*ds[t];
                float srcSum=float(sum)*ds[t];
                if(t==n-1 && (n%10)%2==1){
                    // Actual ARMV86 TILE_1 fuses scale_eff and accumulates with two FMAs.
                    float scaleEff=s*ds[t];
                    accum=std::fma(float(dot),scaleEff,accum);
                    accum=std::fma(offset,srcSum,accum);
                }else{
                    float part=std::fma(offset,srcSum,float(dequant));
                    accum=part+accum;
                }
            }
            accum+=bias[o];b32[t*OC+o]=accum;bHalf[t*OC+o]=std::clamp(float((_Float16)accum),-65504.f,65504.f);
            a64[t*OC+o]=av;b64[t*OC+o]=bv;
        }
    }
    write(prefix+".q.i8",q);write(prefix+".qscale.f32",qs);write(prefix+".dscale.f32",ds);
    write(prefix+".A.f64",a64);write(prefix+".B-ideal.f64",b64);write(prefix+".B-prehalf.f32",b32);write(prefix+".B.f32",bHalf);
    return 0;
}
