"""Binary64 OpenCL shoulder/OKLab mapping, using the CPU contract matrices."""
from .float_gamut import RGB_LMS, LMS_LAB, LAB_LMS, LMS_RGB

def constants(name, matrix):
    return '__constant double '+name+'[9]={'+','.join(format(float(x),'.17g') for x in matrix.flat)+'};\n'

SOURCE='\n'+''.join(constants(name,matrix) for name,matrix in
    [('gm_rgb_lms',RGB_LMS),('gm_lms_lab',LMS_LAB),('gm_lab_lms',LAB_LMS),('gm_lms_rgb',LMS_RGB)])+r'''
double3 gm_matrix(double3 v,__constant double *m) {
    return (double3)((v.x*m[0]+v.y*m[1])+v.z*m[2],
                     (v.x*m[3]+v.y*m[4])+v.z*m[5],
                     (v.x*m[6]+v.y*m[7])+v.z*m[8]);
}
double3 gm_back(double3 lab) {
    double3 lms=gm_matrix(lab,gm_lab_lms);
    return gm_matrix(lms*lms*lms,gm_lms_rgb);
}
int gm_inside(double3 v) {
    return v.x>=0.0 && v.x<=1.0 && v.y>=0.0 && v.y<=1.0 && v.z>=0.0 && v.z<=1.0;
}
__kernel void gamut_map(__global const float4 *source,__global float4 *output,
                        __global uint *flags,ulong count,double wr,double wg,double wb,
                        double exposure,double white) {
    size_t i=get_global_id(0);if(i>=count)return;
    double3 rgb=convert_double3(source[i].xyz);
    double y=((rgb.x*wr+rgb.y*wg)+rgb.z*wb)*exposure;
    uint flag=y>white?16:0;
    if(y<0.0 || !isfinite(y)) {flags[i]=flag|32;output[i]=source[i];return;}
    double shoulder=y*(1.0+y/(white*white))/(1.0+y);
    double ratio=y>0.0?shoulder*exposure/y:0.0;
    rgb*=ratio;
    if(!gm_inside(rgb)) {
        flag|=1;
        double3 lms=gm_matrix(rgb,gm_rgb_lms);
        lms=(double3)(cbrt(lms.x),cbrt(lms.y),cbrt(lms.z));
        double3 lab=gm_matrix(lms,gm_lms_lab);
        if(lab.x<=0.0) {rgb=(double3)(0.0);flag|=2;}
        else if(lab.x>=1.0-1e-7) {rgb=(double3)(1.0);flag|=4;}
        else {
            flag|=8;double lo=0.0,hi=1.0;
            rgb=gm_back((double3)(lab.x,0.0,0.0));
            for(int j=0;j<24;j++) {
                double mid=(lo+hi)*0.5;
                double3 candidate=gm_back((double3)(lab.x,lab.y*mid,lab.z*mid));
                if(gm_inside(candidate)) {lo=mid;rgb=candidate;} else hi=mid;
            }
        }
    }
    output[i]=(float4)(convert_float3_rte(rgb),source[i].w);flags[i]=flag;
}
'''
