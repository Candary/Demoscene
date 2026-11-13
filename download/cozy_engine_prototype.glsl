#version 330
varying vec2 vUV;
uniform float uTime;
uniform vec2 uResolution;
uniform vec3 uWallColor, uFloorColor, uTextileColor, uFireColor;
uniform float uEmpathy, uIntensity;
float sdRoundBox(vec3 p,vec3 b,float r){vec3 q=abs(p)-b+r;return min(max(q.x,max(q.y,q.z)),0.)+length(max(q,0.))-r;}
float sdBox(vec3 p,vec3 b){vec3 q=abs(p)-b;return length(max(q,0.))+min(max(q.x,max(q.y,q.z)),0.);}
float sdPlane(vec3 p,float h){return p.y-h;}
float hash(vec3 p){p=fract(p*0.3183099+0.1);p*=17.;return fract(p.x*p.y*p.z*(p.x+p.y+p.z));}
float noise(vec3 p){vec3 i=floor(p),f=fract(p);f=f*f*(3.-2.*f);
return mix(mix(mix(hash(i),hash(i+vec3(1,0,0)),f.x),mix(hash(i+vec3(0,1,0)),hash(i+vec3(1,1,0)),f.x),f.y),
mix(mix(hash(i+vec3(0,0,1)),hash(i+vec3(1,0,1)),f.x),mix(hash(i+vec3(0,1,1)),hash(i+vec3(1,1,1)),f.x),f.y),f.z);}
float fbm(vec3 p){float v=0.,a=.5;for(int i=0;i<4;i++){v+=a*noise(p);p*=2.;a*=.5;}return v;}
float sdRoom(vec3 p){return min(sdPlane(p,0.),min(sdBox(p-vec3(0,2,-3),vec3(4,2,.05)),min(sdBox(p-vec3(-3,2,0),vec3(.05,2,3)),sdBox(p-vec3(3,2,0),vec3(.05,2,3)))));}
float sdSofa(vec3 p){vec3 q=p-vec3(0,.3,1.5);return min(sdRoundBox(q,vec3(1,.25,.45),.1),min(sdRoundBox(q-vec3(0,.15,-.3),vec3(1,.25,.1),.08),sdRoundBox(q+vec3(0,-.05,.05),vec3(.9,.1,.35),.06)));}
float sdFire(vec3 p,float t){vec3 q=p-vec3(0,.3,-2.4);float f=999.;for(int i=0;i<5;i++){float fi=float(i);vec3 o=vec3(sin(t*2+fi*1.3)*.15,fi*.15-.3,cos(t*1.7+fi*.7)*.1);f=min(f,length(q-o)-(.12-fi*.015)-fbm(q*4+vec3(0,-t*3,0))*.08);}return f;}
float sdFireplace(vec3 p){vec3 q=p-vec3(0,.5,-2.5);return min(sdBox(q,vec3(1,1,.2))-sdBox(q,vec3(.5,.5,.3)),sdBox(q+vec3(0,.9,0),vec3(.8,.08,.3)));}
float sdScene(vec3 p,float t){float c=mod(t,12.);float p1=smoothstep(0,2,c)-smoothstep(4,6,c),p2=smoothstep(3,5,c)-smoothstep(7,9,c),p3=smoothstep(7,9,c)-smoothstep(11,12,c);float d=sdRoom(p);float s=sdSofa(p)+fbm(p*3+vec3(0,-t*.5,0))*p2*.3;d=min(d,mix(d,s,p1));d=min(d,mix(d,sdFireplace(p),p1));float f=sdFire(p,t);f=min(f,sdFire(p+vec3(sin(t)*p3*2,cos(t*.7)*p3*2,0),t*1.5));d=min(d,mix(d,f,p1+p2+p3));return d;}
vec3 calcN(vec3 p,float t){vec2 e=vec2(.001,0);return normalize(vec3(sdScene(p+e.xyy,t)-sdScene(p-e.xyy,t),sdScene(p+e.yxy,t)-sdScene(p-e.yxy,t),sdScene(p+e.yyx,t)-sdScene(p-e.yyx,t)));}
void main(){
vec2 uv=(vUV*2.-1.)*vec2(uResolution.x/uResolution.y,1.);
vec3 ro=vec3(0,1.5,4),rd=normalize(vec3(uv,-1.5));
float d=0.;for(int i=0;i<64;i++){float s=sdScene(ro+rd*d,uTime);if(s<.001)break;d+=s;if(d>20.)break;}
vec3 col;
if(d<20.){vec3 p=ro+rd*d;vec3 n=calcN(p,uTime);
float a=sdRoom(p),b=sdSofa(p),c=sdFire(p,uTime);float m=min(min(a,b),c);
if(m==c){col=uFireColor*(.8+.2*sin(uTime*10+fbm(p*5)*6))*2.;}
elif(m==b){col=uTextileColor*(.3+.7*max(dot(n,normalize(vec3(.5,.8,.3))),0.));}
elif(p.y<.1){col=uFloorColor*(.2+.8*max(dot(n,normalize(vec3(.3,.9,.2))),0.));}
else{col=uWallColor*(.15+.85*max(dot(n,normalize(vec3(.4,.6,.5))),0.));}
vec3 fp=vec3(0,.5,-2.4);col+=uFireColor*max(dot(n,normalize(fp-p)),0.)/(1.+length(fp-p)*length(fp-p)*.3)*.8;
col=mix(col,uWallColor*.1,smoothstep(5,15,d));
}else{col=uWallColor*.05;}
float br=length(col);if(br>1.)col+=col*(br-1.)*.5;
col*=1.-length(uv)*.3*(1.-uEmpathy*.005);
col=(col*(2.51*col+.03))/(col*(2.43*col+.59)+.14);
gl_FragColor=vec4(col,1.);}
