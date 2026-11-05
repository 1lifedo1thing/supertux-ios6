#pragma once
#include <memory>
class Menu;
namespace ios_options {
bool is_tablet();
void load();
void save();
float hud_scale();
float control_scale();
std::unique_ptr<Menu> create_menu(bool complete = true);
}
