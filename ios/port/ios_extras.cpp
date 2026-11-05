#include "ios_extras.hpp"
#include "ios_level_paths.hpp"
#include <algorithm>
#include <memory>
#include <string>
#include <vector>
#include <physfs.h>
#include "control/controller.hpp"
#include "gui/dialog.hpp"
#include "gui/menu.hpp"
#include "gui/menu_manager.hpp"
#include "supertux/game_manager.hpp"
#include "supertux/level_parser.hpp"
#include "supertux/profile.hpp"
#include "supertux/profile_manager.hpp"
#include "supertux/world.hpp"
#include "util/reader_document.hpp"
#include "util/reader_mapping.hpp"
#include "util/writer.hpp"
#include "util/log.hpp"

extern "C" int supertux_ios_compact_phone(void);
namespace ios_extras {
namespace {
int cached_profile = -1;
bool unlocked = false;
bool wide_cinematic_view = false;
std::string unlock_file() {
  return ProfileManager::current()->get_current_profile().get_basedir() + "/ios-unlocks.stcfg";
}
void unlock_all() {
  all_levels_unlocked();
  Writer writer(unlock_file());
  writer.start_list("ios-unlocks");
  writer.write("all-levels", true);
  writer.end_list("ios-unlocks");
  unlocked = true;
  Dialog::show_message("All levels unlocked!\nChoose All Levels on the title screen.");
}
class LevelList final : public Menu {
public:
  void menu_action(MenuItem&) override {}
  explicit LevelList(const std::string& directory) {
    add_label(directory); add_hl();
    for (const char* item : bundled_level_paths) {
      const std::string path(item);
      const auto slash = path.find_last_of('/');
      if (path.substr(0, slash) != directory) continue;
      const std::string filename = path.substr(slash + 1);
      add_entry(LevelParser::get_level_name(path), [directory, filename] {
        auto world = World::from_directory(directory);
        const std::string level = filename;
        MenuManager::instance().clear_menu_stack();
        GameManager::current()->start_level(*world, level);
      });
    }
    add_hl(); add_back("Back");
  }
};
class AllLevels final : public Menu {
public:
  void menu_action(MenuItem&) override {}
  AllLevels() {
    add_label("All Levels"); add_hl();
    std::vector<std::string> groups;
    for (const char* item : bundled_level_paths) {
      std::string path(item); path.resize(path.find_last_of('/'));
      if (std::find(groups.begin(), groups.end(), path) == groups.end()) groups.push_back(path);
    }
    for (const auto& directory : groups)
      add_entry(directory.substr(7), [directory] {
        MenuManager::instance().push_menu(std::unique_ptr<Menu>(new LevelList(directory)));
      });
    add_hl(); add_back("Back");
  }
};
}
bool compact_phone() {
  static const bool compact = supertux_ios_compact_phone() != 0;
  return compact;
}
bool cinematic_view() { return wide_cinematic_view; }
bool set_cinematic_view(bool value) {
  value = compact_phone() && value;
  if (wide_cinematic_view == value) return false;
  wide_cinematic_view = value;
  return true;
}
bool all_levels_unlocked() {
  const int profile = ProfileManager::current()->get_current_profile().get_id();
  if (profile != cached_profile) {
    cached_profile = profile; unlocked = false;
    try {
    if (PHYSFS_exists(unlock_file().c_str())) {
      auto document = ReaderDocument::from_file(unlock_file());
      auto root = document.get_root();
      if (root.get_name() == "ios-unlocks") root.get_mapping().get("all-levels", unlocked);
    }
    } catch (const std::exception& error) { log_warning << error.what() << std::endl; unlocked = false; }
  }
  return unlocked;
}
void credits_input(const Controller& controller, bool enabled) {
  static CreditsCode code;
  if (!enabled) { code.reset(); return; }
  const Control controls[] = {Control::UP, Control::DOWN, Control::LEFT, Control::RIGHT, Control::ACTION, Control::JUMP};
  // Prefer the expected code button when multiple controls arrive together.
  const int expected = code.next();
  if (controller.pressed(controls[expected])) {
    if (code.push(expected)) unlock_all();
    return;
  }
  for (int i = 0; i < 6; ++i) if (controller.pressed(controls[i])) { code.push(i); break; }
}
void show_all_levels() {
  if (all_levels_unlocked()) MenuManager::instance().push_menu(std::unique_ptr<Menu>(new AllLevels()));
}
}
