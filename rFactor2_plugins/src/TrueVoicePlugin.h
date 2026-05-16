//───────────────────────────────────────────────────────────────────────
// TrueVoicePlugin.h — rFactor 2 plugin for TrueVoice event capture.
//───────────────────────────────────────────────────────────────────────
#ifndef TRUEVOICE_PLUGIN_H
#define TRUEVOICE_PLUGIN_H

#include "InternalsPlugin.hpp"
#include "EventDetector.h"
#include "JsonWriter.h"
#include <memory>
#include <string>

class TrueVoicePlugin : public InternalsPluginV07
{
public:
    TrueVoicePlugin();
    ~TrueVoicePlugin() override;

    // Game flow
    void Startup(long version) override;
    void Shutdown() override;
    void StartSession() override;
    void EndSession() override;
    void EnterRealtime() override;
    void ExitRealtime() override;

    // We want scoring + telemetry for all vehicles
    bool WantsScoringUpdates() override;
    void UpdateScoring(const ScoringInfoV01& info) override;

    long WantsTelemetryUpdates() override;  // 2 = all vehicles
    void UpdateTelemetry(const TelemInfoV01& info) override;

    // Environment — to get UserData path
    void SetEnvironment(const EnvironmentInfoV01& info) override;

    // Custom variables — appear in rFactor2 plugin settings UI
    bool GetCustomVariable(long i, CustomVariableV01& var) override;
    void AccessCustomVariable(CustomVariableV01& var) override;
    void GetCustomVariableSetting(CustomVariableV01& var, long i, CustomSettingV01& setting) override;

private:
    bool EnsureCoreInitialized();

    std::unique_ptr<EventDetector> m_detector;
    std::unique_ptr<JsonWriter>    m_writer;
    std::string   m_userDataPath;
    std::string   m_outputPath;
    bool          m_inRealtime = false;
    bool          m_sessionActive = false;
    bool          m_enabled = true;
};

#endif // TRUEVOICE_PLUGIN_H
