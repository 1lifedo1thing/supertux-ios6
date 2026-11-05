#!/usr/bin/env python3
"""Prepare an isolated Xcode 6 compatibility tree without editing upstream src/."""
from pathlib import Path
import hashlib
import json
import re
import shutil

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
OUT = HERE / 'generated'

def write(name, text):
    p = OUT / name
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists() or p.read_text(encoding='utf-8') != text:
        p.write_text(text, encoding='utf-8', newline='\n')

def prepare_source(relative, text):
    if relative == 'video/sdl/sdl_video_system.cpp':
        text = text.replace('SDL_CreateRenderer(m_sdl_window.get(), -1, 0)',
                            'SDL_CreateRenderer(m_sdl_window.get(), -1, SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC)')
    if relative == 'worldmap/tux.cpp':
        text = '#include "ios_extras.hpp"\n' + text
        text = text.replace('if ((!level || level->is_solved() || level->is_perfect()', 'if ((!level || level->is_solved() || level->is_perfect() || ios_extras::all_levels_unlocked()')
        text = text.replace('if (special_tile && special_tile->get_blocking())', 'if (special_tile && special_tile->get_blocking() && !ios_extras::all_levels_unlocked())')
    if relative == 'supertux/game_session.cpp':
        text = '#include "ios_extras.hpp"\n#include "video/sdl/sdl_video_system.hpp"\n' + text
        marker = 'GameSession::restart_level(bool after_death, bool preserve_music)\n{'
        assert marker in text
        text = text.replace(marker, marker + '''
  if (ios_extras::set_cinematic_view(ios_extras::standalone_cinematic(m_levelfile)))
    static_cast<SDLVideoSystem*>(VideoSystem::current())->ios_refresh_viewport();
''')
    if relative == 'squirrel/supertux_api.cpp':
        text = '#include "ios_extras.hpp"\n#include "video/sdl/sdl_video_system.hpp"\n#include "object/camera.hpp"\n' + text
        marker = '  session->get_current_level().m_is_in_cutscene = true;'
        assert marker in text
        text = text.replace(marker, marker + '''
  if (ios_extras::set_cinematic_view(true)) {
    static_cast<SDLVideoSystem*>(VideoSystem::current())->ios_refresh_viewport();
    session->get_current_sector().get_camera().update(0.f);
    ScreenManager::current()->on_window_resize();
  }
''')
    if relative == 'supertux/screen_manager.cpp':
        text = '#include "video/sdl/sdl_video_system.hpp"\n#include "object/camera.hpp"\n#include "ios_extras.hpp"\n#include <SDL_system.h>\n#include <exception>\n#include "ios_lifecycle.hpp"\n#include "ios_options.hpp"\nextern "C" void supertux_ios_pump_run_loop(void);\nextern "C" int supertux_ios_is_active(void);\nextern "C" int SuperTux_UIKitRestoreDrawable(void);\nextern "C" void supertux_ios_hide_loading(void);\n' + text
        text = text.replace('bool always_draw = g_debug.draw_redundant_frames || g_config->frame_prediction;',
                            '// CADisplayLink paces presentation; the simulation keeps its fixed 15 ms step.\n  bool always_draw = true;')
        text += '''
bool ScreenManager::ios_pause_only() const
{
  if (m_screen_stack.empty()) return false;
  auto* session = dynamic_cast<GameSession*>(m_screen_stack.back().get());
  if (!session) return false;
  if (session->has_active_sequence() || Level::current()->m_is_in_cutscene ||
      Level::current()->m_suppress_pause_menu) return true;
  for (auto* player : session->get_current_sector().get_players())
    if (player->ios_controls_locked()) return true;
  return false;
}
'''
        text += '''
void ScreenManager::ios_update_viewport()
{
  if (!ios_extras::set_cinematic_view(ios_pause_only())) return;
  static_cast<SDLVideoSystem&>(m_video_system).ios_refresh_viewport();
  on_window_resize();
  auto* session = dynamic_cast<GameSession*>(m_screen_stack.back().get());
  if (session) session->get_current_sector().get_camera().update(0.f);
}
'''
        text = text.replace('void ScreenManager::loop_iter()\n{', 'void ScreenManager::loop_iter()\n{\n  ios_update_viewport();')
        text = text.replace('    Compositor compositor(', '    ios_update_viewport();\n    Compositor compositor(')
        text = text.replace('    m_mobile_controller.update();', '    m_mobile_controller.set_pause_only(ios_pause_only());\n    m_mobile_controller.update();')
        text = text.replace('  if (g_config->mobile_controls)\n    m_mobile_controller.draw(context);',
                            '  if (g_config->mobile_controls) {\n    m_mobile_controller.set_pause_only(ios_pause_only());\n    m_mobile_controller.draw(context);\n  }')
        text = text.replace('  handle_screen_switch();\n#ifdef __EMSCRIPTEN__', '  handle_screen_switch();\n  supertux_ios_hide_loading();\n#ifdef __EMSCRIPTEN__')
        text = text.replace('    m_mobile_controller.set_pause_only(ios_pause_only());', '''    auto* active_session = dynamic_cast<GameSession*>(m_screen_stack.back().get());
    const bool credits = active_session && active_session->get_level_file() == "levels/misc/credits.stl";
    m_mobile_controller.set_credits_code(credits);
    m_mobile_controller.set_pause_only(ios_pause_only());''')
        text = text.replace('  SquirrelVirtualMachine::current()->update(g_game_time);', '''  auto* code_session = dynamic_cast<GameSession*>(m_screen_stack.back().get());
  ios_extras::credits_input(controller, code_session &&
    code_session->get_level_file() == "levels/misc/credits.stl" && !MenuManager::instance().is_active());
  SquirrelVirtualMachine::current()->update(g_game_time);''')
        original = '  while (!m_screen_stack.empty()) {\n    loop_iter();\n  }'
        assert original in text
        text = text.replace(original, '''  SDL_Window* window = SDL_GetKeyboardFocus();
  if (!window) window = SDL_GetWindowFromID(1);
  if (!window) throw std::runtime_error("No iOS window for display synchronization");
  struct IOSFrames {
    ScreenManager* manager;
    std::exception_ptr error;
    bool drawing;
    ios_lifecycle::State lifecycle;
    Uint32 last_frame;
  } frames{this, std::exception_ptr(), false, {}, SDL_GetTicks()};
  const auto watch = +[](void* opaque, SDL_Event* event) -> int {
    auto& state = static_cast<IOSFrames*>(opaque)->lifecycle;
    if (event->type == SDL_APP_WILLENTERBACKGROUND || event->type == SDL_APP_DIDENTERBACKGROUND)
      state.background();
    if (event->type == SDL_APP_DIDENTERFOREGROUND) state.foreground(SDL_GetTicks());
    if (event->type == SDL_APP_TERMINATING) state.terminating = true;
    return 1;
  };
  const auto draw_frame = +[](void* opaque) {
    auto& frames = *static_cast<IOSFrames*>(opaque);
    if (!frames.lifecycle.can_draw(supertux_ios_is_active() != 0) || frames.drawing ||
        frames.error || frames.manager->m_screen_stack.empty()) return;
    frames.drawing = true;
    try { frames.manager->loop_iter(); }
    catch (...) { frames.error = std::current_exception(); }
    frames.last_frame = SDL_GetTicks();
    frames.drawing = false;
  };
  SDL_AddEventWatch(watch, &frames);
  SDL_iPhoneSetEventPump(SDL_FALSE);
  if (SDL_iPhoneSetAnimationCallback(window, 1, draw_frame, &frames) != 0) {
    SDL_DelEventWatch(watch, &frames);
    SDL_iPhoneSetEventPump(SDL_TRUE);
    throw std::runtime_error(SDL_GetError());
  }
  bool pause_on_resume = false;
  int restore_attempts = 0;
  while (!m_screen_stack.empty() && !frames.error && !frames.lifecycle.terminating) {
    supertux_ios_pump_run_loop();
    try {
      auto& state = frames.lifecycle;
      if (state.suspend_pending) {
        // No GPU work here: UIKit may already be entering the background.
        m_input_manager.reset();
        m_mobile_controller.reset();
        SoundManager::current()->pause_sounds();
        SoundManager::current()->pause_music();
        ios_options::save();
        pause_on_resume = true;
        restore_attempts = 0;
        state.suspend_pending = false;
      }
      if (state.can_restore(supertux_ios_is_active() != 0, SDL_GetTicks())) {
        if (SuperTux_UIKitRestoreDrawable() != 0) {
          if (++restore_attempts > 20) throw std::runtime_error(SDL_GetError());
          state.retry(SDL_GetTicks());
          continue;
        }
        // A live display link resumes naturally; replacing it during a quick
        // Home/return transition needlessly mutates UIKit's callback schedule.
        m_input_manager.reset();
        m_mobile_controller.reset();
        auto* session = dynamic_cast<GameSession*>(m_screen_stack.back().get());
        if (pause_on_resume && session && session->is_active() && !Level::current()->m_suppress_pause_menu) session->toggle_pause();
        if (!session || !MenuManager::instance().is_active()) {
          SoundManager::current()->resume_music();
          SoundManager::current()->resume_sounds();
        }
        pause_on_resume = false;
        last_time = std::chrono::steady_clock::now();
        elapsed_time = 0.f;
        frames.last_frame = SDL_GetTicks();
        state.resume_pending = false;
      }
      if (state.can_draw(supertux_ios_is_active() != 0) && SDL_GetTicks() - frames.last_frame > 500) {
        if (SDL_iPhoneSetAnimationCallback(window, 1, draw_frame, &frames) != 0)
          throw std::runtime_error(SDL_GetError());
        frames.last_frame = SDL_GetTicks();
      }
    } catch (...) { frames.error = std::current_exception(); }
  }
  SDL_iPhoneSetAnimationCallback(window, 1, nullptr, nullptr);
  SDL_DelEventWatch(watch, &frames);
  SDL_iPhoneSetEventPump(SDL_TRUE);
  if (frames.error) std::rethrow_exception(frames.error);''')
    if relative == 'supertux/screen_manager.hpp':
        text = text.replace('  void loop_iter();', '  void loop_iter();\n  bool ios_pause_only() const;\n  void ios_update_viewport();')
    if relative == 'object/player.hpp':
        text = text.replace('  inline bool is_scripting_activated()', '  bool ios_controls_locked() const;\n  inline bool is_scripting_activated()')
    if relative == 'object/player.cpp':
        marker = 'Player::add_bonus(const std::string& bonustype)\n{'
        text = text.replace(marker, marker + '''
  // Replaying the picnic from a powered-up save must still start in the
  // scripted grown form, so Nolok's single hit leaves Tux small.
  auto* session = GameSession::current();
  if (bonustype == "grow" && session && session->get_level_file() == "levels/world1/intro.stl")
    return set_bonus(BONUS_GROWUP);
''')
        text += '''
bool Player::ios_controls_locked() const
{
  return m_deactivated || m_controller == m_scripting_controller.get();
}
'''
    if relative == 'audio/sound_manager.cpp':
        # This short PCM effect is just above the desktop streaming threshold.
        # Keep it buffered to avoid stream setup on every explosion.
        text = text.replace('if (file->m_size < 100000)', 'if (file->m_size < 100000 || filename == "sounds/explosion.wav")')
        text = text.replace('if (file->m_size >= 100000)', 'if (file->m_size >= 100000 && filename != "sounds/explosion.wav")')
    if relative == 'supertux/resources.cpp':
        text = '#include "audio/sound_manager.hpp"\n' + text
        marker = 'Resources::Resources()\n{\n  load();'
        assert marker in text
        text = text.replace(marker, marker + '''
  SpriteManager::current()->create("images/objects/explosion/explosion.sprite");
  SpriteManager::current()->create("images/objects/lightmap_light/lightmap_light-medium.sprite");
  SpriteManager::current()->create("images/objects/lightmap_light/lightmap_light-large.sprite");
  SoundManager::current()->preload("sounds/explosion.wav");
  SoundManager::current()->preload("sounds/firecracker.ogg");
''')
    if relative == 'object/explosion.cpp':
        original = '''      if(!Sector::current()->free_line_of_sight(center, obj->get_pos(), true))
        continue;

'''
        assert original in text
        text = text.replace(original, '')
        marker = '      Vector add_speed = glm::normalize(direction) * force;'
        text = text.replace(marker, '''      // Trace only objects this explosion can affect. Distant solid blocks
      // cannot be shaken, opened or broken by this blast.
      const auto candidate_player = dynamic_cast<Player*>(obj);
      const auto candidate_badguy = dynamic_cast<WalkingBadguy*>(obj);
      const bool moves = (candidate_player && !candidate_player->is_stone()) ||
        (candidate_badguy && candidate_badguy->is_active() && !candidate_badguy->is_heavy());
      const bool block = distance <= 100.f &&
        (dynamic_cast<BonusBlock*>(obj) || dynamic_cast<Brick*>(obj));
      const bool weak = distance <= 60.f && dynamic_cast<WeakBlock*>(obj);
      if (!(moves || block || weak)) continue;
      if (!Sector::current()->free_line_of_sight(center, obj->get_pos(), true)) continue;

''' + marker)
    if relative == 'video/texture_manager.cpp':
        text = '#include "ios_pixels.hpp"\n' + text
        start = text.index('  assert(rect.valid());', text.index('TextureManager::create_image_surface_raw'))
        end = text.index('  return subimage;', start) + len('  return subimage;')
        text = text[:start] + '''  if (!rect.valid()) throw std::runtime_error("Invalid atlas region for " + filename);
  return SDLSurfacePtr(ios_pixels::crop(get_surface(filename), rect.left, rect.top,
                                      rect.get_width(), rect.get_height()));''' + text[end:]
    if relative == 'video/sdl_surface.cpp':
        text = '#include "ios_pixels.hpp"\n' + text
        text = text.replace('    return surface;', '    return SDLSurfacePtr(ios_pixels::rgba(*surface));')
    if relative == 'video/sdl/sdl_texture.cpp':
        text = '#include "ios_pixels.hpp"\n#include "video/sdl_surface.hpp"\n' + text
        start = text.index('  SDL_DestroyTexture(m_texture);', text.index('SDLTexture::reload'))
        end = text.index('  m_width = image.w;', start)
        text = text[:start] + '''  auto* renderer = static_cast<SDLScreenRenderer&>(VideoSystem::current()->get_renderer()).get_sdl_renderer();
  SDLSurfacePtr converted;
  if (image.format->format != SDL_PIXELFORMAT_ABGR8888)
    converted.reset(ios_pixels::rgba(*const_cast<SDL_Surface*>(&image)));
  const SDL_Surface& upload = converted ? *converted : image;
  SDL_Texture* replacement = SDL_CreateTexture(renderer, SDL_PIXELFORMAT_ABGR8888,
                                               SDL_TEXTUREACCESS_STATIC, upload.w, upload.h);
  if (!replacement) throw std::runtime_error(std::string("Texture allocation: ") + SDL_GetError());
  if (SDL_UpdateTexture(replacement, nullptr, upload.pixels, upload.pitch) != 0 ||
      SDL_SetTextureBlendMode(replacement, SDL_BLENDMODE_BLEND) != 0) {
    const std::string error = SDL_GetError();
    SDL_DestroyTexture(replacement);
    throw std::runtime_error(std::string("RGBA texture upload: ") + error);
  }
  SDL_DestroyTexture(m_texture);
  m_texture = replacement;

''' + text[end:]
    if relative == 'control/mobile_controller.hpp':
        text = text.replace('  void buzz();', '  void buzz();\n  void reset();\n  void set_pause_only(bool value);\n  void set_credits_code(bool value) { m_credits_code = value; }')
        text = text.replace('  int m_screen_width, m_screen_height;', '  bool m_pause_only = false;\n  bool m_credits_code = false;\n  int m_screen_width, m_screen_height;')
    if relative == 'supertux/player_status_hud.cpp':
        text = '#include "ios_options.hpp"\n' + text
        text = text.replace('context.transform().scale = 1.f;', 'context.transform().scale = ios_options::hud_scale();')
    if relative == 'video/sdl/sdl_video_system.hpp':
        text = text.replace('  virtual void apply_config() override;', '  virtual void apply_config() override;\n  void ios_refresh_viewport();')
    if relative == 'video/viewport.cpp':
        text = '#include "ios_display_layout.hpp"\n#include "ios_extras.hpp"\n' + text
        text = text.replace('static_cast<int>(static_cast<float>(m_rect.get_width()) / m_scale.x)', 'ios_display::logical_extent(m_rect.get_width(), m_scale.x)')
        text = text.replace('static_cast<int>(static_cast<float>(m_rect.get_height()) / m_scale.y)', 'ios_display::logical_extent(m_rect.get_height(), m_scale.y)')
        marker = 'Viewport::from_size(const Size& target_size, const Size& desktop_size)\n{'
        assert marker in text
        text = text.replace(marker, marker + '''
  const auto profile = ios_display::profile(ios_extras::compact_phone(), ios_extras::cinematic_view(),
                                             s_min_size.width, s_min_size.height);
  const auto fit = ios_display::fit(target_size.width, target_size.height,
      profile.min_width, profile.min_height, s_max_size.width, s_max_size.height);
  return Viewport(Rect(fit.left, fit.top, Size(fit.width, fit.height)),
                  Vector(fit.scale, fit.scale));
''')
    if relative == 'video/sdl/sdl_video_system.cpp':
        start = text.index('#ifndef __ANDROID__', text.index('SDLVideoSystem::apply_config()'))
        end = text.index('    m_viewport = Viewport::from_size', start)
        text = text[:start] + '''    Size target_size;
    if (SDL_GetRendererOutputSize(m_sdl_renderer.get(), &target_size.width, &target_size.height) != 0 ||
        target_size.width <= 0 || target_size.height <= 0)
      target_size = get_window_size();
''' + text[end:]
        text += '''
void SDLVideoSystem::ios_refresh_viewport()
{
  Size size;
  if (SDL_GetRendererOutputSize(m_sdl_renderer.get(), &size.width, &size.height) != 0 ||
      size.width <= 0 || size.height <= 0) size = get_window_size();
  m_viewport = Viewport::from_size(size, m_desktop_size);
  m_lightmap.reset(new SDLTextureRenderer(*this, m_sdl_renderer.get(), m_viewport.get_screen_size(), 5));
}
'''
    if relative == 'control/mobile_controller.cpp':
        text = '#include "ios_display_layout.hpp"\n#include "ios_options.hpp"\n#include "control/input_manager.hpp"\n' + text
        text = text.replace('g_config->m_mobile_controls_scale', 'ios_options::control_scale()')
        start = text.index('    m_rect_directions.set_size(')
        end = text.index('    m_rect_cheats.set_size(', start)
        text = text[:start] + '''    const auto layout = ios_display::controls(width, height, m_mobile_controls_scale);
    const auto box = [](const ios_display::Box& b) {
      return Rectf(Vector(b.x, b.y), Sizef(b.width, b.height));
    };
    m_rect_directions = box(layout.directions);
    m_draw_directions = Rectf::from_center(Vector(m_rect_directions.get_left() + m_rect_directions.get_height() * ios_display::direction_size(ios_options::is_tablet()) / 2.f, m_rect_directions.get_bottom() - m_rect_directions.get_height() * ios_display::direction_size(ios_options::is_tablet()) / 2.f),
      Sizef(m_rect_directions.get_height() * ios_display::direction_size(ios_options::is_tablet()),
            m_rect_directions.get_height() * ios_display::direction_size(ios_options::is_tablet())));
    m_rect_jump = box(layout.jump);
    m_draw_jump = m_rect_jump.grown(-m_rect_jump.get_height() * ios_display::button_inset(ios_options::is_tablet()));
    m_rect_action = box(layout.action);
    m_draw_action = m_rect_action.grown(-m_rect_action.get_height() * ios_display::button_inset(ios_options::is_tablet()));
    m_rect_escape = box(layout.pause);
    m_draw_escape = m_rect_escape.grown(-m_rect_escape.get_height() / 4);

''' + text[end:]
        start = text.index('  context.color().draw_surface_scaled(m_tex_dirs,')
        end = text.index('  context.color().draw_surface_scaled(m_input[CONTROL_INT(ESCAPE)]', start)
        text = text[:start] + '  if (!m_pause_only) {\n' + text[start:end] + '  }\n\n' + text[end:]
        text = text.replace('  if (g_config->developer_mode)\n  {', '  if (g_config->developer_mode && !m_pause_only)\n  {')
        text = text.replace('  Vector pos(event.x * float(m_screen_width), event.y * float(m_screen_height));',
                            '  Vector pos(event.x * float(m_screen_width), event.y * float(m_screen_height));')
        # Keep finger tracking, but only consume the pause region during sequences.
        text = text.replace('  return m_rect_jump.contains(pos) ||', '  if (m_pause_only && !m_credits_code) return m_rect_escape.contains(pos);\n  return m_rect_jump.contains(pos) ||')
        marker = 'MobileController::activate_widget_at_pos(float x, float y)\n{'
        text = text.replace(marker, marker + '''
  if (m_pause_only && !m_credits_code) {
    if (m_rect_escape.contains(Vector(x, y))) m_input.set(CONTROL_INT(ESCAPE), true);
    return;
  }
''')
        text += '''
void MobileController::set_pause_only(bool value)
{
  if (value != m_pause_only) {
    InputManager::current()->reset();
    reset();
    m_pause_only = value;
  }
}
'''
        text += '''
void MobileController::reset()
{
  m_fingers.clear();
  m_input.reset();
  m_input_last.reset();
}
'''
        text = text.replace('  PaintStyle translucent;', '''  m_rect_item = Rectf(Vector(0, 0), Sizef(128.f, 128.f) * ios_options::hud_scale());
  PaintStyle translucent;''')
        start = text.index('  Rectf up = m_rect_directions;')
        end = text.index('\n}', start)
        text = text[:start] + '''  const Vector center = m_draw_directions.get_middle();
  const int direction = ios_display::directions((x - center.x) / (m_draw_directions.get_width() / 2.f),
                                               (y - center.y) / (m_draw_directions.get_height() / 2.f));
  if (direction & ios_display::PAD_LEFT) m_input.set(CONTROL_INT(LEFT), true);
  if (direction & ios_display::PAD_RIGHT) m_input.set(CONTROL_INT(RIGHT), true);
  if (direction & ios_display::PAD_UP) m_input.set(CONTROL_INT(UP), true);
  if (direction & ios_display::PAD_DOWN) m_input.set(CONTROL_INT(DOWN), true);
''' + text[end:]
        text = text.replace('    m_rect_jump = box(layout.jump);', '    m_rect_directions = m_draw_directions.grown(m_draw_directions.get_width() * 0.2f);\n    m_rect_jump = box(layout.jump);')
        start = text.index('  // Allow using on-screen controls with the mouse')
        end = text.index('  for (auto& i : m_fingers)', start)
        text = text[:start] + text[end:]

    if 'std::string_view' in text and '#include <string_view>' not in text:
        text = '#include <string_view>\n' + text
    text = text.replace('std::string_view', 'std::string')
    text = text.replace('.preciseX', '.x').replace('.preciseY', '.y')
    if relative == 'editor/object_option.cpp':
        for name in ['checkbox', 'textbox', 'button', 'dropdown']:
            text = text.replace('return ' + name + ';', 'return std::move(' + name + ');')
    if relative == 'video/texture.hpp':
        text = '#include <string>\n#include <tuple>\n' + text
        # Apple Clang 6 can recurse/crash evaluating optional<tuple<...>>.
        # This private cache-key field needs only empty/value ownership.
        text = text.replace('std::optional<Key> m_cache_key;', 'std::unique_ptr<Key> m_cache_key;')
    if relative == 'video/texture_manager.cpp':
        text = text.replace('texture->m_cache_key = key;', 'texture->m_cache_key.reset(new Texture::Key(key));')
    if relative == 'gui/menu_manager.hpp':
        text = text.replace('std::unique_ptr<T> current = nullptr;', 'SettableItem() : current(), next(), has_next(false) {}\n    std::unique_ptr<T> current;')
        text = text.replace('std::unique_ptr<T> next = nullptr;', 'std::unique_ptr<T> next;').replace('bool has_next = false;', 'bool has_next;')
    # Xcode 6 supports C++14 syntax but its libc++ predates make_unique/clamp.
    # Public compatibility headers supply the missing standard-library facilities.
    text = re.sub(r'for\s*\((const )?auto& \[(\w+), (\w+)\] : ([^\n]+)\)\s*\{',
                  lambda m: 'for ('+(m[1] or '')+'auto& ios_pair : '+m[4]+') {\n    '+(m[1] or '')+'auto& '+m[2]+' = ios_pair.first;\n    '+(m[1] or '')+'auto& '+m[3]+' = ios_pair.second;', text)
    # fmt 7 accepts runtime format strings directly; fmt::runtime was added later.
    while 'fmt::runtime(' in text:
        start = text.index('fmt::runtime(')
        inner = start + len('fmt::runtime(')
        depth, end = 1, inner
        while depth:
            if text[end] == '(':
                depth += 1
            elif text[end] == ')':
                depth -= 1
            end += 1
        text = text[:start] + text[inner:end - 1] + text[end:]
    if relative == 'video/color.hpp':
        definitions = re.findall(r'^inline (const Color Color::.*;)$', text, re.M)
        write('src/video/ios_color_constants.cpp', '#include "video/color.hpp"\n' + '\n'.join(definitions) + '\n')
        text = re.sub(r'^inline const Color Color::.*;\n?', '', text, flags=re.M)
    if relative == 'supertux/colorscheme.cpp':
        text = text.replace('Color Statistics::special_color = Color::CYAN;', 'Color Statistics::special_color(0.f, 1.f, 1.f);')
    if relative == 'object/cloud_particle_system.cpp':
        text += '\nconstexpr int CloudParticleSystem::min_amount;\nconstexpr int CloudParticleSystem::max_amount;\n'
    if relative == 'object/rain_particle_system.cpp':
        text += '\nconstexpr float RainParticleSystem::min_amount;\nconstexpr float RainParticleSystem::max_amount;\nconstexpr float RainParticleSystem::fog_max_value;\n'
    if relative == 'video/canvas.cpp':
        start = text.index('    std::visit(')
        end = text.index('    }, request.request);', start) + len('    }, request.request);')
        methods = ['draw_texture', 'draw_gradient', 'draw_filled_rect', 'draw_inverse_ellipse', 'draw_line', 'draw_triangle', 'get_pixel']
        text = text[:start] + '    switch (request.request.index()) {\n' + ''.join('      case %d: painter.%s(request); break;\n' % (i, method) for i, method in enumerate(methods)) + '    }' + text[end:]
    if relative == 'supertux/game_object_iterator.hpp':
        pattern = r'if constexpr \(std::is_base_of<GameObject, T>::value\)\s*\{\s*m_object = static_cast<T\*>\(\*m_it\);\s*\}\s*else\s*\{\s*m_object = dynamic_cast<T\*>\(\*m_it\);\s*assert\(m_object\);\s*\}'
        text, n = re.subn(pattern, 'm_object = cast_object<T>(*m_it);\n      assert(m_object);', text)
        assert n == 2
        text = text.replace('  Iterator m_it;', '''  template<typename U>
  static typename std::enable_if<std::is_base_of<GameObject, U>::value, U*>::type
  cast_object(GameObject* object) { return static_cast<U*>(object); }

  template<typename U>
  static typename std::enable_if<!std::is_base_of<GameObject, U>::value, U*>::type
  cast_object(GameObject* object) { return dynamic_cast<U*>(object); }

  Iterator m_it;''')
    if relative == 'gui/item_color_picker_2d.cpp':
        text = text.replace('if constexpr (SDL_BYTEORDER == SDL_BIG_ENDIAN)', 'if (SDL_BYTEORDER == SDL_BIG_ENDIAN)')
    if relative == 'supertux/main.cpp':
        text = '#include "video/compositor.hpp"\n#include "ios_options.hpp"\n#include "ios_extras.hpp"\nextern "C" void supertux_ios_show_loading(void);\n' + text
        marker = '  m_sdl_subsystem.reset(new SDLSubsystem());'
        text = text.replace(marker, '''  g_config->mobile_controls = true;
  g_config->touch_controls_visible = true;
  g_config->use_fullscreen = true;
  g_config->fullscreen_size = Size(0, 0);
  g_config->aspect_size = Size(0, 0);
  g_config->magnification = 0.f;
  g_config->video = VideoSystem::VIDEO_SDL;
  g_config->window_resizable = false;
  g_config->custom_mouse_cursor = false;
  g_config->custom_system_cursor = false;
  g_config->fancy_gfx = false;
  g_config->developer_mode = false;
  g_config->disable_network = true;
  g_config->do_release_check = false;
  Compositor::s_render_lighting = false;
  SDL_SetHint(SDL_HINT_RENDER_DRIVER, "opengles2");
  SDL_SetHint(SDL_HINT_ORIENTATIONS, "LandscapeLeft LandscapeRight");
  SDL_SetHint(SDL_HINT_IDLE_TIMER_DISABLED, "1");
  SDL_SetHint(SDL_HINT_TOUCH_MOUSE_EVENTS, "0");
  SDL_SetHint(SDL_HINT_MOUSE_TOUCH_EVENTS, "0");
''' + marker)
        text = text.replace(marker, marker + '\n  ios_options::load();\n  (void)ios_extras::compact_phone();')
        text = text.replace('  init_video();', '  init_video();\n  supertux_ios_show_loading();')
        text = text.replace('  m_savegame = std::make_unique<Savegame>(m_profile_manager->get_current_profile(), "");', '  m_savegame = Savegame::from_current_profile("");')
        start = text.index('  if (!args.filenames.empty())', text.index('Main::launch_game'))
        end = text.index('  m_screen_manager->run();', start)
        text = text[:start] + '  m_screen_manager->push_screen(std::make_unique<TitleScreen>(*m_savegame, g_config->is_christmas()));\n' + text[end:]
        # iOS app resources live inside the flat .app bundle.
        text = text.replace('  if (m_forced_datadir)\n', '  if (!m_forced_datadir) {\n    char* base = SDL_GetBasePath();\n    if (!base) throw std::runtime_error("SDL_GetBasePath failed");\n    m_forced_datadir = std::string(base) + "data";\n    SDL_free(base);\n  }\n\n  if (m_forced_datadir)\n', 1)
        text = text.replace('#ifndef __HAIKU__', '#if !defined(__HAIKU__) && !defined(SUPERTUX_IOS6)')
    if relative in ('supertux/menu/game_menu.cpp', 'supertux/menu/worldmap_menu.cpp'):
        text = '#include "ios_options.hpp"\n' + text
        text = text.replace('  add_submenu(_("Options"), MenuStorage::INGAME_OPTIONS_MENU);',
                            '  add_entry("Options", [] { MenuManager::instance().push_menu(ios_options::create_menu(false)); });')

    if relative == 'supertux/menu/options_menu.cpp':
        start = text.index('      add_toggle(MNID_FRAME_PREDICTION,')
        end = text.index('      add_toggle(MNID_FANCY_GFX,', start)
        text = text[:start] + text[end:]
        start = text.index('      add_submenu(_("Change Video System"),')
        end = text.index('      break;', start)
        text = text[:start] + '      add_inactive("Video System: SDL (iOS)");\n' + text[end:]
    if relative == 'supertux/menu/main_menu.cpp':
        text = '#include "ios_extras.hpp"\n#include "ios_options.hpp"\n' + text
        text = text.replace('  add_entry(MNID_WORLDSET_CONTRIB, _("Contrib Levels"));', '  add_entry(MNID_WORLDSET_CONTRIB, _("Contrib Levels"));\n  if (ios_extras::all_levels_unlocked()) add_entry("All Levels", [] { ios_extras::show_all_levels(); });')
        text = text.replace('  add_submenu(_("Options"), MenuStorage::OPTIONS_MENU);',
                            '  add_entry("Options", [] { MenuManager::instance().push_menu(ios_options::create_menu()); });')
        text = text.replace('  add_submenu(_("Add-ons"), MenuStorage::ADDON_MENU);', '')
    if relative == 'util/file_system.cpp':
        text = text.replace('#include <curl/curl.h>', '#ifdef HAVE_CURL\n#include <curl/curl.h>\n#endif')
        text = text.replace('#include <SDL2/SDL_version.h>', '#include <SDL_version.h>')
        text = text.replace('#ifdef __ANDROID__\n', '#ifdef SUPERTUX_IOS6\n  (void)path;\n  return;\n#elif defined(__ANDROID__)\n', 1)
        text = text.replace('#if !defined(ANDROID) && !defined(EMSCRIPTEN)', '#if !defined(ANDROID) && !defined(EMSCRIPTEN) && !defined(SUPERTUX_IOS6)')
    return text

def main():
    write('ios_display_layout.hpp', (HERE / 'port/ios_display_layout.hpp').read_text())
    write('ios_lifecycle.hpp', (HERE / 'port/ios_lifecycle.hpp').read_text())
    write('ios_pixels.hpp', (HERE / 'port/ios_pixels.hpp').read_text())
    write('ios_compact_device.h', (HERE / 'port/ios_compact_device.h').read_text())
    write('ios_extras.hpp', (HERE / 'port/ios_extras.hpp').read_text())
    write('src/supertux/menu/ios_extras.cpp', (HERE / 'port/ios_extras.cpp').read_text())
    level_paths = sorted(p.relative_to(ROOT / 'data').as_posix() for p in (ROOT / 'data/levels').rglob('*.stl'))
    write('ios_level_paths.hpp', '#pragma once\nstatic const char* const bundled_level_paths[] = {\n' + ',\n'.join(json.dumps(p) for p in level_paths) + '\n};\n')
    write('ios_options.hpp', (HERE / 'port/ios_options.hpp').read_text())
    write('src/supertux/menu/ios_options.cpp', (HERE / 'port/ios_options.cpp').read_text())
    changed = {}
    for p in (ROOT / 'src').rglob('*'):
        if p.suffix not in ('.cpp', '.hpp', '.h', '.c'):
            continue
        relative = p.relative_to(ROOT / 'src').as_posix()
        original = p.read_text(encoding='utf-8-sig')
        updated = prepare_source(relative, original)
        write('src/' + relative, updated)
        if updated != original:
            changed[relative] = {'upstream_sha256': hashlib.sha256(p.read_bytes()).hexdigest()}
    write('source-changes.json', json.dumps(changed, indent=2) + '\n')
    write('config.h', '''#pragma once
#define SUPERTUX_IOS6 1
#define PACKAGE_NAME "supertux2"
#define INSTALL_SUBDIR_BIN ""
#define INSTALL_SUBDIR_SHARE "data"
#define BUILD_DATA_DIR "/__supertux_not_a_source_build__"
#define BUILD_CONFIG_DATA_DIR "/__supertux_not_a_source_build__"
#define HIDE_NONMOBILE_OPTIONS 1
#define REMOVE_QUIT_BUTTON 1
#define ICONV_CONST
''')
    write('version.h', '#pragma once\n#define PACKAGE_VERSION "0.7.0-ios6-0.10"\n#define PACKAGE_VERSION_TAG "0.7.0"\n#define LOGO_FILE "images/engine/menu/logo.png"\n')
    print('Prepared isolated source: %d files with port changes.' % len(changed))

if __name__ == '__main__':
    main()
