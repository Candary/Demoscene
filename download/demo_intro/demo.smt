SMT 1
meta 60.0 60 1280 720 2026
audio 128.0 0.0 4 5.0 10 0.05 0.10 0.20 0.30 0.40 0.50 0.60 0.70 0.80 0.50
sections 3 0.0 20.0 40.0
clip s1 10 scene nebula_raymarch 0.0 17.0 0.0 15.0 normal 11111 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uPrimaryColor vec3 3
prog 1 n:0.05
prog 1 n:0.10
prog 1 n:0.30
uni uAccentColor vec3 3
prog 1 n:0.20
prog 1 n:0.60
prog 1 n:0.90
uni uIntensity float 1
prog 1 n:0.8
uni uMotionSpeed float 1
prog 1 n:1.0
uni uPulse float 1
prog 1 n:0.0
endclip
clip s2 10 scene sphere_scene 13.0 32.0 15.0 15.0 normal 22222 - - 2.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uColor vec3 3
prog 1 n:0.1
prog 1 n:0.5
prog 1 n:0.8
uni uGlow float 1
prog 1 n:1.2
uni uOrbit float 1
prog 5 v:t n:0.3 o:* n:6.2832 f:mod
endclip
clip s3 10 scene particle_swarm 28.0 60.0 30.0 30.0 normal 33333 - - 3.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uColor vec3 3
prog 1 n:0.95
prog 1 n:0.2
prog 1 n:0.55
uni uSwarm float 1
prog 1 n:0.7
uni uBeatKick float 1
prog 5 n:1.0 v:audio.beat_phase o:- n:3.0 f:pow
endclip
clip t1 10 transition crossfade 13.0 17.0 13.0 4.0 normal 10101 s1 s2 0.0
prog opacity 1 n:1.0
prog progress 4 n:0.0 n:1.0 v:p f:smoothstep
endclip
clip t2 10 transition flash 28.0 32.0 28.0 4.0 normal 20202 s2 s3 0.0
prog opacity 1 n:1.0
prog progress 4 n:0.0 n:1.0 v:p f:smoothstep
uni uColor vec3 3
prog 1 n:1.0
prog 1 n:1.0
prog 1 n:1.0
uni uPeak float 1
prog 1 n:1.5
endclip
clip vig 25 post vignette 0.0 60.0 0.0 60.0 normal 99001 - - 0.0
prog opacity 1 n:1.0
prog progress 1 n:1.0
uni uStrength float 1
prog 1 n:0.35
uni uSoftness float 1
prog 1 n:0.5
endclip
clip fin 30 event finish 60.0 60.0 0.0 0.0 normal 77777 - - 0.0
prog opacity 1 n:1.0
prog progress 1 n:0.0
endclip
seg 0.0 13.0 3 1 3
op RENDER s1 - fbo0 - -
op POST vig fbo0 screen - -
op PRESENT - screen - - -
endseg
seg 13.0 17.0 5 3 5
op RENDER s1 - fbo0 - -
op RENDER s2 - fbo1 - -
op TRANSITION t1 fbo0,fbo1 fbo2 - -
op POST vig fbo2 screen - -
op PRESENT - screen - - -
endseg
seg 17.0 28.0 3 1 3
op RENDER s2 - fbo0 - -
op POST vig fbo0 screen - -
op PRESENT - screen - - -
endseg
seg 28.0 32.0 5 3 5
op RENDER s2 - fbo0 - -
op RENDER s3 - fbo1 - -
op TRANSITION t2 fbo0,fbo1 fbo2 - -
op POST vig fbo2 screen - -
op PRESENT - screen - - -
endseg
seg 32.0 60.0 3 1 3
op RENDER s3 - fbo0 - -
op POST vig fbo0 screen - -
op PRESENT - screen - - -
endseg
end
