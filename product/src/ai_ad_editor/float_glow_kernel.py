"""Original MIT OpenCL highlight extraction, FIR light spread and merge."""
SOURCE = r'''
double3 glow_highlight(float4 original, double threshold, double knee,
                       double wr, double wg, double wb) {
    double3 rgb=fmax(convert_double3(original.xyz),(double3)(0.0));
    double luminance=(rgb.x*wr+rgb.y*wg)+rgb.z*wb;
    double contribution=fmax(luminance-threshold,0.0);
    if(knee>0.0) {
        double soft=clamp(luminance-threshold+knee,0.0,2.0*knee);
        contribution=fmax(contribution,soft*soft/(4.0*knee));
    }
    contribution=fmin(contribution,luminance);
    double gate=luminance>0.0?contribution/luminance:0.0;
    return rgb*(gate*(double)original.w);
}
__kernel void glow_bright(__global const float4 *src, __global float4 *out,
    ulong count, double threshold, double knee, double wr, double wg, double wb) {
    size_t i=get_global_id(0); if(i>=count)return;
    out[i]=convert_float4_rte((double4)(glow_highlight(src[i],threshold,knee,wr,wg,wb),0.0));
}
__kernel void glow_blur(__global const float4 *src, __global float4 *out,
    int w, int h, int axis, int support, double sigma, double norm, int transparent) {
    size_t i=get_global_id(0); if(i>=(size_t)w*h)return;
    int x=i%w,y=i/w; double4 sum=(double4)(0.0);
    for(int k=-support;k<=support;k++) {
        int xx=x+(axis==1?k:0),yy=y+(axis==0?k:0);
        double weight=support?exp(-0.5*((double)k/sigma)*((double)k/sigma)):1.0;
        double4 sample=convert_double4(src[clamp(yy,0,h-1)*w+clamp(xx,0,w-1)]);
        if(transparent&&(xx<0||xx>=w||yy<0||yy>=h))sample=(double4)(0.0);
        sum+=sample*weight;
    }
    out[i]=convert_float4_rte(sum/norm);
}
__kernel void glow_merge(__global const float4 *src, __global const float4 *spread,
    __global float4 *out, ulong count, int halation, double threshold, double knee,
    double wr, double wg, double wb, double intensity, double gain,
    double red, double green, double blue, double suppression) {
    size_t i=get_global_id(0); if(i>=count)return;
    float4 original=src[i]; double3 light=convert_double3(spread[i].xyz);
    if(halation) {
        float3 bright=convert_float3_rte(glow_highlight(original,threshold,knee,wr,wg,wb));
        light=fmax(light-suppression*convert_double3(bright),(double3)(0.0));
    }
    double3 rgb=convert_double3(original.xyz)+(light*(double3)(red,green,blue))*(intensity*gain);
    if((double)original.w==0.0)rgb=(double3)(0.0);
    float4 value=convert_float4_rte((double4)(rgb,0.0)); value.w=original.w; out[i]=value;
}
'''
