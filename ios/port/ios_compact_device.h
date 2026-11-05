#pragma once
static inline int supertux_compact_dimensions(int tablet, float width, float height)
{
  const float short_side = width < height ? width : height;
  const float long_side = width > height ? width : height;
  return !tablet && short_side <= 320.f && long_side <= 568.f;
}
