#include "ib_ui.h"

void ib_ui_input_init(ib_ui_input_t *input, bool boot, bool power, uint32_t now_ms)
{
    if (!input) return;
    input->boot = (ib_ui_button_t){boot, boot, !boot, now_ms, now_ms};
    input->power = (ib_ui_button_t){power, power, !power, now_ms, now_ms};
}

static unsigned poll(ib_ui_button_t *button, bool pressed, uint32_t now, bool power)
{
    if (pressed != button->raw) { button->raw = pressed; button->changed_ms = now; }
    if (pressed == button->stable || (uint32_t)(now - button->changed_ms) < IB_UI_DEBOUNCE_MS)
        return IB_UI_NONE;
    button->stable = pressed;
    if (pressed) { button->pressed_ms = now; return IB_UI_NONE; }
    unsigned event = IB_UI_NONE;
    if (button->armed) {
        event = !power ? IB_UI_NEXT :
            ((uint32_t)(now - button->pressed_ms) >= IB_UI_LONG_PRESS_MS ? IB_UI_SLEEP : IB_UI_DEMO);
    }
    button->armed = true; /* A button held across wake must first be released. */
    return event;
}

unsigned ib_ui_input_poll(ib_ui_input_t *input, bool boot, bool power, uint32_t now_ms)
{
    if (!input) return IB_UI_NONE;
    return poll(&input->boot, boot, now_ms, false) | poll(&input->power, power, now_ms, true);
}
