#include "ios_display_layout.hpp"
#include <cassert>
#include <cmath>
#include <cstdio>

static void check(int width, int height, bool full)
{
  const auto fit = ios_display::fit(width, height, 640, 480, 1368, 800);
  assert(fit.scale > 0.f && fit.left >= 0 && fit.top >= 0);
  assert(fit.left + fit.width <= width && fit.top + fit.height <= height);
  if (full) {
    assert(fit.width == width && fit.height == height);
    assert(fit.left == 0 && fit.top == 0);
  }
  const float logical_width = fit.width / fit.scale;
  const float logical_height = fit.height / fit.scale;
  assert(std::fabs(logical_width / logical_height - float(fit.width) / fit.height) < 0.0001f);
  assert(logical_width >= 639.f && logical_height >= 479.f);
  assert(logical_width <= 1369.f && logical_height <= 801.f);
  for (bool tablet : {false, true})
  for (float user_scale : {0.5f, 1.f, 1.3f, 2.f, 5.f}) {
    const auto controls = ios_display::controls(logical_width, logical_height, ios_display::control_scale(tablet, user_scale));
    for (const auto& box : {controls.directions, controls.jump, controls.action, controls.pause}) {
      assert(box.width > 0.f && box.height > 0.f);
      assert(box.x >= 3.99f && box.y >= 3.99f);
      assert(box.x + box.width <= logical_width - 3.99f);
      assert(box.y + box.height <= logical_height - 3.99f);
    }
    assert(controls.directions.x + controls.directions.width <= controls.action.x);
    assert(controls.action.x + controls.action.width <= controls.jump.x + 0.001f);
    const float visible = controls.jump.width * (1.f - 2.f * ios_display::button_inset(tablet));
    assert(visible > 0 && visible <= controls.jump.width);
    for (int size : {0, 1, 2}) {
      const float scale = ios_display::hud_scale(tablet, size);
      assert(logical_width / scale * scale <= logical_width + 0.001f);
      assert(128.f * scale < controls.pause.x); // Pocket hit area cannot steal pause taps.
    }
  }
}

int main()
{
  for (const auto& size : {std::make_pair(480, 320), std::make_pair(568, 320),
       std::make_pair(960, 640), std::make_pair(1136, 640), std::make_pair(1024, 768),
       std::make_pair(2048, 1536), std::make_pair(1280, 800), std::make_pair(800, 450)})
    check(size.first, size.second, true);
  check(320, 480, false);
  check(2560, 640, false);
  const auto small = ios_display::fit(480, 320, 640, 480, 1368, 800);
  assert(std::fabs(480.f / small.scale - 720.f) < 0.01f);
  assert(std::fabs(320.f / small.scale - 480.f) < 0.01f);
  // Repeat after a larger window to catch accidental dependence on old dimensions.
  check(1280, 800, true);
  check(480, 320, true);
  assert(ios_display::hud_scale(true, 1) > ios_display::hud_scale(false, 1));
  assert(ios_display::button_inset(false) <= 0.1f);
  const auto phone = ios_display::controls(852.f, 480.f, ios_display::control_scale(false, 1.3f));
  assert(phone.directions.x == 12.f);
  const float visible = phone.jump.width * (1.f - 2.f * ios_display::button_inset(false));
  assert(visible >= 100.f);
  const auto larger = ios_display::controls(852.f, 480.f, ios_display::control_scale(false, 1.6f));
  assert(larger.jump.width > phone.jump.width);
  std::puts("PASS: adaptive display, edge controls, phone button size and size preference.");
}
