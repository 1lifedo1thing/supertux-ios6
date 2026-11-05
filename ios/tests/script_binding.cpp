#include <simplesquirrel/simplesquirrel.hpp>
#include <sstream>
#include <cstdio>
#include <type_traits>
static int game_random() { return 7; }
static SQInteger raw_value(HSQUIRRELVM vm) { sq_pushinteger(vm, 99); return 1; }
static SQInteger wait_once(HSQUIRRELVM vm, float) { return sq_suspendvm(vm); }
int main() {
  static_assert(std::is_same<int, SQInteger>::value, "Run this regression as 32-bit");
  ssq::VM vm(128, ssq::Libs::MATH);
  vm.addFunc("game_random", &game_random);
  vm.addFunc("raw_value", &raw_value);
  vm.addFunc("wait_once", &wait_once);
  std::istringstream script(
    "assert(game_random() == 7); assert(raw_value() == 99); "
    "phase <- 0; bush <- 0; kidnapped <- false; small <- false; "
    "worker <- newthread(function() { wait_once(0.1); "
    "bush = game_random() % 6; kidnapped = true; small = true; phase = 2; }); "
    "worker.call(); assert(phase == 0); worker.wakeup(); "
    "assert(bush == 1 && kidnapped && small && phase == 2);");
  try { vm.run(vm.compileSource(script, "32-bit-binding-regression"), true); }
  catch (const std::exception& error) { std::puts(error.what()); return 1; }
  std::puts("PASS: 32-bit int return, raw VM callback and suspended cinematic worker.");
}
