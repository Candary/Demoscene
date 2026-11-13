#!/usr/bin/env python3
"""Upgrade v58 .smt from single-pass bloom to multi-pass separable Gaussian bloom.

Replaces:
  op POST blm <src> <dst> - -

With:
  op POST blm_bright <src> <dst> - -
  op POST blm_blurh <dst> <blur> - -
  op POST blm_blurv <blur> <dst> - -
  op COMPOSITE blm_add <dst> - <src> add

Also replaces old blm clip with 4 new clips.
"""
import re
from pathlib import Path

def upgrade_bloom(smt_path: str) -> str:
    content = Path(smt_path).read_text()
    lines = content.splitlines()
    output = []
    
    # Phase 1: Replace blm clip with 4 new clips
    in_blm_clip = False
    blm_replaced = False
    
    for line in lines:
        # Skip old blm clip block
        if line.startswith("clip blm ") and "post" in line and "bloom" in line:
            in_blm_clip = True
            # Insert 4 new clips
            output.extend(NEW_BLOOM_CLIPS.splitlines())
            blm_replaced = True
            continue
        if in_blm_clip and line == "endclip":
            in_blm_clip = False
            continue
        if in_blm_clip:
            continue  # skip old blm clip content
        
        # Phase 2: Replace bloom ops in segments
        if line.startswith("op POST blm ") and "fbo" in line:
            parts = line.split()
            # op POST blm <src> <dst> - -
            src = parts[3]
            dst = parts[4]
            # Determine blur FBO: if dst is fbo1, blur is fbo2; if fbo3, blur is fbo4
            dst_num = int(dst.replace("fbo", ""))
            blur = f"fbo{dst_num + 1}"
            
            # Replace with 4 ops
            output.append(f"op POST blm_bright {src} {dst} - -")
            output.append(f"op POST blm_blurh {dst} {blur} - -")
            output.append(f"op POST blm_blurv {blur} {dst} - -")
            output.append(f"op COMPOSITE blm_add {dst} - {src} add")
            continue
        
        # Phase 3: Fix vig/grn FBO references after bloom
        # After multi-pass bloom, the pipeline is:
        #   ... COMPOSITE blm_add <dst> - <src> add
        #   POST vig <src> <dst> - -        (was: POST vig <dst> <blur> - -)
        #   POST grn <dst> screen - -       (was: POST grn <blur> screen - -)
        # The next 2 lines after bloom ops should be vig and grn.
        # We handle this by tracking the last COMPOSITE blm_add.
        
        output.append(line)
    
    # Phase 3 (post-pass): Fix vig/grn FBO refs
    # After blm_add COMPOSITE, the source FBO has original+bloom.
    # vig should read from that source, not from bloom output.
    final = []
    i = 0
    while i < len(output):
        line = output[i]
        final.append(line)
        
        # Check if this is a COMPOSITE blm_add
        if "COMPOSITE blm_add" in line:
            parts = line.split()
            src_fbo = parts[5]  # the source that got bloom added
            # Next line should be POST vig
            if i + 1 < len(output) and output[i+1].startswith("op POST vig "):
                vig_parts = output[i+1].split()
                old_read = vig_parts[3]  # what vig was reading
                old_write = vig_parts[4]  # what vig was writing
                # Fix: vig reads from src_fbo (original+bloom), writes to old_read
                final.append(f"op POST vig {src_fbo} {old_read} - -")
                # And grn reads from old_read
                if i + 2 < len(output) and output[i+2].startswith("op POST grn "):
                    grn_parts = output[i+2].split()
                    final.append(f"op POST grn {old_read} {grn_parts[4]} - -")
                    i += 3
                    continue
                i += 2
                continue
        i += 1
    
    result = "\n".join(final) + "\n"
    
    # Phase 4: Update segment cost and fbos counts
    # Each segment that had bloom now has 3 more ops, update cost
    result_lines = result.splitlines()
    final2 = []
    for line in result_lines:
        if line.startswith("seg "):
            parts = line.split()
            # Count ops in this segment by scanning forward
            start = len(final2)
            # We'll update cost after we know op count
            final2.append(line)
        else:
            final2.append(line)
    
    # Recount ops per segment and update cost
    result_final = []
    i = 0
    while i < len(final2):
        line = final2[i]
        if line.startswith("seg "):
            parts = line.split()
            seg_start = float(parts[1])
            seg_end = float(parts[2])
            # Count ops until endseg
            op_count = 0
            j = i + 1
            while j < len(final2) and final2[j] != "endseg":
                if final2[j].startswith("op "):
                    op_count += 1
                j += 1
            # Update: cost = op_count, fbos stays same or +1 if needed
            fbos = int(parts[4])
            # Multi-pass bloom needs +1 FBO for blur intermediate
            # Check if this segment has blm_blurh
            has_blur = any("blm_blurh" in final2[k] for k in range(i+1, j))
            if has_blur:
                fbos = max(fbos, 3)  # at least 3 for simple, 5 for transition
            final2_result = f"seg {parts[1]} {parts[2]} {op_count} {fbos} {op_count}"
            result_final.append(final2_result)
        else:
            result_final.append(line)
        i += 1
    
    return "\n".join(result_final) + "\n"


NEW_BLOOM_CLIPS = """clip blm_bright 24 post bloom_bright 0.0 211.0 0.0 211.0 normal 77007 - - 0.0
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
endclip"""


if __name__ == "__main__":
    smt_path = "/home/z/demo-runtime-publish/milestone_v58_stable/demo.smt"
    
    # Backup
    backup = Path(smt_path + ".singlepass.bak")
    if not backup.exists():
        backup.write_text(Path(smt_path).read_text())
    
    # Upgrade
    new_content = upgrade_bloom(smt_path)
    Path(smt_path).write_text(new_content)
    
    # Verify
    lines = new_content.splitlines()
    blm_count = sum(1 for l in lines if l.startswith("clip blm_"))
    old_blm = sum(1 for l in lines if l.startswith("clip blm ") and "bloom" in l and "bright" not in l and "blur" not in l)
    bright_ops = sum(1 for l in lines if "blm_bright" in l and l.startswith("op "))
    blurh_ops = sum(1 for l in lines if "blm_blurh" in l and l.startswith("op "))
    blurv_ops = sum(1 for l in lines if "blm_blurv" in l and l.startswith("op "))
    add_ops = sum(1 for l in lines if "blm_add" in l and l.startswith("op "))
    
    print(f"=== Upgrade result ===")
    print(f"New bloom clips: {blm_count} (expected 4)")
    print(f"Old blm clip: {old_blm} (expected 0)")
    print(f"blm_bright ops: {bright_ops} (expected 13 = 13 segments)")
    print(f"blm_blurh ops: {blurh_ops} (expected 13)")
    print(f"blm_blurv ops: {blurv_ops} (expected 13)")
    print(f"blm_add ops: {add_ops} (expected 13)")
    
    if blm_count == 4 and old_blm == 0:
        print("✅ Multi-pass bloom upgrade successful!")
    else:
        print("❌ Upgrade failed!")
