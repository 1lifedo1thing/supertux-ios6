#include "ios_pixels.hpp"
#include <cassert>
#include <cstdio>

static void expect(SDL_Surface* surface, int x, int y, int r, int g, int b, int a)
{
  Uint32 pixel;
  std::memcpy(&pixel, static_cast<Uint8*>(surface->pixels) + y * surface->pitch + x * 4, 4);
  Uint8 rr, gg, bb, aa;
  SDL_GetRGBA(pixel, surface->format, &rr, &gg, &bb, &aa);
  assert(rr == r && gg == g && bb == b && aa == a);
}

int main()
{
  SDL_Surface* palette = SDL_CreateRGBSurfaceWithFormat(0, 3, 2, 8, SDL_PIXELFORMAT_INDEX8);
  SDL_Color colors[] = {{255, 0, 0, 255}, {0, 255, 0, 128}, {0, 0, 255, 255}};
  assert(SDL_SetPaletteColors(palette->format->palette, colors, 0, 3) == 0);
  auto* p = static_cast<Uint8*>(palette->pixels);
  p[0] = 0; p[1] = 1; p[2] = 2;
  p[palette->pitch] = 2; p[palette->pitch+1] = 1; p[palette->pitch+2] = 0;
  SDL_SetColorKey(palette, SDL_TRUE, 2);
  SDL_Surface* rgba = ios_pixels::rgba(*palette);
  expect(rgba, 0, 0, 255, 0, 0, 255);
  expect(rgba, 1, 0, 0, 255, 0, 128);
  expect(rgba, 2, 0, 0, 0, 255, 0);
  expect(rgba, 0, 1, 0, 0, 255, 0);
  SDL_Surface* cropped = ios_pixels::crop(*rgba, -1, -1, 5, 4);
  expect(cropped, 0, 0, 0, 0, 0, 0);
  expect(cropped, 1, 1, 255, 0, 0, 255);
  expect(cropped, 2, 2, 0, 255, 0, 128);
  expect(cropped, 4, 3, 0, 0, 0, 0);
  SDL_FreeSurface(cropped);
  SDL_Surface* view = SDL_CreateRGBSurfaceFrom(static_cast<Uint8*>(rgba->pixels) + 4, 1, 2, 32,
      rgba->pitch, rgba->format->Rmask, rgba->format->Gmask, rgba->format->Bmask, rgba->format->Amask);
  SDL_Surface* copy = ios_pixels::rgba(*view);
  expect(copy, 0, 1, 0, 255, 0, 128);
  SDL_FreeSurface(copy); SDL_FreeSurface(view); SDL_FreeSurface(rgba); SDL_FreeSurface(palette);
  for (Uint32 format : {SDL_PIXELFORMAT_RGB24, SDL_PIXELFORMAT_RGB565, SDL_PIXELFORMAT_ARGB8888}) {
    SDL_Surface* source = SDL_CreateRGBSurfaceWithFormat(0, 3, 2, SDL_BITSPERPIXEL(format), format);
    SDL_FillRect(source, nullptr, SDL_MapRGBA(source->format, 255, 0, 255, 255));
    SDL_Surface* converted = ios_pixels::rgba(*source);
    expect(converted, 2, 1, 255, 0, 255, 255);
    SDL_FreeSurface(converted); SDL_FreeSurface(source);
  }
  std::puts("PASS: palette alpha, color key, padded rows, atlas subview, 16/24/32-bit pixels.");
}
