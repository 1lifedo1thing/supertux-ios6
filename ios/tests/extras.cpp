#include "ios_extras.hpp"
#include <cassert>
#include <cstdio>
using namespace ios_extras;
int main() {
  assert(compact_size(false, 320, 480));
  assert(compact_size(false, 568, 320));
  assert(!compact_size(true, 320, 480));
  assert(!compact_size(true, 768, 1024));
  assert(!compact_size(false, 375, 667));
  assert(!compact_size(false, 414, 736));
  CreditsCode code;
  const int sequence[] = {UP, UP, DOWN, DOWN, LEFT, RIGHT, LEFT, RIGHT, ACTION, JUMP};
  for (int attempt = 0; attempt < 2; ++attempt)
    for (int i = 0; i < 10; ++i) assert(code.push(sequence[i]) == (i == 9));
  code.push(UP); code.push(LEFT);
  assert(code.step == 0);
  code.push(UP); code.push(UP); code.push(UP);
  assert(code.step == 2); // repeated prefix doesn't require starting over
  for (int i = 2; i < 10; ++i) assert(code.push(sequence[i]) == (i == 9));
  code.push(UP); code.reset(); assert(code.step == 0);
  std::puts("PASS: compact phone detection, tablet/larger-screen exclusion, credits code and error recovery.");
}
