#include "ios_display_layout.hpp"
#include "ios_extras.hpp"
#include <cassert>
#include <cmath>
#include <cstdio>
int main() {
  for (int width : {480, 568, 960, 1136}) {
    const int height = width < 900 ? 320 : 640;
    const auto movie = ios_display::profile(true, true);
    const auto game = ios_display::profile(true, false);
    const auto film = ios_display::fit(width, height, movie.min_width, movie.min_height, 1368, 800);
    const auto play = ios_display::fit(width, height, game.min_width, game.min_height, 1368, 800);
    assert(film.width == width && film.height == height && play.width == width && play.height == height);
    assert(film.width / film.scale >= 799 && film.height / film.scale >= 599);
    assert(play.scale >= film.scale);
    if (height == 320) assert(play.scale > film.scale);
    for (const auto& fit : {film, play}) {
      const int w = ios_display::logical_extent(width, fit.scale);
      const int h = ios_display::logical_extent(height, fit.scale);
      assert(w * double(fit.scale) >= width && h * double(fit.scale) >= height);
    }
  }
  for (int width : {1024, 2048}) {
    const auto movie = ios_display::profile(false, true);
    const auto game = ios_display::profile(false, false);
    assert(movie.min_width == game.min_width && movie.min_height == game.min_height);
  }
  assert(ios_extras::standalone_cinematic("levels/world1/intro.stl"));
  assert(ios_extras::standalone_cinematic("levels/misc/credits.stl"));
  assert(!ios_extras::standalone_cinematic("levels/world1/welcome_antarctica.stl"));
  using namespace ios_display;
  for (float x : {-0.15f, 0.f, 0.15f}) {
    assert(directions(x, -.8f) == PAD_UP);
    assert(directions(x, .8f) == PAD_DOWN);
  }
  assert(directions(-.8f, .1f) == PAD_LEFT);
  assert(directions(.8f, -.1f) == PAD_RIGHT);
  assert(directions(-.8f, -.8f) == (PAD_LEFT | PAD_UP));
  assert(directions(.8f, -.8f) == (PAD_RIGHT | PAD_UP));
  assert(directions(-.8f, .8f) == (PAD_LEFT | PAD_DOWN));
  assert(directions(.8f, .8f) == (PAD_RIGHT | PAD_DOWN));
  assert(directions(.1f, .1f) == 0);
  assert(logical_extent(0, 0.f) == 0);
  std::puts("PASS: larger gameplay, fixed cinematic profile, full edge coverage, straight and diagonal D-pad input.");
}
