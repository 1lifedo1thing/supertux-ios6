// Host-only stubs for SDL 2.0.12 configured without a window backend.
#include <SDL.h>
extern "C" SDL_bool Cocoa_IsWindowInFullscreenSpace(SDL_Window*) { return SDL_FALSE; }
extern "C" SDL_bool Cocoa_SetWindowFullscreenSpace(SDL_Window*, SDL_bool) { return SDL_FALSE; }
