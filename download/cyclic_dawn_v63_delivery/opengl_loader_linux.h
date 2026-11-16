// path: cyclic_dawn_v63/opengl_loader_linux.h
// Linux/Mesa GL loader: GL_GLEXT_PROTOTYPES gives direct access to GL 3.3 core
// functions from libGL.so — no wglGetProcAddress needed.
// On Windows, use the original opengl_loader.h (wglGetProcAddress-based).
#pragma once

#define GL_GLEXT_PROTOTYPES 1
#include <GL/gl.h>
#include <GL/glext.h>

#ifndef APIENTRY
#define APIENTRY
#endif

// Stub: on Linux, all GL 3.3 core functions are real symbols in libGL.so.
// On Windows, this would call wglGetProcAddress for each function.
static inline bool LoadOpenGLFunctions() { return true; }
