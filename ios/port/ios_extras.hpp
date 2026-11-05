#pragma once
#include <cstddef>
#include <string>
#include "ios_compact_device.h"
class Controller;
class Menu;
namespace ios_extras {
enum Button { UP, DOWN, LEFT, RIGHT, ACTION, JUMP };
struct CreditsCode {
  std::size_t step = 0;
  void reset() { step = 0; }
  bool push(int button) {
    const int sequence[] = {UP, UP, DOWN, DOWN, LEFT, RIGHT, LEFT, RIGHT, ACTION, JUMP};
    const std::size_t prefix[] = {0, 1, 0, 0, 0, 0, 0, 0, 0, 0};
    while (step && button != sequence[step]) step = prefix[step-1];
    if (button == sequence[step]) ++step;
    if (step == 10) { step = 0; return true; }
    return false;
  }
  int next() const {
    const int sequence[] = {UP, UP, DOWN, DOWN, LEFT, RIGHT, LEFT, RIGHT, ACTION, JUMP};
    return sequence[step];
  }
};
inline bool compact_size(bool tablet, float short_side, float long_side) {
  return supertux_compact_dimensions(tablet, short_side, long_side) != 0;
}
bool compact_phone();
inline bool standalone_cinematic(const std::string& path) {
  return path == "levels/world1/intro.stl" || path == "levels/misc/credits.stl" ||
    path == "levels/revenge_in_redmond/intro.stl" || path == "levels/revenge_in_redmond/outro.stl";
}
bool cinematic_view();
bool set_cinematic_view(bool value);
bool all_levels_unlocked();
void credits_input(const Controller& controller, bool enabled);
void show_all_levels();
}
