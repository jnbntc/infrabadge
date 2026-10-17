#include "ib_ui.h"
#include <string.h>

const char *ib_ui_status_name(ib_status_t status)
{
    static const char *const names[] = {"HEALTHY", "WARNING", "CRITICAL", "OFFLINE"};
    return (unsigned)status < IB_STATUS_COUNT ? names[status] : "UNKNOWN";
}

bool ib_ui_mock(unsigned scenario, ib_ui_model_t *model)
{
    if (!model || scenario >= IB_STATUS_COUNT) return false;
    memset(model, 0, sizeof(*model));
    model->status = (ib_status_t)scenario;
    model->nodes = 12;
    model->healthy = 12;
    model->battery_mv = 4005;
    model->temperature_centi = 2395;
    model->humidity_centi = 4660;
    model->simulated = true;
    model->clock_synced = false;
    switch (model->status) {
    case IB_WARNING:
        model->healthy = 11; model->warnings = 1; model->alert_count = 1;
        model->alerts[0] = (ib_ui_alert_t){"CPU ALTA", "NODO-02 / CPU 84%"};
        break;
    case IB_CRITICAL:
        model->healthy = 10; model->critical = 2; model->alert_count = 2;
        model->alerts[0] = (ib_ui_alert_t){"SERVICIO CAIDO", "NODO-03 / API"};
        model->alerts[1] = (ib_ui_alert_t){"DISCO LLENO", "NODO-07 / USO 99%"};
        break;
    case IB_OFFLINE:
        model->healthy = 0; model->unavailable = 12; model->alert_count = 2;
        model->alerts[0] = (ib_ui_alert_t){"SIN DATOS EN VIVO", "ESCENARIO OFFLINE"};
        model->alerts[1] = (ib_ui_alert_t){"DATOS NO VIGENTES", "NO INFERIR SALUD"};
        break;
    default: break;
    }
    return true;
}

void ib_ui_reduce(ib_ui_state_t *state, unsigned events)
{
    if (!state || (events & IB_UI_SLEEP)) return;
    if (events & IB_UI_NEXT) state->screen = (ib_screen_t)(((unsigned)state->screen + 1) % IB_SCREEN_COUNT);
    if (events & IB_UI_DEMO) state->scenario = (state->scenario + 1) % IB_STATUS_COUNT;
}
