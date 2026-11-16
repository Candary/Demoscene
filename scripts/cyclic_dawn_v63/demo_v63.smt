SMT 1
meta 45.0 60 1280 720 2026
audio 128.0 0.0 4 0.25 15 0.10 0.30 0.50 0.70 0.85 1.00 0.95 1.00 0.85 0.65 0.45 0.30 0.20
sections 3 0.0 16.5 33.0

clip s1 10 scene dawn 0.0 16.5 0.0 12.0 normal 11111 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uPrimaryColor vec3 3
prog 1 n:0.10
prog 1 n:0.05
prog 1 n:0.02
uni uAccentColor vec3 3
prog 1 n:1.0
prog 1 n:0.55
prog 1 n:0.10
uni uIntensity float 1
prog 1 n:1.1
uni uMotionSpeed float 1
prog 1 n:0.6
uni uPulse float 1
prog 1 n:0.15
endclip

clip s2 10 scene spire 12.0 33.0 16.5 12.0 normal 33333 - - 12.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uPrimaryColor vec3 3
prog 1 n:0.02
prog 1 n:0.05
prog 1 n:0.02
uni uAccentColor vec3 3
prog 1 n:0.85
prog 1 n:1.0
prog 1 n:0.10
uni uIntensity float 1
prog 1 n:1.3
uni uMotionSpeed float 1
prog 1 n:1.0
uni uPulse float 1
prog 1 n:0.4
endclip

clip s3 10 scene fall 28.5 45.0 33.0 12.0 normal 55555 - - 28.5
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uPrimaryColor vec3 3
prog 1 n:0.03
prog 1 n:0.03
prog 1 n:0.04
uni uAccentColor vec3 3
prog 1 n:1.0
prog 1 n:0.35
prog 1 n:0.05
uni uIntensity float 1
prog 1 n:1.0
uni uMotionSpeed float 1
prog 1 n:0.5
uni uPulse float 1
prog 1 n:0.2
endclip

clip t1 10 transition crossfade 12.0 16.5 12.0 4.5 normal 22222 s1 s2 12.0
prog opacity 1 n:1.0
prog progress 4 n:0.0 n:1.0 v:p f:smoothstep
endclip

clip t2 10 transition bloom_transition 28.5 33.0 28.5 4.5 normal 44444 s2 s3 28.5
prog opacity 1 n:1.0
prog progress 4 n:0.0 n:1.0 v:p f:smoothstep
uni uColor vec3 3
prog 1 n:1.0
prog 1 n:1.0
prog 1 n:1.0
uni uPeak float 1
prog 1 n:1.0
endclip

clip blm_bright 24 post bloom_bright 0.0 45.0 0.0 45.0 normal 77007 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uThreshold float 1
prog 1 n:0.6
uni uIntensity float 1
prog 1 n:1.0
endclip
clip blm_blurh 24 post bloom_blur 0.0 45.0 0.0 45.0 normal 77008 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uDirection vec2 2
prog 1 n:1.0
prog 1 n:0.0
endclip
clip blm_blurv 24 post bloom_blur 0.0 45.0 0.0 45.0 normal 77009 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uDirection vec2 2
prog 1 n:0.0
prog 1 n:1.0
endclip
clip blm_add 24 post passthrough 0.0 45.0 0.0 45.0 normal 77010 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
endclip
clip vig 25 post vignette 0.0 45.0 0.0 45.0 normal 99001 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uStrength float 1
prog 1 n:0.35
uni uSoftness float 1
prog 1 n:0.5
endclip
clip grn 25 post grain 0.0 45.0 0.0 45.0 normal 88008 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uAmount float 1
prog 1 n:0.03
uni uExposure float 1
prog 1 n:0.55
endclip

clip fin 30 event finish 45.0 45.0 45.0 0.0 0.0 normal 77777 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
endclip

seg 0.0 12.0 8 2 5
op RENDER s1 - fbo0 - -
op POST blm_bright fbo0 fbo1 - -
op POST blm_blurh fbo1 fbo2 - -
op POST blm_blurv fbo2 fbo1 - -
op COMPOSITE blm_add fbo1 - fbo0 add
op POST vig fbo0 fbo1 - -
op POST grn fbo1 screen - -
op PRESENT - screen - - -
endseg
seg 12.0 16.5 13 3 7
op RENDER s1 - fbo0 - -
op RENDER s2 - fbo1 - -
op TRANSITION t1 fbo0,fbo1 fbo2 - -
op POST blm_bright fbo2 fbo0 - -
op POST blm_blurh fbo0 fbo1 - -
op POST blm_blurv fbo1 fbo0 - -
op COMPOSITE blm_add fbo0 - fbo2 add
op POST vig fbo2 fbo0 - -
op POST grn fbo0 screen - -
op PRESENT - screen - - -
endseg
seg 16.5 28.5 8 2 5
op RENDER s2 - fbo0 - -
op POST blm_bright fbo0 fbo1 - -
op POST blm_blurh fbo1 fbo2 - -
op POST blm_blurv fbo2 fbo1 - -
op COMPOSITE blm_add fbo1 - fbo0 add
op POST vig fbo0 fbo1 - -
op POST grn fbo1 screen - -
op PRESENT - screen - - -
endseg
seg 28.5 33.0 13 3 7
op RENDER s2 - fbo0 - -
op RENDER s3 - fbo1 - -
op TRANSITION t2 fbo0,fbo1 fbo2 - -
op POST blm_bright fbo2 fbo0 - -
op POST blm_blurh fbo0 fbo1 - -
op POST blm_blurv fbo1 fbo0 - -
op COMPOSITE blm_add fbo0 - fbo2 add
op POST vig fbo2 fbo0 - -
op POST grn fbo0 screen - -
op PRESENT - screen - - -
endseg
seg 33.0 45.0 8 2 5
op RENDER s3 - fbo0 - -
op POST blm_bright fbo0 fbo1 - -
op POST blm_blurh fbo1 fbo2 - -
op POST blm_blurv fbo2 fbo1 - -
op COMPOSITE blm_add fbo1 - fbo0 add
op POST vig fbo0 fbo1 - -
op POST grn fbo1 screen - -
op PRESENT - screen - - -
endseg
end
