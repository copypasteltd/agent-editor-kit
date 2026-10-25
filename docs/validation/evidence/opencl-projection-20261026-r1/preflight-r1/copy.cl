
#pragma OPENCL EXTENSION cl_khr_fp64 : enable
#pragma OPENCL FP_CONTRACT OFF
__kernel void copy_probe(write_only image2d_t destination, uint index,
                         read_only image2d_t source, read_only image2d_t parameters) {
    const int2 p = (int2)(get_global_id(0), get_global_id(1));
    const sampler_t nearest = CLK_NORMALIZED_COORDS_FALSE | CLK_ADDRESS_CLAMP_TO_EDGE | CLK_FILTER_NEAREST;
    const float marker = read_imagef(parameters, nearest, (int2)(3, 2)).x;
    const float4 input = read_imagef(source, nearest, p);
    const double value = (double)input.x;
    write_imagef(destination, p, (float4)(marker == 203.0f ? (float)value : NAN));
}
