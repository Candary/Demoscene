SMT 1
meta 211.0 60 1280 720 2026
audio 128.0 0.0 4 0.25 53 0.05 0.10 0.20 0.30 0.40 0.50 0.55 0.60 0.70 0.78 0.82 0.85 0.88 0.92 0.98 1.00 1.00 0.98 0.92 0.85 0.90 0.95 0.92 0.88 0.85 0.92 1.00 1.00 0.98 0.92 0.85 0.78 0.70 0.62 0.55 0.48 0.40 0.33 0.27 0.22 0.18 0.15 0.12 0.10 0.08 0.20 0.30 0.40 0.50 0.55 0.50 0.45 0.40
sections 5 0.0 27.0 77.0 127.0 181.0
clip s1 10 scene nebula_raymarch 0.0 27.0 0.0 25.0 normal 11111 - - 0.0
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
clip s2 10 scene sphere_scene 23.0 52.0 25.0 25.0 normal 22222 - - 2.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uColor vec3 3
prog 1 n:0.1
prog 1 n:0.5
prog 1 n:0.8
uni uGlow float 1
prog 1 n:1.2
uni uOrbit float 1
prog 1 n:0.0
endclip
clip s3 10 scene particle_swarm 48.0 77.0 50.0 25.0 normal 33333 - - 2.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uColor vec3 3
prog 1 n:0.95
prog 1 n:0.2
prog 1 n:0.55
uni uSwarm float 1
prog 1 n:0.7
uni uBeatKick float 1
prog 1 n:0.0
endclip
clip s4 10 scene anxiety_mist 73.0 102.0 75.0 25.0 normal 44444 - - 2.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uPrimaryColor vec3 3
prog 1 n:0.25
prog 1 n:0.05
prog 1 n:0.10
uni uAccentColor vec3 3
prog 1 n:0.80
prog 1 n:0.15
prog 1 n:0.10
uni uIntensity float 1
prog 1 n:1.2
uni uMotionSpeed float 1
prog 1 n:1.5
uni uWarmth float 1
prog 1 n:0.85
endclip
clip s5 10 scene morph_grid 98.0 127.0 100.0 25.0 normal 55555 - - 2.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uColor vec3 3
prog 1 n:0.30
prog 1 n:0.60
prog 1 n:0.90
uni uMorph float 1
prog 1 n:0.5
uni uSpeed float 1
prog 1 n:1.0
endclip
clip s6 10 scene cozy_room_sdf 123.0 181.0 125.0 55.0 normal 66666 - - 2.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uLightColor vec3 3
prog 1 n:1.0
prog 1 n:0.85
prog 1 n:0.6
uni uCamAngle float 1
prog 1 n:0.4
arr uPrimitives 120 0.0000 0.0000 5.0000 0.1000 5.0000 0.0000 -1.5000 0.0000 0.0000 0.8000 0.7000 0.5000 0.0000 0.0000 5.0000 3.0000 0.1000 0.0000 0.0000 -2.5000 0.0000 0.4000 0.3000 0.2500 0.0000 0.0000 0.1000 3.0000 5.0000 -2.5000 0.0000 0.0000 0.0000 0.5000 0.3500 0.2500 0.0000 0.0000 0.1000 3.0000 5.0000 2.5000 0.0000 0.0000 0.0000 0.5000 0.3500 0.2500 0.0000 0.0000 1.5000 0.1000 1.0000 0.0000 -0.5000 0.0000 0.0000 0.4000 0.2500 0.1500 1.0000 0.0000 0.2000 0.2000 0.2000 0.0000 0.1000 0.0000 0.0000 1.0000 0.8500 0.4000 2.0000 0.0000 0.0800 0.1000 0.0800 0.5000 -0.4200 0.3000 0.0000 0.9000 0.9000 0.9500 0.0000 0.0000 0.3000 0.0500 0.4000 -0.4000 -0.4300 0.2000 0.3000 0.7000 0.2000 0.2000 2.0000 0.0000 0.1500 0.2500 0.1500 -1.8000 -1.2000 1.5000 0.0000 0.5500 0.3000 0.2000 0.0000 0.0000 1.5000 1.5000 0.0500 2.4000 0.3000 -1.0000 0.0000 0.7000 0.8500 1.0000
endclip
clip s7 10 scene morphing_figures 180.0 211.0 181.0 30.0 normal 77777 - - 1.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
endclip
clip t1 10 transition crossfade 23.0 27.0 23.0 4.0 normal 10101 s1 s2 0.0
prog opacity 1 n:1.0
prog progress 4 n:0.0 n:1.0 v:p f:smoothstep
endclip
clip t2 10 transition flash 48.0 52.0 48.0 4.0 normal 20202 s2 s3 0.0
prog opacity 1 n:1.0
prog progress 4 n:0.0 n:1.0 v:p f:smoothstep
endclip
clip t3 10 transition crossfade 73.0 77.0 73.0 4.0 normal 30303 s3 s4 0.0
prog opacity 1 n:1.0
prog progress 4 n:0.0 n:1.0 v:p f:smoothstep
endclip
clip t4 10 transition flash 98.0 102.0 98.0 4.0 normal 40404 s4 s5 0.0
prog opacity 1 n:1.0
prog progress 4 n:0.0 n:1.0 v:p f:smoothstep
endclip
clip t5 10 transition crossfade 123.0 127.0 123.0 4.0 normal 50505 s5 s6 0.0
prog opacity 1 n:1.0
prog progress 4 n:0.0 n:1.0 v:p f:smoothstep
endclip
clip t6 10 transition crossfade 180.0 181.0 180.0 1.0 normal 60606 s6 s7 0.0
prog opacity 1 n:1.0
prog progress 4 n:0.0 n:1.0 v:p f:smoothstep
endclip
clip blm_bright 24 post bloom_bright 0.0 211.0 0.0 211.0 normal 77007 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uThreshold float 1
prog 1 n:0.6
uni uIntensity float 1
prog 1 n:1.0
endclip
clip blm_blurh 24 post bloom_blur 0.0 211.0 0.0 211.0 normal 77008 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uDirection vec2 2
prog 1 n:1.0
prog 1 n:0.0
endclip
clip blm_blurv 24 post bloom_blur 0.0 211.0 0.0 211.0 normal 77009 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uDirection vec2 2
prog 1 n:0.0
prog 1 n:1.0
endclip
clip blm_add 24 post passthrough 0.0 211.0 0.0 211.0 normal 77010 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
endclip
clip vig 25 post vignette 0.0 211.0 0.0 211.0 normal 99001 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uStrength float 1
prog 1 n:0.35
uni uSoftness float 1
prog 1 n:0.5
endclip
clip grn 26 post grain 0.0 211.0 0.0 211.0 normal 88008 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uAmount float 1
prog 1 n:0.20
endclip
clip fin 30 event finish 211.0 211.0 0.0 0.0 normal 77777 - - 0.0
prog opacity 1 n:1.0
prog progress 1 n:0.0
endclip
seg 0.0 23.0 8 3 8
op RENDER s1 - fbo0 - -
op POST blm_bright fbo0 fbo1 - -
op POST blm_blurh fbo1 fbo2 - -
op POST blm_blurv fbo2 fbo1 - -
op COMPOSITE blm_add fbo1 - fbo0 add
op POST vig fbo0 fbo1 - -
op POST grn fbo1 screen - -
op PRESENT - screen - - -
endseg
seg 23.0 27.0 10 5 10
op RENDER s1 - fbo0 - -
op RENDER s2 - fbo1 - -
op TRANSITION t1 fbo0,fbo1 fbo2 - -
op POST blm_bright fbo2 fbo3 - -
op POST blm_blurh fbo3 fbo4 - -
op POST blm_blurv fbo4 fbo3 - -
op COMPOSITE blm_add fbo3 - fbo2 add
op POST vig fbo2 fbo3 - -
op POST grn fbo3 screen - -
op PRESENT - screen - - -
endseg
seg 27.0 48.0 8 3 8
op RENDER s2 - fbo0 - -
op POST blm_bright fbo0 fbo1 - -
op POST blm_blurh fbo1 fbo2 - -
op POST blm_blurv fbo2 fbo1 - -
op COMPOSITE blm_add fbo1 - fbo0 add
op POST vig fbo0 fbo1 - -
op POST grn fbo1 screen - -
op PRESENT - screen - - -
endseg
seg 48.0 52.0 10 5 10
op RENDER s2 - fbo0 - -
op RENDER s3 - fbo1 - -
op TRANSITION t2 fbo0,fbo1 fbo2 - -
op POST blm_bright fbo2 fbo3 - -
op POST blm_blurh fbo3 fbo4 - -
op POST blm_blurv fbo4 fbo3 - -
op COMPOSITE blm_add fbo3 - fbo2 add
op POST vig fbo2 fbo3 - -
op POST grn fbo3 screen - -
op PRESENT - screen - - -
endseg
seg 52.0 73.0 8 3 8
op RENDER s3 - fbo0 - -
op POST blm_bright fbo0 fbo1 - -
op POST blm_blurh fbo1 fbo2 - -
op POST blm_blurv fbo2 fbo1 - -
op COMPOSITE blm_add fbo1 - fbo0 add
op POST vig fbo0 fbo1 - -
op POST grn fbo1 screen - -
op PRESENT - screen - - -
endseg
seg 73.0 77.0 10 5 10
op RENDER s3 - fbo0 - -
op RENDER s4 - fbo1 - -
op TRANSITION t3 fbo0,fbo1 fbo2 - -
op POST blm_bright fbo2 fbo3 - -
op POST blm_blurh fbo3 fbo4 - -
op POST blm_blurv fbo4 fbo3 - -
op COMPOSITE blm_add fbo3 - fbo2 add
op POST vig fbo2 fbo3 - -
op POST grn fbo3 screen - -
op PRESENT - screen - - -
endseg
seg 77.0 98.0 8 3 8
op RENDER s4 - fbo0 - -
op POST blm_bright fbo0 fbo1 - -
op POST blm_blurh fbo1 fbo2 - -
op POST blm_blurv fbo2 fbo1 - -
op COMPOSITE blm_add fbo1 - fbo0 add
op POST vig fbo0 fbo1 - -
op POST grn fbo1 screen - -
op PRESENT - screen - - -
endseg
seg 98.0 102.0 10 5 10
op RENDER s4 - fbo0 - -
op RENDER s5 - fbo1 - -
op TRANSITION t4 fbo0,fbo1 fbo2 - -
op POST blm_bright fbo2 fbo3 - -
op POST blm_blurh fbo3 fbo4 - -
op POST blm_blurv fbo4 fbo3 - -
op COMPOSITE blm_add fbo3 - fbo2 add
op POST vig fbo2 fbo3 - -
op POST grn fbo3 screen - -
op PRESENT - screen - - -
endseg
seg 102.0 123.0 8 3 8
op RENDER s5 - fbo0 - -
op POST blm_bright fbo0 fbo1 - -
op POST blm_blurh fbo1 fbo2 - -
op POST blm_blurv fbo2 fbo1 - -
op COMPOSITE blm_add fbo1 - fbo0 add
op POST vig fbo0 fbo1 - -
op POST grn fbo1 screen - -
op PRESENT - screen - - -
endseg
seg 123.0 127.0 10 5 10
op RENDER s5 - fbo0 - -
op RENDER s6 - fbo1 - -
op TRANSITION t5 fbo0,fbo1 fbo2 - -
op POST blm_bright fbo2 fbo3 - -
op POST blm_blurh fbo3 fbo4 - -
op POST blm_blurv fbo4 fbo3 - -
op COMPOSITE blm_add fbo3 - fbo2 add
op POST vig fbo2 fbo3 - -
op POST grn fbo3 screen - -
op PRESENT - screen - - -
endseg
seg 127.0 180.0 8 3 8
op RENDER s6 - fbo0 - -
op POST blm_bright fbo0 fbo1 - -
op POST blm_blurh fbo1 fbo2 - -
op POST blm_blurv fbo2 fbo1 - -
op COMPOSITE blm_add fbo1 - fbo0 add
op POST vig fbo0 fbo1 - -
op POST grn fbo1 screen - -
op PRESENT - screen - - -
endseg
seg 180.0 181.0 10 5 10
op RENDER s6 - fbo0 - -
op RENDER s7 - fbo1 - -
op TRANSITION t6 fbo0,fbo1 fbo2 - -
op POST blm_bright fbo2 fbo3 - -
op POST blm_blurh fbo3 fbo4 - -
op POST blm_blurv fbo4 fbo3 - -
op COMPOSITE blm_add fbo3 - fbo2 add
op POST vig fbo2 fbo3 - -
op POST grn fbo3 screen - -
op PRESENT - screen - - -
endseg
seg 181.0 211.0 8 3 8
op RENDER s7 - fbo0 - -
op POST blm_bright fbo0 fbo1 - -
op POST blm_blurh fbo1 fbo2 - -
op POST blm_blurv fbo2 fbo1 - -
op COMPOSITE blm_add fbo1 - fbo0 add
op POST vig fbo0 fbo1 - -
op POST grn fbo1 screen - -
op PRESENT - screen - - -
endseg
end
