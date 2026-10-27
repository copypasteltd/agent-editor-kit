"""Original OpenCL optical formulas; binary64 math and Float32 RGBA boundaries."""
SOURCE=r'''
double optical_channel(__global const float4 *src, int w,int h,double x,double y,int channel,int edge) {
    x=clamp(x,edge? -2.0:0.0,edge?(double)w+1:(double)w-1);
    y=clamp(y,edge? -2.0:0.0,edge?(double)h+1:(double)h-1);
    int ix=(int)floor(x),iy=(int)floor(y);double dx=x-ix,dy=y-iy;
    double color=0,alpha=0;
    for(int k=0;k<4;k++) {
        int xx=ix+k%2,yy=iy+k/2;
        double weight=(k%2?dx:1-dx)*(k/2?dy:1-dy);
        double4 p=convert_double4(src[clamp(yy,0,h-1)*w+clamp(xx,0,w-1)]);
        double a=p.w*weight;
        if(edge&&(xx<0||xx>=w||yy<0||yy>=h))a=0;
        color+=p[channel]*a;alpha+=a;
    }
    return alpha>0?color/alpha:0;
}
__kernel void optics(__global const float4 *src,__global const double *p,__global float4 *out,
                     int w,int h,int kind,int ghosts,int edge) {
    size_t i=get_global_id(0);if(i>=(size_t)w*h)return;
    float4 original=src[i];
    if(p[0]==0 || (kind==2&&p[14]==0&&p[15]==0) ||
       (kind!=2&&(p[9]==0||(p[6]==0&&p[7]==0&&p[8]==0)))) {out[i]=original;return;}
    if((double)original.w==0.0){out[i]=(float4)(0,0,0,original.w);return;}
    int x=i%w,y=i/w;double shortside=(double)min(w,h);
    double dx=(x+.5-p[1]*w)/shortside,dy=(y+.5-p[2]*h)/shortside;
    double3 rgb=convert_double3(original.xyz);
    if(kind==2) {
        double distance=sqrt(dx*dx+dy*dy),factor=pow(fmin(distance*2,4.0),p[16]);
        double ux=distance>0?dx/distance:0,uy=distance>0?dy/distance:0;
        double red=optical_channel(src,w,h,x+ux*factor*p[14],y+uy*factor*p[14],0,edge);
        double blue=optical_channel(src,w,h,x+ux*factor*p[15],y+uy*factor*p[15],2,edge);
        rgb.x+=p[0]*(red-rgb.x);rgb.z+=p[0]*(blue-rgb.z);
    } else {
        double angle=p[5]*(3.14159265358979323846/180.0),c=cos(angle),s=sin(angle);
        double rx=c*dx+s*dy,ry=-s*dx+c*dy;
        double3 tint=(double3)(p[6],p[7],p[8]),light;
        if(kind==1) {
            double u=rx/p[3],v=ry/(p[3]*p[4]);light=exp(-.5*(u*u+v*v))*tint;
        } else {
            double r=sqrt(dx*dx+dy*dy)/p[3],ring=(r-2.7)/.22;
            double energy=exp(-.5*r*r);
            energy+=p[10]*exp(-fabs(ry)/p[11])*exp(-fabs(rx)/(p[3]*8));
            energy+=p[12]*exp(-.5*ring*ring);light=energy*tint;
            for(int j=1;j<=ghosts;j++) {
                double gx=(x+.5-(p[1]+(.5-p[1])*j*p[13])*w)/shortside;
                double gy=(y+.5-(p[2]+(.5-p[2])*j*p[13])*h)/shortside;
                double rr=sqrt(gx*gx+gy*gy)/(p[3]*(.35+.12*j)),q=(rr-.8)/.23;
                double amount=exp(-.5*q*q)*(.18/(1+.3*j));
                light+=amount*(double3)(p[6]*(1-.04*j),p[7]*(.6+.025*j),p[8]*(.9-.035*j));
            }
        }
        rgb+=light*(p[9]*p[0]);
    }
    float4 result=convert_float4_rte((double4)(rgb,(double)original.w));
    result.w=original.w;out[i]=result;
}
'''
