SMT 1
meta 90 60 1280 720 2026
audio 128 0 4 20 30 0.1 0.15 0.3 0.45 0.55 0.7 0.8 0.9 1 0.95 0.9 0.85 0.95 1 0.9 0.8 0.7 0.55 0.4 0.3 0.5 0.7 0.85 0.95 1 0.9 0.75 0.55 0.35 0.2
sections 3 0 37 72
clip dawn 10 scene fluid_dawn 0 37 0 33 normal 11111 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uPrimaryColor vec3 3
prog 1 n:0.1
prog 1 n:0.05
prog 1 n:0.02
uni uAccentColor vec3 3
prog 1 n:1
prog 1 n:0.55
prog 1 n:0.1
uni uIntensity float 1
prog 1 n:1.1
uni uMotionSpeed float 1
prog 1 n:0.6
uni uPulse float 1
prog 1 n:0.15
endclip
clip spire 10 scene neon_spire 33 72 37 31 normal 33333 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uPrimaryColor vec3 3
prog 1 n:0.02
prog 1 n:0.05
prog 1 n:0.02
uni uAccentColor vec3 3
prog 1 n:0.85
prog 1 n:1
prog 1 n:0.1
uni uIntensity float 1
prog 1 n:1.3
uni uMotionSpeed float 1
prog 1 n:1
uni uPulse float 1
prog 1 n:0.4
endclip
clip fall 10 scene ember_fall 68 90 72 18 normal 55555 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uPrimaryColor vec3 3
prog 1 n:0.03
prog 1 n:0.03
prog 1 n:0.04
uni uAccentColor vec3 3
prog 1 n:1
prog 1 n:0.35
prog 1 n:0.05
uni uIntensity float 1
prog 1 n:1
uni uMotionSpeed float 1
prog 1 n:0.5
uni uPulse float 1
prog 1 n:0.2
endclip
clip t1 10 transition crossfade 33 37 33 4 normal 22222 dawn spire 0.0
prog opacity 1 n:1.0
prog progress 4 n:0.0 n:1.0 v:p f:smoothstep
endclip
clip t2 10 transition flash 68 72 68 4 normal 44444 spire fall 0.0
prog opacity 1 n:1.0
prog progress 4 n:0.0 n:1.0 v:p f:smoothstep
uni uColor vec3 3
prog 1 n:1.0
prog 1 n:1.0
prog 1 n:1.0
uni uPeak float 1
prog 1 n:1.0
endclip
clip blm_bright 24 post bloom_bright 0.0 90 0.0 90 normal 77000 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uThreshold float 1
prog 1 n:0.6
uni uIntensity float 1
prog 1 n:1
endclip
clip blm_blurh 24 post bloom_blur 0.0 90 0.0 90 normal 77000 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uDirection vec2 2
prog 1 n:1
prog 1 n:0
endclip
clip blm_blurv 24 post bloom_blur 0.0 90 0.0 90 normal 77000 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uDirection vec2 2
prog 1 n:0
prog 1 n:1
endclip
clip blm_add 24 post passthrough 0.0 90 0.0 90 normal 77000 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
endclip
clip vig 24 post vignette 0.0 90 0.0 90 normal 77000 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uStrength float 1
prog 1 n:0.35
uni uSoftness float 1
prog 1 n:0.5
endclip
clip grn 24 post grain 0.0 90 0.0 90 normal 77000 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uAmount float 1
prog 1 n:0.03
uni uExposure float 1
prog 1 n:0.55
endclip
clip fin 30 event finish 90 90 90 0.0 0.0 normal 77777 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
endclip
seg 0 33 8 2 5
op RENDER dawn - fbo0 - -
op POST blm_bright fbo0 fbo1 - -
op POST blm_blurh fbo1 fbo2 - -
op POST blm_blurv fbo2 fbo1 - -
op COMPOSITE blm_add fbo1 - fbo0 add
op POST vig fbo0 fbo1 - -
op POST grn fbo1 screen - -
op PRESENT - screen - - -
endseg
seg 33 37 13 3 7
op RENDER dawn - fbo0 - -
op RENDER spire - fbo1 - -
op TRANSITION t1 fbo0,fbo1 fbo2 - -
op POST blm_bright fbo2 fbo0 - -
op POST blm_blurh fbo0 fbo1 - -
op POST blm_blurv fbo1 fbo0 - -
op COMPOSITE blm_add fbo0 - fbo2 add
op POST vig fbo2 fbo0 - -
op POST grn fbo0 screen - -
op PRESENT - screen - - -
endseg
seg 37 68 8 2 5
op RENDER spire - fbo0 - -
op POST blm_bright fbo0 fbo1 - -
op POST blm_blurh fbo1 fbo2 - -
op POST blm_blurv fbo2 fbo1 - -
op COMPOSITE blm_add fbo1 - fbo0 add
op POST vig fbo0 fbo1 - -
op POST grn fbo1 screen - -
op PRESENT - screen - - -
endseg
seg 68 72 13 3 7
op RENDER spire - fbo0 - -
op RENDER fall - fbo1 - -
op TRANSITION t2 fbo0,fbo1 fbo2 - -
op POST blm_bright fbo2 fbo0 - -
op POST blm_blurh fbo0 fbo1 - -
op POST blm_blurv fbo1 fbo0 - -
op COMPOSITE blm_add fbo0 - fbo2 add
op POST vig fbo2 fbo0 - -
op POST grn fbo0 screen - -
op PRESENT - screen - - -
endseg
seg 72 90 8 2 5
op RENDER fall - fbo0 - -
op POST blm_bright fbo0 fbo1 - -
op POST blm_blurh fbo1 fbo2 - -
op POST blm_blurv fbo2 fbo1 - -
op COMPOSITE blm_add fbo1 - fbo0 add
op POST vig fbo0 fbo1 - -
op POST grn fbo1 screen - -
op PRESENT - screen - - -
endseg
end
