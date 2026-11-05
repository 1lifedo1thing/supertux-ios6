#pragma once
#include <algorithm>
#include <cmath>

namespace ios_display {
inline float hud_scale(bool tablet, int size)
{
  const float choices[] = {0.8f, 1.f, 1.25f};
  return (tablet ? 1.6f : 1.f) * choices[std::max(0, std::min(2, size))];
}
inline float control_scale(bool tablet, float scale) { return scale * (tablet ? 1.15f : 1.f); }
inline float button_inset(bool tablet) { return 0.08f; }
inline float direction_size(bool tablet) { return 0.9f; }
enum PadDirection { PAD_LEFT = 1, PAD_RIGHT = 2, PAD_UP = 4, PAD_DOWN = 8 };
inline int directions(float x, float y)
{
  const float ax = std::fabs(x), ay = std::fabs(y);
  if (std::max(ax, ay) > 1.4f || std::sqrt(x*x + y*y) < 0.2f) return 0;
  int mask = 0;
  if (ax >= ay * 0.5f) mask |= x < 0.f ? PAD_LEFT : PAD_RIGHT;
  if (ay >= ax * 0.5f) mask |= y < 0.f ? PAD_UP : PAD_DOWN;
  return mask;
}
inline int logical_extent(int pixels, float scale)
{
  if (pixels <= 0 || scale <= 0.f) return 0;
  return static_cast<int>(std::ceil(double(pixels) / double(scale)));
}
struct Profile { int min_width, min_height; };
inline Profile profile(bool compact, bool cinematic, int width = 640, int height = 480)
{
  return compact && cinematic ? Profile{800, 600} : Profile{width, height};
}
struct Fit {
  int left, top, width, height;
  float scale;
};

// Pixels are square on iOS. Expand the visible logical area to match the
// drawable's aspect ratio, using one scale for both axes. Only extreme aspect
// ratios need bars to stay within the engine's camera bounds.
inline Fit fit(int width, int height, int min_width, int min_height,
               int max_width, int max_height)
{
  width = std::max(width, 1);
  height = std::max(height, 1);
  float scale = 1.f;
  if (width > max_width || height > max_height)
    scale = std::max(float(width) / max_width, float(height) / max_height);
  if (width / scale < min_width || height / scale < min_height)
    scale = std::min(float(width) / min_width, float(height) / min_height);
  const int view_width = std::min(width, std::max(1, int(scale * max_width)));
  const int view_height = std::min(height, std::max(1, int(scale * max_height)));
  return {(width - view_width) / 2, (height - view_height) / 2,
          view_width, view_height, scale};
}

struct Box { float x, y, width, height; };
struct Controls { Box directions, jump, action, pause; };

inline Controls controls(float width, float height, float user_scale)
{
  const float margin = 12.f;
  const float scale = std::max(0.5f, std::min(2.f, user_scale));
  const float button = std::min(height * 0.2f * scale,
                                (width - 3.f * margin) / (2.f + 4.f / 3.f + 0.5f));
  const float bottom = height - margin - button;
  return {{margin, bottom, button * 4.f / 3.f, button},
          {width - margin - button, bottom, button, button},
          {width - margin - 2.f * button, bottom, button, button},
          {width / 2.f - button / 4.f,
           margin, button / 2.f, button / 2.f}};
}
}
