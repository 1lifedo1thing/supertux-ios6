#pragma once
#include <memory>
#include <algorithm>
#include <utility>
#include <type_traits>

// Only used by this C++14 build; never mixed with a C++17 standard library.
namespace std {
template<class T> const T& clamp(const T& value, const T& lo, const T& hi) {
  return value < lo ? lo : hi < value ? hi : value;
}
}
