#pragma once
#include <cstdint>
namespace ios_lifecycle {
struct State {
  bool active = true;
  bool suspend_pending = false;
  bool resume_pending = false;
  bool terminating = false;
  std::uint32_t ready_at = 0;
  void background() { active = false; suspend_pending = true; resume_pending = false; }
  void foreground(std::uint32_t now = 0) { active = true; resume_pending = true; ready_at = now + 120; }
  bool can_restore(bool native_active, std::uint32_t now) const {
    return active && native_active && resume_pending && !suspend_pending && !terminating &&
      static_cast<std::int32_t>(now - ready_at) >= 0;
  }
  void retry(std::uint32_t now) { ready_at = now + 50; }
  bool can_draw(bool native_active) const {
    return native_active && active && !suspend_pending && !resume_pending && !terminating;
  }
};
}
