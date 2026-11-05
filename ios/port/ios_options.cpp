#include "ios_options.hpp"
#include "ios_display_layout.hpp"
#include <physfs.h>
#include "gui/menu.hpp"
#include "gui/menu_item.hpp"
#include "gui/menu_manager.hpp"
#include "supertux/gameconfig.hpp"
#include "supertux/globals.hpp"
#include "supertux/menu/options_menu.hpp"
#include "util/log.hpp"
#include "util/reader_document.hpp"
#include "util/reader_mapping.hpp"
#include "util/writer.hpp"

extern "C" int supertux_ios_is_tablet(void);

namespace ios_options {
namespace {
int hud_size = 1;
int button_size = 1;
const float button_sizes[] = {1.f, 1.3f, 1.6f};
const char* prefs_file = "ios-options.stcfg";
enum Page { ROOT, DISPLAY, CONTROLS };
enum Item { HUD_SIZE = 100, BUTTON_SIZE, FPS, TOUCH_VISIBLE };

void apply_sizes()
{
  hud_size = std::max(0, std::min(2, hud_size));
  button_size = std::max(0, std::min(2, button_size));
  g_config->m_mobile_controls_scale = button_sizes[button_size];
}

class IOSOptionsMenu final : public Menu {
public:
  explicit IOSOptionsMenu(Page page, bool complete = true)
  {
    if (page == ROOT) {
      add_label("Options");
      add_hl();
      const auto native = [this, complete](const char* label, OptionsMenu::Type type) {
        add_entry(label, [type, complete] {
          MenuManager::instance().push_menu(std::make_unique<OptionsMenu>(type, complete));
        });
      };
      if (complete) native("Locale", OptionsMenu::LOCALE);
      native("Video", OptionsMenu::VIDEO);
      native("Audio", OptionsMenu::AUDIO);
      native("Controls", OptionsMenu::CONTROLS);
      native("Extras", OptionsMenu::EXTRAS);
      native("Advanced", OptionsMenu::ADVANCED);
      add_entry("HUD", [] {
        MenuManager::instance().push_menu(std::unique_ptr<Menu>(new IOSOptionsMenu(DISPLAY)));
      });
      add_entry("Touch Controls", [] {
        MenuManager::instance().push_menu(std::unique_ptr<Menu>(new IOSOptionsMenu(CONTROLS)));
      });
    } else if (page == DISPLAY) {
      add_label("HUD");
      add_hl();
      add_string_select(HUD_SIZE, "HUD Size", &hud_size, {"Small", "Medium", "Large"});
      add_toggle(FPS, "Show FPS", &g_config->show_fps);
    } else {
      add_label("Touch Controls");
      add_hl();
      add_string_select(BUTTON_SIZE, "Button Size", &button_size, {"Small", "Medium", "Large"});
      add_toggle(TOUCH_VISIBLE, "Show Buttons", &g_config->touch_controls_visible);
    }
    add_hl();
    add_back("Back");
  }

  ~IOSOptionsMenu() override { save(); }
  void menu_action(MenuItem&) override
  {
    apply_sizes();
    save();
  }
};
}

bool is_tablet()
{
  static const bool tablet = supertux_ios_is_tablet() != 0;
  return tablet;
}

float hud_scale() { return ios_display::hud_scale(is_tablet(), hud_size); }
float control_scale() { return ios_display::control_scale(is_tablet(), g_config->m_mobile_controls_scale); }

void load()
{
  g_config->frame_prediction = true;
  g_config->touch_controls_visible = true;
  if (PHYSFS_exists(prefs_file)) {
    try {
      auto document = ReaderDocument::from_file(prefs_file);
      auto root = document.get_root();
      if (root.get_name() == "ios-options") {
        auto reader = root.get_mapping();
        reader.get("hud-size", hud_size);
        reader.get("button-size", button_size);
        reader.get("show-fps", g_config->show_fps);
        reader.get("show-buttons", g_config->touch_controls_visible);
      }
    } catch (const std::exception& e) {
      log_warning << "iOS options: " << e.what() << std::endl;
    }
  }
  g_config->frame_prediction = true;
  apply_sizes();
}

void save()
{
  g_config->frame_prediction = true;
  try {
    Writer writer(prefs_file);
    writer.start_list("ios-options");
    writer.write("hud-size", hud_size);
    writer.write("button-size", button_size);
    writer.write("smooth-scrolling", g_config->frame_prediction);
    writer.write("show-fps", g_config->show_fps);
    writer.write("show-buttons", g_config->touch_controls_visible);
    writer.end_list("ios-options");
    g_config->save();
  } catch (const std::exception& e) {
    log_warning << "Saving iOS options: " << e.what() << std::endl;
  }
}

std::unique_ptr<Menu> create_menu(bool complete) { return std::unique_ptr<Menu>(new IOSOptionsMenu(ROOT, complete)); }
}
