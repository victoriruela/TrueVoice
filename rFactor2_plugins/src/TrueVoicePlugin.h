//───────────────────────────────────────────────────────────────────────
// TrueVoicePlugin.h — rFactor 2 plugin for TrueVoice event capture.
//───────────────────────────────────────────────────────────────────────
#ifndef TRUEVOICE_PLUGIN_H
#define TRUEVOICE_PLUGIN_H

#include "InternalsPlugin.hpp"
#include "EventDetector.h"
#include "JsonWriter.h"
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
    bool WantsScoringUpdates() override { return true; }
    void UpdateScoring(const ScoringInfoV01& info) override;

    long WantsTelemetryUpdates() override { return 2; }  // 2 = all vehicles
    void UpdateTelemetry(const TelemInfoV01& info) override;

    // Environment — to get UserData path
    void SetEnvironment(const EnvironmentInfoV01& info) override;

private:
    EventDetector m_detector;
    JsonWriter    m_writer;
    std::string   m_userDataPath;
    std::string   m_outputPath;
    bool          m_inRealtime = false;
    bool          m_sessionActive = false;
};

#endif // TRUEVOICE_PLUGIN_H
