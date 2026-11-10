SMT 1
meta 20.0 60 1280 720 2026
audio 120.0 0.0 4 20.0 0 
sections 0 
clip s1 10 scene nebula_raymarch 0.0 10.0 0.0 10.0 normal 8088186 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uPrimaryColor vec3 3
prog 1 n:0.0392156862745098
prog 1 n:0.08235294117647059
prog 1 n:0.18823529411764706
uni uAccentColor vec3 3
prog 1 n:0.18823529411764706
prog 1 n:0.3764705882352941
prog 1 n:0.5647058823529412
uni uIntensity float 1
prog 1 n:0.9
uni uMotionSpeed float 1
prog 1 n:1.0
uni uPulse float 1
prog 7 n:1.0 v:audio.beat_phase o:- n:4.0 f:pow n:0.4 o:*
endclip
clip s2 10 scene sphere_scene 7.0 20.0 8.0 12.0 normal 7486400 - - 4.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uColor vec3 3
prog 1 n:0.0392156862745098
prog 1 n:0.08235294117647059
prog 1 n:0.18823529411764706
uni uGlow float 1
prog 1 n:1.2
uni uOrbit float 1
prog 5 v:t n:0.3 o:* n:6.2832 f:mod
endclip
clip t1 10 transition crossfade 7.0 9.0 7.0 2.0 normal 3865789 s1 s2 4.0
prog opacity 1 n:1.0
prog progress 4 n:0.0 n:1.0 v:p f:smoothstep
endclip
clip vig 25 post vignette 0.0 20.0 0.0 20.0 normal 7990665 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uStrength float 1
prog 1 n:0.4
uni uSoftness float 1
prog 1 n:0.5
endclip
clip blm 25 post bloom 0.0 20.0 0.0 20.0 normal 16055166 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uThreshold float 1
prog 1 n:0.8
uni uIntensity float 1
prog 1 n:0.6
uni uRadius float 1
prog 1 n:1.0
endclip
clip grn 25 post grain 0.0 20.0 0.0 20.0 normal 7821296 - - 0.0
prog opacity 1 n:1.0
prog progress 4 v:p n:0.0 n:1.0 f:clamp
uni uAmount float 1
prog 1 n:0.05
endclip
seg 0.0 7.0 9 2 5
op RENDER s1 - fbo0 - -
op POST vig fbo0 fbo1 - -
op POST blm fbo1 fbo0 - -
op POST grn fbo0 screen - -
op PRESENT - screen - - -
endseg
seg 7.0 9.0 13 3 7
op RENDER s1 - fbo0 - -
op RENDER s2 - fbo1 - -
op TRANSITION t1 fbo0,fbo1 fbo2 - -
op POST vig fbo2 fbo0 - -
op POST blm fbo0 fbo1 - -
op POST grn fbo1 screen - -
op PRESENT - screen - - -
endseg
seg 9.0 10.0 12 2 7
op RENDER s1 - fbo0 - -
op RENDER s2 - fbo1 - -
op COMPOSITE s2 fbo1 - fbo0 normal
op POST vig fbo0 fbo1 - -
op POST blm fbo1 fbo0 - -
op POST grn fbo0 screen - -
op PRESENT - screen - - -
endseg
seg 10.0 20.0 8 2 5
op RENDER s2 - fbo0 - -
op POST vig fbo0 fbo1 - -
op POST blm fbo1 fbo0 - -
op POST grn fbo0 screen - -
op PRESENT - screen - - -
endseg
end
