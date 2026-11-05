#pragma once
#include <SDL.h>
#include <algorithm>
#include <cstring>
#include <stdexcept>

namespace ios_pixels {
// Normalize before taking atlas subviews: a borrowed pixel buffer does not
// inherit its owner's palette, colour key, or software-blitter state.
inline SDL_Surface* rgba(SDL_Surface& source)
{
  if (!source.format || !source.pixels || source.w <= 0 || source.h <= 0 ||
      source.format->BytesPerPixel < 1 || source.format->BytesPerPixel > 4 ||
      source.pitch < source.w * source.format->BytesPerPixel)
    throw std::runtime_error("Invalid source image for RGBA upload");
  SDL_Surface* result = SDL_CreateRGBSurfaceWithFormat(0, source.w, source.h, 32, SDL_PIXELFORMAT_ABGR8888);
  if (!result) throw std::runtime_error(SDL_GetError());
  const bool lock = SDL_MUSTLOCK(&source);
  if (lock && SDL_LockSurface(&source) != 0) {
    SDL_FreeSurface(result);
    throw std::runtime_error(SDL_GetError());
  }
  Uint32 key = 0;
  const bool keyed = SDL_GetColorKey(&source, &key) == 0;
  const int bytes = source.format->BytesPerPixel;
  for (int y = 0; y < source.h; ++y) {
    const auto* src = static_cast<const Uint8*>(source.pixels) + y * source.pitch;
    auto* dst = static_cast<Uint8*>(result->pixels) + y * result->pitch;
    for (int x = 0; x < source.w; ++x) {
      Uint32 pixel = 0;
      if (bytes == 3) {
#if SDL_BYTEORDER == SDL_BIG_ENDIAN
        pixel = (Uint32(src[0]) << 16) | (Uint32(src[1]) << 8) | src[2];
#else
        pixel = src[0] | (Uint32(src[1]) << 8) | (Uint32(src[2]) << 16);
#endif
      } else {
        if (bytes == 1) pixel = *src;
        else if (bytes == 2) { Uint16 value; std::memcpy(&value, src, 2); pixel = value; }
        else std::memcpy(&pixel, src, 4);
      }
      Uint8 r, g, b, a;
      SDL_GetRGBA(pixel, source.format, &r, &g, &b, &a);
      if (keyed && pixel == key) a = 0;
      const Uint32 mapped = SDL_MapRGBA(result->format, r, g, b, a);
      std::memcpy(dst, &mapped, 4);
      src += bytes;
      dst += 4;
    }
  }
  if (lock) SDL_UnlockSurface(&source);
  return result;
}
inline SDL_Surface* crop(const SDL_Surface& source, int left, int top, int width, int height)
{
  if (source.format->format != SDL_PIXELFORMAT_ABGR8888 || width <= 0 || height <= 0)
    throw std::runtime_error("Invalid normalized atlas region");
  SDL_Surface* result = SDL_CreateRGBSurfaceWithFormat(0, width, height, 32, SDL_PIXELFORMAT_ABGR8888);
  if (!result) throw std::runtime_error(SDL_GetError());
  for (int y = 0; y < height; ++y)
    std::memset(static_cast<Uint8*>(result->pixels) + y * result->pitch, 0, width * 4);
  const int x0 = std::max(0, left), y0 = std::max(0, top);
  const int x1 = std::min(source.w, left + width), y1 = std::min(source.h, top + height);
  if (x1 > x0 && y1 > y0) {
    for (int y = y0; y < y1; ++y)
      std::memcpy(static_cast<Uint8*>(result->pixels) + (y - top) * result->pitch + (x0 - left) * 4,
                  static_cast<const Uint8*>(source.pixels) + y * source.pitch + x0 * 4,
                  (x1 - x0) * 4);
  }
  return result;
}

}
