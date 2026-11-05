#include "ios_display_layout.hpp"
#include <SDL.h>
#include <cassert>
#include <cstdio>
#include <cstring>
static bool covered(int width, int height, float scale, bool conservative) {
  SDL_Surface* surface = SDL_CreateRGBSurfaceWithFormat(0, width, height, 32, SDL_PIXELFORMAT_ARGB8888);
  assert(surface);
  SDL_Renderer* renderer = SDL_CreateSoftwareRenderer(surface);
  if (!renderer) { std::puts(SDL_GetError()); return false; }
  SDL_SetRenderDrawColor(renderer, 0, 0, 0, 255); SDL_RenderClear(renderer);
  SDL_RenderSetScale(renderer, scale, scale);
  const int w = conservative ? ios_display::logical_extent(width, scale) : int(float(width) / scale);
  const int h = conservative ? ios_display::logical_extent(height, scale) : int(float(height) / scale);
  const SDL_Rect clip = {0, 0, w, h};
  SDL_RenderSetClipRect(renderer, &clip);
  SDL_SetRenderDrawColor(renderer, 255, 0, 0, 255);
  const SDL_FRect rect = {0, 0, float(w), float(h)};
  SDL_RenderFillRectF(renderer, &rect); SDL_RenderPresent(renderer);
  bool complete = true;
  for (int y = 0; y < height; ++y) {
    Uint32 pixel; std::memcpy(&pixel, static_cast<Uint8*>(surface->pixels) + y * surface->pitch + (width - 1)*4, 4);
    Uint8 r,g,b,a; SDL_GetRGBA(pixel, surface->format, &r,&g,&b,&a); complete = complete && r == 255;
  }
  for (int x = 0; x < width; ++x) {
    Uint32 pixel; std::memcpy(&pixel, static_cast<Uint8*>(surface->pixels) + (height-1)*surface->pitch + x*4, 4);
    Uint8 r,g,b,a; SDL_GetRGBA(pixel, surface->format, &r,&g,&b,&a); complete = complete && r == 255;
  }
  SDL_DestroyRenderer(renderer); SDL_FreeSurface(surface); return complete;
}
int main() {
  int old_gaps = 0;
  for (int width : {480, 568, 1024, 2048}) {
    const int height = width <= 568 ? 320 : width * 3 / 4;
    const auto profile = ios_display::profile(width <= 568, true);
    const auto fit = ios_display::fit(width,height,profile.min_width,profile.min_height,1368,800);
    if (!covered(width,height,fit.scale,false)) ++old_gaps;
    assert(covered(width,height,fit.scale,true));
  }
  assert(old_gaps > 0);
  std::printf("PASS: reproduced old edge gaps at %d sizes; new fades cover every right/bottom edge pixel.\n",old_gaps);
}
