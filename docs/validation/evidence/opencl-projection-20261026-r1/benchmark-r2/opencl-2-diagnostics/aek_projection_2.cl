#define INTEGER_SOURCE 0

#pragma OPENCL EXTENSION cl_khr_fp64 : enable
#pragma OPENCL FP_CONTRACT OFF
const sampler_t nearest = CLK_NORMALIZED_COORDS_FALSE | CLK_ADDRESS_CLAMP_TO_EDGE | CLK_FILTER_NEAREST;
double coefficient(read_only image2d_t p, int i) {
    double a = (double)read_imagef(p, nearest, (int2)(i, 0)).x;
    double b = (double)read_imagef(p, nearest, (int2)(i, 1)).x;
    double c = (double)read_imagef(p, nearest, (int2)(i, 2)).x;
    int exponent = (int)read_imagef(p, nearest, (int2)(i, 3)).x;
    if (exponent == 2048) return NAN;
    if (exponent == 2049) return a < 0.0 ? -INFINITY : INFINITY;
    if (exponent == 2050) return -0.0;
    return ldexp((a * 0x1.0p-20 + b * 0x1.0p-40) + c * 0x1.0p-60, exponent);
}
double pixel(read_only image2d_t s, int x, int y) {
    double value = (double)read_imagef(s, nearest, (int2)(x, y)).x;
#if INTEGER_SOURCE
    return rint(value * 255.0);
#else
    return value;
#endif
}
double sample_bilinear(read_only image2d_t s, double x, double y) {
    int width = get_image_width(s), height = get_image_height(s);
    x = clamp(x, 0.0, (double)(width - 1));
    y = clamp(y, 0.0, (double)(height - 1));
    int ix = (int)x, iy = (int)y;
    int nx = min(ix + 1, width - 1), ny = min(iy + 1, height - 1);
    x -= ix; y -= iy;
    return (1.0-y) * ((1.0-x)*pixel(s, ix, iy) + x*pixel(s, nx, iy))
         + y * ((1.0-x)*pixel(s, ix, ny) + x*pixel(s, nx, ny));
}
void emit(write_only image2d_t destination, int2 p, double value) {
#if INTEGER_SOURCE
    value = (double)convert_uchar_sat_rtz(value) / 255.0;
#endif
    write_imagef(destination, p, (float4)((float)value));
}
double prefix_value(read_only image2d_t s, int x, int y) {
    if (x < 0 || y < 0) return 0.0;
    x = min(x, get_image_width(s)/3 - 1);
    y = min(y, get_image_height(s) - 1);
    double a = (double)read_imagef(s, nearest, (int2)(3*x, y)).x;
    double b = (double)read_imagef(s, nearest, (int2)(3*x+1, y)).x;
    double c = (double)read_imagef(s, nearest, (int2)(3*x+2, y)).x;
    return (a+b)+c;
}
void prefix_store(write_only image2d_t s, int x, int y, double value) {
    float a = convert_float_rte(value);
    float b = convert_float_rte(value-(double)a);
    float c = convert_float_rte((value-(double)a)-(double)b);
    write_imagef(s, (int2)(3*x,y), (float4)(a));
    write_imagef(s, (int2)(3*x+1,y), (float4)(b));
    write_imagef(s, (int2)(3*x+2,y), (float4)(c));
}
double prefix_edge(read_only image2d_t s, double x, double y) {
    int ix = (int)floor(x), iy = (int)floor(y);
    double fx = x-ix, fy = y-iy;
    return (1.0-fx)*(1.0-fy)*prefix_value(s,ix-1,iy-1)
         + fx*(1.0-fy)*prefix_value(s,ix,iy-1)
         + (1.0-fx)*fy*prefix_value(s,ix-1,iy)
         + fx*fy*prefix_value(s,ix,iy);
}
__kernel void row_prefix(write_only image2d_t destination, uint index, read_only image2d_t source) {
    if (get_global_id(0) != 0) return;
    int y = get_global_id(1);
    double total = 0.0;
    for (int x=0; x<get_image_width(source); ++x) {
        total += pixel(source,x,y);
        prefix_store(destination,x,y,total);
    }
}
__kernel void column_prefix(write_only image2d_t destination, uint index, read_only image2d_t source) {
    if (get_global_id(1) != 0 || get_global_id(0)%3 != 0) return;
    int x = get_global_id(0)/3;
    double total = 0.0;
    for (int y=0; y<get_image_height(source); ++y) {
        total += prefix_value(source,x,y);
        prefix_store(destination,x,y,total);
    }
}
__kernel void project(write_only image2d_t destination, uint index, read_only image2d_t source, read_only image2d_t parameters, read_only image2d_t integral) {
  const int2 p = (int2)(get_global_id(0),get_global_id(1));
  const double X = p.x, Y = p.y;

    double w=coefficient(parameters,0), h=coefficient(parameters,1);
    double cx=coefficient(parameters,2), cy=coefficient(parameters,3);
    double fx=coefficient(parameters,4), fy=coefficient(parameters,5);
    double cosine=coefficient(parameters,6), sine=coefficient(parameters,7);
    double dx=X+0.5-coefficient(parameters,8), dy=Y+0.5-coefficient(parameters,9);
    double scale=coefficient(parameters,10);
    double x=cx+coefficient(parameters,11)*w+(dx*cosine+dy*sine)/(scale*fx)-0.5;
    double y=cy+coefficient(parameters,12)*h+(-dx*sine+dy*cosine)/(scale*fy)-0.5;

    double kw=coefficient(parameters,13), kh=coefficient(parameters,14);
    double left=clamp(x+0.5-kw/2.0,cx,cx+w), right=clamp(x+0.5+kw/2.0,cx,cx+w);
    double top=clamp(y+0.5-kh/2.0,cy,cy+h), bottom=clamp(y+0.5+kh/2.0,cy,cy+h);
    double v=(prefix_edge(integral,right,bottom)-prefix_edge(integral,left,bottom)
             -prefix_edge(integral,right,top)+prefix_edge(integral,left,top))/(kw*kh);
    emit(destination,p,v);

}
