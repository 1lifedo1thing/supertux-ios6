#include <cassert>
#include <memory>
#include <string>
#include <tuple>
#include <optional>
#include <variant>
#include <filesystem>
#include <fmt/format.h>

// Exercise the replacement libraries together on the legacy host's libc++.
// The application itself still requires a separate iOS device runtime test.
int main()
{
  std::optional<std::unique_ptr<int>> owned;
  assert(!owned);
  owned.emplace(std::make_unique<int>(42));
  auto moved = std::move(owned);
  assert(moved && **moved == 42);
  moved.reset();
  assert(!moved);

  std::variant<int, std::string> request = 12;
  assert(request.index() == 0 && std::get<int>(request) == 12);
  request = std::string("jump");
  assert(request.index() == 1 && *std::get_if<std::string>(&request) == "jump");
  assert(std::get_if<int>(&request) == nullptr);
  const auto tuple = std::make_tuple(std::string("coin"), 7);
  assert(std::get<1>(tuple) == 7);
  assert(fmt::format("{} {}", std::get<0>(tuple), std::get<1>(tuple)) == "coin 7");
  assert(std::filesystem::is_directory(std::filesystem::canonical(".")));
  assert(std::clamp(12, 0, 8) == 8);
  return 0;
}
