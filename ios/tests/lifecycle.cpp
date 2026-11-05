#include "ios_lifecycle.hpp"
#include <cassert>
#include <cstdio>
int main() {
  ios_lifecycle::State state;
  assert(state.can_draw(true));
  assert(!state.can_draw(false));
  for (int i = 0; i < 20; ++i) {
    state.background();
    assert(!state.can_draw(true));
    state.background(); // resign-active followed by entered-background
    state.suspend_pending = false;
    assert(!state.can_draw(false));
    state.foreground(1000);
    assert(!state.can_restore(true, 1119));
    assert(!state.can_restore(false, 1120));
    assert(state.can_restore(true, 1120));
    assert(!state.can_draw(true)); // drawable and clock must be restored first
    state.resume_pending = false;
    assert(state.can_draw(true));
  }
  // A quick Home / return can deliver both events before the runloop wakes.
  state.background(); state.foreground();
  assert(state.suspend_pending && state.resume_pending && !state.can_draw(true));
  state.suspend_pending = false; state.resume_pending = false;
  assert(state.can_draw(true));
  state.foreground(2000);
  state.background(); // a second quick Home invalidates the pending restore
  assert(!state.resume_pending && !state.can_restore(true, 2200));
  state.suspend_pending = false;
  state.foreground(2300);
  assert(!state.can_restore(true, 2419));
  assert(state.can_restore(true, 2420));
  state.retry(2420);
  assert(!state.can_restore(true, 2469) && state.can_restore(true, 2470));
  state.foreground(0xfffffff0u);
  assert(!state.can_restore(true, 20));
  assert(state.can_restore(true, 104));
  state.terminating = true;
  assert(!state.can_draw(true));
  std::puts("PASS: repeated Home/return, inactive startup, fast transitions, restore gating and termination.");
}
