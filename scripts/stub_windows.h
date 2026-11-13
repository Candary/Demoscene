// Stub for syntax check only on Linux g++ (not a real windows.h).
#pragma once
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <cstdarg>

typedef int BOOL;
typedef int INT;
typedef unsigned int UINT;
typedef unsigned long DWORD;
typedef void* HWND;
typedef void* HDC;
typedef void* HGLRC;
typedef void* HINSTANCE;
typedef void* HCURSOR;
typedef void* HMENU;
typedef long LPARAM;
typedef unsigned int WPARAM;
typedef unsigned short WORD;
typedef short SHORT;
typedef struct tagPOINT { long x; long y; } POINT;
typedef struct tagRECT { long left; long top; long right; long bottom; } RECT;
typedef struct tagMSG { HWND hwnd; UINT message; WPARAM wParam; LPARAM lParam; DWORD time; POINT pt; } MSG;
typedef struct tagWNDCLASSEXA {
    UINT cbSize; UINT style; void* lpfnWndProc; int cbClsExtra; int cbWindowExtra;
    HINSTANCE hInstance; HICON hIcon; HCURSOR hCursor; HBRUSH hbrBackground;
    const char* lpszMenuName; const char* lpszClassName; HICON hIconSm;
} WNDCLASSEX, *PWNDCLASSEX;
typedef void* HICON;
typedef void* HBRUSH;

#define CS_OWNDC 0x20
#define CS_HREDRAW 0x2
#define CS_VREDRAW 0x1
#define WS_POPUP 0x80000000
#define WS_VISIBLE 0x10000000
#define WM_KEYDOWN 0x0100
#define WM_MOUSEWHEEL 0x020A
#define WM_LBUTTONDOWN 0x0201
#define WM_LBUTTONUP 0x0202
#define WM_MOUSEMOVE 0x0200
#define WM_RBUTTONDOWN 0x0204
#define WM_RBUTTONUP 0x0205
#define WM_DESTROY 0x0002
#define WM_QUIT 0x0012
#define WM_PAINT 0x000F
#define WM_SIZE 0x0005
#define VK_ESCAPE 0x1B
#define VK_F1 0x70
#define VK_F2 0x71
#define VK_SPACE 0x20
#define VK_NUMPAD0 0x60
#define VK_NUMPAD9 0x69
#define VK_ADD 0x6B
#define VK_SUBTRACT 0x6D
#define VK_OEM_PLUS 0xBB
#define VK_OEM_MINUS 0xBD
#define VK_LBUTTON 0x01
#define VK_RBUTTON 0x02
#define SM_CXSCREEN 0
#define SM_CYSCREEN 1
#define CS_HREDRAW CS_HREDRAW
#define IDC_ARROW nullptr
#define SW_SHOW 5
#define PM_REMOVE 0x0001
#define COLOR_WINDOW 5
#define CW_USEDEFAULT 0x80000000
#define GET_WHEEL_DELTA_WPARAM(wp) ((short)HIWORD(wp))
#define HIWORD(l) ((WORD)((((DWORD)(l)) >> 16) & 0xFFFF))
#define LOWORD(l) ((WORD)(((DWORD)(l)) & 0xFFFF))
#define GET_X_LPARAM(lp) ((int)(short)LOWORD(lp))
#define GET_Y_LPARAM(lp) ((int)(short)HIWORD(lp))
#define MAKELONG(a, b) ((LONG)(((WORD)(a)) | (((DWORD)((WORD)(b)))) << 16))
#define LRESULT long
#define CALLBACK __stdcall
#define WINAPI __stdcall
#define WM_KEYDOWN WM_KEYDOWN

HWND CreateWindowExA(DWORD, const char*, const char*, DWORD, int, int, int, int, HWND, HMENU, HINSTANCE, void*);
HWND CreateWindowEx(DWORD, const char*, const char*, DWORD, int, int, int, int, HWND, HMENU, HINSTANCE, void*);
#define CreateWindowEx CreateWindowExA
BOOL RegisterClassExA(const WNDCLASSEX*);
#define RegisterClassEx RegisterClassExA
BOOL AdjustWindowRectEx(RECT*, DWORD, BOOL, DWORD);
BOOL ShowWindow(HWND, int);
BOOL UpdateWindow(HWND);
BOOL DestroyWindow(HWND);
BOOL PostQuitMessage(int);
BOOL PeekMessageA(MSG*, HWND, UINT, UINT, UINT);
#define PeekMessage PeekMessageA
BOOL GetMessageA(MSG*, HWND, UINT, UINT);
#define GetMessage GetMessageA
BOOL TranslateMessage(const MSG*);
LRESULT DispatchMessageA(const MSG*);
#define DispatchMessage DispatchMessageA
LRESULT DefWindowProcA(HWND, UINT, WPARAM, LPARAM);
#define DefWindowProc DefWindowProcA
HINSTANCE GetModuleHandleA(const char*);
#define GetModuleHandle GetModuleHandleA
HCURSOR LoadCursorA(HINSTANCE, const char*);
#define LoadCursor LoadCursorA
int GetSystemMetrics(int);
HDC GetDC(HWND);
int ReleaseDC(HWND, HDC);
BOOL SetWindowTextA(HWND, const char*);
#define SetWindowText SetWindowTextA
void OutputDebugStringA(const char*);
HDC BeginPaint(HWND, void*);
void EndPaint(HWND, void*);
void InvalidateRect(HWND, const RECT*, BOOL);
BOOL SetCursorPos(int, int);
HCURSOR SetCursor(HCURSOR);
BOOL GetCursorPos(POINT*);
BOOL ScreenToClient(HWND, POINT*);
BOOL SetCapture(HWND);
BOOL ReleaseCapture();
BOOL GetClientRect(HWND, RECT*);

typedef void* WNDPROC;
