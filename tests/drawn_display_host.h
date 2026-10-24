#pragma once

#include "esphome/components/display/display.h"
#include <chrono>
#include <cstdio>
#include <cstdlib>

// This replaces only the panel transport. ESPHome owns fonts, images, text,
// lines, clipping, colours and the candidate's actual page lambda.
class ProofDisplay : public esphome::display::Display {
 public:
  unsigned char pixels[296 * 128]{};
  unsigned writes = 0;
  void draw_pixel_at(int x, int y, esphome::Color color) override {
    if (x < 0 || y < 0 || x >= 296 || y >= 128 || this->is_point_clipped(x, y)) return;
    pixels[y * 296 + x] = color.is_on() ? 0 : 255;
    ++writes;
  }
  void update() override {}
  esphome::display::DisplayType get_display_type() override {
    return esphome::display::DisplayType::DISPLAY_TYPE_BINARY;
  }
  void save(const char *path) {
    FILE *file = std::fopen(path, "wb");
    if (!file) std::exit(2);
    std::fprintf(file, "P5\n296 128\n255\n");
    if (std::fwrite(pixels, 1, sizeof(pixels), file) != sizeof(pixels)) std::exit(2);
    if (std::fclose(file)) std::exit(2);
  }
 protected:
  int get_width_internal() override { return 296; }
  int get_height_internal() override { return 128; }
};

struct ProofSensor {
  float state;
  bool present;
  bool has_state() const { return present; }
};
struct ProofTime {
  esphome::ESPTime now() const {
    if (std::getenv("SMART_PLANT_CLOCK_VALID"))
      return esphome::ESPTime::from_epoch_utc(1792843200);
    return {};
  }
};
